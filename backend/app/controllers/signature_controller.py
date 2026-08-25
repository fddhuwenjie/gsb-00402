import logging

from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.controllers.deps import get_current_user_id, require_admin, CurrentUser
from app.schemas.common import ApiResponse, PageResponse
from app.schemas.signature import SignatureFileDTO, SignatureContentDTO
from app.services.signature_service import SignatureService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/signatures", tags=["Signatures"])


@router.get("", response_model=ApiResponse[PageResponse[SignatureFileDTO]])
async def list_signatures(
    page: int = 1,
    page_size: int = 20,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    service = SignatureService(db)
    result = await service.list_signatures(page, page_size)
    return ApiResponse(data=result)


@router.post("", response_model=ApiResponse[SignatureFileDTO])
async def upload_signature(
    name: str = Form(...),
    description: str = Form(""),
    file: UploadFile = File(...),
    admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    service = SignatureService(db)
    result = await service.upload_signature(name, description, file.filename or "unknown.yar", content)
    logger.info("Signature uploaded by admin %s: %s", admin.username, name)
    return ApiResponse(data=result)


@router.get("/{sig_id}", response_model=ApiResponse[SignatureContentDTO])
async def get_signature(
    sig_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    service = SignatureService(db)
    result = await service.get_signature_detail(sig_id)
    return ApiResponse(data=result)


@router.delete("/{sig_id}", response_model=ApiResponse)
async def delete_signature(
    sig_id: int,
    admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    service = SignatureService(db)
    deleted = await service.delete_signature(sig_id)
    if not deleted:
        return ApiResponse(code=404, message="Signature file not found")
    logger.info("Signature deleted by admin %s: id=%d", admin.username, sig_id)
    return ApiResponse(message="Deleted successfully")
