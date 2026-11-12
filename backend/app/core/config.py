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
    CORS_ORIGINS: tuple[str, ...]


_default_origins = ("http://localhost:5173", "http://127.0.0.1:5173")
_configured_origins = _read_setting("CORS_ORIGINS")
settings = Settings(
    GROQ_API_KEY=_read_setting("GROQ_API_KEY"),
    GROQ_MODEL=_read_setting("GROQ_MODEL", "openai/gpt-oss-20b"),
    GROQ_CA_BUNDLE=_read_setting("GROQ_CA_BUNDLE"),
    CORS_ORIGINS=tuple(
        origin.strip().rstrip("/")
        for origin in _configured_origins.split(",")
        if origin.strip()
    )
    or _default_origins,
)
