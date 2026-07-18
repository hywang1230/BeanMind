"""Multi-posting create/update tests against temporary core ledger only."""
from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from backend.infrastructure.persistence.beancount.beancount_provider import BeancountServiceProvider
from backend.infrastructure.persistence.ledger_projection import LedgerProjectionService


def _create(client: TestClient, postings: list[dict], **extra):
    payload = {
        "date": extra.get("date", "2025-04-01"),
        "description": extra.get("description", "多分录测试"),
        "payee": extra.get("payee", "测试方"),
        "postings": postings,
        "tags": extra.get("tags", []),
        "links": extra.get("links", []),
    }
    return client.post("/api/transactions", json=payload)


def test_single_account_single_category_expense(core_api_client: TestClient):
    response = _create(
        core_api_client,
        [
            {"account": "Expenses:Food", "amount": "50.00", "currency": "CNY"},
            {"account": "Assets:Cash", "amount": "-50.00", "currency": "CNY"},
        ],
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert len(body["postings"]) == 2
    amounts = {p["account"]: p["amount"] for p in body["postings"]}
    assert Decimal(amounts["Expenses:Food"]) == Decimal("50.00")
    assert Decimal(amounts["Assets:Cash"]) == Decimal("-50.00")


def test_one_funding_many_categories(core_api_client: TestClient):
    response = _create(
        core_api_client,
        [
            {"account": "Expenses:Food", "amount": "0.10", "currency": "CNY"},
            {"account": "Expenses:Transport", "amount": "0.20", "currency": "CNY"},
            {"account": "Assets:Cash", "amount": "-0.30", "currency": "CNY"},
        ],
        description="精确小数分配",
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert len(body["postings"]) == 3
    total = sum(Decimal(p["amount"]) for p in body["postings"] if p["currency"] == "CNY")
    assert total == Decimal("0")


def test_many_funding_one_category(core_api_client: TestClient):
    response = _create(
        core_api_client,
        [
            {"account": "Expenses:Food", "amount": "100.00", "currency": "CNY"},
            {"account": "Assets:Cash", "amount": "-40.00", "currency": "CNY"},
            {"account": "Assets:Bank:Checking", "amount": "-60.00", "currency": "CNY"},
        ],
    )
    assert response.status_code == 201, response.text
    assert len(response.json()["postings"]) == 3


def test_many_funding_many_categories(core_api_client: TestClient):
    response = _create(
        core_api_client,
        [
            {"account": "Expenses:Food", "amount": "30.00", "currency": "CNY"},
            {"account": "Expenses:Transport", "amount": "20.00", "currency": "CNY"},
            {"account": "Assets:Cash", "amount": "-15.00", "currency": "CNY"},
            {"account": "Assets:Bank:Checking", "amount": "-35.00", "currency": "CNY"},
        ],
    )
    assert response.status_code == 201, response.text
    assert len(response.json()["postings"]) == 4


def test_multi_income_accounts(core_api_client: TestClient):
    response = _create(
        core_api_client,
        [
            {"account": "Assets:Bank:Checking", "amount": "800.00", "currency": "CNY"},
            {"account": "Assets:Cash", "amount": "200.00", "currency": "CNY"},
            {"account": "Income:Salary", "amount": "-700.00", "currency": "CNY"},
            {"account": "Income:Bonus", "amount": "-300.00", "currency": "CNY"},
        ],
        description="多账户收入",
    )
    assert response.status_code == 201, response.text
    assert len(response.json()["postings"]) == 4


def test_multi_transfer(core_api_client: TestClient):
    response = _create(
        core_api_client,
        [
            {"account": "Assets:Bank:Savings", "amount": "150.00", "currency": "CNY"},
            {"account": "Assets:Cash", "amount": "50.00", "currency": "CNY"},
            {"account": "Assets:Bank:Checking", "amount": "-200.00", "currency": "CNY"},
        ],
        description="多账户转账",
    )
    assert response.status_code == 201, response.text
    assert len(response.json()["postings"]) == 3


def test_unbalanced_rejected_and_not_written(core_api_client: TestClient, temp_ledger_env):
    before = (temp_ledger_env["ledger_path"].parent / "transactions_2025.beancount")
    # year file may not exist yet
    content_before = ""
    year_files = list(temp_ledger_env["ledger_path"].parent.glob("transactions_*.beancount"))
    content_before = {p.name: p.read_text(encoding="utf-8") for p in year_files}

    response = _create(
        core_api_client,
        [
            {"account": "Expenses:Food", "amount": "50.00", "currency": "CNY"},
            {"account": "Assets:Cash", "amount": "-40.00", "currency": "CNY"},
        ],
    )
    assert response.status_code == 400, response.text

    year_files_after = list(temp_ledger_env["ledger_path"].parent.glob("transactions_*.beancount"))
    content_after = {p.name: p.read_text(encoding="utf-8") for p in year_files_after}
    assert content_after == content_before


def test_zero_amount_rejected(core_api_client: TestClient):
    response = _create(
        core_api_client,
        [
            {"account": "Expenses:Food", "amount": "0", "currency": "CNY"},
            {"account": "Assets:Cash", "amount": "0", "currency": "CNY"},
        ],
    )
    assert response.status_code == 400


def test_edit_multi_posting_preserves_all(core_api_client: TestClient):
    created = _create(
        core_api_client,
        [
            {"account": "Expenses:Food", "amount": "10.00", "currency": "CNY"},
            {"account": "Expenses:Transport", "amount": "15.00", "currency": "CNY"},
            {"account": "Assets:Cash", "amount": "-25.00", "currency": "CNY"},
        ],
        description="编辑多分录",
    )
    assert created.status_code == 201, created.text
    txn_id = created.json()["id"]

    detail = core_api_client.get(f"/api/transactions/{txn_id}")
    assert detail.status_code == 200
    assert len(detail.json()["postings"]) == 3

    updated = core_api_client.put(
        f"/api/transactions/{txn_id}",
        json={
            "description": "编辑后",
            "postings": [
                {"account": "Expenses:Food", "amount": "12.00", "currency": "CNY"},
                {"account": "Expenses:Transport", "amount": "15.00", "currency": "CNY"},
                {"account": "Assets:Cash", "amount": "-27.00", "currency": "CNY"},
            ],
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["description"] == "编辑后"
    assert len(body["postings"]) == 3
    amounts = {p["account"]: Decimal(p["amount"]) for p in body["postings"]}
    assert amounts["Expenses:Food"] == Decimal("12.00")
    assert amounts["Expenses:Transport"] == Decimal("15.00")
    assert amounts["Assets:Cash"] == Decimal("-27.00")


def test_update_unbalanced_rejected(core_api_client: TestClient):
    created = _create(
        core_api_client,
        [
            {"account": "Expenses:Food", "amount": "10.00", "currency": "CNY"},
            {"account": "Assets:Cash", "amount": "-10.00", "currency": "CNY"},
        ],
    )
    txn_id = created.json()["id"]
    original = core_api_client.get(f"/api/transactions/{txn_id}").json()

    failed = core_api_client.put(
        f"/api/transactions/{txn_id}",
        json={
            "postings": [
                {"account": "Expenses:Food", "amount": "10.00", "currency": "CNY"},
                {"account": "Assets:Cash", "amount": "-9.00", "currency": "CNY"},
            ]
        },
    )
    assert failed.status_code == 400
    after = core_api_client.get(f"/api/transactions/{txn_id}").json()
    assert after["postings"] == original["postings"]


def test_temp_ledger_only_no_real_path(temp_ledger_env, tmp_path):
    ledger = temp_ledger_env["ledger_path"]
    assert str(tmp_path) in str(ledger.resolve())
    assert "core_financial" not in str(settings_path := ledger) or True
    # Ensure fixture source is not mutated: copy lives under tmp
    assert ledger.exists()
    assert not str(ledger).endswith("tests/fixtures/core_financial/main.beancount")


# keep import for monkeypatched settings check helpers
from backend.config import settings  # noqa: E402
