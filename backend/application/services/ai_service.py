"""AI 应用服务

协调 AI 领域服务，管理会话状态，提供面向接口层的操作。
"""
import logging
import uuid
from pathlib import Path
from typing import Dict, Optional, List, Generator, Any
from datetime import datetime

from backend.domain.ai.entities import ChatMessage, ChatSession, MessageRole
from backend.domain.ai.services import AIChatService

logger = logging.getLogger(__name__)

# 计算配置文件的绝对路径
_DEFAULT_CONFIG_PATH = str(Path(__file__).parent.parent.parent / 'config' / 'config.toml')


# 预定义的快捷问题
QUICK_QUESTIONS = [
    {"id": "q1", "text": "本月支出分析", "icon": "chart_pie"},
    {"id": "q2", "text": "最近消费趋势", "icon": "chart_line_uptrend_xyaxis"},
    {"id": "q3", "text": "上月账单总结", "icon": "doc_text"},
    {"id": "q4", "text": "今日消费情况", "icon": "calendar_badge_clock"},
    {"id": "q5", "text": "本周支出最多的类别", "icon": "list_bullet"},
    {"id": "q6", "text": "账户余额概览", "icon": "creditcard"},
]


class AIApplicationService:
    """
    AI 应用服务
    
    负责：
    - 管理聊天会话
    - 协调 AI 领域服务
    - 提供流式和非流式对话接口
    - 管理对话历史
    """
    
    # 会话存储（内存缓存，生产环境可改为 Redis）
    _sessions: Dict[str, ChatSession] = {}
    
    def __init__(self, config_path: str = _DEFAULT_CONFIG_PATH):
        """
        初始化 AI 应用服务
        
        Args:
            config_path: AgentUniverse 配置路径
        """
        self.config_path = config_path
        self._chat_service: Optional[AIChatService] = None
    
    @property
    def chat_service(self) -> AIChatService:
        """懒加载 AI 聊天服务"""
        if self._chat_service is None:
            self._chat_service = AIChatService(self.config_path)
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
        同步对话（非流式）
        
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
    
    def chat_stream(
        self,
        message: str,
        session_id: Optional[str] = None,
        history: Optional[List[Dict]] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        流式对话
        
        Args:
            message: 用户消息
            session_id: 会话 ID
            history: 外部传入的历史（可选）
            
        Yields:
            流式输出数据块
        """
        # 获取或创建会话
        session = self.get_or_create_session(session_id)
        
        # 添加用户消息
        user_message = ChatMessage.user_message(message, session.id)
        session.add_message(user_message)
        
        # 获取聊天历史
        chat_history = history or session.get_history_for_context()
        
        # 创建 AI 回复消息（流式状态）
        assistant_message = ChatMessage.assistant_message("", session.id, is_streaming=True)
        session.add_message(assistant_message)
        
        try:
            # 调用流式 AI 服务
            for chunk in self.chat_service.chat_stream(
                message=message,
                session_id=session.id,
                chat_history=chat_history
            ):
                chunk_type = chunk.get('type', 'chunk')
                content = chunk.get('content', '')
                
                if chunk_type == 'chunk':
                    # 累积内容
                    assistant_message.append_content(content)
                    
                    yield {
                        'type': 'chunk',
                        'content': content,
                        'session_id': session.id,
                        'message_id': assistant_message.id,
                    }
                    
                elif chunk_type == 'done':
                    # 完成
                    assistant_message.mark_streaming_complete()
                    # 如果最终内容与累积不同，使用最终内容
                    if content and content != assistant_message.content:
                        assistant_message.content = content
                    
                    yield {
                        'type': 'done',
                        'content': assistant_message.content,
                        'session_id': session.id,
                        'message_id': assistant_message.id,
                    }
                    
                elif chunk_type == 'error':
                    # 错误
                    assistant_message.mark_streaming_complete()
                    assistant_message.content = f"抱歉，处理您的请求时出现了问题：{content}"
                    
                    yield {
                        'type': 'error',
                        'content': content,
                        'session_id': session.id,
                        'message_id': assistant_message.id,
                    }
                    
        except Exception as e:
            logger.error(f"流式对话失败: {e}")
            assistant_message.mark_streaming_complete()
            assistant_message.content = f"抱歉，处理您的请求时出现了问题：{str(e)}"
            
            yield {
                'type': 'error',
                'content': str(e),
                'session_id': session.id,
                'message_id': assistant_message.id,
            }
    
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

