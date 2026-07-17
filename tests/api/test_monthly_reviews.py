from fastapi.testclient import TestClient

from backend.config import get_db
from backend.infrastructure.persistence.ledger_projection import LedgerProjectionService
from backend.main import app
from backend.interfaces.api.monthly_report import get_service


class FakeBeancountService:
    def get_operating_currency(self):
        return "CNY"


def test_disabled_monthly_review_returns_facts_without_external_call(
    db_session, ledger_path, monkeypatch
) -> None:
    LedgerProjectionService(db_session, ledger_path).rebuild_all()
    app.dependency_overrides[get_db] = lambda: db_session
    monkeypatch.setattr(
        "backend.interfaces.api.monthly_report.get_beancount_service",
        lambda: FakeBeancountService(),
    )
    try:
        client = TestClient(app)
        response = client.get("/api/monthly-reviews/2025-01")
        generate = client.post(
            "/api/monthly-reviews/2025-01", json={"regenerate": False}
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["status"] == "DISABLED"
    assert response.json()["facts"]["current"]["income"]["CNY"] == "10000"
    assert generate.status_code == 202
    assert generate.json()["status"] == "DISABLED"


def test_enabled_monthly_review_queues_background_generation(monkeypatch) -> None:
    class FakeService:
        def queue(self, month, regenerate):
            assert month == "2025-01"
            assert regenerate is True
            return {"report_month": month, "status": "PROCESSING"}, True

    called = []
    app.dependency_overrides[get_service] = lambda: FakeService()
    monkeypatch.setattr(
        "backend.interfaces.api.monthly_report.run_generation",
        lambda month: called.append(month),
    )
    try:
        response = TestClient(app).post(
            "/api/monthly-reviews/2025-01", json={"regenerate": True}
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 202
    assert response.json()["status"] == "PROCESSING"
    assert called == ["2025-01"]
