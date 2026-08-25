import logging
import os

import bcrypt
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import engine, Base, async_session_factory
from app.entities.models import User, UserRole
from app.exceptions.handlers import register_exception_handlers
from app.controllers.auth_controller import router as auth_router
from app.controllers.signature_controller import router as sig_router
from app.controllers.analysis_controller import router as analysis_router
from app.controllers.dashboard_controller import router as dashboard_router
from app.controllers.user_controller import router as user_router
from app.controllers.baseline_controller import router as baseline_router, diff_router as diff_report_router

LOG_LEVEL = logging.DEBUG if settings.DEBUG else logging.INFO
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def _seed_admin():
    """Create default admin user if none exists."""
    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT COUNT(*) FROM users")
        )
        count = result.scalar()
        if count == 0:
            hashed = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
            admin = User(username="admin", password_hash=hashed, role=UserRole.ADMIN)
            session.add(admin)
            hashed2 = bcrypt.hashpw("user123".encode(), bcrypt.gensalt()).decode()
            user = User(username="testuser", password_hash=hashed2, role=UserRole.USER)
            session.add(user)
            await session.commit()
            logger.info("Seeded default admin and test user")
        else:
            logger.info("Users already exist, skipping seed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.CODE_SCAN_DIR, exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ensured")

    await _seed_admin()
    logger.info("CBOM Analyzer v%s started", settings.APP_VERSION)

    yield

    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

register_exception_handlers(app)

app.include_router(auth_router)
app.include_router(sig_router)
app.include_router(analysis_router)
app.include_router(dashboard_router)
app.include_router(user_router)
app.include_router(baseline_router)
app.include_router(diff_report_router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}
