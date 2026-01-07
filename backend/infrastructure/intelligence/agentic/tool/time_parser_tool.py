"""时间解析工具

根据用户输入的时间字符串，获取开始和结束时间。
"""
import os
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from backend.infrastructure.intelligence.agentic.util.json_util import parse_json_from_markdown


logger = logging.getLogger(__name__)


class TimeParserToolInput(BaseModel):
    """时间解析工具输入参数"""
    input: str = Field(description="用户输入的时间字符串（如：'上个月'、'本月'、'最近一周'等）")


@tool(args_schema=TimeParserToolInput)
def time_parser_tool(input: str) -> dict:
    """
    根据用户输入的时间字符串，解析并返回开始和结束日期。
    
    调用示例：{"input": "上个月"}
    返回格式：{"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}
    """
    try:
        llm = ChatOpenAI(
            model="qwen3-max",
            temperature=0.1,
            api_key=os.environ.get("DASHSCOPE_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        
        prompt_text = f"""
你是一个时间解析器，请根据用户输入的时间字符串，返回开始和结束时间，当前时间为{datetime.now().strftime("%Y-%m-%d")}，
返回 json 格式，key 为 start_date 和 end_date，value 为日期字符串，格式为 YYYY-MM-DD
用户输入的时间字符串为：{input}
Example:
    input: "本月情况"
    return: {{
        "start_date": "2025-12-01",
        "end_date": "2025-12-31"
    }}
"""
        response = llm.invoke(prompt_text)
        return parse_json_from_markdown(response.content)
    except Exception as e:
        logger.error(f"解析时间字符串失败: {e}")
        return {}
