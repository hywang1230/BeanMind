"""Skill 定义。"""

from dataclasses import dataclass, field
from typing import Tuple


@dataclass(frozen=True)
class SkillDefinition:
    """AI 能力定义。"""

    id: str
    name: str
    description: str
    intents: Tuple[str, ...]
    agent_id: str
    tools: Tuple[str, ...] = field(default_factory=tuple)
    write_policy: str = "read_only"
    enabled: bool = True
    priority: int = 100
