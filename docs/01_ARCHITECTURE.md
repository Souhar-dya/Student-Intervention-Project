# Architecture — AI-Powered Student Success Assistant

> **Document version:** 1.0  
> **Project:** Student Success Assistant  
> **Last updated:** 2026-06-15

---

## High-Level Architecture

```mermaid
C4Context
  Person(advisor, "Academic Advisor", "Uses the dashboard to assess student risk and get intervention recommendations")
  System_Boundary(app, "Student Success Assistant") {
    System(Frontend, "React + Vite SPA", "Port 5173\nNewsprint design system")
    System(Backend, "FastAPI Backend", "Port 8000\nHexagonal architecture")
    Boundary(ext, "External Services") {
      SystemDb(PostgreSQL, "PostgreSQL", "Aiven cloud\nStudent cases, feedback,\nfollow-up tickets")
      SystemDb(Qdrant, "Qdrant", "Cloud vector DB\nDense embeddings (384d)")
      SystemDb(Ollama, "Ollama", "Local LLM\nllama3.2:3b")
      System_Ext(Smtp, "SMTP", "Parent email\ndelivery")
    }
  }
  Rel(advisor, Frontend, "HTTPS", "Uses")
  Rel_Boundary(Backend, Frontend, "REST / JSON")
  Rel(Backend, PostgreSQL, "psycopg", "SQL")
  Rel(Backend, Qdrant, "gRPC/REST", "Vector search")
  Rel(Backend, Ollama, "HTTP", "LLM inference")
  Rel(Backend, Smtp, "SMTP", "Email")
  UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="2")
```

---

## Architecture Style: Hexagonal (Ports and Adapters)

The backend follows the **Hexagonal Architecture** (also called Ports and Adapters) pattern to keep business logic independent of frameworks, databases, and external services.

```
                    ┌─────────────────────┐
                    │     FastAPI HTTP     │  ← Adapter (inbound)
                    │     (api/routes/)    │
                    └─────────┬───────────┘
                              │
                    ┌─────────▼───────────┐
                    │   Application       │  ← Orchestration
                    │   (application/)    │
                    └──┬──────────────┬───┘
                       │              │
              ┌────────▼───┐   ┌─────▼────────┐
              │  Domain    │   │ Infrastructure│  ← Adapter (outbound)
              │ (domain/)  │   │(infrastructure)│
              └────────────┘   └──────┬────────┘
                                      │
                    ┌─────────────────▼──────┐
                    │  PostgreSQL │ Qdrant    │
                    │  Ollama │ SMTP          │  ← External systems
                    └────────────────────────┘
```

### Why Hexagonal Architecture

- **Framework independence**: Domain concepts (`StudentCase`, `outcome_from_grade`) have no import on FastAPI, SQLAlchemy, or any framework. They can be unit-tested without infrastructure.
- **Swapable infrastructure**: The retrieval service falls back from Qdrant → PostgreSQL → baseline search without changing any business logic. Each adapter implements the same contract.
- **Testability**: Application services accept dependencies via constructor injection (see `RetrievalService.__init__`), allowing mocks in tests.
- **Evolution**: Adding a new ML model, vector store, or LLM provider means writing a new adapter, not rewriting the orchestration.

### Layer Mapping

| Layer | Directory | Responsibility |
|---|---|---|
| **Domain** | `domain/` | Pure business concepts: `StudentCase` dataclass, `model_names` constants, `outcome_from_grade()` |
| **Application** | `application/` | Use-case orchestration: retrieval, prediction, recommendation, evaluation, follow-up, feedback, insights, agents |
| **Infrastructure** | `infrastructure/` | External adapters: PostgreSQL (`StudentRepository`, `FollowUpRepository`), Qdrant (`QdrantCaseStore`), embeddings (`EmbeddingProvider`), reranker (`Reranker`) |
| **API** | `api/routes/` | HTTP adapters: thin route handlers that validate input, call application services, return schemas |
| **Schemas** | `schemas/` | Pydantic models defining API boundaries: request/response contracts |
| **Core** | `core/` | Cross-cutting: `Settings` via pydantic-settings, custom HMAC-based auth |

---

## System Context

| Component | Technology | Port | Purpose |
|---|---|---|---|
| **Frontend** | React 18 + Vite + TypeScript | 5173 | Newsprint-styled SPA for advisors |
| **Backend** | Python 3.11+ / FastAPI | 8000 | REST API, orchestration, all business logic |
| **Database** | PostgreSQL (Aiven cloud) | — | Student records, cases, feedback, evaluations, follow-up tickets |
| **Vector DB** | Qdrant (cloud) | — | Dense embedding storage and similarity search |
| **LLM** | Ollama (local) / OpenAI-compatible | 11434 | Recommendation generation, LLM-as-judge |
| **Embeddings** | BAAI/bge-small-en-v1.5 | — | 384-dim dense vectors |
| **Reranker** | BAAI/bge-reranker-base | — | Cross-encoder reranking |
| **Prediction** | XGBoost / Logistic Regression / Random Forest | — | Risk score from student features |
| **Explainability** | SHAP | — | Feature attribution for ML predictions |
| **SMTP** | Configurable | — | Parent email notifications |

---

## Software Development Lifecycle: Hybrid V-Model + Iterative AI

```
                    ┌─────────────────────────────────┐
                    │        Requirements & Design     │
                    │  (Student Case, API contracts)    │
                    └────────────┬────────────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
    ┌─────────────────┐  ┌──────────────┐  ┌──────────────┐
    │ Database Schema │  │  API Design  │  │ Frontend UI  │
    │ (V-Model: fixed)│  │ (V-Model)    │  │ (V-Model)    │
    └────────┬────────┘  └──────┬───────┘  └──────┬───────┘
             │                  │                  │
    ┌────────▼──────────────────▼──────────────────▼────────┐
    │                Integration Layer                       │
    │  (FastAPI app, routes, middleware, auth)               │
    └──────────────┬───────────────────────────────────────┘
                   │
    ┌──────────────▼───────────────────────────────────────┐
    │               AI Modules (Iterative)                  │
    │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐  │
    │  │Prompts   │ │Retrieval │ │Prediction│ │Evalua- │  │
    │  │& Agents  │ │(Hybrid)  │ │(ML/SHAP) │ │tion    │  │
    │  └──────────┘ └──────────┘ └──────────┘ └────────┘  │
    │                                                       │
    │  Each AI module has its own inner loop:               │
    │    Experiment → Evaluate → Refine → Deploy           │
    └──────────────────────────────────────────────────────┘
```

**Why hybrid?** Traditional components (database schema, API routes, frontend pages) benefit from up-front specification and follow a V-Model where each design phase maps to a test phase. AI components — prompts, retrieval strategies, prediction thresholds, evaluation rubrics — require empirical tuning. Separating the cycles means a prompt change does not trigger a full regression of the database layer, and a schema migration does not derail an ongoing prompt experiment.

---

## Backend Architecture

### Package Structure

```
backend/src/student_success_assistant/
├── __init__.py
├── main.py                          # FastAPI app factory + CORS
├── api/
│   ├── __init__.py
│   ├── router.py                    # Public vs protected route aggregation
│   └── routes/
│       ├── __init__.py
│       ├── admin.py                 # POST /admin/storage/init, /ingest, /embeddings/build, /models/train
│       ├── auth.py                  # POST /auth/login, GET /auth/me
│       ├── evaluation.py            # POST /evaluate
│       ├── explanation.py           # POST /explain
│       ├── feedback.py              # POST /feedback
│       ├── follow_up.py             # GET/POST/PATCH /follow-up/cases, /follow-up/assess
│       ├── health.py                # GET /health, GET /ready
│       ├── insights.py              # POST /insights/factors
│       ├── parent_notification.py   # POST /parent-email/send
│       ├── prediction.py            # POST /predict
│       ├── recommendation.py        # POST /recommend
│       └── retrieval.py             # POST /search
├── application/
│   ├── __init__.py
│   ├── agent_tools.py               # AdvisorToolRuntime: LangChain tools for graph
│   ├── agent_workflow.py            # LangGraph StateGraph definition + direct LLM fallback
│   ├── embedding_pipeline.py        # EmbeddingPipeline: DB → embedding → Qdrant upload
│   ├── evaluation_service.py        # LLM-as-judge with deterministic fallback
│   ├── explanation_service.py       # Human-readable risk explanation from contributors
│   ├── feedback_service.py          # Advisor feedback capture (DB + in-memory fallback)
│   ├── follow_up_service.py         # Two-week review: LLM assessment or deterministic rubric
│   ├── ingestion_service.py         # CSV → StudentCase → DB insert
│   ├── insights_service.py          # Factor analysis from merged dataset
│   ├── intervention_planner.py      # Deterministic intervention plan drafting
│   ├── llm_client.py                # LangChain LLM factory: Ollama or OpenAI
│   ├── parent_notification_service.py # SMTP-based parent emails with simulated fallback
│   ├── prediction_service.py        # Risk prediction: baseline or ML artifact
│   ├── recommendation_service.py     # Full recommend pipeline: predict → retrieve → plan → agent
│   ├── retrieval_service.py         # Hybrid search: dense + BM25 + RRF + reranker
│   └── training_service.py          # LR / RF / XGBoost training with sklearn pipelines
├── core/
│   ├── __init__.py
│   ├── config.py                    # Pydantic Settings from environment / .env
│   └── security.py                  # HMAC-based token creation and verification
├── domain/
│   ├── __init__.py
│   ├── model_names.py               # Named constants for model identifiers
│   └── student_case.py              # StudentCase dataclass, domain functions
├── infrastructure/
│   ├── __init__.py
│   ├── database.py                  # psycopg connection management, schema DDL
│   ├── embeddings.py                # SentenceTransformer wrapper with hash fallback
│   ├── follow_up_repository.py      # Follow-up CRUD with event history
│   ├── qdrant_store.py              # Qdrant client wrapper: search, upsert, collection management
│   ├── reranker.py                  # CrossEncoder wrapper for reranking
│   └── student_repository.py        # Student case CRUD, feedback, evaluation storage
└── schemas/
    ├── __init__.py
    ├── admin.py                     # InitializeStorageResponse, IngestDatasetRequest, etc.
    ├── auth.py                      # LoginRequest, AuthSession
    ├── evaluation.py                # EvaluationRequest, JudgeScores, EvaluationResponse
    ├── explanation.py               # ExplanationRequest, ExplanationResponse
    ├── feedback.py                  # FeedbackRequest, FeedbackResponse, FeedbackRating
    ├── follow_up.py                 # FollowUpDecision, PlanFollowed, ProgressTrend, etc.
    ├── health.py                    # HealthResponse, ReadinessCheck, ReadinessResponse
    ├── insights.py                  # FactorInsightRequest, FactorInsight, FactorInsightResponse
    ├── parent_notification.py       # ParentEmailRequest, ParentEmailResponse
    ├── prediction.py                # PredictionRequest, PredictionResponse, RiskCategory
    ├── recommendation.py            # RecommendationRequest, RecommendationResponse
    ├── retrieval.py                 # SearchRequest, SearchFilters, RetrievedCase, SearchResponse
    └── student.py                   # StudentProfile
```

### Layer Responsibilities

#### Domain Layer (`domain/`)

Framework-agnostic business concepts. No imports from FastAPI, SQLAlchemy, or any external library.

| File | Contents |
|---|---|
| `student_case.py` | `StudentCase` frozen dataclass, `attendance_from_absences()`, `outcome_from_grade()`, `build_case_narrative()` |
| `model_names.py` | Constants: `ADVISOR_SCORE_MODEL`, `LOGISTIC_REGRESSION_MODEL`, `RANDOM_FOREST_MODEL`, `XGBOOST_MODEL` |

```python
@dataclass(frozen=True)
class StudentCase:
    student_id: str
    school: str
    age: int
    study_time: int
    failures: int
    absences: int
    previous_grade_average: float
    final_grade: int
    outcome: str
```

#### Application Layer (`application/`)

Use-case orchestration services. Each service is a plain class that depends on interfaces (or concrete adapters with constructor injection).

| Service | Key Methods | Dependencies |
|---|---|---|
| `RetrievalService` | `search()` | `QdrantCaseStore`, `EmbeddingProvider`, `StudentRepository`, `Reranker` |
| `PredictionService` | `predict()` | (none — self-contained with sklearn) |
| `RecommendationService` | `recommend()` | `PredictionService`, `RetrievalService`, `AgentWorkflow` |
| `ExplanationService` | `explain()` | `PredictionService` |
| `EvaluationService` | `evaluate()` | `StudentRepository`, LLM |
| `FeedbackService` | `store_feedback()` | `StudentRepository` |
| `FollowUpService` | `assess()` | LLM (with deterministic rubric fallback) |
| `InsightsService` | `summarize_factors()` | LLM (with deterministic fallback) |
| `IngestionService` | `ingest_csv()` | `StudentRepository` |
| `TrainingService` | `train()` | sklearn, xgboost |
| `ParentNotificationService` | `send_parent_email()` | SMTP |
| `AgentWorkflow` | `generate_recommendation()` | LangGraph, LLM, `AdvisorToolRuntime` |
| `EmbeddingPipeline` | `run()` | `StudentRepository`, `QdrantCaseStore`, `EmbeddingProvider` |

#### Infrastructure Layer (`infrastructure/`)

Adapters for external systems. Each adapter isolates the external library so no other layer needs to import it.

| Adapter | Library | Purpose |
|---|---|---|
| `database.py` | psycopg (v3) | Connection management, schema DDL for 6 tables |
| `student_repository.py` | psycopg | CRUD: students, cases, feedback, evaluations |
| `follow_up_repository.py` | psycopg | CRUD: follow-up cases, event history, assessments |
| `qdrant_store.py` | qdrant-client | Collection management, dense vector search, upsert |
| `embeddings.py` | sentence-transformers | BGE embedding generation with hash-based fallback |
| `reranker.py` | sentence-transformers | CrossEncoder reranking for top-k refinement |

**Fallback strategy**: Every infrastructure adapter has a graceful degradation path. `RetrievalService` tries Qdrant first, then PostgreSQL text matching, then a hardcoded baseline. `EmbeddingProvider` falls back to hash-based sparse embeddings when `enable_remote_models` is `False`. This ensures the app works end-to-end without expensive cloud dependencies during development.

#### API Layer (`api/routes/`)

Thin HTTP handlers. Each route validates input via Pydantic, delegates to an application service, and returns a schema response.

**Route organization** (`router.py`):
- **Public** (no auth): `GET /health`, `GET /ready`, `POST /auth/login`, `GET /auth/me`
- **Protected** (Bearer token required): everything under `/api/v1/` — `/predict`, `/search`, `/recommend`, `/evaluate`, `/explain`, `/feedback`, `/follow-up/*`, `/insights/factors`, `/parent-email/send`, `/admin/*`

Handler pattern (example from `prediction.py`):
```python
@router.post("/predict", response_model=PredictionResponse)
def predict(
    request: PredictionRequest,
    service: PredictionService = Depends(get_prediction_service),
) -> PredictionResponse:
    return service.predict(request)
```

#### Schemas Layer (`schemas/`)

Pydantic v2 models that define the public API contracts. All request/response validation happens here.

| Schema | Purpose |
|---|---|
| `StudentProfile` | Student features: school, age, attendance, failures, study time, grades |
| `SearchFilters` | Metadata filters: school, attendance range, failures range |
| `SearchRequest` / `SearchResponse` | Hybrid search contract with `RetrievedCase` results |
| `PredictionRequest` / `PredictionResponse` | Risk prediction input/output with `FeatureContribution` list |
| `RecommendationRequest` / `RecommendationResponse` | Combined prediction + search + generated recommendation |
| `EvaluationRequest` / `EvaluationResponse` | LLM-as-judge scoring with `JudgeScores` |
| `FeedbackRequest` / `FeedbackResponse` | Advisor rating (useful/not_useful) |
| `FollowUpAssessmentRequest` / `FollowUpAssessmentResponse` | Two-week review assessment |
| `FactorInsightRequest` / `FactorInsightResponse` | Dataset factor analysis |
| `ParentEmailRequest` / `ParentEmailResponse` | Parent notification via SMTP |

#### Core Layer (`core/`)

| File | Purpose |
|---|---|
| `config.py` | `Settings` class via `pydantic-settings`. Reads from `.env` with `SSA_` prefix. Cached via `@lru_cache`. Configures LangChain environment variables. |
| `security.py` | Custom HMAC-SHA256 token generation/verification. No JWT library dependency. Supports configurable TTL. |

### Database Schema

Six PostgreSQL tables managed via inline DDL in `database.py`:

```
students
├── student_id (PK, TEXT)
├── school, age, attendance, failures, absences, study_time
├── previous_grade_average, final_grade, outcome
└── raw_payload (JSONB)

student_cases
├── case_id (PK, TEXT)
├── student_id (FK → students)
├── case_text (TEXT)
└── payload (JSONB)

feedback
├── feedback_id (PK, TEXT)
├── query, recommendation, rating, advisor_note
└── created_at (TIMESTAMPTZ)

evaluation_results
├── evaluation_id (PK, TEXT)
├── query, recommendation, scores (JSONB), notes
└── created_at (TIMESTAMPTZ)

follow_up_cases
├── case_id (PK, TEXT)
├── student_id, student_profile (JSONB), parent_email, school
├── risk_category, risk_score, model_name
├── recommendation, recommendation_summary, evidence_case_ids (JSONB)
├── note, status, escalation_target, last_event
├── plan_followed, attendance_trend, marks_trend, failures_trend
├── follow_up_decision, rationale, next_steps, confidence, generated_by
├── follow_up_assessed_at, closed_at, created_at, updated_at
└── events via FK → follow_up_events

follow_up_events
├── event_id (PK, TEXT)
├── case_id (FK → follow_up_cases, CASCADE)
├── event_type, title, note, payload (JSONB)
└── created_at (TIMESTAMPTZ)
```

Indexes: `idx_follow_up_cases_status` on `status`, `idx_follow_up_events_case_id` on `case_id`.

---

## Key Flows

### 1. RAG Pipeline (Hybrid Search + Reranker)

```
Query → Metadata Filtering
         │
         ├── Dense Search (Qdrant + BGE embeddings) ──┐
         │                                             │
         ├── Sparse Search (BM25 via rank-bm25) ───────┤
         │                                             │
         └── Repository Fallback (PostgreSQL) ────────┘
                                                       │
                                                 RRF Fusion
                                                 (k=60)
                                                       │
                                              Top 20 candidates
                                                       │
                                         Cross-Encoder Reranker
                                         (BAAI/bge-reranker-base)
                                                       │
                                               Top 5 results
                                                       │
                                            LLM Recommendation
```

**Implementation** (`retrieval_service.py`, `RetrievalService._search_hybrid`):

1. **Dense search**: Query embedded via `BAAI/bge-small-en-v1.5` (384-dim). Searched in Qdrant with payload filters (school, attendance range, failures range). Cosine distance. Returns up to 20 candidates.
2. **Sparse search**: Same filters applied to PostgreSQL. `rank_bm25` (BM25Okapi) scores queries against case text corpus. If `rank_bm25` is not installed, falls back to term-overlap scoring. Returns up to 20 candidates.
3. **RRF Fusion**: Reciprocal Rank Fusion with k=60. Each candidate gets `1 / (k + rank)` per ranking. Scores are summed across dense and sparse. Sorted descending.
4. **Reranker**: Top 20 from RRF are scored by `BAAI/bge-reranker-base` cross-encoder. Query + case_text pairs are fed to `model.predict()`. Top 5 returned with updated scores.
5. **Fallback chain**: If Qdrant is not configured, falls to PostgreSQL-only search with term overlap + structured similarity scoring. If PostgreSQL is unavailable, returns a hardcoded baseline case.

### 2. Prediction Pipeline

```
Student Features → Model Selection
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
   Advisor Score  ML Artifact  Baseline
   (interpretable) (LR/RF/XGB) (fallback)
        │           │
        ▼           ▼
   Risk Score    Risk Score
   [0.01-0.99]  [0.01-0.99]
        │           │
        ▼           ▼
   Risk Category  Risk Category
   (Low/Med/High) + SHAP values
```

**Implementation** (`prediction_service.py`):

- **Advisor Score** (default): A transparent baseline using five weighted components:
  - `base_risk`: 0.12
  - `failures`: capped at 0.48 (0.16 per failure)
  - `attendance_gap`: up to 0.30 based on deviation from 85%
  - `grade_gap`: up to 0.38 based on distance from 10/20
  - `study_time`: -0.03 per level above 1 (protective)
- **ML Artifacts**: Pickled `sklearn.pipeline.Pipeline` with `DictVectorizer` + classifier. Supports `LogisticRegression`, `RandomForestClassifier`, `XGBClassifier`. Feature contributions computed via `SHAP` (when available) or `coef_`/`feature_importances_`.
- **Risk categories**: Low (< 0.32), Medium (0.32–0.62), High (≥ 0.62).

### 3. LangGraph Agent Workflow

```
                    ┌──────────────┐
      Entry ──────▶ │  Retrieval   │
                    │   Agent      │
                    │ (summarize   │
                    │  cases)      │
                    └──────┬───────┘
                           ▼
                    ┌──────────────┐
                    │  Prediction  │
                    │   Agent      │
                    │ (summarize   │
                    │  risk)       │
                    └──────┬───────┘
                           ▼
                    ┌──────────────┐
                    │Recommendation│
                    │   Agent      │
                    │ (draft plan +│
                    │  feedback    │
                    │  examples +  │
                    │  LLM call)   │
                    └──────┬───────┘
                           ▼
                    ┌──────────────┐
                    │ Explanation  │
                    │   Agent      │
                    │ (top drivers)│
                    └──────┬───────┘
                           ▼
                         END
```

**Implementation** (`agent_workflow.py`, `StateGraph(AdvisorGraphState)`):

- Four sequential nodes: `retrieve → predict → recommend → explain`
- Each node is a Python function that reads/writes `AdvisorGraphState` (a `TypedDict`)
- The `recommend` node uses `AdvisorToolRuntime` to:
  1. Draft a deterministic intervention plan
  2. Retrieve historical feedback examples (useful patterns to follow, not-useful patterns to avoid)
  3. Retrieve judge-scored recommendation examples
  4. Call the LLM (Ollama or OpenAI) with all context assembled
- **Fallback**: If `langgraph` is not installed, generates recommendation via direct LLM call with equivalent context
- State includes: `query`, `prediction`, `retrieved_cases`, `student_profile_summary`, `evidence_case_ids`, `tool_outputs`, `recommendation`, `reasoning`

### 4. Follow-Up Review (Two-Week Assessment)

```
Follow-Up Request (advisor note + trends)
        │
        ▼
  ┌──────┴──────┐
  │ LLM Judge   │  JSON: decision, status, escalation, rationale
  │ (if avail)  │
  └──────┬──────┘
         │ (fail)
         ▼
  ┌──────────────┐
  │ Deterministic│  Rubric: signals (attendance, marks, failures,
  │ Rubric       │  plan_followed, advisor note keywords)
  └──────┬──────┘
         │
         ▼
  Decision: Close Ticket / Monitor / Escalate
```

**Implementation** (`follow_up_service.py`):

- **LLM path**: Calls judge model with structured prompt asking for JSON. Fields: `decision` (Close ticket/Monitor/Escalate), `recommended_status`, `escalation_target`, `rationale`, `next_steps`, `confidence`.
- **Deterministic rubric**: Counts positive/negative signals from trends. Escalates on: high risk + negative signals, increased failures, plan not followed with no improvement, concerning advisor note keywords. Closes only when plan was fully followed, ≥2 positive signals, no negative signals, risk < 0.65.
- **Escalation targets**: High risk → Counsellor, Medium risk → Academic advisor, Low risk → Class teacher.

### 5. Feedback Loop

```
Advisor Rates Recommendation
        │
   Useful / Not Useful
        │
        ▼
Stored in feedback table (PostgreSQL)
        │
        ▼
(Future) Retrieved as examples
in AgentWorkflow recommendations
        │
        ▼
LLM prompt includes:
  "Treat useful feedback as patterns to follow
   and not-useful feedback as patterns to avoid"
```

**Implementation** (`feedback_service.py`):
- Stores rating, query, recommendation, optional advisor note
- Falls back to in-memory list if PostgreSQL is unavailable
- `AgentWorkflow` retrieves latest `feedback_examples_limit` (default 3) entries for both useful and judged recommendations and injects them into the LLM prompt
- This creates a continuous improvement loop without retraining

---

## Frontend Architecture

### Structure

```
frontend/src/
├── main.tsx                    # Entry point
├── app/
│   └── App.tsx                 # Auth gate + session management
├── components/
│   ├── ui/                     # Design-system primitives (Button, etc.)
│   └── layout/                 # AppShell, navigation, layout
├── features/
│   ├── auth/
│   │   └── LoginPage.tsx       # Login form
│   └── dashboard/
│       └── DashboardPage.tsx   # Main workflow dashboard
├── shared/
│   └── api/
│       ├── client.ts           # HTTP client (fetch-based, no axios)
│       └── types.ts            # TypeScript interfaces matching API schemas
└── styles/                     # Newsprint design tokens, global CSS
```

### Dashboard Screen Flow

```
LoginPage (auth gate)
        │
        ▼
   AppShell
        │
        ▼
  DashboardPage
        │
  ┌──────┴───────────────────────────────────────────────────────┐
  │  StepNav (6 tabs)                                            │
  │                                                              │
  │  Prepare     Student     Analysis     Evaluate   Follow Up   │
  │  (pipeline)  (intake)    (risk +      (judge +   (tickets +  │
  │              + query)    recommend)   feedback)  assessment)  │
  │                                                              │
  │  Factors (success signals from dataset)                      │
  └──────────────────────────────────────────────────────────────┘
```

| Tab | API Calls | UI Components |
|---|---|---|
| **Prepare** | `init-storage`, `ingest-dataset`, `build-embeddings`, `train-models` | Pipeline buttons, metric panels, pipeline log |
| **Student** | (form only) | School, ID, email, numeric fields, advisor query |
| **Analysis** | `full-analysis` (search + predict + recommend) | Risk score card, retrieved cases list, recommendation text, evidence IDs |
| **Evaluate** | `evaluate`, `feedback`, `parent-email/send` | Judge scores (4 dimensions + overall), useful/not-useful buttons, email form |
| **Follow Up** | `follow-up/cases` (list, save, update, assess) | Ticket cards grouped by risk, detail view with trends, assessment button |
| **Factors** | `insights/factors` | Prompt input, guardrail-checked LLM answer, factor list |

The frontend communicates with the backend exclusively through `shared/api/client.ts`, which wraps `fetch()` with auth token injection and error handling. All responses are typed via `shared/api/types.ts`.

---

## API Structure

### Public Endpoints (no auth required)

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness probe — returns `{"status": "ok"}` |
| `GET` | `/ready` | Readiness probe — checks DB, Qdrant, LLM, LangGraph, LangChain |
| `POST` | `/auth/login` | Validates credentials, returns HMAC token |
| `GET` | `/auth/me` | Returns current session info from Bearer token |

### Protected Endpoints (Bearer token required)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/predict` | Risk prediction from student features |
| `POST` | `/api/v1/search` | Hybrid retrieval with filters |
| `POST` | `/api/v1/recommend` | Full recommendation: predict + search + agent |
| `POST` | `/api/v1/evaluate` | LLM-as-judge or rubric-based evaluation |
| `POST` | `/api/v1/explain` | Human-readable risk explanation |
| `POST` | `/api/v1/feedback` | Store advisor rating (useful/not_useful) |
| `GET` | `/api/v1/follow-up/cases` | List follow-up tickets |
| `POST` | `/api/v1/follow-up/cases` | Create follow-up ticket from analysis |
| `PATCH` | `/api/v1/follow-up/cases/{id}` | Update ticket with trends and notes |
| `POST` | `/api/v1/follow-up/cases/{id}/assess` | Trigger two-week review assessment |
| `POST` | `/api/v1/follow-up/assess` | Direct assessment without saving |
| `POST` | `/api/v1/insights/factors` | Dataset factor analysis |
| `POST` | `/api/v1/parent-email/send` | Send parent notification email |
| `POST` | `/api/v1/admin/storage/init` | Create PostgreSQL tables |
| `POST` | `/api/v1/admin/ingest` | Import CSV into DB |
| `POST` | `/api/v1/admin/ingest/batch` | Batch import multiple CSVs |
| `POST` | `/api/v1/admin/embeddings/build` | Build and upload Qdrant embeddings |
| `POST` | `/api/v1/admin/models/train` | Train and persist ML models |

### Authentication

Custom HMAC-based token (not JWT):
- Payload: `{"sub": username, "exp": unix_timestamp}` base64url-encoded
- Signature: `HMAC-SHA256(payload, secret)` base64url-encoded
- Format: `{encoded_payload}.{signature}`
- Configurable TTL via `SSA_AUTH_TOKEN_TTL_SECONDS` (default 8 hours)
- Static credentials via `SSA_AUTH_USERNAME` / `SSA_AUTH_PASSWORD`

---

## Configuration

All configuration is managed through environment variables with the `SSA_` prefix, loaded by `pydantic-settings` from a root `.env` file.

| Variable | Default | Description |
|---|---|---|
| `SSA_DATABASE_URL` | — | PostgreSQL connection string |
| `SSA_QDRANT_URL` | `http://localhost:6333` | Qdrant endpoint |
| `SSA_QDRANT_API_KEY` | — | Qdrant API key |
| `SSA_QDRANT_COLLECTION` | `student_cases` | Qdrant collection name |
| `SSA_EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | SentenceTransformer model |
| `SSA_EMBEDDING_DIMENSION` | `384` | Vector dimension |
| `SSA_ENABLE_REMOTE_MODELS` | `false` | Enable model downloads |
| `SSA_RERANKER_MODEL` | `BAAI/bge-reranker-base` | CrossEncoder model |
| `SSA_LLM_PROVIDER` | `ollama` | `ollama` or `openai` |
| `SSA_LLM_MODEL` | `llama3.2:3b` | Generation model |
| `SSA_JUDGE_MODEL` | `llama3.2:3b` | Evaluation model |
| `SSA_LLM_TEMPERATURE` | `0.7` | Generation temperature |
| `SSA_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint |
| `SSA_OPENAI_API_KEY` | — | OpenAI API key |
| `SSA_OPENAI_BASE_URL` | — | Custom OpenAI-compatible endpoint |
| `SSA_PREDICTION_MODEL` | `advisor_score` | Default risk model |
| `SSA_SELECTED_MODEL` | `logistic_regression` | ML artifact fallback |
| `SSA_SMTP_HOST` | — | SMTP server (empty = simulated) |
| `SSA_AUTH_USERNAME` | `advisor` | Login username |
| `SSA_AUTH_PASSWORD` | `advisor-demo` | Login password |
| `SSA_AUTH_TOKEN_SECRET` | — | HMAC signing secret |
| `SSA_FEEDBACK_EXAMPLES_LIMIT` | `3` | Examples injected into LLM prompt |

---

## Design Decisions

### Why Hexagonal Architecture

The hexagonal pattern was chosen over a traditional layered architecture because the system integrates multiple external services (PostgreSQL, Qdrant, Ollama, SMTP) that are expected to change independently. By depending on abstractions (e.g., `case_store.search()` rather than `QdrantClient.search()`), each external integration can be replaced, mocked, or bypassed without ripple effects. This is critical for development velocity: the app runs fully offline with deterministic fallbacks, cloud services are added incrementally, and tests never need a running database.

### Why Qdrant over pgvector

| Factor | Qdrant | pgvector |
|---|---|---|
| Scaling | Independent cluster, separate from OLTP | Shares PostgreSQL resources |
| Managed cloud | Native cloud with dashboard | Requires self-management or extension setup |
| Hybrid search | Primary focus, built-in | Requires additional extension/layer |
| Filtering | Payload filtering with range/match conditions | JSONB filtering combined with ANN |
| Indexing | HNSW with configurable parameters | IVFFlat or HNSW |

Qdrant allows the vector search infrastructure to scale independently of the relational database, supports managed cloud deployment without operational overhead, and provides straightforward hybrid search capabilities through client-side combination with BM25.

### Why LangGraph

LangGraph was chosen over a simple chain-of-thought prompt or a framework like LangChain LCEL for three reasons:

1. **State graph**: The recommendation workflow has clear independent stages (retrieve, predict, recommend, explain), each producing artifacts that later stages consume. LangGraph's `StateGraph` models this naturally.
2. **Built-in persistence**: Each graph invocation maintains typed state across nodes, with tool outputs accumulating in `tool_outputs` for the final LLM call.
3. **Graceful degradation**: When LangGraph is not installed, the system falls back to the same logic executed inline. This lets developers work on the agent workflow without being blocked by missing dependencies.

### Why BGE Embeddings (BAAI/bge-small-en-v1.5)

- **Quality/size tradeoff**: 384-dim vectors versus the 768-dim or 1024-dim alternatives. 384-dim reduces storage and latency while maintaining competitive retrieval accuracy on the MTEB benchmark.
- **Lightweight**: The Small variant runs on CPU with acceptable latency, enabling local development without GPU infrastructure.
- **Normalized embeddings**: The model outputs L2-normalized vectors by default, which makes cosine similarity equivalent to dot product and simplifies the Qdrant configuration.

### Why Hybrid Search (Dense + Sparse)

Dense retrieval (BGE embeddings) captures semantic similarity: "student struggling with attendance" will match "learner with poor class presence" even when no keywords overlap. Sparse retrieval (BM25) captures keyword precision: "absences" matches only documents containing "absences" or its surface forms. The two are combined via RRF because each excels in different scenarios:

- Dense wins on reformulated queries and synonym-rich text
- Sparse wins on narrow queries with domain-specific terms (e.g., "GPA < 10")
- RRF combines them without requiring training data or score normalization

### Why RRF (Reciprocal Rank Fusion)

RRF was chosen over weighted-score fusion or learning-to-rank because:

- **No training required**: RRF works with the raw rank positions, which are available without calibration across different scoring functions (cosine similarity vs BM25 score).
- **Parameter simplicity**: Only the constant `k` (set to 60, a common default) needs tuning.
- **Empirical effectiveness**: RRF consistently outperforms score averaging or max fusion across heterogeneous retrieval systems in information retrieval benchmarks.

### Why Cross-Encoder Reranker (BAAI/bge-reranker-base)

The cross-encoder performs full attention between query and document, producing more accurate relevance scores than the bi-encoder used in first-stage retrieval. The tradeoff is computational cost — the cross-encoder is O(n) where n is the sequence length, making it prohibitive for large-scale retrieval. By applying it only to the top 20 candidates from RRF fusion, the system gets the accuracy benefit without the latency penalty.
