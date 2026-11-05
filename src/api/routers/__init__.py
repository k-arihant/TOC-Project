"""Routers package for FastAPI."""

from src.api.routers.automata import router as automata_router
from src.api.routers.datasets import router as datasets_router
from src.api.routers.detect import router as detect_router
from src.api.routers.evaluation import router as evaluation_router
from src.api.routers.health import router as health_router
from src.api.routers.ml import router as ml_router
from src.api.routers.packet import router as packet_router
from src.api.routers.workflows import router as workflows_router

__all__ = [
    "health_router",
    "workflows_router",
    "automata_router",
    "datasets_router",
    "ml_router",
    "detect_router",
    "evaluation_router",
    "packet_router",
]
