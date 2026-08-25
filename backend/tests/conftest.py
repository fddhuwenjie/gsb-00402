"""Shared pytest fixtures.

Configures an in-memory SQLite database and required env vars before the app is
imported, so tests exercise the real service/repository layer without a Postgres
instance or a new database framework.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("CODE_SCAN_DIR", "/tmp/cbom_test_scans")
os.environ.setdefault("UPLOAD_DIR", "/tmp/cbom_test_uploads")

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.database import Base
# Import models so their tables are registered on Base.metadata.
from app.entities import models  # noqa: F401


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Provide a fresh in-memory database session per test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def api_client():
    """FastAPI app wired to a shared in-memory DB, with seeded users + tokens.

    Yields a dict with an httpx AsyncClient and pre-minted admin/user tokens so
    permission scenarios (unauthenticated, non-admin) can be exercised over HTTP
    through the real auth dependencies.
    """
    import httpx
    from httpx import ASGITransport

    from app.main import app
    from app.database import get_db
    from app.services.auth_service import AuthService
    from app.entities.models import User, UserRole

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    # Seed an admin and a regular user, then mint tokens for each.
    async with factory() as session:
        admin = User(username="admin", password_hash="x", role=UserRole.ADMIN)
        user = User(username="user", password_hash="x", role=UserRole.USER)
        session.add_all([admin, user])
        await session.commit()
        await session.refresh(admin)
        await session.refresh(user)
        auth = AuthService(session)
        admin_token = auth._create_token(admin)
        user_token = auth._create_token(user)

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield {
            "client": client,
            "factory": factory,
            "admin_headers": {"Authorization": f"Bearer {admin_token}"},
            "user_headers": {"Authorization": f"Bearer {user_token}"},
        }

    app.dependency_overrides.clear()
    await engine.dispose()
