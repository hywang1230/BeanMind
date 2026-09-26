"""现有 Beancount 写入口的共同互斥边界。"""
from functools import wraps
from .ledger_write import ledger_lock, has_pending_write, LedgerWriteError


def coordinated_write(method):
    @wraps(method)
    def guarded(self, *args, **kwargs):
        service = getattr(self, "beancount_service", self)
        with ledger_lock(service.ledger_path):
            if has_pending_write(service.ledger_path):
                raise LedgerWriteError("账本存在未完成恢复，请先恢复投影")
            if service is not self:
                from .beancount_provider import BeancountServiceProvider
                self.beancount_service = BeancountServiceProvider.get_service(service.ledger_path)
                if hasattr(self, "_load_accounts"):
                    self._load_accounts()
                elif hasattr(self, "_load_exchange_rates"):
                    self._load_exchange_rates()
            return method(self, *args, **kwargs)
    return guarded


def coordinated_read(method):
    @wraps(method)
    def guarded(self, *args, **kwargs):
        with ledger_lock(self.ledger_path):
            return method(self, *args, **kwargs)
    return guarded
