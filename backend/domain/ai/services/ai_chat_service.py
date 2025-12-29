"""AI 聊天领域服务

负责与 Agent 交互，提供对话能力。
"""
import logging
import json
from pathlib import Path
from queue import Queue, Empty
from typing import Generator, Optional, Dict, Any
from threading import Thread

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
    
    封装与 AgentUniverse 的交互，提供同步和流式对话能力。
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
        同步对话（非流式）
        
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
    
    def chat_stream(
        self, 
        message: str, 
        session_id: Optional[str] = None,
        chat_history: Optional[list] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        流式对话
        
        Args:
            message: 用户消息
            session_id: 会话 ID
            chat_history: 聊天历史
            
        Yields:
            流式输出的数据块
        """
        output_queue: Queue = Queue()
        result_holder = {'output': None, 'error': None}
        
        def run_agent():
            """在后台线程中运行 Agent"""
            try:
                agent = self._get_agent()
                
                # 构建输入
                kwargs = {
                    'input': message,
                    'output_stream': output_queue,
                }
                if session_id:
                    kwargs['session_id'] = session_id
                if chat_history:
                    kwargs['chat_history'] = self._format_chat_history(chat_history)
                
                # 执行 Agent
                output_object: OutputObject = agent.run(**kwargs)
                result_holder['output'] = output_object.get_data('output', '')
                
            except Exception as e:
                logger.error(f"Agent 执行失败: {e}")
                result_holder['error'] = str(e)
            finally:
                # 发送结束信号
                output_queue.put(None)
        
        # 启动后台线程
        thread = Thread(target=run_agent, daemon=True)
        thread.start()
        
        # 流式输出
        accumulated_content = ""
        is_after_final_answer = False  # 标记是否已经遇到 "Final Answer:"
        pending_content = ""  # 缓存内容，用于检测 Final Answer
        
        try:
            while True:
                try:
                    # 从队列获取数据，设置超时避免永久阻塞
                    data = output_queue.get(timeout=60)
                    
                    if data is None:
                        # 收到结束信号
                        break
                    
                    # 解析数据
                    chunk = self._parse_stream_data(data)
                    if not chunk:
                        continue
                    
                    content = chunk.get('content', '')
                    if not content:
                        continue
                    
                    # 如果已经遇到 Final Answer，直接输出
                    if is_after_final_answer:
                        accumulated_content += content
                        yield {
                            'type': 'chunk',
                            'content': content,
                        }
                    else:
                        # 累积内容，检测 Final Answer
                        pending_content += content
                        
                        # 检查是否包含 "Final Answer:"
                        final_answer_markers = ["Final Answer:", "Final Answer："]
                        for marker in final_answer_markers:
                            if marker in pending_content:
                                is_after_final_answer = True
                                # 提取 Final Answer 之后的内容
                                idx = pending_content.index(marker)
                                after_marker = pending_content[idx + len(marker):]
                                # 去除开头的空格
                                after_marker = after_marker.lstrip()
                                if after_marker:
                                    accumulated_content += after_marker
                                    yield {
                                        'type': 'chunk',
                                        'content': after_marker,
                                    }
                                pending_content = ""
                                break
                        
                except Empty:
                    # 超时，检查线程是否还在运行
                    if not thread.is_alive():
                        break
                    logger.warning("等待 Agent 输出超时，继续等待...")
                    
        except Exception as e:
            logger.error(f"流式输出处理失败: {e}")
            yield {'type': 'error', 'content': str(e)}
        
        # 等待线程结束
        thread.join(timeout=5)
        
        # 检查是否有错误
        if result_holder['error']:
            yield {'type': 'error', 'content': result_holder['error']}
        else:
            # 发送完成信号
            final_content = accumulated_content or result_holder['output'] or ''
            yield {'type': 'done', 'content': final_content}
    
    def _parse_stream_data(self, data: Any) -> Optional[Dict[str, Any]]:
        """
        解析流式数据
        
        AgentUniverse 的流式输出格式为：{'chunk': '文本内容', 'agent_info': {...}}
        我们只需要提取 'chunk' 字段中的文本内容
        
        Args:
            data: 原始流式数据
            
        Returns:
            解析后的数据块，只包含文本内容
        """
        if data is None:
            return None
        
        try:
            # 记录原始数据类型和内容（调试用）
            logger.debug(f"_parse_stream_data 原始数据: type={type(data).__name__}, repr={repr(data)[:200]}")
            
            # 如果是字典（AgentUniverse 直接返回的格式）
            if isinstance(data, dict):
                return self._extract_chunk_from_dict(data)
            
            # 如果是字符串，尝试解析
            if isinstance(data, str):
                # 先尝试 JSON 解析
                try:
                    parsed = json.loads(data)
                    if isinstance(parsed, dict):
                        return self._extract_chunk_from_dict(parsed)
                except json.JSONDecodeError:
                    pass
                
                # 尝试使用 ast.literal_eval 解析 Python 字典字符串格式
                # 例如: "{'chunk': '文本', 'agent_info': {...}}"
                try:
                    import ast
                    parsed = ast.literal_eval(data)
                    if isinstance(parsed, dict):
                        return self._extract_chunk_from_dict(parsed)
                except (ValueError, SyntaxError) as e:
                    logger.debug(f"ast.literal_eval 解析失败: {e}")
                    pass
                
                # 不是可解析的格式，作为纯文本内容处理
                # 但要排除看起来像字典字符串的情况
                data_stripped = data.strip()
                if data_stripped and not data_stripped.startswith('{'):
                    return {
                        'type': 'chunk',
                        'content': data,
                    }
                # 如果是无法解析的字典字符串，记录警告
                elif data_stripped.startswith('{'):
                    logger.warning(f"无法解析的字典字符串: {data[:100]}...")
                return None
            
            # 其他类型（如 OutputObject 等），尝试获取有用信息
            if hasattr(data, 'get_data'):
                # OutputObject 类型
                output = data.get_data('output', '')
                if output:
                    return {
                        'type': 'chunk',
                        'content': str(output),
                    }
            
            # 记录未知类型
            logger.debug(f"未知数据类型: {type(data).__name__}")
            return None
            
        except Exception as e:
            logger.warning(f"解析流式数据失败: {e}, data type={type(data).__name__}")
            return None
    
    def _extract_chunk_from_dict(self, data: dict) -> Optional[Dict[str, Any]]:
        """
        从字典中提取 chunk 内容
        
        AgentUniverse 流式输出格式有两种：
        1. 直接格式：{'chunk': '...', 'agent_info': {...}}
        2. 嵌套格式：{'type': 'token', 'data': {'chunk': '...', 'agent_info': {...}}}
        
        Args:
            data: 字典数据
            
        Returns:
            提取的内容块
        """
        # 检查是否是嵌套格式：{'type': 'token', 'data': {...}}
        if data.get('type') == 'token' and 'data' in data:
            inner_data = data.get('data', {})
            if isinstance(inner_data, dict):
                # 递归处理内层数据
                return self._extract_chunk_from_dict(inner_data)
        
        # 直接格式：{'chunk': '...', 'agent_info': {...}}
        if 'chunk' in data:
            chunk_content = data.get('chunk', '')
            # 只有当 chunk 有内容时才返回
            if chunk_content:
                return {
                    'type': 'chunk',
                    'content': str(chunk_content),
                    'chunk_index': data.get('chunk_index', 0),
                }
            # chunk 为空时跳过
            return None
        elif 'data' in data:
            # 处理其他 data 格式
            content = data.get('data', '')
            # 如果 data 是字典，递归处理
            if isinstance(content, dict):
                return self._extract_chunk_from_dict(content)
            if content:
                return {
                    'type': 'data',
                    'content': str(content),
                }
            return None
        elif 'output' in data:
            # 最终输出格式
            output = data.get('output', '')
            if output:
                return {
                    'type': 'chunk',
                    'content': str(output),
                }
            return None
        else:
            # 未知字典格式，记录日志但不作为内容输出
            logger.debug(f"未知的字典格式，keys: {list(data.keys())}")
            return None
    
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

