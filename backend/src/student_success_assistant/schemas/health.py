from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class ReadinessCheck(BaseModel):
    configured: bool
    detail: str


class ReadinessResponse(BaseModel):
    status: str
    checks: dict[str, ReadinessCheck]
