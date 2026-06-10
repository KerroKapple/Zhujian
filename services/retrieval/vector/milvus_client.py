"""
========================================
Milvus 向量数据库客户端
========================================

📚 模块说明：
- 封装 Milvus 连接生命周期管理
- 实现单例模式，全局共享一个连接
- 为健康检查、资源清理提供统一入口

🎯 核心功能：
1. 连接建立与延迟初始化
2. 连接状态检查
3. 连接关闭

🔧 使用方式：
    from services.retrieval.vector.milvus_client import milvus_client

    milvus_client.ensure_connected()
    if milvus_client.is_connected():
        ...
    milvus_client.close()

========================================
"""
from typing import Optional

from core.config import settings
from core.logger import logger

# 延迟导入 pymilvus，避免未安装时报错
try:
    from pymilvus import connections
    MILVUS_AVAILABLE = True
except ImportError:
    MILVUS_AVAILABLE = False
    logger.warning("pymilvus 包未安装，Milvus 功能将不可用。请运行: uv add pymilvus")


class MilvusClient:
    """
    Milvus 向量数据库客户端

    🎯 职责：
    - 管理 Milvus 连接（default 别名）
    - 提供连接状态检查
    - 统一连接关闭入口

    💡 设计理念：
    - 单例模式：全局共享一个连接
    - 延迟初始化：首次使用时才建立连接
    """

    _instance: Optional["MilvusClient"] = None
    _alias: str = "default"
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        if not MILVUS_AVAILABLE:
            logger.warning("Milvus 客户端初始化跳过：pymilvus 包未安装")

    def connect(self) -> None:
        """建立 Milvus 连接（若已连接则跳过）"""
        if not MILVUS_AVAILABLE:
            raise RuntimeError("pymilvus 包未安装，请运行: uv add pymilvus")

        if connections.has_connection(self._alias):
            return

        try:
            connections.connect(
                alias=self._alias,
                host=settings.MILVUS_HOST,
                port=settings.MILVUS_PORT,
                user=settings.MILVUS_USER or None,
                password=settings.MILVUS_PASSWORD or None,
            )
            logger.info(f"成功连接到 Milvus: {settings.MILVUS_HOST}:{settings.MILVUS_PORT}")
        except Exception as e:
            logger.error(f"连接 Milvus 失败: {str(e)}")
            raise

    def ensure_connected(self) -> None:
        """确保已连接，未连接则建立连接"""
        if not self.is_connected():
            self.connect()

    def is_connected(self) -> bool:
        """检查 Milvus 是否已连接"""
        if not MILVUS_AVAILABLE:
            return False
        try:
            return connections.has_connection(self._alias)
        except Exception:
            return False

    def close(self) -> None:
        """关闭 Milvus 连接"""
        if not MILVUS_AVAILABLE:
            return
        try:
            if connections.has_connection(self._alias):
                connections.disconnect(self._alias)
                logger.info("已断开 Milvus 连接")
        except Exception as e:
            logger.error(f"断开 Milvus 连接失败: {str(e)}")


# 全局单例
milvus_client = MilvusClient()
