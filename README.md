# PS9 — Anomaly Detection in Process Workflows Using Automata and Machine Learning

A Theory of Computation (TOC) TA-activity project developed under a **solo developer model**.

> **Project Execution Status:** The project is engineered end-to-end by a single developer responsible for all modules (automata engine, workflow ML, sequence research, hybrid decision engine, packet validation, database, REST API, Streamlit dashboard, Docker, and deployment). Historical Member 1 / Member 2 / Member 3 functional boundaries are preserved in documentation solely as structural domain references.

> **Status:** Phase 1 (Scaffold and Contracts) is fully implemented and verified. All future experimental results will be populated strictly from the system's own stored evaluation runs.

## What the project is

Normal behaviour of an **Online Order & Payment workflow** is modelled as a **DFA**. The language of valid traces is regular; traces are validated in linear time and any violation is reported with the exact failing transition. Because a finite automaton cannot express statistical regularities (e.g. an unusually high number of payment retries, abnormal timing), **machine-learning detectors** (Isolation Forest, a Markov sequence model, optional Random Forest reference) complement it. A **hybrid decision layer** keeps *formal rule violations* and *statistical anomalies* separate and explains every flag. A small, **independent supplementary experiment** applies a simplified TCP-connection automaton to packet-derived sequences — it is **not** an intrusion-detection system.

**Central academic contribution:** DFA/NFA, NFA→DFA, minimisation, equivalence, reachability, regular-language reasoning, and the formal-vs-learned comparison.

Legend used in all docs: **[M]** mandatory · **[R]** recommended · **[E]** optional enhancement.

## Documents

| # | Document | Purpose |
|---|---|---|
| 01 | [Project Overview](01_Project_Overview.md) | PS9 wording, workflow choice, abstract, scope, limitations |
| 02 | [Requirement Analysis](02_Requirement_Analysis.md) | **Requirement-to-implementation mapping**, ambiguities, FR/NFR |
| 03 | [System Architecture](03_System_Architecture.md) | Layers, dependency rules, DFD, shared type contracts, tech stack |
| 04 | [TOC Automata Design](04_TOC_Automata_Design.md) | DFA/NFA formal design, language, subset construction, minimisation, reachability |
| 05 | [ML and Hybrid Detection](05_ML_and_Hybrid_Detection.md) | Features, detectors, calibration, hybrid decision table, leakage controls |
| 06 | [Dataset and Preprocessing](06_Dataset_and_Preprocessing.md) | Event-log format, simulator, anomaly injection, splits, public logs |
| 07 | [Real Packet Validation](07_Real_Packet_Validation.md) | Supplementary TCP-lifecycle experiment, scope guard, limitations |
| 08 | [Database and API Design](08_Database_and_API_Design.md) | ER diagram, SQL schema, endpoints, environment variables |
| 09 | [Frontend and Dashboard](09_Frontend_and_Dashboard.md) | Pages, owners, visualisations, no-fake-data rule |
| 10 | [Team Distribution](10_Team_Distribution.md) | Solo developer operational model & historical module distribution |
| 11 | [Development Roadmap](11_Development_Roadmap.md) | Sequential solo execution plan, phases, milestones |
| 12 | [Testing and Evaluation](12_Testing_and_Evaluation.md) | Test strategy, evaluation protocol, empty result templates |
| 13 | [Deployment Guide](13_Deployment_Guide.md) | Local run, Docker, hosting options |
| 14 | [Antigravity Master Prompt](14_Antigravity_Master_Prompt.md) | Phase-by-phase build instructions for the AI coding assistant |
| 15 | [Final Demonstration and Viva](15_Final_Demonstration_and_Viva.md) | Demo script, viva question banks |

**Suggested reading order:** 01 → 02 → 04 → 05 → 06 → 03 → 08 → 09 → 10 → 11 → 12 → 07 → 13 → 14 → 15.

## Project Execution (Solo Developer Model)

All modules are owned and implemented sequentially by a single developer:
- **TOC & Automata Engine:** DFA/NFA, subset construction, Moore minimization, language equivalence, reachability, trace validator.
- **Workflow ML & Data:** Simulator, anomaly injector, 144 feature extractor, Isolation Forest, Random Forest reference.
- **Research & Packet Validation:** First-order Markov chain detector, K-Means clustering distance, supplementary TCP packet FSM experiment.
- **Full-Stack & Delivery:** PostgreSQL 16 schema & Alembic migrations, FastAPI backend (8 routers), Streamlit dashboard (5 pages), evaluation harness, and Docker Compose deployment.

Details: [doc 10](10_Team_Distribution.md) and [doc 11](11_Development_Roadmap.md).

## Quick Start (Phase 1 Ready)

```bash
pip install -r requirements.txt -r requirements-dev.txt -r requirements-dashboard.txt
cp .env.example .env
pytest -q
ruff check .
```

Once Docker & Database are configured in later phases:
```bash
docker compose up --build        # db + api + dashboard
# or locally:
alembic upgrade head && python scripts/seed_db.py
uvicorn src.api.main:app --port 8000
streamlit run src/dashboard/app.py
```

## Honesty rules

- Anomalies in the main dataset are **injected by our generator**; they are not real fraud or attack labels.
- No hardcoded metrics, model outputs, or dashboard numbers; fixtures live only in `tests/fixtures/`.
- The packet module makes no attack-detection claims: FSM-invalid ≠ malicious, FSM-valid ≠ benign.
- Statements marked "expected" in doc 04 §6 are hand-derived predictions to be confirmed by the implementation.
