import os
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from student_success_assistant.domain.model_names import ADVISOR_SCORE_MODEL, LOGISTIC_REGRESSION_MODEL

PROJECT_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    app_name: str = "Student Success Assistant API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    environment: str = "local"
    log_level: str = "INFO"
    database_url: str = ""
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "student_cases"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimension: int = 384
    enable_remote_models: bool = False
    reranker_model: str = "BAAI/bge-reranker-base"
    openai_api_key: str = ""
    openai_base_url: str = ""
    llm_provider: str = "ollama"
    llm_model: str = "llama3.2:3b"
    llm_temperature: float = 0.7
    judge_model: str = "llama3.2:3b"
    ollama_base_url: str = "http://localhost:11434"
    langchain_tracing_v2: bool = Field(
        default=False,
        validation_alias=AliasChoices("SSA_LANGCHAIN_TRACING_V2", "LANGCHAIN_TRACING_V2"),
    )
    langchain_endpoint: str = Field(
        default="https://api.smith.langchain.com",
        validation_alias=AliasChoices("SSA_LANGCHAIN_ENDPOINT", "LANGCHAIN_ENDPOINT"),
    )
    langchain_project: str = Field(
        default="student-success-assistant",
        validation_alias=AliasChoices("SSA_LANGCHAIN_PROJECT", "LANGCHAIN_PROJECT"),
    )
    langchain_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("SSA_LANGCHAIN_API_KEY", "LANGCHAIN_API_KEY"),
    )
    langchain_public_api_key: str = ""
    langchain_private_api_key: str = ""
    model_dir: str = "artifacts/models"
    selected_model: str = LOGISTIC_REGRESSION_MODEL
    data_dir: str = "data"
    default_dataset_path: str = "../data/processed/student-merged.csv"
    feedback_examples_limit: int = 3
    prediction_model: str = ADVISOR_SCORE_MODEL
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "advisor@example.edu"
    smtp_use_tls: bool = True
    auth_username: str = "advisor"
    auth_password: str = "advisor-demo"
    auth_token_secret: str = "change-this-local-development-secret"
    auth_token_ttl_seconds: int = 60 * 60 * 8

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_prefix="SSA_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    configure_langchain_environment(settings)
    return settings


def configure_langchain_environment(settings: Settings) -> None:
    langchain_api_key = settings.langchain_api_key or settings.langchain_private_api_key
    values = {
        "LANGCHAIN_TRACING_V2": "true" if settings.langchain_tracing_v2 else "false",
        "LANGCHAIN_ENDPOINT": settings.langchain_endpoint,
        "LANGCHAIN_PROJECT": settings.langchain_project,
        "LANGCHAIN_API_KEY": langchain_api_key,
        "LANGCHAIN_PUBLIC_API_KEY": settings.langchain_public_api_key,
        "LANGCHAIN_PRIVATE_API_KEY": settings.langchain_private_api_key,
    }
    for key, value in values.items():
        if value and not os.environ.get(key):
            os.environ[key] = value
