from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from backend.config import get_db
from backend.infrastructure.persistence.db.models import MonthlyBudget
from backend.infrastructure.persistence.ledger_projection import LedgerProjectionService
from backend.interfaces.api import budget as budget_api
from backend.main import app
from backend.services.ledger_aggregation import LedgerAggregationService
from backend.services.monthly_budget import MonthlyBudgetService


class FakeBeancountService:
    def __init__(self, rates: dict[str, Decimal] | None = None) -> None:
        self.rates = rates or {}

    def get_operating_currency(self) -> str:
        return "CNY"

    def get_all_exchange_rates(self, to_currency: str, as_of_date: date):
        assert to_currency == "CNY"
        return self.rates


def override_budget_service(db_session, ledger_path, rates=None) -> None:
    service = MonthlyBudgetService(
        db_session,
        LedgerAggregationService(db_session, ledger_path),
        FakeBeancountService(rates),
    )
    app.dependency_overrides[budget_api.get_budget_service] = lambda: service


def test_monthly_budget_api_save_read_copy_and_errors(db_session, ledger_path) -> None:
    LedgerProjectionService(db_session, ledger_path).rebuild_all()
    app.dependency_overrides[get_db] = lambda: db_session
    override_budget_service(db_session, ledger_path)
    try:
        client = TestClient(app)
        saved = client.put(
            "/api/budgets/2024-12",
            json={
                "items": [
                    {"name": "餐饮", "account_pattern": "Expenses:Food", "amount": "500"}
                ],
            },
        )
        assert saved.status_code == 200
        assert saved.json()["spent"] == "123.456789123456789"
        copied = client.post("/api/budgets/2025-01/copy")
        assert copied.status_code == 200
        assert copied.json()["spent"] == "50"
        conflict = client.post("/api/budgets/2025-01/copy")
        assert conflict.status_code == 409
        assert conflict.json()["code"] == "MONTHLY_BUDGET_EXISTS"
    finally:
        app.dependency_overrides.clear()


def test_monthly_budget_api_rejects_overlap_without_changing_existing(db_session, ledger_path) -> None:
    LedgerProjectionService(db_session, ledger_path).rebuild_all()
    app.dependency_overrides[get_db] = lambda: db_session
    override_budget_service(db_session, ledger_path)
    try:
        response = TestClient(app).put(
            "/api/budgets/2025-01",
            json={
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


def test_monthly_budget_rejects_removed_currency_field_without_creating_budget(
    db_session, ledger_path
) -> None:
    LedgerProjectionService(db_session, ledger_path).rebuild_all()
    app.dependency_overrides[get_db] = lambda: db_session
    override_budget_service(db_session, ledger_path)
    try:
        response = TestClient(app).put(
            "/api/budgets/2025-02",
            json={
                "currency": "USD",
                "items": [
                    {"name": "餐饮", "account_pattern": "Expenses:Food", "amount": "100"}
                ],
            },
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    assert db_session.query(MonthlyBudget).count() == 0


def test_monthly_budget_query_currency_cannot_select_second_budget(
    db_session, ledger_path
) -> None:
    LedgerProjectionService(db_session, ledger_path).rebuild_all()
    app.dependency_overrides[get_db] = lambda: db_session
    override_budget_service(db_session, ledger_path)
    try:
        client = TestClient(app)
        saved = client.put(
            "/api/budgets/2025-01",
            json={"items": [{"name": "餐饮", "account_pattern": "Expenses:Food", "amount": "100"}]},
        )
        selected = client.get("/api/budgets", params={"month": "2025-01", "currency": "USD"})
    finally:
        app.dependency_overrides.clear()
    assert saved.status_code == 200
    assert selected.status_code == 200
    assert selected.json()["currency"] == "CNY"
    assert db_session.query(MonthlyBudget).count() == 1


def test_monthly_budget_api_converts_foreign_spending(db_session, ledger_path) -> None:
    LedgerProjectionService(db_session, ledger_path).rebuild_all()
    app.dependency_overrides[get_db] = lambda: db_session
    override_budget_service(db_session, ledger_path, {"USD": Decimal("7.25")})
    try:
        response = TestClient(app).put(
            "/api/budgets/2025-02",
            json={"items": [{"name": "差旅", "account_pattern": "Expenses:Travel", "amount": "800"}]},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["currency"] == "CNY"
    assert Decimal(response.json()["spent"]) == Decimal("724.92750000000000725")


def test_monthly_budget_api_missing_rate_returns_no_partial_result(
    db_session, ledger_path
) -> None:
    LedgerProjectionService(db_session, ledger_path).rebuild_all()
    app.dependency_overrides[get_db] = lambda: db_session
    override_budget_service(db_session, ledger_path)
    try:
        response = TestClient(app).put(
            "/api/budgets/2025-02",
            json={"items": [{"name": "差旅", "account_pattern": "Expenses:Travel", "amount": "800"}]},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 400
    assert response.json()["code"] == "MISSING_EXCHANGE_RATE"
    assert response.json()["details"]["currencies"] == ["USD"]
    assert db_session.query(MonthlyBudget).count() == 0


def test_monthly_budget_openapi_has_no_currency_input() -> None:
    schema = TestClient(app).get("/openapi.json").json()
    get_parameters = schema["paths"]["/api/budgets"]["get"]["parameters"]
    copy_parameters = schema["paths"]["/api/budgets/{month}/copy"]["post"]["parameters"]
    input_schema = schema["components"]["schemas"]["MonthlyBudgetInput"]

    assert {parameter["name"] for parameter in get_parameters} == {"month"}
    assert {parameter["name"] for parameter in copy_parameters} == {"month", "overwrite"}
    assert set(input_schema["properties"]) == {"items"}
