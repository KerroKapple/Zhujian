"""施工图域服务：上传/列表/状态/结果/实体/删除/重处理。

处理状态优先持久化到 Redis（多 worker 共享），Redis 不可用时降级为进程内存 dict
并告警（保留单进程可用）。施工图解析依赖（PDF/OCR/CV）缺失时 degraded，绝不假数据。
"""
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from core.config import settings
from core.exceptions import ConflictError, NotFoundError, ValidationError
from core.logger import logger

# 处理状态值
_PENDING = "pending"
_PARSING = "parsing"
_EXTRACTING = "extracting"
_SYNCING = "syncing"
_COMPLETED = "completed"
_FAILED = "failed"
_DEGRADED = "degraded"
_RUNNING = {_PARSING, _EXTRACTING, _SYNCING}

_TASK_PREFIX = "drawing:task:"
_RESULT_PREFIX = "drawing:result:"
_INDEX_KEY = "drawing:index"
_STATE_TTL = 7 * 24 * 3600  # 状态保留 7 天

_MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100MB

# 进程内存兜底（Redis 不可用时单进程可用）
_MEM_TASKS: dict[str, dict] = {}
_MEM_RESULTS: dict[str, dict] = {}
_MEM_INDEX: set[str] = set()


class _StateStore:
    """处理状态存储：Redis-first，失败降级进程内存并告警。"""

    def __init__(self):
        self._redis = None
        self._warned = False
        try:
            from services.cache.redis_client import redis_client

            if redis_client.ping():
                self._redis = redis_client
        except Exception as e:  # Redis 模块/连接异常
            logger.warning(f"Redis 不可用，施工图处理状态降级为进程内存: {e}")

    @property
    def persistent(self) -> bool:
        return self._redis is not None

    def _warn_once(self):
        if not self._warned:
            logger.warning("施工图处理状态使用进程内存兜底（多 worker 不共享，重启丢失）")
            self._warned = True

    def set_task(self, doc_id: str, task: dict) -> None:
        if self._redis:
            self._redis.set(f"{_TASK_PREFIX}{doc_id}", task, expire=_STATE_TTL)
            self._redis.get_client().sadd(_INDEX_KEY, doc_id)
        else:
            self._warn_once()
            _MEM_TASKS[doc_id] = task
            _MEM_INDEX.add(doc_id)

    def get_task(self, doc_id: str) -> Optional[dict]:
        if self._redis:
            return self._redis.get(f"{_TASK_PREFIX}{doc_id}")
        return _MEM_TASKS.get(doc_id)

    def del_task(self, doc_id: str) -> None:
        if self._redis:
            self._redis.delete(f"{_TASK_PREFIX}{doc_id}")
            self._redis.delete(f"{_RESULT_PREFIX}{doc_id}")
            self._redis.get_client().srem(_INDEX_KEY, doc_id)
        else:
            _MEM_TASKS.pop(doc_id, None)
            _MEM_RESULTS.pop(doc_id, None)
            _MEM_INDEX.discard(doc_id)

    def set_result(self, doc_id: str, result: dict) -> None:
        if self._redis:
            self._redis.set(f"{_RESULT_PREFIX}{doc_id}", result, expire=_STATE_TTL)
        else:
            _MEM_RESULTS[doc_id] = result

    def get_result(self, doc_id: str) -> Optional[dict]:
        if self._redis:
            return self._redis.get(f"{_RESULT_PREFIX}{doc_id}")
        return _MEM_RESULTS.get(doc_id)

    def del_result(self, doc_id: str) -> None:
        if self._redis:
            self._redis.delete(f"{_RESULT_PREFIX}{doc_id}")
        else:
            _MEM_RESULTS.pop(doc_id, None)

    def all_ids(self) -> list[str]:
        if self._redis:
            ids = self._redis.get_client().smembers(_INDEX_KEY)
            return sorted(ids)
        return sorted(_MEM_INDEX)


class DrawingService:
    """施工图业务编排，依赖注入 DB 会话（图谱走 GraphRepository）。"""

    def __init__(self, db: Session):
        self.db = db
        self.store = _StateStore()

    # ============ 列表/状态/结果/实体 ============

    def list(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """处理列表，返回 Page 形 {items,total,page,page_size}。"""
        items = []
        for doc_id in self.store.all_ids():
            task = self.store.get_task(doc_id)
            if not task:
                continue
            if status and task.get("status") != status:
                continue
            if project_id and task.get("project_id") != project_id:
                continue
            items.append(self._to_list_item(doc_id, task))

        items.sort(key=lambda x: x.get("started_at") or "", reverse=True)
        total = len(items)
        start = (page - 1) * page_size
        return {
            "items": items[start : start + page_size],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_status(self, doc_id: str) -> dict[str, Any]:
        """处理进度与状态。"""
        task = self._require_task(doc_id)
        return {
            "document_id": doc_id,
            "status": task.get("status", _PENDING),
            "progress": task.get("progress", 0.0),
            "current_step": task.get("current_step", ""),
            "steps": task.get("steps", []),
            "error_message": task.get("error_message"),
            "degraded": task.get("status") == _DEGRADED,
            "started_at": task.get("started_at"),
            "completed_at": task.get("completed_at"),
        }

    def get_result(self, doc_id: str) -> dict[str, Any]:
        """完整处理结果，未完成抛 ConflictError。"""
        task = self._require_task(doc_id)
        if task.get("status") != _COMPLETED:
            raise ConflictError(f"文档尚未处理完成，当前状态: {task.get('status')}")
        result = self.store.get_result(doc_id)
        if not result:
            raise NotFoundError(f"处理结果不存在: {doc_id}")
        return {
            "success": result.get("success", False),
            "document_id": doc_id,
            "filename": task.get("filename", ""),
            "drawing_info": result.get("drawing_info") or None,
            "entities_count": result.get("entities_count", 0),
            "relations_count": result.get("relations_count", 0),
            "neo4j_synced": result.get("neo4j_synced", False),
            "processing_time_ms": result.get("processing_time_ms", 0),
            "steps": result.get("steps", []),
        }

    def get_entities(
        self, doc_id: str, *, entity_type: Optional[str] = None
    ) -> dict[str, Any]:
        """从知识图谱查询实体与关系。图谱不可用时 degraded 空结果。"""
        self._require_task(doc_id)
        entities = {
            "components": [],
            "materials": [],
            "dimensions": [],
            "specifications": [],
        }
        relations: list[dict] = []
        degraded = False

        try:
            from repository.graph_repo import GraphRepository

            graph = GraphRepository().get_document_graph(doc_id)
            label_to_key = {
                "Component": "components",
                "Material": "materials",
                "Dimension": "dimensions",
                "Specification": "specifications",
            }
            for node in graph.get("nodes", []):
                if not node:
                    continue
                key = label_to_key.get(node.get("label"))
                if not key:
                    continue
                if entity_type and key != entity_type and key != f"{entity_type}s":
                    continue
                item = dict(node.get("properties", {}))
                item.setdefault("id", node.get("id"))
                entities[key].append(item)
            for rel in graph.get("relationships", []):
                if not rel:
                    continue
                relations.append(
                    {
                        "id": rel.get("id"),
                        "type": rel.get("type"),
                        "from_node_id": rel.get("from_node_id"),
                        "to_node_id": rel.get("to_node_id"),
                        "properties": rel.get("properties", {}),
                    }
                )
        except Exception as e:
            # 图谱（Neo4j）不可用：降级为空结果并标注，不假数据
            logger.warning(f"知识图谱不可用，实体查询降级: {e}")
            degraded = True

        result = self.store.get_result(doc_id) or {}
        return {
            "document_id": doc_id,
            "drawing_info": result.get("drawing_info") or None,
            "entities": entities,
            "relations": relations,
            "summary": {
                "components": len(entities["components"]),
                "materials": len(entities["materials"]),
                "dimensions": len(entities["dimensions"]),
                "specifications": len(entities["specifications"]),
            },
            "degraded": degraded,
        }

    # ============ 上传/重处理/删除 ============

    def upload(
        self,
        *,
        filename: str,
        content: bytes,
        project_id: Optional[str] = None,
        drawing_type: str = "other",
        enable_ocr: bool = True,
        sync_to_neo4j: bool = True,
    ) -> dict[str, Any]:
        """保存文件 + 初始化状态。返回 document_id 供路由排队后台处理。"""
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext != ".pdf":
            raise ValidationError(f"施工图仅支持 PDF 格式，收到: {file_ext}")
        if len(content) > _MAX_UPLOAD_SIZE:
            raise ValidationError(f"文件过大，限制 {_MAX_UPLOAD_SIZE // 1024 // 1024}MB")

        document_id = f"drawing_{uuid.uuid4().hex[:12]}"
        upload_dir = settings.DATA_DIR / "raw_docs" / "drawings"
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / f"{document_id}_{filename}"
        file_path.write_bytes(content)

        self.store.set_task(
            document_id,
            {
                "status": _PENDING,
                "progress": 0.0,
                "current_step": "等待处理",
                "steps": [],
                "started_at": _now(),
                "completed_at": None,
                "file_path": str(file_path),
                "filename": filename,
                "project_id": project_id,
                "drawing_type": drawing_type,
                "enable_ocr": enable_ocr,
                "sync_to_neo4j": sync_to_neo4j,
            },
        )

        return {
            "document_id": document_id,
            "filename": filename,
            "message": "施工图上传成功，正在后台处理"
            if self.store.persistent
            else "施工图上传成功，正在后台处理（状态降级为单进程内存）",
            "processing_url": f"/api/v1/drawing/{document_id}/status",
        }

    def reprocess(
        self,
        doc_id: str,
        *,
        enable_ocr: bool = True,
        sync_to_neo4j: bool = True,
    ) -> dict[str, Any]:
        """重置状态并清理旧图谱/结果，返回 document_id 供路由排队。"""
        task = self._require_task(doc_id)
        if task.get("status") in _RUNNING:
            raise ConflictError("文档正在处理中，请稍后再试")
        file_path = task.get("file_path")
        if not file_path or not Path(file_path).exists():
            raise NotFoundError("原始文件不存在，无法重新处理")

        if sync_to_neo4j:
            self._clear_graph(doc_id)

        task.update(
            {
                "status": _PENDING,
                "progress": 0.0,
                "current_step": "等待处理",
                "steps": [],
                "error_message": None,
                "started_at": _now(),
                "completed_at": None,
                "enable_ocr": enable_ocr,
                "sync_to_neo4j": sync_to_neo4j,
            }
        )
        self.store.set_task(doc_id, task)
        self.store.del_result(doc_id)
        return {
            "document_id": doc_id,
            "message": "已开始重新处理",
            "status_url": f"/api/v1/drawing/{doc_id}/status",
        }

    def delete(self, doc_id: str) -> dict[str, Any]:
        """删除原始文件 + 图谱数据 + 处理记录。"""
        task = self._require_task(doc_id)
        self._remove_file(task.get("file_path"))
        self._clear_graph(doc_id)
        self.store.del_task(doc_id)
        return {"success": True, "document_id": doc_id, "message": "施工图删除成功"}

    # ============ 后台处理（由路由 BackgroundTasks 调度） ============

    async def process(self, doc_id: str) -> None:
        """执行解析流水线并写回状态。依赖缺失 → degraded，绝不假数据。"""
        task = self.store.get_task(doc_id)
        if not task:
            logger.warning(f"处理任务不存在，跳过: {doc_id}")
            return

        try:
            from services.document.construction_drawing.drawing_processor import (
                DrawingProcessor,
            )
        except Exception as e:
            self._mark_degraded(doc_id, task, f"施工图解析依赖缺失: {e}")
            return

        def on_progress(progress: float, message: str):
            task["progress"] = progress
            task["current_step"] = message
            if progress < 30:
                task["status"] = _PARSING
            elif progress < 70:
                task["status"] = _EXTRACTING
            elif progress < 100:
                task["status"] = _SYNCING
            self.store.set_task(doc_id, task)

        try:
            processor = DrawingProcessor(
                enable_ocr=task.get("enable_ocr", True),
                use_llm=False,
                sync_to_neo4j=task.get("sync_to_neo4j", True),
            )
            result = await processor.process(
                file_path=task["file_path"],
                document_id=doc_id,
                project_id=task.get("project_id"),
                progress_callback=on_progress,
            )
            result_dict = result.to_dict()
            self.store.set_result(doc_id, result_dict)

            if result.success:
                task["status"] = _COMPLETED
                task["progress"] = 100.0
                task["current_step"] = "处理完成"
            else:
                # 解析失败：区分依赖缺失（degraded）与真实失败
                msg = result.error_message or ""
                if self._is_dependency_error(msg):
                    task["status"] = _DEGRADED
                else:
                    task["status"] = _FAILED
                task["error_message"] = msg
            task["steps"] = result.steps
            task["completed_at"] = _now()
            self.store.set_task(doc_id, task)
            logger.info(f"施工图处理完成: {doc_id} | 成功: {result.success}")
        except Exception as e:
            msg = str(e)
            status = _DEGRADED if self._is_dependency_error(msg) else _FAILED
            task["status"] = status
            task["error_message"] = msg
            task["completed_at"] = _now()
            self.store.set_task(doc_id, task)
            logger.error(f"施工图处理异常: {doc_id} | {e}", exc_info=True)

    # ============ 内部工具 ============

    def _require_task(self, doc_id: str) -> dict:
        task = self.store.get_task(doc_id)
        if not task:
            raise NotFoundError(f"文档不存在: {doc_id}")
        return task

    def _mark_degraded(self, doc_id: str, task: dict, message: str) -> None:
        logger.warning(f"施工图处理降级: {doc_id} | {message}")
        task["status"] = _DEGRADED
        task["error_message"] = message
        task["completed_at"] = _now()
        self.store.set_task(doc_id, task)

    @staticmethod
    def _is_dependency_error(message: str) -> bool:
        """依赖缺失类错误（OCR/CV/PDF 库）判定为 degraded 而非 failed。"""
        keys = ("import", "module", "PyPDF2", "pdfplumber", "OCR", "cv2", "未启用")
        low = message.lower()
        return any(k.lower() in low for k in keys)

    @staticmethod
    def _clear_graph(doc_id: str) -> None:
        try:
            from repository.graph_repo import GraphRepository

            GraphRepository().clear_document_graph(doc_id)
            logger.info(f"已清除图谱数据: {doc_id}")
        except Exception as e:
            logger.warning(f"清除图谱数据失败（图谱不可用）: {e}")

    @staticmethod
    def _remove_file(path: Optional[str]) -> None:
        if path and Path(path).exists():
            try:
                Path(path).unlink()
                logger.info(f"已删除文件: {path}")
            except OSError as e:
                logger.warning(f"删除文件失败: {path} | {e}")

    @staticmethod
    def _to_list_item(doc_id: str, task: dict) -> dict[str, Any]:
        return {
            "document_id": doc_id,
            "filename": task.get("filename", ""),
            "status": task.get("status", _PENDING),
            "progress": task.get("progress", 0.0),
            "project_id": task.get("project_id"),
            "drawing_type": task.get("drawing_type"),
            "started_at": task.get("started_at"),
            "completed_at": task.get("completed_at"),
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
