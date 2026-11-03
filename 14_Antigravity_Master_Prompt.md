# 14 — Antigravity Master Prompt

**How to use:** give Antigravity this file **plus** docs 02, 04, 05, 06, 07, 08, 09 as context. Work phase by phase; after each phase run the listed commands and do not advance until acceptance criteria pass. Each member runs the phases for their own modules (see §12), with the shared phases split per doc 10.

---

## 1. Role and goal

You are a senior engineer helping three students build **PS9 – Anomaly Detection in Process Workflows Using Automata and Machine Learning** for a Theory of Computation course. Build a complete, working, locally runnable, then deployable system. **TOC is the central academic contribution**; real packet analysis is a small, independent, supplementary module.

## 2. Non-negotiable rules

1. **No fake functionality.** No hardcoded model results, metrics, scores, or demo numbers anywhere in `src/`, API responses, or the dashboard. Fixtures are allowed only under `tests/fixtures/` and may not contain precomputed metrics. If data is missing, the UI shows an empty state.
2. **No fabricated claims** in code comments, docs, or UI text about accuracy, datasets, or research results. Result tables are filled only from stored evaluation runs.
3. **No data leakage:** split by case; fit scalers/vocabularies on train only; calibrate thresholds on validation negatives; ML features must not include FSM outputs, labels, or injector parameters; labels never appear in the event file given to detectors.
4. **Keep rule evidence and ML evidence separate** everywhere (types, tables, UI).
5. **Packet module isolation:** `src/packet/` must not import `workflow_ml`, `research`, or `hybrid`, and its tables have no foreign keys into main-workflow tables. It reuses `automata.dfa.DFA` and `automata.validator` only. It must not contain attack-detection logic or claims.
6. **Dashboard is a pure API client** (no ML/automata imports).
7. **Interfaces:** change `src/common` only with all three members' approval. Higher score = more anomalous for every detector.
8. Do not load model artefacts not produced by this project. No secrets in git.
9. Write type hints, docstrings, and tests with every module. Prefer simple, readable code.
10. If a requirement is ambiguous, list the ambiguity and the chosen assumption in `docs/decisions.md` instead of silently assuming.

## 3. Stack

Python 3.11; pandas, numpy, scikit-learn; scapy (PcapReader); FastAPI, uvicorn, pydantic v2; SQLAlchemy 2 + Alembic + psycopg; PostgreSQL 16 (SQLite for unit tests); Streamlit, Plotly, graphviz (python pkg + system binary); pytest, pytest-cov, hypothesis, httpx, ruff; Docker + Compose; GitHub Actions. Do not add other major dependencies without a recorded reason.

## 4. Repository structure to create

```
ps9-workflow-anomaly/
├── README.md  .env.example  Makefile  requirements.txt  requirements-dev.txt  requirements-dashboard.txt
├── alembic.ini  docker-compose.yml  docker/{api.Dockerfile,dashboard.Dockerfile}
├── .github/workflows/ci.yml
├── docs/                          # the 15 documents + decisions.md + contribution_log.md
├── config/{simulator.yaml,experiment.example.yaml}
├── workflows/order_payment/{workflow.yaml,activity_map.yaml}                       # M1
├── data/{sample/,raw/(gitignored)}
├── scripts/{generate_dataset.py,seed_db.py,train_models.py,run_evaluation.py,run_packet_experiment.py,smoke_test.py}
├── src/
│   ├── common/{types.py,interfaces.py,config.py,logging.py}                         # M1 (S1), 3 approvals to change
│   ├── automata/{dfa,nfa,conversion,minimization,equivalence,reachability,loader,validator,explain,visualize,variants,cli}.py   # M1
│   ├── workflow_ml/{ingest,sequences,simulator,injector,features,splits,thresholds,isolation_forest,random_forest,explain,registry,evaluate}.py  # M2
│   ├── research/{markov,kmeans_score,compare}.py                                    # M3
│   ├── packet/{reader,flows,mapper,tcp_fsm,evaluate}.py + tcp_fsm.yaml + scenarios/ # M3
│   ├── hybrid/{decision,explanation,pipeline}.py                                    # M3
│   ├── db/{session.py,models_automata.py,models_workflow.py,models_detection.py,models_packet.py,repositories/,migrations/}
│   ├── api/{main.py,deps.py,errors.py,schemas/,routers/{automata,datasets,ml,detect,evaluation,reports,packet}.py}
│   └── dashboard/{app.py,components/,pages/{1_Automata_Explorer,2_Workflow_Data_and_ML,3_Evaluation,4_Hybrid_Detection,5_Packet_Validation}.py}
└── tests/{unit/{automata,workflow_ml,research,packet,hybrid}/,integration/,e2e/,leakage/,fixtures/}
```

## 5. Build order and dependencies

```
P1 contracts + scaffold  →  ┬─ P3 automata (M1)  [validator first]
                            ├─ P2 dataset/preprocessing (M2)  [needs validator v0]
                            └─ P5 packet (M3)  [needs DFA class + equivalence]
P2 → P4 ML (M2: IF/RF; M3: Markov/K-Means)
P3,P4 → P9 hybrid (M3)
P6 milestone review → P7 DB → P8 API → Sprint A/B → P11 dashboard → P12 evaluation → P13 tests → P14 Docker → P15 deploy
```
Develop in this order: **common types → automata validator → simulator/injector → features + IF → Markov → hybrid → packet → DB → API → dashboard → evaluation → Docker → deployment.**

## 6. Phase prompts (copy one at a time)

### Phase 1 — Scaffold and contracts (M1 primary)
Create the repo skeleton (§4), `pyproject`/requirements, ruff config, Makefile, CI running `ruff` and `pytest`. Implement `src/common/types.py` and `interfaces.py` **exactly** as in doc 03 §6. Add `.env.example` from doc 08 §4.2. *Accept:* `make test` and CI pass on empty tests; types import cleanly.

### Phase 2 — Automata engine (M1)
Implement per doc 04 §10, in this order: `dfa.py`, `loader.py` (YAML → DFA with spec lint), `validator.py` (pseudocode in doc 04), `explain.py`; then `nfa.py` (Thompson combinators), `conversion.py` (subset construction), `minimization.py` (Moore), `equivalence.py` (product BFS with counter-example), `reachability.py`, `visualize.py` (DOT with highlight), `variants.py` (bounded retry). Create `workflows/order_payment/workflow.yaml` from doc 04 §1.2–1.4 including the explicit dead state. Add `automata/cli.py` (`validate`, `minimise`, `reach`, `equiv`). Write all tests in doc 04 §11 and doc 12 §2. *Accept:* `pytest tests/unit/automata` green; the §2 trace table reproduced; the §4.2 example reproduced; structural expectations of doc 04 §6 checked by a test whose failure message explains the discrepancy (do not weaken the test to pass).

### Phase 3 — Dataset and preprocessing (M2)
Implement `ingest.py`, `sequences.py` (doc 06 §3), `simulator.py` and `injector.py` (doc 06 §4–5) using `automata.validator` to verify labels, `splits.py` (case-level, stratified, held-out anomaly types), `scripts/generate_dataset.py` writing `events.csv`, `labels.csv`, `meta.json`. *Accept:* seed reproducibility test; label-verification test; split-disjointness test.

### Phase 4 — ML (M2 and M3)
M2: `features.py` (doc 05 §2, with leakage guard test), `isolation_forest.py`, `thresholds.py`, `random_forest.py` (labelled "supervised reference"), `explain.py`, `evaluate.py`. M3: `markov.py` (both score variants), `kmeans_score.py`, `compare.py`. All detectors implement `AnomalyDetector`, expose `raw_score` (higher = more anomalous) and `norm_score` ∈ [0,1], serialise via `to_bytes`/`from_bytes`. *Accept:* determinism, round-trip, range, leakage tests; `scripts/train_models.py` trains and saves via the DB layer once available (until then to a temp dir) and prints computed values only.

### Phase 5 — Hybrid (M3)
Implement `decision.py` (doc 05 §5.1, 5.3), `explanation.py`, `pipeline.py::decide_batch`. *Accept:* tests for all decision rows; every non-NORMAL decision has ≥ 1 explanation.

### Phase 6 — Packet experiment (M3; time-boxed)
Implement `reader.py` (PcapReader streaming, limits), `flows.py`, `mapper.py` (doc 07 §3.3), `tcp_fsm.yaml` + `tcp_fsm.py` (strict and tolerant), `evaluate.py`, `scenarios/README.md`, `scripts/run_packet_experiment.py`. Unit tests use hand-built packet records. Demonstrate strict ⊂ tolerant with `automata.equivalence`. *Accept:* packet unit tests green; run on a small authorised-lab capture produces a report; limitations text included in outputs.

### Phase 7 — Database (S2/S3: M2 schema primary, M3 repositories primary, M1 automata tables)
Implement SQLAlchemy models split by owner file and Alembic migrations exactly matching doc 08 §3 (tables, constraints, view). Repositories per aggregate. `scripts/seed_db.py` loads workflow, events, DFA, NFA, minimised DFA computed by `automata` (no handwritten rows). *Accept:* migrations apply on SQLite and PostgreSQL; repository tests pass.

### Phase 8 — API (S4/S5)
App factory, error format, optional API key, pagination, upload limits (M1); routers per owner (doc 08 §4). Pydantic schemas mirror `common/types.py`. *Accept:* contract test per endpoint; OpenAPI at `/docs`.

### Phase 9 — Dashboard (S7/S8)
Shell and shared components (M2); pages per doc 09 with owners rotated as in doc 10 S8. Provenance footer (dataset id, seed, config hash, model-run id). Empty states. Downloads via `/reports`. *Accept:* doc 12 §7 checklist passes on a local stack.

### Phase 10 — Evaluation (S14: M3 primary)
`scripts/run_evaluation.py` implements doc 12 §3–5 and writes `evaluation_runs` and `evaluation_type_metrics`. Latency per doc 12 §5. *Accept:* running it on a generated dataset fills tables R1–R3 in the dashboard from the DB; no metric is typed anywhere.

### Phase 11 — Docker and deployment (S11/S12)
Dockerfiles and Compose per doc 13; smoke script. *Accept:* fresh-clone `docker compose up --build` + `python scripts/smoke_test.py` pass.

## 7. Interfaces (authoritative)

See doc 03 §6 for dataclasses and the `AnomalyDetector` protocol. Key function signatures:

```python
automata.loader.load_workflow(path: str) -> DFA
automata.validator.validate_trace(dfa: DFA, case_id: str, activities: list[str]) -> FsmResult
automata.conversion.nfa_to_dfa(nfa: NFA) -> DFA
automata.minimization.minimise(dfa: DFA) -> tuple[DFA, dict[str, list[str]]]
automata.equivalence.equivalent(a: DFA, b: DFA) -> tuple[bool, list[str] | None]
automata.reachability.analyse(dfa: DFA) -> ReachabilityReport   # unreachable, dead, useful
workflow_ml.ingest.build_traces(df: pd.DataFrame) -> list[Trace]
workflow_ml.features.extract(traces: Sequence[Trace]) -> tuple[np.ndarray, list[str]]   # matrix, feature names
hybrid.pipeline.decide_batch(traces, fsm_results, scores_by_detector, policy) -> list[HybridDecision]
packet.evaluate.run_experiment(pcap_path: str, profile: str, scenario_map: dict | None) -> dict
```

## 8. Database and API
Implement exactly doc 08 §3 (SQL) and §4 (endpoints, error format, environment variables).

## 9. Commands

```bash
pip install -r requirements.txt -r requirements-dev.txt
alembic upgrade head && python scripts/seed_db.py
python scripts/generate_dataset.py --seed 0 --out data/sample
python scripts/train_models.py --dataset data/sample --seed 0
python scripts/run_evaluation.py --dataset-id 1 --split test
uvicorn src.api.main:app --reload --port 8000
streamlit run src/dashboard/app.py
pytest -q && ruff check .
docker compose up --build
python scripts/smoke_test.py --api http://localhost:8000
```

## 10. Integration sequence (after independent milestone P6)
1. **Sprint A (lead M2):** DB models for automata → seed → `/automata/*` and `/workflows/*` → page 1. Test: validate trace via API, see highlighted path.
2. **Sprint B (lead M1):** dataset/ML tables and routers → `/ml/*` → hybrid → `/detect/*` → pages 2, 4. Test: generate → train → batch → inspect explanation.
3. **Sprint C (lead M3):** packet tables/router → page 5 → evaluation router/page 3 → E2E test → Docker → deploy.
After each sprint: run full test suite; fix before moving on.

## 11. Definition of done
- All [M] items in doc 02 implemented and tested; [R] items either done or listed in `docs/decisions.md` as deferred.
- Dashboard shows execution paths, highlighted failing transitions, anomaly scores, hybrid results, evaluation comparison, packet section — all from the API.
- Evaluation tables filled from stored runs; limitations documented.
- `docker compose up` works from a clean clone; deployment smoke test passes (or fallback documented).
- Each member can run and explain every module.

## 12. Member-scoped starting prompts

**M1:** "Using docs 03, 04, 12 §2, implement Phase 1 then Phase 2. Do not start Phase 3 work. Expose `validate_trace` first and tell M2 when it is merged."
**M2:** "Using docs 05, 06, implement Phase 3 then the M2 part of Phase 4. Until `validate_trace` is merged, use tests/fixtures only; then switch to the real validator."
**M3:** "Using docs 05, 07, implement the M3 part of Phase 4, Phase 5, then Phase 6 within its time-box. Do not import main-pipeline modules into `src/packet/`."
