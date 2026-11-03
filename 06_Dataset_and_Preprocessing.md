# 06 — Dataset and Preprocessing (Main Workflow)

Owner: **Member 2** (ingest, simulator, injector, splits) with **Member 1** (workflow spec, label verification interface) and **Member 3** (reviews, hybrid-relevant labels).

## 1. Dataset strategy in one paragraph

Our **primary dataset is generated** from the documented Order & Payment workflow, with controlled, reproducible anomaly injection. This is the only way to have trustworthy ground-truth labels for rule violations *and* statistical anomalies. Real public process-mining logs are used only as an **optional qualitative smoke test** of the pipeline, because they carry **no ground-truth anomaly labels**. We never describe injected anomalies as "real attacks" or "real fraud".

## 2. Event-log format (required columns)

| Column | Type | Rule |
|---|---|---|
| `case_id` | string | Identifies one process instance (one order) |
| `activity` | string | Must map to a symbol of Σ (`activity_map.yaml` maps raw names to Σ names) |
| `timestamp` | ISO-8601 | Normalised to UTC; used for ordering and timing features |

Optional extra columns (`resource`, `amount`, …) are stored in `attributes` JSON but unused in the base model.

**Labels are never in the event file.** For synthetic data a separate `labels.csv` has: `case_id, label_class, anomaly_type, split`.

## 3. From event log to sequences

```
function BUILD_TRACES(df):
    df ← drop rows with null case_id / activity / timestamp  (count and report)
    df ← parse timestamp → UTC;  df.row_idx ← original order
    df ← sort by (case_id, timestamp, row_idx)               # stable tie-break
    map activity names via activity_map.yaml                  # unmapped → kept as-is (will be UNKNOWN_EVENT)
    group by case_id → Trace(case_id, [Event...])
    report: n_cases, n_events, min/median/max length, duplicate-row count, unmapped activities
```
Edge cases and policy: exact duplicate rows are **kept** (a duplicated event is a legitimate anomaly we might want to catch) but counted; cases with a single event are kept; timestamps equal within a case keep file order; clock-skew (non-monotone file order) is reported.

## 4. Synthetic generation (Member 2) — `workflow_ml/simulator.py`

Seeded (`numpy.random.default_rng(seed)`), config in `config/simulator.yaml`. All numeric values below are **design defaults to be recorded and may be changed**; they are not research findings.

### 4.1 Path sampling (valid classes)

| Path | Class | Default share |
|---|---|---|
| Happy path (0 failures) | normal | majority |
| 1–2 failed payments then success | valid_variation | small |
| Cancel before payment (from Created or PaymentFailed) | valid_variation | small |
| Cancel after payment/packing + refund | valid_variation | small |
| Delivered → return + refund | valid_variation | small |

Per-attempt failure probability, path shares, and the cap on failures for valid classes (default ≤ 2) are config values. Anomaly `excessive_retries` uses a **disjoint** range (default 4–8 failures) so labels are unambiguous; an optional `borderline` mode (3 failures) lets us study the hard region [R].

### 4.2 Timestamps
Inter-event gaps drawn from log-normal distributions with a configurable median per transition (e.g. payment gaps in seconds–minutes, packing in minutes–hours, shipping/delivery in hours–days). Gap parameters live in the config and are exported with the dataset metadata.

## 5. Anomaly injection (Member 2) — `workflow_ml/injector.py`

The injector takes a valid complete trace and mutates it. **Label verification:** after mutation the injector calls `automata.validator.validate_trace` to confirm: `rule_violation` ⇒ verdict INVALID; `statistical_anomaly` ⇒ verdict VALID_COMPLETE. Mismatches are resampled and counted. The DFA is used **only to verify labels at generation time**, never as an ML feature.

| Type | Class | Mutation |
|---|---|---|
| `skip_event` | rule_violation | Delete one non-first event |
| `swap_adjacent` | rule_violation | Swap two neighbouring events |
| `duplicate_event` | rule_violation | Repeat an event in place |
| `insert_random_event` | rule_violation | Insert a random Σ symbol |
| `event_after_closed` | rule_violation | Append an event after `OrderClosed` |
| `replace_event` | rule_violation | Replace one event with a different Σ symbol |
| `excessive_retries` | statistical_anomaly | Insert extra PI/PF loops (default 4–8 failures) |
| `slow_gap` | statistical_anomaly | Multiply one inter-event gap by a large factor |
| `burst_fast` | statistical_anomaly | Compress all gaps to near-zero |
| `uniform_timing` [E] | statistical_anomaly | Replace gaps with a constant (bot-like) |

Default anomaly rate in the *main* test set is a config value (use a realistic minority such as a few percent to ~10 %; report the base rate with every precision figure because precision depends on it). A secondary balanced test set may be reported separately and labelled as such.

## 6. Dataset splits (Member 2) — `workflow_ml/splits.py`

- Unit of splitting: **case**.
- Default: train 60 % / validation 20 % / test 20 %, stratified by `label_class`.
- Train for unsupervised detectors: `normal` + `valid_variation` only.
- **Held-out anomaly-type split:** choose ≥ 1 rule type and ≥ 1 statistical type that appear *only* in test.
- Seeds: generate with seeds {0,1,2,3,4} (default) and report mean ± std.
- Persist: `datasets` row (seed, config hash), `cases.split`.

## 7. Public process-mining logs (optional, qualitative)

Where to look: the 4TU.ResearchData process-mining collections and the BPI Challenge archives. Candidates relevant to ordering/payment flows include the BPI Challenge purchase-order handling log and the Road Traffic Fine Management log (which contains payment-related activities). **Before use, verify for each log: licence, size, activity names, presence of timestamps, and whether any anomaly labels exist.** In general these logs record real behaviour *without* labelled anomalies; research papers have released versions with injected anomalies — check availability and licence yourself before relying on any of them.

How they would be used [E]:
1. Convert to the 3-column CSV (XES via `pm4py` if needed).
2. Run **ML-only** detectors and the pipeline's ingestion/feature code; inspect top-ranked traces **qualitatively**.
3. The base DFA does not apply (different workflow). A DFA could only be obtained by *discovery* (e.g. k-tails state merging) — an optional enhancement [E] that links to automata learning; if done, it must be described as learned-from-data, not as ground truth.
4. **No accuracy claims** from these logs.

## 8. Reproducibility package

`scripts/generate_dataset.py --seed 0 --config config/simulator.yaml --out data/sample/` writes `events.csv`, `labels.csv`, `meta.json` (seed, config hash, git commit, counts). A small sample set (few hundred cases) is committed for tests; large data is git-ignored.

## 9. Preprocessing unit tests (Member 2)

1. Same seed ⇒ identical `events.csv` hash.
2. Every generated `rule_violation` is INVALID and every `statistical_anomaly`/valid class is VALID_COMPLETE under the DFA (label-verification test).
3. No `case_id` appears in two splits; stratification proportions within tolerance.
4. Ties and out-of-order rows sorted as specified.
5. Unmapped activity becomes UNKNOWN_EVENT downstream (integration with automata).
