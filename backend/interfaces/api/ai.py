"""AI 对话 API 端点

提供 AI 对话相关的 HTTP 接口。
"""
import logging
import threading
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from typing import Optional

from backend.application.services import AIApplicationService
from backend.interfaces.dto.request.ai import ChatRequest, ClearSessionRequest, ResumeSessionRequest
from backend.interfaces.dto.response.ai import (
    ChatResponse,
    ChatMessageResponse,
    ChatSessionResponse,
    ChatSessionListResponse,
    ChatSessionSummaryResponse,
    QuickQuestionsListResponse,
    QuickQuestionResponse,
)
from backend.interfaces.dto.response.auth import MessageResponse, ErrorResponse

logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/api/ai", tags=["AI 对话"])

# AI 应用服务实例（懒加载）
_ai_service: Optional[AIApplicationService] = None
_ai_service_lock = threading.Lock()


def get_ai_service() -> AIApplicationService:
    """
    获取 AI 应用服务实例
    
    使用单例模式避免重复初始化 LangChain Agent。
    """
    global _ai_service
    if _ai_service is None:
        with _ai_service_lock:
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
    "/sessions",
    response_model=ChatSessionResponse,
    summary="创建会话",
    description="创建一个空的 AI 会话并返回基础信息",
)
def create_session():
    session = get_ai_service().create_session()
    return ChatSessionResponse(
        id=session["id"],
        title=session.get("title"),
        messages=[],
        created_at=session["created_at"],
        updated_at=session["updated_at"],
        message_count=session.get("message_count", 0),
        pending_action=None,
    )


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="AI 对话",
    description="发送消息给 AI 并获取完整响应",
    responses={
        200: {"description": "对话成功", "model": ChatResponse},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    }
)
def chat(request: ChatRequest):
    """
    AI 对话
    
    发送消息给 AI 并等待完整响应返回。
    """
    ai_service = get_ai_service()
    
    # 转换历史格式
    history = None
    if request.history:
        history = [{"role": h.role, "content": h.content} for h in request.history]
    context = request.context.model_dump() if request.context else None
    
    try:
        result = ai_service.chat(
            message=request.message,
            session_id=request.session_id,
            history=history,
            context=context,
        )
        
        return ChatResponse(
            session_id=result["session_id"],
            message=ChatMessageResponse(**result["message"])
        )
        
    except Exception as e:
        logger.error("AI 对话失败: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI 服务暂时不可用，请稍后重试"
        )


@router.post(
    "/chat/stream",
    summary="AI 流式对话",
    description="发送消息给 AI 并获取流式响应（Server-Sent Events）",
    responses={
        200: {"description": "流式对话成功", "content": {"text/event-stream": {}}},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    }
)
async def chat_stream(request: ChatRequest):
    """
    AI 流式对话
    
    使用 Server-Sent Events (SSE) 流式返回 AI 响应。
    
    事件格式:
    - type: "session" - 包含 session_id
    - type: "token" - 包含 content（token 片段）
    - type: "done" - 包含完整的 message 对象
    - type: "error" - 包含错误信息
    """
    ai_service = get_ai_service()
    
    # 转换历史格式
    history = None
    if request.history:
        history = [{"role": h.role, "content": h.content} for h in request.history]
    context = request.context.model_dump() if request.context else None
    
    async def event_generator():
        try:
            async for chunk in ai_service.chat_stream(
                message=request.message,
                session_id=request.session_id,
                history=history,
                context=context,
            ):
                yield chunk
        except Exception as e:
            import json
            logger.error("AI 流式对话失败: %s", e, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'error': 'AI 服务暂时不可用，请稍后重试'}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        }
    )


@router.get(
    "/sessions",
    response_model=ChatSessionListResponse,
    summary="获取会话列表",
    description="获取最近的 AI 会话摘要列表",
    responses={
        200: {"description": "获取成功", "model": ChatSessionListResponse},
    }
)
def list_sessions():
    """获取会话摘要列表。"""
    ai_service = get_ai_service()
    sessions = ai_service.list_sessions()
    return ChatSessionListResponse(
        sessions=[ChatSessionSummaryResponse(**session) for session in sessions],
        total=len(sessions),
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
        pending_action=session.get("pending_action"),
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


@router.post(
    "/sessions/{session_id}/resume",
    response_model=ChatResponse,
    summary="恢复中断会话",
    description="对待确认草稿执行 confirm/cancel/edit",
    responses={
        200: {"description": "处理成功", "model": ChatResponse},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        404: {"description": "会话或草稿不存在", "model": ErrorResponse},
    }
)
def resume_session(session_id: str, request: ResumeSessionRequest):
    """恢复待确认的 AI 草稿。"""
    try:
        result = get_ai_service().resume_session_action(
            session_id=session_id,
            action=request.action,
            draft=request.draft,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"会话 '{session_id}' 没有待处理草稿"
        )

    return ChatResponse(
        session_id=result["session_id"],
        message=ChatMessageResponse(**result["message"])
    )


@router.get(
    "/capabilities",
    summary="获取 AI 能力摘要",
)
def get_capabilities():
    """返回当前启用的 graph、skill、agent 和模型摘要。"""
    return get_ai_service().get_capabilities()


@router.get(
    "/skills",
    summary="获取 Skill 列表",
)
def get_skills():
    """获取当前启用 Skill 列表。"""
    return {"skills": get_ai_service().list_skills()}


@router.get(
    "/agents",
    summary="获取 SubAgent 列表",
)
def get_agents():
    """获取当前启用 SubAgent 列表。"""
    return {"agents": get_ai_service().list_agents()}


@router.get(
    "/models",
    summary="获取模型 Profile 列表",
)
def get_models():
    """获取当前模型 Profile 摘要。"""
    return {"models": get_ai_service().list_models()}
