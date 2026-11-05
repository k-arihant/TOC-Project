"""FastAPI dependencies and security helpers."""

from typing import Optional

from fastapi import Header, HTTPException, status
from sqlalchemy.orm import Session

from src.common.config import settings
from src.db.session import get_db


def get_db_session() -> Session:
    """Dependency for injecting SQLAlchemy session."""
    return next(get_db())


def verify_api_key(x_api_key: Optional[str] = Header(None)) -> None:
    """Validate X-API-Key header if API_KEY is configured."""
    if settings.API_KEY and settings.API_KEY.strip():
        if not x_api_key or x_api_key != settings.API_KEY:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "UNAUTHORIZED", "message": "Invalid or missing X-API-Key header"},
            )
