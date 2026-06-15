"""问答 API：单轮/多轮/流式问答 + 答案反馈。

路由层仅做 HTTP 入参校验 + 经 Depends 注入 QAService + 返回；
业务编排与降级在 services.qa.QAService，错误经 core.exceptions 统一成错误体。
"""
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

# QAService 经 Depends(get_qa_service) 惰性注入，故不在模块期导入，避免触发 services 包副作用
from core.deps import get_qa_service

router = APIRouter()


# =========================================
# 请求模型（Pydantic2）
# =========================================

class Message(BaseModel):
    """对话消息。"""

    role: str = Field(..., description="角色：user 或 assistant")
    content: str = Field(..., description="消息内容")


class QuestionRequest(BaseModel):
    """单轮问答请求。"""

    query: str = Field(..., description="用户问题", min_length=1, max_length=500)
    top_k: int = Field(5, description="检索文档数量", ge=1, le=20)
    use_rerank: bool = Field(True, description="是否使用重排序")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"query": "建筑结构楼面活荷载如何取值？", "top_k": 5, "use_rerank": True}
        }
    )


class ChatRequest(BaseModel):
    """多轮对话请求。"""

    query: str = Field(..., description="当前问题", min_length=1, max_length=500)
    history: list[Message] = Field(default_factory=list, description="对话历史")
    top_k: int = Field(5, description="检索文档数量", ge=1, le=20)
    use_rerank: bool = Field(True, description="是否使用重排序")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "那活荷载呢？",
                "history": [
                    {"role": "user", "content": "什么是恒荷载？"},
                    {"role": "assistant", "content": "恒荷载是指在结构使用期间不变的荷载。"},
                ],
                "top_k": 5,
                "use_rerank": True,
            }
        }
    )


# =========================================
# 接口
# =========================================

@router.post("/ask", summary="单轮问答", description="基于知识库 RAG 检索并生成答案")
async def ask_question(
    request: QuestionRequest,
    service: Any = Depends(get_qa_service),
) -> dict[str, Any]:
    result = await service.ask(
        query=request.query, top_k=request.top_k, use_rerank=request.use_rerank
    )
    return {"success": True, **result}


@router.post("/chat", summary="多轮对话", description="支持对话历史的多轮 RAG 问答")
async def chat(
    request: ChatRequest,
    service: Any = Depends(get_qa_service),
) -> dict[str, Any]:
    history = [{"role": m.role, "content": m.content} for m in request.history]
    result = await service.chat(
        query=request.query,
        history=history,
        top_k=request.top_k,
        use_rerank=request.use_rerank,
    )
    return {"success": True, **result}


@router.post("/ask/stream", summary="流式问答", description="SSE 流式返回答案")
async def ask_question_stream(
    request: QuestionRequest,
    service: Any = Depends(get_qa_service),
) -> StreamingResponse:
    generator = service.ask_stream(
        query=request.query, top_k=request.top_k, use_rerank=request.use_rerank
    )
    return StreamingResponse(generator, media_type="text/event-stream")


@router.post("/feedback/{query_id}", summary="答案反馈", description="用户对答案评分并落库")
async def submit_feedback(
    query_id: str,
    rating: int = Query(..., description="评分 1-5", ge=1, le=5),
    comment: Optional[str] = Query(None, description="反馈评论"),
    service: Any = Depends(get_qa_service),
) -> dict[str, Any]:
    result = service.submit_feedback(query_id=query_id, rating=rating, comment=comment)
    return {"success": True, "message": "感谢您的反馈", **result}
