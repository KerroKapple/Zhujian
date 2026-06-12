"""统一领域异常与异常处理器。

错误体契约：{"success": false, "error": {"code", "message", "detail"}}。
"""
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from core.config import settings
from core.logger import logger


class AppException(Exception):
    """应用领域异常基类。code 为业务错误码，http_status 为响应状态码。"""

    code: str = "app_error"
    http_status: int = 400

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        http_status: int | None = None,
        detail: Any = None,
    ) -> None:
        self.message = message
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status
        self.detail = detail
        super().__init__(message)


class NotFoundError(AppException):
    code = "not_found"
    http_status = 404


class ValidationError(AppException):
    code = "validation_error"
    http_status = 422


class ServiceUnavailableError(AppException):
    code = "service_unavailable"
    http_status = 503


class UnauthorizedError(AppException):
    code = "unauthorized"
    http_status = 401


class ConflictError(AppException):
    code = "conflict"
    http_status = 409


class ForbiddenError(AppException):
    code = "forbidden"
    http_status = 403


def _error_body(code: str, message: str, detail: Any = None) -> dict[str, Any]:
    return {"success": False, "error": {"code": code, "message": message, "detail": detail}}


def register_exception_handlers(app: FastAPI) -> None:
    """注册统一异常处理器，将异常映射为统一错误体。"""

    @app.exception_handler(AppException)
    async def _handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content=_error_body(exc.code, exc.message, exc.detail),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_error_body("validation_error", "请求参数校验失败", exc.errors()),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.error(f"未处理异常: {exc}", exc_info=True)
        # 生产环境隐藏堆栈，开发环境带 detail 便于排查
        detail = None if settings.ENVIRONMENT == "production" else str(exc)
        return JSONResponse(
            status_code=500,
            content=_error_body("internal_error", "服务器内部错误", detail),
        )
