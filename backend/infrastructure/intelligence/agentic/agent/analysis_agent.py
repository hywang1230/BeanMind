from agentuniverse.agent.template.react_agent_template import ReActAgentTemplate
from agentuniverse.agent.input_object import InputObject


class AnalysisAgent(ReActAgentTemplate):
    """演示 Agent，基于 ReAct 模式智能使用工具和 LLM 协同工作"""
    
    def input_keys(self) -> list[str]:
        """返回输入键列表"""
        return ['input']
    
    def output_keys(self) -> list[str]:
        """返回输出键列表"""
        return ['output']
    
    def parse_input(self, input_object: InputObject, agent_input: dict) -> dict:
        """
        解析输入参数
        
        Args:
            input_object: 输入对象
            agent_input: agent 输入字典
            
        Returns:
            dict: 解析后的输入字典
        """
        # 调用父类的 parse_input 来设置工具相关信息
        agent_input = super().parse_input(input_object, agent_input)
        
        # 设置背景信息（如果有的话）
        if 'background' not in agent_input:
            agent_input['background'] = ''
        
        return agent_input
    
    def parse_result(self, agent_result: dict) -> dict:
        """
        解析结果
        
        Args:
            agent_result: agent 执行结果
            
        Returns:
            dict: 解析后的结果
        """
        return agent_result

