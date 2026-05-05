from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


def _ensure_sqlite_directory() -> None:
    db_path = Path(settings.sqlite_db_path)
    if db_path.parent:
        db_path.parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_directory()

engine = create_engine(
    settings.sqlite_url,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
