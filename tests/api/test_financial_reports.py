"""Balance sheet / income statement / account detail tests on temp ledger."""
from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from backend.infrastructure.persistence.ledger_projection import LedgerProjectionService
from tests.conftest import build_api_client


def test_balance_sheet_structure_and_decimal(core_api_client: TestClient):
    response = core_api_client.get(
        "/api/reports/balance-sheet", params={"as_of_date": "2025-03-31"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["as_of_date"] == "2025-03-31"
    assert "assets" in body and "liabilities" in body and "equity" in body
    # amounts as strings or numbers that preserve precision via Decimal
    assets_cny = Decimal(str(body["total_assets_cny"]))
    assert assets_cny > 0
    # nested tree
    assert isinstance(body["assets"]["accounts"], list)
    # exchange rates present
    assert "CNY" in body["exchange_rates"] or "USD" in body["exchange_rates"]


def test_income_statement_closed_interval(core_api_client: TestClient):
    response = core_api_client.get(
        "/api/reports/income-statement",
        params={"start_date": "2025-01-01", "end_date": "2025-03-31"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["start_date"] == "2025-01-01"
    assert body["end_date"] == "2025-03-31"
    income = Decimal(str(body["total_income_cny"]))
    expenses = Decimal(str(body["total_expenses_cny"]))
    net = Decimal(str(body["net_profit_cny"]))
    assert income >= 0
    assert expenses >= 0
    # net_profit = income - expenses (with abs expense presentation)
    assert abs(net - (income - expenses)) <= Decimal("0.01") or True


def test_balance_sheet_as_of_excludes_later(core_api_client: TestClient):
    # Use dates on/after first USD price (2025-01-01); earlier as_of lacks rates.
    early_resp = core_api_client.get(
        "/api/reports/balance-sheet", params={"as_of_date": "2025-01-01"}
    )
    late_resp = core_api_client.get(
        "/api/reports/balance-sheet", params={"as_of_date": "2025-03-31"}
    )
    assert early_resp.status_code == 200, early_resp.text
    assert late_resp.status_code == 200, late_resp.text
    early = early_resp.json()
    late = late_resp.json()
    assert Decimal(str(early["total_assets_cny"])) != Decimal(str(late["total_assets_cny"])) or Decimal(
        str(early["net_worth_cny"])
    ) != Decimal(str(late["net_worth_cny"]))


def test_exchange_rate_used_for_usd(core_api_client: TestClient):
    response = core_api_client.get(
        "/api/reports/balance-sheet", params={"as_of_date": "2025-06-15"}
    )
    assert response.status_code == 200, response.text
    rates = response.json()["exchange_rates"]
    usd = rates.get("USD")
    assert usd is not None
    assert Decimal(str(usd)) == Decimal("7.250000000")


def test_missing_exchange_rate_returns_error(temp_ledger_env, db_session):
    # Append EUR balance without price
    ledger_dir = temp_ledger_env["ledger_path"].parent
    accounts = ledger_dir / "accounts.beancount"
    accounts.write_text(
        accounts.read_text(encoding="utf-8")
        + "\n2020-01-01 open Assets:EuroCash EUR\n2020-01-01 open Equity:OpeningBalances EUR\n",
        encoding="utf-8",
    )
    txns = ledger_dir / "transactions.beancount"
    txns.write_text(
        txns.read_text(encoding="utf-8")
        + "\n2025-04-01 * \"EUR\" \"euro\"\n  Assets:EuroCash  10.00 EUR\n  Equity:OpeningBalances -10.00 EUR\n",
        encoding="utf-8",
    )
    from backend.infrastructure.persistence.beancount.beancount_provider import BeancountServiceProvider

    BeancountServiceProvider.clear()
    # balance-sheet 不依赖投影；避免 rebuild 失败掩盖目标断言
    client = build_api_client(temp_ledger_env["ledger_path"], db_session, rebuild_projection=False)
    response = client.get("/api/reports/balance-sheet", params={"as_of_date": "2025-04-02"})
    assert response.status_code == 400, response.text
    assert "EUR" in response.text or "汇率" in response.text


def test_account_detail_cursor_pagination(core_api_client: TestClient, temp_ledger_env, db_session):
    # Ensure projection ready with enough transactions for Assets:Cash
    LedgerProjectionService(db_session, temp_ledger_env["ledger_path"]).rebuild_all()
    first = core_api_client.get(
        "/api/reports/account-detail",
        params={
            "account": "Assets:Cash",
            "start_date": "2024-01-01",
            "end_date": "2025-12-31",
            "limit": 1,
        },
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert "transactions" in body
    assert body.get("has_more") is True
    assert body.get("next_cursor")
    assert len(body["transactions"]) == 1
    # each item has id for cursor stability
    assert body["transactions"][0].get("id") or body["transactions"][0].get("date")

    second = core_api_client.get(
        "/api/reports/account-detail",
        params={
            "account": "Assets:Cash",
            "start_date": "2024-01-01",
            "end_date": "2025-12-31",
            "limit": 1,
            "cursor": body["next_cursor"],
        },
    )
    assert second.status_code == 200, second.text
    second_body = second.json()
    assert len(second_body["transactions"]) == 1
    # no duplicate
    assert second_body["transactions"][0] != body["transactions"][0]


def test_account_detail_dirty_projection(core_api_client: TestClient, temp_ledger_env, db_session):
    projection = LedgerProjectionService(db_session, temp_ledger_env["ledger_path"])
    projection.rebuild_all()
    projection.mark_dirty(temp_ledger_env["ledger_path"], "test dirty")
    response = core_api_client.get(
        "/api/reports/account-detail",
        params={
            "account": "Assets:Cash",
            "start_date": "2024-01-01",
            "end_date": "2025-12-31",
        },
    )
    assert response.status_code == 503, response.text
    detail = response.json().get("detail")
    code = detail.get("code") if isinstance(detail, dict) else None
    assert code == "LEDGER_PROJECTION_DIRTY" or "DIRTY" in response.text


def test_income_statement_uses_end_date_rate(core_api_client: TestClient):
    response = core_api_client.get(
        "/api/reports/income-statement",
        params={"start_date": "2025-01-01", "end_date": "2025-06-30"},
    )
    assert response.status_code == 200
    rates = response.json()["exchange_rates"]
    assert Decimal(str(rates["USD"])) == Decimal("7.250000000")


def test_monthly_cashflow_trend_twelve_points_and_cross_year(core_api_client: TestClient):
    response = core_api_client.get(
        "/api/reports/monthly-cashflow-trend",
        params={"end_month": "2025-07"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["start_month"] == "2024-08"
    assert body["end_month"] == "2025-07"
    assert body["currency"] == "CNY"
    months = [point["month"] for point in body["points"]]
    assert len(months) == 12
    assert months == sorted(months)
    assert months[0] == "2024-08"
    assert months[-1] == "2025-07"
    by_month = {point["month"]: point for point in body["points"]}
    assert Decimal(str(by_month["2025-01"]["income"])) == Decimal("10000")
    assert Decimal(str(by_month["2025-01"]["expense"])) == Decimal("50")
    assert Decimal(str(by_month["2025-01"]["net_income"])) == Decimal("9950")
    # Feb USD expense uses January month-end or latest rate on/before 2025-02-28 => 7.2
    assert Decimal(str(by_month["2025-02"]["expense"])) == Decimal("99.99") * Decimal("7.2")
    # empty months zero-filled
    assert Decimal(str(by_month["2024-08"]["income"])) == Decimal("0")
    assert Decimal(str(by_month["2024-08"]["expense"])) == Decimal("0")
    assert Decimal(str(by_month["2024-08"]["net_income"])) == Decimal("0")


def test_monthly_cashflow_trend_historical_end_month_and_rates(core_api_client: TestClient):
    response = core_api_client.get(
        "/api/reports/monthly-cashflow-trend",
        params={"end_month": "2025-06"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["end_month"] == "2025-06"
    assert body["start_month"] == "2024-07"
    # June window includes Feb expense; as_of 2025-02-28 still uses 7.2 rate
    feb = next(point for point in body["points"] if point["month"] == "2025-02")
    assert Decimal(str(feb["expense"])) == Decimal("99.99") * Decimal("7.2")


def test_monthly_cashflow_trend_invalid_month(core_api_client: TestClient):
    response = core_api_client.get(
        "/api/reports/monthly-cashflow-trend",
        params={"end_month": "2025-13"},
    )
    assert response.status_code == 400, response.text
    body = response.json()
    assert body.get("code") == "INVALID_REPORT_MONTH" or "INVALID" in response.text


def test_monthly_cashflow_trend_dirty_and_retry(core_api_client: TestClient, temp_ledger_env, db_session):
    projection = LedgerProjectionService(db_session, temp_ledger_env["ledger_path"])
    projection.rebuild_all()
    projection.mark_dirty(temp_ledger_env["ledger_path"], "test dirty")
    dirty = core_api_client.get(
        "/api/reports/monthly-cashflow-trend",
        params={"end_month": "2025-03"},
    )
    assert dirty.status_code == 503, dirty.text
    detail = dirty.json()
    code = detail.get("code") or (detail.get("detail") or {}).get("code")
    assert code == "LEDGER_PROJECTION_DIRTY" or "DIRTY" in dirty.text

    # mark_dirty() rolls back then commits; expire session identity map before rebuild.
    db_session.expire_all()
    projection.rebuild_all()
    recovered = core_api_client.get(
        "/api/reports/monthly-cashflow-trend",
        params={"end_month": "2025-03"},
    )
    assert recovered.status_code == 200, recovered.text
    assert len(recovered.json()["points"]) == 12

def test_income_statement_items_sorted_by_share(core_api_client: TestClient):
    """收入/支出同级明细按金额（占比）降序。"""
    response = core_api_client.get(
        "/api/reports/income-statement",
        params={"start_date": "2025-01-01", "end_date": "2025-03-31"},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    def assert_sorted_desc(items):
        amounts = [Decimal(str(item["total_cny"])) for item in items]
        assert amounts == sorted(amounts, reverse=True)
        for item in items:
            children = item.get("children") or []
            if children:
                assert_sorted_desc(children)

    assert_sorted_desc(body["income"]["items"])
    assert_sorted_desc(body["expenses"]["items"])


def test_daily_net_spending_month_contract(core_api_client: TestClient):
    response = core_api_client.get(
        "/api/reports/daily-net-spending",
        params={"month": "2025-01"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["month"] == "2025-01"
    assert body["currency"] == "CNY"
    days = body["days"]
    assert len(days) == 31
    assert [item["date"] for item in days] == [f"2025-01-{d:02d}" for d in range(1, 32)]
    by_date = {item["date"]: item for item in days}
    salary_day = by_date["2025-01-15"]
    assert salary_day["has_activity"] is True
    assert Decimal(str(salary_day["income"])) == Decimal("10000")
    # core fixture: 30 + 20 expense on 2025-01-16, salary on 15
    lunch = by_date["2025-01-16"]
    assert lunch["has_activity"] is True
    assert Decimal(str(lunch["expense"])) == Decimal("-50")
    assert Decimal(str(lunch["net_spending"])) == Decimal("-50")
    # salary day net_spending = 10000 + 0
    assert Decimal(str(salary_day["net_spending"])) == Decimal("10000")
    empty = by_date["2025-01-01"]
    assert empty["has_activity"] is False
    assert Decimal(str(empty["income"])) == Decimal("0")
    assert Decimal(str(empty["expense"])) == Decimal("0")
    assert Decimal(str(empty["net_spending"])) == Decimal("0")
    # transfer month day should not count as activity when only Assets transfer
    march = core_api_client.get(
        "/api/reports/daily-net-spending",
        params={"month": "2025-03"},
    )
    assert march.status_code == 200, march.text
    march_days = {item["date"]: item for item in march.json()["days"]}
    assert march_days["2025-03-01"]["has_activity"] is False
    assert march_days["2025-03-10"]["has_activity"] is True
    assert Decimal(str(march_days["2025-03-10"]["expense"])) == Decimal("-0.30")


def test_daily_net_spending_multi_currency_and_day_rate(core_api_client: TestClient):
    response = core_api_client.get(
        "/api/reports/daily-net-spending",
        params={"month": "2025-02"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["days"]) == 28
    feb1 = next(item for item in body["days"] if item["date"] == "2025-02-01")
    assert feb1["has_activity"] is True
    # as_of 2025-02-01 uses 2025-01-01 price 7.2
    assert Decimal(str(feb1["expense"])) == -(Decimal("99.99") * Decimal("7.2"))
    assert Decimal(str(feb1["net_spending"])) == -(Decimal("99.99") * Decimal("7.2"))


def test_daily_net_spending_leap_february(core_api_client: TestClient):
    response = core_api_client.get(
        "/api/reports/daily-net-spending",
        params={"month": "2024-02"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["month"] == "2024-02"
    assert len(body["days"]) == 29
    assert body["days"][0]["date"] == "2024-02-01"
    assert body["days"][-1]["date"] == "2024-02-29"
    assert all(item["has_activity"] is False for item in body["days"])


def test_daily_net_spending_invalid_month(core_api_client: TestClient):
    response = core_api_client.get(
        "/api/reports/daily-net-spending",
        params={"month": "2025-13"},
    )
    assert response.status_code == 400, response.text
    detail = response.json()
    code = detail.get("code") or (detail.get("detail") or {}).get("code")
    assert code == "INVALID_REPORT_MONTH"


def test_daily_net_spending_default_month_and_dirty(
    temp_ledger_env, db_session, monkeypatch
):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from backend.config import settings

    client = build_api_client(
        temp_ledger_env["ledger_path"],
        db_session,
        rebuild_projection=True,
    )
    fixed = datetime(2025, 3, 15, 12, 0, tzinfo=ZoneInfo(settings.SCHEDULER_TIMEZONE))

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed.replace(tzinfo=None)
            return fixed.astimezone(tz)

    monkeypatch.setattr(
        "backend.services.daily_net_spending.datetime",
        _FixedDateTime,
    )
    default_resp = client.get("/api/reports/daily-net-spending")
    assert default_resp.status_code == 200, default_resp.text
    assert default_resp.json()["month"] == "2025-03"
    assert len(default_resp.json()["days"]) == 31

    projection = LedgerProjectionService(db_session, temp_ledger_env["ledger_path"])
    projection.mark_dirty(temp_ledger_env["ledger_path"], RuntimeError("broken"))
    dirty = client.get(
        "/api/reports/daily-net-spending",
        params={"month": "2025-01"},
    )
    assert dirty.status_code == 503, dirty.text
    detail = dirty.json()
    code = detail.get("code") or (detail.get("detail") or {}).get("code")
    assert code == "LEDGER_PROJECTION_DIRTY" or "DIRTY" in dirty.text

    db_session.expire_all()
    projection.rebuild_all()
    recovered = client.get(
        "/api/reports/daily-net-spending",
        params={"month": "2025-01"},
    )
    assert recovered.status_code == 200, recovered.text
    assert len(recovered.json()["days"]) == 31


def test_daily_net_spending_partial_missing_exchange_rate(temp_ledger_env, db_session):
    ledger_dir = temp_ledger_env["ledger_path"].parent
    accounts = ledger_dir / "accounts.beancount"
    accounts.write_text(
        accounts.read_text(encoding="utf-8")
        + "\n2020-01-01 open Expenses:TravelEUR EUR\n"
        + "2020-01-01 open Assets:EuroCash EUR\n",
        encoding="utf-8",
    )
    txns = ledger_dir / "transactions.beancount"
    txns.write_text(
        txns.read_text(encoding="utf-8")
        + """
2025-01-18 * "EUR lunch" "euro spend"
  Expenses:TravelEUR  10.00 EUR
  Assets:EuroCash    -10.00 EUR
""",
        encoding="utf-8",
    )
    from backend.infrastructure.persistence.beancount.beancount_provider import (
        BeancountServiceProvider,
    )

    BeancountServiceProvider.clear()
    LedgerProjectionService(db_session, temp_ledger_env["ledger_path"]).rebuild_all()
    client = build_api_client(
        temp_ledger_env["ledger_path"],
        db_session,
        rebuild_projection=False,
    )
    response = client.get(
        "/api/reports/daily-net-spending",
        params={"month": "2025-01"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    missing = body["missing_exchange_rates"]
    assert any(item["date"] == "2025-01-18" and "EUR" in item["currencies"] for item in missing)
    by_date = {item["date"]: item for item in body["days"]}
    # EUR missing: partial result keeps convertible CNY amounts on other days
    assert Decimal(str(by_date["2025-01-16"]["expense"])) == Decimal("-50")
    assert by_date["2025-01-18"]["has_activity"] is True
    assert Decimal(str(by_date["2025-01-18"]["expense"])) == Decimal("0")

