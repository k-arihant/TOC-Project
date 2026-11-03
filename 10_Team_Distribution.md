# 10 — Team Distribution (Revised: Equal Three-Member Workload)

This revision replaces any earlier distribution in which one member carried database, backend, frontend, integration and deployment. **No single member is the default integrator, full-stack developer, or deployer.**

> Fairness statement: this is a *work-distribution design*. Final marks are decided by the faculty; nothing here guarantees equal marks. The design goal is that each member has substantial, independently demonstrable technical contributions and can explain the whole project in the viva.

Members (names to be filled by the team): **M1 – TOC & Automata**, **M2 – Workflow ML**, **M3 – ML Research & Real Packet Validation**.

## 1. Individual modules (each independently testable)

| Member | Module | Expected deliverable |
|---|---|---|
| **M1** | Workflow definition (`workflows/order_payment/`), `src/automata/*`: DFA, NFA, NFA→DFA, minimisation, equivalence, reachability, dead/unreachable detection, trace validator, explanation text, DOT visualisation, bounded-retry variant [R]; automata tests and technical write-up (doc 04) | A **fully working, independently testable automata engine** (`pytest tests/unit/automata` passes; CLI `python -m automata.cli validate ...`) |
| **M2** | Ingest/preprocessing, workflow sequence generation (simulator + anomaly injector with DFA-verified labels), feature extraction, case-level splits, Isolation Forest, Random Forest [R], threshold calibration, ML evaluation + visualisation, ML tests and docs (docs 05–06) | A **fully working, independently testable workflow anomaly detection module** (`pytest tests/unit/workflow_ml`; `python scripts/train_models.py`) |
| **M3** | Markov baseline, comparative detector research (K-Means distance [R]; One-Class SVM/LOF [E]), packet validation module (reader, flows, flag mapper, simplified TCP FSM strict/tolerant, experiment + scenario agreement), comparative evaluation and validation documentation (docs 05 §3, 07, 12) | A **working supplementary packet-validation module** and a **comparative anomaly-analysis report** (`pytest tests/unit/{research,packet}`) |

Important: packet validation stays supplementary (≈10–11 % of total planned effort; hard cap 15 %); it must not turn the project into network intrusion detection.

## 2. Shared implementation responsibilities — owner / reviewer / contributor / deliverable

Rule: **primary owner** writes and merges; **second reviewer** must approve the pull request and runs the deliverable independently; the **third member** contributes a defined slice (code, tests, or data).

| ID | Shared task | Primary | Second reviewer | Third member contributes | Measurable deliverable |
|---|---|---|---|---|---|
| S1 | Repo scaffold, `src/common` contracts, lint/CI | M1 | M2 | M3: pre-commit config, `.env.example`, Makefile targets | `make test` and CI green on empty modules; `common/types.py` frozen as v1 |
| S2 | Database schema, ER diagram, migrations | M2 | M3 | M1: automata/FSM table definitions + sample seed script | `alembic upgrade head` creates all tables; ER diagram in docs; each owner's tables per doc 08 §2 |
| S3 | Data-access (repository) layer | M3 | M1 | M2: dataset/event-log repositories | CRUD tests per repository on SQLite and PostgreSQL |
| S4 | API core: app factory, config, error format, upload limits, optional API key, OpenAPI | M1 | M3 | M2: upload endpoint plumbing, pagination helper | `/health`, `/docs` live; error-format test; upload-limit test |
| S5 | Routers | each owns own: M1 automata, M2 datasets/ml, M3 detect/evaluation/reports/packet | the next member in cycle (M1→M2, M2→M3, M3→M1) | the remaining member writes ≥ 3 contract tests against it | All endpoints in doc 08 §4 return documented shapes; contract tests green |
| S6 | Hybrid pipeline + explanation merging | M3 | M1 | M2: feature-deviation explanation function, ML-score adapters | Decision-table tests (all 4 rows) + explanation completeness test |
| S7 | Dashboard shell, API client, shared chart components, report-download helper | M2 | M1 | M3: provenance footer + empty-state components | App starts; all pages load against the live API |
| S8 | Dashboard pages | M1: pages 1 and 4; M2: page 2; M3: pages 3 and 5 | cycle: M1→M2, M2→M3, M3→M1 | third member reviews UX/data correctness against the API | Each page meets doc 09 §1 and the demo checklist |
| S9 | Integration sprints (rotating lead, §3) | A: M2 · B: M1 · C: M3 | non-lead with the strongest knowledge of the interfaces | the other member fixes defects found | Each sprint ends with the stated integration test green |
| S10 | Testing: integration suite (M3), E2E/system tests (M1), leakage audit + reproducibility tests (M2) | as listed | cycle | third member adds ≥ 5 cases | `tests/integration`, `tests/e2e`, `tests/leakage` all green in CI |
| S11 | Docker: images + Compose | M2 | M1 | M3: dashboard image + healthchecks | `docker compose up` runs db+api+dashboard from a clean clone |
| S12 | Deployment: API+DB (M1), dashboard (M3), smoke tests + rollback notes (M2) | as listed | cycle | third member executes the deploy checklist independently | Public URLs respond; smoke script passes against them |
| S13 | Final documentation: architecture/README (M1), user guide/report core (M2), evaluation report (M3) | as listed | cycle | third member proofreads against code | Docs consistent with code; README commands verified by a fresh-clone run |
| S14 | Evaluation harness: FSM-only vs ML-only vs hybrid, metrics, latency | M3 | M2 | M1: FSM-only baseline and rule-side metrics | `scripts/run_evaluation.py` stores `evaluation_runs`; results recorded in doc 12 template |
| S15 | Presentation and viva preparation | all three, each presents own modules + one cross-module segment (§6) | — | — | Rehearsed demo; viva Q&A banks answered in doc 15 |

## 3. Integration strategy and rotation

Independent development first (Phases 2–4 in doc 11); then three integration sprints, each with a **different lead** so no one becomes the permanent bug-fixer:

| Sprint | Scope | Lead | Exit test |
|---|---|---|---|
| A | Automata ↔ DB ↔ API ↔ dashboard page 1 (a trace validated via API appears with highlighted path) | **M2** | `tests/integration/test_validate_flow.py` |
| B | ML + Markov ↔ DB ↔ hybrid ↔ API ↔ pages 2–4 | **M1** | `tests/integration/test_detect_flow.py` (dataset → train → batch → decisions + explanations stored) |
| C | Packet module ↔ API ↔ page 5, evaluation page, Docker, deployment, E2E | **M3** | `tests/e2e/test_full_pipeline.py` + public smoke test |

Rotation rules:
1. The lead for a sprint is **not** the owner of the majority of the code in it (A leads ML-side member through automata work, B leads the automata member through ML work, C leads the research member through everything else) — this forces cross-module understanding.
2. Pull requests need one approval from a member who did not write the code.
3. "Fix-it" duty rotates weekly (on-call member triages CI failures).
4. Interface changes to `src/common` need all three approvals.

## 4. Module interfaces (what each member must hand over)

Each member's handover package for each module: **source code, input/output spec, installation instructions, unit tests, example input and output, documentation**.

| Interface | Producer | Consumers | Contract |
|---|---|---|---|
| `automata.validator.validate_trace(dfa, case_id, activities) -> FsmResult` | M1 | M2 (label verification), M3 (hybrid, packet), API | `common/types.py::FsmResult` |
| `automata.loader.load_workflow(path) -> DFA`; `packet.tcp_fsm.load_tcp_dfa(profile)` (uses M1's DFA class) | M1 / M3 | all | YAML spec format (doc 04) |
| `AnomalyDetector` protocol (`fit`, `calibrate`, `score`, `to_bytes`, `from_bytes`) | M2 (IF, RF), M3 (Markov, K-Means) | hybrid, API | `common/interfaces.py` |
| `hybrid.pipeline.decide_batch(traces, fsm_results, scores, policy)` | M3 | API | doc 05 §5 |
| Dataset files: `events.csv`, `labels.csv`, `meta.json` | M2 | all | doc 06 §2, §8 |
| REST API | per router owner | dashboard, tests | doc 08 §4 |

**Stub policy (no fake functionality):** during independent development a member may use *fixtures in `tests/fixtures/`* (e.g. a few hand-written traces, a tiny generated dataset) to exercise their module. Fixtures never ship in `src/`, never appear in dashboard or API runtime paths, and never contain pre-computed metrics. Cross-module calls use the real implementation as soon as it exists (target: end of Week 3).

## 5. File and folder ownership

| Path | Owner | Notes |
|---|---|---|
| `workflows/`, `src/automata/`, `tests/unit/automata/`, `docs/04_*` | M1 | |
| `src/workflow_ml/`, `config/simulator.yaml`, `tests/unit/workflow_ml/`, `docs/06_*` | M2 | |
| `src/research/`, `src/packet/`, `tests/unit/{research,packet}/`, `docs/07_*` | M3 | |
| `src/hybrid/`, `tests/unit/hybrid/` | M3 (M1 reviewer) | |
| `src/common/`, `.github/`, `pyproject/requirements`, `Makefile` | M1 (S1) | frozen interfaces need 3 approvals |
| `src/db/models_automata.py` + its migration | M1 | |
| `src/db/models_workflow.py` + its migration | M2 | |
| `src/db/models_detection.py`, `models_packet.py` + migrations | M3 | |
| `src/api/routers/automata.py` M1; `datasets.py`, `ml.py` M2; `detect.py`, `evaluation.py`, `reports.py`, `packet.py` M3 | per router | |
| `src/dashboard/app.py`, `components/` M2; pages per doc 09 | per page | |
| `docker/`, `docker-compose.yml` | M2 (dashboard image M3) | |
| `docs/` (shared), `README.md` | M1 (S13) | each member maintains their own doc sections |

## 6. Contribution matrix (planning estimate, abstract effort points)

Points are **planning estimates** of relative effort, not measured hours and not grades.

| Item | M1 | M2 | M3 |
|---|---|---|---|
| Automata engine (46) + tests/docs (8) | 54 | | |
| Preprocessing 8 · simulator/injector 10 · features/splits 8 · IF/RF/thresholds 14 · ML eval/viz/tests/docs 12 | | 52 | |
| Markov 10 · comparative research 8 · **packet module 30** · tests/docs 4 | | | 52 |
| S1 scaffold / contracts / CI | 5 | 1 | 2 |
| S2 DB schema | 3 | 6 | 2 |
| S3 data-access layer | 2 | 3 | 6 |
| S4 API core | 5 | 2 | 2 |
| S5 routers | 4 | 4 | 4 |
| S6 hybrid pipeline | 3 | 2 | 7 |
| S7 dashboard shell | 2 | 6 | 2 |
| S8 dashboard pages | 6 | 4 | 5 |
| S9 integration sprints | 8 | 9 | 7 |
| S10 testing | 6 | 6 | 6 |
| S11 Docker | 1 | 4 | 2 |
| S12 deployment | 4 | 4 | 4 |
| S13 final docs | 3 | 4 | 3 |
| S14 evaluation harness | 3 | 2 | 5 |
| S15 presentation / viva | 3 | 3 | 3 |
| **Total** | **112** | **112** | **112** |

Packet-related effort ≈ 36 of 336 points (module 30 + packet router ≈ 2 + page ≈ 2 + share of docs/tests ≈ 2) ≈ **10.7 %**, inside the 10–15 % budget. Track actual time in a shared sheet each week; if packet work exceeds 15 % of tracked time, apply the scope guard (doc 07 §1).

## 7. Per-member profile

### Member 1 — TOC & Automata
- **Individual technical contribution:** all formal automata algorithms and the workflow specification; explanation text from the DFA.
- **Code ownership:** §5 rows 1, 4 (common/CI), automata DB tables, automata router, pages 1 and 4.
- **Independent implementation milestone (end Week 3):** `pytest tests/unit/automata` green incl. property tests; §4.2 worked example reproduced; expected-structure table (doc 04 §6) confirmed or discrepancies documented.
- **Integration contribution:** leads Sprint B; API core; E2E tests; API+DB deployment.
- **Testing contribution:** automata unit/property tests; E2E suite; FSM-only baseline in evaluation.
- **Documentation contribution:** doc 04, README/architecture, API docs.
- **Presentation & viva topics:** DFA formal definition, δ, L(M) regular expression, subset construction, Myhill–Nerode/minimisation, equivalence checking, reachability/dead states, regular vs non-regular limits (pumping lemma), hybrid layer logic.

### Member 2 — Workflow ML
- **Individual technical contribution:** dataset generation with DFA-verified labels; features; Isolation Forest; Random Forest reference; calibration; ML evaluation.
- **Code ownership:** `workflow_ml/`, dataset/ML DB tables and routers, dashboard shell + page 2, Docker.
- **Independent milestone (end Week 3):** seeded dataset reproducible; IF trained and calibrated; ML metrics computed locally from generated data; leakage unit tests green.
- **Integration contribution:** leads Sprint A; DB schema; Docker/Compose; smoke tests/rollback.
- **Testing contribution:** reproducibility + leakage audit; ML unit tests.
- **Documentation contribution:** docs 05–06 (ML parts), user guide.
- **Viva topics:** feature design, why no FSM features in ML, Isolation Forest mechanism, threshold calibration, leakage controls, valid-variation vs anomaly, Random Forest caveats.

### Member 3 — ML Research & Real Packet Validation
- **Individual technical contribution:** Markov detector; comparative research; packet pipeline and simplified TCP FSM; evaluation harness; hybrid decision implementation.
- **Code ownership:** `research/`, `packet/`, `hybrid/`, detection/packet DB tables and routers, pages 3 and 5.
- **Independent milestone (end Week 3):** Markov detector fitted/scored on generated data; packet unit tests (hand-built records) pass; one lab capture parsed into flows.
- **Integration contribution:** leads Sprint C; repository layer; dashboard deployment; integration test suite.
- **Testing contribution:** integration suite; packet tests; evaluation correctness tests.
- **Documentation contribution:** docs 07, 12 (results sections), evaluation report.
- **Viva topics:** Markov chain scoring, comparison of detectors, hybrid decision table, packet-to-event mapping, TCP FSM, strict⊂tolerant equivalence, limits of FSM on real traffic, why FSM-invalid ≠ attack.

## 8. Ensuring every member understands the whole project

1. **Walkthrough swaps (Weeks 3, 6, 8):** each member explains another member's module in 10 minutes using the code; the owner corrects.
2. **Cross-review:** every PR gets a non-author approval (S5/S8 cycles above).
3. **Cross-module viva drill:** doc 15 includes a cross-topic question bank; each member answers questions on the other two modules.
4. **Presentation split:** each member presents their module *and* one cross-module segment (M1: hybrid logic; M2: dataset/pipeline end-to-end; M3: evaluation + packet).
5. **Contribution log:** keep `docs/contribution_log.md` (date, member, task, PR link) — real records of what was done, which also supports the faculty's assessment.
