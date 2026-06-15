"""系统管理 API：仅做入参校验 + 调 AdminService + 返回；错误经 core.exceptions。"""
import os
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query

from core.config import settings
from core.deps import get_admin_service
from core.exceptions import UnauthorizedError
from core.logger import logger

router = APIRouter()


# =========================================
# 破坏性端点的可选鉴权开关
# =========================================

async def require_admin_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> None:
    """破坏性操作（清缓存/重建索引）鉴权。

    仅当 settings.ENABLE_PERMISSION_CHECK 为 True 且配置了 ADMIN_API_KEY 时校验；
    开关开启但未配置密钥则放行并告警，避免阻断联调。
    """
    if not settings.ENABLE_PERMISSION_CHECK:
        return
    expected = os.environ.get("ADMIN_API_KEY")
    if not expected:
        logger.warning("ENABLE_PERMISSION_CHECK 已开启但未配置 ADMIN_API_KEY，破坏性端点暂未鉴权")
        return
    if x_api_key != expected:
        raise UnauthorizedError("缺少或无效的 API Key")


# =========================================
# 系统状态 / 健康
# =========================================

@router.get("/status", summary="系统状态", description="CPU/内存/磁盘真实占用与运行时长")
async def get_system_status(service=Depends(get_admin_service)) -> dict:
    return service.system_status()


@router.get("/health", summary="健康检查", description="逐组件探测 Redis/PostgreSQL/Milvus/Neo4j")
async def health_check(service=Depends(get_admin_service)) -> dict:
    return service.health()


# =========================================
# 索引
# =========================================

@router.get("/index/stats", summary="索引统计", description="文档/分块真实计数，DB 不可用降级")
async def get_index_stats(service=Depends(get_admin_service)) -> dict:
    return service.index_stats()


@router.post("/index/rebuild", summary="重建索引", description="触发真实全量重建，缺依赖 503")
async def rebuild_index(
    drop_existing: bool = Query(False, description="是否删除现有数据后重建"),
    _: None = Depends(require_admin_key),
    service=Depends(get_admin_service),
) -> dict:
    return service.rebuild_index(drop_existing=drop_existing)


# =========================================
# 缓存
# =========================================

@router.get("/cache/stats", summary="缓存统计", description="Redis 真实运行信息，不可用降级")
async def get_cache_stats(service=Depends(get_admin_service)) -> dict:
    return service.cache_stats()


@router.post("/cache/clear", summary="清理缓存", description="按模式清理 Redis 键，缺 Redis 503")
async def clear_cache(
    pattern: Optional[str] = Query(None, description="缓存键模式，如 qa:*"),
    _: None = Depends(require_admin_key),
    service=Depends(get_admin_service),
) -> dict:
    return service.clear_cache(pattern=pattern)


# =========================================
# 数据统计 / 配置
# =========================================

@router.get("/statistics", summary="数据统计", description="近 N 天查询统计，真实来源，DB 不可用降级")
async def get_statistics(
    days: int = Query(7, ge=1, le=365, description="统计天数"),
    service=Depends(get_admin_service),
) -> dict:
    return service.statistics(days=days)


@router.get("/config", summary="系统配置", description="当前系统配置（敏感信息不外露）")
async def get_config(service=Depends(get_admin_service)) -> dict:
    return service.config()
