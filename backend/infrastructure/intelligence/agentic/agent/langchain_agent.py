"""LangChain Agent 实现

基于 LangChain 的 Agent，用于财务分析。
"""
import os
import logging
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

from backend.infrastructure.intelligence.agentic.tool.budget_tool import budget_tool
from backend.infrastructure.intelligence.agentic.tool.transaction_tool import transaction_tool
from backend.infrastructure.intelligence.agentic.tool.time_parser_tool import time_parser_tool

logger = logging.getLogger(__name__)


# 系统提示词
SYSTEM_PROMPT = """你是一个专业的记账助手，精通工具使用和财务分析。
你的目标是根据用户的问题，合理使用工具回答用户关于记账、消费、预算等方面的问题。

你必须优先选择使用提供的工具回答用户提出的问题，若用户没有提供工具可以根据你的通识知识解决问题。
你在回答问题时必须使用中文回答。
你必须从多个角度、维度分析用户的问题，帮助用户获取最全面的财务信息。

注意：
1. 如果用户只是简单问候或闲聊，直接回答，不要使用工具
2. 只有在确实需要获取特定信息时才使用工具，避免不必要的工具调用
3. 查询预算或交易信息时，先使用时间解析工具获取日期范围"""


def create_analysis_agent():
    """
    创建财务分析 Agent
    
    Returns:
        CompiledStateGraph: 可执行的 Agent 实例
    """
    # 配置 LLM（使用 DashScope OpenAI 兼容模式）
    llm = ChatOpenAI(
        model="qwen3-max",
        temperature=0.1,
        api_key=os.environ.get("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    
    # 工具列表
    tools = [time_parser_tool, transaction_tool, budget_tool]
    
    # 创建 Agent
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
    )
    
    logger.info("LangChain Agent 创建成功")
    return agent
