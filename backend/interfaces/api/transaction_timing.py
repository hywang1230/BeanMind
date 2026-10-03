"""Transaction write timing, including dependency resolution and error mapping."""

import logging
import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send


logger = logging.getLogger(__name__)


class TransactionWriteTimingMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        operation = None
        if scope["type"] == "http":
            path = scope.get("path", "").rstrip("/")
            method = scope.get("method")
            if method == "POST" and path == "/api/transactions":
                operation = "create"
            elif method in {"PUT", "DELETE"} and path.startswith("/api/transactions/"):
                suffix = path.removeprefix("/api/transactions/")
                if suffix and "/" not in suffix:
                    operation = "update" if method == "PUT" else "delete"
        if operation is None:
            return await self.app(scope, receive, send)

        started = time.perf_counter()
        # Unhandled errors are mapped to 500 by the outer ServerErrorMiddleware.
        status_code = 500

        async def timed_send(message: Message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, timed_send)
        finally:
            logger.info("ledger_request operation=%s status_code=%d duration_ms=%.1f",
                        operation, status_code, (time.perf_counter() - started) * 1000)
