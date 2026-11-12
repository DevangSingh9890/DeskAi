from contextlib import asynccontextmanager
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import ENV_FILE, settings
from app.routes.chat import router as chat_router
from app.routes.knowledge_base import router as knowledge_base_router
from app.services.file_service import ensure_uploads_dir

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    ensure_uploads_dir()
    api_key = settings.GROQ_API_KEY
    print("GROQ_API_KEY loaded:", "YES" if api_key else "NO")
    print("GROQ_MODEL:", settings.GROQ_MODEL)
    if api_key:
        logging.getLogger(__name__).info(
            "Groq configuration loaded (API key value omitted)"
        )
    else:
        logging.getLogger(__name__).error(
            "GROQ_API_KEY is missing or empty; checked environment and %s",
            ENV_FILE,
        )
    yield


app = FastAPI(title="AI Service Desk Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.CORS_ORIGINS),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(chat_router, prefix="/api")
app.include_router(knowledge_base_router, prefix="/api/documents", tags=["documents"])


@app.get("/")
def health_check() -> dict[str, str]:
    return {
        "status": "running",
        "service": "AI Service Desk Backend",
    }
