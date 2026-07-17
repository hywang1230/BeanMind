from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.infrastructure.persistence.ledger_projection import (
    LedgerProjectionService,
    TransactionQueryService,
)
from backend.interfaces.api import transaction as transaction_api


def _client(db_session, ledger_path):
    app = FastAPI()
    app.include_router(transaction_api.router)
    query = TransactionQueryService(db_session, ledger_path)
    app.dependency_overrides[transaction_api.get_transaction_query_service] = lambda: query
    app.dependency_overrides[transaction_api.get_projection_service] = lambda: query.projection
    return TestClient(app), query


def test_transaction_api_uses_cursor_contract(db_session, ledger_path):
    LedgerProjectionService(db_session, ledger_path).rebuild_all()
    client, _ = _client(db_session, ledger_path)

    response = client.get("/api/transactions", params={"limit": 2})

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"items", "next_cursor", "has_more"}
    assert len(payload["items"]) == 2
    assert payload["has_more"] is True
    assert payload["items"][0]["display_amounts"]
    assert set(payload["items"][0]["display_amounts"][0]) == {"currency", "amount"}


def test_transaction_api_maps_invalid_cursor_and_dirty(db_session, ledger_path):
    projection = LedgerProjectionService(db_session, ledger_path)
    projection.rebuild_all()
    client, _ = _client(db_session, ledger_path)

    invalid = client.get("/api/transactions", params={"cursor": "%%"})
    assert invalid.status_code == 400
    assert invalid.json()["detail"]["code"] == "INVALID_TRANSACTION_CURSOR"

    projection.mark_dirty(ledger_path, "test")
    dirty = client.get("/api/transactions")
    assert dirty.status_code == 503
    assert dirty.json()["detail"]["code"] == "LEDGER_PROJECTION_DIRTY"


def test_projection_admin_endpoints_rebuild_check_and_recover(db_session, ledger_path):
    client, query = _client(db_session, ledger_path)

    assert client.post("/api/transactions/projection/rebuild").status_code == 200
    checked = client.post("/api/transactions/projection/check")
    assert checked.status_code == 200
    assert checked.json()["consistent"] is True

    year_file = ledger_path.parent / "transactions_2025.beancount"
    original = year_file.read_text(encoding="utf-8")
    year_file.write_text(original + "\ninvalid beancount line\n", encoding="utf-8")
    failed = client.post("/api/transactions/projection/rebuild")
    assert failed.status_code == 503
    assert failed.json()["detail"]["code"] == "LEDGER_PROJECTION_REBUILD_FAILED"
    assert query.projection.status()["status"] == "DIRTY"

    year_file.write_text(original, encoding="utf-8")
    assert client.post("/api/transactions/projection/rebuild").status_code == 200
    assert query.projection.status()["status"] == "READY"
