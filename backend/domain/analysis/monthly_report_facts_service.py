"""月报结构化事实分析服务"""
from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Sequence

from backend.domain.transaction.entities import Transaction


ZERO = Decimal("0")
HUNDRED = Decimal("100")


@dataclass(frozen=True)
class MonthWindow:
    """月份时间窗"""

    month: str
    start_date: date
    end_date: date

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days + 1


class MonthlyReportFactsService:
    """基于交易和账户结构构建月报事实"""

    def build_facts(
        self,
        report_month: str,
        current_transactions: Sequence[Transaction],
        previous_transactions: Sequence[Transaction],
        recent_average_transactions: Sequence[Sequence[Transaction]],
        current_balances: Dict[str, Dict[str, Decimal]],
        previous_balances: Optional[Dict[str, Dict[str, Decimal]]] = None,
    ) -> Dict[str, Any]:
        window = self.parse_month(report_month)
        summary = self._calculate_summary(current_transactions, current_balances, previous_balances, window)
        spending_structure = self._calculate_spending_structure(current_transactions)
        change_analysis = self._calculate_change_analysis(
            current_transactions,
            previous_transactions,
            recent_average_transactions,
        )
        anomalies = self._detect_anomalies(current_transactions, spending_structure)
        cash_flow = self._calculate_cash_flow(current_transactions)
        investment = self._calculate_investment(current_transactions, current_balances, previous_balances)

        return {
            "report_month": report_month,
            "period": {
                "start_date": window.start_date.isoformat(),
                "end_date": window.end_date.isoformat(),
                "days": window.days,
            },
            "summary_metrics": summary,
            "spending_structure": spending_structure,
            "change_analysis": change_analysis,
            "anomalies": anomalies,
            "cash_flow": cash_flow,
            "investment": investment,
        }

    @staticmethod
    def parse_month(report_month: str) -> MonthWindow:
        year, month = report_month.split("-")
        month_int = int(month)
        year_int = int(year)
        start_date = date(year_int, month_int, 1)
        end_date = date(year_int, month_int, monthrange(year_int, month_int)[1])
        return MonthWindow(month=report_month, start_date=start_date, end_date=end_date)

    def _calculate_summary(
        self,
        transactions: Sequence[Transaction],
        current_balances: Dict[str, Dict[str, Decimal]],
        previous_balances: Optional[Dict[str, Dict[str, Decimal]]],
        window: MonthWindow,
    ) -> Dict[str, Any]:
        income_total, expense_total = self._income_and_expense(transactions)

        balance = income_total - expense_total
        savings_rate = self._safe_percentage(balance, income_total)
        daily_expense = self._quantize(expense_total / Decimal(window.days)) if window.days else ZERO

        current_net_worth = self._calculate_net_worth(current_balances)
        previous_net_worth = (
            self._calculate_net_worth(previous_balances) if previous_balances is not None else None
        )
        net_worth_change = (
            self._quantize(current_net_worth - previous_net_worth)
            if previous_net_worth is not None
            else None
        )

        trend_label = "稳定"
        if balance > ZERO:
            trend_label = "改善"
        elif balance < ZERO:
            trend_label = "承压"

        return {
            "income": self._decimal_str(income_total),
            "expense": self._decimal_str(expense_total),
            "balance": self._decimal_str(balance),
            "savings_rate": self._decimal_str(savings_rate),
            "daily_expense": self._decimal_str(daily_expense),
            "net_worth_change": self._decimal_str(net_worth_change) if net_worth_change is not None else None,
            "trend_label": trend_label,
            "currency": "CNY",
        }

    def _calculate_spending_structure(self, transactions: Sequence[Transaction]) -> Dict[str, Any]:
        category_totals: Dict[str, Decimal] = defaultdict(lambda: ZERO)
        pattern_groups = {
            "fixed": defaultdict(lambda: ZERO),
            "variable": defaultdict(lambda: ZERO),
            "one_time": defaultdict(lambda: ZERO),
        }

        expense_transactions = [txn for txn in transactions if any(p.account.startswith("Expenses:") for p in txn.postings)]
        narration_counter = defaultdict(int)
        for txn in expense_transactions:
            narration_counter[(txn.payee or "", txn.description or "")] += 1

        for transaction in expense_transactions:
            for posting in transaction.postings:
                if not posting.account.startswith("Expenses:"):
                    continue
                amount = abs(posting.amount)
                category = self._expense_category(posting.account)
                category_totals[category] += amount

                bucket = self._classify_expense_pattern(transaction, posting.account, narration_counter)
                pattern_groups[bucket][category] += amount

        top_categories = sorted(
            (
                {"category": category, "amount": self._decimal_str(amount)}
                for category, amount in category_totals.items()
            ),
            key=lambda item: Decimal(item["amount"]),
            reverse=True,
        )[:5]

        return {
            "top_categories": top_categories,
            "fixed_expenses": self._serialize_amount_map(pattern_groups["fixed"]),
            "variable_expenses": self._serialize_amount_map(pattern_groups["variable"]),
            "one_time_expenses": self._serialize_amount_map(pattern_groups["one_time"]),
        }

    def _calculate_change_analysis(
        self,
        current_transactions: Sequence[Transaction],
        previous_transactions: Sequence[Transaction],
        recent_average_transactions: Sequence[Sequence[Transaction]],
    ) -> Dict[str, Any]:
        current_income, current_expense = self._income_and_expense(current_transactions)
        previous_income, previous_expense = self._income_and_expense(previous_transactions)

        recent_expense_values = [self._income_and_expense(items)[1] for items in recent_average_transactions if items]
        recent_avg_expense = self._quantize(Decimal(str(mean(recent_expense_values)))) if recent_expense_values else None

        category_changes = self._category_change_breakdown(current_transactions, previous_transactions)
        return {
            "vs_previous_month": {
                "income_change": self._decimal_str(current_income - previous_income),
                "expense_change": self._decimal_str(current_expense - previous_expense),
                "expense_change_rate": self._decimal_str(
                    self._safe_percentage(current_expense - previous_expense, previous_expense)
                )
                if previous_expense != ZERO
                else None,
            },
            "vs_recent_average": {
                "expense_average": self._decimal_str(recent_avg_expense) if recent_avg_expense is not None else None,
                "expense_change": self._decimal_str(current_expense - recent_avg_expense)
                if recent_avg_expense is not None
                else None,
            },
            "drivers": category_changes[:3],
        }

    def _detect_anomalies(
        self,
        transactions: Sequence[Transaction],
        spending_structure: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        expense_amounts = []
        repeated_candidates = defaultdict(list)
        for transaction in transactions:
            expense_total = ZERO
            for posting in transaction.postings:
                if posting.account.startswith("Expenses:"):
                    expense_total += abs(posting.amount)
            if expense_total > ZERO:
                expense_amounts.append((transaction, expense_total))
                repeated_candidates[(transaction.payee or "", transaction.description or "")].append(transaction)

        if not expense_amounts:
            return [{"type": "insufficient_data", "message": "无法判断"}]

        total_expense = sum(amount for _, amount in expense_amounts)
        threshold = max(Decimal("1000"), self._quantize(total_expense * Decimal("0.3")))
        anomalies: List[Dict[str, Any]] = []

        for transaction, amount in sorted(expense_amounts, key=lambda item: item[1], reverse=True):
            if amount >= threshold:
                anomalies.append(
                    {
                        "type": "large_expense",
                        "message": f"{transaction.date.isoformat()} {transaction.description} 金额较大",
                        "amount": self._decimal_str(amount),
                    }
                )
                break

        repeated = [
            key for key, values in repeated_candidates.items()
            if key != ("", "") and len(values) >= 2
        ]
        if repeated:
            payee, narration = repeated[0]
            anomalies.append(
                {
                    "type": "repeated_transaction",
                    "message": f"检测到重复交易模式：{payee or narration}",
                }
            )

        top_categories = spending_structure.get("top_categories", [])
        if top_categories:
            anomalies.append(
                {
                    "type": "category_focus",
                    "message": f"支出集中在 {top_categories[0]['category']}",
                    "amount": top_categories[0]["amount"],
                }
            )

        return anomalies or [{"type": "insufficient_data", "message": "无法判断"}]

    def _calculate_cash_flow(self, transactions: Sequence[Transaction]) -> Dict[str, Any]:
        income_total, expense_total = self._income_and_expense(transactions)
        transfer_total = ZERO
        repayment_total = ZERO

        for transaction in transactions:
            account_roots = {posting.account.split(":")[0] for posting in transaction.postings}
            if account_roots <= {"Assets", "Liabilities"}:
                if not any(self._is_investment_account(posting.account) for posting in transaction.postings):
                    transfer_total += self._transaction_single_side_amount(transaction, "Assets:")
            elif "Liabilities" in account_roots and "Expenses" not in account_roots:
                repayment_total += self._transaction_single_side_amount(transaction, "Liabilities:")

        return {
            "income": self._decimal_str(income_total),
            "expense": self._decimal_str(expense_total),
            "net_cash_flow": self._decimal_str(income_total - expense_total),
            "transfer_amount": self._decimal_str(transfer_total),
            "repayment_amount": self._decimal_str(repayment_total),
        }

    def _calculate_investment(
        self,
        transactions: Sequence[Transaction],
        current_balances: Dict[str, Dict[str, Decimal]],
        previous_balances: Optional[Dict[str, Dict[str, Decimal]]],
    ) -> Dict[str, Any]:
        investment_flow = ZERO
        for transaction in transactions:
            investment_accounts = [
                posting for posting in transaction.postings
                if self._is_investment_account(posting.account)
            ]
            if not investment_accounts:
                continue
            for posting in investment_accounts:
                if posting.account.startswith("Assets:"):
                    investment_flow += posting.amount

        current_value = self._sum_matching_balances(current_balances, self._is_investment_account)
        previous_value = (
            self._sum_matching_balances(previous_balances, self._is_investment_account)
            if previous_balances is not None
            else None
        )
        investment_return = None
        if previous_value is not None:
            investment_return = current_value - previous_value - investment_flow

        return {
            "net_inflow": self._decimal_str(investment_flow),
            "return": self._decimal_str(investment_return) if investment_return is not None else "无法判断",
            "current_value": self._decimal_str(current_value),
        }

    def _category_change_breakdown(
        self,
        current_transactions: Sequence[Transaction],
        previous_transactions: Sequence[Transaction],
    ) -> List[Dict[str, Any]]:
        current_map = self._expense_category_totals(current_transactions)
        previous_map = self._expense_category_totals(previous_transactions)

        changes = []
        for category in set(current_map) | set(previous_map):
            current_amount = current_map.get(category, ZERO)
            previous_amount = previous_map.get(category, ZERO)
            delta = current_amount - previous_amount
            if delta == ZERO:
                continue
            changes.append(
                {
                    "category": category,
                    "change_amount": self._decimal_str(delta),
                    "reason": f"{category} 较上月{'增加' if delta > ZERO else '减少'}",
                }
            )
        changes.sort(key=lambda item: abs(Decimal(item["change_amount"])), reverse=True)
        return changes

    def _income_and_expense(self, transactions: Sequence[Transaction]) -> tuple[Decimal, Decimal]:
        income_total = ZERO
        expense_total = ZERO
        for transaction in transactions:
            for posting in transaction.postings:
                if posting.account.startswith("Income:"):
                    income_total += self._normalized_posting_amount(posting.account, posting.amount)
                elif posting.account.startswith("Expenses:"):
                    expense_total += self._normalized_posting_amount(posting.account, posting.amount)
        return self._quantize(income_total), self._quantize(expense_total)

    def _expense_category_totals(self, transactions: Sequence[Transaction]) -> Dict[str, Decimal]:
        totals: Dict[str, Decimal] = defaultdict(lambda: ZERO)
        for transaction in transactions:
            for posting in transaction.postings:
                if posting.account.startswith("Expenses:"):
                    totals[self._expense_category(posting.account)] += self._normalized_posting_amount(
                        posting.account,
                        posting.amount,
                    )
        return totals

    def _classify_expense_pattern(
        self,
        transaction: Transaction,
        account_name: str,
        narration_counter: Dict[tuple[str, str], int],
    ) -> str:
        tags = {tag.lower() for tag in transaction.tags}
        description = (transaction.description or "").lower()
        account_lower = account_name.lower()
        payee_key = (transaction.payee or "", transaction.description or "")

        if "fixed" in tags or "recurring" in tags or "monthly" in tags:
            return "fixed"
        if "once" in tags or "one_time" in tags or "annual" in tags:
            return "one_time"
        if any(keyword in description for keyword in ("房租", "rent", "subscription", "保险", "loan")):
            return "fixed"
        if narration_counter.get(payee_key, 0) >= 2:
            return "fixed"
        if any(keyword in account_lower for keyword in ("investment", "broker", "fund")):
            return "one_time"
        return "variable"

    def _calculate_net_worth(self, balances: Optional[Dict[str, Dict[str, Decimal]]]) -> Decimal:
        if not balances:
            return ZERO
        assets = self._sum_matching_balances(balances, lambda name: name.startswith("Assets:"))
        liabilities = self._sum_matching_balances(balances, lambda name: name.startswith("Liabilities:"))
        return self._quantize(assets + liabilities)

    def _sum_matching_balances(
        self,
        balances: Optional[Dict[str, Dict[str, Decimal]]],
        predicate,
    ) -> Decimal:
        if not balances:
            return ZERO
        total = ZERO
        for account_name, currency_map in balances.items():
            if not predicate(account_name):
                continue
            total += sum(currency_map.values(), ZERO)
        return self._quantize(total)

    @staticmethod
    def _is_investment_account(account_name: str) -> bool:
        lowered = account_name.lower()
        return any(keyword in lowered for keyword in ("investment", "broker", "fund", "stock", "bond"))

    @staticmethod
    def _expense_category(account_name: str) -> str:
        parts = account_name.split(":")
        if len(parts) >= 2:
            return parts[1]
        return account_name

    @staticmethod
    def _normalized_posting_amount(account_name: str, amount: Decimal) -> Decimal:
        if account_name.startswith("Income:"):
            return -amount
        if account_name.startswith("Expenses:"):
            return amount
        return ZERO

    @staticmethod
    def _transaction_single_side_amount(transaction: Transaction, prefix: str) -> Decimal:
        positives = [
            abs(posting.amount)
            for posting in transaction.postings
            if posting.account.startswith(prefix) and posting.amount > ZERO
        ]
        if positives:
            return sum(positives, ZERO)
        matching = [
            abs(posting.amount)
            for posting in transaction.postings
            if posting.account.startswith(prefix)
        ]
        if not matching:
            return ZERO
        return max(matching)

    @staticmethod
    def _serialize_amount_map(values: Dict[str, Decimal]) -> List[Dict[str, str]]:
        return [
            {"category": key, "amount": MonthlyReportFactsService._decimal_str(value)}
            for key, value in sorted(values.items(), key=lambda item: item[1], reverse=True)
        ]

    @staticmethod
    def _safe_percentage(numerator: Decimal, denominator: Decimal) -> Decimal:
        if denominator == ZERO:
            return ZERO
        return MonthlyReportFactsService._quantize((numerator / denominator) * HUNDRED)

    @staticmethod
    def _quantize(value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _decimal_str(value: Optional[Decimal]) -> str:
        if value is None:
            return "无法判断"
        return format(MonthlyReportFactsService._quantize(value), "f")
