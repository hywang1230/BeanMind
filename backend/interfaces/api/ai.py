"""AI 对话 API 端点

提供 AI 对话相关的 HTTP 接口，支持流式输出。
"""
import json
import logging
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from typing import Optional

from backend.application.services import AIApplicationService
from backend.interfaces.dto.request.ai import ChatRequest, ClearSessionRequest
from backend.interfaces.dto.response.ai import (
    ChatResponse,
    ChatMessageResponse,
    ChatSessionResponse,
    QuickQuestionsListResponse,
    QuickQuestionResponse,
)
from backend.interfaces.dto.response.auth import MessageResponse, ErrorResponse

logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/api/ai", tags=["AI 对话"])

# AI 应用服务实例（懒加载）
_ai_service: Optional[AIApplicationService] = None


def get_ai_service() -> AIApplicationService:
    """
    获取 AI 应用服务实例
    
    使用单例模式避免重复初始化 AgentUniverse。
    """
    global _ai_service
    if _ai_service is None:
        _ai_service = AIApplicationService()
    return _ai_service


@router.get(
    "/questions",
    response_model=QuickQuestionsListResponse,
    summary="获取快捷问题列表",
    description="获取预定义的常见问题列表，用于快速开始对话",
    responses={
        200: {"description": "获取成功", "model": QuickQuestionsListResponse},
    }
)
def get_quick_questions():
    """
    获取快捷问题列表
    
    返回预定义的常见问题，用户可以点击快速发起对话。
    """
    ai_service = get_ai_service()
    questions = ai_service.get_quick_questions()
    return QuickQuestionsListResponse(
        questions=[QuickQuestionResponse(**q) for q in questions]
    )


@router.post(
    "/chat",
    summary="AI 对话（流式）",
    description="发送消息给 AI 并获取流式响应（SSE）",
    responses={
        200: {"description": "流式响应", "content": {"text/event-stream": {}}},
        400: {"description": "请求参数错误", "model": ErrorResponse},
    }
)
async def chat_stream(request: ChatRequest):
    """
    AI 对话（流式）
    
    使用 Server-Sent Events (SSE) 返回流式响应。
    每个数据块格式为：`data: {"type": "chunk", "content": "..."}\n\n`
    
    数据块类型：
    - chunk: 内容片段
    - done: 对话完成
    - error: 发生错误
    """
    ai_service = get_ai_service()
    
    # 转换历史格式
    history = None
    if request.history:
        history = [{"role": h.role, "content": h.content} for h in request.history]
    
    async def generate():
        """生成 SSE 流"""
        try:
            for chunk in ai_service.chat_stream(
                message=request.message,
                session_id=request.session_id,
                history=history
            ):
                # 格式化为 SSE
                data = json.dumps(chunk, ensure_ascii=False)
                yield f"data: {data}\n\n"
                
        except Exception as e:
            logger.error(f"流式对话失败: {e}")
            error_data = json.dumps({
                "type": "error",
                "content": str(e),
                "session_id": request.session_id,
            }, ensure_ascii=False)
            yield f"data: {error_data}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        }
    )


@router.post(
    "/chat/sync",
    response_model=ChatResponse,
    summary="AI 对话（同步）",
    description="发送消息给 AI 并获取完整响应（非流式）",
    responses={
        200: {"description": "对话成功", "model": ChatResponse},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    }
)
def chat_sync(request: ChatRequest):
    """
    AI 对话（同步/非流式）
    
    等待 AI 处理完成后返回完整响应。
    适用于不需要流式输出的场景。
    """
    ai_service = get_ai_service()
    
    # 转换历史格式
    history = None
    if request.history:
        history = [{"role": h.role, "content": h.content} for h in request.history]
    
    try:
        result = ai_service.chat(
            message=request.message,
            session_id=request.session_id,
            history=history
        )
        
        return ChatResponse(
            session_id=result["session_id"],
            message=ChatMessageResponse(**result["message"])
        )
        
    except Exception as e:
        logger.error(f"同步对话失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI 对话失败: {str(e)}"
        )


@router.get(
    "/sessions/{session_id}",
    response_model=ChatSessionResponse,
    summary="获取会话历史",
    description="获取指定会话的完整历史记录",
    responses={
        200: {"description": "获取成功", "model": ChatSessionResponse},
        404: {"description": "会话不存在", "model": ErrorResponse},
    }
)
def get_session_history(session_id: str):
    """
    获取会话历史
    
    返回指定会话的所有消息记录。
    """
    ai_service = get_ai_service()
    session = ai_service.get_session_history(session_id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"会话 '{session_id}' 不存在"
        )
    
    return ChatSessionResponse(
        id=session["id"],
        title=session.get("title"),
        messages=[ChatMessageResponse(**msg) for msg in session.get("messages", [])],
        created_at=session["created_at"],
        updated_at=session["updated_at"],
        message_count=session.get("message_count", 0),
    )


@router.delete(
    "/sessions/{session_id}",
    response_model=MessageResponse,
    summary="删除会话",
    description="删除指定的会话及其所有消息",
    responses={
        200: {"description": "删除成功", "model": MessageResponse},
        404: {"description": "会话不存在", "model": ErrorResponse},
    }
)
def delete_session(session_id: str):
    """
    删除会话
    
    永久删除指定的会话及其所有消息。
    """
    ai_service = get_ai_service()
    success = ai_service.delete_session(session_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"会话 '{session_id}' 不存在"
        )
    
    return MessageResponse(message=f"会话 '{session_id}' 已删除")


@router.post(
    "/sessions/{session_id}/clear",
    response_model=MessageResponse,
    summary="清空会话消息",
    description="清空指定会话的所有消息，但保留会话本身",
    responses={
        200: {"description": "清空成功", "model": MessageResponse},
        404: {"description": "会话不存在", "model": ErrorResponse},
    }
)
def clear_session(session_id: str):
    """
    清空会话消息
    
    清空指定会话的所有消息历史，会话本身保留。
    """
    ai_service = get_ai_service()
    success = ai_service.clear_session(session_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"会话 '{session_id}' 不存在"
        )
    
    return MessageResponse(message=f"会话 '{session_id}' 已清空")

