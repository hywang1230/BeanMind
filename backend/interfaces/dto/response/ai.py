"""AI 相关的响应 DTO

定义 AI 对话 API 的响应数据结构。
"""
from pydantic import BaseModel, Field
from typing import Optional, List


class ChatMessageResponse(BaseModel):
    """
    聊天消息响应
    """
    id: str = Field(..., description="消息 ID")
    role: str = Field(..., description="消息角色")
    content: str = Field(..., description="消息内容")
    created_at: str = Field(..., description="创建时间")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "msg-001",
                "role": "assistant",
                "content": "根据您的账单数据分析...",
                "created_at": "2025-01-15T10:30:00"
            }
        }


class ChatResponse(BaseModel):
    """
    聊天响应
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
                    "created_at": "2025-01-15T10:30:00"
                }
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
