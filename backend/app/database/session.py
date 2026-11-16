from collections.abc import Generator

from sqlalchemy.orm import Session, sessionmaker

from app.database.database import engine

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    if engine is None:
        raise RuntimeError(
            "DATABASE_URL is not configured; ticket persistence requires PostgreSQL."
        )

    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()
