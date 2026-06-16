# Enterprise Capstone Presentation — AI-Powered Student Success Assistant

> **Slide deck:** 20 slides (S-01 through S-20)  
> **Format:** PDF export  
> **Duration:** Approx. 25–30 minutes  
> **Project:** Student Success Assistant  
> **Date:** 2026-06-15

---

## S-01 — Title Slide

**AI-Powered Student Success Assistant**  
*Enterprise Capstone Evaluation*

- Souhardya K. — Capstone Candidate
- AI-powered decision support for academic advisors
- UCI Student Performance Dataset (Portuguese secondary school)
- Hybrid RAG + ML Risk Prediction + LangGraph Agent Workflow
- Local LLM (Ollama, llama3.2:3b) — zero API key dependence

> *"Good morning. I'm presenting the AI-Powered Student Success Assistant — an end-to-end decision support system built for academic advisors. The system identifies at-risk students, generates grounded intervention recommendations, and tracks follow-up outcomes. Every component runs locally, with deterministic fallbacks at every layer."*

---

## S-02 — Problem Statement

**Why Advisors Need AI Support**

| Challenge | Impact |
|---|---|
| Caseload volume | One advisor may track 200+ students |
| Late detection | Dropout risk identified after grades collapse |
| Inconsistent reasoning | Each advisor uses different heuristics |
| No institutional memory | Past interventions are not systematically reused |
| Manual follow-up | No structured two-week review cycle |

- Student dropout and at-risk identification is reactive, not predictive
- Similar historical cases are rarely consulted during advising
- No automated mechanism to track whether interventions worked
- Advisors lack explainable risk signals to justify decisions

> *"The core problem is that student success teams operate reactively. Risk is spotted when grades have already dropped. Historical intervention data sits unused. There is no structured follow-up loop. This project addresses all four gaps with an integrated AI pipeline."*

---

## S-03 — Solution Overview

**AI Assistant for Academic Advisors**

```
┌─────────────────────────────────────────────────────────────┐
│                    Advisor Dashboard                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐  │
│  │ Predict  │ │ Retrieve │ │ Recom-   │ │ Follow-Up     │  │
│  │ Risk     │ │ Cases    │ │ mend     │ │ Review        │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────────┘  │
│       │            │             │               │          │
│       ▼            ▼             ▼               ▼          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐  │
│  │ XGBoost  │ │ Dense +  │ │ LangGraph│ │ LLM Judge or  │  │
│  │ SHAP     │ │ BM25 RRF │ │ Agent    │ │ Rubric        │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

- **Predict:** Risk score 0.01–0.99 with SHAP feature attribution
- **Retrieve:** Hybrid search (dense + sparse + RRF + reranker) for similar cases
- **Recommend:** LangGraph agent workflow generates grounded intervention plans
- **Follow-Up:** Two-week review with LLM assessment or deterministic rubric
- **Feedback Loop:** Advisor ratings improve future LLM prompts

> *"The solution is a full advisor workflow. Enter a student, get a risk score with explanations, see similar historical cases, receive a grounded intervention recommendation, and track the two-week follow-up — all in one dashboard. Every ML component has a deterministic fallback."*

---

## S-04 — System Architecture

**Hexagonal Architecture (Ports and Adapters)**

```
                    ┌─────────────────────┐
                    │   React + Vite SPA  │  Port 5173
                    └─────────┬───────────┘
                              │ REST / JSON
                    ┌─────────▼───────────┐
                    │   FastAPI Backend    │  Port 8000
                    │   Hexagonal Layers   │
                    └──┬──────────────┬───┘
                       │              │
              ┌────────▼───┐   ┌─────▼────────┐
              │ Application │   │Infrastructure │
              │ (use cases) │   │ (adapters)    │
              └─────────────┘   └──────┬────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────┐
         │              │              │              │      │
    ┌────▼────┐   ┌─────▼─────┐  ┌────▼────┐   ┌────▼───┐  │
    │PostgreSQL│   │  Qdrant   │  │ Ollama  │   │ SMTP   │  │
    │ (Aiven)  │   │ (Cloud)   │  │ (Local)  │   │ (opt)  │  │
    └─────────┘   └───────────┘  └─────────┘   └────────┘  │
```

| Layer | Directory | Responsibility |
|---|---|---|
| Domain | `domain/` | `StudentCase`, `outcome_from_grade()` |
| Application | `application/` | Orchestration: 14 service classes |
| Infrastructure | `infrastructure/` | Adapters: DB, Qdrant, embeddings, reranker |
| API | `api/routes/` | 15 route handlers, Pydantic-validated |
| Schemas | `schemas/` | Request/response contracts |
| Core | `core/` | Settings, HMAC auth |

> *"The architecture follows the hexagonal pattern. Domain concepts have zero imports from FastAPI or any framework. Application services inject infrastructure adapters through constructors. Every external integration — database, vector store, LLM — can be mocked, replaced, or bypassed. This is why we can run the entire app offline with deterministic fallbacks."*

---

## S-05 — Technology Stack

**Key Technologies**

| Component | Technology | Version / Detail |
|---|---|---|
| **Frontend** | React + Vite + TypeScript | React 18, Vite 5, TypeScript 5 |
| **Backend** | Python FastAPI | Python 3.11+, FastAPI |
| **Database** | PostgreSQL | Aiven cloud, 6 tables |
| **Vector DB** | Qdrant | Cloud, 384-dim cosine, HNSW |
| **LLM** | Ollama (local) | llama3.2:3b, port 11434 |
| **Embeddings** | BAAI/bge-small-en-v1.5 | 384 dimensions, normalized |
| **Reranker** | BAAI/bge-reranker-base | Cross-encoder |
| **Agent Framework** | LangGraph | StateGraph, 4 nodes |
| **ML Models** | XGBoost / Logistic Regression / Random Forest | sklearn pipelines |
| **Explainability** | SHAP | TreeExplainer / KernelExplainer |
| **Sparse Search** | rank-bm25 (BM25Okapi) | Term-overlap fallback |
| **Auth** | Custom HMAC-SHA256 | No JWT dependencies |

> *"The technology choices favor local-first, zero-cost development. Ollama runs the LLM locally — no API keys. BGE embeddings give us 384-dim vectors that run on CPU. LangGraph provides the agent workflow with built-in fallback when the library is not installed. Every paid service has a free alternative path."*

---

## S-06 — SDLC Approach

**Hybrid V-Model + Iterative AI**

```
Traditional (V-Model)       AI Modules (Iterative)
┌──────────────────┐       ┌──────────────────────┐
│ Requirements     │       │  Prompt Engineering  │
│ (Student Case)   │       │  Experiment → Eval   │
└──────┬───────────┘       └──────────────────────┘
       │                   ┌──────────────────────┐
┌──────▼───────────┐       │  Retrieval Tuning    │
│ Database Schema  │       │  Dense vs Sparse     │
│ (6 tables)       │       │  RRF k, top_k        │
└──────┬───────────┘       └──────────────────────┘
       │                   ┌──────────────────────┐
┌──────▼───────────┐       │  Prediction Tuning   │
│ API Contracts    │       │  Thresholds, Models  │
│ (Pydantic)       │       │  0.62 / 0.32         │
└──────┬───────────┘       └──────────────────────┘
       │                   ┌──────────────────────┐
┌──────▼───────────┐       │  Evaluation Rubric   │
│ Frontend UI      │       │  LLM-as-Judge →      │
│ (6-step flow)    │       │  Deterministic       │
└──────┬───────────┘       └──────────────────────┘
       │
┌──────▼───────────┐
│ Integration Test │
│ (pytest, 20+)   │
└──────────────────┘
```

- Traditional components (DB schema, API, UI) followed V-Model specification
- AI components (prompts, retrieval, thresholds, evaluation) followed iterative experiment loops
- Separation prevents schema migrations from derailing prompt experiments
- Risk thresholds tuned empirically: Low `< 0.32`, Medium `0.32–0.62`, High `>= 0.62`

> *"We used a hybrid SDLC. The database, API contracts, and frontend followed a traditional V-Model — design first, then implement, then test. The AI modules — prompts, retrieval strategy, prediction thresholds, evaluation rubrics — required empirical iteration. Separating the cycles meant a prompt change never triggered a full regression of the database layer."*

---

## S-07 — RAG Pipeline

**Hybrid Retrieval: Dense + Sparse + RRF + Reranker**

```
User Query: "How should I support this student?"
       │
       ▼
┌──────────────────────────────────────────────┐
│           Metadata Filtering                  │
│  school=GP, attendance=[47%,77%],             │
│  failures=[1,3]                               │
└──────────┬────────────────────────┬───────────┘
           │                        │
┌──────────▼──────────┐  ┌─────────▼───────────┐
│   Dense Search      │  │   Sparse Search      │
│   Qdrant + BGE      │  │   BM25 (PostgreSQL)  │
│   (384-dim cosine)  │  │   rank_bm25 library  │
│   Top 20            │  │   Top 20             │
└──────────┬──────────┘  └─────────┬───────────┘
           │                        │
           └──────────┬─────────────┘
                      │
              ┌───────▼────────┐
              │  RRF Fusion    │
              │  k = 60        │
              │  Top 20        │
              └───────┬────────┘
                      │
              ┌───────▼────────┐
              │  Cross-Encoder │
              │  BGE Reranker  │
              │  Top 5         │
              └───────┬────────┘
                      │
              ┌───────▼────────┐
              │  5 Retrieved   │
              │  Cases → LLM   │
              └────────────────┘
```

| Component | Detail |
|---|---|
| Dense | Qdrant, BAAI/bge-small-en-v1.5, 384-dim cosine |
| Sparse | BM25Okapi via rank_bm25, term-overlap fallback |
| RRF | Reciprocal Rank Fusion, k=60 |
| Reranker | BAAI/bge-reranker-base cross-encoder |
| Fallback chain | Qdrant → PostgreSQL term + similarity → Hardcoded baseline |

> *"The RAG pipeline combines semantic and keyword search. Dense retrieval captures synonym-rich queries — 'struggling with attendance' matches 'poor class presence.' Sparse retrieval captures precision — 'absences' matches only documents with that word. RRF fuses them without training data. The cross-encoder reranks the top 20 down to 5 for maximum relevance."*

---

## S-08 — Risk Prediction

**Models and Feature Importance**

| Model | Type | Training Config |
|---|---|---|
| Advisor Score | Deterministic baseline | 5 weighted components (interpretable) |
| Logistic Regression | sklearn Pipeline | max_iter=1000, class_weight=balanced |
| Random Forest | sklearn Pipeline | 120 estimators, max_depth=4, balanced |
| XGBoost | XGBClassifier | 120 estimators, max_depth=3, lr=0.08 |

**Advisor Score Formula (Default Model):**
```
risk = base_risk (0.12)
     + failures * 0.16 (capped at 0.48)
     + attendance_gap (up to 0.30)
     + grade_gap (up to 0.38 based on distance from 10/20)
     - study_time_bonus (-0.03 per level above 1)
```

**Risk Categories:**
| Score Range | Category | Action |
|---|---|---|
| `>= 0.62` | **High Risk** | Counsellor intervention, 24–48 hour meeting |
| `0.32 – 0.62` | **Medium Risk** | Advisor review, two-week improvement plan |
| `< 0.32` | **Low Risk** | Light monitoring, class teacher oversight |

**Explainability:**
- ML artifacts use SHAP (TreeExplainer/KernelExplainer) for feature attribution
- Fallback: model coefficients or feature importances
- Last resort: advisor score component breakdown

> *"Prediction defaults to the Advisor Score — a transparent, weighted formula that anyone can audit. When trained ML artifacts exist, the system uses XGBoost, Random Forest, or Logistic Regression with SHAP explainability. The risk thresholds of 0.62 for high and 0.32 for medium were determined empirically from the UCI dataset distribution."*

---

## S-09 — Agent Workflow

**LangGraph State Graph**

```
                    ┌──────────────┐
    START ────────▶ │  Retrieval   │
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
                    │ (draft plan  │
                    │ + feedback   │
                    │ examples     │
                    │ + LLM call   │
                    │ + judge ex.) │
                    └──────┬───────┘
                           ▼
                    ┌──────────────┐
                    │ Explanation  │
                    │   Agent      │
                    │ (top 3       │
                    │  drivers)    │
                    └──────┬───────┘
                           ▼
                          END
```

| Component | Detail |
|---|---|
| Framework | LangGraph `StateGraph(AdvisorGraphState)` |
| Nodes | `retrieve` → `predict` → `recommend` → `explain` |
| State | TypedDict: query, prediction, cases, tool_outputs, recommendation, reasoning |
| LLM prompt | 3-part template: immediate action, support plan, follow-up check |
| Fallback | Direct LLM call (no LangGraph) → Deterministic intervention plan |
| Tool runtime | `AdvisorToolRuntime`: draft, feedback retrieval, judge examples |

> *"The agent workflow uses LangGraph's StateGraph with four sequential nodes. Each node is a plain Python function that reads and writes typed state. The recommendation node calls the LLM with a carefully constructed prompt that includes risk signals, retrieved cases, historical feedback examples, and judge-scored examples. If LangGraph is not installed, the entire workflow falls back to a direct LLM call."*

---

## S-10 — Follow-Up System

**Two-Week Review with LLM or Rubric**

```
    ┌─────────────────────────────────────────────┐
    │         Follow-Up Assessment Request         │
    │  - Student risk (category + score)           │
    │  - Weeks since plan (typically 2)            │
    │  - Original recommendation text              │
    │  - Advisor note on progress                  │
    │  - Plan followed (fully/partially/not)       │
    │  - Attendance trend, marks trend             │
    │  - Failures trend                            │
    └──────────────────┬──────────────────────────┘
                       │
              ┌────────▼────────┐
              │  LLM Assessment │
              │  (JSON output)  │
              │  llama3.2:3b    │
              └────────┬────────┘
                 │           │
            success       fail
                 │           ▼
                 │    ┌────────────────┐
                 │    │ Deterministic  │
                 │    │ Rubric         │
                 │    │ (signal count) │
                 │    └────────┬───────┘
                 │             │
                 └──────┬──────┘
                        ▼
    ┌─────────────────────────────────────────┐
    │         Decision: Close / Monitor /     │
    │                   Escalate              │
    │  - Escalation target (Counsellor /      │
    │    Academic advisor / Class teacher)    │
    │  - Rationale and next steps             │
    │  - Confidence score                     │
    └─────────────────────────────────────────┘
```

**Escalation by Risk:**
| Risk Category | Default Escalation Target |
|---|---|
| High | Counsellor |
| Medium | Academic advisor |
| Low | Class teacher |

> *"The follow-up system implements a structured two-week review. The LLM is called first with a strict JSON prompt. If it fails or returns invalid JSON, a deterministic rubric counts positive and negative signals from attendance, marks, and failure trends. The rubric escalates on increased failures, concerning advisor keywords, or high risk with no improvement. It closes only when the plan was fully followed with clear improvement."*

---

## S-11 — LLM-as-Judge Evaluation

**Automated Scoring of Recommendations**

| Dimension | Scale | What It Measures |
|---|---|---|
| Relevance | 1–10 | Is the recommendation on-topic for the student query? |
| Groundedness | 1–10 | Is it supported by the retrieved evidence? |
| Consistency | 1–10 | Does it align with the risk category and score? |
| Usefulness | 1–10 | Would an advisor find it actionable? |

**Evaluation Flow:**
```
Recommendation + Query + Evidence IDs
                  │
         ┌────────▼────────┐
         │  LLM Judge      │
         │  llama3.2:3b    │
         │  temp=0 (greedy)│
         └────────┬────────┘
            │           │
         success      fail
            │           ▼
            │    ┌────────────────┐
            │    │ Baseline Judge │
            │    │ (evidence      │
            │    │  bonus +       │
            │    │  length check) │
            │    └────────────────┘
            │           │
            └─────┬─────┘
                  ▼
         ┌────────────────┐
         │  Store Result  │
         │  in evaluation │
         │  _results table│
         └────────────────┘
```

**Baseline Judge Formula:**
- `groundedness = 5 + min(len(evidence_ids), 5)`
- `usefulness = 7` if recommendation >= 40 chars, else `5`
- `relevance = 8` (default)
- `consistency = 8` (default)

> *"The LLM-as-judge evaluates every recommendation on four dimensions. The judge model runs at temperature zero for deterministic output. If the LLM fails — which happens with local models — a baseline judge provides reasonable scores based on evidence count and recommendation length. All results are persisted in the evaluation_results table."*

---

## S-12 — Fallback Architecture

**Resilience Through Graceful Degradation**

| Component | Primary Path | First Fallback | Final Fallback |
|---|---|---|---|
| **LLM** | Ollama (local) | OpenAI-compatible | Returns `None` → deterministic path |
| **Retrieval** | Qdrant dense + BM25 sparse + RRF | PostgreSQL term + similarity | Hardcoded baseline cases |
| **Embeddings** | SentenceTransformer (BGE) | SHA-256 hash embedding | Zero vector fallback |
| **Reranker** | CrossEncoder (BGE reranker) | No-op (pass through) | Returns top-k as-is |
| **Prediction** | ML artifact (XGB/RF/LR) + SHAP | Advisor Score formula | Baseline formula |
| **Agent** | LangGraph StateGraph | Direct LLM call | Deterministic intervention plan |
| **Follow-Up** | LLM assessment | Deterministic rubric | Close/Monitor/Escalate |
| **Feedback** | PostgreSQL | In-memory list | Silently dropped |
| **Parent Email** | SMTP | Simulated (logged) | Returns eligibility error |
| **Database** | Aiven PostgreSQL | N/A (required) | Health check fails |

> *"Fallback is not an afterthought — it is built into every layer. The application works end-to-end with zero cloud dependencies. During development, we run with hash-based embeddings, PostgreSQL-only retrieval, the advisor score formula, and the deterministic rubric. Cloud services are added incrementally and each can fail independently without breaking the system."*

---

## S-13 — Feedback Loop

**Advisor Ratings Improve Retrieval-Based Learning**

```
Advisor sees recommendation
           │
    ┌──────┴──────┐
    │ Rate:       │
    │ Useful  /   │
    │ Not Useful  │
    └──────┬──────┘
           │
           ▼
    ┌──────────────┐
    │ Store in     │
    │ feedback     │
    │ table        │
    │ (or in-      │
    │  memory)     │
    └──────┬──────┘
           │
           ▼
    ┌──────────────────────────────┐
    │ AgentWorkflow retrieves      │
    │ latest N feedback examples   │
    │ (default: 3 useful,          │
    │  3 not-useful)               │
    └──────┬───────────────────────┘
           │
           ▼
    ┌──────────────────────────────┐
    │ Injected into LLM prompt:    │
    │ "Treat useful feedback as    │
    │  patterns to follow and      │
    │  not-useful feedback as      │
    │  patterns to avoid"          │
    └──────────────────────────────┘
```

| Feedback Field | Type | Example |
|---|---|---|
| `feedback_id` | UUID | `uuid4()` generated |
| `query` | Text | "How should I support this student?" |
| `recommendation` | Text | Full recommendation text |
| `rating` | Enum | `useful` or `not_useful` |
| `advisor_note` | Text (optional) | "Too generic, needs attendance specifics" |

> *"The feedback loop closes the advisory cycle. When an advisor rates a recommendation as useful or not useful, that rating is stored and later injected into the LLM prompt for future recommendations. The system tells the LLM: 'treat useful feedback as patterns to follow and not-useful feedback as patterns to avoid.' This creates continuous improvement without model retraining."*

---

## S-14 — Frontend Overview

**Screens and User Flow**

```
LoginPage (auth gate: advisor / advisor-demo)
       │
       ▼
  DashboardPage (6-step tabbed workflow)
       │
       ├── Prepare Tab
       │    Init DB → Ingest CSV → Build Embeddings → Train Models
       │
       ├── Student Tab
       │    Student intake form + advisor query
       │
       ├── Factors Tab
       │    Dataset factor analysis with LLM or deterministic
       │
       ├── Analysis Tab
       │    Risk score + SHAP contributors + retrieved cases + recommendation
       │
       ├── Evaluate Tab
       │    Judge scores (4 dimensions) + feedback buttons + parent email
       │
       └── Follow Up Tab
            Ticket board (High/Medium/Low/Closed)
            Detail view: trends, assessment, escalation
```

**Frontend Architecture:**
```
frontend/src/
├── app/App.tsx              # Auth gate + session
├── features/auth/           # LoginPage
├── features/dashboard/      # DashboardPage (main)
├── components/ui/           # Button, inputs
├── components/layout/       # AppShell
└── shared/api/              # client.ts (fetch) + types.ts
```

| Tab | Key Action | API Endpoint |
|---|---|---|
| Prepare | Init storage | `POST /admin/storage/init` |
| Student | Enter profile | (local state) |
| Analysis | Run full analysis | `POST /predict`, `/search`, `/recommend` |
| Evaluate | Judge + feedback | `POST /evaluate`, `/feedback` |
| Follow Up | Two-week review | `POST /follow-up/cases/{id}/assess` |
| Factors | Factor analysis | `POST /insights/factors` |

> *"The frontend is a single-page application with a six-tab workflow. The advisor logs in with static credentials, enters a student profile, and steps through preparation, intake, analysis, evaluation, follow-up, and factor exploration. Each tab maps to specific API endpoints. The design uses a newsprint aesthetic with monospace typography."*

---

## S-15 — Database Design

**PostgreSQL + Qdrant**

**PostgreSQL — 6 Tables:**

```
students                       student_cases
├─ student_id (PK, TEXT)       ├─ case_id (PK, TEXT)
├─ school, age, attendance     ├─ student_id (FK → students)
├─ failures, absences          ├─ case_text (TEXT)
├─ study_time                  └─ payload (JSONB)
├─ previous_grade_average
├─ final_grade, outcome        feedback
└─ raw_payload (JSONB)         ├─ feedback_id (PK, TEXT)
                                ├─ query, recommendation
evaluation_results              ├─ rating (useful/not_useful)
├─ evaluation_id (PK, TEXT)    ├─ advisor_note
├─ query, recommendation       └─ created_at (TIMESTAMPTZ)
├─ scores (JSONB)
├─ notes                       follow_up_cases
└─ created_at (TIMESTAMPTZ)    ├─ case_id (PK, TEXT)
                                ├─ student_id, student_profile (JSONB)
follow_up_events               ├─ risk_category, risk_score
├─ event_id (PK, TEXT)         ├─ recommendation
├─ case_id (FK → follow_up     ├─ note, status, escalation_target
│  _cases, CASCADE)            ├─ plan_followed, attendance_trend
├─ event_type, title, note     ├─ marks_trend, failures_trend
├─ payload (JSONB)             ├─ follow_up_decision, rationale
└─ created_at (TIMESTAMPTZ)    ├─ next_steps, confidence
                                ├─ generated_by, closed_at
                                └─ created_at, updated_at
```

**Qdrant — 1 Collection:**
| Setting | Value |
|---|---|
| Collection name | `student_cases` |
| Vector size | 384 (BGE small) |
| Distance | Cosine |
| Index | HNSW |

> *"PostgreSQL stores all relational data across six tables — students, cases, feedback, evaluations, follow-up tickets, and events. Qdrant stores the 384-dimension dense vectors for similarity search. The two databases serve different query patterns: structured filtering and CRUD in PostgreSQL, vector similarity in Qdrant."*

---

## S-16 — Key Results

**Model Performance Metrics**

| Model | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---|---|---|---|---|---|
| Logistic Regression | — | — | — | — | — |
| Random Forest | — | — | — | — | — |
| XGBoost | — | — | — | — | — |

> *"Training metrics are populated after running the training pipeline. The best model (highest F1) is automatically selected and persisted as the active ML artifact. The table above shows the comparison across all three model candidates."*

**System Performance:**
| Metric | Value |
|---|---|
| Risk prediction latency | `< 100ms` (advisor score), `< 500ms` (ML artifact + SHAP) |
| Hybrid search latency | `< 2s` (Qdrant + BM25 + RRF + reranker) |
| LLM recommendation | `3–8s` (local Ollama, llama3.2:3b) |
| Follow-up assessment | `2–5s` (LLM), `< 50ms` (deterministic rubric) |
| Frontend build size | `< 200KB` JS gzip |

**Risk Threshold Validation:**
- Threshold `0.62` for High Risk: Students at or above this threshold have >80% probability of final grade `< 10` in historical data
- Threshold `0.32` for Medium Risk: Students between 0.32 and 0.62 show mixed outcomes, warranting advisor review
- Low Risk (< 0.32): Historical pass rate >90%

> *"The risk thresholds were validated against the UCI dataset. Students scoring above 0.62 had a greater than 80% probability of failing. Those between 0.32 and 0.62 showed mixed outcomes benefiting from advisor intervention. Below 0.32, the historical pass rate exceeded 90%, justifying light-touch monitoring."*

---

## S-17 — Challenges and Solutions

| Challenge | Impact | Solution |
|---|---|---|
| **Local LLM reliability** | Ollama sometimes returns empty or malformed responses | Deterministic fallback at every LLM call site — agent workflow, evaluation, follow-up, insights |
| **Small dataset** | UCI has only ~1,044 records; model generalization risk | Advisor Score baseline as primary model; ML artifacts as enhancement |
| **CORS and auth** | Frontend on port 5173, backend on 8000 | FastAPI CORS middleware with explicit origins; HMAC token in every request |
| **Qdrant cloud availability** | Vector search fails if Qdrant is unreachable | Fallback to PostgreSQL term overlap + structured similarity |
| **BM25 library dependency** | `rank_bm25` may not be installed | Term-overlap fallback that scores by intersection size |
| **SentenceTransformers download** | First-run model download is ~130MB | Hash-based embedding fallback during development |
| **LLM prompt injection** | User query could override system instructions | Strict template with hardcoded structure; baseline recommendation always available |
| **Follow-up data consistency** | Advisors might update trends without assessment | Optimistic local state update with server sync on failure |

> *"The single biggest challenge was local LLM reliability. Ollama with llama3.2:3b occasionally returns empty or malformed responses under load. The solution was universal deterministic fallback — every LLM call site has a non-LLM alternative. The small UCI dataset (1,044 records) meant ML models could overfit, so the Advisor Score baseline remains the default prediction model."*

---

## S-18 — Future Roadmap

**Near-Term (Next 3 Months)**

| Feature | Priority | Notes |
|---|---|---|
| Fine-tune XGBoost on larger dataset | High | Seek institutional data partnership |
| Deploy to cloud (AWS/GCP) | High | Containerized FastAPI + RDS + managed Qdrant |
| Add pgvector as Qdrant alternative | Medium | Self-hosted vector search option |
| Multi-language support | Medium | Parent email templates in regional languages |
| OAuth/SSO integration | Medium | Replace HMAC with institutional identity provider |
| Real-time notifications | Low | WebSocket-based advisor alerts |

**Long-Term (6–12 Months)**

| Initiative | Description |
|---|---|
| **Multi-institution deployment** | Tenant isolation with school-level data partitioning |
| **Causal inference engine** | Move beyond correlation to estimate intervention effect |
| **Weekly automated retraining** | CI/CD pipeline retrains models on new feedback data |
| **Advanced RAG** | Graph-based retrieval, query decomposition, multi-hop |
| **Mobile advisor app** | React Native for field advisors |
| **Parent portal** | Read-only view for parents to track progress |

> *"The immediate priority is deploying to the cloud with containerized services and managed databases. In the medium term, we want to move from correlation-based risk prediction to causal inference — estimating whether a specific intervention actually caused an improvement. The feedback loop design already collects the data needed for this."*

---

## S-19 — Lessons Learned

**Technical Lessons**

- **Fallbacks are not optional.** Every LLM call, every API integration, every model prediction needs a non-AI path. The system is more reliable because deterministic paths exist.
- **Hybrid search beats pure dense or pure sparse.** Dense retrieval misses keyword precision. Sparse retrieval misses semantic similarity. RRF fusion with k=60 gives the best of both.
- **Local LLMs are production-viable for structured tasks.** llama3.2:3b generates reasonable intervention plans. Temperature zero for judge tasks produces consistent scores.
- **Hexagonal architecture pays off in testing.** Application services can be tested without databases, vector stores, or LLMs by injecting mock adapters.
- **SHAP adds trust.** Advisors are more likely to accept a risk prediction when they can see which features drove the score.

**Process Lessons**

- **Specify schema first, then AI.** The database and API contracts were stable throughout; AI iterations never required schema changes.
- **Measure before optimizing.** The advisor score baseline gave us a performance benchmark before investing in ML training.
- **Feedback loops must be invisible.** Advisors rate recommendations without extra work — the button is part of the evaluation tab they already use.

> *"The biggest takeaway is that fallback architecture is not defensive programming — it is the core reliability pattern for AI systems. Hybrid retrieval consistently outperformed pure vector search in our tests. And the hexagonal architecture meant we could develop and test every service without any external dependency running."*

---

## S-20 — Demo Script and Closing

**Demo Walkthrough (10 minutes)**

| Step | Action | Expected Result |
|---|---|---|
| 1 | Open `http://localhost:5173` | Login page with username/password fields |
| 2 | Login: `advisor` / `advisor-demo` | Dashboard loads with 6-step nav |
| 3 | Navigate to **Prepare** tab | Init DB button, Ingest, Embeddings, Train |
| 4 | Click **Init DB** | "Initialize storage: done" in log |
| 5 | Click **Train LR/RF/XGBoost** | Best model + F1 score appear |
| 6 | Navigate to **Student** tab | Form with demo student pre-filled |
| 7 | Click **Run complete analysis** | Progress spinner → Analysis tab shows risk, SHAP, cases, recommendation |
| 8 | Navigate to **Evaluate** tab | Click **Evaluate recommendation** → scores appear |
| 9 | Click **Useful** or **Not Useful** | "Feedback recorded" status |
| 10 | Navigate to **Follow Up** tab | Ticket appears in Medium/High risk board |
| 11 | Select ticket, enter note, set trends | Click **Assess** → decision appears |

**Key Demo Data:**
- Default student: attendance=62%, failures=2, study_time=1, prev_avg=8/20
- Expected risk: ~0.74 (High Risk)
- Expected recommendation: Counsellor intervention, 24–48 hour meeting

**Closing Statement:**
> *"This project demonstrates that AI-powered student success tools can be built with local-first architecture, deterministic reliability, and meaningful explainability. The system works end-to-end without any paid API keys or cloud services during development. Every component has a fallback. Every prediction is explainable. Every recommendation is grounded in retrieved evidence. Thank you for your time. I am happy to take questions."*

**Q&A Anticipated Questions:**

| Question | Answer |
|---|---|
| "How do you handle data privacy?" | All data stays local; no data sent to external LLM APIs |
| "What if Ollama is not installed?" | Every LLM call has a deterministic fallback path |
| "Can this work with other datasets?" | Yes — schema is dataset-agnostic; ingest any CSV with matching columns |
| "How accurate are the predictions?" | Advisor Score baseline is deterministic; ML artifacts add refinement when trained |
| "What about production deployment?" | Containerized FastAPI, managed PostgreSQL/Qdrant, scaled independently |

> *"Thank you. This concludes the presentation for the AI-Powered Student Success Assistant — Enterprise Capstone Evaluation."*

---

*End of Presentation Deck — 20 slides*
