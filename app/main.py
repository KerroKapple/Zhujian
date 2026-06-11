"""
========================================
 RAG 系统 - 主入口（更新版）
========================================

📚 模块说明：
- FastAPI 应用入口
- 路由注册（包含Agent路由）
- 中间件配置
- 生命周期管理

🚀 启动方式：
    # 开发模式
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

    # 生产模式
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

========================================
"""

import sys
import os
from pathlib import Path
from contextlib import asynccontextmanager

# 添加项目根目录到 Python 路径
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# 导入配置和核心模块
from core.config import settings
from core.logger import logger

# 导入路由
from app.api.v1 import qa, document, admin
from agents.api.v1 import agents as agents_api  # Agent路由

# 新增：施工图和知识图谱路由
try:
    from app.api.v1 import drawing as drawing_api
    from app.api.v1 import graph as graph_api
    DRAWING_GRAPH_AVAILABLE = True
except ImportError as e:
    logger.warning(f"施工图/知识图谱路由加载失败: {e}")
    DRAWING_GRAPH_AVAILABLE = False


# =========================================
# 生命周期管理
# =========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理

    启动时：
    - 初始化日志
    - 检查数据库连接
    - 预热模型（可选）

    关闭时：
    - 清理资源
    - 关闭连接
    """
    # ===== 启动阶段 =====
    logger.info("=" * 60)
    logger.info(f"🚀 启动 {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info("=" * 60)

    # 日志系统已在导入时自动初始化

    # 校验安全配置（生产环境占位密钥直接 fail-fast）
    from core.security import check_security_config
    check_security_config()

    # 创建运行所需目录（data/processed 等）
    settings.ensure_dirs()

    # 检查关键服务连接
    await check_services()

    logger.info("✅ 应用启动完成")
    logger.info(f"📡 API 地址: http://{settings.HOST}:{settings.PORT}")
    logger.info(f"📚 API 文档: http://{settings.HOST}:{settings.PORT}/docs")

    yield  # 应用运行中

    # ===== 关闭阶段 =====
    logger.info("🛑 应用正在关闭...")

    # 清理资源
    await cleanup_resources()

    logger.info("👋 应用已关闭")


async def check_services():
    """检查关键服务连接"""
    logger.info("检查服务连接...")

    # 检查 Redis
    try:
        from services.cache.redis_client import redis_client
        if redis_client.ping():
            logger.info("  ✓ Redis 连接正常")
    except Exception as e:
        logger.warning(f"  ✗ Redis 连接失败: {e}")

    # 检查 PostgreSQL
    try:
        from core.database import check_db_connection
        if check_db_connection():
            logger.info("  ✓ PostgreSQL 连接正常")
    except Exception as e:
        logger.warning(f"  ✗ PostgreSQL 连接失败: {e}")

    # 检查 Milvus
    try:
        from services.retrieval.vector.milvus_client import milvus_client
        if milvus_client.is_connected():
            logger.info("  ✓ Milvus 连接正常")
    except Exception as e:
        logger.warning(f"  ✗ Milvus 连接失败: {e}")

    # 检查 Neo4j
    try:
        from services.graph.neo4j_client import neo4j_client
        if neo4j_client.ping():
            logger.info("  ✓ Neo4j 连接正常")
    except Exception as e:
        logger.warning(f"  ✗ Neo4j 连接失败: {e}")


async def cleanup_resources():
    """清理资源"""
    try:
        # 关闭 Redis 连接
        from services.cache.redis_client import redis_client
        redis_client.close()
        logger.info("  ✓ Redis 连接已关闭")
    except Exception as e:
        logger.warning(f"  ✗ Redis 关闭失败: {e}")

    try:
        # 关闭 Milvus 连接
        from services.retrieval.vector.milvus_client import milvus_client
        milvus_client.close()
        logger.info("  ✓ Milvus 连接已关闭")
    except Exception as e:
        logger.warning(f"  ✗ Milvus 关闭失败: {e}")


# =========================================
# 创建 FastAPI 应用
# =========================================

app = FastAPI(
    title=settings.APP_NAME,
    description="""
    RAG 智能问答系统
    
    ## 功能特性
    
    * 📄 **文档管理** - 支持 PDF、Word、文本等多种格式
    * 🔍 **智能检索** - 混合检索 + 重排序
    * 💬 **智能问答** - 基于检索内容生成回答
    * 🤖 **Agent 智能体** - 周报生成、风险分析等
    * 📊 **项目管理** - 进度、成本、安全分析
    
    ## API 版本
    
    当前版本：v1
    """,
    version=settings.APP_VERSION,
    openapi_url=f"{settings.API_PREFIX}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)


# =========================================
# 中间件配置
# =========================================

# CORS 配置（限定来源，配合 allow_credentials）
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录请求日志"""
    import time

    start_time = time.time()

    # 处理请求
    response = await call_next(request)

    # 计算耗时
    process_time = time.time() - start_time

    # 记录日志
    logger.info(
        f"{request.method} {request.url.path} "
        f"| Status: {response.status_code} "
        f"| Time: {process_time:.3f}s"
    )

    # 添加响应头
    response.headers["X-Process-Time"] = str(process_time)

    return response


# =========================================
# 全局异常处理
# =========================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP 异常处理"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.status_code,
                "message": exc.detail
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """通用异常处理"""
    logger.error(f"未处理的异常: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": 500,
                "message": "服务器内部错误" if settings.ENVIRONMENT == "production" else str(exc)
            }
        }
    )


# =========================================
# 注册路由
# =========================================

# API v1 路由 - 问答
app.include_router(
    qa.router,
    prefix=f"{settings.API_PREFIX}/qa",
    tags=["问答接口"]
)

# API v1 路由 - 文档管理
app.include_router(
    document.router,
    prefix=f"{settings.API_PREFIX}/document",
    tags=["文档管理"]
)

# API v1 路由 - 系统管理
app.include_router(
    admin.router,
    prefix=f"{settings.API_PREFIX}/admin",
    tags=["系统管理"]
)

# API v1 路由 - Agent 智能体
app.include_router(
    agents_api.router,
    prefix=f"{settings.API_PREFIX}/agents",
    tags=["Agent 智能体"]
)

# API v1 路由 - 施工图处理（新增）
if DRAWING_GRAPH_AVAILABLE:
    app.include_router(
        drawing_api.router,
        prefix=f"{settings.API_PREFIX}/drawing",
        tags=["施工图处理"]
    )
    logger.info("已注册施工图处理路由")

    # API v1 路由 - 知识图谱（新增）
    app.include_router(
        graph_api.router,
        prefix=f"{settings.API_PREFIX}/graph",
        tags=["知识图谱"]
    )
    logger.info("已注册知识图谱路由")

# 如果存在项目管理路由，也注册
try:
    from app.api.v1 import projects
    app.include_router(
        projects.router,
        prefix=f"{settings.API_PREFIX}/projects",
        tags=["项目管理"]
    )
    logger.info("已注册项目管理路由")
except ImportError:
    logger.debug("项目管理路由未找到，跳过注册")


# =========================================
# 根路由
# =========================================

@app.get("/", tags=["根路由"])
async def root():
    """
    根路由 - 返回系统信息
    """
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "api_prefix": settings.API_PREFIX,
        "features": [
            "RAG 智能问答",
            "文档管理",
            "Agent 智能体",
            "项目管理",
            "施工图处理",
            "知识图谱"
        ]
    }


@app.get("/health", tags=["健康检查"])
async def health_check():
    """
    健康检查接口

    用于负载均衡器和容器编排的健康检查
    """
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


@app.get("/info", tags=["系统信息"])
async def system_info():
    """
    获取系统信息
    """
    import platform

    return {
        "app": {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "debug": settings.DEBUG
        },
        "system": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor()
        },
        "config": {
            "api_prefix": settings.API_PREFIX,
            "milvus_host": settings.MILVUS_HOST,
            "redis_host": settings.REDIS_HOST,
            "postgres_host": settings.POSTGRES_HOST
        },
        "routes": {
            "qa": f"{settings.API_PREFIX}/qa",
            "document": f"{settings.API_PREFIX}/document",
            "admin": f"{settings.API_PREFIX}/admin",
            "agents": f"{settings.API_PREFIX}/agents",
            "projects": f"{settings.API_PREFIX}/projects",
            "drawing": f"{settings.API_PREFIX}/drawing",
            "graph": f"{settings.API_PREFIX}/graph"
        }
    }


# =========================================
# 启动入口
# =========================================

def main():
    """主函数 - 启动应用"""
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else settings.WORKERS,
        log_level="info" if settings.DEBUG else "warning"
    )


if __name__ == "__main__":
    main()


# =========================================
# 💡 使用说明
# =========================================
"""
# 1. 开发模式启动（自动重载）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 2. 生产模式启动（多 worker）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# 3. 使用 Python 直接启动
python app/main.py

# 4. 指定配置文件
ENVIRONMENT=production python app/main.py

# 5. 访问 API 文档
# Swagger UI: http://localhost:8000/docs
# ReDoc: http://localhost:8000/redoc

# 6. 健康检查
curl http://localhost:8000/health

# 7. 系统信息
curl http://localhost:8000/info

# 8. Agent 接口示例
# 生成周报
curl -X POST "http://localhost:8000/api/v1/agents/weekly-report" \
     -H "Content-Type: application/json" \
     -d '{"project_id": "P001", "format": "markdown"}'

# 风险分析
curl -X POST "http://localhost:8000/api/v1/agents/risk-analysis" \
     -H "Content-Type: application/json" \
     -d '{"project_id": "P001"}'

# 快速风险扫描
curl "http://localhost:8000/api/v1/agents/risk-analysis/P001/quick-scan"

# 项目仪表盘
curl "http://localhost:8000/api/v1/agents/dashboard/P001"
"""