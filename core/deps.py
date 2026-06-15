"""FastAPI 依赖注入：DB 会话与各域服务 provider。

约定：
- get_db 从 core.database.SessionLocal 取会话，yield 后 finally 关闭。
- 各 get_xxx_service 在函数体内惰性 import 对应服务类后构造返回，
  避免模块导入期触发尚未实现的服务依赖（服务类由各域 agent 创建）。
- 服务类构造约定：接收 db 会话（无 DB 依赖的服务可忽略该参数）。
"""
from typing import Any, Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from core.database import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """提供请求级数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_qa_service(db: Session = Depends(get_db)) -> Any:
    """问答域服务（RAG 编排）。"""
    from services.qa.qa_service import QAService

    return QAService(db)


def get_document_service(db: Session = Depends(get_db)) -> Any:
    """文档域服务（上传/列表/状态）。"""
    from services.document.document_service import DocumentService

    return DocumentService(db)


def get_drawing_service(db: Session = Depends(get_db)) -> Any:
    """施工图域服务（解析/处理状态）。"""
    from services.drawing.drawing_service import DrawingService

    return DrawingService(db)


def get_graph_service(db: Session = Depends(get_db)) -> Any:
    """知识图谱域服务。"""
    from services.graph.graph_service import GraphService

    return GraphService(db)


def get_admin_service(db: Session = Depends(get_db)) -> Any:
    """系统管理域服务（统计/健康）。"""
    from services.admin.admin_service import AdminService

    return AdminService(db)


def get_project_service(db: Session = Depends(get_db)) -> Any:
    """项目域服务。"""
    from services.project.project_service import ProjectService

    return ProjectService(db)


def get_task_service(db: Session = Depends(get_db)) -> Any:
    """任务域服务。"""
    from services.project.project_service import TaskService

    return TaskService(db)


def get_cost_service(db: Session = Depends(get_db)) -> Any:
    """成本域服务。"""
    from services.project.project_service import CostService

    return CostService(db)


def get_safety_service(db: Session = Depends(get_db)) -> Any:
    """安全域服务。"""
    from services.project.project_service import SafetyService

    return SafetyService(db)


def get_agent_service(db: Session = Depends(get_db)) -> Any:
    """智能分析 Agent 域服务。"""
    from services.agent.agent_service import AgentService

    return AgentService(db)
