from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from student_success_assistant.api.router import api_router
from student_success_assistant.api.routes import health
from student_success_assistant.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
