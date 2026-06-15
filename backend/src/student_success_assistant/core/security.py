from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from student_success_assistant.core.config import get_settings

auth_scheme = HTTPBearer(auto_error=False)


def create_access_token(username: str) -> str:
    settings = get_settings()
    payload = {
        "sub": username,
        "exp": int(time.time()) + settings.auth_token_ttl_seconds,
    }
    encoded_payload = _base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _sign(encoded_payload, settings.auth_token_secret)
    return f"{encoded_payload}.{signature}"


def require_authenticated_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _auth_error()

    settings = get_settings()
    try:
        payload = verify_access_token(credentials.credentials, settings.auth_token_secret)
    except ValueError as exc:
        raise _auth_error() from exc

    username = str(payload.get("sub") or "")
    if not username:
        raise _auth_error()
    return username


def verify_access_token(token: str, secret: str) -> dict[str, Any]:
    try:
        encoded_payload, signature = token.split(".", 1)
    except ValueError as exc:
        raise ValueError("Malformed token") from exc

    expected_signature = _sign(encoded_payload, secret)
    if not hmac.compare_digest(signature, expected_signature):
        raise ValueError("Invalid token signature")

    try:
        payload = json.loads(_base64url_decode(encoded_payload))
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError("Invalid token payload") from exc

    if int(payload.get("exp", 0)) < int(time.time()):
        raise ValueError("Token expired")
    return payload


def credentials_are_valid(username: str, password: str) -> bool:
    settings = get_settings()
    return hmac.compare_digest(username, settings.auth_username) and hmac.compare_digest(
        password,
        settings.auth_password,
    )


def _sign(encoded_payload: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), encoded_payload.encode("utf-8"), hashlib.sha256).digest()
    return _base64url_encode(digest)


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")


def _auth_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )
