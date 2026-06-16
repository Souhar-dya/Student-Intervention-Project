# API Reference — AI-Powered Student Success Assistant

> **Version:** 0.1.0  
> **Base URL (protected):** `/api/v1`  
> **Public endpoints:** `/health`, `/ready`, `/auth/login`, `/auth/me`  
> **Authentication:** HMAC-SHA256 bearer token  

---

## Table of Contents

1. [Authentication & Security](#1-authentication--security)
2. [System](#2-system)
3. [Auth](#3-auth)
4. [Prediction](#4-prediction)
5. [Retrieval](#5-retrieval)
6. [Recommendation](#6-recommendation)
7. [Evaluation (LLM-as-Judge)](#7-evaluation-llm-as-judge)
8. [Explanation](#8-explanation)
9. [Feedback](#9-feedback)
10. [Follow-Up](#10-follow-up)
11. [Insights (Factor Analysis)](#11-insights-factor-analysis)
12. [Parent Notification](#12-parent-notification)
13. [Admin](#13-admin)

---

## 1. Authentication & Security

**Token scheme:** HMAC-SHA256 (not JWT). The token is a base64url-encoded JSON payload concatenated with a dot and an HMAC-SHA256 signature.

```
{base64url(payload)}.{base64url(HMAC-SHA256(payload, secret))}
```

**Payload fields:**
| Field | Type | Description |
|-------|------|-------------|
| `sub` | string | Username |
| `exp` | integer | Expiration Unix timestamp (default 8 hours) |

**Send as header:**
```
Authorization: Bearer <token>
```

**Credentials** (configurable via environment variables):
| Variable | Default |
|----------|---------|
| `SSA_AUTH_USERNAME` | `advisor` |
| `SSA_AUTH_PASSWORD` | `advisor-demo` |
| `SSA_AUTH_TOKEN_SECRET` | `change-this-local-development-secret` |
| `SSA_AUTH_TOKEN_TTL_SECONDS` | `28800` (8 hours) |

---

## 2. System

### 2.1 Health Check

Returns a simple liveness indicator.

| Attribute | Value |
|-----------|-------|
| **Purpose** | Liveness probe |
| **Method** | `GET` |
| **Path** | `/health` |
| **Authentication** | None |

**Response Schema**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Always `"ok"` |

**Status Codes**
| Code | Description |
|------|-------------|
| `200` | Service is alive |

**Example**

```bash
curl -s http://localhost:8000/health | python -m json.tool
```

```json
{
  "status": "ok"
}
```

---

### 2.2 Readiness Check

Reports whether external dependencies are configured.

| Attribute | Value |
|-----------|-------|
| **Purpose** | Readiness probe — checks DB, Qdrant, LLM, LangGraph, LangChain |
| **Method** | `GET` |
| **Path** | `/ready` |
| **Authentication** | None |

**Response Schema**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `"ready"` when DB + Qdrant are configured; `"degraded"` otherwise |
| `checks` | object | Map of component name → `ReadinessCheck` |

**ReadinessCheck Schema**

| Field | Type | Description |
|-------|------|-------------|
| `configured` | boolean | Whether the component has required config |
| `detail` | string | Human-readable detail message |

**Components checked**

| Key | Configured when |
|-----|-----------------|
| `database` | `SSA_DATABASE_URL` is set |
| `qdrant` | `SSA_QDRANT_URL` + `SSA_QDRANT_API_KEY` are set |
| `llm` | `SSA_OPENAI_API_KEY` is set |
| `langgraph` | `langgraph` package is installed |
| `langchain` | `SSA_LANGCHAIN_API_KEY` or `SSA_LANGCHAIN_PRIVATE_API_KEY` is set |

**Status Codes**
| Code | Description |
|------|-------------|
| `200` | Readiness report returned (even if degraded) |

**Example**

```bash
curl -s http://localhost:8000/ready | python -m json.tool
```

```json
{
  "status": "degraded",
  "checks": {
    "database": {
      "configured": false,
      "detail": "SSA_DATABASE_URL is empty"
    },
    "qdrant": {
      "configured": false,
      "detail": "Qdrant URL or API key is missing"
    },
    "llm": {
      "configured": true,
      "detail": "generation=llama3.2:3b, judge=llama3.2:3b"
    },
    "langgraph": {
      "configured": false,
      "detail": "Install agent dependencies with `uv sync --extra agents`"
    },
    "langchain": {
      "configured": false,
      "detail": "LangChain/LangSmith key is optional and empty"
    }
  }
}
```

---

## 3. Auth

### 3.1 Login

Exchange credentials for an HMAC-SHA256 bearer token.

| Attribute | Value |
|-----------|-------|
| **Purpose** | Authenticate and receive a bearer token |
| **Method** | `POST` |
| **Path** | `/auth/login` |
| **Authentication** | None |

**Request Body**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `username` | string | 1–120 chars | Username |
| `password` | string | 1–200 chars | Password |

**Response Schema — `AuthSession`**

| Field | Type | Description |
|-------|------|-------------|
| `token` | string | HMAC-SHA256 bearer token |
| `token_type` | string | Always `"bearer"` |
| `username` | string | Authenticated username |

**Status Codes**
| Code | Description |
|------|-------------|
| `200` | Login successful |
| `401` | Invalid username or password |

**Validation Rules**

- `username` and `password` are compared using constant-time `hmac.compare_digest`
- Token expires after `SSA_AUTH_TOKEN_TTL_SECONDS` (default 8 hours)

**Example**

```bash
curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "advisor", "password": "advisor-demo"}' | python -m json.tool
```

```json
{
  "token": "eyJzdWIiOiJhZHZpc29yIiwiZXhwIjoxNzE4MDAwMDAwfQ.abc123signature",
  "token_type": "bearer",
  "username": "advisor"
}
```

---

### 3.2 Current Session

Return the authenticated user's session info.

| Attribute | Value |
|-----------|-------|
| **Purpose** | Verify token and return current user info |
| **Method** | `GET` |
| **Path** | `/auth/me` |
| **Authentication** | Bearer token required |

**Response Schema — `AuthSession`**

| Field | Type | Description |
|-------|------|-------------|
| `token` | string | Empty string (token not re-issued) |
| `token_type` | string | Always `"bearer"` |
| `username` | string | Authenticated username |

**Status Codes**
| Code | Description |
|------|-------------|
| `200` | Token is valid |
| `401` | Missing or invalid token |

**Example**

```bash
curl -s http://localhost:8000/auth/me \
  -H "Authorization: Bearer eyJzdWIiOiJhZHZpc29yIiwiZXhwIjoxNzE4MDAwMDAwfQ.abc123signature" | python -m json.tool
```

```json
{
  "token": "",
  "token_type": "bearer",
  "username": "advisor"
}
```

---

## 4. Prediction

### 4.1 Predict Risk

Assess a student's at-risk probability using either a trained model or a deterministic baseline formula.

| Attribute | Value |
|-----------|-------|
| **Purpose** | Compute risk score and category for a student |
| **Method** | `POST` |
| **Path** | `/api/v1/predict` |
| **Authentication** | Bearer token required |

**Request Body — `PredictionRequest`**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `student` | `StudentProfile` | — | Student demographic and academic profile |
| `model_name` | string \| null | min 1 char | Optional model override; defaults to `SSA_PREDICTION_MODEL` |

**StudentProfile Schema**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `student_id` | string \| null | min 1 char | Optional unique identifier |
| `parent_email` | string \| null | max 254 chars | Parent email for notifications |
| `school` | string | 2 chars | School code (e.g. `"GP"`, `"MS"`) |
| `age` | integer | 15–22 | Student age |
| `attendance` | integer | 0–100 | Attendance percentage |
| `failures` | integer | 0–4 | Number of past class failures |
| `absences` | integer | 0–100 | Number of absences |
| `study_time` | integer | 1–4 | Study time category (1 = low, 4 = high) |
| `previous_grade_average` | float | 0–20 | Average of G1 and G2 scores |

**Available Models**

| Model Name | Description |
|------------|-------------|
| `advisor_score` | Baseline formula (always available) |
| `logistic_regression` | Logistic Regression (requires trained artifact) |
| `random_forest` | Random Forest (requires trained artifact) |
| `xgboost` | XGBoost (requires trained artifact + `xgboost` package) |

**Risk Thresholds**

| Category | Threshold |
|----------|-----------|
| High | `risk_score >= 0.62` |
| Medium | `risk_score >= 0.32` |
| Low | `risk_score < 0.32` |

**Baseline Formula (`advisor_score`)**

```
base_risk (0.12)
+ failures * 0.16 (capped at 0.48)
+ attendance_gap: max((85 - attendance) / 85, 0) * 0.3 (capped at 0.30)
+ grade_gap: ((max((10 - grade_avg) / 10, 0) * 0.65 + (max((10 - grade_avg) / 10, 0))^2 * 0.35) * 0.38 (capped at 0.38)
- study_time: (study_time - 1) * 0.03 (capped at 0.09, subtracted)
Final: clamped to [0.01, 0.99]
```

**Response Schema — `PredictionResponse`**

| Field | Type | Description |
|-------|------|-------------|
| `student_id` | string \| null | Student identifier from request |
| `risk_score` | float (0–1) | Probability of at-risk outcome |
| `risk_category` | string | `"Low Risk"`, `"Medium Risk"`, or `"High Risk"` |
| `model_name` | string | Model used for prediction |
| `top_contributors` | `[FeatureContribution]` | Up to 5 top contributing features |

**FeatureContribution Schema**

| Field | Type | Description |
|-------|------|-------------|
| `feature` | string | Feature name (e.g. `"failures"`, `"attendance_gap"`, `"grade_gap"`) |
| `contribution` | float | Signed contribution to risk score |

**Status Codes**
| Code | Description |
|------|-------------|
| `200` | Prediction successful |
| `401` | Missing or invalid token |

**Example**

```bash
curl -s -X POST http://localhost:8000/api/v1/predict \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "student": {
      "school": "GP",
      "age": 18,
      "attendance": 78,
      "failures": 2,
      "absences": 12,
      "study_time": 2,
      "previous_grade_average": 8.5
    }
  }' | python -m json.tool
```

```json
{
  "student_id": null,
  "risk_score": 0.789,
  "risk_category": "High Risk",
  "model_name": "advisor_score",
  "top_contributors": [
    {
      "feature": "failures",
      "contribution": 0.32
    },
    {
      "feature": "grade_gap",
      "contribution": 0.214
    },
    {
      "feature": "attendance_gap",
      "contribution": 0.136
    },
    {
      "feature": "base_risk",
      "contribution": 0.12
    },
    {
      "feature": "study_time",
      "contribution": -0.03
    }
  ]
}
```

---

## 5. Retrieval

### 5.1 Search Cases

Retrieve similar student cases using hybrid search (Qdrant dense + BM25 sparse + RRF fusion + BGE reranker).

| Attribute | Value |
|-----------|-------|
| **Purpose** | Semantic + keyword search over historical student cases |
| **Method** | `POST` |
| **Path** | `/api/v1/search` |
| **Authentication** | Bearer token required |

**Request Body — `SearchRequest`**

| Field | Type | Constraints | Default | Description |
|-------|------|-------------|---------|-------------|
| `query` | string | min 3 chars | — | Natural language search query |
| `top_k` | integer | 1–20 | `5` | Number of results to return |
| `filters` | `SearchFilters` | — | `{}` | Optional structured filters |

**SearchFilters Schema**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `school` | string \| null | 2 chars | Two-letter school code |
| `min_attendance` | integer \| null | 0–100 | Minimum attendance percentage |
| `max_attendance` | integer \| null | 0–100 | Maximum attendance percentage |
| `min_failures` | integer \| null | 0–4 | Minimum past failures |
| `max_failures` | integer \| null | 0–4 | Maximum past failures |

**Search Pipeline**

1. **Dense retrieval** — Embed query with BGE-small-en-v1.5 → search Qdrant
2. **Sparse retrieval** — BM25 (via `rank_bm25` or term-overlap fallback) over PostgreSQL cases
3. **RRF fusion** — Reciprocal rank fusion with `k = 60`
4. **Reranking** — BGE-reranker-base re-scores top 20 candidates
5. **Fallback** — If Qdrant is unavailable, falls through to PostgreSQL text similarity → structured scoring → baseline synthetic results

**Response Schema — `SearchResponse`**

| Field | Type | Description |
|-------|------|-------------|
| `query` | string | Echoed search query |
| `total` | integer | Number of results returned |
| `results` | `[RetrievedCase]` | Ranked case results |

**RetrievedCase Schema**

| Field | Type | Description |
|-------|------|-------------|
| `case_id` | string | Unique case identifier |
| `student_id` | string | Student identifier |
| `score` | float (0–1) | Relevance score after reranking |
| `school` | string | School code |
| `failures` | integer | Past failures count |
| `absences` | integer | Absence count |
| `final_grade` | integer | Final grade (G3) |
| `case_text` | string | Narrative description of the case |

**Status Codes**
| Code | Description |
|------|-------------|
| `200` | Search completed |
| `401` | Missing or invalid token |

**Validation Rules**

- `query` must be at least 3 characters
- `top_k` clamped to 1–20

**Example**

```bash
curl -s -X POST http://localhost:8000/api/v1/search \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "student with high absences and failing grades",
    "top_k": 3,
    "filters": {
      "school": "GP",
      "min_failures": 1,
      "max_failures": 4
    }
  }' | python -m json.tool
```

```json
{
  "query": "student with high absences and failing grades",
  "total": 3,
  "results": [
    {
      "case_id": "case-001",
      "student_id": "GP-1234",
      "score": 0.892,
      "school": "GP",
      "failures": 3,
      "absences": 18,
      "final_grade": 6,
      "case_text": "Student attends GP school. Study time level is low. Previous failures: 3. Absences: 18. Final grade: 6. Outcome: At Risk."
    }
  ]
}
```

---

## 6. Recommendation

### 6.1 Generate Recommendation

Orchestrates the full prediction → retrieval → agent workflow to produce a grounded intervention recommendation.

| Attribute | Value |
|-----------|-------|
| **Purpose** | Generate an evidence-grounded intervention plan |
| **Method** | `POST` |
| **Path** | `/api/v1/recommend` |
| **Authentication** | Bearer token required |

**Request Body — `RecommendationRequest`**

| Field | Type | Description |
|-------|------|-------------|
| `prediction` | `PredictionRequest` | Student profile and optional model name |
| `search` | `SearchRequest` | Query and filters for similar case retrieval |

**Workflow**

1. **Predict** risk using `PredictionService`
2. **Augment** search query with current student details and auto-set filters (±15% attendance, ±1 failure)
3. **Retrieve** top 5 similar cases via `RetrievalService`
4. **Draft** baseline intervention plan via `draft_intervention_plan()`
5. **LangGraph** agent workflow (4 nodes: retrieve → predict → recommend → explain)
6. **Fallback** → direct LLM call → drafted intervention plan

**Response Schema — `RecommendationResponse`**

| Field | Type | Description |
|-------|------|-------------|
| `student_id` | string \| null | Student identifier |
| `risk_category` | string | `"Low Risk"`, `"Medium Risk"`, or `"High Risk"` |
| `recommendation` | string | Intervention plan text (immediate action + support plan + follow-up) |
| `reasoning` | string | Reasoning or provenance of the recommendation |
| `evidence_case_ids` | `[string]` | Case IDs of the top 5 retrieved evidence cases |

**Status Codes**
| Code | Description |
|------|-------------|
| `200` | Recommendation generated |
| `401` | Missing or invalid token |

**Example**

```bash
curl -s -X POST http://localhost:8000/api/v1/recommend \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "prediction": {
      "student": {
        "school": "GP",
        "age": 18,
        "attendance": 78,
        "failures": 2,
        "absences": 12,
        "study_time": 2,
        "previous_grade_average": 8.5
      }
    },
    "search": {
      "query": "students with attendance issues and past failures",
      "top_k": 5
    }
  }' | python -m json.tool
```

```json
{
  "student_id": null,
  "risk_category": "High Risk",
  "recommendation": "Immediate action: Risk is high at 79%. Start with an advisor meeting in the next 24-48 hours and assign one staff owner for the recovery plan.\nSupport plan: Prior failures need a confidence rebuild: ask each subject teacher for the smallest pass-critical task the student can complete first. Attendance is pulling risk upward, so set a weekly attendance target and ask the student to identify the top reason for missed classes. The grade gap is important, so schedule one focused tutoring or doubt-clearing session for the weakest subject area. Use the closest historical case (case-123, final grade 6) as a reference point, but adapt the plan to this student's current drivers.\nFollow-up check: Review attendance and grade movement twice a week for the first two weeks.",
  "reasoning": "Recommendation generated from validated student risk signals and the currently retrieved similar-case evidence.",
  "evidence_case_ids": [
    "case-123",
    "case-456",
    "case-789",
    "case-012",
    "case-345"
  ]
}
```

---

## 7. Evaluation (LLM-as-Judge)

### 7.1 Evaluate Recommendation

Score a recommendation across four quality dimensions using an LLM judge, with automatic fallback to a baseline rubric.

| Attribute | Value |
|-----------|-------|
| **Purpose** | LLM-as-Judge evaluation of recommendation quality |
| **Method** | `POST` |
| **Path** | `/api/v1/evaluate` |
| **Authentication** | Bearer token required |

**Request Body — `EvaluationRequest`**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `query` | string | min 3 chars | Advisor's original query |
| `recommendation` | string | min 3 chars | Generated recommendation text |
| `evidence_case_ids` | `[string]` | max 20 items | Case IDs used as evidence |

**Response Schema — `EvaluationResponse`**

| Field | Type | Description |
|-------|------|-------------|
| `scores` | `JudgeScores` | Scores across four dimensions |
| `notes` | string | Judge notes or fallback explanation |

**JudgeScores Schema**

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| `relevance` | integer | 1–10 | Relevance to the advisor query |
| `groundedness` | integer | 1–10 | Grounding in retrieved evidence |
| `consistency` | integer | 1–10 | Internal consistency |
| `usefulness` | integer | 1–10 | Practical usefulness for an advisor |
| `overall` | float | 1–10 | Computed average of the four scores |

**LLM Judge Prompt Structure**

The judge model (configured via `SSA_JUDGE_MODEL`) receives:
- The advisor query
- The recommendation text
- The evidence case IDs

And must return valid JSON with keys: `relevance`, `groundedness`, `consistency`, `usefulness`, `notes`.

**Baseline Rubric Fallback**

If the LLM judge is unavailable or returns unparseable output:

| Dimension | Score | Logic |
|-----------|-------|-------|
| relevance | 8 | Fixed |
| groundedness | 5 + min(len(evidence_ids), 5) | Evidence bonus |
| consistency | 8 | Fixed |
| usefulness | 7 or 5 | 7 if recommendation >= 40 chars, else 5 |

**Status Codes**
| Code | Description |
|------|-------------|
| `200` | Evaluation completed |
| `401` | Missing or invalid token |

**Validation Rules**

- `query` and `recommendation` must be at least 3 characters
- `evidence_case_ids` limited to 20 items

**Example**

```bash
curl -s -X POST http://localhost:8000/api/v1/evaluate \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "student with high absences and failing grades",
    "recommendation": "Set a weekly attendance target and schedule tutoring for math.",
    "evidence_case_ids": ["case-001", "case-002"]
  }' | python -m json.tool
```

```json
{
  "scores": {
    "relevance": 8,
    "groundedness": 7,
    "consistency": 8,
    "usefulness": 7,
    "overall": 7.5
  },
  "notes": "Automatic local judge used because no LLM judge is configured. Set SSA_OPENAI_API_KEY and SSA_JUDGE_MODEL to use LLM judging."
}
```

---

## 8. Explanation

### 8.1 Explain Prediction

Return top feature contributors with a natural-language explanation of the risk drivers.

| Attribute | Value |
|-----------|-------|
| **Purpose** | Explain why a student received a particular risk score |
| **Method** | `POST` |
| **Path** | `/api/v1/explain` |
| **Authentication** | Bearer token required |

**Request Body — `ExplanationRequest`**

| Field | Type | Description |
|-------|------|-------------|
| `prediction` | `PredictionRequest` | Student profile and optional model name |

**Response Schema — `ExplanationResponse`**

| Field | Type | Description |
|-------|------|-------------|
| `student_id` | string \| null | Student identifier |
| `risk_score` | float (0–1) | Risk score from prediction |
| `risk_category` | string | Risk category |
| `top_contributors` | `[FeatureContribution]` | Full list of feature contributions |
| `explanation` | string | Natural-language explanation focusing on top 3 non-system features |

**System features excluded from top-3 explanation:** `base_risk`, `score_cap`, `score_floor`

**Status Codes**
| Code | Description |
|------|-------------|
| `200` | Explanation generated |
| `401` | Missing or invalid token |

**Example**

```bash
curl -s -X POST http://localhost:8000/api/v1/explain \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "prediction": {
      "student": {
        "school": "GP",
        "age": 18,
        "attendance": 78,
        "failures": 2,
        "absences": 12,
        "study_time": 2,
        "previous_grade_average": 8.5
      }
    }
  }' | python -m json.tool
```

```json
{
  "student_id": null,
  "risk_score": 0.789,
  "risk_category": "High Risk",
  "top_contributors": [
    { "feature": "failures", "contribution": 0.32 },
    { "feature": "grade_gap", "contribution": 0.214 },
    { "feature": "attendance_gap", "contribution": 0.136 },
    { "feature": "base_risk", "contribution": 0.12 },
    { "feature": "study_time", "contribution": -0.03 }
  ],
  "explanation": "Risk is High Risk at 79%. Top drivers: failures moved risk by +0.32; grade_gap moved risk by +0.21; attendance_gap moved risk by +0.14."
}
```

---

## 9. Feedback

### 9.1 Store Feedback

Capture advisor feedback (useful / not useful) on a recommendation for future retrieval-based learning.

| Attribute | Value |
|-----------|-------|
| **Purpose** | Store advisor feedback for continuous improvement |
| **Method** | `POST` |
| **Path** | `/api/v1/feedback` |
| **Authentication** | Bearer token required |
| **Success Code** | `201 Created` |

**Request Body — `FeedbackRequest`**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `query` | string | min 3 chars | Original advisor query |
| `recommendation` | string | min 3 chars | Generated recommendation |
| `rating` | string | `"useful"` or `"not_useful"` | Advisor rating |
| `advisor_note` | string \| null | max 1000 chars | Optional advisor commentary |

**Response Schema — `FeedbackResponse`**

| Field | Type | Description |
|-------|------|-------------|
| `feedback_id` | string | UUID of stored feedback |
| `stored` | boolean | Whether feedback was persisted |
| `received_at` | string (ISO 8601) | Timestamp of receipt |
| `message` | string | Confirmation message |

**Storage behavior:** Attempts PostgreSQL `feedback` table first; falls back to in-memory list if unavailable.

**Status Codes**
| Code | Description |
|------|-------------|
| `201` | Feedback stored successfully |
| `401` | Missing or invalid token |

**Validation Rules**

- `query` and `recommendation` minimum 3 characters
- `rating` must be `"useful"` or `"not_useful"`
- `advisor_note` max 1000 characters

**Example**

```bash
curl -s -X POST http://localhost:8000/api/v1/feedback \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "student with high absences",
    "recommendation": "Set weekly attendance target and schedule tutoring.",
    "rating": "useful",
    "advisor_note": "Good suggestion, followed up with parent."
  }' | python -m json.tool
```

```json
{
  "feedback_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "stored": true,
  "received_at": "2026-06-15T10:30:00+00:00",
  "message": "Captured useful feedback for future retrieval-based learning."
}
```

---

## 10. Follow-Up

### 10.1 List Follow-Up Cases

Retrieve all follow-up cases, ordered by status (open first) then last updated.

| Attribute | Value |
|-----------|-------|
| **Purpose** | List all saved follow-up cases |
| **Method** | `GET` |
| **Path** | `/api/v1/follow-up/cases` |
| **Authentication** | Bearer token required |

**Response Schema — `[FollowUpCaseResponse]`**

See section 10.3 for the full schema.

**Status Codes**
| Code | Description |
|------|-------------|
| `200` | Cases returned |
| `401` | Missing or invalid token |
| `503` | Database unavailable |

**Example**

```bash
curl -s http://localhost:8000/api/v1/follow-up/cases \
  -H "Authorization: Bearer <token>" | python -m json.tool
```

---

### 10.2 Create Follow-Up Case

Save or upsert a follow-up case from a prediction and recommendation.

| Attribute | Value |
|-----------|-------|
| **Purpose** | Create (or update) a follow-up case for ongoing monitoring |
| **Method** | `POST` |
| **Path** | `/api/v1/follow-up/cases` |
| **Authentication** | Bearer token required |

**Request Body — `FollowUpCaseCreateRequest`**

| Field | Type | Description |
|-------|------|-------------|
| `student` | `StudentProfile` | Student profile |
| `prediction` | `PredictionResponse` | Full prediction result |
| `recommendation` | string | Intervention recommendation text |
| `recommendation_summary` | string | Optional shorter summary (auto-truncated to 220 chars) |
| `evidence_case_ids` | `[string]` | Case IDs used as evidence |

**Default status by risk category**

| Risk Category | Default Status | Default Escalation Target |
|---------------|----------------|---------------------------|
| High | `"Escalated"` | `"Counsellor"` |
| Medium | `"Open"` | `"Academic advisor"` |
| Low | `"Monitoring"` | `"Class teacher"` |

**Response Schema — `FollowUpCaseResponse`**

| Field | Type | Description |
|-------|------|-------------|
| `case_id` | string | Case ID (same as `student_id`) |
| `student_id` | string | Student identifier |
| `student` | `StudentProfile` | Student snapshot |
| `risk_category` | string | `"Low Risk"`, `"Medium Risk"`, `"High Risk"` |
| `risk_score` | float | Risk score at creation |
| `model_name` | string | Model used for prediction |
| `recommendation` | string | Full recommendation text |
| `recommendation_summary` | string | Short summary |
| `evidence_case_ids` | `[string]` | Evidence case IDs |
| `note` | string | Advisor note (empty at creation) |
| `status` | string | Case status |
| `escalation_target` | string | Escalation contact/title |
| `last_event` | string | Description of last event |
| `plan_followed` | string | Whether plan was followed (`"Unknown"` at creation) |
| `attendance_trend` | string | Attendance trend (`"No new evidence"` at creation) |
| `marks_trend` | string | Marks trend |
| `failures_trend` | string | Failures trend |
| `follow_up_decision` | string \| null | Assessment decision (null until assessed) |
| `follow_up_rationale` | string \| null | Assessment rationale |
| `follow_up_next_steps` | string \| null | Assessment next steps |
| `follow_up_confidence` | float \| null | Assessment confidence |
| `follow_up_generated_by` | string \| null | Assessment generator |
| `follow_up_assessed_at` | string \| null | Assessment timestamp |
| `closed_at` | string \| null | Closure timestamp |
| `created_at` | string | Creation timestamp |
| `updated_at` | string | Last update timestamp |
| `events` | `[FollowUpCaseEvent]` | Event history |

**Status Codes**
| Code | Description |
|------|-------------|
| `200` | Case created or updated |
| `401` | Missing or invalid token |
| `503` | Database unavailable |

**Example**

```bash
curl -s -X POST http://localhost:8000/api/v1/follow-up/cases \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "student": {
      "school": "GP",
      "age": 18,
      "attendance": 78,
      "failures": 2,
      "absences": 12,
      "study_time": 2,
      "previous_grade_average": 8.5
    },
    "prediction": {
      "student_id": null,
      "risk_score": 0.789,
      "risk_category": "High Risk",
      "model_name": "advisor_score",
      "top_contributors": [
        {"feature": "failures", "contribution": 0.32}
      ]
    },
    "recommendation": "Immediate action: Risk is high at 79%. Start with an advisor meeting.",
    "evidence_case_ids": ["case-001", "case-002"]
  }' | python -m json.tool
```

---

### 10.3 Update Follow-Up Case

Update status, note, escalation target, or progress trends on an existing case.

| Attribute | Value |
|-----------|-------|
| **Purpose** | Update a follow-up case with advisor notes and progress data |
| **Method** | `PATCH` |
| **Path** | `/api/v1/follow-up/cases/{case_id}` |
| **Authentication** | Bearer token required |

**Query Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `record_event` | boolean | `true` | Whether to log an event for this update |

**Request Body — `FollowUpCaseUpdateRequest`**

All fields optional; only provided fields are updated.

| Field | Type | Allowed Values | Description |
|-------|------|----------------|-------------|
| `note` | string \| null | — | Advisor note |
| `status` | string \| null | — | Case status |
| `escalation_target` | string \| null | — | Escalation contact |
| `last_event` | string \| null | — | Event description |
| `plan_followed` | string \| null | `"Fully followed"`, `"Partially followed"`, `"Not followed"`, `"Unknown"` | Plan adherence |
| `attendance_trend` | string \| null | `"Improved"`, `"No clear change"`, `"Worsened"`, `"No new evidence"` | Attendance trajectory |
| `marks_trend` | string \| null | `"Improved"`, `"No clear change"`, `"Worsened"`, `"No new evidence"` | Marks trajectory |
| `failures_trend` | string \| null | `"Decreased"`, `"No change"`, `"Increased"`, `"Unknown"` | Failure trajectory |

**Status auto‑management:** Setting status to `"Closed"` sets `closed_at` to current timestamp; removing `"Closed"` sets `closed_at` to NULL.

**Response Schema — `FollowUpCaseResponse`**

Same as section 10.2.

**Status Codes**
| Code | Description |
|------|-------------|
| `200` | Case updated |
| `401` | Missing or invalid token |
| `404` | Case not found |
| `503` | Database unavailable |

**Example**

```bash
curl -s -X PATCH "http://localhost:8000/api/v1/follow-up/cases/GP-1234?record_event=true" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "note": "Student showed slight improvement in attendance, but marks still low.",
    "plan_followed": "Partially followed",
    "attendance_trend": "Improved",
    "marks_trend": "No clear change"
  }' | python -m json.tool
```

---

### 10.4 Assess Saved Case

Run an LLM-powered or rubric-based assessment on a saved follow-up case using the stored advisor note and progress data.

| Attribute | Value |
|-----------|-------|
| **Purpose** | Assess a saved follow-up case (close, monitor, or escalate) |
| **Method** | `POST` |
| **Path** | `/api/v1/follow-up/cases/{case_id}/assess` |
| **Authentication** | Bearer token required |

**Request Body:** None (uses data from the saved case)

**Prerequisites**

- Case must exist
- Case must have a non-empty `note` (advisor must document what happened)

**Assessment defaults**

| Parameter | Value |
|-----------|-------|
| `weeks_since_plan` | `2` |
| `plan_followed` | From case |
| `attendance_trend` | From case |
| `marks_trend` | From case |
| `failures_trend` | From case |

**Decision outcomes**

| Decision | Recommended Status | Description |
|----------|-------------------|-------------|
| `"Close ticket"` | `"Closed"` | Plan followed, clear improvement, no new failures |
| `"Monitor"` | `"Monitoring"` | Mixed evidence, keep open without escalation |
| `"Escalate"` | `"Escalated"` | Weak progress, plan not followed, failures increased |

**Response Schema — `FollowUpCaseResponse`**

Full case with assessment fields populated.

**Status Codes**
| Code | Description |
|------|-------------|
| `200` | Assessment completed and stored |
| `400` | Case note is empty |
| `401` | Missing or invalid token |
| `404` | Case not found |
| `503` | Database unavailable |

**Example**

```bash
curl -s -X POST "http://localhost:8000/api/v1/follow-up/cases/GP-1234/assess" \
  -H "Authorization: Bearer <token>" | python -m json.tool
```

---

### 10.5 Direct Assess

Assess a follow-up case directly without saving, using the provided data.

| Attribute | Value |
|-----------|-------|
| **Purpose** | Run an assessment on ad-hoc follow-up data without persisting a case |
| **Method** | `POST` |
| **Path** | `/api/v1/follow-up/assess` |
| **Authentication** | Bearer token required |

**Request Body — `FollowUpAssessmentRequest`**

| Field | Type | Constraints | Default | Description |
|-------|------|-------------|---------|-------------|
| `student` | `StudentProfile` | — | — | Student profile |
| `current_risk_category` | string | — | — | Current risk category |
| `current_risk_score` | float | 0–1 | — | Current risk score |
| `recommendation` | string | min 1 char | — | Original recommendation |
| `advisor_note` | string | min 1 char | — | Advisor follow-up note |
| `weeks_since_plan` | integer | 1–12 | `2` | Weeks since plan started |
| `plan_followed` | string | — | `"Unknown"` | Whether plan was followed |
| `attendance_trend` | string | — | `"No new evidence"` | Attendance trajectory |
| `marks_trend` | string | — | `"No new evidence"` | Marks trajectory |
| `failures_trend` | string | — | `"Unknown"` | Failure trajectory |

**PlanFollowed enum:** `"Fully followed"`, `"Partially followed"`, `"Not followed"`, `"Unknown"`

**ProgressTrend enum:** `"Improved"`, `"No clear change"`, `"Worsened"`, `"No new evidence"`

**FailureTrend enum:** `"Decreased"`, `"No change"`, `"Increased"`, `"Unknown"`

**Response Schema — `FollowUpAssessmentResponse`**

| Field | Type | Description |
|-------|------|-------------|
| `decision` | string | `"Close ticket"`, `"Monitor"`, or `"Escalate"` |
| `recommended_status` | string | `"Closed"`, `"Monitoring"`, or `"Escalated"` |
| `escalation_target` | string | Target person/role for escalation |
| `rationale` | string | Reasoning for the decision |
| `next_steps` | string | Recommended next actions |
| `confidence` | float (0–1) | Confidence in the decision |
| `generated_by` | string | `"llm"` or `"deterministic"` |

**Status Codes**
| Code | Description |
|------|-------------|
| `200` | Assessment completed |
| `401` | Missing or invalid token |

**Example**

```bash
curl -s -X POST http://localhost:8000/api/v1/follow-up/assess \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "student": {
      "school": "GP",
      "age": 18,
      "attendance": 78,
      "failures": 2,
      "absences": 12,
      "study_time": 2,
      "previous_grade_average": 8.5
    },
    "current_risk_category": "High Risk",
    "current_risk_score": 0.789,
    "recommendation": "Set weekly attendance target and schedule tutoring.",
    "advisor_note": "Attendance improved slightly but marks remain low.",
    "plan_followed": "Partially followed",
    "attendance_trend": "Improved",
    "marks_trend": "No clear change",
    "failures_trend": "No change"
  }' | python -m json.tool
```

```json
{
  "decision": "Monitor",
  "recommended_status": "Monitoring",
  "escalation_target": "Academic advisor",
  "rationale": "The follow-up has mixed or incomplete evidence, so the case should stay open without immediate escalation.",
  "next_steps": "Continue the plan for one more checkpoint and require concrete evidence: attendance movement, completed work, and the next test or teacher note.",
  "confidence": 0.68,
  "generated_by": "deterministic"
}
```

---

## 11. Insights (Factor Analysis)

### 11.1 Factor Insights

Analyze dataset factors correlated with student success or failure using LLM or deterministic fallback. Includes a guardrail that restricts prompts to dataset-scoped terms.

| Attribute | Value |
|-----------|-------|
| **Purpose** | Analyze and explain factors from the student dataset |
| **Method** | `POST` |
| **Path** | `/api/v1/insights/factors` |
| **Authentication** | Bearer token required |

**Request Body — `FactorInsightRequest`**

| Field | Type | Constraints | Default | Description |
|-------|------|-------------|---------|-------------|
| `prompt` | string | min 3 chars | `"What factors influence student success or failure the most?"` | Natural language query |
| `path` | string \| null | — | `null` (uses default) | Path to CSV dataset |

**Guardrail terms**

The prompt must contain at least one allowed term from the following categories: student/success/failure/risk/grade/mark/score/performance, attendance/absence/absences, study/school/education/support, dataset/data/UCI, family/famil/parent/mother/father/guardian/famrel/famsize/famsup/mjob/fjob/medu/fedu/pstatus, feature/factor, top/best, pass/fail.

If the prompt doesn't match, the response returns a guardrail message with `generated_by: "guardrail"`.

**Response Schema — `FactorInsightResponse`**

| Field | Type | Description |
|-------|------|-------------|
| `prompt` | string | Echoed prompt |
| `source_path` | string | Path to the analyzed CSV file |
| `row_count` | integer | Number of rows analyzed |
| `summary` | string | One-line summary of top signals |
| `answer` | string | LLM or deterministic answer |
| `generated_by` | string | `"llm"`, `"deterministic"`, or `"guardrail"` |
| `factors` | `[FactorInsight]` | Per-feature analysis sorted by strength |

**FactorInsight Schema**

| Field | Type | Description |
|-------|------|-------------|
| `feature` | string | Human-readable feature name |
| `association` | string | `"success"` or `"failure"` |
| `strength` | float | Effect size (0–1) |
| `passed_average` | float | Average value for passing students (G3 >= 10) |
| `at_risk_average` | float | Average value for at-risk students (G3 < 10) |
| `explanation` | string | Plain-language explanation |

**Status Codes**
| Code | Description |
|------|-------------|
| `200` | Analysis completed |
| `400` | Invalid request (e.g. missing dataset, too few rows) |
| `401` | Missing or invalid token |

**Example**

```bash
curl -s -X POST http://localhost:8000/api/v1/insights/factors \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What factors most influence student success?"
  }' | python -m json.tool
```

```json
{
  "prompt": "What factors most influence student success?",
  "source_path": "../data/processed/student-merged.csv",
  "row_count": 1044,
  "summary": "Top signals in the merged dataset are second period grade, first period grade, number of failures. The analysis scans canonical fields, subject-specific grade/behavior columns, and family or social context fields preserved from the raw files.",
  "answer": "The top factors influencing student success are prior grades (G1 and G2) and the number of past failures. Students with higher prior grades and fewer failures are significantly more likely to pass. Attendance, study time, and absences also show measurable associations.",
  "generated_by": "deterministic",
  "factors": [
    {
      "feature": "second period grade",
      "association": "success",
      "strength": 0.733,
      "passed_average": 13.26,
      "at_risk_average": 8.97,
      "explanation": "Second period grade averaged 13.3 for passing students and 9.0 for at-risk students, so higher second period grade is associated with success in this dataset."
    }
  ]
}
```

---

## 12. Parent Notification

### 12.1 Send Parent Email

Send (or simulate) a parent notification email for medium-risk or high-risk students.

| Attribute | Value |
|-----------|-------|
| **Purpose** | Notify parents of at-risk students |
| **Method** | `POST` |
| **Path** | `/api/v1/parent-email/send` |
| **Authentication** | Bearer token required |

**Eligibility**

Only students with `risk_category` of `"Medium Risk"` or `"High Risk"` are eligible. Low-risk students receive `eligible: false` and the email is not sent.

**Request Body — `ParentEmailRequest`**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `student` | `StudentProfile` | — | Student profile |
| `prediction` | `PredictionResponse` | — | Full prediction result |
| `recommendation` | string | min 3 chars | Recommendation text |
| `parent_email` | string | 3–254 chars, must contain `@` not at start/end | Parent email address |
| `subject` | string | 3–160 chars | Email subject |
| `body` | string | 10–5000 chars | Email body |

**Response Schema — `ParentEmailResponse`**

| Field | Type | Description |
|-------|------|-------------|
| `eligible` | boolean | Whether the student qualifies for parent notification |
| `sent` | boolean | Whether the email was sent |
| `delivery_status` | string | `"sent"`, `"simulated"`, or `"skipped"` |
| `recipient` | string | Target email address |
| `subject` | string | Email subject |
| `message` | string | Status message |

**Delivery modes**

| Condition | Delivery Status |
|-----------|----------------|
| Low risk | `"skipped"` — not eligible |
| Medium/high risk, SMTP not configured | `"simulated"` — prepared but not sent |
| Medium/high risk, SMTP configured | `"sent"` — delivered via SMTP |

**SMTP Configuration**

| Variable | Default |
|----------|---------|
| `SSA_SMTP_HOST` | `""` (empty = simulated mode) |
| `SSA_SMTP_PORT` | `587` |
| `SSA_SMTP_USERNAME` | `""` |
| `SSA_SMTP_PASSWORD` | `""` |
| `SSA_SMTP_FROM_EMAIL` | `"advisor@example.edu"` |
| `SSA_SMTP_USE_TLS` | `true` |

**Status Codes**
| Code | Description |
|------|-------------|
| `200` | Request processed |
| `401` | Missing or invalid token |

**Validation Rules**

- `parent_email` must contain `@` not at start or end
- `subject` 3–160 chars
- `body` 10–5000 chars

**Example**

```bash
curl -s -X POST http://localhost:8000/api/v1/parent-email/send \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "student": {
      "school": "GP",
      "age": 18,
      "attendance": 78,
      "failures": 2,
      "absences": 12,
      "study_time": 2,
      "previous_grade_average": 8.5
    },
    "prediction": {
      "student_id": null,
      "risk_score": 0.789,
      "risk_category": "High Risk",
      "model_name": "advisor_score",
      "top_contributors": []
    },
    "recommendation": "Immediate advisor meeting and weekly attendance check.",
    "parent_email": "parent@example.com",
    "subject": "Academic support update for your child",
    "body": "Your child has been identified as needing additional academic support. Our advisor will be reaching out to develop a plan."
  }' | python -m json.tool
```

```json
{
  "eligible": true,
  "sent": true,
  "delivery_status": "simulated",
  "recipient": "parent@example.com",
  "subject": "Academic support update for your child",
  "message": "Email prepared. Configure SMTP settings to send real parent emails."
}
```

---

## 13. Admin

All admin endpoints require authentication.

### 13.1 Initialize Storage

Create PostgreSQL tables (`students`, `student_cases`, `feedback`, `evaluation_results`, `follow_up_cases`, `follow_up_events`).

| Attribute | Value |
|-----------|-------|
| **Purpose** | Initialize database schema |
| **Method** | `POST` |
| **Path** | `/api/v1/admin/storage/init` |
| **Authentication** | Bearer token required |

**Response Schema — `InitializeStorageResponse`**

| Field | Type | Description |
|-------|------|-------------|
| `initialized` | boolean | Always `true` on success |
| `message` | string | `"PostgreSQL tables are ready."` |

**Status Codes**
| Code | Description |
|------|-------------|
| `200` | Tables created successfully |
| `401` | Missing or invalid token |
| `503` | Database unavailable |

**Example**

```bash
curl -s -X POST http://localhost:8000/api/v1/admin/storage/init \
  -H "Authorization: Bearer <token>" | python -m json.tool
```

```json
{
  "initialized": true,
  "message": "PostgreSQL tables are ready."
}
```

---

### 13.2 Ingest Dataset

Import a CSV dataset into the PostgreSQL `students` and `student_cases` tables.

| Attribute | Value |
|-----------|-------|
| **Purpose** | Ingest a single CSV dataset |
| **Method** | `POST` |
| **Path** | `/api/v1/admin/ingest` |
| **Authentication** | Bearer token required |

**Request Body — `IngestDatasetRequest`**

| Field | Type | Constraints | Default | Description |
|-------|------|-------------|---------|-------------|
| `path` | string | min 1 char | — | Path to CSV file |
| `persist` | boolean | — | `true` | Whether to write to database |

**CSV Format Requirements**

Expected columns: `school`, `age`, `studytime` (or `study_time`), `failures`, `absences`, `G1`, `G2`, `G3`, and optionally `student_id`. Delimiter auto-detected (`,` or `;`).

**Processing per row:**
- `previous_grade_average` = `(G1 + G2) / 2`
- `attendance` = derived from absences (`max(100 - absences, 0)`)
- `outcome` = `"Passed"` if G3 >= 10, else `"At Risk"`
- `case_text` = built narrative string

**Response Schema — `IngestionResult`**

| Field | Type | Description |
|-------|------|-------------|
| `source_path` | string | Source file path |
| `imported` | integer | Number of rows successfully imported |
| `skipped` | integer | Number of rows skipped due to errors |
| `persisted` | boolean | Whether data was persisted to DB |

**Status Codes**
| Code | Description |
|------|-------------|
| `200` | Ingestion completed |
| `400` | File not found or invalid data |
| `401` | Missing or invalid token |
| `503` | Database unavailable |

**Example**

```bash
curl -s -X POST http://localhost:8000/api/v1/admin/ingest \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "path": "data/processed/student-merged.csv",
    "persist": true
  }' | python -m json.tool
```

```json
{
  "source_path": "data/processed/student-merged.csv",
  "imported": 1044,
  "skipped": 0,
  "persisted": true
}
```

---

### 13.3 Batch Ingest Datasets

Import 1–10 CSV datasets in a single request. Each path is processed independently; a failure in one does not stop the others.

| Attribute | Value |
|-----------|-------|
| **Purpose** | Ingest multiple CSV datasets at once |
| **Method** | `POST` |
| **Path** | `/api/v1/admin/ingest/batch` |
| **Authentication** | Bearer token required |

**Request Body — `IngestDatasetsRequest`**

| Field | Type | Constraints | Default | Description |
|-------|------|-------------|---------|-------------|
| `paths` | `[string]` | 1–10 items | — | Array of CSV file paths |
| `persist` | boolean | — | `true` | Whether to write to database |

**Response Schema — `[IngestionResult]`**

Array of `IngestionResult` objects, one per path.

**Status Codes**
| Code | Description |
|------|-------------|
| `200` | All ingestion attempts completed (some may have errors) |
| `400` | File not found or invalid data in any file |
| `401` | Missing or invalid token |
| `503` | Database unavailable |

**Example**

```bash
curl -s -X POST http://localhost:8000/api/v1/admin/ingest/batch \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "paths": [
      "data/raw/student-mat.csv",
      "data/raw/student-por.csv"
    ],
    "persist": true
  }' | python -m json.tool
```

```json
[
  {
    "source_path": "data/raw/student-mat.csv",
    "imported": 395,
    "skipped": 0,
    "persisted": true
  },
  {
    "source_path": "data/raw/student-por.csv",
    "imported": 649,
    "skipped": 0,
    "persisted": true
  }
]
```

---

### 13.4 Build Embeddings

Generate vector embeddings for all stored cases using the configured embedding model (default: `BAAI/bge-small-en-v1.5`) and upload them to Qdrant.

| Attribute | Value |
|-----------|-------|
| **Purpose** | Build and upload vector embeddings to Qdrant |
| **Method** | `POST` |
| **Path** | `/api/v1/admin/embeddings/build` |
| **Authentication** | Bearer token required |

**Request Body — `BuildEmbeddingsRequest`**

| Field | Type | Constraints | Default | Description |
|-------|------|-------------|---------|-------------|
| `limit` | integer | 1–10000 | `1000` | Maximum number of cases to embed |

**Response Schema — `EmbeddingPipelineResult`**

| Field | Type | Description |
|-------|------|-------------|
| `embedded` | integer | Number of cases embedded |
| `uploaded` | integer | Number of vectors uploaded to Qdrant |
| `collection` | string | Qdrant collection name (default: `"student_cases"`) |
| `warnings` | `[string]` | Any warnings during the process |

**Status Codes**
| Code | Description |
|------|-------------|
| `200` | Embeddings built and uploaded |
| `401` | Missing or invalid token |
| `503` | Qdrant or database unavailable |

**Example**

```bash
curl -s -X POST http://localhost:8000/api/v1/admin/embeddings/build \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"limit": 500}' | python -m json.tool
```

```json
{
  "embedded": 500,
  "uploaded": 500,
  "collection": "student_cases",
  "warnings": []
}
```

---

### 13.5 Train Models

Train ML models (Logistic Regression, Random Forest, XGBoost) on a CSV dataset and persist the best-performing artifact (by F1 score).

| Attribute | Value |
|-----------|-------|
| **Purpose** | Train prediction models from CSV data |
| **Method** | `POST` |
| **Path** | `/api/v1/admin/models/train` |
| **Authentication** | Bearer token required |

**Request Body — `TrainModelsRequest`**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `path` | string | min 1 char | Path to training CSV |

**Training details**

- **Test split:** 25% stratified
- **Random state:** 42
- **Models:**
  - `logistic_regression`: `LogisticRegression(max_iter=1000, class_weight="balanced")`
  - `random_forest`: `RandomForestClassifier(n_estimators=120, max_depth=4, class_weight="balanced")`
  - `xgboost`: `XGBClassifier(n_estimators=120, max_depth=3, learning_rate=0.08)` (requires `xgboost` package)
- **Feature vectorization:** All numeric fields via `DictVectorizer`
- **Best model:** Selected by highest F1 score
- **Artifact saved to:** `{model_dir}/{best_model_name}.pkl` (directory configured by `SSA_MODEL_DIR`, default `artifacts/models`)

**Response Schema — `TrainingResult`**

| Field | Type | Description |
|-------|------|-------------|
| `source_path` | string | Source training file |
| `best_model` | string | Name of the best-performing model |
| `artifact_path` | string | Path to the saved model pickle |
| `metrics` | `[ModelMetric]` | Performance metrics for all trained models |

**ModelMetric Schema**

| Field | Type | Description |
|-------|------|-------------|
| `model_name` | string | Model name |
| `accuracy` | float | Accuracy score |
| `precision` | float | Precision score |
| `recall` | float | Recall score |
| `f1` | float | F1 score |
| `roc_auc` | float \| null | ROC AUC score (null for models without predict_proba) |

**Requirements**

Training requires `scikit-learn`. For XGBoost, the `xgboost` package must also be installed. Install with:
```bash
uv sync --extra ml
```

**Status Codes**
| Code | Description |
|------|-------------|
| `200` | Training completed |
| `400` | Invalid data, file not found, or < 20 rows with mixed outcomes |
| `401` | Missing or invalid token |

**Validation Rules**

- At least 20 rows required
- Both pass and at-risk outcomes must be present
- `G3` column must exist for label extraction (G3 >= 10 → passed)

**Example**

```bash
curl -s -X POST http://localhost:8000/api/v1/admin/models/train \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"path": "data/processed/student-merged.csv"}' | python -m json.tool
```

```json
{
  "source_path": "data/processed/student-merged.csv",
  "best_model": "logistic_regression",
  "artifact_path": "artifacts/models/logistic_regression.pkl",
  "metrics": [
    {
      "model_name": "logistic_regression",
      "accuracy": 0.8115,
      "precision": 0.8132,
      "recall": 0.8143,
      "f1": 0.8137,
      "roc_auc": 0.8401
    },
    {
      "model_name": "random_forest",
      "accuracy": 0.7854,
      "precision": 0.7872,
      "recall": 0.7901,
      "f1": 0.7886,
      "roc_auc": 0.8203
    }
  ]
}
```

---

## Appendix A: Common HTTP Status Codes

| Code | Description | Usage |
|------|-------------|-------|
| `200` | Success | All endpoints except `/feedback` |
| `201` | Created | `POST /feedback` |
| `400` | Bad Request | Invalid input, missing dataset, validation error |
| `401` | Unauthorized | Missing or invalid bearer token, wrong credentials |
| `404` | Not Found | Case or resource does not exist |
| `503` | Service Unavailable | Database, Qdrant, or other dependency unavailable |

## Appendix B: Environment Variables Reference

| Variable | Endpoint(s) Affected |
|----------|----------------------|
| `SSA_DATABASE_URL` | All admin, follow-up, search, feedback, evaluation |
| `SSA_QDRANT_URL` | `/search`, `/admin/embeddings/build` |
| `SSA_QDRANT_API_KEY` | `/search`, `/admin/embeddings/build` |
| `SSA_OPENAI_API_KEY` | `/recommend`, `/evaluate`, `/insights/factors`, `/follow-up/assess` |
| `SSA_JUDGE_MODEL` | `/evaluate`, `/follow-up/assess` |
| `SSA_LLM_MODEL` | `/recommend`, `/insights/factors` |
| `SSA_PREDICTION_MODEL` | `/predict` |
| `SSA_MODEL_DIR` | `/admin/models/train` |
| `SSA_AUTH_USERNAME` | `/auth/login` |
| `SSA_AUTH_PASSWORD` | `/auth/login` |
| `SSA_AUTH_TOKEN_SECRET` | All authenticated endpoints |
| `SSA_SMTP_HOST` | `/parent-email/send` |
| `SSA_DEFAULT_DATASET_PATH` | `/insights/factors` |
| `SSA_EMBEDDING_MODEL` | `/admin/embeddings/build` |
| `SSA_RERANKER_MODEL` | `/search` |
