"""通用 API Schema：分页、错误体、成功体。Pydantic2 写法。"""
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """统一分页响应。"""

    items: list[T]
    total: int
    page: int
    page_size: int


class ErrorDetail(BaseModel):
    code: str
    message: str
    detail: Any = None


class ErrorResponse(BaseModel):
    """统一错误体。"""

    success: bool = False
    error: ErrorDetail


class OkResponse(BaseModel):
    """统一成功体（动作类接口）。"""

    success: bool = True
    message: str | None = None
