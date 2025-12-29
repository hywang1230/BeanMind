"""聊天会话领域实体

表示一个 AI 对话会话，包含多条消息。
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
import uuid

from .chat_message import ChatMessage, MessageRole


@dataclass
class ChatSession:
    """
    聊天会话领域实体
    
    表示一个完整的 AI 对话会话，包含会话的所有消息历史。
    
    Attributes:
        id: 会话唯一标识
        messages: 消息列表
        created_at: 创建时间
        updated_at: 最后更新时间
        title: 会话标题（可选，可从第一条消息自动生成）
    """
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    messages: List[ChatMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    title: Optional[str] = None
    
    def add_message(self, message: ChatMessage):
        """
        添加消息到会话
        
        Args:
            message: 要添加的消息
        """
        message.session_id = self.id
        self.messages.append(message)
        self.updated_at = datetime.now()
        
        # 如果没有标题且是第一条用户消息，自动生成标题
        if not self.title and message.role == MessageRole.USER:
            self._generate_title_from_message(message)
    
    def _generate_title_from_message(self, message: ChatMessage):
        """从消息内容生成会话标题"""
        content = message.content.strip()
        if len(content) > 30:
            self.title = content[:30] + "..."
        else:
            self.title = content
    
    def get_last_message(self) -> Optional[ChatMessage]:
        """获取最后一条消息"""
        return self.messages[-1] if self.messages else None
    
    def get_last_assistant_message(self) -> Optional[ChatMessage]:
        """获取最后一条 AI 助手消息"""
        for message in reversed(self.messages):
            if message.role == MessageRole.ASSISTANT:
                return message
        return None
    
    def get_history_for_context(self, max_messages: int = 10) -> List[dict]:
        """
        获取用于上下文的历史消息
        
        Args:
            max_messages: 最大消息数量
            
        Returns:
            消息字典列表，格式为 [{"role": "user", "content": "..."}, ...]
        """
        # 只取最近的消息
        recent_messages = self.messages[-max_messages:] if len(self.messages) > max_messages else self.messages
        
        return [
            {"role": msg.role.value, "content": msg.content}
            for msg in recent_messages
            if not msg.is_streaming  # 排除正在流式输出的消息
        ]
    
    def clear_messages(self):
        """清空所有消息"""
        self.messages.clear()
        self.updated_at = datetime.now()
        self.title = None
    
    @property
    def message_count(self) -> int:
        """获取消息数量"""
        return len(self.messages)
    
    @property
    def is_empty(self) -> bool:
        """判断会话是否为空"""
        return len(self.messages) == 0
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "id": self.id,
            "title": self.title,
            "messages": [msg.to_dict() for msg in self.messages],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "message_count": self.message_count,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ChatSession":
        """从字典创建会话实体"""
        session = cls(
            id=data.get("id", str(uuid.uuid4())),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(),
            title=data.get("title"),
        )
        
        # 恢复消息
        for msg_data in data.get("messages", []):
            session.messages.append(ChatMessage.from_dict(msg_data))
        
        return session
    
    def __repr__(self) -> str:
        """字符串表示"""
        return f"<ChatSession(id={self.id[:8]}..., messages={self.message_count}, title='{self.title}')>"

