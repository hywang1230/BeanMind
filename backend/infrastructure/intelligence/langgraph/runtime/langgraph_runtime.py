"""LangGraph 运行时。"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from backend.config import settings
from backend.infrastructure.intelligence.langgraph.graph.supervisor_graph import SupervisorGraphBuilder
from backend.infrastructure.intelligence.langgraph.registry.model_registry import ModelRegistry
from backend.infrastructure.intelligence.langgraph.registry.skill_registry import SkillRegistry
from backend.infrastructure.intelligence.langgraph.registry.subagent_registry import SubAgentRegistry
from backend.infrastructure.intelligence.langgraph.tools import ReadOnlyToolExecutor, ToolExecutionResult

logger = logging.getLogger(__name__)


@dataclass
class GraphPlanningResult:
    """Graph 规划结果。"""

    session_id: str
    intent: str
    selected_skills: List[str]
    selected_agents: List[str]
    model_profiles: List[str]
    requires_confirmation: bool
    requires_guardrail: bool
    response_hint: str


class LangGraphRuntime:
    """阶段 1：只负责会话规划与事件流，不直接替代业务写入。"""

    def __init__(self) -> None:
        self.skill_registry = SkillRegistry()
        self.agent_registry = SubAgentRegistry()
        self.model_registry = ModelRegistry()
        self.tool_executor = ReadOnlyToolExecutor()
        self._graph = None

    def _get_or_create_session_id(self, session_id: Optional[str]) -> str:
        return session_id or str(uuid.uuid4())

    def _build_graph(self):
        if self._graph is not None:
            return self._graph

        builder = self._build_graph_builder()
        if builder is None:
            self._graph = None
            return None

        checkpointer = self._build_checkpointer()
        try:
            self._graph = builder.compile(checkpointer=checkpointer) if checkpointer else builder.compile()
        except Exception as exc:
            logger.warning("编译 LangGraph 失败，降级为无 checkpoint 模式: %s", exc)
            self._graph = builder.compile()
        return self._graph

    def _build_graph_builder(self):
        return SupervisorGraphBuilder(
            skill_registry=self.skill_registry,
            agent_registry=self.agent_registry,
            model_registry=self.model_registry,
        ).build()

    def _build_checkpointer(self):
        try:
            from langgraph.checkpoint.memory import MemorySaver
        except ImportError:
            logger.warning("未找到 LangGraph MemorySaver，跳过 checkpointer 初始化")
            return None

        # 阶段 1 优先保证能运行；SQLite saver 缺失时退回 MemorySaver
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver  # type: ignore
            import sqlite3

            conn = sqlite3.connect(str(settings.AI_CHECKPOINT_DB), check_same_thread=False)
            return SqliteSaver(conn)
        except Exception as exc:
            logger.warning("初始化 SQLite checkpointer 失败，降级到 MemorySaver: %s", exc)
            return MemorySaver()

    async def _astream_updates(
        self,
        input_state: Dict[str, Any],
        config: Dict[str, Any],
    ):
        builder = self._build_graph_builder()
        if builder is None:
            raise RuntimeError("LangGraph 不可用")

        checkpoint_path = Path(settings.AI_CHECKPOINT_DB)
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver  # type: ignore
        except ImportError as exc:
            raise RuntimeError("未找到 AsyncSqliteSaver") from exc

        async with AsyncSqliteSaver.from_conn_string(str(checkpoint_path)) as checkpointer:
            graph = builder.compile(checkpointer=checkpointer)
            async for chunk in graph.astream(input_state, config=config, stream_mode="updates"):
                yield chunk

    def _build_config(self, session_id: str) -> Dict[str, Any]:
        return {"configurable": {"thread_id": session_id}}

    def _fallback_plan(
        self,
        session_id: str,
        message: str,
    ) -> GraphPlanningResult:
        lower = message.lower()
        if any(keyword in lower for keyword in ["记一笔", "记账", "帮我记", "花了"]):
            return GraphPlanningResult(
                session_id=session_id,
                intent="record_transaction",
                selected_skills=["transaction.record"],
                selected_agents=["ledger_agent"],
                model_profiles=["structured"],
                requires_confirmation=True,
                requires_guardrail=False,
                response_hint="fallback record transaction",
            )
        return GraphPlanningResult(
            session_id=session_id,
            intent="analyze",
            selected_skills=["analysis.spending"],
            selected_agents=["analysis_agent"],
            model_profiles=["reasoning"],
            requires_confirmation=False,
            requires_guardrail=False,
            response_hint="fallback analyze",
        )

    def plan(
        self,
        message: str,
        session_id: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> GraphPlanningResult:
        actual_session_id = self._get_or_create_session_id(session_id)
        logger.info("AI runtime plan start: session=%s", actual_session_id)
        graph = self._build_graph()
        if graph is None:
            return self._fallback_plan(actual_session_id, message)

        input_state = {
            "session_id": actual_session_id,
            "message": message,
            "history": history or [],
            "context": context or {},
        }
        result = graph.invoke(input_state, config=self._build_config(actual_session_id))
        logger.info(
            "AI runtime plan finished: session=%s intent=%s skills=%s agents=%s",
            actual_session_id,
            result.get("intent", "analyze"),
            result.get("selected_skills", []),
            result.get("selected_agents", []),
        )
        return GraphPlanningResult(
            session_id=actual_session_id,
            intent=result.get("intent", "analyze"),
            selected_skills=result.get("selected_skills", []),
            selected_agents=result.get("selected_agents", []),
            model_profiles=result.get("model_profiles", []),
            requires_confirmation=result.get("requires_confirmation", False),
            requires_guardrail=result.get("requires_guardrail", False),
            response_hint=result.get("response_hint", ""),
        )

    async def plan_stream(
        self,
        message: str,
        session_id: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        actual_session_id = self._get_or_create_session_id(session_id)
        yield {"type": "session", "session_id": actual_session_id}

        graph = self._build_graph()
        if graph is None:
            plan = self._fallback_plan(actual_session_id, message)
            yield {"type": "progress", "stage": "fallback", "message": "LangGraph 不可用，已降级为最小路由"}
            for skill in plan.selected_skills:
                yield {"type": "skill", "skill_id": skill}
            for agent in plan.selected_agents:
                yield {"type": "agent", "agent_id": agent}
            return

        input_state = {
            "session_id": actual_session_id,
            "message": message,
            "history": history or [],
            "context": context or {},
        }
        config = self._build_config(actual_session_id)
        try:
            async for chunk in self._astream_updates(input_state, config):
                for node_name, update in chunk.items():
                    yield {"type": "progress", "stage": node_name, "message": f"{node_name} 完成"}
                    if "selected_skills" in update:
                        for skill in update["selected_skills"]:
                            yield {"type": "skill", "skill_id": skill}
                    if "selected_agents" in update:
                        for agent in update["selected_agents"]:
                            yield {"type": "agent", "agent_id": agent}
        except Exception as exc:
            logger.warning("plan_stream 降级为同步 plan: %s", exc)
            # 某些 LangGraph 版本或 checkpointer 组合不支持 astream，退回线程执行同步 plan
            plan = await asyncio.to_thread(self.plan, message, actual_session_id, history, context)
            yield {"type": "progress", "stage": "plan", "message": "graph 规划完成"}
            for skill in plan.selected_skills:
                yield {"type": "skill", "skill_id": skill}
            for agent in plan.selected_agents:
                yield {"type": "agent", "agent_id": agent}

    def list_skills(self) -> list[Dict[str, Any]]:
        return [
            {
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "agent_id": skill.agent_id,
                "write_policy": skill.write_policy,
            }
            for skill in self.skill_registry.list_skills()
        ]

    def list_agents(self) -> list[Dict[str, Any]]:
        return [
            {
                "id": agent.id,
                "name": agent.name,
                "description": agent.description,
                "model_profile": agent.model_profile,
                "write_policy": agent.write_policy,
            }
            for agent in self.agent_registry.list_agents()
        ]

    def list_models(self) -> list[Dict[str, Any]]:
        return [
            {
                "profile_id": profile.profile_id,
                "provider": profile.provider,
                "model_name": profile.model_name,
                "base_url": profile.base_url,
                "temperature": profile.temperature,
            }
            for profile in self.model_registry.list_profiles()
        ]

    def execute_readonly_skills(
        self,
        message: str,
        plan: GraphPlanningResult,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[ToolExecutionResult]:
        readonly_skills = [
            skill_id
            for skill_id in plan.selected_skills
            if skill_id in {
                "transaction.record",
                "transaction.query",
                "analysis.spending",
                "budget.inspect",
                "budget.plan",
                "report.explain",
                "recurring.manage",
                "account.classify",
                "account.manage",
            }
        ]
        logger.info(
            "AI runtime execute_readonly_skills: session=%s skills=%s",
            plan.session_id,
            readonly_skills,
        )
        return self.tool_executor.run(message, readonly_skills, context)

    def build_system_context(
        self,
        results: List[ToolExecutionResult],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        return self.tool_executor.build_system_context(results, context=context)
