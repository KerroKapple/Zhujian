"""系统管理域服务：真实系统指标、组件健康探测、真实计数与运维操作；缺依赖优雅降级。"""
import os
import time
from datetime import datetime, timezone
from typing import Any, Optional

import psutil
from sqlalchemy.orm import Session

from core.config import settings
from core.exceptions import ServiceUnavailableError
from core.logger import logger

# 进程级运行时长锚点：模块导入即进程启动近似时刻
_PROCESS = psutil.Process(os.getpid())


def _now_iso() -> str:
    """时区感知 ISO 时间戳。"""
    return datetime.now(timezone.utc).isoformat()


class AdminService:
    """系统管理业务编排：构造注入 db，方法返回 DTO/dict。

    统计类失败 → 单项标 degraded 不编造；破坏性/运维操作缺依赖 → 抛 ServiceUnavailableError。
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # =========================================
    # 系统状态（psutil 真实指标）
    # =========================================

    def system_status(self) -> dict:
        """CPU/内存/磁盘真实占用 + 进程运行时长。"""
        cpu_percent = psutil.cpu_percent(interval=0.5)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(os.getcwd())  # 用当前工作目录锚定盘符
        uptime = max(0.0, time.time() - _PROCESS.create_time())
        return {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "disk_percent": disk.percent,
            "uptime": uptime,
            "timestamp": _now_iso(),
        }

    # =========================================
    # 健康探测（逐组件 try/except）
    # =========================================

    def health(self) -> dict:
        """逐个探测 Redis/PostgreSQL/Milvus/Neo4j，返回每组件 ok/down。"""
        components = {
            "database": self._probe(self._probe_postgres),
            "redis": self._probe(self._probe_redis),
            "vector_db": self._probe(self._probe_milvus),
            "graph_db": self._probe(self._probe_neo4j),
        }
        overall = "healthy" if all(c["ok"] for c in components.values()) else "degraded"
        return {"status": overall, "timestamp": _now_iso(), "components": components}

    @staticmethod
    def _probe(fn) -> dict:
        """单组件探测包装：捕获异常归一为 ok/down。"""
        try:
            ok = bool(fn())
        except Exception as e:  # noqa: BLE001
            logger.warning(f"组件健康探测失败: {e}")
            return {"ok": False, "status": "down", "detail": str(e)}
        return {"ok": ok, "status": "up" if ok else "down"}

    @staticmethod
    def _probe_postgres() -> bool:
        from core.database import check_db_connection

        return check_db_connection()

    @staticmethod
    def _probe_redis() -> bool:
        from services.cache.redis_client import redis_client

        return redis_client.ping()

    @staticmethod
    def _probe_milvus() -> bool:
        from services.retrieval.vector.milvus_client import milvus_client

        milvus_client.ensure_connected()
        return milvus_client.is_connected()

    @staticmethod
    def _probe_neo4j() -> bool:
        from services.graph.neo4j_client import NEO4J_AVAILABLE, neo4j_client

        return NEO4J_AVAILABLE and neo4j_client.ping()

    # =========================================
    # 索引统计（真实计数 / DB 不可用降级）
    # =========================================

    def index_stats(self) -> dict:
        """文档/分块真实计数；DB 不可用则标 degraded 不编造。"""
        try:
            from repository.document_repo import DocumentRepository

            repo = DocumentRepository(self.db)
            stats = repo.get_statistics()
            return {
                "degraded": False,
                "total_documents": stats.get("total_documents", 0),
                "total_chunks": stats.get("total_chunks", 0),
                "vector_dimension": settings.VECTOR_DIM,
                "by_type": stats.get("by_type", {}),
                "by_status": stats.get("by_status", {}),
                "last_updated": _now_iso(),
            }
        except Exception as e:  # noqa: BLE001
            logger.warning(f"索引统计降级（DB 不可用）: {e}")
            return {
                "degraded": True,
                "reason": "数据库不可用",
                "total_documents": None,
                "total_chunks": None,
                "vector_dimension": settings.VECTOR_DIM,
                "last_updated": None,
            }

    # =========================================
    # 数据统计（真实查询日志计数 / 降级）
    # =========================================

    def statistics(self, days: int = 7) -> dict:
        """近 N 天查询统计：总量/成功率/平均耗时/热门问题；DB 不可用降级。"""
        try:
            from repository.document_repo import DocumentRepository
            from repository.query_log_repo import QueryLogRepository

            doc_repo = DocumentRepository(self.db)
            log_repo = QueryLogRepository(self.db)

            qstats = log_repo.get_query_statistics()
            total = qstats.get("total_queries", 0)
            success = qstats.get("successful_queries", 0)
            success_rate = (success / total) if total else 0.0

            hot = log_repo.get_hot_queries(limit=10, days=days)
            popular = [{"query": q, "count": c} for q, c in hot]

            return {
                "degraded": False,
                "days": days,
                "total_queries": total,
                "total_documents": doc_repo.count_documents(),
                "avg_response_time": round(qstats.get("avg_total_time", 0.0), 3),
                "success_rate": round(success_rate, 4),
                "popular_queries": popular,
            }
        except Exception as e:  # noqa: BLE001
            logger.warning(f"数据统计降级（DB 不可用）: {e}")
            return {
                "degraded": True,
                "reason": "数据库不可用",
                "days": days,
                "total_queries": None,
                "total_documents": None,
                "avg_response_time": None,
                "success_rate": None,
                "popular_queries": [],
            }

    # =========================================
    # 缓存
    # =========================================

    def cache_stats(self) -> dict:
        """Redis 真实运行信息；不可用降级。"""
        try:
            from services.cache.redis_client import redis_client

            if not redis_client.ping():
                raise RuntimeError("Redis 未连接")
            info = redis_client.get_info()
            return {"degraded": False, **info}
        except Exception as e:  # noqa: BLE001
            logger.warning(f"缓存统计降级: {e}")
            return {"degraded": True, "reason": "Redis 不可用"}

    def clear_cache(self, pattern: Optional[str] = None) -> dict:
        """按模式清理 Redis 键；缺 Redis → 503。"""
        try:
            from services.cache.redis_client import redis_client

            if not redis_client.ping():
                raise RuntimeError("Redis 未连接")
        except Exception as e:  # noqa: BLE001
            raise ServiceUnavailableError("Redis 服务不可用，无法清理缓存", detail=str(e))

        if pattern:
            deleted = redis_client.delete_pattern(pattern)
        else:
            # 无模式时清空当前 db（仅作用于配置库）
            redis_client.clear_all()
            deleted = None
        logger.info(f"缓存清理完成 | 模式: {pattern} | 删除: {deleted}")
        return {"success": True, "pattern": pattern, "deleted_keys": deleted}

    # =========================================
    # 索引重建（真实触发 / 缺依赖 503）
    # =========================================

    def rebuild_index(self, drop_existing: bool = False) -> dict:
        """触发真实全量重建（BM25 + 向量）；缺重型依赖或外部服务 → 503。"""
        try:
            from scripts.rebuild_index import IndexRebuilder
        except Exception as e:  # noqa: BLE001
            raise ServiceUnavailableError("索引重建依赖缺失（向量/检索层未就绪）", detail=str(e))

        rebuilder = None
        try:
            rebuilder = IndexRebuilder()
            ok = rebuilder.rebuild_all(drop_existing=drop_existing)
            return {"success": ok, "stats": rebuilder.stats, "timestamp": _now_iso()}
        except Exception as e:  # noqa: BLE001
            logger.error(f"索引重建失败: {e}", exc_info=True)
            raise ServiceUnavailableError("索引重建执行失败（依赖服务不可用）", detail=str(e))
        finally:
            if rebuilder is not None:
                rebuilder.close()

    # =========================================
    # 配置
    # =========================================

    def config(self) -> dict:
        """系统配置（敏感信息不外露）。"""
        return {
            "app_name": settings.APP_NAME,
            "app_version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "debug": settings.DEBUG,
            "llm_model": settings.LLM_MODEL_NAME,
            "embedding_model": settings.EMBEDDING_MODEL_NAME,
            "vector_dimension": settings.VECTOR_DIM,
        }
