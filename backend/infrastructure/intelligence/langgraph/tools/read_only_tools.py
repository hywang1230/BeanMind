"""阶段 2：只读 AI 工具。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload

from backend.config.dependencies import get_beancount_service, get_db_session
from backend.application.services.account_service import AccountApplicationService
from backend.application.services.recurring_service import RecurringApplicationService
from backend.application.services.transaction_service import TransactionApplicationService
from backend.domain.budget.entities.budget import Budget, CycleType, PeriodType
from backend.domain.budget.entities.budget_item import BudgetItem
from backend.domain.budget.services.budget_execution_service import BudgetExecutionService
from backend.infrastructure.intelligence.langgraph.tools.account_inference import AccountInferenceEngine
from backend.infrastructure.persistence.beancount.repositories import (
    AccountRepositoryImpl,
    TransactionRepositoryImpl,
)
from backend.infrastructure.persistence.db.models.budget import Budget as BudgetModel
from backend.infrastructure.persistence.db.models.recurring import RecurringRule as RecurringRuleModel


@dataclass
class ToolExecutionResult:
    """工具执行结果。"""

    tool_name: str
    skill_id: str
    payload: Dict[str, Any]


class ReadOnlyToolExecutor:
    """只读工具执行器。"""

    def _get_ai_preferences(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        context = context or {}
        preferences = context.get("ai_preferences")
        return preferences if isinstance(preferences, dict) else {}

    def _build_transaction_service(self) -> Tuple[TransactionApplicationService, Any]:
        db = get_db_session()
        beancount_service = get_beancount_service()
        transaction_repo = TransactionRepositoryImpl(beancount_service, db)
        account_repo = AccountRepositoryImpl(beancount_service)
        return TransactionApplicationService(transaction_repo, account_repo), db

    def _build_account_service(self) -> AccountApplicationService:
        beancount_service = get_beancount_service()
        account_repo = AccountRepositoryImpl(beancount_service)
        return AccountApplicationService(account_repo)

    def _resolve_date_range(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, str, str]:
        context = context or {}
        date_range = context.get("date_range") or {}
        start = date_range.get("start_date") or date_range.get("start")
        end = date_range.get("end_date") or date_range.get("end")
        if start and end:
            return start, end, "context"

        today = datetime.now().date()
        lower = message.lower()

        if "今天" in message or "今日" in message:
            return today.isoformat(), today.isoformat(), "today"
        if "昨天" in message or "昨日" in message:
            target = today - timedelta(days=1)
            return target.isoformat(), target.isoformat(), "yesterday"
        if "本周" in message:
            start_date = today - timedelta(days=today.weekday())
            return start_date.isoformat(), today.isoformat(), "this_week"
        if "上周" in message:
            this_week_start = today - timedelta(days=today.weekday())
            start_date = this_week_start - timedelta(days=7)
            end_date = this_week_start - timedelta(days=1)
            return start_date.isoformat(), end_date.isoformat(), "last_week"
        if "上月" in message or "上个月" in message:
            first_of_this_month = today.replace(day=1)
            end_date = first_of_this_month - timedelta(days=1)
            start_date = end_date.replace(day=1)
            return start_date.isoformat(), end_date.isoformat(), "last_month"
        if "本月" in message:
            start_date = today.replace(day=1)
            return start_date.isoformat(), today.isoformat(), "this_month"
        if "本年" in message or "今年" in message:
            start_date = today.replace(month=1, day=1)
            return start_date.isoformat(), today.isoformat(), "this_year"
        if "最近7天" in message or "近7天" in message:
            start_date = today - timedelta(days=6)
            return start_date.isoformat(), today.isoformat(), "last_7_days"
        if "最近30天" in message or "近30天" in message:
            start_date = today - timedelta(days=29)
            return start_date.isoformat(), today.isoformat(), "last_30_days"

        return (today.replace(day=1).isoformat(), today.isoformat(), "default_this_month")

    def _resolve_transaction_date(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        start_date, end_date, resolved_from = self._resolve_date_range(message, context)
        if resolved_from in {"today", "yesterday"}:
            return start_date
        return end_date

    def _get_account_names(self) -> List[str]:
        account_service = self._build_account_service()
        accounts = account_service.get_all_accounts(active_only=True)
        return sorted([item["name"] for item in accounts])

    def _infer_transaction_kind(self, message: str) -> str:
        if any(keyword in message for keyword in ["收入", "工资", "报销", "退款", "奖金", "收了", "收到"]):
            return "income"
        if any(keyword in message for keyword in ["转账", "转给", "转到"]):
            return "transfer"
        return "expense"

    def _parse_amount_and_currency(self, message: str) -> Tuple[Optional[str], str]:
        patterns = [
            r"(\d+(?:\.\d+)?)\s*(?:元|块|rmb|cny)",
            r"(?:\$|usd\s*)(\d+(?:\.\d+)?)",
            r"(\d+(?:\.\d+)?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                amount = Decimal(match.group(1)).quantize(Decimal("0.01"))
                upper_message = message.upper()
                if "USD" in upper_message or "$" in message:
                    return str(amount), "USD"
                if "EUR" in upper_message or "€" in message:
                    return str(amount), "EUR"
                return str(amount), "CNY"
        return None, "CNY"

    def _list_recent_transactions(self) -> List[Dict[str, Any]]:
        service, db = self._build_transaction_service()
        try:
            return service.get_transactions(limit=50, offset=0)[:50]
        finally:
            db.close()

    def _build_inference_engine(
        self,
        account_names: List[str],
        preferences: Optional[Dict[str, Any]] = None,
        recent_transactions: Optional[List[Dict[str, Any]]] = None,
    ) -> AccountInferenceEngine:
        return AccountInferenceEngine(
            account_names=account_names,
            preferences=preferences,
            recent_transactions=recent_transactions,
        )

    def _select_funding_account(
        self,
        account_names: List[str],
        message: str,
        preferences: Optional[Dict[str, Any]] = None,
        recent_transactions: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        engine = self._build_inference_engine(account_names, preferences, recent_transactions)
        decision = engine.infer_funding_account(message)
        return decision.selected_account, {
            "selected": decision.selected_account,
            "candidates": decision.candidates,
            "confidence": decision.confidence,
            "source": decision.source,
        }

    def _select_counterparty_account(
        self,
        account_names: List[str],
        message: str,
        txn_kind: str,
        preferences: Optional[Dict[str, Any]] = None,
        payee: Optional[str] = None,
        recent_transactions: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        engine = self._build_inference_engine(account_names, preferences, recent_transactions)
        decision = engine.infer_counterparty_account(message, txn_kind, payee)
        return decision.selected_account, {
            "selected": decision.selected_account,
            "candidates": decision.candidates,
            "confidence": decision.confidence,
            "source": decision.source,
        }

    def _resolve_budget_start_date(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        today = datetime.now().date()
        if "下月" in message or "下个月" in message:
            if today.month == 12:
                return date(today.year + 1, 1, 1).isoformat()
            return date(today.year, today.month + 1, 1).isoformat()
        start_date, _, _ = self._resolve_date_range(message, context)
        return start_date

    def _infer_payee(self, message: str) -> Optional[str]:
        for marker in ["在", "给", "向"]:
            if marker in message:
                fragment = message.split(marker, 1)[1].strip()
                fragment = re.split(r"花了|消费|付了|支付|买了|收入|收到", fragment)[0].strip(" ，。,.")
                if 1 <= len(fragment) <= 30:
                    return fragment
        return None

    def _infer_description(
        self,
        message: str,
        txn_kind: str,
        payee: Optional[str],
        related_accounts: List[str],
        account_names: List[str],
        preferences: Optional[Dict[str, Any]] = None,
        recent_transactions: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        engine = self._build_inference_engine(account_names, preferences, recent_transactions)
        decision = engine.infer_description(message, txn_kind, payee, related_accounts)
        return decision.text, {
            "selected": decision.text,
            "confidence": decision.confidence,
            "source": decision.source,
        }

    def query_transactions(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ToolExecutionResult:
        start_date, end_date, resolved_from = self._resolve_date_range(message, context)
        service, db = self._build_transaction_service()
        try:
            transactions = service.get_transactions(
                start_date=start_date,
                end_date=end_date,
                limit=20,
                offset=0,
            )
        finally:
            db.close()

        simplified = []
        for txn in transactions[:10]:
            posting_summaries = []
            total_amount = None
            for posting in txn.get("postings", [])[:4]:
                posting_amount = posting.get("amount")
                posting_summaries.append(
                    {
                        "account": posting.get("account"),
                        "amount": posting_amount,
                        "currency": posting.get("currency"),
                    }
                )
            if txn.get("transaction_type") == "expense":
                total_amount = next(
                    (
                        abs(float(posting.get("amount", 0)))
                        for posting in txn.get("postings", [])
                        if str(posting.get("account", "")).startswith("Expenses:")
                    ),
                    None,
                )
            elif txn.get("transaction_type") == "income":
                total_amount = next(
                    (
                        abs(float(posting.get("amount", 0)))
                        for posting in txn.get("postings", [])
                        if str(posting.get("account", "")).startswith("Income:")
                    ),
                    None,
                )
            simplified.append(
                {
                    "id": txn["id"],
                    "date": txn["date"],
                    "description": txn.get("description"),
                    "payee": txn.get("payee"),
                    "transaction_type": txn.get("transaction_type"),
                    "amount": total_amount,
                    "accounts": txn.get("accounts", [])[:4],
                    "currencies": txn.get("currencies", []),
                    "postings": posting_summaries,
                }
            )

        return ToolExecutionResult(
            tool_name="query_transactions",
            skill_id="transaction.query",
            payload={
                "date_range": {"start_date": start_date, "end_date": end_date, "resolved_from": resolved_from},
                "total": len(transactions),
                "transactions": simplified,
            },
        )

    def classify_account(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ToolExecutionResult:
        account_names = self._get_account_names()
        account_service = self._build_account_service()
        preferences = self._get_ai_preferences(context)
        recent_transactions = self._list_recent_transactions()
        summary = account_service.get_account_summary()
        related_accounts = []
        suggested_account = None
        suggestion_reason = "根据关键词和账户前缀做的最小推荐。"

        if any(keyword in message for keyword in ["工资", "收入", "奖金", "报销", "退款"]):
            suggested_account, decision = self._select_counterparty_account(
                account_names,
                message,
                "income",
                preferences,
                recent_transactions=recent_transactions,
            )
            related_accounts = [name for name in account_names if name.startswith("Income:")][:5]
            suggestion_reason = f"基于收入账户推断，来源: {decision['source']}。"
        elif any(keyword in message for keyword in ["账户", "余额", "资金", "银行卡", "现金", "信用卡", "卡"]):
            suggested_account, decision = self._select_funding_account(
                account_names,
                message,
                preferences,
                recent_transactions=recent_transactions,
            )
            related_accounts = [name for name in account_names if name.startswith(("Assets:", "Liabilities:"))][:5]
            suggestion_reason = f"基于资金账户推断，来源: {decision['source']}。"
        else:
            suggested_account, decision = self._select_counterparty_account(
                account_names,
                message,
                "expense",
                preferences,
                recent_transactions=recent_transactions,
            )
            related_accounts = [name for name in account_names if name.startswith("Expenses:")][:5]
            suggestion_reason = f"基于支出账户推断，来源: {decision['source']}。"

        return ToolExecutionResult(
            tool_name="classify_account",
            skill_id="account.classify",
            payload={
                "suggested_account": suggested_account,
                "reason": suggestion_reason,
                "related_accounts": related_accounts,
                "account_summary": summary,
            },
        )

    def draft_account_action(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ToolExecutionResult:
        account_names = self._get_account_names()
        action = "create"
        draft: Dict[str, Any] = {}
        missing_fields: List[str] = []
        assumptions: Dict[str, Any] = {}

        if any(keyword in message for keyword in ["关闭账户", "关户", "停用账户", "关闭科目"]):
            action = "close"
            matched_account = next((name for name in account_names if name in message), None)
            draft = {
                "action": "close",
                "account_name": matched_account,
                "close_date": self._resolve_transaction_date(message, context),
            }
            if not matched_account:
                missing_fields.append("account_name")
        else:
            account_type = "Assets"
            if any(keyword in message for keyword in ["收入", "工资"]):
                account_type = "Income"
            elif any(keyword in message for keyword in ["支出", "餐饮", "交通", "房租"]):
                account_type = "Expenses"
            elif any(keyword in message for keyword in ["负债", "信用卡", "借款"]):
                account_type = "Liabilities"

            raw_name = None
            matched = re.search(r"(?:新建|创建|开户|增加)(?:一个)?账户[:：]?\s*([A-Za-z\u4e00-\u9fa5:_-]+)", message)
            if matched:
                raw_name = matched.group(1).strip()
            if raw_name and ":" in raw_name:
                account_name = raw_name
            elif raw_name:
                account_name = f"{account_type}:{raw_name}"
            else:
                account_name = None

            draft = {
                "action": "create",
                "name": account_name,
                "account_type": account_type,
                "currencies": ["CNY"],
                "open_date": self._resolve_transaction_date(message, context),
            }
            assumptions["account_type"] = account_type
            if not account_name:
                missing_fields.append("name")

        return ToolExecutionResult(
            tool_name="draft_account_action",
            skill_id="account.manage",
            payload={
                "draft": draft,
                "missing_fields": missing_fields,
                "assumptions": assumptions,
                "status": "draft_only_not_committed",
                "action": action,
            },
        )

    def draft_transaction(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ToolExecutionResult:
        account_names = self._get_account_names()
        preferences = self._get_ai_preferences(context)
        recent_transactions = self._list_recent_transactions()
        txn_kind = self._infer_transaction_kind(message)
        amount, currency = self._parse_amount_and_currency(message)
        preferred_currency = preferences.get("preferred_currency")
        if preferred_currency and "cny" not in message.lower() and "usd" not in message.lower() and "eur" not in message.lower():
            currency = preferred_currency
        txn_date = self._resolve_transaction_date(message, context)
        payee = self._infer_payee(message)
        asset_account, funding_decision = self._select_funding_account(
            account_names,
            message,
            preferences,
            recent_transactions=recent_transactions,
        )
        counterparty_account, counterparty_decision = self._select_counterparty_account(
            account_names,
            message,
            txn_kind,
            preferences,
            payee=payee,
            recent_transactions=recent_transactions,
        )
        related_accounts = [account for account in [asset_account, counterparty_account] if account]
        description, description_decision = self._infer_description(
            message,
            txn_kind,
            payee,
            related_accounts,
            account_names,
            preferences,
            recent_transactions,
        )

        missing_fields: List[str] = []
        postings: List[Dict[str, Any]] = []

        if amount is None:
            missing_fields.append("amount")
        if asset_account is None:
            missing_fields.append("funding_account")
        if counterparty_account is None:
            missing_fields.append("counterparty_account")
        else:
            if txn_kind == "income" and asset_account and counterparty_account:
                postings = [
                    {"account": asset_account, "amount": amount, "currency": currency},
                    {"account": counterparty_account, "amount": f"-{amount}", "currency": currency},
                ]
            elif txn_kind == "transfer":
                missing_fields.append("target_account")
            elif asset_account and counterparty_account:
                postings = [
                    {"account": counterparty_account, "amount": amount, "currency": currency},
                    {"account": asset_account, "amount": f"-{amount}", "currency": currency},
                ]

        confidence = 0.85
        if missing_fields:
            confidence = 0.35
        elif payee is None:
            confidence = 0.65

        return ToolExecutionResult(
            tool_name="draft_transaction",
            skill_id="transaction.record",
            payload={
                "draft": {
                    "date": txn_date,
                    "description": description,
                    "payee": payee,
                    "postings": postings,
                    "tags": [],
                    "links": [],
                },
                "transaction_kind": txn_kind,
                "confidence": confidence,
                "missing_fields": missing_fields,
                "assumptions": {
                    "asset_account": asset_account,
                    "counterparty_account": counterparty_account,
                    "currency": currency,
                    "funding_account_inference": funding_decision,
                    "counterparty_account_inference": counterparty_decision,
                    "description_inference": description_decision,
                },
                "status": "draft_only_not_committed",
            },
        )

    def analyze_spending(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ToolExecutionResult:
        start_date, end_date, resolved_from = self._resolve_date_range(message, context)
        service, db = self._build_transaction_service()
        try:
            transactions = service.get_transactions(
                start_date=start_date,
                end_date=end_date,
                transaction_type="expense",
                limit=500,
                offset=0,
            )
        finally:
            db.close()

        total_expense = Decimal("0")
        category_totals: Dict[str, Decimal] = {}

        for txn in transactions:
            for posting in txn.get("postings", []):
                account = posting.get("account", "")
                if not account.startswith("Expenses:"):
                    continue

                amount = Decimal(str(posting.get("amount", "0")))
                normalized = abs(amount)
                total_expense += normalized

                parts = account.split(":")
                category = parts[1] if len(parts) > 1 else "其他"
                category_totals[category] = category_totals.get(category, Decimal("0")) + normalized

        sorted_categories = sorted(category_totals.items(), key=lambda item: item[1], reverse=True)
        top_categories = []
        for category, amount in sorted_categories[:5]:
            percentage = float((amount / total_expense * 100)) if total_expense > 0 else 0.0
            top_categories.append(
                {
                    "category": category,
                    "amount": float(amount),
                    "percentage": round(percentage, 2),
                }
            )

        return ToolExecutionResult(
            tool_name="analyze_spending",
            skill_id="analysis.spending",
            payload={
                "date_range": {"start_date": start_date, "end_date": end_date, "resolved_from": resolved_from},
                "transaction_count": len(transactions),
                "total_expense": float(total_expense),
                "top_categories": top_categories,
            },
        )

    def inspect_budget(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ToolExecutionResult:
        start_date, end_date, resolved_from = self._resolve_date_range(message, context)
        service, db = self._build_transaction_service()
        try:
            stmt = (
                select(BudgetModel)
                .options(selectinload(BudgetModel.items))
                .where(
                    and_(
                        BudgetModel.is_active == True,  # noqa: E712
                        BudgetModel.start_date <= date.fromisoformat(end_date),
                        (BudgetModel.end_date == None) | (BudgetModel.end_date >= date.fromisoformat(start_date)),  # noqa: E711
                    )
                )
            )
            models = db.execute(stmt).scalars().all()
            execution_service = BudgetExecutionService(service.transaction_repository)
            budgets = [self._budget_model_to_entity(model) for model in models]
            executions = execution_service.calculate_all_budgets_execution(budgets)
        finally:
            db.close()

        budget_summaries = []
        for budget, execution in zip(budgets, executions):
            budget_summaries.append(
                {
                    "id": budget.id,
                    "name": budget.name,
                    "amount": float(budget.amount),
                    "spent": float(execution.total_spent),
                    "remaining": float(execution.remaining),
                    "execution_rate": round(execution.execution_rate, 2),
                    "status": execution.status.value,
                }
            )

        return ToolExecutionResult(
            tool_name="inspect_budget",
            skill_id="budget.inspect",
            payload={
                "date_range": {"start_date": start_date, "end_date": end_date, "resolved_from": resolved_from},
                "budget_count": len(budget_summaries),
                "budgets": budget_summaries[:5],
            },
        )

    def draft_budget_plan(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ToolExecutionResult:
        analysis = self.analyze_spending(message, context)
        payload = analysis.payload
        account_names = self._get_account_names()
        suggestions = []
        items = []
        for item in payload.get("top_categories", [])[:5]:
            base_amount = Decimal(str(item.get("amount", 0)))
            suggested_amount = (base_amount * Decimal("1.10")).quantize(Decimal("0.01"))
            category = item.get("category")
            account_pattern = next(
                (name for name in account_names if name.startswith("Expenses:") and category in name),
                None,
            ) or "Expenses:*"
            suggestions.append(
                {
                    "category": category,
                    "historical_amount": float(base_amount),
                    "suggested_budget_amount": float(suggested_amount),
                    "currency": "CNY",
                    "account_pattern": account_pattern,
                }
            )
            items.append(
                {
                    "account_pattern": account_pattern,
                    "amount": float(suggested_amount),
                    "currency": "CNY",
                }
            )

        start_date = self._resolve_budget_start_date(message, context)
        start_dt = date.fromisoformat(start_date)
        budget_name = f"{start_dt.year}年{start_dt.month}月 AI预算建议"
        total_amount = float(sum(Decimal(str(item["amount"])) for item in items)) if items else 0.0

        return ToolExecutionResult(
            tool_name="draft_budget_plan",
            skill_id="budget.plan",
            payload={
                "date_range": payload.get("date_range"),
                "basis": "基于最近周期支出上浮 10% 生成的最小预算建议草稿。",
                "suggestions": suggestions,
                "draft": {
                    "name": budget_name,
                    "amount": total_amount,
                    "period_type": "MONTHLY",
                    "start_date": start_date,
                    "end_date": None,
                    "items": items,
                    "cycle_type": "NONE",
                    "carry_over_enabled": False,
                },
                "missing_fields": [] if items else ["items", "amount"],
                "status": "draft_only_not_committed",
            },
        )

    def explain_report(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ToolExecutionResult:
        beancount_service = get_beancount_service()
        start_date, end_date, resolved_from = self._resolve_date_range(message, context)

        if any(keyword in message for keyword in ["资产负债", "净资产", "资产情况", "余额概览", "账户余额", "balance sheet"]):
            target_date = date.fromisoformat(end_date)
            exchange_rates = beancount_service.get_all_exchange_rates(to_currency="CNY", as_of_date=target_date)
            balances = beancount_service.get_account_balances(as_of_date=target_date)

            total_assets = Decimal("0")
            total_liabilities = Decimal("0")
            total_equity = Decimal("0")

            for account_name, account_balances in balances.items():
                for currency, amount in account_balances.items():
                    converted = amount * exchange_rates.get(currency, Decimal("1"))
                    if account_name.startswith("Assets:"):
                        total_assets += converted
                    elif account_name.startswith("Liabilities:"):
                        total_liabilities += converted
                    elif account_name.startswith("Equity:"):
                        total_equity += converted

            return ToolExecutionResult(
                tool_name="explain_report",
                skill_id="report.explain",
                payload={
                    "report_type": "balance_sheet",
                    "as_of_date": target_date.isoformat(),
                    "total_assets_cny": float(total_assets),
                    "total_liabilities_cny": float(abs(total_liabilities)),
                    "total_equity_cny": float(abs(total_equity)),
                    "net_worth_cny": float(total_assets + total_liabilities),
                },
            )

        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        transactions = beancount_service.get_transactions(start_date=start, end_date=end)
        exchange_rates = beancount_service.get_all_exchange_rates(to_currency="CNY", as_of_date=end)
        income_total = Decimal("0")
        expense_total = Decimal("0")
        expense_categories: Dict[str, Decimal] = {}

        for txn in transactions:
            for posting in txn.get("postings", []):
                account = posting.get("account", "")
                currency = posting.get("currency", "CNY")
                amount = Decimal(str(posting.get("amount", 0)))
                rate = exchange_rates.get(currency, Decimal("1"))
                converted = amount * rate

                if account.startswith("Income:"):
                    income_total += abs(converted)
                elif account.startswith("Expenses:"):
                    normalized = abs(converted)
                    expense_total += normalized
                    parts = account.split(":")
                    category = parts[1] if len(parts) > 1 else "其他"
                    expense_categories[category] = expense_categories.get(category, Decimal("0")) + normalized

        top_expense_categories = sorted(
            (
                {"category": category, "amount": float(amount)}
                for category, amount in expense_categories.items()
            ),
            key=lambda item: item["amount"],
            reverse=True,
        )[:5]

        return ToolExecutionResult(
            tool_name="explain_report",
            skill_id="report.explain",
            payload={
                "report_type": "income_statement",
                "start_date": start_date,
                "end_date": end_date,
                "resolved_from": resolved_from,
                "income_total_cny": float(income_total),
                "expense_total_cny": float(expense_total),
                "net_profit_cny": float(income_total - expense_total),
                "top_expense_categories": top_expense_categories,
            },
        )

    def inspect_recurring_rules(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ToolExecutionResult:
        check_date = date.fromisoformat(self._resolve_transaction_date(message, context))
        db = get_db_session()
        try:
            service = RecurringApplicationService(db)
            active_rules = (
                db.query(RecurringRuleModel)
                .filter(RecurringRuleModel.is_active == True)  # noqa: E712
                .all()
            )
            pending_rules = service.get_pending_rules(check_date)
        finally:
            db.close()

        simplified_active_rules = [
            {
                "id": rule.id,
                "name": rule.name,
                "frequency": rule.frequency,
                "start_date": rule.start_date.isoformat() if rule.start_date else None,
                "end_date": rule.end_date.isoformat() if rule.end_date else None,
            }
            for rule in active_rules[:5]
        ]

        return ToolExecutionResult(
            tool_name="inspect_recurring_rules",
            skill_id="recurring.manage",
            payload={
                "check_date": check_date.isoformat(),
                "active_rule_count": len(active_rules),
                "active_rules": simplified_active_rules,
                "pending_rule_count": len(pending_rules),
                "pending_rules": pending_rules[:5],
            },
        )

    def draft_recurring_rule(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ToolExecutionResult:
        txn_result = self.draft_transaction(message, context)
        txn_payload = txn_result.payload
        txn_draft = txn_payload.get("draft", {})
        txn_kind = txn_payload.get("transaction_kind", "expense")
        start_date = self._resolve_transaction_date(message, context)
        start_dt = date.fromisoformat(start_date)

        frequency = "MONTHLY"
        frequency_config: Dict[str, Any] = {"month_days": [start_dt.day]}
        if "每天" in message or "每日" in message:
            frequency = "DAILY"
            frequency_config = {}
        elif "每周" in message or "每星期" in message:
            frequency = "WEEKLY"
            frequency_config = {"weekdays": [start_dt.isoweekday()]}
        elif "每两周" in message or "隔周" in message:
            frequency = "BIWEEKLY"
            frequency_config = {"weekdays": [start_dt.isoweekday()]}
        elif "每年" in message:
            frequency = "YEARLY"
            frequency_config = {"month_days": [start_dt.day]}

        draft = {
            "name": f"{txn_draft.get('description') or '周期记账'}规则",
            "frequency": frequency.lower(),
            "frequency_config": frequency_config,
            "transaction_template": {
                "description": txn_draft.get("description") or "周期记账",
                "postings": txn_draft.get("postings") or [],
                "payee": txn_draft.get("payee"),
                "tags": (txn_draft.get("tags") or []) + ["recurring"],
            },
            "start_date": start_date,
            "end_date": None,
            "is_active": True,
        }

        missing_fields = list(txn_payload.get("missing_fields") or [])
        if not draft["transaction_template"]["postings"]:
            missing_fields.append("transaction_template.postings")

        return ToolExecutionResult(
            tool_name="draft_recurring_rule",
            skill_id="recurring.manage",
            payload={
                "draft": draft,
                "transaction_kind": txn_kind,
                "missing_fields": sorted(set(missing_fields)),
                "assumptions": {
                    "frequency": frequency.lower(),
                    "frequency_config": frequency_config,
                },
                "status": "draft_only_not_committed",
            },
        )

    def _budget_model_to_entity(self, model: BudgetModel) -> Budget:
        items = []
        for item_model in model.items:
            items.append(
                BudgetItem(
                    id=item_model.id,
                    budget_id=item_model.budget_id,
                    account_pattern=item_model.account_pattern,
                    amount=Decimal(str(item_model.amount)),
                    currency=item_model.currency,
                    spent=Decimal(str(item_model.spent)),
                    created_at=item_model.created_at,
                    updated_at=item_model.updated_at,
                )
            )

        return Budget(
            id=model.id,
            user_id=model.user_id,
            name=model.name,
            amount=Decimal(str(model.amount)),
            period_type=PeriodType(model.period_type),
            start_date=model.start_date,
            end_date=model.end_date,
            is_active=model.is_active,
            items=items,
            created_at=model.created_at,
            updated_at=model.updated_at,
            cycle_type=CycleType(model.cycle_type),
            carry_over_enabled=model.carry_over_enabled,
        )

    def run(
        self,
        message: str,
        skill_ids: List[str],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[ToolExecutionResult]:
        results: List[ToolExecutionResult] = []

        if "transaction.query" in skill_ids:
            results.append(self.query_transactions(message, context))

        if "transaction.record" in skill_ids:
            results.append(self.draft_transaction(message, context))

        if "analysis.spending" in skill_ids:
            results.append(self.analyze_spending(message, context))

        if "budget.inspect" in skill_ids:
            results.append(self.inspect_budget(message, context))

        if "budget.plan" in skill_ids:
            results.append(self.draft_budget_plan(message, context))

        if "report.explain" in skill_ids:
            results.append(self.explain_report(message, context))

        if "recurring.manage" in skill_ids:
            results.append(self.inspect_recurring_rules(message, context))
            if any(keyword in message for keyword in ["每月", "每周", "每天", "隔周", "定期", "自动记", "周期记"]):
                results.append(self.draft_recurring_rule(message, context))

        if "account.classify" in skill_ids:
            results.append(self.classify_account(message, context))

        if "account.manage" in skill_ids and any(
            keyword in message for keyword in ["开户", "新建账户", "创建账户", "关闭账户", "关户", "停用账户"]
        ):
            results.append(self.draft_account_action(message, context))

        return results

    def build_system_context(
        self,
        results: List[ToolExecutionResult],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        if not results and not context:
            return None

        lines = [
            "以下是系统基于 BeanMind 当前账本和数据库查询到的只读事实，请优先基于这些事实回答。",
            "如果事实不足，再明确说明不足，不要编造数据。",
        ]

        context = context or {}
        source_page = context.get("source_page")
        selected_entity_id = context.get("selected_entity_id")
        date_range = context.get("date_range") or {}
        if source_page or selected_entity_id or date_range:
            context_parts = []
            if source_page:
                context_parts.append(f"来源页面 {source_page}")
            if selected_entity_id:
                context_parts.append(f"当前实体 {selected_entity_id}")
            if date_range.get("start_date") or date_range.get("end_date") or date_range.get("start") or date_range.get("end"):
                start_date = date_range.get("start_date") or date_range.get("start") or "未指定"
                end_date = date_range.get("end_date") or date_range.get("end") or "未指定"
                context_parts.append(f"页面时间范围 {start_date} 到 {end_date}")
            lines.append("[页面上下文] " + "，".join(context_parts))

        for result in results:
            payload = result.payload
            if result.skill_id == "transaction.query":
                lines.append(
                    f"[交易查询] 时间范围 {payload['date_range']['start_date']} 到 {payload['date_range']['end_date']}，"
                    f"共 {payload['total']} 笔，示例: {payload['transactions']}"
                )
            elif result.skill_id == "transaction.record":
                lines.append(
                    f"[记账草稿] 当前仅生成草稿，尚未写入账本。"
                    f"草稿 {payload['draft']}，缺失字段 {payload['missing_fields']}，"
                    f"假设 {payload['assumptions']}，置信度 {payload['confidence']}"
                )
            elif result.skill_id == "analysis.spending":
                lines.append(
                    f"[支出分析] 时间范围 {payload['date_range']['start_date']} 到 {payload['date_range']['end_date']}，"
                    f"支出交易 {payload['transaction_count']} 笔，总支出 {payload['total_expense']}，"
                    f"前五分类 {payload['top_categories']}"
                )
            elif result.skill_id == "budget.inspect":
                lines.append(
                    f"[预算检查] 时间范围 {payload['date_range']['start_date']} 到 {payload['date_range']['end_date']}，"
                    f"活跃预算 {payload['budget_count']} 个，摘要 {payload['budgets']}"
                )
            elif result.skill_id == "budget.plan":
                lines.append(
                    f"[预算草稿] 时间范围 {payload['date_range']['start_date']} 到 {payload['date_range']['end_date']}，"
                    f"建议依据 {payload['basis']}，预算草稿 {payload['suggestions']}"
                )
            elif result.skill_id == "report.explain":
                if payload["report_type"] == "balance_sheet":
                    lines.append(
                        f"[资产负债表] 截止 {payload['as_of_date']}，总资产 {payload['total_assets_cny']} CNY，"
                        f"总负债 {payload['total_liabilities_cny']} CNY，净资产 {payload['net_worth_cny']} CNY"
                    )
                else:
                    lines.append(
                        f"[利润表] 时间范围 {payload['start_date']} 到 {payload['end_date']}，"
                        f"收入 {payload['income_total_cny']} CNY，支出 {payload['expense_total_cny']} CNY，"
                        f"净利润 {payload['net_profit_cny']} CNY，支出分类 {payload['top_expense_categories']}"
                    )
            elif result.skill_id == "recurring.manage":
                lines.append(
                    f"[周期规则] 检查日期 {payload['check_date']}，"
                    f"启用规则 {payload['active_rule_count']} 个，待执行 {payload['pending_rule_count']} 个，"
                    f"待执行规则 {payload['pending_rules']}"
                )
            elif result.skill_id == "account.classify":
                lines.append(
                    f"[账户分类建议] 推荐账户 {payload['suggested_account']}，"
                    f"原因 {payload['reason']}，相关账户 {payload['related_accounts']}，"
                    f"账户摘要 {payload['account_summary']}"
                )
            elif result.skill_id == "account.manage":
                lines.append(
                    f"[账户草稿] 动作 {payload['action']}，草稿 {payload['draft']}，"
                    f"缺失字段 {payload['missing_fields']}，假设 {payload['assumptions']}"
                )

        return "\n".join(lines)
