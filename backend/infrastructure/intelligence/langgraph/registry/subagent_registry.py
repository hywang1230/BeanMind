"""SubAgent 注册表。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple


@dataclass(frozen=True)
class SubAgentDefinition:
    """专业 Agent 定义。"""

    id: str
    name: str
    description: str
    model_profile: str
    skills: Tuple[str, ...]
    tools: Tuple[str, ...] = field(default_factory=tuple)
    write_policy: str = "read_only"
    enabled: bool = True
    priority: int = 100


class SubAgentRegistry:
    """统一管理 SubAgent。"""

    def __init__(self) -> None:
        self._agents: Dict[str, SubAgentDefinition] = {
            "supervisor_agent": SubAgentDefinition(
                id="supervisor_agent",
                name="Supervisor Agent",
                description="负责总控、拆任务和结果汇总",
                model_profile="fast",
                skills=tuple(),
            ),
            "ledger_agent": SubAgentDefinition(
                id="ledger_agent",
                name="Ledger Agent",
                description="负责自然语言记账和交易草稿",
                model_profile="structured",
                skills=("transaction.record",),
                tools=("query_accounts", "draft_transaction"),
                write_policy="confirm_required",
                priority=10,
            ),
            "analysis_agent": SubAgentDefinition(
                id="analysis_agent",
                name="Analysis Agent",
                description="负责交易查询和消费分析",
                model_profile="reasoning",
                skills=("transaction.query", "analysis.spending"),
                tools=("query_transactions", "query_statistics"),
                priority=20,
            ),
            "budget_agent": SubAgentDefinition(
                id="budget_agent",
                name="Budget Agent",
                description="负责预算查询和预算规划",
                model_profile="reasoning",
                skills=("budget.inspect", "budget.plan"),
                tools=("query_budgets", "draft_budget"),
                write_policy="confirm_required",
                priority=20,
            ),
            "report_agent": SubAgentDefinition(
                id="report_agent",
                name="Report Agent",
                description="负责报表解释",
                model_profile="long_context",
                skills=("report.explain",),
                tools=("query_reports",),
                priority=30,
            ),
            "recurring_agent": SubAgentDefinition(
                id="recurring_agent",
                name="Recurring Agent",
                description="负责周期规则查询与草拟",
                model_profile="structured",
                skills=("recurring.manage",),
                tools=("query_recurring_rules", "draft_recurring_rule"),
                write_policy="confirm_required",
                priority=30,
            ),
            "account_agent": SubAgentDefinition(
                id="account_agent",
                name="Account Agent",
                description="负责账户分类和账户管理草拟",
                model_profile="structured",
                skills=("account.classify", "account.manage"),
                tools=("query_accounts", "draft_account_action"),
                write_policy="confirm_required",
                priority=30,
            ),
            "guardrail_agent": SubAgentDefinition(
                id="guardrail_agent",
                name="Guardrail Agent",
                description="负责风险校验和确认兜底",
                model_profile="guardrail",
                skills=tuple(),
                tools=tuple(),
                priority=5,
            ),
        }

    def get(self, agent_id: str) -> SubAgentDefinition | None:
        return self._agents.get(agent_id)

    def list_agents(self) -> list[SubAgentDefinition]:
        return [agent for agent in self._agents.values() if agent.enabled]
