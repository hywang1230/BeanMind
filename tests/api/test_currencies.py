"""币种目录 API 与种子行为。"""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from backend.config import get_db, settings
from backend.infrastructure.persistence.beancount.beancount_provider import BeancountServiceProvider
from backend.infrastructure.persistence.db.models import MonthlyBudget
from backend.main import app
from backend.services.currency_catalog import CurrencyCatalogService

CORE_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "core_financial"


def _bind_temp_ledger(tmp_path: Path, monkeypatch) -> Path:
    """绑定临时 core fixture 账本，避免依赖真实 LEDGER_FILE。"""
    target = tmp_path / "currency_ledger"
    shutil.copytree(CORE_FIXTURE, target)
    ledger = target / "main.beancount"
    BeancountServiceProvider.clear()
    monkeypatch.setattr(settings, "LEDGER_FILE", ledger)
    return ledger


def test_currency_catalog_seed_list_create_and_operating_guard(
    db_session, tmp_path, monkeypatch
) -> None:
    _bind_temp_ledger(tmp_path, monkeypatch)
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        listed = client.get("/api/currencies")
        assert listed.status_code == 200, listed.text
        body = listed.json()
        codes = [item["code"] for item in body["currencies"]]
        # 默认仅预置人民币/美元（经营币种若非 CNY 会额外确保其存在）
        assert "CNY" in codes and "USD" in codes
        assert "EUR" not in codes
        assert body["total"] == len(set(codes))
        assert set(codes).issuperset({"CNY", "USD"})
        assert len(codes) <= 3  # CNY/USD + 可能的非 CNY 经营币种
        # core fixture 账本使用了 CNY/USD
        by_code = {item["code"]: item for item in body["currencies"]}
        assert by_code["CNY"]["in_use"] is True
        assert by_code["USD"]["in_use"] is True
        assert by_code["CNY"]["is_operating"] is True
        assert by_code["USD"]["is_operating"] is False

        enabled = client.get("/api/currencies", params={"enabled_only": True})
        assert enabled.status_code == 200
        assert all(item["enabled"] for item in enabled.json()["currencies"])

        created = client.post(
            "/api/currencies",
            json={"code": "nzd", "name": "新西兰元", "symbol": "NZ$"},
        )
        assert created.status_code == 201, created.text
        assert created.json()["code"] == "NZD"
        assert created.json()["enabled"] is True
        assert created.json()["in_use"] is False

        dup = client.post(
            "/api/currencies",
            json={"code": "NZD", "name": "重复"},
        )
        assert dup.status_code == 409
        assert dup.json()["code"] == "CURRENCY_ALREADY_EXISTS"

        invalid = client.post(
            "/api/currencies",
            json={"code": "US1", "name": "非法"},
        )
        assert invalid.status_code == 400
        assert invalid.json()["code"] == "INVALID_CURRENCY_CODE"

        op = CurrencyCatalogService(db_session).operating_currency
        disable_op = client.patch(f"/api/currencies/{op}", json={"enabled": False})
        assert disable_op.status_code == 400
        assert disable_op.json()["code"] == "CANNOT_DISABLE_OPERATING_CURRENCY"

        # 已使用币种不可停用
        disable_usd = client.patch("/api/currencies/USD", json={"enabled": False})
        assert disable_usd.status_code == 400
        assert disable_usd.json()["code"] == "CURRENCY_IN_USE"

        # 未使用币种可停用；enabled_only 不再包含
        disable_nzd = client.patch("/api/currencies/NZD", json={"enabled": False})
        assert disable_nzd.status_code == 200, disable_nzd.text
        assert disable_nzd.json()["enabled"] is False
        enabled_codes = [
            c["code"]
            for c in client.get("/api/currencies", params={"enabled_only": True}).json()[
                "currencies"
            ]
        ]
        assert "NZD" not in enabled_codes
        all_codes = [c["code"] for c in client.get("/api/currencies").json()["currencies"]]
        assert "NZD" in all_codes
    finally:
        app.dependency_overrides.clear()
        BeancountServiceProvider.clear()


def test_currency_in_use_cannot_disable_or_delete(db_session, tmp_path, monkeypatch) -> None:
    _bind_temp_ledger(tmp_path, monkeypatch)
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)

        created = client.post(
            "/api/currencies",
            json={"code": "NZD", "name": "新西兰元", "symbol": "NZ$"},
        )
        assert created.status_code == 201, created.text
        assert created.json()["in_use"] is False

        # 预算引用后视为使用中
        db_session.add(MonthlyBudget(month="2026-07", currency="NZD"))
        db_session.commit()

        listed = client.get("/api/currencies")
        assert listed.status_code == 200
        nzd = next(item for item in listed.json()["currencies"] if item["code"] == "NZD")
        assert nzd["in_use"] is True

        disable = client.patch("/api/currencies/NZD", json={"enabled": False})
        assert disable.status_code == 400
        assert disable.json()["code"] == "CURRENCY_IN_USE"

        delete_used = client.delete("/api/currencies/NZD")
        assert delete_used.status_code == 400
        assert delete_used.json()["code"] == "CURRENCY_IN_USE"

        # 解除引用后可删除
        db_session.query(MonthlyBudget).filter(MonthlyBudget.currency == "NZD").delete()
        db_session.commit()

        delete_ok = client.delete("/api/currencies/NZD")
        assert delete_ok.status_code == 204, delete_ok.text
        codes = [item["code"] for item in client.get("/api/currencies").json()["currencies"]]
        assert "NZD" not in codes

        # 经营币种不可删除
        op = CurrencyCatalogService(db_session).operating_currency
        delete_op = client.delete(f"/api/currencies/{op}")
        assert delete_op.status_code == 400
        assert delete_op.json()["code"] == "CANNOT_DELETE_OPERATING_CURRENCY"
    finally:
        app.dependency_overrides.clear()
        BeancountServiceProvider.clear()
