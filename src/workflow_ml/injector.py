"""Controlled anomaly injector applying formal rule mutations and statistical anomalies with DFA label verification."""

from datetime import timedelta
from typing import Any, Dict, List, Optional

import numpy as np

from src.automata.dfa import DFA
from src.automata.loader import load_workflow
from src.automata.validator import validate_trace
from src.common.types import Event, FsmVerdict, Trace
from src.workflow_ml.simulator import SimulatedCase


class AnomalyInjector:
    """Mutates valid workflow traces and verifies ground truth labels against the DFA."""

    def __init__(
        self,
        dfa: Optional[DFA] = None,
        config: Optional[Dict[str, Any]] = None,
        seed: int = 0,
    ):
        self.dfa = dfa or load_workflow("workflows/order_payment/workflow.yaml")
        self.config = config or {}
        self.rng = np.random.default_rng(seed)

        anom_cfg = self.config.get("anomalies", {})
        self.anomaly_rate = float(anom_cfg.get("rate", 0.10))
        self.rule_weights = anom_cfg.get(
            "rule_violations",
            {
                "skip_event": 0.18,
                "swap_adjacent": 0.18,
                "duplicate_event": 0.16,
                "insert_random_event": 0.16,
                "event_after_closed": 0.16,
                "replace_event": 0.16,
            },
        )
        self.stat_cfg = anom_cfg.get("statistical_anomalies", {})

        self.alphabet = sorted(self.dfa.alphabet)

    def _mutate_skip_event(self, events: List[Event]) -> List[Event]:
        """Delete one non-first, non-last event."""
        if len(events) <= 2:
            return events
        idx_to_drop = int(self.rng.integers(1, len(events) - 1))
        return [e for i, e in enumerate(events) if i != idx_to_drop]

    def _mutate_swap_adjacent(self, events: List[Event]) -> List[Event]:
        """Swap two neighboring events."""
        if len(events) <= 2:
            return events
        idx = int(self.rng.integers(0, len(events) - 1))
        mutated = list(events)
        # Swap activities while preserving timestamps
        e1, e2 = mutated[idx], mutated[idx + 1]
        mutated[idx] = Event(
            case_id=e1.case_id,
            activity=e2.activity,
            timestamp=e1.timestamp,
            attributes=e1.attributes,
        )
        mutated[idx + 1] = Event(
            case_id=e2.case_id,
            activity=e1.activity,
            timestamp=e2.timestamp,
            attributes=e2.attributes,
        )
        return mutated

    def _mutate_duplicate_event(self, events: List[Event]) -> List[Event]:
        """Repeat an event in place."""
        if not events:
            return events
        idx = int(self.rng.integers(0, len(events)))
        dup_event = events[idx]
        new_event = Event(
            case_id=dup_event.case_id,
            activity=dup_event.activity,
            timestamp=dup_event.timestamp + timedelta(seconds=1),
            attributes=dup_event.attributes,
        )
        mutated = list(events)
        mutated.insert(idx + 1, new_event)
        return mutated

    def _mutate_insert_random_event(self, events: List[Event]) -> List[Event]:
        """Insert a random alphabet symbol."""
        if not events:
            return events
        idx = int(self.rng.integers(1, len(events)))
        sym = str(self.rng.choice(self.alphabet))
        ref_time = events[idx - 1].timestamp
        new_event = Event(
            case_id=events[0].case_id,
            activity=sym,
            timestamp=ref_time + timedelta(seconds=2),
        )
        mutated = list(events)
        mutated.insert(idx, new_event)
        return mutated

    def _mutate_event_after_closed(self, events: List[Event]) -> List[Event]:
        """Append an event after the closed state."""
        if not events:
            return events
        sym = str(self.rng.choice(self.alphabet))
        last_time = events[-1].timestamp
        new_event = Event(
            case_id=events[0].case_id,
            activity=sym,
            timestamp=last_time + timedelta(seconds=30),
        )
        mutated = list(events)
        mutated.append(new_event)
        return mutated

    def _mutate_replace_event(self, events: List[Event]) -> List[Event]:
        """Replace an event with a different alphabet symbol."""
        if len(events) <= 2:
            return events
        idx = int(self.rng.integers(1, len(events) - 1))
        curr_act = events[idx].activity
        alt_symbols = [s for s in self.alphabet if s != curr_act]
        new_sym = str(self.rng.choice(alt_symbols))

        mutated = list(events)
        mutated[idx] = Event(
            case_id=events[idx].case_id,
            activity=new_sym,
            timestamp=events[idx].timestamp,
            attributes=events[idx].attributes,
        )
        return mutated

    def _mutate_excessive_retries(self, events: List[Event]) -> List[Event]:
        """Insert 4-8 failed payment attempts while keeping the trace DFA-valid."""
        retries_cfg = self.stat_cfg.get("excessive_retries", {})
        min_fail = int(retries_cfg.get("min_failures", 4))
        max_fail = int(retries_cfg.get("max_failures", 8))
        n_extra_fails = int(self.rng.integers(min_fail, max_fail + 1))

        # Find position of first PaymentInitiated or Created
        insert_idx = None
        for i, e in enumerate(events):
            if e.activity == "PaymentInitiated":
                insert_idx = i
                break

        if insert_idx is None:
            # If no PI (e.g. cancelled immediately), insert after OrderCreated
            insert_idx = 1

        case_id = events[0].case_id
        ref_time = events[insert_idx].timestamp if insert_idx < len(events) else events[0].timestamp

        extra_events: List[Event] = []
        cur_t = ref_time
        for _ in range(n_extra_fails):
            cur_t += timedelta(seconds=float(self.rng.uniform(30, 180)))
            extra_events.append(
                Event(case_id=case_id, activity="PaymentInitiated", timestamp=cur_t)
            )
            cur_t += timedelta(seconds=float(self.rng.uniform(3, 10)))
            extra_events.append(Event(case_id=case_id, activity="PaymentFailed", timestamp=cur_t))

        # Re-time remaining downstream events
        time_shift = cur_t - ref_time + timedelta(seconds=60)
        remaining = [
            Event(
                case_id=e.case_id,
                activity=e.activity,
                timestamp=e.timestamp + time_shift,
                attributes=e.attributes,
            )
            for e in events[insert_idx:]
        ]

        return events[:insert_idx] + extra_events + remaining

    def _mutate_slow_gap(self, events: List[Event]) -> List[Event]:
        """Multiply one inter-event gap by a large multiplier (Doc 06 §5)."""
        if len(events) <= 2:
            return events
        multiplier = float(self.stat_cfg.get("slow_gap", {}).get("multiplier", 20.0))
        target_idx = int(self.rng.integers(1, len(events)))

        mutated = [events[0]]
        cur_time = events[0].timestamp

        for i in range(1, len(events)):
            original_gap = (events[i].timestamp - events[i - 1].timestamp).total_seconds()
            if i == target_idx:
                gap = original_gap * multiplier
            else:
                gap = original_gap

            cur_time += timedelta(seconds=gap)
            mutated.append(
                Event(
                    case_id=events[i].case_id,
                    activity=events[i].activity,
                    timestamp=cur_time,
                    attributes=events[i].attributes,
                )
            )

        return mutated

    def _mutate_burst_fast(self, events: List[Event]) -> List[Event]:
        """Compress all gaps to near-zero (bot-like timing)."""
        factor = float(self.stat_cfg.get("burst_fast", {}).get("compression_factor", 0.01))
        mutated = [events[0]]
        cur_time = events[0].timestamp

        for i in range(1, len(events)):
            original_gap = (events[i].timestamp - events[i - 1].timestamp).total_seconds()
            gap = max(0.01, original_gap * factor)
            cur_time += timedelta(seconds=gap)
            mutated.append(
                Event(
                    case_id=events[i].case_id,
                    activity=events[i].activity,
                    timestamp=cur_time,
                    attributes=events[i].attributes,
                )
            )

        return mutated

    def inject_anomalies(self, simulated_cases: List[SimulatedCase]) -> List[SimulatedCase]:
        """Inject rule violations and statistical anomalies with automated DFA label verification."""
        n_total = len(simulated_cases)
        n_anomalous = int(np.round(n_total * self.anomaly_rate))

        # Randomly choose cases to mutate
        indices = self.rng.choice(n_total, size=n_anomalous, replace=False)
        indices_set = set(indices)

        rule_types = list(self.rule_weights.keys())
        rule_probs = np.array(list(self.rule_weights.values()))
        rule_probs /= rule_probs.sum()

        stat_types = ["excessive_retries", "slow_gap", "burst_fast"]
        stat_weights = [
            float(self.stat_cfg.get("excessive_retries", {}).get("share", 0.35)),
            float(self.stat_cfg.get("slow_gap", {}).get("share", 0.35)),
            float(self.stat_cfg.get("burst_fast", {}).get("share", 0.30)),
        ]
        stat_probs = np.array(stat_weights) / sum(stat_weights)

        result_cases: List[SimulatedCase] = []

        for idx, case in enumerate(simulated_cases):
            if idx not in indices_set:
                result_cases.append(case)
                continue

            # Decide whether to inject rule_violation (60%) or statistical_anomaly (40%)
            inject_rule = bool(self.rng.choice([True, False], p=[0.60, 0.40]))

            max_retries = 10
            success = False
            mutated_events = case.trace.events
            chosen_type = "none"
            label_class = "normal"

            for _ in range(max_retries):
                if inject_rule:
                    label_class = "rule_violation"
                    chosen_type = str(self.rng.choice(rule_types, p=rule_probs))
                    if chosen_type == "skip_event":
                        mutated_events = self._mutate_skip_event(case.trace.events)
                    elif chosen_type == "swap_adjacent":
                        mutated_events = self._mutate_swap_adjacent(case.trace.events)
                    elif chosen_type == "duplicate_event":
                        mutated_events = self._mutate_duplicate_event(case.trace.events)
                    elif chosen_type == "insert_random_event":
                        mutated_events = self._mutate_insert_random_event(case.trace.events)
                    elif chosen_type == "event_after_closed":
                        mutated_events = self._mutate_event_after_closed(case.trace.events)
                    elif chosen_type == "replace_event":
                        mutated_events = self._mutate_replace_event(case.trace.events)

                    # Automated label verification: must be INVALID
                    activities = [e.activity for e in mutated_events]
                    fsm_res = validate_trace(self.dfa, case.trace.case_id, activities)
                    if fsm_res.verdict == FsmVerdict.INVALID:
                        success = True
                        break

                else:
                    label_class = "statistical_anomaly"
                    chosen_type = str(self.rng.choice(stat_types, p=stat_probs))
                    if chosen_type == "excessive_retries":
                        mutated_events = self._mutate_excessive_retries(case.trace.events)
                    elif chosen_type == "slow_gap":
                        mutated_events = self._mutate_slow_gap(case.trace.events)
                    elif chosen_type == "burst_fast":
                        mutated_events = self._mutate_burst_fast(case.trace.events)

                    # Automated label verification: must be VALID_COMPLETE
                    activities = [e.activity for e in mutated_events]
                    fsm_res = validate_trace(self.dfa, case.trace.case_id, activities)
                    if fsm_res.verdict == FsmVerdict.VALID_COMPLETE:
                        success = True
                        break

            if success:
                new_trace = Trace(case_id=case.trace.case_id, events=mutated_events)
                result_cases.append(
                    SimulatedCase(
                        trace=new_trace, label_class=label_class, anomaly_type=chosen_type
                    )
                )
            else:
                # If mutation couldn't satisfy constraint after retries, keep original valid trace
                result_cases.append(case)

        return result_cases
