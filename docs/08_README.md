# AI-Powered Student Success Assistant

> **Capstone Project** | Version 0.1.0  
> **Dataset:** UCI Student Performance (Math + Portuguese, 1044 rows merged)  
> **Frontend:** React + Vite (port 5173) | **Backend:** FastAPI (port 8000)

---

## Overview

The Student Success Assistant is a full-stack AI-powered dashboard that helps academic advisors assess student at-risk probability, retrieve similar historical cases, generate evidence-grounded intervention recommendations, and track follow-up outcomes. It uses a hybrid RAG pipeline (dense + sparse + reranker), locally-hosted LLM via Ollama, and trained ML models (Logistic Regression / Random Forest / XGBoost) with SHAP explainability.

Built on the UCI Student Performance dataset (Portuguese secondary school data), the assistant ingests CSV data into a PostgreSQL database (Aiven cloud), builds vector embeddings for Qdrant (cloud), and orchestrates a LangGraph agent workflow for recommendation generation. All features have deterministic fallback paths so the system functions without external dependencies during development.

The frontend uses the Newsprint design system — high-contrast editorial typography, sharp corners, visible grid borders, sparse red accents — delivered as a single-page React application. Authentication uses HMAC-based bearer tokens (not JWT) with static advisor credentials.

---

## Features

| Feature | Description |
|---|---|
| **Risk Prediction** | Student at-risk score via interpretable baseline formula or trained ML artifacts (LR, RF, XGBoost) |
| **Hybrid Retrieval** | Dense (BGE-small-en-v1.5, 384d) + Sparse (BM25) + RRF fusion + BGE-reranker-base re-ranking |
| **Intervention Recommendations** | LangGraph agent workflow with LLM-generated plans grounded in retrieved evidence |
| **LLM-as-Judge Evaluation** | Scores recommendations across relevance, groundedness, consistency, and usefulness |
| **Two-Week Follow-Up** | Ticket-based case management with LLM or rubric-based assessment (close / monitor / escalate) |
| **Factor Analysis** | Data-grounded answers about success/failure signals from the merged dataset |
| **Parent Email Notifications** | SMTP-based (or simulated) emails for medium/high-risk students |
| **Advisor Feedback Loop** | Useful/not-useful ratings injected into future LLM prompts |
| **SHAP Explainability** | Feature contribution analysis for ML model predictions |
| **Model Training** | Train Logistic Regression, Random Forest, and XGBoost with automated best-model selection |
| **Admin Pipeline** | One-click DB init, CSV ingestion, embedding build, and model training |

---

## Architecture

The backend follows **Hexagonal Architecture (Ports and Adapters)** to keep business logic independent of frameworks, databases, and external services. Six layers separate concerns: Domain, Application, Infrastructure, API, Schemas, and Core.

See [`01_ARCHITECTURE.md`](01_ARCHITECTURE.md) for full architecture documentation (C4 diagrams, layer details, key flows, design decisions).

### System Overview

```
Frontend (React + Vite, port 5173)
  │
  ▼ (REST / JSON)
Backend (FastAPI, port 8000)
  │
  ├── PostgreSQL (Aiven cloud) — Students, cases, feedback, evaluations, follow-up
  ├── Qdrant (cloud) — Dense vectors (384d)
  ├── Ollama (local, port 11434) — LLM inference (llama3.2:3b)
  └── SMTP (configurable) — Parent email delivery
```

**Key architecture decisions:**
- Qdrant over pgvector for independent vector search scaling
- LangGraph over simple chain-of-thought for structured agent workflows
- BGE-small-en-v1.5 (384d) over larger embeddings for quality/size tradeoff
- RRF fusion for combining dense and sparse search without training data
- Cross-encoder reranker applied only to top-20 candidates for latency/accuracy balance

---

## Technology Stack

| Component | Technology | Version |
|---|---|---|
| **Backend** | Python / FastAPI | 3.11+ / 0.115+ |
| **Frontend** | React + Vite + TypeScript | 19 / 7 / 5.6 |
| **Database** | PostgreSQL (Aiven cloud) | 16 |
| **Vector DB** | Qdrant (cloud) | — |
| **LLM** | Ollama (local) | llama3.2:3b |
| **Agent Framework** | LangGraph | 0.2+ |
| **Embeddings** | BAAI/bge-small-en-v1.5 | 384-dim |
| **Reranker** | BAAI/bge-reranker-base | — |
| **ML Models** | scikit-learn, XGBoost | 1.5+ / 2.1+ |
| **Explainability** | SHAP | 0.46+ |
| **Authentication** | HMAC-SHA256 (custom, no JWT) | — |
| **Design System** | Tailwind CSS v4 (Newsprint) | 4.0 |
| **Icons** | Lucide React | 0.468 |
| **Build Tool** | uv (Python) | — |
| **Testing** | pytest, httpx, FastAPI TestClient | 8.3+ / 0.27+ |
| **Linting** | Ruff | 0.6+ |

---

## Prerequisites

- **Python** 3.11 or later
- **Node.js** 18 or later
- **PostgreSQL** 16 — or use an Aiven cloud instance
- **Qdrant** cloud instance — or local Docker deployment
- **Ollama** — installed locally with `llama3.2:3b` pulled

```bash
# Install Ollama from https://ollama.com, then:
ollama pull llama3.2:3b
```

---

## Quick Start

### 1. Clone the repository

```bash
git clone <repo-url> student-success-assistant
cd student-success-assistant
```

### 2. Backend setup

```bash
cd backend
# Create virtual environment and sync dependencies
uv sync --extra full
# Or install specific extras: uv sync --extra database --extra retrieval --extra ml --extra agents
```

Configure environment variables by copying the template:

```bash
cp .env.example .env
# Edit .env with your PostgreSQL and Qdrant credentials
```

Key `.env` settings:
- `SSA_DATABASE_URL` — PostgreSQL connection string
- `SSA_QDRANT_URL` / `SSA_QDRANT_API_KEY` — Qdrant cloud endpoint
- `SSA_LLM_PROVIDER=ollama` — Local LLM (no API key needed)

Start Ollama in a separate terminal:

```bash
ollama serve
```

Start the backend:

```bash
uv run uvicorn student_success_assistant.main:app --app-dir src --reload --port 8000
```

### 3. Frontend setup

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:5173`. Set `VITE_API_BASE_URL` in `frontend/.env` if the backend runs on a different port.

### 4. Initialization

With the backend running, initialize the database, ingest data, build embeddings, and train models via the admin API. Login first to get a bearer token:

```bash
# Login
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "advisor", "password": "advisor-demo"}' | python -c "import sys,json;print(json.load(sys.stdin)['token'])")
```

**Initialize PostgreSQL tables:**

```bash
curl -s -X POST http://localhost:8000/api/v1/admin/storage/init \
  -H "Authorization: Bearer $TOKEN"
```

**Ingest the merged dataset:**

```bash
curl -s -X POST http://localhost:8000/api/v1/admin/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"path": "../data/processed/student-merged.csv", "persist": true}'
```

**Build vector embeddings and upload to Qdrant:**

```bash
curl -s -X POST http://localhost:8000/api/v1/admin/embeddings/build \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"limit": 1000}'
```

**Train ML models:**

```bash
curl -s -X POST http://localhost:8000/api/v1/admin/models/train \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"path": "../data/processed/student-merged.csv"}'
```

---

## Configuration

All configuration is managed through environment variables with the `SSA_` prefix, loaded by `pydantic-settings` from a root `.env` file. See `.env.example` for the full template.

| Variable | Default | Description |
|---|---|---|
| `SSA_DATABASE_URL` | — | PostgreSQL connection string |
| `SSA_QDRANT_URL` | `http://localhost:6333` | Qdrant endpoint |
| `SSA_QDRANT_API_KEY` | — | Qdrant API key |
| `SSA_QDRANT_COLLECTION` | `student_cases` | Qdrant collection name |
| `SSA_EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Embedding model name |
| `SSA_EMBEDDING_DIMENSION` | `384` | Vector dimension |
| `SSA_ENABLE_REMOTE_MODELS` | `false` | Enable model downloads |
| `SSA_RERANKER_MODEL` | `BAAI/bge-reranker-base` | Cross-encoder model |
| `SSA_LLM_PROVIDER` | `ollama` | `ollama` or `openai` |
| `SSA_LLM_MODEL` | `llama3.2:3b` | Generation model |
| `SSA_JUDGE_MODEL` | `llama3.2:3b` | LLM-as-judge model |
| `SSA_LLM_TEMPERATURE` | `0.7` | Generation temperature |
| `SSA_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint |
| `SSA_PREDICTION_MODEL` | `advisor_score` | Default risk model |
| `SSA_SELECTED_MODEL` | `logistic_regression` | ML artifact fallback |
| `SSA_SMTP_HOST` | — | SMTP server (empty = simulated) |
| `SSA_AUTH_USERNAME` | `advisor` | Login username |
| `SSA_AUTH_PASSWORD` | `advisor-demo` | Login password |
| `SSA_AUTH_TOKEN_SECRET` | — | HMAC signing secret |
| `SSA_AUTH_TOKEN_TTL_SECONDS` | `28800` | Token TTL (8 hours) |
| `SSA_FEEDBACK_EXAMPLES_LIMIT` | `3` | Examples in LLM prompts |

---

## API Overview

| Method | Path | Description | Auth |
|---|---|---|---|
| `GET` | `/health` | Liveness probe | No |
| `GET` | `/ready` | Readiness check (DB, Qdrant, LLM, LangGraph) | No |
| `POST` | `/auth/login` | Login, returns HMAC bearer token | No |
| `POST` | `/api/v1/predict` | Risk prediction from student features | Yes |
| `POST` | `/api/v1/search` | Hybrid retrieval (dense + sparse + RRF) | Yes |
| `POST` | `/api/v1/recommend` | Full recommendation pipeline | Yes |
| `POST` | `/api/v1/evaluate` | LLM-as-Judge evaluation | Yes |
| `POST` | `/api/v1/explain` | Human-readable risk explanation | Yes |
| `POST` | `/api/v1/feedback` | Store advisor rating | Yes |
| `GET` | `/api/v1/follow-up/cases` | List follow-up tickets | Yes |
| `POST` | `/api/v1/follow-up/cases` | Create follow-up ticket | Yes |
| `PATCH` | `/api/v1/follow-up/cases/{id}` | Update ticket | Yes |
| `POST` | `/api/v1/follow-up/cases/{id}/assess` | Assess follow-up | Yes |
| `POST` | `/api/v1/insights/factors` | Dataset factor analysis | Yes |
| `POST` | `/api/v1/parent-email/send` | Send parent email | Yes |
| `POST` | `/api/v1/admin/storage/init` | Create DB tables | Yes |
| `POST` | `/api/v1/admin/ingest` | Ingest CSV | Yes |
| `POST` | `/api/v1/admin/embeddings/build` | Build Qdrant embeddings | Yes |
| `POST` | `/api/v1/admin/models/train` | Train ML models | Yes |

See [`03_API.md`](03_API.md) for the complete API reference with request/response schemas and examples.

---

## Project Structure

```
student-success-assistant/
├── .env                          # Local configuration (not committed)
├── .env.example                  # Template for environment variables
├── README.md                     # This file
├── backend/
│   ├── pyproject.toml            # Python dependencies and metadata
│   ├── uv.lock                   # Locked dependency versions
│   ├── src/
│   │   └── student_success_assistant/
│   │       ├── main.py           # FastAPI app factory
│   │       ├── api/
│   │       │   ├── router.py     # Public vs protected route aggregation
│   │       │   └── routes/       # HTTP handlers (admin, auth, prediction, etc.)
│   │       ├── application/      # Use-case orchestration (18 services)
│   │       ├── core/             # Settings, security (HMAC auth)
│   │       ├── domain/           # Business concepts (StudentCase, model names)
│   │       ├── infrastructure/   # External adapters (PostgreSQL, Qdrant, etc.)
│   │       └── schemas/          # Pydantic request/response models
│   ├── tests/                    # pytest tests (health, API contracts, AI pipeline)
│   ├── artifacts/models/         # Trained ML model pickles
│   └── .venv/                    # Python virtual environment
├── frontend/
│   ├── package.json              # Node dependencies
│   ├── src/
│   │   ├── main.tsx              # Entry point
│   │   ├── app/App.tsx           # Auth gate + session management
│   │   ├── components/ui/        # Design-system primitives
│   │   ├── components/layout/    # AppShell, navigation
│   │   ├── features/auth/        # LoginPage
│   │   ├── features/dashboard/   # DashboardPage (6 tabs)
│   │   ├── shared/api/           # HTTP client + types
│   │   └── styles/               # Newsprint design tokens
│   └── dist/                     # Production build output
├── data/
│   ├── raw/                      # Original UCI CSVs (student-mat.csv, student-por.csv)
│   ├── processed/                # Merged dataset (student-merged.csv)
│   └── scripts/                  # Data merge utility (merge_student_data.py)
└── docs/
    ├── 01_ARCHITECTURE.md        # Architecture documentation
    ├── 02_DESIGN.md              # Design decisions
    ├── 03_API.md                 # Full API reference
    ├── 04_DATABASE.md            # Database schema and setup
    ├── 05_TESTING.md             # Testing strategy
    ├── 06_SECURITY.md            # Security architecture
    ├── 07_PRESENTATION.md        # Capstone presentation deck
    └── 08_README.md              # This file
```

---

## Development Commands

### Backend

```bash
cd backend
uv sync --extra full              # Install all dependencies
uv sync                           # Install base dependencies only
uv run uvicorn ...                # Start dev server
uv run pytest                     # Run tests
uv run pytest --cov               # Run tests with coverage
uv run pytest -v                  # Verbose test output
uv run ruff check src/            # Lint source code
uv run ruff format --check src/   # Check formatting
```

### Frontend

```bash
cd frontend
npm run dev                       # Start dev server (port 5173)
npm run build                     # Production build
npm run check                     # TypeScript type checking
```

---

## Testing

The project uses `pytest` with FastAPI `TestClient` for API-contract tests and hand-rolled fakes/mocks for pipeline logic. External dependencies (database, Qdrant, LLM) are isolated — no infrastructure required at test time.

```bash
cd backend
uv run pytest                     # Run all tests
uv run pytest -k "api"            # Run API contract tests
uv run pytest --cov=src           # Run with coverage report
```

Test files:
- `tests/test_health.py` — Liveness and readiness endpoint tests
- `tests/test_api_contracts.py` — Request/response contract tests
- `tests/test_ai_pipeline.py` — AI pipeline integration tests

See [`05_TESTING.md`](05_TESTING.md) for the full testing strategy.

---

## Deployment Notes

- **LLM is local** via Ollama — no API keys needed. Ensure `ollama serve` is running alongside the backend.
- **PostgreSQL** is hosted on Aiven cloud; configure `SSA_DATABASE_URL` with the connection string.
- **Qdrant** is hosted on Qdrant cloud; configure `SSA_QDRANT_URL` and `SSA_QDRANT_API_KEY`.
- All LLM-dependent features have **deterministic fallbacks** when the LLM is unavailable.
- The frontend builds to a static `dist/` folder that can be served by any web server or CDN.
- For production, set `SSA_AUTH_USERNAME`, `SSA_AUTH_PASSWORD`, and `SSA_AUTH_TOKEN_SECRET` to strong values.
- Configure `SSA_SMTP_*` variables for real parent email delivery (defaults to simulated mode).
- No RBAC — this is a single-user system.
- No frontend tests are included.

---

## Documentation Index

| Document | Description |
|---|---|
| [`01_ARCHITECTURE.md`](01_ARCHITECTURE.md) | System architecture, C4 diagrams, layer details, key flows, design decisions |
| [`02_DESIGN.md`](02_DESIGN.md) | Design decisions, technology choices, tradeoff analysis |
| [`03_API.md`](03_API.md) | Full API reference with request/response schemas and examples |
| [`04_DATABASE.md`](04_DATABASE.md) | PostgreSQL schema, Qdrant vector store, data migration notes |
| [`05_TESTING.md`](05_TESTING.md) | Testing strategy, test structure, environment setup |
| [`06_SECURITY.md`](06_SECURITY.md) | HMAC authentication, token handling, security architecture |
| [`07_PRESENTATION.md`](07_PRESENTATION.md) | Capstone presentation slide deck (20 slides, PDF export) |
| [`08_README.md`](08_README.md) | This file — project overview, setup, and usage |

---

## License

This project is developed as a capstone submission for an enterprise academic program. The UCI Student Performance dataset is used under its original terms. See `data/` for dataset attribution.
