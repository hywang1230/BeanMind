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


class ChatContextRequest(BaseModel):
    """对话上下文。"""

    source_page: Optional[str] = Field(None, description="来源页面")
    selected_entity_id: Optional[str] = Field(None, description="当前选中实体 ID")
    date_range: Optional[dict] = Field(None, description="当前日期范围")


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
    context: Optional[ChatContextRequest] = Field(None, description="页面上下文")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "分析一下本月的消费情况",
                "session_id": "session-001",
                "history": [],
                "context": {
                    "source_page": "/ai"
                }
            }
        }


class ClearSessionRequest(BaseModel):
    """
    清空会话请求
    """
    session_id: str = Field(..., description="会话 ID")


class ResumeSessionRequest(BaseModel):
    """恢复中断会话请求。"""

    action: str = Field(..., description="操作类型：confirm/cancel/edit")
    draft: Optional[dict] = Field(None, description="编辑后的草稿")
