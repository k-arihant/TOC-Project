from typing import Protocol, Sequence

from src.common.types import DetectorScore, Trace


class AnomalyDetector(Protocol):
    name: str

    def fit(self, traces: Sequence[Trace]) -> None:
        """Fit model on normal-only training data (unsupervised)."""
        ...

    def calibrate(self, traces: Sequence[Trace], target_fpr: float) -> None:
        """Calibrate decision threshold on validation normal traces."""
        ...

    def score(self, traces: Sequence[Trace]) -> list[DetectorScore]:
        """Compute anomaly scores for given traces (higher score = more anomalous)."""
        ...

    def to_bytes(self) -> bytes:
        """Serialize detector to bytes."""
        ...

    @classmethod
    def from_bytes(cls, b: bytes) -> "AnomalyDetector":
        """Deserialize detector from bytes."""
        ...
