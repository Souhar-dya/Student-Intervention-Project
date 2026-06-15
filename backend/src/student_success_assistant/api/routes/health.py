from fastapi import APIRouter

from student_success_assistant.application.agent_workflow import AgentWorkflow
from student_success_assistant.core.config import get_settings
from student_success_assistant.schemas.health import HealthResponse, ReadinessCheck, ReadinessResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadinessResponse)
def readiness() -> ReadinessResponse:
    settings = get_settings()
    checks = {
        "database": ReadinessCheck(
            configured=bool(settings.database_url),
            detail="SSA_DATABASE_URL is set" if settings.database_url else "SSA_DATABASE_URL is empty",
        ),
        "qdrant": ReadinessCheck(
            configured=bool(settings.qdrant_url and settings.qdrant_api_key),
            detail="Qdrant URL and API key are set"
            if settings.qdrant_url and settings.qdrant_api_key
            else "Qdrant URL or API key is missing",
        ),
        "llm": ReadinessCheck(
            configured=bool(settings.openai_api_key),
            detail=(
                f"generation={settings.llm_model}, judge={settings.judge_model}"
                if settings.openai_api_key
                else "LLM key is optional and empty"
            ),
        ),
        "langgraph": ReadinessCheck(
            configured=AgentWorkflow().graph_available(),
            detail="LangGraph is installed"
            if AgentWorkflow().graph_available()
            else "Install agent dependencies with `uv sync --extra agents`",
        ),
        "langchain": ReadinessCheck(
            configured=bool(settings.langchain_api_key or settings.langchain_private_api_key),
            detail=(
                f"project={settings.langchain_project}, tracing={settings.langchain_tracing_v2}"
                if settings.langchain_api_key or settings.langchain_private_api_key
                else "LangChain/LangSmith key is optional and empty"
            ),
        ),
    }
    status = "ready" if checks["database"].configured and checks["qdrant"].configured else "degraded"
    return ReadinessResponse(status=status, checks=checks)
