"""Account create / close / reopen against temporary core ledger only."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_create_account_success(core_api_client: TestClient):
    response = core_api_client.post(
        "/api/accounts",
        json={
            "name": "Assets:Bank:NewCard",
            "account_type": "Assets",
            "currencies": ["CNY"],
            "open_date": "2025-05-01",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "Assets:Bank:NewCard"
    assert body.get("is_active") in (True, None) or body.get("close_date") in (None, "")


def test_create_duplicate_rejected(core_api_client: TestClient):
    response = core_api_client.post(
        "/api/accounts",
        json={
            "name": "Assets:Cash",
            "account_type": "Assets",
            "currencies": ["CNY"],
        },
    )
    assert response.status_code == 400


def test_create_type_mismatch_rejected(core_api_client: TestClient):
    response = core_api_client.post(
        "/api/accounts",
        json={
            "name": "Assets:Something",
            "account_type": "Expenses",
            "currencies": ["CNY"],
        },
    )
    assert response.status_code == 400


def test_close_zero_balance_leaf(core_api_client: TestClient):
    response = core_api_client.request(
        "DELETE",
        "/api/accounts/Assets:EmptyWallet",
        json={"close_date": "2025-05-01"},
    )
    assert response.status_code == 200, response.text
    detail = core_api_client.get("/api/accounts/Assets:EmptyWallet")
    assert detail.status_code == 200
    body = detail.json()
    assert body.get("is_active") is False or body.get("close_date")


def test_close_non_zero_balance_rejected(core_api_client: TestClient):
    response = core_api_client.request(
        "DELETE",
        "/api/accounts/Assets:Cash",
        json={"close_date": "2025-05-01"},
    )
    assert response.status_code == 400, response.text
    text = response.text
    assert "余额" in text or "balance" in text.lower() or "CNY" in text or "USD" in text


def test_close_with_active_children_rejected(core_api_client: TestClient):
    response = core_api_client.request(
        "DELETE",
        "/api/accounts/Assets:Bank",
        json={"close_date": "2025-05-01"},
    )
    # Assets:Bank may be synthetic - if not exist 404; if exists with children 400
    assert response.status_code in (400, 404)


def test_close_already_closed_rejected(core_api_client: TestClient):
    response = core_api_client.request(
        "DELETE",
        "/api/accounts/Assets:ClosedLater",
        json={"close_date": "2025-05-01"},
    )
    assert response.status_code == 400


def test_reopen_closed_account(core_api_client: TestClient):
    response = core_api_client.post("/api/accounts/Assets:ClosedLater/reopen")
    assert response.status_code == 200, response.text
    detail = core_api_client.get("/api/accounts/Assets:ClosedLater")
    assert detail.status_code == 200
    body = detail.json()
    assert body.get("is_active") is True or not body.get("close_date")


def test_reopen_active_rejected(core_api_client: TestClient):
    response = core_api_client.post("/api/accounts/Assets:Cash/reopen")
    assert response.status_code == 400


def test_closed_account_excluded_from_active_list(core_api_client: TestClient):
    closed = core_api_client.request(
        "DELETE",
        "/api/accounts/Assets:EmptyWallet",
        json={"close_date": "2025-05-01"},
    )
    assert closed.status_code == 200, closed.text
    active = core_api_client.get("/api/accounts", params={"active_only": True})
    assert active.status_code == 200
    names = [a["name"] for a in active.json()["accounts"]]
    assert "Assets:EmptyWallet" not in names


def test_close_date_before_open_rejected(core_api_client: TestClient):
    response = core_api_client.request(
        "DELETE",
        "/api/accounts/Assets:EmptyWallet",
        json={"close_date": "2019-01-01"},
    )
    assert response.status_code == 400


def test_create_account_unknown_currency_rejected(core_api_client: TestClient):
    response = core_api_client.post(
        "/api/accounts",
        json={
            "name": "Assets:Bank:FxGhost",
            "account_type": "Assets",
            "currencies": ["ZZZ"],
            "open_date": "2025-05-01",
        },
    )
    assert response.status_code == 400, response.text
    body = response.json()
    assert body.get("code") in ("UNKNOWN_CURRENCY", "INVALID_CURRENCY_CODE") or "ZZZ" in response.text
