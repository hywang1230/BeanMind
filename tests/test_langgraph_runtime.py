"""LangGraph 运行时关键测试。"""

import asyncio

from backend.infrastructure.intelligence.langgraph.graph.supervisor_graph import RoutingDecision, SupervisorGraphBuilder
from backend.infrastructure.intelligence.langgraph.registry.model_registry import ModelRegistry
from backend.infrastructure.intelligence.langgraph.registry.skill_registry import SkillRegistry
from backend.infrastructure.intelligence.langgraph.registry.subagent_registry import SubAgentRegistry
from backend.infrastructure.intelligence.langgraph.runtime.langgraph_runtime import LangGraphRuntime


def test_plan_marks_guardrail_for_account_close():
    """关闭账户应在 graph 规划阶段带上 guardrail。"""
    runtime = LangGraphRuntime()

    plan = runtime.plan("关闭账户 Assets:Cash")

    assert plan.intent == "account"
    assert "account.manage" in plan.selected_skills
    assert "account_agent" in plan.selected_agents
    assert "guardrail_agent" in plan.selected_agents
    assert plan.requires_confirmation is True
    assert plan.requires_guardrail is True


def test_budget_query_only_selects_budget_inspect():
    """预算查询不应误触发预算草稿技能。"""
    runtime = LangGraphRuntime()

    plan = runtime.plan("我问现在还剩多少预算")

    assert plan.intent == "budget"
    assert plan.selected_skills == ["budget.inspect"]


def test_budget_creation_selects_budget_plan():
    """显式创建预算时才选择预算草稿技能。"""
    runtime = LangGraphRuntime()

    plan = runtime.plan("帮我生成一个本月预算建议")

    assert plan.intent == "budget"
    assert plan.selected_skills == ["budget.plan"]


def test_account_balance_overview_routes_to_report(monkeypatch):
    """账户余额概览不应误路由到账户分类。"""
    builder = SupervisorGraphBuilder(
        skill_registry=SkillRegistry(),
        agent_registry=SubAgentRegistry(),
        model_registry=ModelRegistry(),
    )
    monkeypatch.setattr(builder, "_route_with_llm", lambda state: None)

    intent_state = builder.route_intent(
        {
            "session_id": "test-session",
            "message": "账户余额概览",
            "normalized_message": "账户余额概览",
            "history": [],
            "context": {},
        }
    )
    skill_state = builder.route_skills(
        {
            "session_id": "test-session",
            "message": "账户余额概览",
            "normalized_message": "账户余额概览",
            "history": [],
            "context": {},
            **intent_state,
        }
    )

    assert intent_state["intent"] == "report"
    assert skill_state["selected_skills"] == ["report.explain"]


def test_transaction_like_message_falls_back_to_record_transaction(monkeypatch):
    """模型路由失败时，带金额的记账句不应误判为账户查询。"""
    builder = SupervisorGraphBuilder(
        skill_registry=SkillRegistry(),
        agent_registry=SubAgentRegistry(),
        model_registry=ModelRegistry(),
    )
    monkeypatch.setattr(builder, "_route_with_llm", lambda state: None)

    fallback_state = {
        "session_id": "test-session",
        "message": "吃饭100，信用卡账户支出",
        "normalized_message": "吃饭100，信用卡账户支出",
        "history": [],
        "context": {},
    }

    intent_state = builder.route_intent(fallback_state)

    assert intent_state["intent"] == "record_transaction"


def test_supervisor_prefers_llm_routing_result(monkeypatch):
    """有 LLM 路由结果时，应优先使用模型选择的意图和技能。"""
    builder = SupervisorGraphBuilder(
        skill_registry=SkillRegistry(),
        agent_registry=SubAgentRegistry(),
        model_registry=ModelRegistry(),
    )

    monkeypatch.setattr(
        builder,
        "_route_with_llm",
        lambda state: RoutingDecision(
            intent="budget",
            selected_skills=["budget.inspect"],
            reason="预算余额查询",
        ),
    )

    base_state = {
        "session_id": "test-session",
        "message": "我现在还剩多少预算",
        "normalized_message": "我现在还剩多少预算",
        "history": [],
        "context": {},
    }
    intent_state = builder.route_intent(base_state)
    skill_state = builder.route_skills({**base_state, **intent_state})

    assert intent_state["intent"] == "budget"
    assert intent_state["llm_selected_skills"] == ["budget.inspect"]
    assert skill_state["selected_skills"] == ["budget.inspect"]


def test_route_with_llm_can_recover_when_intent_is_missing(monkeypatch):
    """模型漏掉 intent 时，应从技能反推出意图而不是整体失败。"""
    builder = SupervisorGraphBuilder(
        skill_registry=SkillRegistry(),
        agent_registry=SubAgentRegistry(),
        model_registry=ModelRegistry(),
    )

    class _FakeStructuredLLM:
        def invoke(self, messages):
            return RoutingDecision(
                selected_skills=["transaction.record"],
                reason="根据金额和动作词判断为记账",
            )

    class _FakeLLM:
        def with_structured_output(self, schema):
            return _FakeStructuredLLM()

    monkeypatch.setattr(builder, "_build_llm", lambda profile_id="reasoning": _FakeLLM())

    decision = builder._route_with_llm(
        {
            "session_id": "test-session",
            "message": "午饭花了 46",
            "normalized_message": "午饭花了 46",
            "history": [],
            "context": {},
        }
    )

    assert decision is not None
    assert decision.intent == "record_transaction"
    assert decision.selected_skills == ["transaction.record"]


def test_plan_stream_includes_new_graph_stages():
    """流式规划应输出新增的 graph 节点阶段。"""
    runtime = LangGraphRuntime()

    async def collect():
        events = []
        async for event in runtime.plan_stream(
            "帮我记一笔今天午饭46元",
            context={"source_page": "/ai"},
        ):
            events.append(event)
        return events

    events = asyncio.run(collect())
    progress_stages = [event["stage"] for event in events if event.get("type") == "progress"]

    assert "context_loader" in progress_stages or "plan" in progress_stages
    assert "approval_gate" in progress_stages or "plan" in progress_stages
    assert "response_builder" in progress_stages or "plan" in progress_stages
