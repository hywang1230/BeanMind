"""应用服务模块。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .account_service import AccountApplicationService
    from .transaction_service import TransactionApplicationService

__all__ = [
    "AccountApplicationService",
    "TransactionApplicationService",
]


def __getattr__(name: str):
    if name == "AccountApplicationService":
        from .account_service import AccountApplicationService

        return AccountApplicationService
    if name == "TransactionApplicationService":
        from .transaction_service import TransactionApplicationService

        return TransactionApplicationService
    raise AttributeError(name)
