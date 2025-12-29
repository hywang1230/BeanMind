import sys
from pathlib import Path
from dotenv import load_dotenv
# 将项目根目录添加到 Python 路径，以便导入 backend 模块
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agentuniverse.agent.agent import Agent
from agentuniverse.agent.agent_manager import AgentManager
from agentuniverse.base.agentuniverse import AgentUniverse

load_dotenv()

AgentUniverse().start(config_path='../backend/config/config.toml', core_mode=True)


def chat(question: str, session_id=None):
    """ Peer agents example.

    The peer agents in agentUniverse become a chatbot and can ask questions to get the answer.
    """
    instance: Agent = AgentManager().get_instance_obj('analysis_agent')
    output_object = instance.run(input=question, session_id=session_id)
    res_info = f"\nPeer agent execution result is :\n"
    res_info += output_object.get_data('output')
    print(res_info)


if __name__ == '__main__':
    chat(question="上个月的消费情况", session_id="test-02")