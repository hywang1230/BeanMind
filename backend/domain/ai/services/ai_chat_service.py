"""AI 聊天领域服务

负责与 Agent 交互，提供对话能力。
"""
import logging
from pathlib import Path
from typing import Optional

from agentuniverse.agent.agent import Agent
from agentuniverse.agent.agent_manager import AgentManager
from agentuniverse.base.agentuniverse import AgentUniverse
from agentuniverse.agent.output_object import OutputObject

from backend.domain.ai.entities import ChatMessage, ChatSession, MessageRole

logger = logging.getLogger(__name__)

# 计算配置文件的绝对路径
_DEFAULT_CONFIG_PATH = str(Path(__file__).parent.parent.parent.parent / 'config' / 'config.toml')


class AIChatService:
    """
    AI 聊天领域服务
    
    封装与 AgentUniverse 的交互，提供对话能力。
    """
    
    _initialized: bool = False
    
    def __init__(self, config_path: str = _DEFAULT_CONFIG_PATH):
        """
        初始化 AI 聊天服务
        
        Args:
            config_path: AgentUniverse 配置文件路径
        """
        self.config_path = config_path
        self._ensure_initialized()
    
    def _ensure_initialized(self):
        """确保 AgentUniverse 已初始化（单例模式）"""
        if not AIChatService._initialized:
            try:
                AgentUniverse().start(config_path=self.config_path, core_mode=True)
                AIChatService._initialized = True
                logger.info("AgentUniverse 初始化成功")
            except Exception as e:
                logger.error(f"AgentUniverse 初始化失败: {e}")
                raise
    
    def _get_agent(self, agent_name: str = 'analysis_agent') -> Agent:
        """
        获取 Agent 实例
        
        Args:
            agent_name: Agent 名称
            
        Returns:
            Agent 实例
        """
        agent = AgentManager().get_instance_obj(agent_name)
        if not agent:
            raise ValueError(f"Agent '{agent_name}' 不存在")
        return agent
    
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
            agent = self._get_agent()
            
            # 构建输入
            kwargs = {'input': message}
            if session_id:
                kwargs['session_id'] = session_id
            if chat_history:
                kwargs['chat_history'] = self._format_chat_history(chat_history)
            
            # 执行 Agent
            output_object: OutputObject = agent.run(**kwargs)
            
            # 提取输出
            result = output_object.get_data('output', '')
            return result
            
        except Exception as e:
            logger.error(f"AI 对话失败: {e}")
            raise
    
    def _format_chat_history(self, history: list) -> str:
        """
        格式化聊天历史为字符串
        
        Args:
            history: 聊天历史列表
            
        Returns:
            格式化后的字符串
        """
        if not history:
            return ""
        
        lines = []
        for msg in history:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if role == 'user':
                lines.append(f"用户: {content}")
            elif role == 'assistant':
                lines.append(f"助手: {content}")
        
        return "\n".join(lines)

