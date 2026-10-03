"""Write timing begins before dependencies and observes mapped response status."""

import logging
from types import SimpleNamespace

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel
import pytest

from backend.interfaces.api import transaction_timing as timing


class Body(BaseModel):
    value: int


@pytest.mark.parametrize("outcome,status", [
    ("success", 201), ("dependency", 409), ("business", 400),
    ("validation", 422), ("unhandled", 500),
])
def test_write_timing_includes_dependency_and_final_status(monkeypatch, caplog, outcome, status):
    clock = [10.0]
    monkeypatch.setattr(timing, "time", SimpleNamespace(perf_counter=lambda: clock[0]))
    app = FastAPI()
    app.add_middleware(timing.TransactionWriteTimingMiddleware)

    class DependencyError(Exception):
        pass

    @app.exception_handler(DependencyError)
    async def mapped(request, error):
        return JSONResponse(status_code=409, content={"error": "mapped"})

    def dependency():
        clock[0] += 0.025
        if outcome == "dependency":
            raise DependencyError("PRIVATE-DETAIL")

    @app.post("/api/transactions", status_code=201)
    def create(body: Body, ready=Depends(dependency)):
        if outcome == "business":
            raise HTTPException(400, "PRIVATE-DETAIL")
        if outcome == "unhandled":
            raise RuntimeError("PRIVATE-DETAIL")
        return {"ok": True}

    caplog.set_level(logging.INFO, logger=timing.__name__)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/transactions?private=PRIVATE-DETAIL",
                               json={"value": "invalid" if outcome == "validation" else 1,
                                     "private": "PRIVATE-DETAIL"})
    assert response.status_code == status
    messages = [record.getMessage() for record in caplog.records if record.name == timing.__name__]
    assert messages == [f"ledger_request operation=create status_code={status} duration_ms=25.0"]
    assert "PRIVATE-DETAIL" not in " ".join(messages)


@pytest.mark.parametrize("method,operation", [("PUT", "update"), ("DELETE", "delete")])
def test_update_delete_timing_never_logs_identifier(caplog, method, operation):
    app = FastAPI()
    app.add_middleware(timing.TransactionWriteTimingMiddleware)

    @app.api_route("/api/transactions/{identifier}", methods=[method])
    def write(identifier: str):
        return {"ok": True}

    caplog.set_level(logging.INFO, logger=timing.__name__)
    with TestClient(app) as client:
        assert client.request(method, "/api/transactions/PRIVATE-ID").status_code == 200
    messages = [record.getMessage() for record in caplog.records if record.name == timing.__name__]
    assert len(messages) == 1 and f"operation={operation} status_code=200" in messages[0]
    assert "PRIVATE-ID" not in messages[0]


def test_read_and_projection_endpoints_are_outside_write_timing(caplog):
    app = FastAPI()
    app.add_middleware(timing.TransactionWriteTimingMiddleware)

    @app.get("/api/transactions")
    @app.post("/api/transactions/projection/rebuild")
    def read_or_rebuild():
        return {"ok": True}

    caplog.set_level(logging.INFO, logger=timing.__name__)
    with TestClient(app) as client:
        assert client.get("/api/transactions").status_code == 200
        assert client.post("/api/transactions/projection/rebuild").status_code == 200
    assert not [record for record in caplog.records if record.name == timing.__name__]
