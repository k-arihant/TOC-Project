from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


@dataclass(frozen=True)
class Event:
    case_id: str
    activity: str
    timestamp: datetime  # timezone-aware UTC
    attributes: dict = field(default_factory=dict)


@dataclass
class Trace:
    case_id: str
    events: list[Event]  # sorted by (timestamp, original_row_index)

    @property
    def activities(self) -> list[str]:
        return [e.activity for e in self.events]


class FsmVerdict(str, Enum):
    VALID_COMPLETE = "VALID_COMPLETE"  # ends in accepting state
    VALID_PREFIX = "VALID_PREFIX"  # all transitions legal, not yet accepting
    INVALID = "INVALID"  # illegal transition or unknown event


@dataclass
class FsmResult:
    case_id: str
    verdict: FsmVerdict
    state_path: list[str]  # states visited, len = events processed + 1
    fail_index: Optional[int] = None  # 0-based index of offending event
    fail_state: Optional[str] = None
    fail_event: Optional[str] = None
    allowed_events: list[str] = field(default_factory=list)
    reason_code: Optional[str] = None  # ILLEGAL_TRANSITION | UNKNOWN_EVENT | EVENT_AFTER_FINAL


@dataclass
class Factor:  # one human-readable reason element
    name: str
    value: float
    reference: float
    note: str


@dataclass
class DetectorScore:
    case_id: str
    detector: str  # "isolation_forest" | "markov" | "kmeans" | "random_forest"
    raw_score: float  # HIGHER = MORE ANOMALOUS (convention for all detectors)
    norm_score: float  # in [0,1]: ECDF rank vs training-score distribution
    threshold: float  # on norm_score, calibrated on validation data
    is_anomaly: bool
    factors: list[Factor] = field(default_factory=list)


class FinalLabel(str, Enum):
    NORMAL = "NORMAL"
    RULE_VIOLATION = "RULE_VIOLATION"
    STATISTICAL_ANOMALY = "STATISTICAL_ANOMALY"
    IN_PROGRESS = "IN_PROGRESS"


@dataclass
class HybridDecision:
    case_id: str
    final_label: FinalLabel
    fsm: FsmResult
    ml: list[DetectorScore]
    explanation: list[str]  # ordered, human-readable
