# Architecture Notes

## Boundaries

- `backend/` contains the FastAPI service and Python dependency workflow.
- `frontend/` contains the React + Vite application and Newsprint design system.
- The backend must not depend on frontend code, and the frontend must communicate through HTTP APIs.

## Backend Shape

- `api/`: FastAPI routers, request/response schemas, and HTTP concerns.
- `application/`: use-case orchestration for retrieval, prediction, recommendation, explanation, evaluation, and feedback.
- `domain/`: business concepts and rules that do not depend on frameworks.
- `infrastructure/`: PostgreSQL, Qdrant, model, embedding, reranker, and LLM integrations.
- `core/`: settings, lifecycle, and cross-cutting configuration.

Route handlers should stay thin. They validate input, call application services, and return schemas.
Application services should depend on interfaces where external systems are involved so PostgreSQL,
Qdrant, model, and LLM implementations can be tested or replaced independently.

## Frontend Shape

- `app/`: app composition and top-level providers.
- `components/ui/`: reusable design-system primitives.
- `components/layout/`: shell, navigation, and layout primitives.
- `features/`: page-level and workflow-level modules grouped by product capability.
- `styles/`: centralized Newsprint tokens and global utilities.

The frontend should keep visual tokens centralized, prefer reusable components over one-off styles,
and preserve accessible semantic HTML.

