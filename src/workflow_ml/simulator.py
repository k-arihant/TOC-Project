"""Workflow trace simulator generating reproducible process executions with log-normal timing."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import yaml

from src.common.types import Event, Trace

DEFAULT_CONFIG_PATH = Path("config/simulator.yaml")


@dataclass
class SimulatedCase:
    trace: Trace
    label_class: str  # "normal" | "valid_variation"
    anomaly_type: str  # "none"


def load_simulator_config(path: Optional[str | Path] = None) -> Dict[str, Any]:
    """Load simulator configuration YAML."""
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not cfg_path.exists():
        raise FileNotFoundError(f"Simulator config not found: {cfg_path}")
    with open(cfg_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


class WorkflowSimulator:
    """Simulator generating valid process executions with realistic timing."""

    def __init__(self, config: Optional[Dict[str, Any]] = None, seed: int = 0):
        self.config = config or load_simulator_config()
        self.seed = seed
        self.rng = np.random.default_rng(seed)

        self.paths_cfg = self.config.get("paths", {})
        self.timing_cfg = self.config.get("timing", {})
        self.default_median = float(self.timing_cfg.get("default_median_sec", 300.0))
        self.default_sigma = float(self.timing_cfg.get("default_sigma", 0.5))
        self.gaps_cfg = self.timing_cfg.get("gaps", {})

    def _sample_gap_seconds(self, from_activity: str, to_activity: str) -> float:
        """Sample inter-event time gap from log-normal distribution."""
        key = f"{from_activity}_to_{to_activity}"
        gap_params = self.gaps_cfg.get(key, {})
        median_sec = float(gap_params.get("median_sec", self.default_median))
        sigma = float(gap_params.get("sigma", self.default_sigma))

        # For LogNormal, median = exp(mu) => mu = ln(median)
        mu = np.log(max(1.0, median_sec))
        gap = float(self.rng.lognormal(mean=mu, sigma=sigma))
        return max(0.5, gap)

    def _sample_activities(self) -> Tuple[List[str], str]:
        """Sample a valid complete sequence of activities and determine class."""
        path_choices = [
            "happy_path",
            "retry_success",
            "cancel_before_paid",
            "cancel_after_paid",
            "delivered_refund",
        ]
        weights = [
            float(self.paths_cfg.get("happy_path", 0.65)),
            float(self.paths_cfg.get("retry_success", 0.15)),
            float(self.paths_cfg.get("cancel_before_paid", 0.05)),
            float(self.paths_cfg.get("cancel_after_paid", 0.05)),
            float(self.paths_cfg.get("delivered_refund", 0.05)),
        ]
        total_w = sum(weights)
        probs = [w / total_w for w in weights]

        chosen_path = self.rng.choice(path_choices, p=probs)

        if chosen_path == "happy_path":
            activities = [
                "OrderCreated",
                "PaymentInitiated",
                "PaymentAuthorized",
                "OrderPacked",
                "OrderShipped",
                "OrderDelivered",
                "OrderClosed",
            ]
            return activities, "normal"

        if chosen_path == "retry_success":
            # 1 or 2 failed payment attempts before success
            n_retries = int(self.rng.choice([1, 2], p=[0.7, 0.3]))
            activities = ["OrderCreated"]
            for _ in range(n_retries):
                activities.extend(["PaymentInitiated", "PaymentFailed"])
            activities.extend(
                [
                    "PaymentInitiated",
                    "PaymentAuthorized",
                    "OrderPacked",
                    "OrderShipped",
                    "OrderDelivered",
                    "OrderClosed",
                ]
            )
            return activities, "valid_variation"

        if chosen_path == "cancel_before_paid":
            # Cancellation from Created or PaymentFailed
            has_failed_attempt = bool(self.rng.choice([False, True], p=[0.6, 0.4]))
            if has_failed_attempt:
                activities = [
                    "OrderCreated",
                    "PaymentInitiated",
                    "PaymentFailed",
                    "OrderCancelled",
                    "OrderClosed",
                ]
            else:
                activities = ["OrderCreated", "OrderCancelled", "OrderClosed"]
            return activities, "valid_variation"

        if chosen_path == "cancel_after_paid":
            # Cancellation from Paid or Packed, followed by refund
            cancel_after_packing = bool(self.rng.choice([False, True], p=[0.5, 0.5]))
            if cancel_after_packing:
                activities = [
                    "OrderCreated",
                    "PaymentInitiated",
                    "PaymentAuthorized",
                    "OrderPacked",
                    "OrderCancelled",
                    "RefundRequested",
                    "RefundCompleted",
                    "OrderClosed",
                ]
            else:
                activities = [
                    "OrderCreated",
                    "PaymentInitiated",
                    "PaymentAuthorized",
                    "OrderCancelled",
                    "RefundRequested",
                    "RefundCompleted",
                    "OrderClosed",
                ]
            return activities, "valid_variation"

        # delivered_refund: Return after delivery with refund
        activities = [
            "OrderCreated",
            "PaymentInitiated",
            "PaymentAuthorized",
            "OrderPacked",
            "OrderShipped",
            "OrderDelivered",
            "RefundRequested",
            "RefundCompleted",
            "OrderClosed",
        ]
        return activities, "valid_variation"

    def generate_case(self, case_id: str, base_time: datetime) -> SimulatedCase:
        """Generate a single complete simulated case with timestamps."""
        activities, label_class = self._sample_activities()

        events: List[Event] = []
        current_time = base_time

        for i, act in enumerate(activities):
            if i > 0:
                gap = self._sample_gap_seconds(activities[i - 1], act)
                current_time += timedelta(seconds=gap)

            events.append(
                Event(
                    case_id=case_id,
                    activity=act,
                    timestamp=current_time,
                )
            )

        trace = Trace(case_id=case_id, events=events)
        return SimulatedCase(trace=trace, label_class=label_class, anomaly_type="none")

    def generate_dataset(
        self,
        n_cases: Optional[int] = None,
        start_time: Optional[datetime] = None,
    ) -> List[SimulatedCase]:
        """Generate a collection of simulated cases."""
        count = n_cases if n_cases is not None else int(self.config.get("n_cases", 1000))
        cur_time = start_time or datetime(2026, 1, 1, 8, 0, 0, tzinfo=timezone.utc)

        cases: List[SimulatedCase] = []
        for i in range(count):
            case_id = f"CASE-{i + 1:05d}"
            # Stagger start times slightly across cases
            case_start = cur_time + timedelta(seconds=float(self.rng.uniform(0, 120)))
            cases.append(self.generate_case(case_id, case_start))

        return cases
