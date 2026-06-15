from fastapi import APIRouter, Depends, HTTPException, status

from student_success_assistant.core.security import (
    create_access_token,
    credentials_are_valid,
    require_authenticated_user,
)
from student_success_assistant.schemas.auth import AuthSession, LoginRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=AuthSession)
def login(request: LoginRequest) -> AuthSession:
    if not credentials_are_valid(request.username, request.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    return AuthSession(token=create_access_token(request.username), username=request.username)


@router.get("/me", response_model=AuthSession)
def current_session(username: str = Depends(require_authenticated_user)) -> AuthSession:
    return AuthSession(token="", username=username)
