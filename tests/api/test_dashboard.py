from decimal import Decimal

from fastapi.testclient import TestClient

from backend.config import get_db, settings
from backend.infrastructure.persistence.ledger_projection import LedgerProjectionService
from backend.main import app


class FakeBeancountService:
    def get_operating_currency(self):
        return "CNY"

    def get_all_exchange_rates(self, to_currency, as_of_date):
        return {"USD": Decimal("7")}


def test_dashboard_contract_uses_projection(db_session, ledger_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "LLM_ENABLED", False)
    LedgerProjectionService(db_session, ledger_path).rebuild_all()
    app.dependency_overrides[get_db] = lambda: db_session
    monkeypatch.setattr(
        "backend.interfaces.api.dashboard.get_beancount_service",
        lambda: FakeBeancountService(),
    )
    try:
        response = TestClient(app).get("/api/dashboard", params={"month": "2025-01"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    payload = response.json()
    assert payload["income"] == "10000"
    assert payload["expense"] == "50"
    assert payload["net_income"] == "9950"
    assert payload["budget_risk"] == "NORMAL"
    assert payload["review_status"] == "DISABLED"


def test_dashboard_dirty_and_invalid_month(db_session, ledger_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "LLM_ENABLED", False)
    projection = LedgerProjectionService(db_session, ledger_path)
    projection.rebuild_all()
    projection.mark_dirty(ledger_path, RuntimeError("broken"))
    app.dependency_overrides[get_db] = lambda: db_session
    monkeypatch.setattr(
        "backend.interfaces.api.dashboard.get_beancount_service",
        lambda: FakeBeancountService(),
    )
    try:
        client = TestClient(app)
        dirty = client.get("/api/dashboard", params={"month": "2025-01"})
        invalid = client.get("/api/dashboard", params={"month": "bad"})
    finally:
        app.dependency_overrides.clear()
    assert dirty.status_code == 503
    assert dirty.json()["code"] == "LEDGER_PROJECTION_DIRTY"
    assert invalid.status_code == 400
    assert invalid.json()["code"] == "INVALID_MONTH"
