"""
RAG Tool
========

基于 `services.rag.RagPipeline` 的工具封装，供上层 Agents 或 FastAPI 调用。
重型 ML 依赖延迟到调用时导入，避免仅导入本模块即触发 torch 连锁加载。
"""

from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from services.rag import RagPipeline


async def run_rag(
    query: str,
    *,
    top_k: int = 5,
    project_id: Optional[str] = None,
    extra_context: Optional[str] = None,
    pipeline: "RagPipeline | None" = None,
) -> dict[str, Any]:
    """
    对外暴露的 RAG 调用工具。

    - `query`: 用户问题
    - `top_k`: 检索文档数量
    - `project_id`: 可选的项目 ID，用于限定检索范围
    - `extra_context`: 额外上下文（例如结构化指标、Agent 组装的说明）
    - `pipeline`: 可注入自定义 RagPipeline（方便测试或不同配置）
    """
    if pipeline is None:
        # 延迟 import：触发 torch 等重型依赖仅在真正调用时发生
        from services.rag import RagPipeline

        pipeline = RagPipeline()

    return await pipeline.run(
        query=query,
        top_k=top_k,
        project_id=project_id,
        extra_context=extra_context,
    )
