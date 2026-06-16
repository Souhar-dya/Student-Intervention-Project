# Design — AI-Powered Student Success Assistant

> **Document version:** 1.0  
> **Project:** Student Success Assistant  
> **Last updated:** 2026-06-15

---

## Table of Contents

1. [Architecture Decision Records (ADRs)](#1-architecture-decision-records-adrs)
2. [SOLID Principles](#2-solid-principles)
3. [Design Patterns](#3-design-patterns)
4. [Data Flows](#4-data-flows)
5. [Error Handling Strategy](#5-error-handling-strategy)

---

## 1. Architecture Decision Records (ADRs)

### ADR-001: PostgreSQL as Primary Relational Database

**Status:** Accepted

**Context:** The system needs a relational database to store student records, case narratives, advisor feedback, evaluation results, and follow-up tickets. The data has strong relational structure: students have cases, feedback references recommendations, follow-up tickets reference students and accumulate event histories.

**Decision:** Use PostgreSQL managed on Aiven cloud. Six tables: `students`, `student_cases`, `feedback`, `evaluation_results`, `follow_up_cases`, `follow_up_events`. All DDL is maintained inline in `database.py` as raw SQL — no ORM. Schema is version-controlled alongside application code.

**Alternatives Rejected:**

| Alternative | Why Rejected |
|---|---|
| **MongoDB** | The data is deeply relational (student → cases → feedback → evaluations → tickets → events). A document store would embed deeply or require application-side joins, losing referential integrity. The fixed schema also simplifies migration tracking. |
| **Neo4j** | A graph database is overkill for this domain. The relationship depth rarely exceeds two hops. The query patterns are primarily range filters and text search, not graph traversal. Operational overhead with no benefit. |
| **SQLite** | Cannot support concurrent writes from multiple advisor sessions. No managed cloud offering. Not suitable for production multi-user access. |

**Consequences:**
- Schema migrations require explicit SQL scripts rather than ORM auto-migration.
- Each repository method writes raw SQL with psycopg v3. This is explicit but verbose.
- Connection management is manual via `db_connection()` context manager.
- Positive: no ORM overhead, no hidden N+1 queries, full control over query plans.

**Trade-offs:**
- Losing an ORM means more boilerplate for CRUD operations.
- Gaining full control over query performance and zero magic.
- psycopg v3 provides async support when needed in the future.

---

### ADR-002: Qdrant as Vector Database

**Status:** Accepted

**Context:** The RAG pipeline requires vector similarity search over student case embeddings. The system must support payload filtering (school, attendance range, failures range) combined with ANN search, independent scaling of vector infrastructure, and a managed cloud offering to reduce operational burden.

**Decision:** Use Qdrant cloud as the dedicated vector database. Collection `student_cases` with 384-dim vectors, COSINE distance, HNSW indexing. Payload filtering via `models.FieldCondition` with match and range operators.

**Alternatives Rejected:**

| Alternative | Why Rejected |
|---|---|
| **pgvector (PostgreSQL extension)** | Shares compute resources with OLTP workloads, making independent scaling impossible. The managed Aiven PostgreSQL plan would need a larger instance to accommodate vector indexing. No dedicated cloud dashboard for vector operations. Hybrid search requires additional extension layers. |
| **Pinecone** | Proprietary, higher per-vector cost, no native payload filtering in the free tier. Vendor lock-in concerns for an academic project. |
| **Weaviate** | Full-fledged vector database with built-in hybrid search, but operational complexity is higher than Qdrant cloud. Requires more configuration for simple use cases. |
| **ChromaDB** | Immature for production. No managed cloud offering at time of decision. Limited filtering capabilities. |

**Consequences:**
- Two database systems to manage instead of one. Each has independent connection strings, credentials, and scaling policies.
- Qdrant client (`qdrant-client`) is imported only in `qdrant_store.py`, isolating the dependency.
- The `QdrantCaseStore.is_configured()` method checks for URL and API key, allowing graceful fallback when Qdrant is unavailable.

**Trade-offs:**
- Operational complexity of two data stores.
- Better independent scaling: vector search loads don't affect relational query performance.
- Qdrant's native payload filtering is cleaner than JSONB + ANN in pgvector.

---

### ADR-003: BAAI/bge-small-en-v1.5 for Embeddings

**Status:** Accepted

**Context:** The system requires a text embedding model for dense retrieval of student case narratives. The requirements are: (1) balanced quality vs. speed for CPU inference, (2) normalized embeddings for simplified distance calculations, (3) small enough to run in development without GPU.

**Decision:** Use `BAAI/bge-small-en-v1.5` with 384-dimensional output vectors. Model is loaded via `sentence-transformers` when `SSA_ENABLE_REMOTE_MODELS=true`. Output is L2-normalized by default, making cosine similarity equivalent to dot product.

**Alternatives Rejected:**

| Alternative | Why Rejected |
|---|---|
| **BAAI/bge-base-en-v1.5 (768 dim)** | 2x storage and compute cost. While marginally more accurate on MTEB benchmarks, the small variant provides sufficient retrieval quality for the student case domain (short to medium-length narratives, ~100-500 tokens). |
| **BAAI/bge-large-en-v1.5 (1024 dim)** | 2.7x the dimension of small, requires GPU for acceptable latency in batch. Development teams without GPU hardware would be blocked. |
| **text-embedding-3-small (OpenAI)** | API dependency, per-token cost, latency over network. The system needs to work fully offline. Exposing an API key for embedding generation creates security surface area. |
| **all-MiniLM-L6-v2** | 384-dim competitor, but BGE small consistently outperforms MiniLM on retrieval benchmarks while being comparable in size. |

**Consequences:**
- Each case narrative produces a 384-element float vector (1,536 bytes at float32).
- Embedding generation runs on CPU with acceptable latency (~50-100ms per text).
- When `enable_remote_models` is false, the `EmbeddingProvider` falls back to a hash-based sparse embedding: SHA-256 token hashing into the 384-dim space with sign-based L2 normalization. This produces deterministic but low-quality embeddings for development.

**Trade-offs:**
- 384-dim may miss nuanced semantic relationships that a 768-dim model would capture.
- Storage and query latency are half of the 768-dim alternative.
- The fallback hash embedding is purely for development; production deployments must enable remote models.

---

### ADR-004: Hybrid Search (Dense + Sparse)

**Status:** Accepted

**Context:** The retrieval system must handle diverse advisor queries. Some queries are semantically reformulated ("learner with poor attendance and failing subjects"), while others are keyword-precise ("absences > 10 AND failures > 2"). Neither dense nor sparse retrieval alone covers both cases adequately.

**Decision:** Implement hybrid search combining dense retrieval (BGE embeddings in Qdrant, cosine distance) with sparse retrieval (BM25Okapi via `rank_bm25` library, term-overlap fallback when `rank_bm25` is not installed). Both run with the same payload filters (school, attendance range, failures range).

**Alternatives Rejected:**

| Alternative | Why Rejected |
|---|---|
| **Dense-only (Qdrant only)** | Misses keyword-precise matches. For example, searching for "GPA < 10" will not surface cases with exact grade values if the semantic embedding spaces the query differently. Precision on narrow queries suffers. |
| **Sparse-only (BM25 only)** | Misses semantically equivalent but lexically different queries. "Student struggling with attendance" would not match "learner with poor class presence" without keyword overlap. Recall on reformulated queries suffers. |
| **Learned sparse (SPLADE)** | Requires training or fine-tuning. Adds operational complexity for marginal improvement over BM25 in this domain. Not available as a lightweight offline model. |
| **Hybrid with learned fusion** | Training a fusion model requires relevance judgments (labeled data). The system has no training data for search ranking. |

**Consequences:**
- Two retrieval pipelines run per query: one Qdrant ANN search + one BM25 scoring pass over PostgreSQL results.
- The sparse pass loads up to 500 rows from PostgreSQL and tokenizes them for BM25 scoring. At scale, this becomes a bottleneck.
- Hybrid search improves recall at the cost of doubling retrieval latency.

**Trade-offs:**
- Higher latency (~2x a single dense search) in exchange for higher recall (precision + recall gains from both strategies).
- Works without training data, unlike learned fusion approaches.
- The sparse fallback (term overlap when `rank_bm25` is missing) preserves correctness but degrades ranking quality.

---

### ADR-005: Reciprocal Rank Fusion (RRF)

**Status:** Accepted

**Context:** After running dense and sparse retrieval, the system needs to combine two ranked lists into a single fused ranking. The fusion method must work without training data, handle uncalibrated scores (cosine similarity and BM25 scores are not directly comparable), and be simple to implement and tune.

**Decision:** Use Reciprocal Rank Fusion with `k=60`. Each candidate from both rankings receives a fused score `1 / (k + rank)`. Scores are summed across dense and sparse, then candidates are sorted descending.

**Alternatives Rejected:**

| Alternative | Why Rejected |
|---|---|
| **Score averaging** | Cosine similarity scores (0.0-1.0) and BM25 scores (unbounded, typically 0-50+) are on different scales. Averaging them directly gives disproportionate weight to BM25. |
| **Score max fusion** | Takes the maximum score from either ranking. Tends to favor the system that gives higher scores to most documents, which is often BM25. |
| **CombSUM / CombMNZ** | Requires score normalization (min-max or z-score) which is sensitive to outliers and distribution shifts. |
| **Learning-to-rank (LambdaRank, ListNet)** | Requires labeled training data with relevance judgments for each query-document pair. This data does not exist for this system and would be expensive to produce. |

**Consequences:**
- Fusion is a deterministic O(n log n) operation with a single configurable parameter `k`.
- The constant `k=60` is a common default from research literature. It smooths the rank contributions so that top-ranked items from one system don't dominate.
- RRF does not require score normalization, score calibration, or training data.

**Trade-offs:**
- RRF treats all ranking sources equally. If one source is consistently better, RRF cannot weight it higher without introducing a learned weight.
- However, empirical research shows RRF is surprisingly robust and often matches or exceeds trained fusion methods in heterogeneous retrieval settings.
- The simplicity (no training, one parameter) justifies any marginal quality loss vs. a trained approach.

---

### ADR-006: BAAI/bge-reranker-base Cross-Encoder

**Status:** Accepted

**Context:** After first-stage retrieval (hybrid dense+sparse), the system needs to refine the top-k candidates for relevance. The bi-encoder (BGE small) produces embeddings independently for query and document, losing the interaction between them. A cross-encoder performs full attention between query and document, producing more accurate relevance scores.

**Decision:** Apply `BAAI/bge-reranker-base` cross-encoder to the top 20 candidates from RRF fusion. The reranker scores each (query, case_text) pair via `CrossEncoder.predict()`, and the top 5 results are returned.

**Alternatives Rejected:**

| Alternative | Why Rejected |
|---|---|
| **No reranker** | Top 20 from RRF would be returned as-is. The bi-encoder's independent encoding misses query-document interaction, so irrelevant candidates can rank high due to embedding artifacts. |
| **BAAI/bge-reranker-large** | Higher accuracy but significantly slower. The base model provides sufficient accuracy improvement for the rerank-at-20 use case. |
| **Cohere rerank** | External API dependency, per-call cost, cannot run offline. |
| **Cross-encoder on full corpus** | O(n) where n is sequence length, applied to thousands of documents would be prohibitively slow. Rerank-at-20 limits the cost. |

**Consequences:**
- Reranking adds ~20 cross-encoder inference calls per query. On CPU, this takes 100-500ms depending on text length.
- Only the top 20 candidates from RRF are reranked, limiting the cross-encoder cost to constant time regardless of corpus size.
- The `Reranker` class in `reranker.py` wraps `CrossEncoder` and degrades gracefully (returns candidates unchanged) when remote models are disabled.

**Trade-offs:**
- 100-500ms additional latency per query in exchange for significantly improved precision at top-5.
- Without the reranker, top-5 results may contain irrelevant cases that happened to have high bi-encoder similarity.
- The reranker is applied to all queries uniformly; for time-sensitive queries this adds latency with no bypass mechanism.

---

### ADR-007: LangGraph for Multi-Agent Workflow

**Status:** Accepted

**Context:** The recommendation generation workflow has four clearly defined stages: retrieve similar cases, predict risk, draft recommendation, and explain drivers. Each stage produces artifacts consumed by subsequent stages. The system needs a structured way to model this pipeline with typed state passing and fallback when the graph library is unavailable.

**Decision:** Use LangGraph's `StateGraph` to model the advisor workflow as a four-node sequential graph (`retrieve → predict → recommend → explain`). State is a `TypedDict` (`AdvisorGraphState`) with typed fields. Each node is a plain Python function that reads and mutates state. When `langgraph` is not installed, the system falls back to a direct LLM call with equivalent context assembled inline.

**Alternatives Rejected:**

| Alternative | Why Rejected |
|---|---|
| **LangChain LCEL (RunnableSequence)** | Linear chain without easy state accumulation across steps. Tool outputs would need external storage rather than being part of typed graph state. |
| **Simple function pipeline (no framework)** | Would work for the happy path, but loses the structured state passing, tool accumulation pattern, and the ability to evolve into conditional branching or parallel nodes in the future. |
| **Custom state machine** | Duplicating LangGraph's work. LangGraph provides typed state, node registration, edge configuration, compilation, and invocation — all features that would need to be rebuilt. |
| **Direct LLM call only** | Loses the structured multi-step reasoning. The four agents (retrieve, predict, recommend, explain) provide intermediate artifacts that improve the final recommendation quality and enable the explanation agent to reference specific tool outputs. |

**Consequences:**
- `AgentWorkflow` in `agent_workflow.py` defines four node functions that operate on `AdvisorGraphState`.
- `AdvisorToolRuntime` in `agent_tools.py` provides the tool primitives (summarize cases, summarize prediction, draft intervention, retrieve feedback examples, retrieve judge examples) that are called by the node functions.
- The `generate_recommendation()` method tries `_generate_with_langgraph()` first, and if it returns `None` (LangGraph not installed or empty recommendation), falls back to `_generate_with_direct_llm()`.
- Each tool output is appended to `tool_outputs` in state, accumulating context for the final LLM call.

**Trade-offs:**
- LangGraph adds a dependency. If it lags behind Python version upgrades or has breaking changes, the fallback path ensures continuity.
- The graph is purely sequential with no branching, cycles, or conditional edges. The full power of LangGraph (conditional routing, parallel execution, persistent state) is not leveraged. However, this keeps the workflow simple and testable.
- The fallback path produces a slightly different prompt (no LangGraph-specific tool outputs), but the final LLM call has equivalent information.

---

### ADR-008: XGBoost for ML Prediction

**Status:** Accepted

**Context:** The prediction service needs to classify student risk (binary: pass/at-risk) from structured features (school, age, study time, failures, absences, grades). Multiple algorithms were evaluated to determine which provides the best F1 score on the student dataset.

**Decision:** Use `sklearn.pipeline.Pipeline` with `DictVectorizer` + classifier. Three candidate models are trained via `TrainingService.train()`: Logistic Regression (`LogisticRegression` with `class_weight="balanced"`, max_iter=1000), Random Forest (`RandomForestClassifier` with n_estimators=120, max_depth=4, class_weight="balanced"), and XGBoost (`XGBClassifier` with n_estimators=120, max_depth=3, learning_rate=0.08, subsample=0.9, colsample_bytree=0.9). The best model by F1 score is persisted via pickle to `artifacts/models/`. The prediction service loads the artifact and uses `predict_proba()` to derive risk scores.

**Alternatives Rejected:**

| Alternative | Why Rejected |
|---|---|
| **Neural network (MLP / PyTorch)** | Requires more data (the dataset is ~650 rows), GPU for efficient training, and more hyperparameter tuning. The structured tabular data is better suited to tree-based methods. |
| **Support Vector Machine (SVM)** | Does not provide calibrated probabilities by default. Platt scaling adds complexity. F1 performance on this dataset was consistently lower than XGBoost in internal benchmarks. |
| **Gradient Boosting Machine (LightGBM)** | Similar performance to XGBoost but with fewer tuning knobs exposed in the training service. XGBoost was chosen for familiarity and broader ecosystem support. |
| **Logistic Regression only** | Linear decision boundary is insufficient for the interaction effects in student data (e.g., high failures + low attendance has compounded effect). |

**Consequences:**
- Training produces pickled `Pipeline` objects containing `DictVectorizer` and the best classifier.
- The prediction service loads the artifact and vectorizes input features identically to training.
- `TrainingService.train()` handles the full ML pipeline: CSV reading, train/test split, stratified by label, three-model comparison, F1 selection, and artifact persistence.
- XGBoost consistently achieves the highest F1 score due to its ability to model non-linear interactions and handle imbalanced classes.

**Trade-offs:**
- XGBoost models are less interpretable than Logistic Regression's linear coefficients.
- SHAP explanations mitigate this by providing per-feature contribution analysis.
- Pickle persistence means model artifacts are tied to Python/scikit-learn versions. Version pinning is required.
- Training requires the ML extras (`uv sync --extra ml`).

---

### ADR-009: SHAP for Model Explainability

**Status:** Accepted

**Context:** ML model predictions need to be explainable to academic advisors. Advisors need to understand why a student received a particular risk score — which features contributed most and by how much. The explanation must work for all three model types (Logistic Regression, Random Forest, XGBoost).

**Decision:** Use SHAP (SHapley Additive exPlanations) for both local (per-prediction) and global (feature importance) explanations. The `PredictionService._shap_contributors()` method attempts three strategies: (1) `shap.Explainer` with additive feature attribution, (2) `shap.TreeExplainer` for tree-based models (Random Forest, XGBoost), (3) falls back to model coefficients or feature importances.

**Alternatives Rejected:**

| Alternative | Why Rejected |
|---|---|
| **LIME** | Local explanations only, no global view. Less stable than SHAP — different runs on the same prediction can produce different explanations. |
| **Partial dependence plots** | Global only, no per-prediction explanations. Advisors need to understand individual student risk scores. |
| **Feature importances (sklearn native)** | Available for tree models and regression coefficients, but not standardized across model types. No support for non-linear interaction effects. |
| **No explanation** | Advisors would not trust or act on predictions without understanding the reasoning. Explainability is a hard requirement for educational intervention systems. |

**Consequences:**
- SHAP add `shap` as a dependency (with `matplotlib`, `scipy`, `numba` as transitive deps).
- SHAP computation adds 50-200ms per prediction depending on model complexity.
- The explanation service (`ExplanationService`) produces human-readable text from the top-3 contributors: "failures moved risk by +0.32; attendance_gap moved risk by +0.15; study_time moved risk by -0.03".
- When SHAP is unavailable (ImportError), falls back to `coef_` for linear models and `feature_importances_` for tree models.

**Trade-offs:**
- SHAP values are computationally expensive but theoretically grounded (Shapley values from coalitional game theory).
- The fallback paths produce coarser explanations (linear coefficients assume independent features; feature importances show only magnitude, not direction).
- SHAP's `TreeExplainer` is optimized for tree-based models and is significantly faster than the generic `Explainer`.

---

### ADR-010: FastAPI as Web Framework

**Status:** Accepted

**Context:** The backend requires a Python web framework that supports async request handling, automatic request/response validation, and OpenAPI documentation generation. The framework must be lightweight, well-maintained, and support dependency injection for service wiring.

**Decision:** Use FastAPI with Pydantic v2 schemas for all request/response validation. Routes are grouped by domain in `api/routes/`. Dependencies are injected via `Depends()` factory functions. OpenAPI docs are auto-generated at `/docs`.

**Alternatives Rejected:**

| Alternative | Why Rejected |
|---|---|
| **Flask** | No native async support (requires Quart or gevent). No built-in request validation — requires marshmallow or manual validation. No auto-generated OpenAPI docs. More boilerplate for equivalent functionality. |
| **Django + DRF** | Heavy framework for a focused API service. ORM-centric architecture conflicts with the hexagonal architecture goal. Opinionated project structure is harder to adapt to the ports-and-adapters pattern. |
| **Starlette (raw)** | FastAPI is built on Starlette and adds Pydantic validation, OpenAPI generation, and dependency injection on top. Using raw Starlette would require rebuilding these features. |
| **Litestar** | Newer framework with less community adoption. Fewer resources for troubleshooting. Team familiarity with FastAPI was a deciding factor. |

**Consequences:**
- Route handlers are thin: validate via Pydantic, delegate to service, return schema.
- `Depends(get_prediction_service)` provides constructor-injected services.
- Auto-generated OpenAPI docs at `/docs` provide interactive API exploration.
- Pydantic v2 schemas in `schemas/` define the API contract explicitly.

**Trade-offs:**
- FastAPI's dependency injection is function-based, not class-based like Spring or NestJS. This works well for stateless services but requires careful handling of stateful dependencies.
- The async-first design is not fully leveraged — most service methods are synchronous (DB calls use blocking psycopg). True async would require asyncpg and async Qdrant client.
- Pydantic v2 validation overhead is negligible for the request volumes (~1000 req/day).

---

### ADR-011: React + Vite for Frontend

**Status:** Accepted

**Context:** The frontend needs a modern single-page application (SPA) with a component-based architecture, fast development iteration, and TypeScript support. The UI follows the Newsprint design system with a dashboard workflow across six tabs.

**Decision:** Use React 18 with Vite as the build tool and TypeScript for type safety. The project structure follows feature-based organization: `features/auth/`, `features/dashboard/`, `components/ui/` (design system primitives), `components/layout/` (shell and navigation), `shared/api/` (HTTP client and types).

**Alternatives Rejected:**

| Alternative | Why Rejected |
|---|---|
| **Next.js** | Server-side rendering is unnecessary for a dashboard SPA. Adds complexity with routing, SSR, and build configuration. Vite provides faster HMR and simpler configuration for client-only apps. |
| **Vue.js** | Team familiarity with React was stronger. Vue's composition API is comparable to React hooks, but the React ecosystem (testing library, state management patterns) is more mature for this use case. |
| **Svelte** | Smaller ecosystem and fewer UI component libraries. The Newsprint design system would need to be built from scratch with fewer reference implementations. |
| **Angular** | Heavy framework with opinionated module system. Overkill for a focused dashboard application with limited pages. RxJS adds unnecessary complexity for simple fetch-based API calls. |

**Consequences:**
- `shared/api/client.ts` wraps `fetch()` with automatic auth token injection and error handling. No axios dependency.
- `shared/api/types.ts` contains TypeScript interfaces that mirror the Pydantic schemas.
- `features/dashboard/DashboardPage.tsx` orchestrates the six-tab workflow.
- The Newsprint design system is implemented through `styles/newsprint.css` and `components/ui/` primitives.
- `vite-env.d.ts` provides Vite type declarations.

**Trade-offs:**
- Without SSR, initial page load includes the full JS bundle (~200KB gzipped). For an internal dashboard, this is acceptable.
- Feature-based organization scales well but can lead to duplicate code across features if shared utilities are not extracted early.
- The fetch-based client is simpler than axios but requires manual JSON parsing and error handling.

---

## 2. SOLID Principles

### Single Responsibility Principle (SRP)

Each class in the system has exactly one responsibility, identified by its file and class name.

| Class | Responsibility |
|---|---|
| `PredictionService` | Risk prediction: baseline or ML artifact, feature contributions |
| `RetrievalService` | Hybrid search: dense, sparse, RRF fusion, reranker orchestration |
| `RecommendationService` | Orchestrate predict → search → draft → agent for recommendations |
| `EvaluationService` | LLM-as-judge evaluation with rubric fallback |
| `FeedbackService` | Store advisor feedback, in-memory fallback |
| `FollowUpService` | Two-week review assessment with LLM or rubric |
| `ExplanationService` | Human-readable risk explanation from contributors |
| `IngestionService` | CSV ingestion into PostgreSQL |
| `TrainingService` | Model training: read, split, train three models, persist best |
| `InsightsService` | Factor analysis from merged dataset via LLM |
| `ParentNotificationService` | SMTP email sending |
| `EmbeddingPipeline` | Orchestrate DB → embedding → Qdrant upload |
| `QdrantCaseStore` | Qdrant collection management and vector search |
| `StudentRepository` | PostgreSQL CRUD for students, cases, feedback, evaluations |
| `FollowUpRepository` | PostgreSQL CRUD for follow-up tickets and events |
| `EmbeddingProvider` | Text → vector embedding with hash fallback |
| `Reranker` | Cross-encoder reranking |
| `AgentWorkflow` | LangGraph state graph for multi-agent recommendation |
| `AdvisorToolRuntime` | Tool primitives for the agent workflow |
| `Settings` | Configuration from environment variables |

**Evidence:** Each file in `application/` contains exactly one service class. Each file in `infrastructure/` contains exactly one adapter. Route files in `api/routes/` are similarly focused.

### Open/Closed Principle (OCP)

Classes are open for extension but closed for modification through strategy interfaces and factory selection.

**Prediction Model Strategy:** `PredictionService.predict()` selects between models by name:
```python
if model_name == ADVISOR_SCORE_MODEL:
    return self._predict_with_baseline(...)
model_response = self._predict_with_artifact(...)
if model_response is not None:
    return model_response
return self._predict_with_baseline(...)
```
Adding a new prediction model requires only a new entry in the model registry — `PredictionService` itself is never modified.

**LLM Provider Strategy:** `get_chat_llm()` in `llm_client.py` selects between Ollama and OpenAI providers without the calling code knowing which:
```python
if provider == "openai":
    return ChatOpenAI(...)
if provider == "ollama":
    return ChatOllama(...)
```
Adding a new provider (e.g., Anthropic, Groq) means adding a new `if` branch without changing any service that calls `get_chat_llm()`.

**Training Model Strategy:** `TrainingService.train()` iterates over a dictionary of candidate models:
```python
candidates = {
    LOGISTIC_REGRESSION_MODEL: LogisticRegression(...),
    RANDOM_FOREST_MODEL: RandomForestClassifier(...),
}
xgboost = self._xgboost_candidate()
if xgboost is not None:
    candidates[XGBOOST_MODEL] = xgboost
```
Adding a new model means adding it to the candidates dict — the training loop, evaluation, and persistence code remain unchanged.

### Liskov Substitution Principle (LSP)

Subtypes must be substitutable for their base types without altering correctness.

**Schema Inheritance:** Pydantic models use inheritance through protocol-like compatibility. `SearchRequest` and `RecommendationRequest` both embed a `PredictionRequest` student profile. The `RecommendationService.recommend()` method calls `request.search.model_copy(update={...})`, treating the search request as a base schema that can be extended.

**Strategy Interfaces:** Although Python uses duck typing rather than formal interfaces, the prediction models follow the same protocol: each must implement `predict_proba()` returning class probabilities. Logistic Regression, Random Forest, and XGBoost from sklearn all satisfy this protocol and are substitutable in the training pipeline:
```python
probabilities = (
    pipeline.predict_proba(test_x)[:, 1]
    if hasattr(pipeline.named_steps["classifier"], "predict_proba")
    else None
)
```

**Fallback Chain Substitutability:** The retrieval fallback chain demonstrates LSP: `_search_hybrid`, `_search_repository`, and `_baseline_search` all return `SearchResponse` and are substitutable at the call site. The caller (`search()`) does not know which implementation ran.

### Interface Segregation Principle (ISP)

Clients should not depend on interfaces they do not use.

**Focused Schemas:** Pydantic schemas are narrow and specific:
- `PredictionRequest` contains only student features needed for prediction.
- `SearchRequest` contains only query, filters, and top_k.
- `FeedbackRequest` contains only query, recommendation, rating, and advisor_note.
- `FollowUpAssessmentRequest` contains only the fields needed for assessment.
No schema bundles unrelated fields. A client retrieving feedback does not need to import prediction fields.

**Repository Interface Segregation:** `StudentRepository` exposes multiple focused methods rather than a general-purpose CRUD interface:
- `search_cases(filters, limit)` — only for search
- `store_feedback(...)` — only for feedback
- `store_evaluation(...)` — only for evaluations
- `list_feedback_examples(limit)` — only for agent tools
- `list_judged_recommendations(limit)` — only for agent tools
No client is forced to depend on methods it doesn't call.

**Tool Runtime Interface:** `AdvisorToolRuntime` exposes separate methods (`summarize_retrieved_cases`, `summarize_prediction`, `retrieve_feedback_examples`, `retrieve_judge_examples`, `draft_intervention`) rather than a single `execute_tool(name, args)` method. Each node in the LangGraph calls only the tools it needs.

### Dependency Inversion Principle (DIP)

High-level modules should not depend on low-level modules. Both should depend on abstractions.

**Constructor Injection:** Application services accept dependencies via constructor injection:
```python
class RecommendationService:
    def __init__(self, prediction_service, retrieval_service, agent_workflow=None):
        ...
```
`RecommendationService` does not instantiate its dependencies — they are injected. The caller (`get_recommendation_service()`) wires the concrete implementations:
```python
def get_recommendation_service() -> RecommendationService:
    return RecommendationService(
        prediction_service=PredictionService(),
        retrieval_service=RetrievalService(),
    )
```

**Factory Function Decoupling:** FastAPI route handlers depend on factory functions, not concrete classes:
```python
@router.post("/recommend", response_model=RecommendationResponse)
def recommend(
    request: RecommendationRequest,
    service: RecommendationService = Depends(get_recommendation_service),
) -> RecommendationResponse:
```
The route handler knows only that `service` is a `RecommendationService`. The factory `get_recommendation_service()` determines how it is constructed.

**Settings Abstraction:** All components depend on the `Settings` abstraction from `core/config.py` rather than reading environment variables directly:
```python
settings = get_settings()  # cached singleton
```
Tests can override settings by setting environment variables before `get_settings()` is first called.

**Repository Abstraction:** Services depend on `StudentRepository` (a concrete class that wraps psycopg), but the repository itself abstracts PostgreSQL behind its method signatures. The same `StudentRepository` interface could be reimplemented with a different database without changing the services.

---

## 3. Design Patterns

### Repository Pattern

The Repository pattern mediates between the domain and data mapping layers, providing a collection-like interface for accessing domain objects.

**Implementation:**
- `StudentRepository` (`infrastructure/student_repository.py`) wraps PostgreSQL CRUD for students, cases, feedback, and evaluations. Methods: `initialize()`, `upsert_student_case()`, `list_cases()`, `search_cases()`, `store_feedback()`, `store_evaluation()`, `list_feedback_examples()`, `list_judged_recommendations()`.
- `FollowUpRepository` (`infrastructure/follow_up_repository.py`) wraps PostgreSQL CRUD for follow-up tickets and events.

**Why:** Isolates SQL from business logic. Changes to the database schema require changes only in the repository, not in application services.

**Usage locations:**
- `IngestionService`, `FeedbackService`, `EvaluationService`, `AgentWorkflow` → `StudentRepository`
- `FollowUpService` → `FollowUpRepository`

### Factory Pattern

Factory functions encapsulate the creation of complex objects or service instances.

**Implementation:**
- `get_prediction_service()` — creates `PredictionService()` with default constructor
- `get_retrieval_service()` — creates `RetrievalService()` with four injected adapters
- `get_recommendation_service()` — creates `RecommendationService()` with prediction and retrieval services, no agent workflow (creates default)
- `get_evaluation_service()` — creates `EvaluationService()`
- `get_feedback_service()` — creates `FeedbackService()`
- `get_follow_up_service()` — creates `FollowUpService()`
- `get_chat_llm()` — creates `ChatOllama` or `ChatOpenAI` based on settings
- `get_embedding_provider()` — creates `EmbeddingProvider` with settings, cached via `@lru_cache`
- `get_reranker()` — creates `Reranker` with settings, cached via `@lru_cache`
- `get_student_repository()` — creates `StudentRepository()`
- `get_qdrant_case_store()` — creates `QdrantCaseStore()`

**Why:** (1) Centralizes creation logic. (2) Enables DI via `Depends()` in FastAPI routes. (3) Caching of expensive objects (embedding provider, reranker, settings).

**Usage locations:** FastAPI route handlers use `Depends(get_*_service)` for injection. Application services use `get_chat_llm()` for LLM instantiation.

### Strategy Pattern

The Strategy pattern defines a family of algorithms, encapsulates each one, and makes them interchangeable.

**Implementation:**

**Prediction Models:** Three strategies for risk prediction:
1. `_predict_with_baseline()` — deterministic advisor score with weighted components
2. `_predict_with_artifact()` — ML model artifact (Logistic Regression, Random Forest, or XGBoost)
3. Fall back from artifact to baseline

**LLM Providers:** Two strategies for LLM interaction:
1. `ChatOllama` — local model via Ollama
2. `ChatOpenAI` — cloud model via OpenAI-compatible API

**Training Candidates:** Three model strategies in `TrainingService.train()`:
1. `LogisticRegression(max_iter=1000, class_weight="balanced")`
2. `RandomForestClassifier(n_estimators=120, max_depth=4)`
3. `XGBClassifier(n_estimators=120, max_depth=3, learning_rate=0.08)`

**Fallback Strategies:** Multiple services use the try-different-strategies pattern:
- `EvaluationService`: LLM judge → rubric baseline
- `FollowUpService`: LLM assessment → deterministic signal-counting rubric
- `RetrievalService`: hybrid search → repository search → baseline search
- `EmbeddingProvider`: sentence-transformers → hash-based embedding
- `PredictionService`: artifact → baseline advisor score
- `AgentWorkflow`: LangGraph → direct LLM → drafted plan

**Why:** Systems with multiple interchangeable algorithms benefit from isolated strategy implementations. The fallback chains provide graceful degradation without complex error handling.

### Dependency Injection Pattern

Dependencies are provided to objects rather than created internally.

**Implementation:**
- FastAPI's `Depends()` injects service instances into route handlers
- Services accept dependencies via `__init__` parameters (constructor injection)
- Factory functions wire the dependency graph
- `RecommendationService.__init__` takes `prediction_service`, `retrieval_service`, and optional `agent_workflow`
- `RetrievalService.__init__` takes `case_store`, `embedding_provider`, `repository`, and `reranker`

**Why:** (1) Decouples object creation from usage. (2) Enables unit testing with mocks. (3) Centralizes wiring changes.

**Usage locations:** All route handlers in `api/routes/`. All application services with external dependencies.

### Pipeline Pattern

A sequence of processing stages where the output of one stage feeds into the next.

**Implementation:**

**RAG Pipeline:** `RetrievalService._search_hybrid()`:
```
Query → Dense Qdrant search → Sparse BM25 search → RRF Fusion → Reranker → Response
```

**Training Pipeline:** `TrainingService.train()`:
```
CSV → Row parsing → Feature/label extraction → Train/test split → Model fitting → Evaluation → Persistence
```

**Recommendation Pipeline:** `RecommendationService.recommend()`:
```
Student features → Predict risk → Search similar cases → Draft intervention → Agent workflow → Response
```

**LangGraph Agent Pipeline:** `AgentWorkflow._generate_with_langgraph()`:
```
Entry → Retrieve agent → Predict agent → Recommend agent → Explain agent → END
```

**Embedding Pipeline:** `EmbeddingPipeline.run()`:
```
DB read → Case narrative generation → Embedding → Qdrant upsert
```

**Why:** Pipelines decompose complex multi-stage processes into discrete, testable steps. Each stage can be modified, replaced, or skipped independently.

### Facade Pattern

A simplified interface to a complex subsystem.

**Implementation:**
- **`RecommendationService`** is a facade that coordinates `PredictionService`, `RetrievalService`, and `AgentWorkflow`. The route handler calls `service.recommend(request)` and receives a complete recommendation without knowing about prediction, retrieval, or agent orchestration.
- **`RetrievalService`** is a facade that coordinates `QdrantCaseStore`, `EmbeddingProvider`, `StudentRepository`, and `Reranker`. The caller calls `service.search(request)` and gets results without knowing about dense/sparse/fusion/rerank internals.
- **`EmbeddingPipeline`** is a facade that coordinates `StudentRepository`, `EmbeddingProvider`, and `QdrantCaseStore`. The admin endpoint calls `pipeline.run()` and all three systems are orchestrated.

**Why:** Simplifies client code by hiding subsystem complexity. Each facade represents a single use-case boundary.

### Template Method Pattern

Defines the skeleton of an algorithm, deferring some steps to subclasses or fallback functions.

**Implementation:** The fallback chain pattern used throughout the system:
```python
def assess(self, request):
    llm_response = self._assess_with_llm(request)
    if llm_response is not None:
        return llm_response
    return self._assess_with_rubric(request)
```
The skeleton ("try primary strategy; if it fails, try fallback") is fixed, while the specific strategies (`_assess_with_llm`, `_assess_with_rubric`) vary.

This pattern appears in:
- `EvaluationService.evaluate()` — try LLM, fall back to rubric
- `FollowUpService.assess()` — try LLM, fall back to signal-counting rubric
- `AgentWorkflow.generate_recommendation()` — try LangGraph, fall back to direct LLM
- `RetrievalService.search()` — try hybrid, fall back to repository, fall back to baseline
- `PredictionService.predict()` — try artifact, fall back to advisor score

**Why:** Provides a consistent error-handling structure across all services. The "try/fallback" template is simple, predictable, and easy to trace in logs.

---

## 4. Data Flows

### Student Prediction Flow

```
Advisor input via API (POST /api/v1/predict)
         │
         ▼
  PredictionRequest validated by Pydantic
  (student_id, school, age, study_time, failures,
   absences, attendance, previous_grade_average)
         │
         ▼
  PredictionService.predict(request)
         │
         ├── model_name == "advisor_score"?
         │   YES → _predict_with_baseline()
         │   │        ├── 5 weighted components calculated:
         │   │        │    base_risk (0.12)
         │   │        │    failures (capped at 0.48)
         │   │        │    attendance_gap (0-0.30)
         │   │        │    grade_gap (0-0.38)
         │   │        │    study_time (-0.03 per level above 1)
         │   │        ├── Raw score = sum of components
         │   │        ├── Clamped to [0.01, 0.99]
         │   │        ├── Categorized: low < 0.32, medium 0.32-0.62, high >= 0.62
         │   │        └── Score adjustment (floor/cap) computed
         │   │
         │   NO → _predict_with_artifact()
         │         ├── Load pickled Pipeline from artifacts/models/{model}.pkl
         │         ├── Feature dict: {school, age, study_time, failures, absences, g1, g2}
         │         ├── Vectorize via DictVectorizer
         │         ├── Predict probability via predict_proba()[0][1]
         │         ├── Risk score = 1 - probability
         │         ├── SHAP contributions (try shappy.Explainer, then TreeExplainer)
         │         │   └── Fallback: coef_ (linear) or feature_importances_ (tree)
         │         │       └── Fallback: baseline contributors
         │         └── Top 5 contributors by absolute value
         │
         ▼
  PredictionResponse returned
  (student_id, risk_score, risk_category, model_name, top_contributors)
```

**Key files:** `api/routes/prediction.py`, `application/prediction_service.py`, `application/training_service.py`, `domain/model_names.py`

**Fallback chain:** ML artifact (pickled model) → Baseline advisor score (deterministic weighted formula)

### Recommendation Generation Flow

```
Advisor input via API (POST /api/v1/recommend)
         │
         ▼
  RecommendationRequest validated
  (prediction features + search query + filters)
         │
         ▼
  RecommendationService.recommend()
         │
         ├── 1. Predict risk
         │      └── PredictionService.predict(request.prediction)
         │
         ├── 2. Focused search for similar cases
         │      ├── Augment query with student profile
         │      ├── Set filters: same school, ±15 attendance, ±1 failures
         │      └── RetrievalService.search(focused_request)
         │
         ├── 3. Extract evidence case IDs (top 5)
         │
         ├── 4. Draft deterministic intervention plan
         │      └── draft_intervention_plan(prediction, retrieved_cases)
         │           ├── Identify risk drivers from prediction
         │           ├── Select variant by student_id hash (3 variants)
         │           ├── Build driver-specific actions (failures, attendance, grades, study time)
         │           └── Format: Immediate action + Support plan + Follow-up check
         │
         ├── 5. Agent workflow
         │      └── AgentWorkflow.generate_recommendation()
         │           ├── Try LangGraph (StateGraph with 4 nodes)
         │           │   ├── retrieve agent: summarize retrieved cases
         │           │   ├── predict agent: summarize risk
         │           │   ├── recommend agent: draft plan + feedback examples
         │           │   │   + judge examples → LLM call → recommendation
         │           │   └── explain agent: top 3 driver factors
         │           │
         │           └── Fallback: Direct LLM call
         │               ├── Assemble context (query, prediction, cases, tools)
         │               ├── Structured prompt with guidelines
         │               └── LLM response → recommendation
         │
         ├── 6. If agent returns None, use drafted plan as final
         │
         ▼
  RecommendationResponse returned
  (student_id, risk_category, recommendation, reasoning, evidence_case_ids)
```

**Key files:** `api/routes/recommendation.py`, `application/recommendation_service.py`, `application/agent_workflow.py`, `application/agent_tools.py`, `application/intervention_planner.py`

**Fallback chain:** LangGraph StateGraph → Direct LLM call → Deterministic drafted plan

### RAG Retrieval Flow

```
Advisor query via API (POST /api/v1/search)
         │
         ▼
  SearchRequest validated
  (query, filters: school, attendance range, failures range, top_k)
         │
         ▼
  RetrievalService.search(request)
         │
         ├── Qdrant configured? (is_configured() returns true)
         │   YES → _search_hybrid()
         │   │
         │   │   ├── Dense Qdrant search
         │   │   │   ├── Embed query via BAAI/bge-small-en-v1.5 (384-dim)
         │   │   │   │   └── Fallback: hash-based embedding
         │   │   │   ├── Qdrant ANN search with payload filters
         │   │   │   │   └── Filters: school match, attendance range, failures range
         │   │   │   └── Return top 20 candidates
         │   │   │
         │   │   ├── Sparse BM25 search
         │   │   │   ├── Query PostgreSQL with same filters (up to 500 rows)
         │   │   │   ├── BM25Okapi scoring against case_text corpus
         │   │   │   │   └── Fallback: term-overlap scoring
         │   │   │   └── Return top 20 candidates
         │   │   │
         │   │   ├── RRF Fusion (k=60)
         │   │   │   ├── Each candidate: score = sum(1 / (60 + rank)) across both rankings
         │   │   │   └── Sorted descending, top 20
         │   │   │
         │   │   ├── Cross-Encoder Reranker
         │   │   │   ├── (query, case_text) pairs for top 20
         │   │   │   ├── BAAI/bge-reranker-base scores
         │   │   │   │   └── Fallback: no reranking (pass through)
         │   │   │   └── Return top_k (default 5)
         │   │   │
         │   │   └── Build SearchResponse
         │   │
         │   NO → _search_repository()
         │   │   ├── Query PostgreSQL with filters (up to 200 rows)
         │   │   ├── Term-overlap scoring + structured similarity scoring
         │   │   │   (attendance proximity + failures proximity)
         │   │   └── Return top_k results
         │   │
         │   NO (repository fails too) → _baseline_search()
         │       ├── Synthesize 2 hardcoded cases from filters
         │       └── Return baseline cases
         │
         ▼
  SearchResponse returned
  (query, total, results: [RetrievedCase with case_id, student_id,
   score, school, failures, absences, final_grade, case_text])
```

**Key files:** `application/retrieval_service.py`, `infrastructure/qdrant_store.py`, `infrastructure/embeddings.py`, `infrastructure/reranker.py`, `infrastructure/student_repository.py`

**Fallback chain:** Hybrid search (dense+sparse+RRF+reranker) → Repository search (term overlap + structured similarity) → Baseline search (synthetic cases)

### Feedback Storage and Retrieval Flow

```
Advisor rates recommendation via API (POST /api/v1/feedback)
         │
         ▼
  FeedbackRequest validated
  (query, recommendation, rating: useful/not_useful, advisor_note)
         │
         ▼
  FeedbackService.store_feedback(request)
         │
         ├── Generate UUID feedback_id
         ├── Try PostgreSQL insert via StudentRepository.store_feedback()
         │   └── On failure: append to _IN_MEMORY_FEEDBACK list
         │
         ▼
  FeedbackResponse returned
  (feedback_id, stored=true, received_at, message)
```

```
                  RETRIEVAL (in AgentWorkflow / Direct LLM)
                             │
                             ▼
  AdvisorToolRuntime.retrieve_feedback_examples(limit=SSA_FEEDBACK_EXAMPLES_LIMIT)
         │
         ├── Query PostgreSQL: SELECT query, recommendation, rating, advisor_note
         │                    FROM feedback ORDER BY created_at DESC LIMIT N
         │   └── On failure: return empty list
         │
         ├── Format each row:
         │   - rating == "useful": "follow this pattern: Query: ... | Recommendation: ..."
         │   - rating == "not_useful": "avoid this pattern: Query: ... | Recommendation: ..."
         │
         ▼
  Injected into LLM prompt:
  "Treat useful feedback as patterns to follow and not-useful feedback
   as patterns to avoid."
```

```
                  RETRIEVAL (judge-scored examples)
                             │
                             ▼
  AdvisorToolRuntime.retrieve_judge_examples(limit=SSA_FEEDBACK_EXAMPLES_LIMIT)
         │
         ├── Query PostgreSQL: SELECT query, recommendation, scores, notes
         │                    FROM evaluation_results
         │                    ORDER BY (scores->>'overall')::float DESC, created_at DESC
         │                    LIMIT N
         │   └── On failure: return empty list
         │
         ├── Format: "overall={score}: Query: ... | Recommendation: ..."
         │
         ▼
  Injected into LLM prompt alongside feedback examples
```

**Key files:** `application/feedback_service.py`, `application/agent_tools.py`, `infrastructure/student_repository.py`

**Fallback chain:** PostgreSQL insert → In-memory list (volatile, lost on restart)

### Follow-Up Assessment Flow

```
Advisor initiates two-week review via API (POST /api/v1/follow-up/cases/{id}/assess)
         │
         ▼
  FollowUpAssessmentRequest validated
  (student profile, risk info, weeks_since_plan, recommendation,
   advisor_note, plan_followed, attendance_trend, marks_trend, failures_trend)
         │
         ▼
  FollowUpService.assess(request)
         │
         ├── Try LLM assessment
         │   ├── Call judge model (temperature=0) with structured prompt
         │   ├── Expect JSON: decision, recommended_status, escalation_target,
         │   │               rationale, next_steps, confidence
         │   └── Parse and validate JSON
         │       └── On failure: fall through
         │
         └── Deterministic rubric assessment
             ├── Count positive signals:
             │   +1 attendance improved
             │   +1 marks improved
             │   +1 failures decreased
             ├── Count negative signals:
             │   +1 attendance worsened
             │   +1 marks worsened
             │   +2 failures increased
             ├── Check plan adherence:
             │   fully followed / partially / not_followed
             ├── Check advisor note keywords:
             │   concern terms: barely, declined, failed, missed, worse, still low...
             │   progress terms: better, completed, improved, increased, recovered...
             │
             ├── Escalate if:
             │   high risk + negative signals OR not-followed
             │   OR failures increased
             │   OR not/partially followed + no positive signals
             │   OR 2+ negative signals
             │   OR concerning note + fewer than 2 positive signals
             │
             ├── Close if:
             │   not escalated
             │   AND plan fully followed
             │   AND 2+ positive signals
             │   AND 0 negative signals
             │   AND risk score < 0.65
             │
             └── Otherwise: Monitor
                 └── Escalation target by risk:
                     high → Counsellor
                     medium → Academic advisor
                     low → Class teacher
         │
         ▼
  FollowUpAssessmentResponse returned
  (decision: close/monitor/escalate, recommended_status,
   escalation_target, rationale, next_steps, confidence, generated_by)
```

**Key files:** `api/routes/follow_up.py`, `application/follow_up_service.py`, `infrastructure/follow_up_repository.py`

**Fallback chain:** LLM assessment (structured JSON prompt) → Deterministic signal-counting rubric

---

## 5. Error Handling Strategy

### Graceful Degradation Through Fallback Chains

Every critical service has a fallback chain. The primary path uses the most capable implementation; fallbacks reduce functionality rather than failing.

| Service | Primary | Fallback 1 | Fallback 2 |
|---|---|---|---|
| `RetrievalService.search()` | Hybrid (dense+sparse+RRF+reranker) | Repository search (term overlap) | Baseline search (synthetic cases) |
| `PredictionService.predict()` | ML artifact (pickled model) | Advisor score (deterministic) | — |
| `AgentWorkflow.generate_recommendation()` | LangGraph StateGraph | Direct LLM call | Drafted plan |
| `EvaluationService.evaluate()` | LLM-as-judge | Rubric baseline | — |
| `FollowUpService.assess()` | LLM assessment | Deterministic rubric | — |
| `EmbeddingProvider.embed()` | SentenceTransformer | Hash-based embedding | — |
| `FeedbackService.store_feedback()` | PostgreSQL insert | In-memory list | — |

### Silent Failure for Non-Critical Operations

Operations that are not essential to the primary response should fail silently (log and continue). This prevents a non-critical failure from degrading the user experience.

**Examples:**

1. **Evaluation storage failure** (`EvaluationService._store_result`):
```python
def _store_result(self, request, response):
    try:
        self._repository.store_evaluation(...)
    except Exception:
        pass  # Non-critical: evaluation is stored for analytics, not for the response
```

2. **Feedback example retrieval failure** (`AdvisorToolRuntime.retrieve_feedback_examples`):
```python
try:
    rows = self._repository.list_feedback_examples(limit=limit)
except RuntimeError:
    rows = []  # Non-critical: examples improve quality but absence doesn't break the flow
```

3. **Judge example retrieval failure** (`AdvisorToolRuntime.retrieve_judge_examples`):
```python
try:
    rows = self._repository.list_judged_recommendations(limit=limit)
except RuntimeError:
    rows = []  # Non-critical: same reasoning as feedback examples
```

### HTTPException for API Errors

API-layer errors that should be communicated to the client use FastAPI's `HTTPException`. These represent client errors (invalid input, authentication failure, resource not found) rather than infrastructure failures.

**Examples:**

- **Authentication failure** (`api/routes/auth.py`): Invalid credentials return HTTP 401.
- **Model not found** (training with insufficient data): `TrainingService.train()` raises `ValueError` with a descriptive message. The admin route can catch this and return HTTP 400.
- **Invalid input** (Pydantic validation): FastAPI automatically returns HTTP 422 with validation details when Pydantic validation fails on a request body.

### RuntimeError for Infrastructure Failures

Infrastructure failures (database connection failure, missing library, misconfigured service) raise `RuntimeError` with descriptive messages. These propagate to FastAPI's exception handler and return HTTP 500.

**Examples:**

1. **Missing library** (`QdrantCaseStore._client_and_models`):
```python
try:
    from qdrant_client import QdrantClient, models
except ImportError as exc:
    raise RuntimeError("Install the retrieval extra with `uv sync --extra retrieval`.") from exc
```

2. **Missing ML dependencies** (`TrainingService.train`):
```python
try:
    from sklearn.compose import ColumnTransformer
    ...
except ImportError as exc:
    raise RuntimeError("Install ML dependencies with `uv sync --extra ml`.") from exc
```

3. **Insufficient training data** (`TrainingService.train`):
```python
if len(set(labels)) < 2 or len(labels) < 20:
    raise ValueError("Training requires at least 20 rows with both pass and at-risk outcomes.")
```

### Error Boundaries by Layer

| Layer | Error Handling Strategy | Example |
|---|---|---|
| **API Routes** | Catch service exceptions, return HTTP 500. Pydantic handles validation (422). | `recommendation.py` route delegates to service; any exception propagates to FastAPI handler. |
| **Application Services** | Try primary implementation, fall back to degraded path. Log warnings on fallback. | `RetrievalService.search()` catches all exceptions from `_search_hybrid()`, falls to `_search_repository()`. |
| **Infrastructure Adapters** | Raise `RuntimeError` for configuration/connectivity issues. Silent pass for non-critical operations. | `QdrantCaseStore.upsert_cases()` raises if Qdrant is not configured. |
| **External Dependencies** | Try/except around all external calls. LLM failures caught and return None. | `EvaluationService._evaluate_with_llm()` catches `Exception` on `llm.invoke()` and returns None. |

### Logging Strategy

Logging uses Python's `logging` module with `getLogger(__name__)` for each module. Key logging points:

- LLM failures (warnings with model and provider info):
  ```python
  log.warning("get_chat_llm returned None for judge model=%s provider=%s", ...)
  ```
- LLM invoke failures (warnings with exc_info):
  ```python
  log.warning("LLM judge invoke failed", exc_info=True)
  ```
- Unparseable LLM responses (warnings with truncated content):
  ```python
  log.warning("LLM judge response could not be parsed: %r", raw_content[:300])
  ```

### Configuration-Driven Resilience

- `SSA_ENABLE_REMOTE_MODELS=false` disables sentence-transformers and cross-encoder, forcing hash-based embeddings and no reranking. This allows full offline development.
- Missing `SSA_QDRANT_URL` or `SSA_QDRANT_API_KEY` causes `QdrantCaseStore.is_configured()` to return false, triggering the repository search fallback.
- Missing `SSA_OPENAI_API_KEY` with `SSA_LLM_PROVIDER=openai` causes `get_chat_llm()` to return None, triggering rubric/plan fallbacks.
- Empty `SSA_SMTP_HOST` causes `ParentNotificationService` to simulate email sending instead of actually connecting to SMTP.
- `model_dir` defaulting to `artifacts/models` means ML artifacts are found relative to the working directory.

---

> **End of Document**
>
> This document captures the architectural and design decisions for the AI-Powered Student Success Assistant. All descriptions correspond to the implementation in backend source files.
