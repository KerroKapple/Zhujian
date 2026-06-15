"""问答域服务：编排 RAG Pipeline，落库查询日志与反馈，依赖缺失时优雅降级。

策略：契约优先 + 真实实现 + 优雅降级。
- 向量/嵌入/LLM 缺失（构造或调用抛异常）时，chat/ask 抛 ServiceUnavailableError(503)；
  流式接口无法中途改状态码，故 yield 一条明确「依赖未就绪」的 SSE 通知，绝不返回假数据。
- 反馈落库依赖 DB，无 DB 抛 ServiceUnavailableError(503)。
"""
from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Optional

from sqlalchemy.orm import Session

from core.exceptions import ServiceUnavailableError
from core.logger import logger

# 单例 RagPipeline：懒构造，进程内复用（其内部组件亦懒加载）
_pipeline: Any = None

_DEP_HINT = "问答依赖未就绪：需要向量库与 LLM"


def _get_pipeline() -> Any:
    """惰性获取 RagPipeline 单例。仅 import 与构造，重型组件在首次 run 时懒加载。"""
    global _pipeline
    if _pipeline is None:
        from services.rag.pipeline import RagPipeline

        _pipeline = RagPipeline()
    return _pipeline


class QAService:
    """问答服务。构造接收 DB 会话；RAG 编排经惰性单例。"""

    def __init__(self, db: Session):
        self.db = db

    # =========================================
    # 问答
    # =========================================

    async def chat(
        self,
        query: str,
        history: Optional[list[dict[str, str]]] = None,
        top_k: int = 5,
        use_rerank: bool = True,
    ) -> dict[str, Any]:
        """多轮对话问答。history 拼入额外上下文供检索/生成参考。"""
        extra_context = self._history_to_context(history)
        return await self._run(query, top_k=top_k, use_rerank=use_rerank, extra_context=extra_context)

    async def ask(
        self,
        query: str,
        top_k: int = 5,
        use_rerank: bool = True,
    ) -> dict[str, Any]:
        """单轮问答。"""
        return await self._run(query, top_k=top_k, use_rerank=use_rerank, extra_context=None)

    async def ask_stream(
        self,
        query: str,
        top_k: int = 5,
        use_rerank: bool = True,
    ) -> AsyncGenerator[str, None]:
        """流式问答：本方法即 SSE 异步生成器。

        当前 Pipeline 一次性生成答案，故先取完整结果再切块下发；
        依赖缺失时 yield 明确降级通知而非崩溃。
        """
        try:
            result = await self._run(query, top_k=top_k, use_rerank=use_rerank, extra_context=None)
        except ServiceUnavailableError as e:
            async for chunk in self._degraded_stream(e.message):
                yield chunk
            return
        async for chunk in self._answer_stream(result):
            yield chunk

    # =========================================
    # 反馈
    # =========================================

    def submit_feedback(
        self,
        query_id: str,
        rating: int,
        comment: Optional[str] = None,
    ) -> dict[str, Any]:
        """落 QueryFeedback。无 DB 或目标查询日志不存在时抛领域异常。"""
        if self.db is None:
            raise ServiceUnavailableError("反馈依赖未就绪：需要数据库")

        from repository.query_log_repo import QueryLogRepository

        repo = QueryLogRepository(self.db)
        if repo.get_query_log_by_id(query_id) is None:
            from core.exceptions import NotFoundError

            raise NotFoundError(f"查询记录不存在：{query_id}")

        try:
            feedback = repo.create_feedback(
                query_log_id=query_id,
                rating=rating,
                is_helpful=rating >= 3,  # 由评分派生是否有帮助
                comment=comment,
            )
        except Exception as e:
            logger.error(f"反馈落库失败: {e}")
            raise ServiceUnavailableError("反馈落库失败：数据库不可用", detail=str(e))

        return {"feedback_id": feedback.id, "query_id": query_id, "rating": rating}

    # =========================================
    # 内部
    # =========================================

    async def _run(
        self,
        query: str,
        *,
        top_k: int,
        use_rerank: bool,
        extra_context: Optional[str],
    ) -> dict[str, Any]:
        """调用 Pipeline 真实方法；捕获依赖异常降级为 503；尽力落库查询日志。"""
        try:
            pipeline = _get_pipeline()
            result = await pipeline.run(
                query,
                top_k=top_k,
                use_rerank=use_rerank,
                extra_context=extra_context,
            )
        except ServiceUnavailableError:
            raise
        except Exception as e:
            # 嵌入/LLM/向量库缺失等：统一降级为服务不可用，绝不假数据
            logger.warning(f"RAG 编排失败，降级 503: {e}")
            raise ServiceUnavailableError(_DEP_HINT, detail=str(e))

        query_id = self._persist_log(query, result, top_k)
        return self._shape(result, query_id)

    def _persist_log(self, query: str, result: dict[str, Any], top_k: int) -> Optional[str]:
        """尽力落查询日志，返回日志 ID（供反馈关联）。DB 不可用不阻断问答。"""
        if self.db is None:
            return None
        from core.constants import QueryType, RetrievalMode
        from repository.query_log_repo import QueryLogRepository

        meta = result.get("metadata", {})
        try:
            repo = QueryLogRepository(self.db)
            log = repo.create_query_log(
                query=query,
                query_type=QueryType.GENERAL_QUERY,
                retrieval_mode=RetrievalMode.HYBRID,
                top_k=top_k,
                retrieved_count=meta.get("retrieval_count", len(result.get("sources", []))),
                answer=result.get("answer"),
                answer_sources=result.get("sources"),
                total_time=meta.get("response_time"),
                has_answer=not meta.get("no_result", False),
            )
            return log.id
        except Exception as e:
            logger.warning(f"查询日志落库失败（不阻断问答）: {e}")
            return None

    @staticmethod
    def _shape(result: dict[str, Any], query_id: Optional[str]) -> dict[str, Any]:
        """整形为路由层响应所需结构，保留前端可用字段。"""
        metadata = dict(result.get("metadata", {}))
        metadata["degraded"] = False
        return {
            "answer": result.get("answer", ""),
            "query": result.get("query", ""),
            "sources": result.get("sources", []),
            "metadata": metadata,
            "query_id": query_id,
            "graph_context": result.get("graph_context"),
        }

    @staticmethod
    def _history_to_context(history: Optional[list[dict[str, str]]]) -> Optional[str]:
        """将对话历史压成额外上下文文本。"""
        if not history:
            return None
        lines = [f"{m.get('role', 'user')}: {m.get('content', '')}" for m in history]
        return "对话历史：\n" + "\n".join(lines)

    @staticmethod
    async def _answer_stream(result: dict[str, Any]) -> AsyncGenerator[str, None]:
        """将完整答案按块下发为 SSE。"""
        answer = result.get("answer", "")
        step = 24
        for i in range(0, len(answer), step):
            yield f"data: {json.dumps({'delta': answer[i:i + step]}, ensure_ascii=False)}\n\n"
        meta = {
            "sources": result.get("sources", []),
            "metadata": result.get("metadata", {}),
            "query_id": result.get("query_id"),
        }
        yield f"event: meta\ndata: {json.dumps(meta, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    @staticmethod
    async def _degraded_stream(message: str) -> AsyncGenerator[str, None]:
        """依赖缺失时的降级流：明确告知不可用，绝不输出假答案。"""
        payload = {"degraded": True, "reason": message}
        yield f"event: degraded\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
