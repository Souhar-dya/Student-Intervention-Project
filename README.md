# AI-Powered Education Student Success Assistant

Full-stack scaffold for the Student Success Assistant described in the project brief.
The backend and frontend are intentionally separated so each layer can evolve with a
clean architecture.

## Project Layout

```text
backend/   FastAPI service, uv-managed Python dependencies, tests
frontend/  React + Vite application using the Newsprint design system
```

## Backend

Python dependency management is standardized on `uv`.

```powershell
cd backend
uv sync
uv run pytest
uv run uvicorn student_success_assistant.main:app --app-dir src --reload
```

Configuration lives in the root `.env` file. Use `.env.example` as the safe template
when sharing setup instructions, and keep real local secrets out of version control.

The dashboard uses a simple advisor login before sensitive student APIs can be called.
For local development the default credentials are `advisor` / `advisor-demo`; change
these in `.env` before sharing the app:

- `SSA_AUTH_USERNAME`
- `SSA_AUTH_PASSWORD`
- `SSA_AUTH_TOKEN_SECRET`
- `SSA_AUTH_TOKEN_TTL_SECONDS`

Install the full AI stack when working on retrieval, LangGraph agents, prediction, or
explainability:

```powershell
uv sync --extra full
```

Backend dependency rules:

- `backend/pyproject.toml` is the source of truth.
- `backend/uv.lock` should be committed after `uv sync` or `uv lock` succeeds.
- Do not add a Python `requirements.txt` for normal development.
- Use `uv run ...` for backend commands.
- Keep heavyweight AI/ML dependencies in named extras so the basic API/test workflow stays fast.

Initial backend endpoints:

- `GET /health`
- `GET /ready`
- `GET /api/v1/health`
- `GET /api/v1/ready`
- `POST /api/v1/search`
- `POST /api/v1/predict`
- `POST /api/v1/explain`
- `POST /api/v1/recommend`
- `POST /api/v1/evaluate`
- `POST /api/v1/feedback`
- `POST /api/v1/parent-email/send`
- `POST /api/v1/admin/storage/init`
- `POST /api/v1/admin/ingest`
- `POST /api/v1/admin/ingest/batch`
- `POST /api/v1/admin/embeddings/build`
- `POST /api/v1/admin/models/train`

The advisor endpoints use real service boundaries and fall back to deterministic local
behavior when optional infrastructure is unavailable.

LLM configuration uses separate models for generation and judging:

- `SSA_LLM_MODEL`: recommendation-generation model
- `SSA_LLM_TEMPERATURE`: recommendation variety setting, default `0.7`
- `SSA_JUDGE_MODEL`: LLM-as-judge evaluation model
- `SSA_PREDICTION_MODEL`: app-facing risk model, defaulting to the interpretable `advisor_score`
- `SSA_SELECTED_MODEL`: trained artifact fallback, defaulting to `logistic_regression`

Parent email sending is guarded to medium-risk and high-risk students. Without SMTP
settings, the endpoint returns a simulated delivery so the workflow remains testable.
Configure these variables for real delivery:

- `SSA_SMTP_HOST`
- `SSA_SMTP_PORT`
- `SSA_SMTP_USERNAME`
- `SSA_SMTP_PASSWORD`
- `SSA_SMTP_FROM_EMAIL`
- `SSA_SMTP_USE_TLS`

Agent orchestration uses LangGraph when the `agents` extra is installed. The recommendation
workflow is structured as retrieval, prediction, recommendation, and explanation graph nodes
with advisor tools for case summaries, risk summaries, feedback examples, and intervention
drafting. Without `agents`, the endpoint keeps working through the deterministic fallback path.

### Backend Pipeline

Install the full backend stack before running the data and AI workflows:

```powershell
cd backend
uv sync --extra full
```

Initialize PostgreSQL tables:

```powershell
uv run python -m uvicorn student_success_assistant.main:app --app-dir src --reload
```

Then call:

```http
POST http://localhost:8000/api/v1/admin/storage/init
```

The app uses the canonical merged dataset by default:

```text
../data/processed/student-merged.csv
```

Regenerate it from the two raw CSV files:

```powershell
python data/scripts/merge_student_data.py
```

Ingest only when you add a new CSV or need to refresh the database:

```http
POST http://localhost:8000/api/v1/admin/ingest
Content-Type: application/json

{
  "path": "../data/processed/student-merged.csv",
  "persist": true
}
```

Build embeddings and upload cases to Qdrant:

```http
POST http://localhost:8000/api/v1/admin/embeddings/build
Content-Type: application/json

{
  "limit": 1000
}
```

Train and select the best prediction model:

```http
POST http://localhost:8000/api/v1/admin/models/train
Content-Type: application/json

{
  "path": "../data/processed/student-merged.csv"
}
```

## Frontend

The frontend is a standalone Vite app with centralized Newsprint tokens and reusable UI
primitives.

```powershell
cd frontend
npm install
npm run dev
```

Set `VITE_API_BASE_URL` if the backend is not running at `http://localhost:8000/api/v1`.

The UI should preserve the Newsprint design language: sharp corners, high-contrast
editorial typography, visible grid borders, sparse red accents, and responsive layouts.
