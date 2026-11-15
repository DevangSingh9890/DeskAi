import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"
load_dotenv(dotenv_path=ENV_FILE)


def _read_setting(name: str, default: str = "") -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value

    dotenv_value = (dotenv_values(ENV_FILE).get(name) or "").strip()
    return dotenv_value or default


@dataclass(frozen=True)
class Settings:
    GROQ_API_KEY: str
    GROQ_MODEL: str
    GROQ_CA_BUNDLE: str
    EMBEDDING_MODEL: str
    CHROMA_PERSIST_DIRECTORY: Path
    CHROMA_COLLECTION_NAME: str
    RAG_RELEVANCE_THRESHOLD: float
    CORS_ORIGINS: tuple[str, ...]


_default_origins = ("http://localhost:5173", "http://127.0.0.1:5173")
_configured_origins = _read_setting("CORS_ORIGINS")
_configured_chroma_directory = Path(
    _read_setting("CHROMA_PERSIST_DIRECTORY", "./chroma_db")
).expanduser()
if not _configured_chroma_directory.is_absolute():
    _configured_chroma_directory = BACKEND_DIR / _configured_chroma_directory

settings = Settings(
    GROQ_API_KEY=_read_setting("GROQ_API_KEY"),
    GROQ_MODEL=_read_setting("GROQ_MODEL", "openai/gpt-oss-20b"),
    GROQ_CA_BUNDLE=_read_setting("GROQ_CA_BUNDLE"),
    EMBEDDING_MODEL=_read_setting(
        "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    ),
    CHROMA_PERSIST_DIRECTORY=_configured_chroma_directory.resolve(),
    CHROMA_COLLECTION_NAME=_read_setting(
        "CHROMA_COLLECTION_NAME", "deskai_knowledge"
    ),
    RAG_RELEVANCE_THRESHOLD=float(_read_setting("RAG_RELEVANCE_THRESHOLD", "0.35")),
    CORS_ORIGINS=tuple(
        origin.strip().rstrip("/")
        for origin in _configured_origins.split(",")
        if origin.strip()
    )
    or _default_origins,
)
