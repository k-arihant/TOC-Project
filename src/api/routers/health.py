"""Health check router."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.api.schemas.health import HealthResponse
from src.db.session import get_db

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def get_health(db: Session = Depends(get_db)) -> HealthResponse:
    """Return API and database connectivity status."""
    db_connected = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_connected = False

    return HealthResponse(
        status="ok" if db_connected else "degraded",
        db_connected=db_connected,
        version="1.0.0",
        timestamp=datetime.now(timezone.utc),
    )
