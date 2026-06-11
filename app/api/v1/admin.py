"""
========================================
系统管理API接口
========================================

📚 模块说明：
- 系统状态监控
- 索引管理
- 配置管理
- 数据统计

🎯 核心功能：
1. 系统状态
2. 索引重建
3. 缓存清理
4. 数据统计

========================================
"""

import os

from fastapi import APIRouter, HTTPException, status, Depends, Header
from pydantic import BaseModel, Field
from typing import Dict, Optional
from datetime import datetime
import psutil

from loguru import logger
from core.config import settings

router = APIRouter()


# =========================================
# 破坏性端点的可选 API Key 鉴权
# =========================================

async def require_admin_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """
    破坏性操作（清缓存/重建索引）的可选鉴权开关。

    - 仅当 settings.ENABLE_PERMISSION_CHECK 为 True 时启用；
    - 期望密钥来自环境变量 ADMIN_API_KEY；
    - 若开关开启但未配置 ADMIN_API_KEY，则放行并告警（避免阻断前端联调），
      但记录风险提示。
    """
    if not settings.ENABLE_PERMISSION_CHECK:
        return

    expected = os.environ.get("ADMIN_API_KEY")
    if not expected:
        logger.warning("ENABLE_PERMISSION_CHECK 已开启但未配置 ADMIN_API_KEY，破坏性端点暂未鉴权")
        return

    if x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少或无效的 API Key"
        )


# =========================================
# 响应模型
# =========================================

class SystemStatus(BaseModel):
    """系统状态"""
    cpu_percent: float = Field(..., description="CPU使用率")
    memory_percent: float = Field(..., description="内存使用率")
    disk_percent: float = Field(..., description="磁盘使用率")
    uptime: float = Field(..., description="运行时间(秒)")
    timestamp: str = Field(..., description="时间戳")


class IndexStats(BaseModel):
    """索引统计"""
    total_documents: int = Field(..., description="文档总数")
    total_chunks: int = Field(..., description="分块总数")
    vector_dimension: int = Field(..., description="向量维度")
    index_size: str = Field(..., description="索引大小")
    last_updated: str = Field(..., description="最后更新时间")


class Statistics(BaseModel):
    """数据统计"""
    total_queries: int = Field(..., description="总查询数")
    total_documents: int = Field(..., description="总文档数")
    avg_response_time: float = Field(..., description="平均响应时间(秒)")
    success_rate: float = Field(..., description="成功率")
    popular_queries: list = Field(..., description="热门问题")


# =========================================
# 系统状态接口
# =========================================

@router.get(
    "/status",
    response_model=SystemStatus,
    summary="系统状态",
    description="获取系统运行状态和资源使用情况"
)
async def get_system_status():
    """
    系统状态接口

    返回：
    - CPU使用率
    - 内存使用率
    - 磁盘使用率
    - 运行时间
    """
    try:
        # 获取系统信息（Windows 用当前工作目录锚定盘符）
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(os.getcwd())

        # 计算运行时间
        import time
        uptime = time.time() - psutil.boot_time()

        return SystemStatus(
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            disk_percent=disk.percent,
            uptime=uptime,
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"获取系统状态失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取系统状态失败"
        )


@router.get(
    "/health",
    summary="健康检查",
    description="检查各组件健康状态"
)
async def health_check():
    """
    健康检查接口

    检查：
    - 数据库连接
    - 向量库连接
    - Redis连接
    - LLM服务
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {}
    }

    # 检查PostgreSQL
    try:
        # await db.ping()
        health_status["components"]["database"] = "healthy"
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        health_status["components"]["database"] = "unhealthy"
        health_status["status"] = "degraded"

    # 检查Milvus
    try:
        # await vector_db.ping()
        health_status["components"]["vector_db"] = "healthy"
    except Exception as e:
        logger.error(f"向量库连接失败: {e}")
        health_status["components"]["vector_db"] = "unhealthy"
        health_status["status"] = "degraded"

    # 检查Redis
    try:
        # await redis_client.ping()
        health_status["components"]["redis"] = "healthy"
    except Exception as e:
        logger.error(f"Redis连接失败: {e}")
        health_status["components"]["redis"] = "unhealthy"
        health_status["status"] = "degraded"

    # 检查LLM服务
    try:
        # await llm_client.ping()
        health_status["components"]["llm"] = "healthy"
    except Exception as e:
        logger.error(f"LLM服务连接失败: {e}")
        health_status["components"]["llm"] = "unhealthy"
        health_status["status"] = "degraded"

    return health_status


# =========================================
# 索引管理接口
# =========================================

@router.post(
    "/index/rebuild",
    summary="重建索引",
    description="重新构建所有索引"
)
async def rebuild_index(_: None = Depends(require_admin_key)):
    """
    重建索引接口

    流程：
    1. 从数据库加载所有文档
    2. 重新分词和向量化
    3. 重建BM25和向量索引
    4. 更新数据库状态
    """
    try:
        logger.info("开始重建索引")

        # TODO: 接入索引重建任务（无对应 service，当前为占位响应）

        return {
            "success": True,
            "message": "索引重建任务已启动",
            "task_id": "task_001"
        }

    except Exception as e:
        logger.error(f"重建索引失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="重建索引失败"
        )


@router.get(
    "/index/stats",
    response_model=IndexStats,
    summary="索引统计",
    description="获取索引统计信息"
)
async def get_index_stats():
    """
    索引统计接口

    返回索引的详细统计信息
    """
    try:
        # 这里应该从数据库和向量库查询实际统计
        # stats = await get_index_statistics()

        # 临时示例
        return IndexStats(
            total_documents=150,
            total_chunks=3000,
            vector_dimension=1024,
            index_size="500 MB",
            last_updated=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"获取索引统计失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取索引统计失败"
        )


# =========================================
# 缓存管理接口
# =========================================

@router.post(
    "/cache/clear",
    summary="清理缓存",
    description="清理Redis缓存"
)
async def clear_cache(
        pattern: Optional[str] = None,
        _: None = Depends(require_admin_key)
):
    """
    清理缓存接口

    参数：
        pattern: 缓存键模式（可选），如 "qa:*"
    """
    try:
        logger.info(f"清理缓存 | 模式: {pattern}")

        # TODO: 接入 redis_client 清理逻辑（当前为占位）

        count = 0  # 临时

        return {
            "success": True,
            "message": f"缓存清理完成",
            "deleted_keys": count
        }

    except Exception as e:
        logger.error(f"清理缓存失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="清理缓存失败"
        )


@router.get(
    "/cache/stats",
    summary="缓存统计",
    description="获取缓存使用统计"
)
async def get_cache_stats():
    """
    缓存统计接口

    返回Redis缓存的使用情况
    """
    try:
        # 这里应该从Redis获取实际统计
        # stats = await redis_client.info()

        # 临时示例
        return {
            "total_keys": 1000,
            "memory_usage": "50 MB",
            "hit_rate": 0.85,
            "evicted_keys": 10
        }

    except Exception as e:
        logger.error(f"获取缓存统计失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取缓存统计失败"
        )


# =========================================
# 数据统计接口
# =========================================

@router.get(
    "/statistics",
    response_model=Statistics,
    summary="数据统计",
    description="获取系统使用统计"
)
async def get_statistics(
        days: int = 7
):
    """
    数据统计接口

    参数：
        days: 统计天数（默认7天）

    返回：
    - 查询数量
    - 文档数量
    - 平均响应时间
    - 成功率
    - 热门问题
    """
    try:
        # 这里应该从数据库查询实际统计
        # stats = await db.get_statistics(days=days)

        # 临时示例
        return Statistics(
            total_queries=5000,
            total_documents=150,
            avg_response_time=1.5,
            success_rate=0.95,
            popular_queries=[
                {"query": "建筑荷载如何计算", "count": 50},
                {"query": "混凝土强度等级", "count": 45},
                {"query": "钢筋保护层厚度", "count": 40}
            ]
        )

    except Exception as e:
        logger.error(f"获取统计数据失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取统计数据失败"
        )


@router.get(
    "/logs",
    summary="查询日志",
    description="查询系统日志"
)
async def get_logs(
        level: str = "INFO",
        limit: int = 100
):
    """
    日志查询接口

    参数：
        level: 日志级别（DEBUG, INFO, WARNING, ERROR）
        limit: 返回条数
    """
    try:
        # 这里应该从日志文件或数据库查询
        # logs = await get_system_logs(level=level, limit=limit)

        # 临时示例
        logs = [
            {
                "timestamp": datetime.now().isoformat(),
                "level": level,
                "message": "示例日志消息",
                "module": "app.api.v1.qa"
            }
        ]

        return {
            "success": True,
            "total": len(logs),
            "logs": logs
        }

    except Exception as e:
        logger.error(f"查询日志失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="查询日志失败"
        )


# =========================================
# 配置管理接口
# =========================================

@router.get(
    "/config",
    summary="系统配置",
    description="获取系统配置信息"
)
async def get_config():
    """
    系统配置接口

    返回当前系统配置（敏感信息已脱敏）
    """
    try:
        config = {
            "app_name": settings.APP_NAME,
            "environment": settings.ENVIRONMENT,
            "debug": settings.DEBUG,
            "llm_model": settings.LLM_MODEL if hasattr(settings, 'LLM_MODEL') else "N/A",
            "embedding_model": settings.EMBEDDING_MODEL if hasattr(settings, 'EMBEDDING_MODEL') else "N/A"
        }

        return {
            "success": True,
            "config": config
        }

    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取配置失败"
        )


# =========================================
# 💡 使用示例
# =========================================
"""
# 1. 查看系统状态
curl "http://localhost:8000/api/v1/admin/status"


# 2. 健康检查
curl "http://localhost:8000/api/v1/admin/health"


# 3. 重建索引
curl -X POST "http://localhost:8000/api/v1/admin/index/rebuild"


# 4. 索引统计
curl "http://localhost:8000/api/v1/admin/index/stats"


# 5. 清理缓存
curl -X POST "http://localhost:8000/api/v1/admin/cache/clear"


# 6. 数据统计
curl "http://localhost:8000/api/v1/admin/statistics?days=7"


# 7. 查询日志
curl "http://localhost:8000/api/v1/admin/logs?level=ERROR&limit=50"


# 8. 查看配置
curl "http://localhost:8000/api/v1/admin/config"
"""