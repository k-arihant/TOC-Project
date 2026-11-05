"""Health check response schema."""

from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field("ok", description="Service overall health")
    db_connected: bool = Field(True, description="Database connectivity status")
    version: str = Field("1.0.0", description="API version")
    timestamp: datetime = Field(..., description="Timestamp of health check")
