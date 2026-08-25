import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.controllers.deps import get_current_user, require_admin, CurrentUser
from app.schemas.common import ApiResponse, PageResponse
from app.schemas.baseline import (
    BaselineCreateRequest,
    BaselineDTO,
    BaselineDetailDTO,
    DiffCreateRequest,
    DiffDetailDTO,
    DiffReportDTO,
)
from app.services.baseline_service import BaselineService

logger = logging.getLogger(__name__)

baseline_router = APIRouter(prefix="/api/baselines", tags=["Baselines"])
diff_router = APIRouter(prefix="/api/diffs", tags=["Diffs"])


@baseline_router.get("", response_model=ApiResponse[PageResponse[BaselineDTO]])
async def list_baselines(
    page: int = 1,
    page_size: int = 20,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = BaselineService(db)
    result = await service.list_baselines(current_user, page, page_size)
    return ApiResponse(data=result)


@baseline_router.post("", response_model=ApiResponse[BaselineDetailDTO])
async def create_baseline(
    req: BaselineCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = BaselineService(db)
    result = await service.create_baseline(req, current_user)
    logger.info("Baseline created by user %d: %s", current_user.id, req.name)
    return ApiResponse(data=result)


@baseline_router.get("/{baseline_id}", response_model=ApiResponse[BaselineDetailDTO])
async def get_baseline(
    baseline_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = BaselineService(db)
    result = await service.get_baseline(baseline_id, current_user)
    return ApiResponse(data=result)


@baseline_router.delete("/{baseline_id}", response_model=ApiResponse)
async def delete_baseline(
    baseline_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = BaselineService(db)
    deleted = await service.delete_baseline(baseline_id, current_user)
    if not deleted:
        return ApiResponse(code=404, message="Baseline not found")
    logger.info("Baseline deleted by user %s: id=%d", current_user.username, baseline_id)
    return ApiResponse(message="Deleted successfully")


@diff_router.post("", response_model=ApiResponse[DiffDetailDTO])
async def create_diff(
    req: DiffCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = BaselineService(db)
    result = await service.create_diff(req.baseline_id, req.task_id, current_user)
    logger.info(
        "Diff created by user %d: baseline=%d task=%d",
        current_user.id, req.baseline_id, req.task_id,
    )
    return ApiResponse(data=result)


@diff_router.get("/{diff_id}", response_model=ApiResponse[DiffDetailDTO])
async def get_diff(
    diff_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = BaselineService(db)
    result = await service.get_diff(diff_id, current_user)
    return ApiResponse(data=result)


@diff_router.get("", response_model=ApiResponse[list[DiffReportDTO]])
async def list_diffs(
    task_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = BaselineService(db)
    result = await service.list_diffs_by_task(task_id, current_user)
    return ApiResponse(data=result)
