"""AI 应用服务

协调 AI 领域服务，管理会话状态，提供面向接口层的操作。
"""
import logging
import uuid
from typing import Dict, Optional, List

from backend.domain.ai.entities import ChatMessage, ChatSession, MessageRole
from backend.domain.ai.services import AIChatService

logger = logging.getLogger(__name__)




# 预定义的快捷问题
QUICK_QUESTIONS = [
    {"id": "q1", "text": "本月支出分析", "icon": "chart_pie"},
    {"id": "q2", "text": "最近消费趋势", "icon": "graph_square"},
    {"id": "q3", "text": "上月账单总结", "icon": "doc_text"},
    {"id": "q4", "text": "今日消费情况", "icon": "calendar"},
    {"id": "q5", "text": "本周支出最多的类别", "icon": "list_bullet"},
    {"id": "q6", "text": "账户余额概览", "icon": "creditcard"},
]


class AIApplicationService:
    """
    AI 应用服务
    
    负责：
    - 管理聊天会话
    - 协调 AI 领域服务
    - 提供对话接口
    - 管理对话历史
    """
    
    # 会话存储（内存缓存，生产环境可改为 Redis）
    _sessions: Dict[str, ChatSession] = {}
    
    def __init__(self):
        """初始化 AI 应用服务"""
        self._chat_service: Optional[AIChatService] = None
    
    @property
    def chat_service(self) -> AIChatService:
        """懒加载 AI 聊天服务"""
        if self._chat_service is None:
            self._chat_service = AIChatService()
        return self._chat_service
    
    def get_quick_questions(self) -> List[Dict]:
        """
        获取快捷问题列表
        
        Returns:
            快捷问题列表
        """
        return QUICK_QUESTIONS
    
    def get_or_create_session(self, session_id: Optional[str] = None) -> ChatSession:
        """
        获取或创建会话
        
        Args:
            session_id: 会话 ID，如果为 None 则创建新会话
            
        Returns:
            会话实体
        """
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        
        # 创建新会话
        new_id = session_id or str(uuid.uuid4())
        session = ChatSession(id=new_id)
        self._sessions[new_id] = session
        return session
    
    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """
        获取会话
        
        Args:
            session_id: 会话 ID
            
        Returns:
            会话实体，不存在返回 None
        """
        return self._sessions.get(session_id)
    
    def clear_session(self, session_id: str) -> bool:
        """
        清空会话
        
        Args:
            session_id: 会话 ID
            
        Returns:
            是否成功
        """
        if session_id in self._sessions:
            self._sessions[session_id].clear_messages()
            return True
        return False
    
    def delete_session(self, session_id: str) -> bool:
        """
        删除会话
        
        Args:
            session_id: 会话 ID
            
        Returns:
            是否成功
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False
    
    def chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        history: Optional[List[Dict]] = None
    ) -> Dict:
        """
        对话
        
        Args:
            message: 用户消息
            session_id: 会话 ID
            history: 外部传入的历史（可选）
            
        Returns:
            对话响应 DTO
        """
        # 获取或创建会话
        session = self.get_or_create_session(session_id)
        
        # 添加用户消息
        user_message = ChatMessage.user_message(message, session.id)
        session.add_message(user_message)
        
        # 获取聊天历史
        chat_history = history or session.get_history_for_context()
        
        try:
            # 调用 AI 服务
            response = self.chat_service.chat(
                message=message,
                session_id=session.id,
                chat_history=chat_history
            )
            
            # 添加 AI 回复消息
            assistant_message = ChatMessage.assistant_message(response, session.id)
            session.add_message(assistant_message)
            
            return {
                "session_id": session.id,
                "message": assistant_message.to_dict()
            }
            
        except Exception as e:
            logger.error(f"AI 对话失败: {e}")
            raise
    
    async def chat_stream(
        self,
        message: str,
        session_id: Optional[str] = None,
        history: Optional[List[Dict]] = None
    ):
        """
        流式对话
        
        Args:
            message: 用户消息
            session_id: 会话 ID
            history: 外部传入的历史（可选）
            
        Yields:
            SSE 格式的数据块
        """
        import json
        
        # 获取或创建会话
        session = self.get_or_create_session(session_id)
        
        # 添加用户消息
        user_message = ChatMessage.user_message(message, session.id)
        session.add_message(user_message)
        
        # 获取聊天历史
        chat_history = history or session.get_history_for_context()
        
        # 收集完整响应
        full_response = ""
        
        try:
            # 首先发送 session_id
            yield f"data: {json.dumps({'type': 'session', 'session_id': session.id})}\n\n"
            
            # 流式输出 AI 回复
            async for token in self.chat_service.chat_stream(
                message=message,
                session_id=session.id,
                chat_history=chat_history
            ):
                full_response += token
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
            
            # 添加 AI 回复消息到会话
            assistant_message = ChatMessage.assistant_message(full_response, session.id)
            session.add_message(assistant_message)
            
            # 发送完成消息
            yield f"data: {json.dumps({'type': 'done', 'message': assistant_message.to_dict()})}\n\n"
            
        except Exception as e:
            logger.error(f"AI 流式对话失败: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
            raise
    
    def get_session_history(self, session_id: str) -> Optional[Dict]:
        """
        获取会话历史
        
        Args:
            session_id: 会话 ID
            
        Returns:
            会话 DTO，不存在返回 None
        """
        session = self.get_session(session_id)
        return session.to_dict() if session else None

