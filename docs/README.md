# AI-Powered Student Success Assistant — Documentation Suite

> Enterprise capstone evaluation documentation for an AI-Powered Student Success Assistant
> built on the UCI Student Performance Dataset with Hexagonal Architecture, LangGraph agents,
> hybrid RAG retrieval, and local LLM inference via Ollama.

---

## Document Index

| # | Document | Description |
|---|----------|-------------|
| 01 | [Architecture](01_ARCHITECTURE.md) | System architecture, hexagonal layers, technology stack, SDLC approach, key design decisions |
| 02 | [Design](02_DESIGN.md) | ADRs, SOLID principles, design patterns, data flows, error handling strategy |
| 03 | [API Reference](03_API.md) | Complete API documentation for all 22 endpoints with schemas, validation, and examples |
| 04 | [Database](04_DATABASE.md) | PostgreSQL schema, Qdrant collection, ER diagram, architecture decisions |
| 05 | [Testing](05_TESTING.md) | Test strategy, coverage mapping, fixture architecture, CI/CD integration |
| 06 | [Security](06_SECURITY.md) | Authentication, authorization, data protection, LLM security, open issues |
| 07 | [Presentation](07_PRESENTATION.md) | 20-slide capstone presentation outline with speaker notes |
| 08 | [README](08_README.md) | Comprehensive project README with quick start, configuration, and development guide |
| 09 | [Diagrams](09_DIAGRAMS.md) | 11 Mermaid diagrams covering all system aspects |

---

## Technology Stack Summary

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Backend | Python 3.11 / FastAPI | REST API server (port 8000) |
| Frontend | React / Vite | Single-page application (port 5173) |
| Database | PostgreSQL (Aiven) | Relational data storage |
| Vector DB | Qdrant Cloud | 384-dim embedding storage + hybrid search |
| LLM | Ollama / llama3.2:3b | Local LLM inference (port 11434) |
| Embeddings | BAAI/bge-small-en-v1.5 | Dense vector embeddings |
| Reranker | BAAI/bge-reranker-base | Cross-encoder result reranking |
| Prediction | XGBoost / Logistic Regression / Random Forest | Risk prediction models |
| XAI | SHAP | Feature importance explanations |
| Agent Framework | LangGraph | Multi-agent orchestration |
| Validation | Pydantic v2 | Request/response schema validation |
| Auth | HMAC-SHA256 | Token-based authentication |

---

## Quick Links

- **Backend**: `backend/src/student_success_assistant/`
- **Frontend**: `frontend/src/`
- **Tests**: `backend/tests/`
- **Configuration**: `backend/.env`
- **Start Backend**: `uv run api` (requires `ollama serve` running)
- **Start Frontend**: `npm run dev`

---

*Generated for enterprise capstone evaluation — June 2026*
