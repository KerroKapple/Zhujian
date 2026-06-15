"""文档域服务：上传/列表/详情/状态/删除，全部经 DocumentRepository 真实落库。

DB 不可用时抛 ServiceUnavailableError；不返回假数据。
"""
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.config import settings
from core.constants import DocumentStatus, DocumentType
from core.exceptions import NotFoundError, ServiceUnavailableError, ValidationError
from core.logger import logger
from repository.document_repo import DocumentRepository

# 允许的上传格式 -> 业务文档类型
_EXT_TO_TYPE = {
    ".pdf": DocumentType.PDF,
    ".docx": DocumentType.WORD,
    ".doc": DocumentType.WORD,
    ".txt": DocumentType.TEXT,
    ".md": DocumentType.TEXT,
}
_MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB


class DocumentService:
    """文档业务编排，依赖注入 DB 会话与 Repository。"""

    def __init__(self, db: Session):
        self.db = db
        self.repo = DocumentRepository(db)

    # ============ 列表/详情/状态 ============

    def list(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        category: Optional[str] = None,
    ) -> dict[str, Any]:
        """真实分页列表，返回 Page 形 {items,total,page,page_size}。"""
        status_enum = self._parse_status(status)
        type_enum = self._parse_category(category)
        skip = (page - 1) * page_size
        try:
            docs = self.repo.list_documents(
                doc_type=type_enum,
                status=status_enum,
                skip=skip,
                limit=page_size,
            )
            total = self.repo.count_documents(doc_type=type_enum, status=status_enum)
        except SQLAlchemyError as e:
            raise ServiceUnavailableError("数据库不可用", detail=str(e)) from e

        return {
            "items": [self._to_info(d) for d in docs],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_detail(self, doc_id: str) -> dict[str, Any]:
        """文档详情，不存在抛 NotFoundError。"""
        doc = self._require(doc_id)
        return self._to_info(doc)

    def get_status(self, doc_id: str) -> dict[str, Any]:
        """文档处理状态与进度。"""
        doc = self._require(doc_id)
        status = doc.status.value if doc.status else DocumentStatus.PENDING.value
        progress = {
            DocumentStatus.PENDING.value: 0.0,
            DocumentStatus.PROCESSING.value: 50.0,
            DocumentStatus.COMPLETED.value: 100.0,
            DocumentStatus.FAILED.value: 0.0,
        }.get(status, 0.0)
        return {
            "doc_id": doc.id,
            "status": status,
            "progress": progress,
            "message": doc.status_message or "",
        }

    # ============ 上传/删除 ============

    def upload(
        self,
        *,
        filename: str,
        content: bytes,
        category: Optional[str] = None,
    ) -> dict[str, Any]:
        """落库 + 触发处理排队。返回新文档信息。"""
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext not in _EXT_TO_TYPE:
            raise ValidationError(
                f"不支持的文件格式: {file_ext}", detail=sorted(_EXT_TO_TYPE.keys())
            )
        if len(content) > _MAX_UPLOAD_SIZE:
            raise ValidationError(f"文件过大，限制 {_MAX_UPLOAD_SIZE // 1024 // 1024}MB")

        doc_id = str(uuid.uuid4())
        upload_dir = settings.DATA_DIR / "raw_docs"
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / f"{doc_id}_{filename}"
        file_path.write_bytes(content)

        type_enum = _EXT_TO_TYPE[file_ext]
        try:
            doc = self.repo.create_document(
                name=filename,
                doc_type=type_enum,
                source_path=str(file_path),
                id=doc_id,
                file_size=len(content),
                file_extension=file_ext,
                status=DocumentStatus.PENDING,
                extra_metadata={"category": category} if category else None,
            )
        except SQLAlchemyError as e:
            # 落库失败：清理已写入文件，避免孤儿文件
            file_path.unlink(missing_ok=True)
            raise ServiceUnavailableError("数据库不可用", detail=str(e)) from e

        self._enqueue_processing(doc.id)
        info = self._to_info(doc)
        info["message"] = "文档上传成功，已排队处理"
        return info

    def delete(self, doc_id: str) -> dict[str, Any]:
        """删除文档（级联 chunks/metadata）+ 原始文件。"""
        doc = self._require(doc_id)
        source_path = doc.source_path
        try:
            self.repo.delete_document(doc_id)
        except SQLAlchemyError as e:
            raise ServiceUnavailableError("数据库不可用", detail=str(e)) from e
        self._remove_file(source_path)
        return {"success": True, "doc_id": doc_id, "message": "文档删除成功"}

    def batch_delete(self, doc_ids: list[str]) -> dict[str, Any]:
        """批量删除，逐个记录结果。"""
        results = []
        for doc_id in doc_ids:
            try:
                self.delete(doc_id)
                results.append({"doc_id": doc_id, "success": True})
            except NotFoundError:
                results.append({"doc_id": doc_id, "success": False, "error": "文档不存在"})
        success_count = sum(1 for r in results if r["success"])
        return {
            "total": len(doc_ids),
            "success_count": success_count,
            "failed_count": len(doc_ids) - success_count,
            "results": results,
        }

    # ============ 内部工具 ============

    def _require(self, doc_id: str):
        try:
            doc = self.repo.get_document_by_id(doc_id)
        except SQLAlchemyError as e:
            raise ServiceUnavailableError("数据库不可用", detail=str(e)) from e
        if not doc:
            raise NotFoundError(f"文档不存在: {doc_id}")
        return doc

    def _enqueue_processing(self, doc_id: str) -> None:
        """触发/排队后处理。当前置为 pending，由后台流水线消费。"""
        # 暂无独立任务队列：标记 pending，处理流水线由 loader/splitter 异步消费。
        logger.info(f"文档已排队处理: {doc_id}")

    @staticmethod
    def _remove_file(path: Optional[str]) -> None:
        if path and Path(path).exists():
            try:
                Path(path).unlink()
            except OSError as e:
                logger.warning(f"删除原始文件失败: {path} | {e}")

    @staticmethod
    def _parse_status(status: Optional[str]) -> Optional[DocumentStatus]:
        if not status:
            return None
        try:
            return DocumentStatus(status)
        except ValueError as e:
            raise ValidationError(f"非法状态: {status}") from e

    @staticmethod
    def _parse_category(category: Optional[str]) -> Optional[DocumentType]:
        if not category:
            return None
        try:
            return DocumentType(category)
        except ValueError:
            # category 非业务类型时不作类型过滤（透传保存于 metadata）
            return None

    @staticmethod
    def _to_info(doc) -> dict[str, Any]:
        return {
            "doc_id": doc.id,
            "filename": doc.name,
            "file_type": doc.doc_type.value if doc.doc_type else "",
            "file_size": doc.file_size or 0,
            "status": doc.status.value if doc.status else DocumentStatus.PENDING.value,
            "uploaded_at": doc.created_at.isoformat() if doc.created_at else None,
            "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
            "metadata": doc.extra_metadata or {},
        }
