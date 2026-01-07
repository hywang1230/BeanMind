"""AI 聊天领域服务

负责与 LangChain Agent 交互，提供对话能力。
"""
import logging
import traceback
from typing import Optional, List, Dict

from backend.infrastructure.intelligence.agentic.agent.langchain_agent import create_analysis_agent

logger = logging.getLogger(__name__)


class AIChatService:
    """
    AI 聊天领域服务
    
    封装与 LangChain Agent 的交互，提供对话能力。
    """
    
    _agent = None
    _initialized: bool = False
    
    def __init__(self):
        """初始化 AI 聊天服务"""
        self._ensure_initialized()
    
    def _ensure_initialized(self):
        """确保 Agent 已初始化（单例模式）"""
        if not AIChatService._initialized:
            try:
                AIChatService._agent = create_analysis_agent()
                AIChatService._initialized = True
                logger.info("LangChain Agent 初始化成功")
            except Exception as e:
                logger.error(f"LangChain Agent 初始化失败: {type(e).__name__}: {e}")
                logger.error(f"详细堆栈追踪:\n{traceback.format_exc()}")
                raise
    
    def chat(
        self, 
        message: str, 
        session_id: Optional[str] = None,
        chat_history: Optional[list] = None
    ) -> str:
        """
        对话
        
        Args:
            message: 用户消息
            session_id: 会话 ID（用于多轮对话）
            chat_history: 聊天历史
            
        Returns:
            AI 回复内容
        """
        try:
            # 构建消息列表
            messages = self._build_messages(message, chat_history)
            
            # 执行 Agent
            result = AIChatService._agent.invoke({"messages": messages})
            
            # 从结果中提取最后的 AI 消息
            return self._extract_response(result)
            
        except Exception as e:
            logger.error(f"AI 对话失败: {type(e).__name__}: {e}")
            logger.error(f"详细堆栈追踪:\n{traceback.format_exc()}")
            raise
    
    def _build_messages(self, message: str, chat_history: Optional[list] = None) -> List[Dict]:
        """
        构建消息列表
        
        Args:
            message: 当前用户消息
            chat_history: 聊天历史
            
        Returns:
            消息列表
        """
        messages = []
        
        # 添加历史消息
        if chat_history:
            for msg in chat_history:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                messages.append({"role": role, "content": content})
        
        # 添加当前用户消息
        messages.append({"role": "user", "content": message})
        
        return messages
    
    def _extract_response(self, result: dict) -> str:
        """
        从 Agent 结果中提取响应
        
        Args:
            result: Agent 执行结果
            
        Returns:
            AI 回复内容
        """
        # LangChain create_agent 返回格式为 {"messages": [...]}
        messages = result.get("messages", [])
        
        # 找到最后一条 AI 消息
        for msg in reversed(messages):
            # 兼容不同的消息格式
            if hasattr(msg, 'content'):
                # AIMessage 对象
                if hasattr(msg, 'type') and msg.type == 'ai':
                    return msg.content
                # 也可能是其他 Message 类型
                if msg.__class__.__name__ == 'AIMessage':
                    return msg.content
            elif isinstance(msg, dict):
                if msg.get('role') == 'assistant':
                    return msg.get('content', '')
        
        # 如果没找到 AI 消息，返回空字符串
        logger.warning("未找到 AI 响应消息")
        return ""
