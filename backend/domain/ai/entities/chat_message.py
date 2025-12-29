"""聊天消息领域实体

表示一条 AI 对话中的消息。
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum
import uuid


class MessageRole(str, Enum):
    """消息角色枚举"""
    USER = "user"        # 用户消息
    ASSISTANT = "assistant"  # AI 助手消息
    SYSTEM = "system"    # 系统消息


@dataclass
class ChatMessage:
    """
    聊天消息领域实体
    
    表示 AI 对话中的一条消息，可以是用户发送的，也可以是 AI 回复的。
    
    Attributes:
        id: 消息唯一标识
        role: 消息角色（user/assistant/system）
        content: 消息内容
        created_at: 创建时间
        session_id: 所属会话 ID
    """
    
    role: MessageRole
    content: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    session_id: Optional[str] = None
    
    def __post_init__(self):
        """验证消息数据"""
        self._validate()
    
    def _validate(self):
        """验证消息内容"""
        if not isinstance(self.role, MessageRole):
            raise ValueError(f"无效的消息角色: {self.role}")
        
        if self.content is None:
            raise ValueError("消息内容不能为 None")
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "id": self.id,
            "role": self.role.value,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "session_id": self.session_id,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ChatMessage":
        """从字典创建消息实体"""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            role=MessageRole(data["role"]),
            content=data["content"],
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            session_id=data.get("session_id"),
        )
    
    @classmethod
    def user_message(cls, content: str, session_id: Optional[str] = None) -> "ChatMessage":
        """创建用户消息的工厂方法"""
        return cls(
            role=MessageRole.USER,
            content=content,
            session_id=session_id,
        )
    
    @classmethod
    def assistant_message(cls, content: str, session_id: Optional[str] = None) -> "ChatMessage":
        """创建 AI 助手消息的工厂方法"""
        return cls(
            role=MessageRole.ASSISTANT,
            content=content,
            session_id=session_id,
        )
    
    @classmethod
    def system_message(cls, content: str, session_id: Optional[str] = None) -> "ChatMessage":
        """创建系统消息的工厂方法"""
        return cls(
            role=MessageRole.SYSTEM,
            content=content,
            session_id=session_id,
        )
    
    def __repr__(self) -> str:
        """字符串表示"""
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<ChatMessage(role={self.role.value}, content='{content_preview}')>"
