from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.common.config import settings
from src.db.base import Base

# Engine configuration
# If using SQLite, check_same_thread=False is needed for multi-threaded access
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency for obtaining database sessions in API endpoints."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables(bind_engine=None) -> None:
    """Create all tables defined in models if they do not exist."""
    target_engine = bind_engine or engine
    Base.metadata.create_all(bind=target_engine)


def drop_tables(bind_engine=None) -> None:
    """Drop all tables defined in models."""
    target_engine = bind_engine or engine
    Base.metadata.drop_all(bind=target_engine)
