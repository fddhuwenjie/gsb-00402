import logging
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.entities.models import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserDTO

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.repo = UserRepository(db)

    async def login(self, req: LoginRequest) -> TokenResponse:
        user = await self.repo.find_by_username(req.username)
        if not user:
            raise ValueError("Invalid username or password")
        if not bcrypt.checkpw(req.password.encode(), user.password_hash.encode()):
            raise ValueError("Invalid username or password")

        token = self._create_token(user)
        logger.info("User logged in: %s", user.username)
        return TokenResponse(access_token=token)

    async def register(self, req: RegisterRequest) -> UserDTO:
        existing = await self.repo.find_by_username(req.username)
        if existing:
            raise ValueError(f"Username '{req.username}' already exists")

        hashed = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
        user = User(
            username=req.username,
            password_hash=hashed,
            role=UserRole.USER,
        )
        user = await self.repo.create(user)
        logger.info("New user registered: %s", user.username)
        return UserDTO(
            id=user.id,
            username=user.username,
            role=user.role.value,
            created_at=user.created_at,
        )

    async def get_current_user(self, user_id: int) -> UserDTO:
        user = await self.repo.find_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        return UserDTO(
            id=user.id,
            username=user.username,
            role=user.role.value,
            created_at=user.created_at,
        )

    def _create_token(self, user: User) -> str:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {
            "sub": str(user.id),
            "username": user.username,
            "role": user.role.value,
            "exp": expire,
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    @staticmethod
    def verify_token(token: str) -> dict:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.InvalidTokenError:
            raise ValueError("Invalid token")
