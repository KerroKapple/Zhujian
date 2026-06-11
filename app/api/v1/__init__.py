"""
API v1 路由模块

聚合 v1 版本的所有路由模块，供 app.main 统一注册。
缺失的可选模块以 None 占位，避免导入期连锁失败。
"""

from app.api.v1 import qa
from app.api.v1 import document
from app.api.v1 import admin

# 可选模块：施工图、知识图谱、项目管理
try:
    from app.api.v1 import projects
except ImportError:
    projects = None

try:
    from app.api.v1 import drawing
except ImportError:
    drawing = None

try:
    from app.api.v1 import graph
except ImportError:
    graph = None

__all__ = [
    "qa",
    "document",
    "admin",
    "projects",
    "drawing",
    "graph",
]
