"""应用服务模块。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .account_service import AccountApplicationService
    from .auth_service import AuthApplicationService
    from .budget_service import BudgetApplicationService
    from .transaction_service import TransactionApplicationService

__all__ = [
    "AccountApplicationService",
    "AuthApplicationService",
    "TransactionApplicationService",
    "BudgetApplicationService",
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
    raise AttributeError(name)
