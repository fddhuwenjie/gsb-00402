import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.controllers.deps import get_current_user_id
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.signature_repository import SignatureRepository
from app.schemas.common import ApiResponse
from app.schemas.dashboard import DashboardStats

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=ApiResponse[DashboardStats])
async def get_stats(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    analysis_repo = AnalysisRepository(db)
    sig_repo = SignatureRepository(db)

    status_counts = await analysis_repo.count_by_status()
    total_analyses = await analysis_repo.count_total()
    risk_dist = await analysis_repo.risk_distribution()
    lang_dist = await analysis_repo.language_distribution()
    total_sigs = await sig_repo.count()
    total_funcs = await sig_repo.total_functions()

    stats = DashboardStats(
        total_analyses=total_analyses,
        completed_analyses=status_counts.get("completed", 0),
        failed_analyses=status_counts.get("failed", 0),
        total_signatures=total_sigs,
        total_functions=total_funcs,
        recent_risk_distribution=risk_dist,
        language_distribution=lang_dist,
    )
    return ApiResponse(data=stats)
