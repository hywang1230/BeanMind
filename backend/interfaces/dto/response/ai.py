"""AI 相关的响应 DTO

定义 AI 对话 API 的响应数据结构。
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ChatMessageResponse(BaseModel):
    """
    聊天消息响应
    """
    id: str = Field(..., description="消息 ID")
    role: str = Field(..., description="消息角色")
    content: str = Field(..., description="消息内容")
    created_at: str = Field(..., description="创建时间")
    is_streaming: bool = Field(False, description="是否为流式输出中")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "msg-001",
                "role": "assistant",
                "content": "根据您的账单数据分析...",
                "created_at": "2025-01-15T10:30:00",
                "is_streaming": False
            }
        }


class ChatResponse(BaseModel):
    """
    聊天响应（非流式）
    """
    session_id: str = Field(..., description="会话 ID")
    message: ChatMessageResponse = Field(..., description="AI 回复消息")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session-001",
                "message": {
                    "id": "msg-001",
                    "role": "assistant",
                    "content": "根据您的账单数据分析...",
                    "created_at": "2025-01-15T10:30:00",
                    "is_streaming": False
                }
            }
        }


class StreamChunkResponse(BaseModel):
    """
    流式输出块响应
    
    用于 SSE 流式输出的单个数据块。
    """
    type: str = Field(..., description="数据类型（chunk/done/error）")
    content: str = Field("", description="内容片段")
    session_id: Optional[str] = Field(None, description="会话 ID")
    message_id: Optional[str] = Field(None, description="消息 ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "chunk",
                "content": "根据您的",
                "session_id": "session-001",
                "message_id": "msg-001"
            }
        }


class ChatSessionResponse(BaseModel):
    """
    聊天会话响应
    """
    id: str = Field(..., description="会话 ID")
    title: Optional[str] = Field(None, description="会话标题")
    messages: List[ChatMessageResponse] = Field(default_factory=list, description="消息列表")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")
    message_count: int = Field(0, description="消息数量")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "session-001",
                "title": "本月消费分析",
                "messages": [],
                "created_at": "2025-01-15T10:00:00",
                "updated_at": "2025-01-15T10:30:00",
                "message_count": 4
            }
        }


class QuickQuestionResponse(BaseModel):
    """
    快捷问题响应
    """
    id: str = Field(..., description="问题 ID")
    text: str = Field(..., description="问题文本")
    icon: Optional[str] = Field(None, description="图标名称")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "q1",
                "text": "本月支出分析",
                "icon": "chart_pie"
            }
        }


class QuickQuestionsListResponse(BaseModel):
    """
    快捷问题列表响应
    """
    questions: List[QuickQuestionResponse] = Field(..., description="快捷问题列表")

