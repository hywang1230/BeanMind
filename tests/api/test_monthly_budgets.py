from fastapi.testclient import TestClient

from backend.config import get_db
from backend.infrastructure.persistence.ledger_projection import LedgerProjectionService
from backend.main import app


def test_monthly_budget_api_save_read_copy_and_errors(db_session, ledger_path) -> None:
    LedgerProjectionService(db_session, ledger_path).rebuild_all()
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        saved = client.put(
            "/api/budgets/2024-12",
            json={
                "currency": "CNY",
                "items": [
                    {"name": "餐饮", "account_pattern": "Expenses:Food", "amount": "500"}
                ],
            },
        )
        assert saved.status_code == 200
        assert saved.json()["spent"] == "123.456789123456789"
        copied = client.post("/api/budgets/2025-01/copy", params={"currency": "CNY"})
        assert copied.status_code == 200
        assert copied.json()["spent"] == "50"
        conflict = client.post("/api/budgets/2025-01/copy", params={"currency": "CNY"})
        assert conflict.status_code == 409
        assert conflict.json()["code"] == "MONTHLY_BUDGET_EXISTS"
    finally:
        app.dependency_overrides.clear()


def test_monthly_budget_api_rejects_overlap_without_changing_existing(db_session, ledger_path) -> None:
    LedgerProjectionService(db_session, ledger_path).rebuild_all()
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        response = TestClient(app).put(
            "/api/budgets/2025-01",
            json={
                "currency": "CNY",
                "items": [
                    {"name": "餐饮", "account_pattern": "Expenses:Food", "amount": "100"},
                    {"name": "外食", "account_pattern": "Expenses:Food:Dining", "amount": "50"},
                ],
            },
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 400
    assert response.json()["code"] == "OVERLAPPING_BUDGET_PATTERN"
