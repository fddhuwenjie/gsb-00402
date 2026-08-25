import logging
import os
import tempfile
import shutil
import json
from typing import List

from fastapi import APIRouter, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.controllers.deps import get_current_user_id, require_admin, CurrentUser
from app.schemas.analysis import AnalysisCreateRequest, AnalysisTaskDTO, AnalysisDetailDTO
from app.schemas.common import ApiResponse, PageResponse
from app.services.analysis_service import AnalysisService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analyses", tags=["Analysis"])


@router.get("", response_model=ApiResponse[PageResponse[AnalysisTaskDTO]])
async def list_analyses(
    page: int = 1,
    page_size: int = 20,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    service = AnalysisService(db)
    result = await service.list_analyses(page, page_size)
    return ApiResponse(data=result)


@router.post("", response_model=ApiResponse[AnalysisDetailDTO])
async def create_analysis(
    req: AnalysisCreateRequest,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    service = AnalysisService(db)
    result = await service.create_and_run(req, user_id)
    logger.info("Analysis created by user %d: %s", user_id, req.name)
    return ApiResponse(data=result)


@router.post("/upload", response_model=ApiResponse[AnalysisDetailDTO])
async def create_analysis_with_upload(
    name: str = Form(...),
    language: str = Form(...),
    signature_file_ids: str = Form(...),
    project_key: str = Form(...),
    files: List[UploadFile] = File(...),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    通过上传文件创建分析任务
    """
    # 创建临时目录存放上传的文件
    temp_dir = tempfile.mkdtemp(prefix="cbom_scan_")
    
    try:
        # 保存上传的文件
        for file in files:
            file_path = os.path.join(temp_dir, file.filename)
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            logger.info("Saved uploaded file: %s", file_path)
        
        # 解析 signature_file_ids
        try:
            sig_ids = json.loads(signature_file_ids)
        except json.JSONDecodeError:
            sig_ids = [int(x.strip()) for x in signature_file_ids.split(",") if x.strip()]
        
        # 创建请求对象
        req = AnalysisCreateRequest(
            name=name,
            language=language,
            code_path=temp_dir,
            signature_file_ids=sig_ids,
            project_key=project_key,
        )
        
        # 执行分析（允许临时目录）
        service = AnalysisService(db)
        result = await service.create_and_run(req, user_id, allow_temp=True)
        logger.info("Analysis created with uploaded files by user %d: %s", user_id, name)
        
        return ApiResponse(data=result)
    
    except Exception as e:
        logger.error("Failed to create analysis with upload: %s", str(e))
        raise
    finally:
        # 分析完成后清理临时目录
        try:
            shutil.rmtree(temp_dir)
            logger.info("Cleaned up temp directory: %s", temp_dir)
        except Exception as e:
            logger.warning("Failed to cleanup temp dir %s: %s", temp_dir, e)


@router.get("/{task_id}", response_model=ApiResponse[AnalysisDetailDTO])
async def get_analysis(
    task_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    service = AnalysisService(db)
    result = await service.get_analysis_detail(task_id)
    return ApiResponse(data=result)


@router.get("/{task_id}/report")
async def get_report(
    task_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    service = AnalysisService(db)
    report = await service.get_report_json(task_id)
    return JSONResponse(content=report)


@router.delete("/{task_id}", response_model=ApiResponse)
async def delete_analysis(
    task_id: int,
    admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    service = AnalysisService(db)
    deleted = await service.delete_analysis(task_id)
    if not deleted:
        return ApiResponse(code=404, message="Analysis not found")
    logger.info("Analysis deleted by admin %s: id=%d", admin.username, task_id)
    return ApiResponse(message="Deleted successfully")
