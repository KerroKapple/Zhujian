"""施工图处理 API：上传/列表/状态/结果/实体/删除/重处理。

路由层仅做入参校验 + 调 DrawingService + 返回；列表返回 Page；错误经 core.exceptions；
依赖缺失时 service 返回 degraded 语义。
"""
from enum import Enum
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile

from app.schemas.common import Page
from core.deps import get_drawing_service
from services.drawing.drawing_service import DrawingService

router = APIRouter()


class DrawingType(str, Enum):
    STRUCTURAL = "structural"
    ARCHITECTURAL = "architectural"
    MEP = "mep"
    OTHER = "other"


@router.post("/upload", summary="上传施工图", description="上传施工图 PDF 并触发解析处理")
async def upload_drawing(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="施工图PDF文件"),
    project_id: Optional[str] = Query(None, description="关联项目ID"),
    drawing_type: DrawingType = Query(DrawingType.OTHER, description="图纸类型"),
    enable_ocr: bool = Query(True, description="是否启用OCR"),
    sync_to_neo4j: bool = Query(True, description="是否同步到知识图谱"),
    service: DrawingService = Depends(get_drawing_service),
) -> dict[str, Any]:
    content = await file.read()
    info = service.upload(
        filename=file.filename,
        content=content,
        project_id=project_id,
        drawing_type=drawing_type.value,
        enable_ocr=enable_ocr,
        sync_to_neo4j=sync_to_neo4j,
    )
    background_tasks.add_task(service.process, info["document_id"])
    return info


@router.get("/list", response_model=Page, summary="施工图列表", description="分页获取施工图处理列表")
async def list_drawings(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="状态筛选"),
    project_id: Optional[str] = Query(None, description="项目ID筛选"),
    service: DrawingService = Depends(get_drawing_service),
) -> Page:
    data = service.list(page=page, page_size=page_size, status=status, project_id=project_id)
    return Page(**data)


@router.get("/{document_id}/status", summary="查询处理状态", description="查询施工图处理进度和状态")
async def get_processing_status(
    document_id: str,
    service: DrawingService = Depends(get_drawing_service),
) -> dict[str, Any]:
    return service.get_status(document_id)


@router.get("/{document_id}/result", summary="获取处理结果", description="获取施工图处理的完整结果")
async def get_processing_result(
    document_id: str,
    service: DrawingService = Depends(get_drawing_service),
) -> dict[str, Any]:
    return service.get_result(document_id)


@router.get("/{document_id}/entities", summary="获取提取的实体", description="获取施工图中提取的实体和关系")
async def get_drawing_entities(
    document_id: str,
    entity_type: Optional[str] = Query(None, description="筛选实体类型: components/materials/dimensions/specifications"),
    service: DrawingService = Depends(get_drawing_service),
) -> dict[str, Any]:
    return service.get_entities(document_id, entity_type=entity_type)


@router.post("/{document_id}/reprocess", summary="重新处理", description="清除旧结果并重新处理施工图")
async def reprocess_drawing(
    document_id: str,
    background_tasks: BackgroundTasks,
    enable_ocr: bool = Query(True, description="是否启用OCR"),
    sync_to_neo4j: bool = Query(True, description="是否同步到知识图谱"),
    service: DrawingService = Depends(get_drawing_service),
) -> dict[str, Any]:
    info = service.reprocess(document_id, enable_ocr=enable_ocr, sync_to_neo4j=sync_to_neo4j)
    background_tasks.add_task(service.process, document_id)
    return info


@router.delete("/{document_id}", summary="删除施工图", description="删除施工图及其关联的知识图谱数据")
async def delete_drawing(
    document_id: str,
    service: DrawingService = Depends(get_drawing_service),
) -> dict[str, Any]:
    return service.delete(document_id)
