"""Shared dependencies for controller injection."""

import logging
from dataclasses import dataclass

from fastapi import Header, HTTPException, status

from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)


@dataclass
class CurrentUser:
    id: int
    username: str
    role: str


async def get_current_user_id(authorization: str = Header(default="")) -> int:
    user = await get_current_user(authorization)
    return user.id


async def get_current_user(authorization: str = Header(default="")) -> CurrentUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
        )
    token = authorization[7:]
    try:
        payload = AuthService.verify_token(token)
        return CurrentUser(
            id=int(payload["sub"]),
            username=payload.get("username", ""),
            role=payload.get("role", "user"),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


async def require_admin(authorization: str = Header(default="")) -> CurrentUser:
    user = await get_current_user(authorization)
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user
