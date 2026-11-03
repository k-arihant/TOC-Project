# 05 — ML and Hybrid Detection

Owners: **Member 2** (workflow ML: features, Isolation Forest, Random Forest, evaluation) · **Member 3** (Markov baseline, comparative detectors, hybrid decision & explanation) · **Member 1** (rule evidence, reviewer of the hybrid decision). No numerical result appears in this document; all numbers below are *configuration defaults or design parameters*, not findings.

## 1. Detection taxonomy (ground-truth classes)

| Class | Definition | DFA verdict | Should be flagged? |
|---|---|---|---|
| `normal` | Typical happy-path or low-variation trace | VALID_COMPLETE | No |
| `valid_variation` | Legal but less common path: 1–2 payment retries, cancel before/after payment, return with refund | VALID_COMPLETE | **No** — this is the PS9 "valid process variation" |
| `rule_violation` | Contains an illegal transition / unknown event / event after Closed | INVALID | Yes (formal) |
| `statistical_anomaly` | DFA-legal but deviant: excessive retries, abnormal timing | VALID_COMPLETE | Yes (ML) |

Binary evaluation target: `is_anomaly = class ∈ {rule_violation, statistical_anomaly}`. We also report per-class and per-anomaly-type recall, and the **false-positive rate on `valid_variation` separately** (the quantity most directly tied to the PS wording).

## 2. Feature extraction (Member 2) — `src/workflow_ml/features.py`

All features are computed **only from the event sequence and timestamps**. They must not use the DFA, the injector's labels, or anything derived from them.

| Group | Features | Count |
|---|---|---|
| Length | `n_events`, `n_distinct_events` | 2 |
| Event counts | count of each symbol in Σ | 11 |
| Bigram counts | counts of every ordered pair (a,b) ∈ Σ×Σ (fixed vocabulary from Σ, **not** from the data or the DFA) | 121 |
| Payment behaviour | `payment_attempts` (=#PI), `payment_failures` (=#PF), `retry_ratio` | 3 |
| Repetition | `max_run_same_event` (longest run of identical consecutive events) | 1 |
| Timing | `log1p` of: total duration (s), mean gap, max gap, min gap, std gap; `max_gap / median_gap` | 6 |
| Termination | `ends_with_closed` (last event == `OrderClosed`; a sequence-level fact, not an FSM verdict) | 1 |

Excluded on purpose (leakage list): FSM verdict, failing index/state/event, number of invalid transitions, class label, anomaly type, injector parameters, case id, split name. A unit test asserts the feature-name list contains none of these tokens.

Feature spec is versioned (`feature_spec_version`) and stored with every model run, so scoring uses exactly the training-time schema.

## 3. Models

### 3.1 Isolation Forest — [M] (Member 2)

- Role: unsupervised statistical anomaly detector.
- Training data: `normal` + `valid_variation` cases from the **train split only** (assumed clean). No labels used.
- Hyper-parameter search space (starting point; tune on validation only): `n_estimators ∈ {100, 200, 400}`, `max_samples ∈ {"auto", 256, 0.5}`, `max_features ∈ {0.5, 1.0}`, `random_state = seed`. `contamination` is left at `"auto"` because decisions use our calibrated threshold, not sklearn's internal one.
- Output: `raw_score = -score_samples(x)` (higher = more anomalous); `norm_score` = ECDF rank of `raw_score` among training scores.

### 3.2 Markov sequence model — [M] (Member 3) — `src/research/markov.py`

- First-order chain over events with `<s>` start and `</s>` end tokens: P(aₜ | aₜ₋₁) estimated from train traces with Laplace smoothing (α default 1.0; tunable).
- Score options (compare on validation, record choice): **mean negative log-likelihood per transition** vs **total negative log-likelihood**. They behave differently on long loops (excessive retries), which is a legitimate research question for Member 3; no expected outcome is asserted here.
- Explanation factors: the 3 transitions with the lowest probability, e.g. "`PaymentFailed → PaymentInitiated` has probability 0.xx in normal data" (value filled from the fitted model).
- Limitation: ignores timing; a first-order model cannot see long-range structure.

### 3.3 K-Means distance score — [R] (Member 3, comparison) — `src/research/kmeans_score.py`

Standardise features (scaler fitted on train only), fit K-Means on train; `raw_score` = distance to nearest centroid. Choose k by silhouette on train or elbow; record method. This covers the "clustering" technique named in PS9.

### 3.4 Random Forest — [R, conditional] (Member 2)

- Supervised reference on **injected** labels (binary or 4-class). Feasible only because our generator provides labels; real logs generally have none.
- It will be evaluated and labelled in all outputs as **"supervised reference under injected labels"**. It may learn the generator's artefacts (and, via bigram counts, the rules themselves), so its score is **not** evidence of real-world detection ability.
- Mandatory safeguards: class weights for imbalance; train on train split only; hyper-parameters on validation; report an ablation without timing features and one with held-out anomaly types.

### 3.5 Optional extras — [E]
One-Class SVM, Local Outlier Factor, SHAP for tree models, small LSTM autoencoder. Only after all [M]/[R] items are complete.

## 4. Threshold calibration (no test leakage)

1. Fit detector on train.
2. Compute `norm_score` for validation cases whose class ∈ {normal, valid_variation} (the *negatives*).
3. Threshold τ = (1 − target_fpr)-quantile of those negative scores; default `target_fpr = 0.05` (configurable; **an operating-point choice, not a result**).
4. Freeze τ. Report test metrics once at τ, plus threshold-free ROC-AUC / PR-AUC.

## 5. Hybrid decision (Member 3 primary; Member 1 reviewer; Member 2 contributor)

Design principles: (1) formal rule violations and statistical anomalies stay **separate labels**; (2) the formal verdict is never overridden by ML; (3) every label is traceable to stored evidence.

### 5.1 Decision table

| # | FSM verdict | ML flag (policy §5.2) | Final label | Reason code |
|---|---|---|---|---|
| 1 | INVALID | any | `RULE_VIOLATION` | `FSM_ILLEGAL_TRANSITION` / `FSM_UNKNOWN_EVENT` / `FSM_EVENT_AFTER_FINAL` |
| 2 | VALID_COMPLETE | yes | `STATISTICAL_ANOMALY` | `ML_<detector>` (one per firing detector) |
| 3 | VALID_COMPLETE | no | `NORMAL` | `NONE` |
| 4 | VALID_PREFIX | not applied | `IN_PROGRESS` | `INCOMPLETE_TRACE` |

ML evidence is still computed and stored for row 1 (useful context: "also statistically unusual"), but does not change the label.

### 5.2 ML flag policy
`ml_policy ∈ {"any", "all", "primary:<detector>"}` over the configured detector set (default set: `isolation_forest`, `markov`). Default `any`. Alternatives are compared on **validation** data and the choice is recorded in the experiment config before test evaluation.

### 5.3 Pseudocode

```
function DECIDE(fsm: FsmResult, scores: list[DetectorScore], policy) -> HybridDecision:
    ml_fired ← [s for s in scores if s.is_anomaly]
    ml_flag  ← policy.apply(scores)                       # any / all / primary
    if fsm.verdict == INVALID:
        label ← RULE_VIOLATION
        expl  ← explain_fsm(fsm) + (["Also statistically unusual: ..."] if ml_flag else [])
    elif fsm.verdict == VALID_PREFIX:
        label ← IN_PROGRESS
        expl  ← ["Trace valid so far; current state ...", "ML not applied to incomplete traces"]
    elif ml_flag:
        label ← STATISTICAL_ANOMALY
        expl  ← ["Trace is valid under the workflow rules (no violation).",
                 *[explain_ml(s) for s in ml_fired]]
    else:
        label ← NORMAL
        expl  ← ["No rule violation; anomaly scores below thresholds."]
    return HybridDecision(label, fsm, scores, expl)
```

### 5.4 Explanation of ML flags (honest wording)

- **Isolation Forest**: for each feature, compute its percentile in the training-normal distribution; list the top 3 features by distance from the median percentile, with the observed value and the training reference (e.g. "`payment_attempts` = 7; 95th percentile of training = 2"). This is a *descriptive deviation summary*, not a causal decomposition of the forest's score; the UI must say so. SHAP [E] may replace it.
- **Markov**: lowest-probability transitions (§3.2).
- **K-Means**: distance to nearest centroid and the 3 most deviating standardised features.

### 5.5 Alternative (documented, not default)
Weighted risk `risk = w₁·1[INVALID] + w₂·norm_score` is simple but the weights are arbitrary and mix categories; we keep it only as a comparison in Member 3's research report.

## 6. Avoiding data leakage — checklist

| Risk | Control |
|---|---|
| Same case in train and test | Split by `case_id` before any feature/model work; assert disjoint sets |
| Scaler / vocabulary fitted on all data | Fit on train only; persist with the model |
| Threshold chosen on test | Calibrate on validation negatives; freeze before test |
| FSM info in ML features | Feature list excludes FSM outputs; unit test (§2) |
| Labels in event file | Labels live in a separate `labels` table/CSV; detectors never read it at score time |
| Injection artefacts | Report per-anomaly-type results; hold out ≥1 anomaly type from train/validation entirely |
| Hyper-parameter tuning on test | Config hash recorded; test evaluated once per config |
| Seed luck | Repeat with ≥5 seeds; report mean ± std |
| Contaminated training | Main experiment trains on clean data; [R] robustness experiment with x % anomalies in training |

## 7. Evaluation of the ML components (Member 2 / Member 3)

Per detector: ROC-AUC and PR-AUC on `norm_score`; precision/recall/F1/FPR at calibrated τ; recall per anomaly type; FPR on `valid_variation`; latency (doc 12 §5). Plots: score histograms per class, ROC, PR, feature-deviation bars for sample flagged cases. All stored via `evaluation_runs` (doc 08) and drawn from the DB by the dashboard.

## 8. Modules and ownership

| File | Owner | Spec |
|---|---|---|
| `workflow_ml/features.py` | M2 | §2, deterministic, versioned |
| `workflow_ml/isolation_forest.py` | M2 | implements `AnomalyDetector` |
| `workflow_ml/random_forest.py` | M2 | supervised reference, same I/O style |
| `workflow_ml/thresholds.py` | M2 | §4 |
| `workflow_ml/splits.py` | M2 | case-level stratified split, seed, held-out types |
| `workflow_ml/explain.py` | M2 | §5.4 for IF |
| `research/markov.py` | M3 | §3.2 |
| `research/kmeans_score.py` | M3 | §3.3 |
| `research/compare.py` | M3 | runs detectors under identical splits; writes comparison tables |
| `hybrid/decision.py` | M3 | §5.1–5.3 |
| `hybrid/explanation.py` | M3 | merges FSM/ML explanation lines |
| `hybrid/pipeline.py` | M3 | batch orchestration used by API |

Independent test (each owner): a detector trained on a small **seeded generated** dataset must (a) run end-to-end, (b) be deterministic under the same seed, (c) produce scores in [0,1] for `norm_score`, (d) serialise/deserialise identically. These are structural tests; they assert nothing about accuracy.
