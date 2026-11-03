# 12 — Testing and Evaluation

**Hard rule (NFR-05):** no result in this repository may be typed in by hand. Every metric shown in the dashboard or pasted into the report must come from a stored `evaluation_runs` row (or a CSV written by the evaluation script). The tables in §6 are **empty templates**.

## 1. Test pyramid

| Level | Scope | Tooling | Owner |
|---|---|---|---|
| Unit | Each module in isolation (fixtures allowed) | pytest | module owner |
| Property | Automata equivalences on random strings | hypothesis [R] | M1 |
| Contract | API request/response shapes vs doc 08 | pytest + httpx/TestClient | non-author of the router |
| Integration | Module combinations with real DB (SQLite/PostgreSQL) | pytest | M3 |
| E2E | Dataset → train → detect → evaluate → report on local stack | pytest + docker compose | M1 |
| Leakage & reproducibility | Splits, feature list, seeds, hashes | pytest | M2 |
| Performance | Latency measurement scripts | `scripts/run_evaluation.py` | M3 |
| Manual demo | Checklist (§7) | human | all |

Commands (from repo root):

```bash
pytest tests/unit -q
pytest tests/unit/automata -q --hypothesis-seed=0
pytest tests/integration -q
pytest tests/e2e -q                 # needs `docker compose up -d db` or SQLite mode
pytest --cov=src --cov-report=term-missing
ruff check . && ruff format --check .
```

## 2. Key test cases by module (minimum set)

**Automata (M1):** all δ edges; §2 trace table of doc 04; worked NFA→DFA example; minimised ≡ original (equivalence + random strings); counter-example correctness; defective-spec reachability tests; unknown-event and event-after-final reason codes.
**Workflow ML (M2):** seed determinism; label verification (injected class vs DFA verdict); case-level split disjointness; feature-name leakage guard; IF fit/score/serialise round-trip; `norm_score ∈ [0,1]`; threshold computed from validation negatives only (assert test scores never touched).
**Research/Markov (M3):** probabilities of each row sum to 1 after smoothing; unseen transition gets non-zero probability; scoring deterministic; factors list the lowest-probability transitions.
**Hybrid (M3):** all four decision-table rows; ML evidence stored but not label-changing for INVALID; explanation non-empty for every non-NORMAL decision.
**Packet (M3):** hand-built records for clean close, reset, invalid order, mid-stream, port reuse, unknown flags, tolerant vs strict differences; strict ⊂ tolerant via equivalence.
**DB/API (shared):** migrations apply; unique constraints; error format; upload limits; pagination.
**Dashboard (shared):** smoke import test per page against a running test API; empty-state rendering.

## 3. Evaluation methodology — what we compare

| Detector | Flags a case when | Inputs allowed |
|---|---|---|
| **FSM-only** | DFA verdict is INVALID (`VALID_PREFIX` not flagged) | trace only |
| **ML-only** | ML flag per policy (IF and/or Markov, calibrated τ) | features; **no FSM outputs** |
| **Hybrid** | final label ∈ {RULE_VIOLATION, STATISTICAL_ANOMALY} | FSM + ML via decision table |

Single-detector rows (IF, Markov, K-Means, RF-reference) are also reported. Random Forest rows carry the label "supervised reference under injected labels".

Positive class = `rule_violation ∪ statistical_anomaly`. Negatives = `normal ∪ valid_variation`. Incomplete traces are excluded from the main metrics and reported separately (A6).

## 4. Fair split protocol and leakage prevention

1. Generate dataset with seed *s* (default seeds 0–4); log config hash.
2. Split **by case**: train/val/test stratified by class (doc 06 §6). Hold out ≥ 1 rule type and ≥ 1 statistical type from train and validation.
3. Fit detectors on train negatives only (unsupervised) — RF-reference on train labels.
4. Calibrate τ on validation negatives (target FPR; default 0.05).
5. Select hyper-parameters and ML policy on validation; write `experiment.yaml`; compute its hash.
6. Evaluate on test **once** for that hash.
7. Repeat for each seed; report mean ± standard deviation (and per-seed values in the appendix).
8. Run the leakage audit (doc 05 §6) and attach its output.
Optional [R]: contaminated-training experiment; difficulty sweep with `borderline` mode.

## 5. Metrics

| Metric | Definition |
|---|---|
| Precision | TP / (TP + FP) |
| Recall (detection rate) | TP / (TP + FN) |
| F1 | 2TP / (2TP + FP + FN) |
| False-positive rate | FP / (FP + TN) |
| FPR on `valid_variation` | FP among valid_variation / count of valid_variation |
| Confusion matrix | TP, FP, TN, FN counts (stored) |
| ROC-AUC, PR-AUC | from `norm_score` (threshold-free) |
| Base rate | positives / total in the evaluated split (always reported beside precision) |
| Processing time | per-trace latency: warm-up 100 traces discarded, ≥ 1000 timed traces (or all available), `time.perf_counter`, report median and p95, record hardware and Python version |
| Explainability | (a) completeness: share of flagged cases with ≥ 1 stored explanation (expected 100 %, verified by test); (b) **localisation agreement** for injected rule violations: fraction where `fail_index` lies within the injector's recorded mutation position and the following event; (c) qualitative rubric score by two members on a random sample of flagged cases (clarity, correctness, actionability), sample size recorded |

## 6. Result recording templates (fill only from stored runs)

**Table R1 — Main comparison (test split, mean ± std over seeds; n seeds = ___; base rate = ___)**

| Detector | Precision | Recall | F1 | FPR | FPR on valid_variation | ROC-AUC | PR-AUC | Latency median / p95 (ms) |
|---|---|---|---|---|---|---|---|---|
| FSM-only | | | | | | n/a | n/a | |
| ML-only (policy: ___) | | | | | | | | |
| Hybrid | | | | | | | | |
| IF alone | | | | | | | | |
| Markov alone | | | | | | | | |
| K-Means [R] | | | | | | | | |
| RF reference [R] | | | | | | | | |

**Table R2 — Confusion matrices (seed ___)** one per detector: TP / FP / TN / FN.

**Table R3 — Recall by anomaly type** (rows: each injected type; columns: FSM-only, ML-only, Hybrid; mark held-out types).

**Table R4 — Ablation** (ML-only with/without timing features; with/without bigram features; contaminated training %).

**Table R5 — Explainability** (completeness %, localisation agreement %, rubric mean ± sd, sample size).

**Table R6 — Packet experiment** (scenario, intended verdict, strict verdict, tolerant verdict, n flows; false-violation causes list; MIDSTREAM count).

**Hypotheses to test (not results):** (H1) FSM-only detects rule violations but not statistical anomalies; (H2) ML-only is weaker than FSM-only on rule violations that do not alter feature distributions; (H3) hybrid recall ≥ each of the others, possibly at higher FPR; (H4) learned detectors degrade on held-out anomaly types. Report whether each was supported, refuted, or inconclusive.

## 7. Manual demo checklist (all must pass before presenting)

1. `docker compose up` from a clean clone; health OK.
2. Page 1: validate a valid, a violating, and an incomplete trace; red edge appears for the violation.
3. Page 1: NFA→DFA table, minimisation merges shown, reachability report.
4. Page 2: generate dataset (seed shown); train IF; score histogram appears.
5. Page 4: run hybrid on test split; filter to each label; open one explanation per label.
6. Page 3: run evaluation; table and confusion matrices come from the API; CSV download works.
7. Page 5: run packet experiment on the bundled small lab capture; limitations panel visible.
8. Restart services; data persists.
