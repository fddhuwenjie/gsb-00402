import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.controllers.deps import get_current_user, require_admin, CurrentUser
from app.schemas.baseline import (
    BaselineCreateRequest,
    BaselineDTO,
    BaselineDetailDTO,
    DiffCreateRequest,
    DiffReportDTO,
    DiffReportDetailDTO,
)
from app.schemas.common import ApiResponse, PageResponse
from app.services.baseline_service import BaselineService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/baselines", tags=["Baseline"])
diff_router = APIRouter(prefix="/api/diffs", tags=["Diff"])


# ---------------- baselines ----------------

@router.get("", response_model=ApiResponse[PageResponse[BaselineDTO]])
async def list_baselines(
    page: int = 1,
    page_size: int = 20,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = BaselineService(db)
    result = await service.list_baselines(page, page_size, user)
    return ApiResponse(data=result)


@router.post("", response_model=ApiResponse[BaselineDetailDTO])
async def create_baseline(
    req: BaselineCreateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = BaselineService(db)
    result = await service.create_baseline(req, user)
    logger.info("Baseline created by user %d: %s", user.id, req.name)
    return ApiResponse(data=result)


@router.get("/{baseline_id}", response_model=ApiResponse[BaselineDetailDTO])
async def get_baseline(
    baseline_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = BaselineService(db)
    result = await service.get_baseline_detail(baseline_id, user)
    return ApiResponse(data=result)


@router.delete("/{baseline_id}", response_model=ApiResponse)
async def delete_baseline(
    baseline_id: int,
    admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    service = BaselineService(db)
    deleted = await service.delete_baseline(baseline_id)
    if not deleted:
        return ApiResponse(code=404, message="Baseline not found")
    logger.info("Baseline deleted by admin %s: id=%d", admin.username, baseline_id)
    return ApiResponse(message="Deleted successfully")


# ---------------- diff reports ----------------

@diff_router.get("", response_model=ApiResponse[PageResponse[DiffReportDTO]])
async def list_diffs(
    page: int = 1,
    page_size: int = 20,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = BaselineService(db)
    result = await service.list_diffs(page, page_size, user)
    return ApiResponse(data=result)


@diff_router.post("", response_model=ApiResponse[DiffReportDetailDTO])
async def create_diff(
    req: DiffCreateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = BaselineService(db)
    result = await service.create_diff(req, user)
    logger.info("Diff report created by user %d: baseline=%d task=%d", user.id, req.baseline_id, req.task_id)
    return ApiResponse(data=result)


@diff_router.get("/{diff_id}", response_model=ApiResponse[DiffReportDetailDTO])
async def get_diff(
    diff_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = BaselineService(db)
    result = await service.get_diff_detail(diff_id, user)
    return ApiResponse(data=result)


@diff_router.delete("/{diff_id}", response_model=ApiResponse)
async def delete_diff(
    diff_id: int,
    admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    service = BaselineService(db)
    deleted = await service.delete_diff(diff_id)
    if not deleted:
        return ApiResponse(code=404, message="Diff report not found")
    logger.info("Diff report deleted by admin %s: id=%d", admin.username, diff_id)
    return ApiResponse(message="Deleted successfully")
