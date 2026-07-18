"""利润表同级明细按占比排序的单元测试。"""
from decimal import Decimal

from backend.interfaces.api.reports import (
    calculate_percentages,
    sort_income_expense_by_share,
)
from backend.interfaces.dto.reports import IncomeExpenseItem


def _item(account: str, total: str, children=None) -> IncomeExpenseItem:
    return IncomeExpenseItem(
        account=account,
        display_name=account.split(":")[-1],
        amounts={"CNY": Decimal(total)},
        total_cny=Decimal(total),
        children=children or [],
        depth=account.count(":"),
    )


def test_sort_income_expense_by_share_recursive():
    food = _item(
        "Expenses:Food",
        "30",
        children=[
            _item("Expenses:Food:Snack", "10"),
            _item("Expenses:Food:Dining", "20"),
        ],
    )
    travel = _item("Expenses:Travel", "70")
    items = [food, travel]
    calculate_percentages(items, Decimal("100"))
    sort_income_expense_by_share(items)

    assert [item.account for item in items] == ["Expenses:Travel", "Expenses:Food"]
    assert items[0].percentage == Decimal("70")
    assert [child.account for child in items[1].children] == [
        "Expenses:Food:Dining",
        "Expenses:Food:Snack",
    ]
