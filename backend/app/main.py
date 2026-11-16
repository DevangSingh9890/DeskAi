import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import ENV_FILE, settings
from app.routes.chat import router as chat_router
from app.routes.knowledge_base import router as knowledge_base_router
from app.routes.rag import router as rag_router
from app.routes.tickets import router as tickets_router
from app.services.file_service import ensure_uploads_dir
from app.services.rag_service import (
    is_embedding_model_loaded,
    recover_interrupted_ingestions,
    start_background_embedding_warmup,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    ensure_uploads_dir()
    recover_interrupted_ingestions()

    api_key = settings.GROQ_API_KEY
    print("GROQ_API_KEY loaded:", "YES" if api_key else "NO")
    print("GROQ_MODEL:", settings.GROQ_MODEL)
    if api_key:
        logger.info("Groq configuration loaded (API key value omitted)")
    else:
        logger.error(
            "GROQ_API_KEY is missing or empty; checked environment and %s",
            ENV_FILE,
        )
    logger.info("Backend started")
    logger.info("Backend startup complete")
    logger.info("Embedding model not loaded yet")
    # Give Uvicorn time to bind and answer readiness probes before ML imports.
    start_background_embedding_warmup(delay_seconds=3.0)
    yield


app = FastAPI(title="AI Service Desk Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.CORS_ORIGINS),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(chat_router, prefix="/api")
app.include_router(knowledge_base_router, prefix="/api/documents", tags=["documents"])
app.include_router(rag_router, prefix="/api/knowledge-base", tags=["knowledge-base"])
app.include_router(tickets_router, prefix="/api", tags=["tickets"])


@app.get("/")
def health_check() -> dict[str, str]:
    return {
        "status": "running",
        "service": "AI Service Desk Backend",
    }


@app.get("/api/health")
def api_health_check() -> dict[str, str | bool]:
    return {
        "backend": "ready",
        "embedding_model_loaded": is_embedding_model_loaded(),
    }
