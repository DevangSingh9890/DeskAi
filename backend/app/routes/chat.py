import logging
from secrets import compare_digest

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import ValidationError

from app.agents.classification_agent import ClassificationAgentError
from app.core.config import settings
from app.graphs.service_desk_graph import run_service_desk_graph
from app.models.agent import AgentChatRequest, AgentChatResponse
from app.models.classification import (
    ClassificationRequest,
    IncidentClassification,
)
from app.models.chat import ChatRequest, ChatResponse
from app.services.file_service import DocumentStorageError, list_documents
from app.services.classification_service import (
    ClassificationServiceError,
    classify_incident,
)
from app.services.groq_service import (
    GroqConfigurationError,
    GroqServiceError,
    GroqTimeoutError,
    generate_response,
    generate_refined_response,
)
from app.services.rag_service import (
    VectorStoreError,
    get_embedding_warmup_status,
    is_embedding_model_loaded,
    search_knowledge,
    warm_up_embedding_service,
)
from app.services.ticket_service import TicketServiceError

logger = logging.getLogger(__name__)
router = APIRouter()

NO_KNOWLEDGE_RESPONSE = "I could not find this information in the knowledge base."


@router.get("/debug/config")
def debug_config() -> dict[str, str | bool]:
    return {
        "groq_key_loaded": bool(settings.GROQ_API_KEY),
        "model": settings.GROQ_MODEL,
    }


@router.get("/debug/performance")
def debug_performance() -> dict[str, bool | int | str | None]:
    try:
        documents = list_documents()
    except DocumentStorageError as exc:
        logger.exception("Could not read document count for performance diagnostics")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document performance data is unavailable.",
        ) from exc

    warmup = get_embedding_warmup_status()
    return {
        "warming": warmup["warming"],
        "embedding_model_loaded": warmup["embedding_model_loaded"],
        "warmup_started_at": warmup["warmup_started_at"],
        "warmup_completed_at": warmup["warmup_completed_at"],
        "warmup_status": warmup["warmup_status"],
        "warmup_error": warmup["warmup_error"],
        "model": settings.EMBEDDING_MODEL,
        "model_loaded": is_embedding_model_loaded(),
        "model_name": settings.EMBEDDING_MODEL,
        "documents_indexed": sum(
            document.ingestion_status == "Indexed" for document in documents
        ),
    }


@router.post("/admin/warmup")
def warm_up_model(
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
) -> dict[str, bool | str]:
    if not settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model warm-up is disabled; configure ADMIN_API_KEY.",
        )
    if x_admin_key is None or not compare_digest(
        x_admin_key.encode("utf-8"), settings.ADMIN_API_KEY.encode("utf-8")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid X-Admin-Key header is required.",
        )

    try:
        warm_up_embedding_service()
    except VectorStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The embedding model is unavailable.",
        ) from exc

    return {"status": "ready", "model_loaded": True}


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


@router.post("/agent/chat", response_model=AgentChatResponse)
def agent_chat(request: AgentChatRequest) -> AgentChatResponse:
    if request.refinement_context is not None:
        refinement = request.refinement_context
        logger.info("Agent chat refinement started using supplied retrieval context")
        try:
            response = generate_refined_response(
                request.message,
                refinement,
            )
        except GroqConfigurationError as exc:
            logger.error("Groq API is not configured for response refinement: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The AI service is not configured.",
            ) from exc
        except GroqTimeoutError as exc:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=(
                    "The Groq service did not complete the refined response "
                    "within its 25-second request limit."
                ),
            ) from exc
        except GroqServiceError as exc:
            logger.exception("Groq failed while refining a service-desk response")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The AI service could not generate a refined response.",
            ) from exc

        return AgentChatResponse(
            classification=refinement.classification,
            knowledge_sources=refinement.knowledge_sources,
            knowledge_results=refinement.knowledge_results,
            troubleshooting=refinement.troubleshooting,
            response=response,
            ticket_recommendation=refinement.ticket_recommendation,
            similar_tickets=refinement.similar_tickets,
            ticket_status=refinement.ticket_status,
        )

    try:
        state = run_service_desk_graph(request.message)
    except GroqConfigurationError as exc:
        logger.error("Groq API is not configured for agent orchestration: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The AI service is not configured.",
        ) from exc
    except VectorStoreError as exc:
        logger.exception("Agent knowledge retrieval failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The knowledge base is unavailable.",
        ) from exc
    except TicketServiceError as exc:
        logger.exception("Agent ticket tools are unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The ticket service is unavailable.",
        ) from exc
    except GroqTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="The Groq service did not complete the response in time.",
        ) from exc
    except (ClassificationAgentError, GroqServiceError, ValidationError) as exc:
        logger.exception("Service-desk agent graph failed")
        detail = (
            f"Service-desk agent workflow failed: {exc}"
            if settings.APP_ENV == "development"
            else "The service-desk agent workflow failed."
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail,
        ) from exc

    return AgentChatResponse(
        classification=state.get("classification", {}),
        knowledge_sources=state.get("knowledge", {}).get("sources", []),
        knowledge_results=state.get("knowledge", {}).get("chunks", []),
        troubleshooting=state.get("troubleshooting", {}),
        response=state.get("final_response", {}).get("response", ""),
        ticket_recommendation=state.get("ticket_recommendation"),
        similar_tickets=state.get("similar_tickets", []),
        ticket_status=state.get("ticket_status"),
    )


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
