"""Supervisor graph 最小实现。"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Literal, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from backend.config import settings
from backend.infrastructure.intelligence.langgraph.graph.state import AssistantState
from backend.infrastructure.intelligence.langgraph.registry.model_registry import ModelRegistry
from backend.infrastructure.intelligence.langgraph.registry.skill_registry import SkillRegistry
from backend.infrastructure.intelligence.langgraph.registry.subagent_registry import SubAgentRegistry

logger = logging.getLogger(__name__)


class RoutingDecision(BaseModel):
    """LLM 路由决策。"""

    intent: Optional[
        Literal[
        "analyze",
        "record_transaction",
        "budget",
        "report",
        "account",
        "query_transaction",
        "recurring",
        ]
    ] = Field(default=None, description="用户请求的意图类别")
    selected_skills: List[str] = Field(default_factory=list, description="本次请求应执行的技能 ID 列表，最多 2 个")
    reason: str = Field(default="", description="简短说明为什么这样路由")


class SupervisorGraphBuilder:
    """构建阶段 1 的最小 supervisor graph。"""

    def __init__(
        self,
        skill_registry: SkillRegistry,
        agent_registry: SubAgentRegistry,
        model_registry: ModelRegistry,
    ) -> None:
        self.skill_registry = skill_registry
        self.agent_registry = agent_registry
        self.model_registry = model_registry

    def _build_llm(self, profile_id: str = "reasoning") -> Optional[ChatOpenAI]:
        if not settings.AI_API_KEY:
            return None
        profile = self.model_registry.get(profile_id)
        return ChatOpenAI(
            model=profile.model_name,
            temperature=0,
            api_key=settings.AI_API_KEY,
            base_url=profile.base_url,
            timeout=profile.timeout,
            max_tokens=profile.max_tokens,
        )

    def _fallback_intent(self, message: str) -> str:
        intent = "analyze"
        has_amount = re.search(r"\d+(?:\.\d+)?", message) is not None
        looks_like_transaction = any(
            keyword in message
            for keyword in [
                "记一笔",
                "记账",
                "帮我记",
                "入账",
                "消费了",
                "花了",
                "收到",
                "收了",
                "工资",
                "收入",
                "吃饭",
                "午饭",
                "晚饭",
                "早餐",
                "支出",
                "付款",
                "支付",
            ]
        )

        if any(keyword in message for keyword in ["周期", "每月", "每周", "定期", "每天", "自动记", "隔周"]):
            intent = "recurring"
        elif looks_like_transaction and has_amount:
            intent = "record_transaction"
        elif any(keyword in message for keyword in ["记一笔", "记账", "帮我记", "入账", "消费了", "花了", "收到", "收了", "工资", "收入"]):
            intent = "record_transaction"
        elif any(keyword in message for keyword in ["预算", "超支", "剩余预算"]):
            intent = "budget"
        elif any(keyword in message for keyword in ["报表", "利润表", "资产负债表", "净资产", "资产情况", "余额概览", "账户余额", "balance sheet", "明细"]):
            intent = "report"
        elif any(keyword in message for keyword in ["账户", "科目", "分类"]):
            intent = "account"
        elif any(keyword in message for keyword in ["查询交易", "查一下", "账单", "流水"]):
            intent = "query_transaction"

        return intent

    def _fallback_skills(self, intent: str, message: str) -> List[str]:
        skills = self.skill_registry.get_by_intent(intent)
        if not skills and intent != "analyze":
            skills = self.skill_registry.get_by_intent("analyze")

        if intent == "budget":
            if any(keyword in message for keyword in ["创建预算", "新建预算", "做预算", "预算建议", "预算规划", "预算草稿", "生成预算"]):
                return ["budget.plan"]
            return ["budget.inspect"]
        if intent == "account":
            if any(keyword in message for keyword in ["开户", "新建账户", "创建账户", "关闭账户", "关户", "停用账户"]):
                return ["account.manage"]
            return ["account.classify"]
        return [skill.id for skill in skills[:2]]

    def _route_with_llm(self, state: AssistantState) -> Optional[RoutingDecision]:
        llm = self._build_llm("reasoning")
        if llm is None:
            return None

        history = state.get("history") or []
        context = state.get("context") or {}
        skill_descriptions = [
            {
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "write_policy": skill.write_policy,
                "intents": list(skill.intents),
            }
            for skill in self.skill_registry.list_skills()
        ]
        history_lines = [
            f"{item.get('role', 'user')}: {item.get('content', '')}"
            for item in history[-6:]
        ] or ["无"]

        system_prompt = (
            "你是 BeanMind 的意图路由器，只负责识别用户意图并选择技能，不要回答业务内容。\n"
            "必须结合当前用户消息、最近对话历史、页面上下文进行判断。\n"
            "你必须输出合法 JSON。\n"
            "优先选择最小必要技能，默认只选 1 个，最多 2 个。\n"
            "只有当用户明确要求创建、生成、草拟、记账、开户、关户、创建规则等写操作时，"
            "才允许选择 confirm_required 技能。\n"
            "像“还剩多少预算/预算用了多少/是否超支”属于预算查询，应选 budget.inspect，不能选 budget.plan。\n"
            "像“账户怎么分类/这个科目放哪里”属于账户查询，应选 account.classify，不能选 account.manage。\n"
            "像“新建账户/关闭账户”才选 account.manage。\n"
            "像“账户余额概览/账户余额/余额概览/净资产”属于报表或余额查询，应选 report.explain，不能选 account.classify。\n"
            "如果是消费分析、趋势分析、总体解读，优先选 analysis.spending；"
            "如果是查具体账单、流水、某笔交易，优先选 transaction.query。"
        )
        user_prompt = (
            f"当前消息：{state.get('message', '')}\n"
            f"最近历史：\n" + "\n".join(history_lines) + "\n"
            f"页面上下文：{json.dumps(context, ensure_ascii=False)}\n"
            f"可选技能(JSON)：{json.dumps(skill_descriptions, ensure_ascii=False)}\n"
            "请仅返回 JSON，不要返回额外说明。"
        )

        try:
            structured_llm = llm.with_structured_output(RoutingDecision)
            decision = structured_llm.invoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
            )
            valid_skill_ids = {skill.id for skill in self.skill_registry.list_skills()}
            selected_skills = [
                skill_id
                for skill_id in decision.selected_skills
                if skill_id in valid_skill_ids
            ][:2]
            intent = decision.intent
            if intent is None and selected_skills:
                first_skill = self.skill_registry.get(selected_skills[0])
                if first_skill and first_skill.intents:
                    intent = first_skill.intents[0]
            if intent is None:
                intent = self._fallback_intent(
                    (state.get("normalized_message") or state.get("message") or "").lower()
                )
            if not selected_skills:
                selected_skills = self._fallback_skills(
                    intent,
                    (state.get("normalized_message") or state.get("message") or "").lower(),
                )
            decision.intent = intent
            decision.selected_skills = selected_skills
            return decision
        except Exception as exc:
            logger.warning("AI graph LLM 路由失败，降级关键词兜底: %s", exc)
            return None

    def normalize_input(self, state: AssistantState) -> AssistantState:
        message = (state.get("message") or "").strip()
        logger.info("AI graph node normalize_input: session=%s", state.get("session_id"))
        return {
            "normalized_message": " ".join(message.split()),
            "errors": [],
        }

    def route_intent(self, state: AssistantState) -> AssistantState:
        message = (state.get("normalized_message") or state.get("message") or "").lower()
        decision = self._route_with_llm(state)
        if decision is not None:
            intent = decision.intent
            llm_selected_skills = decision.selected_skills
            routing_reason = decision.reason
        else:
            intent = self._fallback_intent(message)
            llm_selected_skills = []
            routing_reason = "fallback_keyword"

        logger.info("AI graph node route_intent: session=%s intent=%s", state.get("session_id"), intent)
        return {
            "intent": intent,
            "llm_selected_skills": llm_selected_skills,
            "routing_reason": routing_reason,
        }

    def route_skills(self, state: AssistantState) -> AssistantState:
        intent = state.get("intent", "analyze")
        message = (state.get("normalized_message") or state.get("message") or "").lower()
        llm_selected_skills = list(state.get("llm_selected_skills", []))
        if llm_selected_skills:
            logger.info(
                "AI graph node route_skills: session=%s skills=%s source=llm",
                state.get("session_id"),
                llm_selected_skills,
            )
            return {"selected_skills": llm_selected_skills}
        selected_skills = self._fallback_skills(intent, message)

        logger.info("AI graph node route_skills: session=%s skills=%s", state.get("session_id"), selected_skills)
        return {"selected_skills": selected_skills}

    def route_subagents(self, state: AssistantState) -> AssistantState:
        selected_skills = state.get("selected_skills", [])
        agents: List[str] = []
        profiles: List[str] = []

        for skill in self.skill_registry.get_many(selected_skills):
            if skill.agent_id not in agents:
                agents.append(skill.agent_id)
                agent = self.agent_registry.get(skill.agent_id)
                if agent:
                    profiles.append(agent.model_profile)

        if not agents:
            agents.append("analysis_agent")
            profiles.append("reasoning")

        logger.info(
            "AI graph node route_subagents: session=%s agents=%s profiles=%s",
            state.get("session_id"),
            agents,
            profiles,
        )
        return {
            "selected_agents": agents,
            "model_profiles": profiles,
        }

    def context_loader(self, state: AssistantState) -> AssistantState:
        context = state.get("context") or {}
        summary: Dict[str, Any] = {}
        if context.get("source_page"):
            summary["source_page"] = context["source_page"]
        if context.get("selected_entity_id"):
            summary["selected_entity_id"] = context["selected_entity_id"]
        if context.get("date_range"):
            summary["date_range"] = context["date_range"]
        logger.info("AI graph node context_loader: session=%s keys=%s", state.get("session_id"), sorted(summary.keys()))
        return {"context_summary": summary}

    def approval_gate(self, state: AssistantState) -> AssistantState:
        selected_skills = state.get("selected_skills", [])
        message = (state.get("normalized_message") or state.get("message") or "").lower()
        requires_confirmation = any(
            self.skill_registry.get(skill_id)
            and self.skill_registry.get(skill_id).write_policy == "confirm_required"
            for skill_id in selected_skills
        )
        requires_guardrail = False
        if "account.manage" in selected_skills and any(
            keyword in message for keyword in ["关闭账户", "关户", "close account", "close"]
        ):
            requires_guardrail = True

        selected_agents = list(state.get("selected_agents", []))
        model_profiles = list(state.get("model_profiles", []))
        if requires_guardrail and "guardrail_agent" not in selected_agents:
            selected_agents.append("guardrail_agent")
            model_profiles.append("guardrail")

        logger.info(
            "AI graph node approval_gate: session=%s confirm=%s guardrail=%s",
            state.get("session_id"),
            requires_confirmation,
            requires_guardrail,
        )
        return {
            "requires_confirmation": requires_confirmation,
            "requires_guardrail": requires_guardrail,
            "selected_agents": selected_agents,
            "model_profiles": model_profiles,
        }

    def response_builder(self, state: AssistantState) -> AssistantState:
        skills = state.get("selected_skills", [])
        agents = state.get("selected_agents", [])
        intent = state.get("intent", "analyze")
        context_summary = state.get("context_summary", {})
        requires_confirmation = state.get("requires_confirmation", False)
        requires_guardrail = state.get("requires_guardrail", False)
        context_hint = ",".join(sorted(context_summary.keys())) or "none"
        response_hint = (
            f"intent={intent}; skills={','.join(skills) or 'none'}; "
            f"agents={','.join(agents) or 'none'}; "
            f"context={context_hint}; "
            f"confirm={'yes' if requires_confirmation else 'no'}; "
            f"guardrail={'yes' if requires_guardrail else 'no'}"
        )
        logger.info("AI graph node response_builder: session=%s hint=%s", state.get("session_id"), response_hint)
        return {"response_hint": response_hint}

    def build(self):
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError:
            logger.warning("LangGraph 未安装，无法构建 supervisor graph")
            return None

        builder = StateGraph(AssistantState)
        builder.add_node("normalize_input", self.normalize_input)
        builder.add_node("route_intent", self.route_intent)
        builder.add_node("route_skills", self.route_skills)
        builder.add_node("route_subagents", self.route_subagents)
        builder.add_node("context_loader", self.context_loader)
        builder.add_node("approval_gate", self.approval_gate)
        builder.add_node("response_builder", self.response_builder)

        builder.add_edge(START, "normalize_input")
        builder.add_edge("normalize_input", "route_intent")
        builder.add_edge("route_intent", "route_skills")
        builder.add_edge("route_skills", "route_subagents")
        builder.add_edge("route_subagents", "context_loader")
        builder.add_edge("context_loader", "approval_gate")
        builder.add_edge("approval_gate", "response_builder")
        builder.add_edge("response_builder", END)
        return builder
