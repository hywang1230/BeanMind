from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from backend.interfaces.api import exchange_rate as exchange_rate_api
from backend.interfaces.api import reports as reports_api
from backend.main import app


class FakeExchangeRateService:
    def get_all_exchange_rates(self, quote_currency: str):
        assert quote_currency == "CNY"
        return [
            {
                "currency": "USD",
                "rate": "7.123456789",
                "quote_currency": "CNY",
                "effective_date": "2026-07-01",
                "currency_pair": "USD/CNY",
            }
        ]


class FakeReportService:
    def get_all_exchange_rates(self, to_currency: str, as_of_date: date):
        assert to_currency == "CNY"
        return {"CNY": Decimal("1"), "USD": Decimal("7.123456789")}

    def get_account_balances(self, account_name=None, as_of_date=None):
        balances = {
            "Assets:Cash": {"CNY": Decimal("100.123456789")},
            "Liabilities:Card": {"CNY": Decimal("-20.000000001")},
            "Equity:Opening": {"CNY": Decimal("-80.123456788")},
        }
        if account_name:
            return {account_name: balances.get(account_name, {})}
        return balances

    def get_transactions(self, start_date=None, end_date=None, account=None):
        return [
            {
                "date": "2026-07-10",
                "description": "精度测试",
                "payee": "商户",
                "postings": [
                    {
                        "account": "Expenses:Food",
                        "amount": "0.123456789",
                        "currency": "CNY",
                    },
                    {
                        "account": "Assets:Cash",
                        "amount": "-0.123456789",
                        "currency": "CNY",
                    },
                ],
            }
        ]

    def get_accounts(self):
        return [{"name": "Assets:Cash"}]


def test_exchange_rate_list_keeps_decimal_string_contract() -> None:
    app.dependency_overrides[exchange_rate_api.get_exchange_rate_service] = (
        lambda: FakeExchangeRateService()
    )
    try:
        response = TestClient(app).get("/api/exchange-rates")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["exchange_rates"][0]["rate"] == "7.123456789"


def test_advanced_reports_keep_decimal_string_contract() -> None:
    app.dependency_overrides[reports_api.get_beancount_service] = (
        lambda: FakeReportService()
    )
    client = TestClient(app)
    try:
        balance = client.get(
            "/api/reports/balance-sheet", params={"as_of_date": "2026-07-31"}
        )
        income = client.get(
            "/api/reports/income-statement",
            params={"start_date": "2026-07-01", "end_date": "2026-07-31"},
        )
    finally:
        app.dependency_overrides.clear()

    assert balance.status_code == 200
    assert balance.json()["net_worth_cny"] == "80.123456788"
    assert balance.json()["exchange_rates"]["USD"] == "7.123456789"
    assert income.status_code == 200
    assert income.json()["total_expenses_cny"] == "0.123456789"
    assert isinstance(income.json()["total_expenses_cny"], str)
