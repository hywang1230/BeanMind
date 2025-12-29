"""AI 相关的请求 DTO

定义 AI 对话 API 的请求数据结构。
"""
from pydantic import BaseModel, Field
from typing import Optional, List


class ChatMessageRequest(BaseModel):
    """
    聊天消息请求
    """
    role: str = Field(..., description="消息角色（user/assistant/system）")
    content: str = Field(..., description="消息内容")


class ChatRequest(BaseModel):
    """
    聊天请求
    
    Example:
        {
            "message": "分析一下本月的消费情况",
            "session_id": "session-001",
            "history": [
                {"role": "user", "content": "你好"},
                {"role": "assistant", "content": "你好！有什么可以帮助你的？"}
            ]
        }
    """
    message: str = Field(..., min_length=1, max_length=4000, description="用户消息")
    session_id: Optional[str] = Field(None, description="会话 ID（用于多轮对话）")
    history: Optional[List[ChatMessageRequest]] = Field(None, description="聊天历史")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "分析一下本月的消费情况",
                "session_id": "session-001",
                "history": []
            }
        }


class ClearSessionRequest(BaseModel):
    """
    清空会话请求
    """
    session_id: str = Field(..., description="会话 ID")

