from fastapi.testclient import TestClient

from backend.config import get_db
from backend.main import app


def payload():
    return {
        "name": "每月房租",
        "frequency": "monthly",
        "frequency_config": {"month_days": [1]},
        "transaction_template": {
            "description": "支付房租",
            "postings": [
                {"account": "Expenses:Housing", "amount": "1000.123456789", "currency": "CNY"},
                {"account": "Assets:Cash", "amount": "-1000.123456789", "currency": "CNY"},
            ],
        },
        "start_date": "2026-01-01",
        "is_active": True,
    }


def test_single_machine_recurring_rule_crud_has_no_user_identity(db_session) -> None:
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        created = client.post("/api/recurring/rules", json=payload())
        listed = client.get("/api/recurring/rules")
        rule_id = created.json()["id"]
        updated = client.put(
            f"/api/recurring/rules/{rule_id}", json={"is_active": False}
        )
    finally:
        app.dependency_overrides.clear()

    assert created.status_code == 200
    assert "user_id" not in created.json()
    assert created.json()["transaction_template"]["postings"][0]["amount"] == "1000.123456789"
    assert listed.status_code == 200
    assert [rule["name"] for rule in listed.json()] == ["每月房租"]
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False


def test_recurring_rule_rejects_missing_month_days(db_session) -> None:
    invalid = payload()
    invalid["frequency_config"] = {}
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        response = TestClient(app).post("/api/recurring/rules", json=invalid)
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 400
