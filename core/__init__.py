"""
========================================
Core 模块初始化
========================================

📚 模块说明：
- 导入并初始化所有核心模块
- 提供统一的导入接口
- 自动设置日志系统

🎯 使用方法：
    # 方式1：导入所有常用组件
    from core import settings, logger, DocumentType

    # 方式2：按需导入
    from core.config import settings
    from core.logger import logger
    from core.constants import DocumentType

========================================
"""

# =========================================
# 1. 导入配置模块
# =========================================
from core.config import settings, get_settings

# =========================================
# 2. 导入日志模块
# =========================================
from core.logger import (
    logger,                    # loguru logger实例
    setup_logger,              # 日志系统初始化函数
    log_execution,             # 日志装饰器
    log_api_call,              # API 调用日志装饰器
    StructuredLogger,          # 结构化日志器
    monitor_performance        # 性能监控装饰器
)

# =========================================
# 3. 导入常量模块
# =========================================
from core.constants import (
    # 枚举类型
    DocumentType,              # 文档类型
    DocumentStatus,            # 文档状态
    PermissionLevel,           # 权限级别
    UserRole,                  # 用户角色
    RetrievalMode,             # 检索模式
    MilvusCollection,          # Milvus集合名称
    QueryType,                 # 查询类型
    AnswerQuality,             # 答案质量
    PromptType,                # Prompt类型

    # 常量类
    HTTPStatus,                # HTTP状态码
    ErrorMessage,              # 错误消息
    SuccessMessage,            # 成功消息
    CacheKey,                  # 缓存键前缀
    LogEvent,                  # 日志事件类型
    FileSizeLimit,             # 文件大小限制
    RegexPattern,              # 正则表达式模式
    SystemConfig,              # 系统配置常量
    MilvusIndexParams,         # Milvus索引参数
    SearchParams,              # 搜索参数
)

# =========================================
# 4. 初始化日志系统
# =========================================
# 📝 在导入core模块时自动初始化日志
setup_logger()

# =========================================
# 5. 导出列表
# =========================================
# 定义 `from core import *` 时导出的内容
__all__ = [
    # ===== 配置相关 =====
    "settings",                # 全局配置实例
    "get_settings",            # 获取配置的函数

    # ===== 日志相关 =====
    "logger",                  # 日志记录器
    "setup_logger",            # 日志初始化
    "log_execution",           # 日志装饰器
    "log_api_call",            # API 调用日志装饰器
    "StructuredLogger",        # 结构化日志器
    "monitor_performance",     # 性能监控装饰器

    # ===== 枚举类型 =====
    "DocumentType",            # 文档类型枚举
    "DocumentStatus",          # 文档状态枚举
    "PermissionLevel",         # 权限级别枚举
    "UserRole",                # 用户角色枚举
    "RetrievalMode",           # 检索模式枚举
    "MilvusCollection",        # Milvus集合枚举
    "QueryType",               # 查询类型枚举
    "AnswerQuality",           # 答案质量枚举
    "PromptType",              # Prompt类型枚举

    # ===== 常量类 =====
    "HTTPStatus",              # HTTP状态码
    "ErrorMessage",            # 错误消息
    "SuccessMessage",          # 成功消息
    "CacheKey",                # 缓存键前缀
    "LogEvent",                # 日志事件类型
    "FileSizeLimit",           # 文件大小限制
    "RegexPattern",            # 正则表达式
    "SystemConfig",            # 系统配置常量
    "MilvusIndexParams",       # Milvus索引参数
    "SearchParams",            # 搜索参数
]

# =========================================
# 6. 版本信息
# =========================================
__version__ = settings.APP_VERSION
__author__ = "筑见 BuildView Team"
__description__ = "筑见 BuildView · 建筑工程「知识库 + 项目智能」双核平台 - 核心模块"


# =========================================
# 💡 使用示例
# =========================================
"""
# 示例1：基础使用
from core import settings, logger

logger.info(f"应用启动: {settings.APP_NAME}")
logger.info(f"数据库: {settings.postgres_url}")


# 示例2：使用枚举
from core import DocumentType, PermissionLevel

doc = {
    "type": DocumentType.STANDARD,
    "permission": PermissionLevel.PUBLIC
}


# 示例3：使用日志上下文
from core import LoggerContext

with LoggerContext("文档处理", doc_id="doc_001"):
    # 处理文档的代码
    process_document()


# 示例4：使用装饰器
from core import log_execution

@log_execution("数据库查询")
def query_database(query):
    # 查询逻辑
    return results


# 示例5：错误处理
from core import ErrorMessage, HTTPStatus

if not document_found:
    raise ValueError(ErrorMessage.DOCUMENT_NOT_FOUND)
"""