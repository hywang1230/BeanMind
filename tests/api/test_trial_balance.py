"""Trial balance contracts against temporary Beancount ledgers."""
from decimal import Decimal

from tests.conftest import build_api_client


def _category(body: dict, kind: str) -> dict:
    return next(item for item in body["categories"] if item["type"] == kind)


def test_trial_balance_preserves_raw_signs_and_parent_postings(core_api_client):
    response = core_api_client.get(
        "/api/reports/trial-balance", params={"as_of_date": "2025-03-31"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["as_of_date"] == "2025-03-31"
    assert [item["type"] for item in body["categories"]] == [
        "Assets", "Liabilities", "Equity", "Income", "Expenses"
    ]
    assert body["ledger_error_count"] == 0
    assert Decimal(str(_category(body, "Assets")["total_cny"])) == Decimal("17389.772")
    assert Decimal(str(_category(body, "Liabilities")["total_cny"])) == Decimal("-300")
    assert Decimal(str(_category(body, "Equity")["total_cny"])) == Decimal("-7860")
    assert Decimal(str(_category(body, "Income")["total_cny"])) == Decimal("-10000")
    assert Decimal(str(_category(body, "Expenses")["total_cny"])) == Decimal("770.228")
    assert Decimal(str(body["signed_sum_cny"])) == Decimal("0")

    food = next(
        item for item in _category(body, "Expenses")["accounts"]
        if item["account"] == "Expenses:Food"
    )
    assert Decimal(str(food["balances"]["CNY"])) == Decimal("50.10")
    assert Decimal(str(food["children"][0]["balances"]["CNY"])) == Decimal("30.00")
    assert all(not item.get("is_virtual") for category in body["categories"] for item in category["accounts"])


def test_trial_balance_empty_and_invalid_dates(core_api_client):
    empty = core_api_client.get(
        "/api/reports/trial-balance", params={"as_of_date": "2020-01-01"}
    )
    assert empty.status_code == 200, empty.text
    body = empty.json()
    assert len(body["categories"]) == 5
    assert all(not category["accounts"] for category in body["categories"])
    assert Decimal(str(body["signed_sum_cny"])) == Decimal("0")
    invalid = core_api_client.get(
        "/api/reports/trial-balance", params={"as_of_date": "2025-02-30"}
    )
    assert invalid.status_code == 400


def test_trial_balance_conversion_residual_is_reported_not_hidden(temp_ledger_env, db_session):
    txns = temp_ledger_env["ledger_path"].parent / "transactions.beancount"
    txns.write_text(
        txns.read_text(encoding="utf-8")
        + '\n2025-03-15 * "换汇"\n  Assets:Cash -10 USD @ 7.30 CNY\n'
        + '  Assets:Bank:Checking 73 CNY\n',
        encoding="utf-8",
    )
    client = build_api_client(temp_ledger_env["ledger_path"], db_session)
    response = client.get(
        "/api/reports/trial-balance", params={"as_of_date": "2025-03-31"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ledger_error_count"] == 0
    assert Decimal(str(body["signed_sum_cny"])) == Decimal("1")
    assert Decimal(str(_category(body, "Assets")["total_cny"])) == Decimal("17390.772")


def test_trial_balance_sums_multiple_cost_positions_of_same_currency(temp_ledger_env, db_session):
    ledger_dir = temp_ledger_env["ledger_path"].parent
    accounts = ledger_dir / "accounts.beancount"
    accounts.write_text(
        accounts.read_text(encoding="utf-8") + "\n2020-01-01 open Assets:Lots STK\n",
        encoding="utf-8",
    )
    prices = ledger_dir / "prices.beancount"
    prices.write_text(
        prices.read_text(encoding="utf-8") + "\n2025-01-01 price STK 10 CNY\n",
        encoding="utf-8",
    )
    txns = ledger_dir / "transactions.beancount"
    txns.write_text(
        txns.read_text(encoding="utf-8")
        + '\n2025-03-18 * "批次一"\n  Assets:Lots 1 STK {10 CNY}\n'
        + '  Assets:Cash -10 CNY\n'
        + '\n2025-03-19 * "批次二"\n  Assets:Lots 2 STK {11 CNY}\n'
        + '  Assets:Cash -22 CNY\n',
        encoding="utf-8",
    )
    client = build_api_client(temp_ledger_env["ledger_path"], db_session)
    trial = client.get("/api/reports/trial-balance", params={"as_of_date": "2025-03-31"})
    assert trial.status_code == 200, trial.text
    body = trial.json()
    assert body["ledger_error_count"] == 0
    lots = next(
        item for item in _category(body, "Assets")["accounts"]
        if item["account"] == "Assets:Lots"
    )
    assert Decimal(str(lots["balances"]["STK"])) == Decimal("3")
    assert Decimal(str(lots["total_cny"])) == Decimal("30")
    assert Decimal(str(body["signed_sum_cny"])) == Decimal("-2")
    balance_sheet = client.get("/api/reports/balance-sheet", params={"as_of_date": "2025-03-31"})
    assert balance_sheet.status_code == 200, balance_sheet.text
    sheet_lots = next(
        item for item in balance_sheet.json()["assets"]["accounts"]
        if item["account"] == "Assets:Lots"
    )
    assert Decimal(str(sheet_lots["balances"]["STK"])) == Decimal("3")


def test_trial_balance_missing_rate_and_ledger_error_count(temp_ledger_env, db_session):
    ledger_dir = temp_ledger_env["ledger_path"].parent
    accounts = ledger_dir / "accounts.beancount"
    accounts.write_text(
        accounts.read_text(encoding="utf-8")
        + "\n2020-01-01 open Assets:EuroCash EUR\n"
        + "2020-01-01 open Equity:EuroOpening EUR\n",
        encoding="utf-8",
    )
    txns = ledger_dir / "transactions.beancount"
    txns.write_text(
        txns.read_text(encoding="utf-8")
        + '\n2025-03-20 * "欧元"\n  Assets:EuroCash 10 EUR\n'
        + '  Equity:EuroOpening -10 EUR\n',
        encoding="utf-8",
    )
    client = build_api_client(temp_ledger_env["ledger_path"], db_session)
    missing = client.get("/api/reports/trial-balance", params={"as_of_date": "2025-03-31"})
    assert missing.status_code == 400
    assert "MISSING_EXCHANGE_RATE" in missing.text

    txns.write_text(
        txns.read_text(encoding="utf-8")
        + "\n2025-03-21 balance Assets:Cash 999999 CNY\n",
        encoding="utf-8",
    )
    prices = ledger_dir / "prices.beancount"
    prices.write_text(
        prices.read_text(encoding="utf-8") + "\n2025-01-01 price EUR 8 CNY\n",
        encoding="utf-8",
    )
    client = build_api_client(temp_ledger_env["ledger_path"], db_session)
    response = client.get("/api/reports/trial-balance", params={"as_of_date": "2025-03-31"})
    assert response.status_code == 200, response.text
    assert response.json()["ledger_error_count"] == 1
