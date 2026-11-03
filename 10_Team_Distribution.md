# 10 — Team Distribution (Solo Developer Operational Model)

> **PROJECT UPDATE (Solo Developer Model):** The entire TOC-Project is now engineered, maintained, and delivered by a **single solo developer**. The developer is individually responsible for every module: TOC automata engine, workflow ML, sequence research, hybrid decision layer, supplementary packet validation, database schema & repositories, REST API, Streamlit dashboard, benchmarking evaluation, Docker packaging, and deployment.
> 
> *Historical Note:* The functional designations below (**M1 – TOC & Automata**, **M2 – Workflow ML**, **M3 – ML Research & Packet Validation**) are preserved to represent the distinct architectural modules, functional boundaries, and viva defense topics. The single developer completes all deliverables sequentially across all three domains.

---

## 1. Functional Modules (Sequential Implementation by Solo Developer)

| Functional Domain | Module Scope | Deliverable |
|---|---|---|
| **Domain 1 (ex-M1: TOC Engine)** | Workflow definition (`workflows/order_payment/`), `src/automata/*`: DFA, NFA, NFA→DFA, minimisation, equivalence, reachability, dead/unreachable detection, trace validator, explanation text, DOT visualisation, bounded-retry variant [R]; automata tests and technical write-up (doc 04) | A **fully working, independently testable automata engine** (`pytest tests/unit/automata` passes; CLI `python -m automata.cli validate ...`) |
| **Domain 2 (ex-M2: Workflow ML)** | Ingest/preprocessing, workflow sequence generation (simulator + anomaly injector with DFA-verified labels), feature extraction, case-level splits, Isolation Forest, Random Forest [R], threshold calibration, ML evaluation + visualisation, ML tests and docs (docs 05–06) | A **fully working, independently testable workflow anomaly detection module** (`pytest tests/unit/workflow_ml`; `python scripts/train_models.py`) |
| **Domain 3 (ex-M3: Research & Packets)** | Markov baseline, comparative detector research (K-Means distance [R]; One-Class SVM/LOF [E]), packet validation module (reader, flows, flag mapper, simplified TCP FSM strict/tolerant, experiment + scenario agreement), comparative evaluation and validation documentation (docs 05 §3, 07, 12) | A **working supplementary packet-validation module** and a **comparative anomaly-analysis report** (`pytest tests/unit/{research,packet}`) |

*Scope Guard:* Packet validation stays supplementary ($\approx 10\text{--}11\%$ of total planned effort; hard cap 15%); it must not turn the project into network intrusion detection.

---

## 2. Implementation Responsibilities (Solo Developer Execution)

In the solo development model, the developer implements, self-reviews, and tests every deliverable against the documented criteria before moving to the next phase:

| ID | Task | Component / Deliverable | Acceptance Criteria |
|---|---|---|---|
| S1 | Repo scaffold, `src/common` contracts, lint/CI | `pyproject.toml`, requirements, `common/types.py`, `interfaces.py`, `.env.example`, Makefile | `ruff check .` and `pytest` green; types frozen |
| S2 | Database schema, ER diagram, migrations | PostgreSQL 16 schema, Alembic migrations, `scripts/seed_db.py` | `alembic upgrade head` applies cleanly on SQLite and PostgreSQL |
| S3 | Data-access (repository) layer | Repositories for workflows, datasets, cases, model runs, decisions | Unit CRUD tests green across all repositories |
| S4 | API core | FastAPI app factory, error handling, upload limits, optional API key | `/health` and `/docs` functional; contract tests green |
| S5 | Routers | 8 REST routers (`/automata`, `/datasets`, `/ml`, `/detect`, `/evaluation`, `/reports`, `/packet`, `/health`) | Endpoints return documented JSON schemas |
| S6 | Hybrid pipeline | Decision table and combined explanation engine | Decision-table tests cover all 4 states; 100% explanation completeness |
| S7 | Dashboard shell | Streamlit app shell, navigation, shared chart components | App starts cleanly and connects to live API |
| S8 | Dashboard pages | 5 interactive pages per doc 09 | All pages load real API data with zero fake metrics |
| S9 | Integration | End-to-end integration flows connecting automata, ML, DB, API, and UI | Automated integration test suite green |
| S10 | Testing & Audit | Unit, property (Hypothesis), integration, E2E, and data leakage audits | Target $\ge 80\%$ line coverage on core logic |
| S11 | Docker packaging | `docker-compose.yml`, `docker/api.Dockerfile`, `docker/dashboard.Dockerfile` | `docker compose up --build` works from a clean clone |
| S12 | Deployment | Cloud or local production stack with automated smoke test script | `python scripts/smoke_test.py` passes |
| S13 | Final documentation | Architecture, viva prep, and user guides | All markdown documentation synchronized with code |
| S14 | Evaluation harness | Automated benchmark script (`scripts/run_evaluation.py`) | Fills tables R1–R6 from stored database records |
| S15 | Presentation & Viva | Demo script and viva question defense | Rehearsed demo covering all technical domains |

---

## 3. Solo Developer Sequential Execution Workflow

Instead of parallel sprints with rotating leads, the developer advances strictly **one phase at a time**:

1. **Phase 1: Scaffold & Contracts:** (Done & verified) Repo skeleton, `common/types.py`, `common/interfaces.py`, CI, tests.
2. **Phase 2: Automata Engine:** DFA, NFA, subset construction, minimization, equivalence, reachability, trace validator.
3. **Phase 3: Dataset & Ingestion:** Ingest, sequence generation, simulator, anomaly injector, case-level splits.
4. **Phase 4: ML Detectors:** 144 features, Isolation Forest, Markov chain detector, K-Means clustering, threshold calibration.
5. **Phase 5: Hybrid Decision Layer:** Decision table and explanation generator.
6. **Phase 6: Supplementary Packet Experiment:** Streaming PCAP reader, TCP flow mapper, strict/tolerant TCP FSM.
7. **Phase 7: Database & Repositories:** PostgreSQL models, Alembic migrations, database seeding.
8. **Phase 8: REST API:** FastAPI application and routers.
9. **Phase 9: Interactive Dashboard:** Streamlit multi-page UI.
10. **Phase 10: Evaluation & Benchmarking:** Automated metric collection and confusion matrices.
11. **Phase 11: Docker & Deployment:** Containerization, health checks, and smoke tests.

---

## 4. Module Interfaces (Contract Consistency)

Even in solo development, interfaces remain strictly decoupled to ensure code quality:

| Interface | Producer Function | Consumers | Shared Contract |
|---|---|---|---|
| Trace Validator | `automata.validator.validate_trace(dfa, case_id, activities)` | Data injector, Hybrid engine, API | `common/types.py::FsmResult` |
| Spec Loader | `automata.loader.load_workflow(path) -> DFA` | Seeder, API, CLI | YAML spec format (doc 04) |
| Detector Protocol | `fit`, `calibrate`, `score`, `to_bytes`, `from_bytes` | ML models (IF, Markov, RF, K-Means) | `common/interfaces.py::AnomalyDetector` |
| Hybrid Pipeline | `hybrid.pipeline.decide_batch(traces, fsm_results, scores, policy)` | API, Evaluation harness | `common/types.py::HybridDecision` |
| Dataset Files | `events.csv`, `labels.csv`, `meta.json` | ML training, API, evaluation | Doc 06 §2, §8 |

---

## 5. File and Folder Ownership

All code is authored by the solo developer, organized cleanly by domain:

| Path | Functional Domain | Purpose |
|---|---|---|
| `workflows/`, `src/automata/`, `tests/unit/automata/` | TOC Core | Formal DFA, NFA, minimization, equivalence, validator |
| `src/workflow_ml/`, `config/simulator.yaml`, `tests/unit/workflow_ml/` | Workflow ML | Data generation, feature extraction, Isolation Forest |
| `src/research/`, `tests/unit/research/` | Sequence Research | Markov transition detector, K-Means centroid scoring |
| `src/packet/`, `tests/unit/packet/` | Supplementary | PCAP flow reader, simplified TCP FSM |
| `src/hybrid/`, `tests/unit/hybrid/` | Decision Fusion | Hybrid decision table & explanation generation |
| `src/common/` | Shared Contracts | Frozen types, interfaces, settings, logging |
| `src/db/` | Persistence | SQLAlchemy models, Alembic migrations, repositories |
| `src/api/` | REST Backend | FastAPI routers, schemas, error formatting |
| `src/dashboard/` | Frontend | Streamlit multi-page dashboard |
| `docker/`, `docker-compose.yml` | Infrastructure | Container orchestration |
| `scripts/` | Tooling | Seed, generate, train, evaluate, and smoke test scripts |

---

## 6. Comprehensive Viva Mastery (Solo Developer Defense)

Because the developer builds the entire system, they must be prepared to defend all aspects in the viva:
1. **TOC Automata:** DFA formal 5-tuple, total $\delta$ with $S_{\text{dead}}$, language $L(M)$, Thompson $\epsilon$-NFA, subset construction, Moore minimization, Myhill-Nerode equivalence, product-automaton BFS, pumping lemma limits (why unbounded counting is non-regular).
2. **Workflow ML:** Feature extraction without FSM leakage, Isolation Forest scoring ($raw\_score = -score\_samples$), ECDF calibration on validation negatives, stratified case-level splitting, valid variations vs. anomalies.
3. **Research & Supplementary:** First-order Markov chain scoring (mean vs. total negative log-likelihood), TCP flag mapping, strict vs. tolerant TCP FSM, strict $\subset$ tolerant proof, and why FSM-invalid $\neq$ attack.
4. **System Architecture:** Clean separation between rules and ML, zero hardcoded numbers, and end-to-end trace explainability.
