"""模型配置定义。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelProfile:
    """模型配置抽象。"""

    profile_id: str
    provider: str
    model_name: str
    base_url: str
    temperature: float = 0.1
    max_tokens: int = 4096
    timeout: int = 120
    supports_tool_call: bool = True
    supports_json_mode: bool = True
