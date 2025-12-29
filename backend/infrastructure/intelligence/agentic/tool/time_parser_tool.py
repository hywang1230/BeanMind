from agentuniverse.agent.action.tool.tool import Tool, ToolInput
from datetime import datetime
from agentuniverse.llm.llm import LLM
from agentuniverse.llm.llm_manager import LLMManager
from backend.infrastructure.intelligence.agentic.util.json_util import parse_json_from_markdown
import logging
from agentuniverse.llm.llm_output import LLMOutput


logger = logging.getLogger(__name__)


class TimeParserTool(Tool):
    """根据用户输入的时间字符串，获取开始和结束时间"""
    
    def execute(self, input: str) -> dict:
        """
        执行工具，解析时间字符串，返回开始和结束日期
        
        Args:
            input: 用户输入的时间字符串
            
        Returns:
            {
                "start_date": "2025-01-01",
                "end_date": "2025-01-01"
            }
        """
        return self._parse_time(input)
    
    def _parse_time(self, input: str) -> dict:
        """
        调用 llm 模型，解析时间字符串，返回开始和结束日期

        Args:
            input: 用户输入的时间字符串

        Returns:
            dict: 开始和结束日期
        """
        try:
            llm: LLM = LLMManager().get_instance_obj('qwen3_max_llm_sync')
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
            response: LLMOutput = llm.call(messages=[{"role": "user", "content": prompt_text}])
            return parse_json_from_markdown(response.text)
        except Exception as e:
            logger.error(f"解析时间字符串失败: {e}")
            return {}

