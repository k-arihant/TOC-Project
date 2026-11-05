"""Pydantic schemas package for API contracts."""

from src.api.schemas.automata import (
    EquivalenceRequest,
    EquivalenceResponse,
    MinimizeRequest,
    MinimizeResponse,
    NfaToDfaRequest,
    NfaToDfaResponse,
    ReachabilityResponse,
    ValidateRequest,
    ValidateResponse,
)
from src.api.schemas.common import ErrorDetail, ErrorResponse, PaginatedResponse, PaginationMeta
from src.api.schemas.datasets import (
    CaseDetailResponse,
    CaseResponse,
    DatasetResponse,
    EventSchema,
    GenerateDatasetRequest,
)
from src.api.schemas.detect import (
    AnalyzeTraceRequest,
    AnalyzeTraceResponse,
    BatchDetectRequest,
    BatchDetectResponse,
    DecisionDetailResponse,
    HybridDecisionResponse,
)
from src.api.schemas.evaluation import (
    EvaluationDetailResponse,
    EvaluationRunRequest,
    EvaluationRunResponse,
)
from src.api.schemas.health import HealthResponse
from src.api.schemas.ml import (
    ModelMetricsResponse,
    ModelRunResponse,
    ScoreDatasetRequest,
    ScoreDatasetResponse,
    TrainModelRequest,
    TrainModelResponse,
)
from src.api.schemas.packet import (
    PacketEventResponse,
    PacketExperimentResponse,
    PacketFlowDetailResponse,
    PacketFlowResponse,
)
from src.api.schemas.workflows import (
    AutomatonResponse,
    AutomatonStateSchema,
    AutomatonTransitionSchema,
    WorkflowResponse,
)

__all__ = [
    "ErrorDetail",
    "ErrorResponse",
    "PaginationMeta",
    "PaginatedResponse",
    "HealthResponse",
    "WorkflowResponse",
    "AutomatonResponse",
    "AutomatonStateSchema",
    "AutomatonTransitionSchema",
    "ValidateRequest",
    "ValidateResponse",
    "NfaToDfaRequest",
    "NfaToDfaResponse",
    "MinimizeRequest",
    "MinimizeResponse",
    "ReachabilityResponse",
    "EquivalenceRequest",
    "EquivalenceResponse",
    "GenerateDatasetRequest",
    "DatasetResponse",
    "CaseResponse",
    "EventSchema",
    "CaseDetailResponse",
    "TrainModelRequest",
    "TrainModelResponse",
    "ModelRunResponse",
    "ScoreDatasetRequest",
    "ScoreDatasetResponse",
    "ModelMetricsResponse",
    "AnalyzeTraceRequest",
    "AnalyzeTraceResponse",
    "BatchDetectRequest",
    "BatchDetectResponse",
    "HybridDecisionResponse",
    "DecisionDetailResponse",
    "EvaluationRunRequest",
    "EvaluationRunResponse",
    "EvaluationDetailResponse",
    "PacketExperimentResponse",
    "PacketFlowResponse",
    "PacketEventResponse",
    "PacketFlowDetailResponse",
]
