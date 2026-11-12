import logging

from fastapi import APIRouter, HTTPException, status

from app.core.config import settings
from app.models.chat import ChatRequest, ChatResponse
from app.services.groq_service import (
    GroqConfigurationError,
    GroqServiceError,
    generate_response,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/debug/config")
def debug_config() -> dict[str, str | bool]:
    return {
        "groq_key_loaded": bool(settings.GROQ_API_KEY),
        "model": settings.GROQ_MODEL,
    }


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        response = generate_response(request.message)
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

    return ChatResponse(response=response)
