import logging
import traceback

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from app.schemas.common import ApiResponse

logger = logging.getLogger(__name__)


class BusinessException(Exception):
    def __init__(self, message: str, code: int = 400):
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundException(BusinessException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, code=404)


class UnauthorizedException(BusinessException):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, code=401)


class ForbiddenException(BusinessException):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, code=403)


def register_exception_handlers(app: FastAPI):
    @app.exception_handler(BusinessException)
    async def business_exception_handler(request: Request, exc: BusinessException):
        logger.warning("Business error: %s (path=%s)", exc.message, request.url.path)
        return JSONResponse(
            status_code=exc.code,
            content=ApiResponse(code=exc.code, message=exc.message, data=None).model_dump(),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        logger.warning("HTTP error %d: %s (path=%s)", exc.status_code, exc.detail, request.url.path)
        return JSONResponse(
            status_code=exc.status_code,
            content=ApiResponse(code=exc.status_code, message=str(exc.detail), data=None).model_dump(),
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        logger.warning("Validation error: %s (path=%s)", str(exc), request.url.path)
        return JSONResponse(
            status_code=400,
            content=ApiResponse(code=400, message=str(exc), data=None).model_dump(),
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(
            "Unhandled error: %s (path=%s)\n%s",
            str(exc), request.url.path, traceback.format_exc(),
        )
        return JSONResponse(
            status_code=500,
            content=ApiResponse(code=500, message="Internal server error", data=None).model_dump(),
        )
