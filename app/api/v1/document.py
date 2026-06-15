"""文档管理 API：上传/列表/详情/状态/删除/批量删除。

路由层仅做入参校验 + 调 DocumentService + 返回；列表返回 Page；错误经 core.exceptions。
"""
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, File, Query, UploadFile

from app.schemas.common import Page
from core.deps import get_document_service
from services.document.document_service import DocumentService

router = APIRouter()


@router.post("/upload", summary="上传文档", description="上传单个文档到知识库")
async def upload_document(
    file: UploadFile = File(..., description="上传的文件"),
    category: Optional[str] = Query(None, description="文档分类"),
    service: DocumentService = Depends(get_document_service),
) -> dict[str, Any]:
    content = await file.read()
    return service.upload(filename=file.filename, content=content, category=category)


@router.post("/upload/batch", summary="批量上传", description="批量上传多个文档")
async def upload_documents_batch(
    files: list[UploadFile] = File(..., description="上传的文件列表"),
    category: Optional[str] = Query(None, description="文档分类"),
    service: DocumentService = Depends(get_document_service),
) -> dict[str, Any]:
    results = []
    for file in files:
        content = await file.read()
        info = service.upload(filename=file.filename, content=content, category=category)
        results.append({"filename": file.filename, "doc_id": info["doc_id"]})
    return {"total": len(files), "success_count": len(results), "results": results}


@router.get("/list", response_model=Page, summary="文档列表", description="分页获取文档列表")
async def list_documents(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    category: Optional[str] = Query(None, description="文档分类"),
    status: Optional[str] = Query(None, description="处理状态"),
    service: DocumentService = Depends(get_document_service),
) -> Page:
    data = service.list(page=page, page_size=page_size, category=category, status=status)
    return Page(**data)


@router.get("/{doc_id}", summary="文档详情", description="获取单个文档详细信息")
async def get_document(
    doc_id: str,
    service: DocumentService = Depends(get_document_service),
) -> dict[str, Any]:
    return service.get_detail(doc_id)


@router.get("/{doc_id}/status", summary="处理状态", description="查询文档处理状态")
async def get_document_status(
    doc_id: str,
    service: DocumentService = Depends(get_document_service),
) -> dict[str, Any]:
    return service.get_status(doc_id)


@router.delete("/{doc_id}", summary="删除文档", description="从知识库删除文档")
async def delete_document(
    doc_id: str,
    service: DocumentService = Depends(get_document_service),
) -> dict[str, Any]:
    return service.delete(doc_id)


@router.post("/delete/batch", summary="批量删除", description="批量删除多个文档")
async def delete_documents_batch(
    doc_ids: list[str] = Body(..., embed=True, description="文档ID列表"),
    service: DocumentService = Depends(get_document_service),
) -> dict[str, Any]:
    return service.batch_delete(doc_ids)
