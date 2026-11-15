import logging

from fastapi import APIRouter, HTTPException, status

from app.core.config import settings
from app.models.classification import (
    ClassificationRequest,
    IncidentClassification,
)
from app.models.chat import ChatRequest, ChatResponse
from app.services.classification_service import (
    ClassificationServiceError,
    classify_incident,
)
from app.services.groq_service import (
    GroqConfigurationError,
    GroqServiceError,
    generate_response,
)
from app.services.rag_service import VectorStoreError, search_knowledge

logger = logging.getLogger(__name__)
router = APIRouter()

NO_KNOWLEDGE_RESPONSE = "I could not find this information in the knowledge base."


@router.get("/debug/config")
def debug_config() -> dict[str, str | bool]:
    return {
        "groq_key_loaded": bool(settings.GROQ_API_KEY),
        "model": settings.GROQ_MODEL,
    }


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    classification = _classify_or_raise(request.message)

    try:
        results = search_knowledge(request.message)
    except VectorStoreError as exc:
        logger.exception("Knowledge-base search failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The knowledge base is unavailable.",
        ) from exc

    if not results:
        return ChatResponse(
            response=NO_KNOWLEDGE_RESPONSE,
            classification=classification,
        )

    context = "\n\n".join(
        f"Source document: {result['metadata'].get('filename', 'Unknown')}\n"
        f"Content: {result['content']}"
        for result in results
    )
    sources = list(
        dict.fromkeys(
            result["metadata"]["filename"]
            for result in results
            if result["metadata"].get("filename")
        )
    )

    try:
        response = generate_response(request.message, context)
    except GroqConfigurationError as exc:
        logger.error("Groq API is not configured: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The AI service is not configured.",
        ) from exc
    except GroqServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to generate a response at this time.",
        ) from exc

    if sources and response != NO_KNOWLEDGE_RESPONSE:
        response = f"{response}\n\nSources: {', '.join(sources)}"
    return ChatResponse(response=response, classification=classification)


@router.post("/classify", response_model=IncidentClassification)
def classify(request: ClassificationRequest) -> IncidentClassification:
    return _classify_or_raise(request.message)


def _classify_or_raise(message: str) -> IncidentClassification:
    try:
        return classify_incident(message)
    except GroqConfigurationError as exc:
        logger.error("Groq API is not configured for incident classification: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The AI service is not configured.",
        ) from exc
    except (GroqServiceError, ClassificationServiceError) as exc:
        logger.exception("Incident classification failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to classify the incident at this time.",
        ) from exc
