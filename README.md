# AI-Powered Student Success Assistant

**Capstone Project** — UCI Student Performance Dataset | FastAPI + React + PostgreSQL + Qdrant + Ollama

AI-powered dashboard for academic advisors to assess student risk, retrieve similar cases, generate intervention recommendations, and track follow-up outcomes.

## Quick Start

```bash
# Backend
cd backend && uv sync --extra full
ollama serve                              # start local LLM (llama3.2:3b)
uv run uvicorn student_success_assistant.main:app --app-dir src --reload

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
```

```bash
# Initialize pipeline (after starting backend)
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" \
  -d '{"username":"advisor","password":"advisor-demo"}' | python -c "import sys,json;print(json.load(sys.stdin)['token'])")
curl -X POST http://localhost:8000/api/v1/admin/storage/init -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:8000/api/v1/admin/ingest -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"path":"../data/processed/student-merged.csv","persist":true}'
curl -X POST http://localhost:8000/api/v1/admin/embeddings/build -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"limit":1000}'
curl -X POST http://localhost:8000/api/v1/admin/models/train -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"path":"../data/processed/student-merged.csv"}'
```

## Architecture

- **Hexagonal Architecture** — Domain, Application, Infrastructure, API, Schemas, Core layers
- **Hybrid Retrieval** — Dense (BGE-small-en-v1.5, 384d) + Sparse (BM25) + RRF fusion + BGE-reranker-base
- **LangGraph Agent Workflow** — 4-node state graph (retrieve → predict → recommend → explain)
- **Risk Prediction** — Advisor score baseline or trained ML (LR, RF, XGBoost) with SHAP explainability
- **HMAC Authentication** — Custom bearer tokens (not JWT), single-user, no RBAC
- **Deterministic Fallbacks** — All LLM-dependent features work without Ollama or cloud services

## Tech Stack

| Layer | Stack |
|---|---|
| Backend | Python 3.11+ / FastAPI / uv |
| Frontend | React 19 / Vite 7 / TypeScript / Tailwind v4 (Newsprint) |
| Database | PostgreSQL 16 (Aiven cloud) |
| Vector DB | Qdrant (cloud) |
| LLM | Ollama (local, llama3.2:3b) — no API key needed |
| ML | scikit-learn, XGBoost, SHAP |
| Agent | LangGraph + LangChain Ollama |
| Tests | pytest, httpx, FastAPI TestClient |

## Project Layout

```
backend/        FastAPI service (port 8000)
frontend/       React + Vite SPA (port 5173)
data/           UCI dataset (raw CSVs + merged CSV + merge script)
docs/           Architecture, API reference, design, database, security, testing
```

## Docs

| Doc | Description |
|---|---|
| `docs/01_ARCHITECTURE.md` | System architecture, C4 diagrams, layer details, key flows |
| `docs/02_DESIGN.md` | Design decisions and tradeoff analysis |
| `docs/03_API.md` | Full API reference with schemas and examples |
| `docs/04_DATABASE.md` | PostgreSQL schema, Qdrant vector store |
| `docs/05_TESTING.md` | Testing strategy and environment setup |
| `docs/06_SECURITY.md` | HMAC authentication and security architecture |
| `docs/07_PRESENTATION.md` | Capstone presentation deck (20 slides) |
| `docs/08_README.md` | Comprehensive project README |
| `docs/09_DIAGRAMS.md` | 11 Mermaid diagrams for all system views |
