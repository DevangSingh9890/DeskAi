from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _database_url(url: str) -> URL:
    parsed_url = make_url(url)
    if parsed_url.drivername in {"postgres", "postgresql"}:
        parsed_url = parsed_url.set(drivername="postgresql+psycopg")
    return parsed_url


engine = (
    create_engine(
        _database_url(settings.DATABASE_URL),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
    )
    if settings.DATABASE_URL
    else None
)


def initialize_database() -> None:
    if engine is None:
        raise RuntimeError(
            "DATABASE_URL is not configured; ticket persistence requires PostgreSQL."
        )

    from app.database import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
