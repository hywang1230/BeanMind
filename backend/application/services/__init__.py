"""应用服务模块。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .account_service import AccountApplicationService
    from .auth_service import AuthApplicationService
    from .budget_service import BudgetApplicationService
    from .monthly_report_service import MonthlyReportApplicationService
    from .transaction_service import TransactionApplicationService

__all__ = [
    "AccountApplicationService",
    "AuthApplicationService",
    "TransactionApplicationService",
    "BudgetApplicationService",
    "MonthlyReportApplicationService",
]


def __getattr__(name: str):
    if name == "AccountApplicationService":
        from .account_service import AccountApplicationService

        return AccountApplicationService
    if name == "AuthApplicationService":
        from .auth_service import AuthApplicationService

        return AuthApplicationService
    if name == "TransactionApplicationService":
        from .transaction_service import TransactionApplicationService

        return TransactionApplicationService
    if name == "BudgetApplicationService":
        from .budget_service import BudgetApplicationService

        return BudgetApplicationService
    if name == "MonthlyReportApplicationService":
        from .monthly_report_service import MonthlyReportApplicationService

        return MonthlyReportApplicationService
    raise AttributeError(name)
