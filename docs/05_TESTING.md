# Testing — AI-Powered Student Success Assistant

## 1. Testing Strategy

The project follows a **practical, API-first testing strategy** focused on exercising the FastAPI application layer with real HTTP semantics, while isolating external dependencies (vector store, LLM, database) behind fake implementations. The goal is high confidence in endpoint contracts and business logic without requiring external infrastructure at test time.

| Layer | Approach | Tools |
|-------|----------|-------|
| API contracts | FastAPI `TestClient` against `create_app()` | `httpx`, `pytest` |
| Pipeline logic | Fake/mock implementations of stores and providers | `unittest.mock`, hand-rolled fakes |
| Health/readiness | Lightweight endpoint assertions | `TestClient` |

There are **no frontend tests** (React Testing Library is not configured).

---

## 2. Test Pyramid

```
         /\
        /  \           API contract tests (end-to-end via TestClient,
       /    \           covering auth, predict, search, recommend,
      /______\          feedback, ingest, explain, insights, follow-up)
     /        \
    /          \        Pipeline / unit tests (hybrid retrieval,
   /            \       embedding pipeline, agent workflow)
  /______________\
 /                  \   No distinct unit/service-layer test suite;
/                    \  pipeline tests double as unit tests
```

All tests sit at the **integration** or **pipeline** level — there are no isolated unit tests for individual domain functions.

---

## 3. Test Files

### 3.1 `conftest.py`

Sets environment variables **before any application code is imported**, overriding settings that would otherwise require a running PostgreSQL, Qdrant, or OpenAI instance.

| Variable | Value | Purpose |
|----------|-------|---------|
| `SSA_DATABASE_URL` | `""` | Prevents SQLAlchemy engine init |
| `SSA_OPENAI_API_KEY` | `""` | Disables real LLM calls |
| `SSA_QDRANT_URL` | `""` | Disables Qdrant client init |
| `LANGCHAIN_TRACING_V2` / `SSA_LANGCHAIN_TRACING_V2` | `"false"` | Disables LangSmith telemetry |
| `SSA_AUTH_USERNAME` / `SSA_AUTH_PASSWORD` | `"advisor"` / `"advisor-demo"` | Fixed test credentials |
| `SSA_AUTH_TOKEN_SECRET` | `"test-only-auth-secret"` | Deterministic JWT signing |

### 3.2 `test_health.py`

Lightest-weight test in the suite. Verifies the unauthenticated `/health` endpoint responds `{"status": "ok"}` on a bare `TestClient(create_app())`.

| Test | What it asserts |
|------|-----------------|
| `test_health_returns_ok` | `GET /health` → `200`, JSON is `{"status": "ok"}` |

### 3.3 `test_ai_pipeline.py`

Tests core AI components using **hand-rolled fake classes** (`FakeEmbeddingProvider`, `FakeQdrantStore`, `FakeCaseRepository`, `FakeReranker`) that implement the same interface as production collaborators but return deterministic data.

| Test | What it asserts |
|------|-----------------|
| `test_hybrid_retrieval_uses_dense_sparse_rrf_and_reranker` | `RetrievalService.search()` executes dense (Qdrant), sparse (BM25 repo), reciprocal-rank fusion, and reranking, returning results ordered by the reranker |
| `test_embedding_to_qdrant_pipeline_uploads_one_case` | `EmbeddingPipeline.run()` creates the Qdrant collection, embeds text, and upserts points with correct payload |
| `test_workflow_accepts_retrieved_qdrant_cases_for_recommendation_context` | `AgentWorkflow.generate_recommendation()` accepts a `GroundingContext` with prediction + retrieved cases and returns a response or `None` |
| `test_xgboost_model_name_is_available_for_training_results` | Verifies the `XGBOOST_MODEL` constant equals `"xgboost"` |

### 3.4 `test_api_contracts.py`

The largest test file. Exercises every major API endpoint through `TestClient` with **real HTTP request/response serialization**. Authentication is handled by `authenticated_client()` which logs in via `/api/v1/auth/login` and attaches the JWT bearer token.

| Category | Test | What it asserts |
|----------|------|-----------------|
| **Auth** | `test_login_rejects_invalid_credentials` | Wrong password → `401` |
| **Auth** | `test_protected_endpoints_require_login` | `/api/v1/predict` without token → `401` |
| **Predict** | `test_predict_returns_risk_category` | Valid student → `200`, `risk_category`, `model_name`, `top_contributors` sum to `risk_score` |
| **Predict** | `test_predict_rejects_invalid_attendance` | Attendance > 100 → `422` |
| **Predict** | `test_low_previous_average_pushes_risk_higher` | Lower grades → `"High Risk"`, `grade_gap` contribution > 0.12 |
| **Search** | `test_search_returns_baseline_cases` | Valid query → `200`, `total`, `results` with correct school |
| **Feedback** | `test_feedback_is_accepted` | Valid feedback → `201`, `{"stored": true}` |
| **Recommend** | `test_recommend_returns_grounded_response` | Prediction + search → `200`, `student_id`, `recommendation`, `evidence_case_ids` |
| **Admin** | `test_ingest_csv_without_persistence` | Single CSV ingest → `200`, `imported == 1` |
| **Admin** | `test_batch_ingest_csv_without_persistence` | Batch CSV ingest → `200`, `imported == 1` per file |
| **Health** | `test_readiness_reports_dependency_configuration` | `GET /api/v1/ready` → `"ready"` or `"degraded"` with checks for all dependencies |
| **Explain** | `test_explain_returns_feature_contributions` | `POST /api/v1/explain` → `200`, `top_contributors`, `explanation` containing "Risk is" |
| **Insights** | `test_factor_insights_use_default_merged_dataset` | Default dataset → `row_count == 382`, `generated_by == "deterministic"` |
| **Insights** | `test_factor_insights_answer_custom_top_students_prompt` | Custom prompt → response references "top-performing students" and "merged-" |
| **Insights** | `test_factor_insights_include_family_features` | Family prompt → `factors` > 20 with "family" features |
| **Insights** | `test_factor_insights_reject_unrelated_prompts` | Irrelevant prompt → `generated_by == "guardrail"`, `factors == []` |
| **Tool Runtime** | `test_advisor_tool_runtime_drafts_intervention` | `draft_intervention(prediction)` → output contains "Immediate action:", "Support plan:", "Follow-up check:" |
| **Tool Runtime** | `test_advisor_tool_runtime_uses_feedback_as_prompt_examples` | `retrieve_feedback_examples()` → output with "follow this pattern", "avoid this pattern" |
| **Parent Email** | `test_parent_email_sends_only_for_medium_or_high_risk` | Medium risk → `eligible == true`, `sent == true`, `delivery_status` "sent" or "simulated" |
| **Parent Email** | `test_parent_email_skips_low_risk_students` | Low risk → `eligible == false`, `sent == false`, `delivery_status == "skipped"` |
| **Follow-up** | `test_follow_up_assessment_escalates_when_two_week_progress_is_weak` | Weak progress → `decision == "Escalate"`, `escalation_target == "Counsellor"` |
| **Follow-up** | `test_follow_up_assessment_closes_when_progress_is_clear` | Good progress → `decision == "Close ticket"`, `recommended_status == "Closed"` |

---

## 4. Mocking Strategy

The project uses **two distinct isolation techniques**:

### 4.1 Environment-Variable Overrides (conftest.py)

Early environment variable assignment prevents production clients (SQLAlchemy engine, Qdrant client, OpenAI client) from initialising at all. This is a coarse-grained isolation — any code path that would attempt a real connection simply short-circuits because required config is empty.

### 4.2 Hand-Rolled Fake Classes (test_ai_pipeline.py)

For pipeline tests, each external dependency is replaced by a purpose-built fake:

| Production Dependency | Fake | Behaviour |
|-----------------------|------|-----------|
| Embedding provider | `FakeEmbeddingProvider` | Returns `[1.0, 0.0, 0.0]` for any input |
| Qdrant vector store | `FakeQdrantStore` | In-memory store; tracks `collection_ready`, records upserted points, returns deterministic search results |
| Case repository (PostgreSQL) | `FakeCaseRepository` | Returns static case lists for `list_cases`, `search_cases` |
| Reranker | `FakeReranker` | Sorts by `case_id` descending (deterministic ordering) |

These fakes implement the same duck-typed interface as the real classes, so no mocking framework (`unittest.mock`) is needed for pipeline tests.

### 4.3 No `unittest.mock` Usage

The codebase does not use `patch` or `Mock`. All isolation is achieved through dependency injection of fake objects (pipeline tests) or TestClient against a fully-wired app that uses in-memory deterministic backends (API contract tests).

---

## 5. Fixture Architecture

`conftest.py` is the sole fixture file. It contains **no pytest fixtures** — it only sets environment variables at module load time.

| File | Fixtures Defined | Scope |
|------|------------------|-------|
| `conftest.py` | None (env vars only) | Module (executed before any test) |

Test files produce their own test helpers inline:
- `test_api_contracts.py` defines `authenticated_client()` — a plain function (not a fixture) that creates a `TestClient`, logs in, and returns the authed client.
- `test_ai_pipeline.py` instantiates its own fake classes per test function.

The `tmp_path` built-in fixture is used in `test_ingest_csv_without_persistence` and `test_batch_ingest_csv_without_persistence` to create temporary CSV files.

---

## 6. Running Tests

### 6.1 Prerequisites

```bash
cd backend
uv sync
```

### 6.2 Run All Tests

```bash
uv run pytest
```

### 6.3 Run With Coverage

```bash
uv run pytest --cov=student_success_assistant --cov-report=term-missing
```

### 6.4 Run a Specific Test File

```bash
uv run pytest tests/test_api_contracts.py -v
```

### 6.5 Run a Specific Test

```bash
uv run pytest tests/test_api_contracts.py::test_predict_returns_risk_category -v
```

### 6.6 Configuration (pyproject.toml)

```toml
[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
addopts = "-q"
```

---

## 7. Coverage Targets and Current Gaps

### 7.1 Targets

- **Overall coverage target**: ≥ 80 %
- **Critical paths** (prediction, recommendation, auth): ≥ 90 %

### 7.2 Current Coverage Scope

| Module | Covered By |
|--------|-----------|
| `routes/` (all API endpoints) | `test_api_contracts.py` |
| `application/retrieval_service.py` | `test_ai_pipeline.py` |
| `application/embedding_pipeline.py` | `test_ai_pipeline.py` |
| `application/agent_workflow.py` | `test_ai_pipeline.py` |
| `application/agent_tools.py` | `test_api_contracts.py` |
| `main.py` / `create_app()` | `test_health.py`, `test_api_contracts.py` |

### 7.3 Known Gaps

| Area | Reason | Priority |
|------|--------|----------|
| Database repository layer | No test database is configured; SQLAlchemy models are untested | High |
| LLM client factory | No tests for model selection / fallback logic | Medium |
| SHAP explanation service | Exercise via API test only; no isolated unit tests | Medium |
| XGBoost training pipeline | Only the model name constant is tested | Low |
| Frontend | No frontend tests exist | Not planned |

---

## 8. CI/CD Integration

No CI/CD pipeline (GitHub Actions, GitLab CI, etc.) is currently configured. When one is added, the recommended workflow is:

```yaml
# Recommended CI steps
- name: Install dependencies
  run: cd backend && uv sync

- name: Run tests with coverage
  run: cd backend && uv run pytest --cov=student_success_assistant --cov-report=xml

- name: Upload coverage
  uses: codecov/codecov-action@v4
```

All tests run **without external infrastructure** — no database, no vector store, no LLM API key — so they can execute in any CI environment without service containers or secrets.

---

## Appendix A: Dependency Graph

```
conftest.py  (env var overrides)
    |
    +-- test_health.py           (no imports from src)
    |
    +-- test_api_contracts.py    (imports schemas, main, domain/model_names, agent_tools)
    |       |
    |       +-- create_app()     (fully wired with in-memory deterministic backends)
    |       +-- TestClient       (httpx ASGI transport)
    |
    +-- test_ai_pipeline.py      (imports application layer + schemas)
            |
            +-- RetrievalService (+ fakes)
            +-- EmbeddingPipeline (+ fakes)
            +-- AgentWorkflow    (+ fakes)
```

## Appendix B: Test Count

| File | Test Functions | Lines |
|------|---------------|-------|
| `test_health.py` | 1 | 13 |
| `test_ai_pipeline.py` | 4 | 181 |
| `test_api_contracts.py` | 22 | 525 |
| **Total** | **27** | **719** |
