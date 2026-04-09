"""Graph 状态定义。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class AssistantState(TypedDict, total=False):
    """Supervisor graph 状态。"""

    session_id: str
    user_id: Optional[str]
    message: str
    history: List[Dict[str, str]]
    context: Dict[str, Any]
    normalized_message: str
    intent: str
    llm_selected_skills: List[str]
    routing_reason: str
    selected_skills: List[str]
    selected_agents: List[str]
    model_profiles: List[str]
    context_summary: Dict[str, Any]
    requires_confirmation: bool
    requires_guardrail: bool
    response_hint: str
    errors: List[str]
