"""
Agent API v1 路由模块

导出 Agent 调度路由，供 app.main 统一注册。
"""

from agents.api.v1 import agents

__all__ = ["agents"]
