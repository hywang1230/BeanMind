"""每月自动汇率：换算、取数、提交、调度补跑与 API。"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.application.services.monthly_exchange_rate import (
    MonthlyExchangeRateService,
    cny_rates_from_safe_rows,
    existing_pair_currencies,
    format_price_rate,
    operating_rates_from_cny,
    should_catch_up_monthly_fx,
)
from backend.config import get_db, settings
from backend.infrastructure.fx.safe_fx_client import SAFE_FX_URL, SafeFxClient
from backend.infrastructure.persistence.beancount.beancount_provider import BeancountServiceProvider
from backend.infrastructure.persistence.beancount import ledger_write as writer
from backend.infrastructure.persistence.beancount.ledger_write import LedgerWriteConflict, _workspace
from backend.infrastructure.persistence.db.models.ledger_projection import LedgerIndexFile, LedgerTransaction
from backend.infrastructure.persistence.ledger_projection import LedgerProjectionService, PROJECTION_READY
from backend.infrastructure.scheduler.recurring_scheduler import RecurringScheduler
from backend.interfaces.api import exchange_rate as exchange_rate_api
from backend.main import app
from backend.services.currency_catalog import CurrencyCatalogService
from beancount.core.amount import Amount
from beancount.core.data import Price


USD_CNY_ROW = [Decimal("100"), "美元", Decimal("671.68"), "人民币"]
KRW_CNY_ROW = [Decimal("100"), "人民币", Decimal("20299"), "韩元"]
SAMPLE_ROWS = [USD_CNY_ROW, KRW_CNY_ROW]


class FakeFxClient:
    def __init__(self, payload_by_date: dict[str, list] | None = None) -> None:
        self.payload_by_date = payload_by_date or {}
        self.calls: list[date] = []

    def fetch_first_quote_day(self, start_date: date, *, max_lookback_days: int = 10):
        for offset in range(max_lookback_days + 1):
            day = start_date - timedelta(days=offset)
            self.calls.append(day)
            rows = self.payload_by_date.get(day.isoformat())
            if rows:
                return day, rows
        return None


def _write_ledger(path: Path, *, operating: str = "CNY", extra: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'option "title" "monthly fx test"\n'
        f'option "operating_currency" "{operating}"\n\n'
        f"2020-01-01 open Assets:Cash {operating}\n"
        f"{extra}",
        encoding="utf-8",
    )
    return path


def _bind_ledger(tmp_path: Path, monkeypatch, *, operating: str = "CNY", extra: str = "") -> Path:
    ledger = _write_ledger(tmp_path / "ledger" / "main.beancount", operating=operating, extra=extra)
    BeancountServiceProvider.clear()
    monkeypatch.setattr(settings, "LEDGER_FILE", ledger)
    return ledger


def _seed_catalog(db_session, operating: str, extra_codes: list[str]) -> None:
    catalog = CurrencyCatalogService(db_session, operating_currency=operating)
    catalog.ensure_seeded()
    for code in extra_codes:
        if catalog.get(code) is None:
            catalog.create(code, code, enabled=True)


def test_format_price_rate_strips_zeros_without_scientific_notation() -> None:
    assert format_price_rate(Decimal("6.7168")) == "6.7168"
    assert format_price_rate(Decimal("2") / Decimal("3")) == "0.66666667"
    tiny = Decimal("1e-8")
    assert format_price_rate(tiny) == "0.00000001"
    assert "e" not in format_price_rate(tiny).lower()


def test_cny_rates_cover_both_quote_directions() -> None:
    rates = cny_rates_from_safe_rows(SAMPLE_ROWS)
    assert rates["USD"] == Decimal("671.68") / Decimal("100")
    assert rates["KRW"] == Decimal("100") / Decimal("20299")
    assert "CNY" not in rates
    assert cny_rates_from_safe_rows([[100.0, "美元", 671.68, "人民币"]]) == {}
    assert cny_rates_from_safe_rows([[Decimal("100"), "比特币", Decimal("1"), "人民币"]]) == {}
    assert cny_rates_from_safe_rows([[Decimal("0"), "美元", Decimal("1"), "人民币"]]) == {}


def test_operating_cross_rate_and_missing_operating_blocks_batch() -> None:
    cny_rates = cny_rates_from_safe_rows(SAMPLE_ROWS)
    as_cny = operating_rates_from_cny(cny_rates, operating="CNY", currencies=["USD", "KRW", "EUR"])
    assert as_cny is not None
    assert "EUR" not in as_cny
    assert format_price_rate(as_cny["USD"]) == "6.7168"
    assert format_price_rate(as_cny["KRW"]) == format(
        (Decimal("100") / Decimal("20299")).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP),
        "f",
    ).rstrip("0").rstrip(".")

    as_usd = operating_rates_from_cny(cny_rates, operating="USD", currencies=["KRW", "CNY"])
    assert as_usd is not None
    assert format_price_rate(as_usd["KRW"]) == format_price_rate(
        (Decimal("100") / Decimal("20299")) / (Decimal("671.68") / Decimal("100"))
    )
    assert format_price_rate(as_usd["CNY"]) == format_price_rate(
        Decimal("1") / (Decimal("671.68") / Decimal("100"))
    )
    assert operating_rates_from_cny(cny_rates, operating="EUR", currencies=["USD"]) is None


def test_existing_pair_matches_either_direction() -> None:
    effective = date(2026, 11, 1)
    entries = [
        Price({}, effective, "USD", Amount(Decimal("7"), "CNY")),
        Price({}, effective, "CNY", Amount(Decimal("190"), "KRW")),
        Price({}, date(2026, 10, 1), "EUR", Amount(Decimal("8"), "CNY")),
    ]
    found = existing_pair_currencies(
        entries,
        effective_date=effective,
        operating="CNY",
        currencies=["USD", "KRW", "EUR"],
    )
    assert found == {"USD", "KRW"}


def test_safe_client_lookback_uses_first_non_empty_json_array() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        day = request.url.params.get("date")
        assert str(request.url).startswith(SAFE_FX_URL)
        assert request.headers.get("cookie") in (None, "")
        if day == "2026-11-01":
            return httpx.Response(200, content=b"[]")
        if day == "2026-10-31":
            body = '[[100, "美元", 671.68, "人民币"]]'
            return httpx.Response(200, content=body.encode("utf-8"))
        return httpx.Response(500, content=b"ignored-body")

    client = SafeFxClient(transport=httpx.MockTransport(handler))
    found = client.fetch_first_quote_day(date(2026, 11, 1), max_lookback_days=10)
    assert found is not None
    source_date, rows = found
    assert source_date == date(2026, 10, 31)
    assert rows[0][0] == Decimal("100")
    assert rows[0][2] == Decimal("671.68")
    assert not isinstance(rows[0][2], float)


def test_safe_client_unavailable_after_eleven_empty_days() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.params["date"])
        return httpx.Response(200, content=b"[]")

    client = SafeFxClient(transport=httpx.MockTransport(handler))
    assert client.fetch_first_quote_day(date(2026, 11, 1)) is None
    assert calls[0] == "2026-11-01"
    assert calls[-1] == "2026-10-22"
    assert len(calls) == 11


def test_generate_writes_first_of_month_from_lookback_day(db_session, tmp_path, monkeypatch) -> None:
    ledger = _bind_ledger(tmp_path, monkeypatch)
    _seed_catalog(db_session, "CNY", ["KRW"])
    fx = FakeFxClient({"2026-10-31": SAMPLE_ROWS})
    service = MonthlyExchangeRateService(db_session, ledger, fx_client=fx, timezone="Asia/Shanghai")
    now = datetime(2026, 11, 15, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    result = service.generate_current_month(now=now)
    assert result["status"] == "completed"
    assert result["effective_date"] == "2026-11-01"
    assert result["source_date"] == "2026-10-31"
    assert result["written"] == ["USD", "KRW"]
    text = ledger.read_text(encoding="utf-8")
    assert "2026-11-01 price USD 6.7168 CNY" in text
    expected_krw = format_price_rate(Decimal("100") / Decimal("20299"))
    assert f"2026-11-01 price KRW {expected_krw} CNY" in text
    assert fx.calls[0] == date(2026, 11, 1)


def test_generate_unavailable_leaves_ledger_unchanged(db_session, tmp_path, monkeypatch) -> None:
    ledger = _bind_ledger(tmp_path, monkeypatch)
    original = ledger.read_text(encoding="utf-8")
    _seed_catalog(db_session, "CNY", [])
    service = MonthlyExchangeRateService(
        db_session, ledger, fx_client=FakeFxClient({}), timezone="Asia/Shanghai"
    )
    result = service.generate_current_month(
        now=datetime(2026, 11, 1, 11, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    )
    assert result["status"] == "unavailable"
    assert result["source_date"] is None
    assert result["written"] == []
    assert ledger.read_text(encoding="utf-8") == original


def test_generate_skips_existing_either_direction(db_session, tmp_path, monkeypatch) -> None:
    extra = "2026-11-01 price CNY 0.1488 USD\n"
    ledger = _bind_ledger(tmp_path, monkeypatch, extra=extra)
    original = ledger.read_text(encoding="utf-8")
    _seed_catalog(db_session, "CNY", ["KRW"])
    service = MonthlyExchangeRateService(
        db_session,
        ledger,
        fx_client=FakeFxClient({"2026-11-01": SAMPLE_ROWS}),
        timezone="Asia/Shanghai",
    )
    result = service.generate_current_month(
        now=datetime(2026, 11, 1, 11, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    )
    assert result["status"] == "completed"
    assert result["skipped"] == ["USD"]
    assert "KRW" in result["written"]
    text = ledger.read_text(encoding="utf-8")
    assert text.count("price USD") == 0
    assert "2026-11-01 price CNY 0.1488 USD" in text
    assert "2026-11-01 price KRW" in text


def test_generate_blocks_when_operating_missing_from_quotes(db_session, tmp_path, monkeypatch) -> None:
    ledger = _bind_ledger(tmp_path, monkeypatch, operating="EUR")
    original = ledger.read_text(encoding="utf-8")
    _seed_catalog(db_session, "EUR", ["KRW"])
    service = MonthlyExchangeRateService(
        db_session,
        ledger,
        fx_client=FakeFxClient({"2026-11-01": SAMPLE_ROWS}),
        timezone="Asia/Shanghai",
    )
    result = service.generate_current_month(
        now=datetime(2026, 11, 1, 11, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    )
    assert result["status"] == "unavailable"
    assert result["written"] == []
    assert ledger.read_text(encoding="utf-8") == original


def test_generate_writes_cross_rate_when_operating_is_usd(db_session, tmp_path, monkeypatch) -> None:
    ledger = _bind_ledger(tmp_path, monkeypatch, operating="USD")
    _seed_catalog(db_session, "USD", ["KRW"])
    service = MonthlyExchangeRateService(
        db_session,
        ledger,
        fx_client=FakeFxClient({"2026-11-01": SAMPLE_ROWS}),
        timezone="Asia/Shanghai",
    )
    result = service.generate_current_month(
        now=datetime(2026, 11, 1, 11, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    )
    assert result["status"] == "completed"
    assert "KRW" in result["written"]
    assert "CNY" in result["written"]
    assert "USD" not in result["written"]
    text = ledger.read_text(encoding="utf-8")
    expected_krw = format_price_rate(
        (Decimal("100") / Decimal("20299")) / (Decimal("671.68") / Decimal("100"))
    )
    assert f"2026-11-01 price KRW {expected_krw} USD" in text
    assert "2026-11-01 price USD" not in text


def test_pending_manifest_blocks_generate(db_session, tmp_path, monkeypatch) -> None:
    ledger = _bind_ledger(tmp_path, monkeypatch)
    original = ledger.read_text(encoding="utf-8")
    _seed_catalog(db_session, "CNY", [])
    workspace = _workspace(ledger.resolve())
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "manifest.json").write_text("{}", encoding="utf-8")
    service = MonthlyExchangeRateService(
        db_session,
        ledger,
        fx_client=FakeFxClient({"2026-11-01": SAMPLE_ROWS}),
        timezone="Asia/Shanghai",
    )
    with pytest.raises(LedgerWriteConflict):
        service.generate_current_month(
            now=datetime(2026, 11, 1, 11, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
        )
    assert ledger.read_text(encoding="utf-8") == original


def test_successful_commit_keeps_projection_ready_without_transactions(
    db_session, tmp_path, monkeypatch
) -> None:
    ledger = _bind_ledger(tmp_path, monkeypatch)
    _seed_catalog(db_session, "CNY", ["KRW"])
    projection = LedgerProjectionService(db_session, ledger)
    projection.rebuild_all()
    before = db_session.query(LedgerTransaction).count()
    before_record = db_session.get(LedgerIndexFile, str(ledger.resolve()))
    assert before_record is not None
    before_hash = before_record.content_hash
    service = MonthlyExchangeRateService(
        db_session,
        ledger,
        fx_client=FakeFxClient({"2026-11-01": SAMPLE_ROWS}),
        timezone="Asia/Shanghai",
    )
    result = service.generate_current_month(
        now=datetime(2026, 11, 1, 11, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    )
    assert result["written"]
    assert "2026-11-01 price USD 6.7168 CNY" in ledger.read_text(encoding="utf-8")
    assert db_session.query(LedgerTransaction).count() == before
    db_session.expire_all()
    after_record = db_session.get(LedgerIndexFile, str(ledger.resolve()))
    assert after_record is not None
    assert after_record.status == PROJECTION_READY
    assert after_record.content_hash != before_hash
    assert after_record.content_hash == writer.file_fingerprint(ledger)[2]
    status = projection.ensure_current()
    assert status["status"] == PROJECTION_READY


def test_commit_interrupt_before_replace_keeps_official_ledger(
    db_session, tmp_path, monkeypatch
) -> None:
    ledger = _bind_ledger(tmp_path, monkeypatch)
    original = ledger.read_bytes()
    _seed_catalog(db_session, "CNY", ["KRW"])
    LedgerProjectionService(db_session, ledger).rebuild_all()

    def fail_dirty(self, paths, error="write pending"):
        raise RuntimeError("dirty failed")

    monkeypatch.setattr(LedgerProjectionService, "mark_dirty_files", fail_dirty)
    service = MonthlyExchangeRateService(
        db_session,
        ledger,
        fx_client=FakeFxClient({"2026-11-01": SAMPLE_ROWS}),
        timezone="Asia/Shanghai",
    )
    with pytest.raises(RuntimeError, match="dirty failed"):
        service.generate_current_month(
            now=datetime(2026, 11, 1, 11, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
        )
    assert ledger.read_bytes() == original
    assert not writer.has_pending_write(ledger)


def test_missing_currency_in_selected_day_does_not_look_further(
    db_session, tmp_path, monkeypatch
) -> None:
    ledger = _bind_ledger(tmp_path, monkeypatch)
    _seed_catalog(db_session, "CNY", ["KRW", "EUR"])
    fx = FakeFxClient({
        "2026-11-01": [USD_CNY_ROW],
        "2026-10-31": SAMPLE_ROWS + [[Decimal("100"), "欧元", Decimal("780"), "人民币"]],
    })
    service = MonthlyExchangeRateService(db_session, ledger, fx_client=fx, timezone="Asia/Shanghai")
    result = service.generate_current_month(
        now=datetime(2026, 11, 1, 11, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    )
    assert result["status"] == "completed"
    assert result["source_date"] == "2026-11-01"
    assert result["written"] == ["USD"]
    assert result["missing"] == ["KRW", "EUR"]
    text = ledger.read_text(encoding="utf-8")
    assert "2026-11-01 price USD 6.7168 CNY" in text
    assert "price KRW" not in text
    assert "price EUR" not in text
    assert fx.calls == [date(2026, 11, 1)]


def test_should_catch_up_only_after_ten_on_first() -> None:
    tz = ZoneInfo("Asia/Shanghai")
    assert should_catch_up_monthly_fx(datetime(2026, 11, 1, 10, 0, 1, tzinfo=tz))
    assert not should_catch_up_monthly_fx(datetime(2026, 11, 1, 10, 0, 0, tzinfo=tz))
    assert not should_catch_up_monthly_fx(datetime(2026, 11, 1, 9, 59, 59, tzinfo=tz))
    assert not should_catch_up_monthly_fx(datetime(2026, 11, 2, 0, 0, 1, tzinfo=tz))


def test_scheduler_registers_catchup_only_inside_window() -> None:
    scheduler = RecurringScheduler()
    original = scheduler._scheduler
    from apscheduler.schedulers.background import BackgroundScheduler

    tz = ZoneInfo("Asia/Shanghai")
    try:
        scheduler._scheduler = BackgroundScheduler()
        scheduler.add_monthly_exchange_rate_job(
            timezone="Asia/Shanghai",
            now=datetime(2026, 11, 1, 10, 30, tzinfo=tz),
        )
        assert scheduler._scheduler.get_job("monthly_exchange_rate_job") is not None
        assert scheduler._scheduler.get_job("monthly_exchange_rate_job_catchup") is not None

        scheduler._scheduler = BackgroundScheduler()
        scheduler.add_monthly_exchange_rate_job(
            timezone="Asia/Shanghai",
            now=datetime(2026, 11, 2, 0, 1, tzinfo=tz),
        )
        assert scheduler._scheduler.get_job("monthly_exchange_rate_job") is not None
        assert scheduler._scheduler.get_job("monthly_exchange_rate_job_catchup") is None
    finally:
        scheduler._scheduler = original


def test_generate_current_month_api(db_session, tmp_path, monkeypatch) -> None:
    ledger = _bind_ledger(tmp_path, monkeypatch)
    _seed_catalog(db_session, "CNY", ["KRW"])
    class CurrentMonthFxClient:
        def fetch_first_quote_day(self, start_date, *, max_lookback_days=10):
            return start_date, SAMPLE_ROWS

    service = MonthlyExchangeRateService(
        db_session,
        ledger,
        fx_client=CurrentMonthFxClient(),
        timezone="Asia/Shanghai",
    )
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[exchange_rate_api.get_monthly_exchange_rate_service] = lambda: service
    try:
        response = TestClient(app).post("/api/exchange-rates/generate-current-month")
    finally:
        app.dependency_overrides.clear()
        BeancountServiceProvider.clear()
    assert response.status_code == 200, response.text
    body = response.json()
    first = datetime.now(ZoneInfo("Asia/Shanghai")).date().replace(day=1).isoformat()
    assert body["status"] == "completed"
    assert body["effective_date"] == first
    assert "USD" in body["written"]
    assert body["source_date"] == first
    assert "[[100" not in response.text
