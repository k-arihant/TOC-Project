# PS9 — Anomaly Detection in Process Workflows Using Automata and Machine Learning

A Theory of Computation (TOC) TA-activity project by a three-member team.

> **Status: planning blueprint.** These documents define *what to build and how*. Nothing here has been implemented or measured yet, and no experimental results are claimed. All results must come from the system's own stored evaluation runs.

## What the project is

Normal behaviour of an **Online Order & Payment workflow** is modelled as a **DFA**. The language of valid traces is regular; traces are validated in linear time and any violation is reported with the exact failing transition. Because a finite automaton cannot express statistical regularities (e.g. an unusually high number of payment retries, abnormal timing), **machine-learning detectors** (Isolation Forest, a Markov sequence model, optional Random Forest reference) complement it. A **hybrid decision layer** keeps *formal rule violations* and *statistical anomalies* separate and explains every flag. A small, **independent supplementary experiment** applies a simplified TCP-connection automaton to packet-derived sequences — it is **not** an intrusion-detection system.

**Central academic contribution:** DFA/NFA, NFA→DFA, minimisation, equivalence, reachability, regular-language reasoning, and the formal-vs-learned comparison.

Legend used in all docs: **[M]** mandatory · **[R]** recommended · **[E]** optional enhancement.

## Documents

| # | Document | Purpose |
|---|---|---|
| 01 | [Project Overview](docs/01_Project_Overview.md) | PS9 wording, workflow choice, abstract, scope, limitations |
| 02 | [Requirement Analysis](docs/02_Requirement_Analysis.md) | **Requirement-to-implementation mapping**, ambiguities, FR/NFR |
| 03 | [System Architecture](docs/03_System_Architecture.md) | Layers, dependency rules, DFD, shared type contracts, tech stack |
| 04 | [TOC Automata Design](docs/04_TOC_Automata_Design.md) | DFA/NFA formal design, language, subset construction, minimisation, reachability |
| 05 | [ML and Hybrid Detection](docs/05_ML_and_Hybrid_Detection.md) | Features, detectors, calibration, hybrid decision table, leakage controls |
| 06 | [Dataset and Preprocessing](docs/06_Dataset_and_Preprocessing.md) | Event-log format, simulator, anomaly injection, splits, public logs |
| 07 | [Real Packet Validation](docs/07_Real_Packet_Validation.md) | Supplementary TCP-lifecycle experiment, scope guard, limitations |
| 08 | [Database and API Design](docs/08_Database_and_API_Design.md) | ER diagram, SQL schema, endpoints, environment variables |
| 09 | [Frontend and Dashboard](docs/09_Frontend_and_Dashboard.md) | Pages, owners, visualisations, no-fake-data rule |
| 10 | [Team Distribution](docs/10_Team_Distribution.md) | **Equal three-member plan**, shared-task ownership, rotation, contribution matrix |
| 11 | [Development Roadmap](docs/11_Development_Roadmap.md) | Phases, milestones, risks |
| 12 | [Testing and Evaluation](docs/12_Testing_and_Evaluation.md) | Test strategy, evaluation protocol, empty result templates |
| 13 | [Deployment Guide](docs/13_Deployment_Guide.md) | Local run, Docker, hosting options |
| 14 | [Antigravity Master Prompt](docs/14_Antigravity_Master_Prompt.md) | Phase-by-phase build instructions for the AI coding assistant |
| 15 | [Final Demonstration and Viva](docs/15_Final_Demonstration_and_Viva.md) | Demo script, viva question banks |

**Suggested reading order:** 01 → 02 → 04 → 05 → 06 → 03 → 08 → 09 → 10 → 11 → 12 → 07 → 13 → 14 → 15.

## Team (equal workload design)

| Member | Individual module | Shared-task leadership (rotating) |
|---|---|---|
| M1 | TOC & automata engine | Integration Sprint B · API core · E2E tests · API/DB deploy · dashboard pages 1 & 4 |
| M2 | Workflow ML (data, features, IF, RF) | Integration Sprint A · DB schema · Docker · dashboard shell & page 2 · smoke/rollback |
| M3 | ML research, Markov baseline, packet validation | Integration Sprint C · repository layer · hybrid pipeline · evaluation harness · dashboard pages 3 & 5 · dashboard deploy |

Planned effort is balanced at 112 / 112 / 112 abstract points (planning estimate, not measured hours, not a grade). Final marks are decided by the faculty. Details: [doc 10](docs/10_Team_Distribution.md).

## Planned quick start (once implemented)

```bash
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
docker compose up --build        # db + api + dashboard
# or locally:
alembic upgrade head && python scripts/seed_db.py
uvicorn src.api.main:app --port 8000 &
streamlit run src/dashboard/app.py
pytest -q
```

## Open decisions to resolve first (from doc 02)

1. **A8 – confirm with the faculty/TA** that a supplementary TCP-lifecycle experiment is acceptable alongside the PS9 main workflow (currently *unconfirmed*).
2. A3 – confirm that generated (controlled) logs are acceptable as the primary dataset.
3. A13 – real deadline; the roadmap assumes 8 weeks.
4. Deployment provider — verify current free-tier terms before choosing.

## Honesty rules

- Anomalies in the main dataset are **injected by our generator**; they are not real fraud or attack labels.
- No hardcoded metrics, model outputs, or dashboard numbers; fixtures live only in `tests/fixtures/`.
- The packet module makes no attack-detection claims: FSM-invalid ≠ malicious, FSM-valid ≠ benign.
- Statements marked "expected" in doc 04 §6 are hand-derived predictions to be confirmed by the implementation.
