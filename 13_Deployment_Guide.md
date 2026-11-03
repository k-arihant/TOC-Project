# 13 — Deployment Guide

Principle: **the project must run completely locally before any deployment.** Free-tier hosting terms (sleep policies, database expiry, resource limits, supported system packages) change; **verify each provider's current terms before committing to it** — nothing below should be taken as a guarantee.

## 1. Local development setup

```bash
git clone <repo-url> ps9-workflow-anomaly && cd ps9-workflow-anomaly
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env                                   # edit values
# System dependency for diagrams (Ubuntu/Debian): sudo apt-get install graphviz
```

SQLite quick mode (no Docker): set `DATABASE_URL=sqlite:///./ps9.db`.
PostgreSQL mode: `docker compose up -d db`.

```bash
alembic upgrade head                                   # create tables
python scripts/seed_db.py                              # load workflow + DFA/NFA/minimised DFA from workflows/ (real spec, no dummy rows)
python scripts/generate_dataset.py --seed 0 --out data/sample
uvicorn src.api.main:app --reload --port 8000          # API at http://localhost:8000/docs
streamlit run src/dashboard/app.py                     # dashboard at http://localhost:8501
```

Makefile shortcuts: `make setup`, `make migrate`, `make seed`, `make api`, `make dash`, `make test`, `make lint`, `make up`, `make down`.

## 2. Docker

`docker/api.Dockerfile`
```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends graphviz libpq5 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
COPY workflows ./workflows
COPY config ./config
COPY alembic.ini ./
COPY scripts ./scripts
ENV PYTHONPATH=/app/src
CMD ["sh","-c","alembic upgrade head && python scripts/seed_db.py && uvicorn api.main:app --host 0.0.0.0 --port ${API_PORT:-8000}"]
```

`docker/dashboard.Dockerfile`
```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends graphviz && rm -rf /var/lib/apt/lists/*
COPY requirements-dashboard.txt .
RUN pip install --no-cache-dir -r requirements-dashboard.txt
COPY src/dashboard ./dashboard
CMD ["streamlit","run","dashboard/app.py","--server.address=0.0.0.0","--server.port=8501"]
```
(`requirements-dashboard.txt` contains only streamlit, httpx/requests, plotly, pandas, graphviz — enforcing that the dashboard imports no ML code.)

`docker-compose.yml`
```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL","pg_isready -U ${POSTGRES_USER}"]
      interval: 5s
      retries: 10
  api:
    build: { context: ., dockerfile: docker/api.Dockerfile }
    env_file: .env
    depends_on: { db: { condition: service_healthy } }
    ports: ["8000:8000"]
  dashboard:
    build: { context: ., dockerfile: docker/dashboard.Dockerfile }
    environment:
      API_BASE_URL: http://api:8000/api/v1
    depends_on: [api]
    ports: ["8501:8501"]
volumes: { pgdata: {} }
```
Run: `docker compose up --build`. Stop: `docker compose down` (add `-v` to wipe data).

## 3. Environment variables
See doc 08 §4.2. Commit `.env.example` only; keep real values out of git. For hosted PostgreSQL use the provider's connection string as `DATABASE_URL` (ensure the SQLAlchemy driver prefix matches the installed driver).

## 4. Deployment options

| Option | Components | Notes |
|---|---|---|
| **A (suggested)** | API as a Docker web service on a free/low-cost PaaS; PostgreSQL from a free managed tier; Streamlit dashboard on Streamlit Community Cloud | Three separate consoles; dashboard needs system package `graphviz` (supported through a `packages.txt` file — verify) and `API_BASE_URL` set to the public API URL |
| B | One VM (any provider you have credits or a free allowance for) running `docker compose up -d` behind a reverse proxy | Simplest mentally; needs VM admin |
| C (fallback) | Local demo + recorded video + screenshots | Always prepare this regardless |

Candidate providers to evaluate (verify current free-tier terms for each): Render, Railway, Fly.io (API); Neon, Supabase (PostgreSQL); Streamlit Community Cloud (dashboard).

### 4.1 Steps for Option A
1. **Database:** create a managed PostgreSQL instance; copy its connection string.
2. **API:** deploy from the Dockerfile; set `DATABASE_URL`, `API_KEY` (optional), `CORS_ORIGINS`, upload limits. Confirm `GET /health`.
3. **Initial data:** the container's start command runs migrations and `seed_db.py`. Then create the dataset and models on the deployed instance with the documented script/API calls (`/datasets/generate`, `/ml/train`) — models are stored as BYTEA in the database so they survive ephemeral file systems.
4. **Dashboard:** deploy; set `API_BASE_URL`. Open every page.
5. **Smoke test:** `python scripts/smoke_test.py --api https://<api-url>` calls health, validate, generate (small), train, batch, evaluation, report download; fails loudly on any non-2xx or empty result.
6. **Record** URLs, versions (git commit), and date in the README.

### 4.2 Operational notes
- Free services may sleep; open the dashboard before the demo to warm the stack.
- Free databases may expire or have size limits; keep seed + generate scripts so the system can be rebuilt from scratch.
- **Model artefacts:** only load artefacts produced by our own training code (pickle-based formats are unsafe for untrusted files).
- Do not expose the packet upload endpoint without size limits (`PACKET_MAX_MB`, `PACKET_MAX_PACKETS`); do not accept pcaps from the public in a demo deployment — restrict to the bundled lab capture if the API is public.
- **Rollback:** tag each release; redeploy previous tag; migrations are additive; `alembic downgrade -1` documented for the latest migration only.

## 5. Deployment responsibilities (rotated, doc 10 S12)
API+DB deployment: M1 · Dashboard deployment: M3 · Smoke tests, rollback notes, warm-up checklist: M2 · each executes a peer's checklist once to prove it is reproducible.
