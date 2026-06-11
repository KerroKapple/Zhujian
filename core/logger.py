"""
========================================
日志系统配置
========================================

📚 模块说明：
- 基于Loguru的日志系统
- 支持文件和控制台输出
- 自动日志轮转和压缩

🎯 核心功能：
1. 多级别日志（DEBUG, INFO, WARNING, ERROR）
2. 日志文件自动轮转
3. 彩色控制台输出
4. 结构化日志
5. 异常追踪

========================================
"""

import sys
import os
from pathlib import Path
from functools import wraps
import time
from typing import Callable, Any, Optional

from loguru import logger as loguru_logger


# =========================================
# 日志配置
# =========================================

class Logger:
    """
    日志管理器

    基于Loguru实现的统一日志系统
    """

    _instance: Optional['Logger'] = None
    _initialized: bool = False

    def __new__(cls, *args, **kwargs):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
            self,
            log_dir: str = "logs",
            log_level: str = "INFO",
            rotation: str = "500 MB",
            retention: str = "30 days",
            compression: str = "zip"
    ):
        """
        初始化日志系统

        参数：
            log_dir: 日志目录
            log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
            rotation: 日志轮转条件 (如 "500 MB", "1 week")
            retention: 日志保留时间 (如 "30 days")
            compression: 压缩格式 (如 "zip", "tar.gz")
        """
        # 避免重复初始化
        if Logger._initialized:
            return

        self.log_dir = Path(log_dir)
        self.log_level = log_level.upper()
        self.rotation = rotation
        self.retention = retention
        self.compression = compression

        # 创建日志目录
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 移除默认的handler
        loguru_logger.remove()

        # 配置日志输出
        self._setup_handlers()

        Logger._initialized = True

    def _setup_handlers(self):
        """配置日志处理器"""

        # 控制台统一 UTF-8，避免 Windows cp1252 写中文/emoji 时 UnicodeEncodeError
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

        # ===== 1. 控制台输出（彩色） =====
        loguru_logger.add(
            sys.stdout,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>"
            ),
            level=self.log_level,
            colorize=True,
            backtrace=True,
            diagnose=True
        )

        # ===== 2. 通用日志文件 =====
        loguru_logger.add(
            self.log_dir / "app.log",
            format=(
                "{time:YYYY-MM-DD HH:mm:ss} | "
                "{level: <8} | "
                "{name}:{function}:{line} | "
                "{message}"
            ),
            level="DEBUG",
            rotation=self.rotation,
            retention=self.retention,
            compression=self.compression,
            encoding="utf-8",
            enqueue=True,  # 异步写入
            backtrace=True,
            diagnose=True
        )

        # ===== 3. 错误日志文件（单独记录ERROR及以上） =====
        loguru_logger.add(
            self.log_dir / "error.log",
            format=(
                "{time:YYYY-MM-DD HH:mm:ss} | "
                "{level: <8} | "
                "{name}:{function}:{line} | "
                "{message}\n"
                "{exception}"
            ),
            level="ERROR",
            rotation=self.rotation,
            retention=self.retention,
            compression=self.compression,
            encoding="utf-8",
            enqueue=True,
            backtrace=True,
            diagnose=True
        )

        # ===== 4. JSON格式日志（用于日志分析） =====
        loguru_logger.add(
            self.log_dir / "app.json",
            format="{message}",
            level="INFO",
            rotation=self.rotation,
            retention=self.retention,
            compression=self.compression,
            encoding="utf-8",
            serialize=True,  # 输出为JSON格式
            enqueue=True
        )

    def get_logger(self):
        """获取logger实例"""
        return loguru_logger


# =========================================
# 全局Logger实例
# =========================================

# 从环境变量或配置读取日志级别
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = os.getenv("LOG_DIR", "logs")

# 创建全局Logger实例
_logger_manager = Logger(
    log_dir=LOG_DIR,
    log_level=LOG_LEVEL,
    rotation="500 MB",
    retention="30 days",
    compression="zip"
)

# 导出logger供其他模块使用
logger = _logger_manager.get_logger()


# =========================================
# setup_logger 函数（兼容性接口）
# =========================================

def setup_logger(
    log_dir: str = None,
    log_level: str = None,
    rotation: str = None,
    retention: str = None
) -> None:
    """
    设置/重新配置日志系统

    这个函数主要用于兼容性，因为 Logger 在模块导入时已自动初始化。
    如果需要使用不同的配置，可以调用此函数重新初始化。

    参数：
        log_dir: 日志目录
        log_level: 日志级别
        rotation: 日志轮转条件
        retention: 日志保留时间

    用法：
        from core.logger import setup_logger, logger

        # 使用默认配置（推荐，无需调用）
        logger.info("Hello")

        # 如果需要自定义配置
        setup_logger(log_dir="custom_logs", log_level="DEBUG")
    """
    global _logger_manager

    # 如果提供了新配置，重新初始化
    if any([log_dir, log_level, rotation, retention]):
        # 重置初始化标志
        Logger._initialized = False

        # 重新创建实例
        _logger_manager = Logger(
            log_dir=log_dir or LOG_DIR,
            log_level=log_level or LOG_LEVEL,
            rotation=rotation or "500 MB",
            retention=retention or "30 days"
        )

        logger.info(f"日志系统已重新配置 | 目录: {log_dir or LOG_DIR} | 级别: {log_level or LOG_LEVEL}")


# =========================================
# 日志装饰器
# =========================================

def log_execution(description: str = ""):
    """
    记录函数执行的装饰器

    自动记录函数的开始、结束、耗时和异常

    用法：
        @log_execution("处理文档")
        def process_document(doc_id):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            func_name = func.__name__
            desc = description or func_name

            # 记录开始
            logger.info(f"开始 {desc}")
            start_time = time.time()

            try:
                # 执行函数
                result = func(*args, **kwargs)

                # 记录成功
                elapsed = time.time() - start_time
                logger.info(f"完成 {desc} | 耗时: {elapsed:.2f}s")

                return result

            except Exception as e:
                # 记录异常
                elapsed = time.time() - start_time
                logger.error(
                    f"失败 {desc} | 耗时: {elapsed:.2f}s | 错误: {str(e)}",
                    exc_info=True
                )
                raise

        return wrapper

    return decorator


def log_api_call(endpoint: str = ""):
    """
    记录API调用的装饰器

    用法：
        @log_api_call("/api/v1/qa/ask")
        async def ask_question(request):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            ep = endpoint or func.__name__

            # 记录请求
            logger.info(f"API调用: {ep}")
            start_time = time.time()

            try:
                # 执行函数
                result = await func(*args, **kwargs)

                # 记录成功响应
                elapsed = time.time() - start_time
                logger.info(f"API响应: {ep} | 耗时: {elapsed:.2f}s | 状态: 成功")

                return result

            except Exception as e:
                # 记录错误响应
                elapsed = time.time() - start_time
                logger.error(
                    f"API错误: {ep} | 耗时: {elapsed:.2f}s | 错误: {str(e)}",
                    exc_info=True
                )
                raise

        return wrapper

    return decorator


# =========================================
# 结构化日志
# =========================================

class StructuredLogger:
    """
    结构化日志工具

    用于记录带有额外字段的日志，便于日志分析
    """

    @staticmethod
    def log_event(
            event_type: str,
            message: str,
            level: str = "INFO",
            **extra_fields
    ):
        """
        记录结构化事件

        参数：
            event_type: 事件类型（如 "qa_request", "doc_upload"）
            message: 日志消息
            level: 日志级别
            **extra_fields: 额外字段
        """
        log_data = {
            "event_type": event_type,
            "message": message,
            **extra_fields
        }

        log_method = getattr(logger, level.lower(), logger.info)
        log_method(str(log_data))

    @staticmethod
    def log_qa_request(
            query: str,
            user_id: str = None,
            response_time: float = None,
            success: bool = True
    ):
        """记录问答请求"""
        StructuredLogger.log_event(
            event_type="qa_request",
            message=f"问答请求: {query[:50]}...",
            user_id=user_id,
            query_length=len(query),
            response_time=response_time,
            success=success
        )

    @staticmethod
    def log_document_upload(
            filename: str,
            file_size: int,
            user_id: str = None,
            success: bool = True
    ):
        """记录文档上传"""
        StructuredLogger.log_event(
            event_type="doc_upload",
            message=f"文档上传: {filename}",
            filename=filename,
            file_size=file_size,
            user_id=user_id,
            success=success
        )


# =========================================
# 性能监控装饰器
# =========================================

def monitor_performance(threshold: float = 1.0):
    """
    性能监控装饰器

    如果执行时间超过阈值，记录WARNING

    参数：
        threshold: 时间阈值（秒）

    用法：
        @monitor_performance(threshold=2.0)
        def slow_function():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time

            if elapsed > threshold:
                logger.warning(
                    f"性能警告: {func.__name__} 耗时 {elapsed:.2f}s "
                    f"(阈值: {threshold}s)"
                )

            return result

        return wrapper

    return decorator


# =========================================
# 导出列表
# =========================================

__all__ = [
    "Logger",
    "logger",
    "setup_logger",
    "log_execution",
    "log_api_call",
    "StructuredLogger",
    "monitor_performance",
]


# =========================================
# 💡 使用示例
# =========================================
"""
from core.logger import logger, setup_logger, log_execution, StructuredLogger

# 1. 基础使用（推荐，无需额外配置）
logger.debug("调试信息")
logger.info("普通信息")
logger.warning("警告信息")
logger.error("错误信息")
logger.critical("严重错误")

# 2. 如果需要自定义配置
setup_logger(log_dir="custom_logs", log_level="DEBUG")

# 3. 带上下文的日志
logger.info(f"处理文档: {doc_id} | 状态: {status}")

# 4. 异常日志（自动记录堆栈）
try:
    result = risky_operation()
except Exception as e:
    logger.exception(f"操作失败: {e}")
    # 或
    logger.error(f"操作失败: {e}", exc_info=True)

# 5. 使用装饰器
@log_execution("加载文档")
def load_document(path):
    # 自动记录开始、结束、耗时
    return document

# 6. 结构化日志
StructuredLogger.log_qa_request(
    query="什么是建筑荷载？",
    user_id="user_123",
    response_time=1.5,
    success=True
)

# 7. 性能监控
@monitor_performance(threshold=2.0)
def slow_process():
    # 如果超过2秒会记录WARNING
    time.sleep(3)
"""