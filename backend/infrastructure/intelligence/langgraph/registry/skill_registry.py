"""Skill 注册表。"""

from __future__ import annotations

from typing import Dict, Iterable

from backend.infrastructure.intelligence.langgraph.skills.base import SkillDefinition


class SkillRegistry:
    """统一管理内置 Skill。"""

    def __init__(self) -> None:
        self._skills: Dict[str, SkillDefinition] = {
            "transaction.record": SkillDefinition(
                id="transaction.record",
                name="自然语言记账",
                description="将自然语言描述转成交易草稿",
                intents=("record_transaction",),
                agent_id="ledger_agent",
                tools=("query_accounts", "draft_transaction"),
                write_policy="confirm_required",
                priority=10,
            ),
            "transaction.query": SkillDefinition(
                id="transaction.query",
                name="交易查询",
                description="查询交易并解释结果",
                intents=("query_transaction",),
                agent_id="analysis_agent",
                tools=("query_transactions",),
                priority=20,
            ),
            "analysis.spending": SkillDefinition(
                id="analysis.spending",
                name="支出分析",
                description="分析支出趋势和异常",
                intents=("analyze",),
                agent_id="analysis_agent",
                tools=("query_transactions", "query_statistics"),
                priority=20,
            ),
            "budget.inspect": SkillDefinition(
                id="budget.inspect",
                name="预算执行解释",
                description="解释预算执行情况",
                intents=("budget",),
                agent_id="budget_agent",
                tools=("query_budgets",),
                priority=20,
            ),
            "budget.plan": SkillDefinition(
                id="budget.plan",
                name="预算规划",
                description="生成预算建议和预算草稿",
                intents=("budget",),
                agent_id="budget_agent",
                tools=("query_budgets", "draft_budget"),
                write_policy="confirm_required",
                priority=30,
            ),
            "report.explain": SkillDefinition(
                id="report.explain",
                name="报表解释",
                description="解释报表和明细数据",
                intents=("report",),
                agent_id="report_agent",
                tools=("query_reports",),
                priority=20,
            ),
            "recurring.manage": SkillDefinition(
                id="recurring.manage",
                name="周期交易管理",
                description="查询和草拟周期交易规则",
                intents=("recurring",),
                agent_id="recurring_agent",
                tools=("query_recurring_rules", "draft_recurring_rule"),
                write_policy="confirm_required",
                priority=20,
            ),
            "account.classify": SkillDefinition(
                id="account.classify",
                name="账户分类建议",
                description="推荐账户分类并解释账户树",
                intents=("account",),
                agent_id="account_agent",
                tools=("query_accounts",),
                priority=20,
            ),
            "account.manage": SkillDefinition(
                id="account.manage",
                name="账户管理",
                description="草拟开户或关户动作",
                intents=("account",),
                agent_id="account_agent",
                tools=("query_accounts", "draft_account_action"),
                write_policy="confirm_required",
                priority=30,
            ),
        }

    def get(self, skill_id: str) -> SkillDefinition | None:
        return self._skills.get(skill_id)

    def list_skills(self) -> list[SkillDefinition]:
        return [skill for skill in self._skills.values() if skill.enabled]

    def get_by_intent(self, intent: str) -> list[SkillDefinition]:
        matches = [skill for skill in self.list_skills() if intent in skill.intents]
        return sorted(matches, key=lambda skill: skill.priority)

    def get_many(self, skill_ids: Iterable[str]) -> list[SkillDefinition]:
        result = []
        for skill_id in skill_ids:
            skill = self.get(skill_id)
            if skill and skill.enabled:
                result.append(skill)
        return result
