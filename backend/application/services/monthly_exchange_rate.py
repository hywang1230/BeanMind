"""每月自动汇率：选币、换算、查重与一次提交。"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from beancount.core.data import Price
from sqlalchemy.orm import Session

from backend.config import settings
from backend.infrastructure.fx.safe_fx_client import DEFAULT_MAX_LOOKBACK_DAYS, SafeFxClient
from backend.infrastructure.persistence.beancount.beancount_provider import BeancountServiceProvider
from backend.infrastructure.persistence.beancount.ledger_write import (
    LedgerWriteConflict,
    LedgerWriteError,
    commit_ledger_files,
    has_pending_write,
    ledger_lock,
)
from backend.infrastructure.persistence.ledger_projection import LedgerProjectionService
from backend.services.currency_catalog import CurrencyCatalogService

logger = logging.getLogger(__name__)

PRICE_SCALE = Decimal("0.00000001")
STATUS_COMPLETED = "completed"
STATUS_UNAVAILABLE = "unavailable"

SAFE_CURRENCY_NAMES: dict[str, str] = {
    "美元": "USD",
    "欧元": "EUR",
    "日元": "JPY",
    "港元": "HKD",
    "英镑": "GBP",
    "澳元": "AUD",
    "新西兰元": "NZD",
    "新加坡元": "SGD",
    "瑞士法郎": "CHF",
    "加元": "CAD",
    "瑞典克朗": "SEK",
    "里拉": "TRY",
    "泰铢": "THB",
    "澳门元": "MOP",
    "林吉特": "MYR",
    "卢布": "RUB",
    "兰特": "ZAR",
    "韩元": "KRW",
    "迪拉姆": "AED",
    "里亚尔": "SAR",
    "福林": "HUF",
    "兹罗提": "PLN",
    "丹麦克朗": "DKK",
    "挪威克朗": "NOK",
    "比索": "MXN",
    "人民币": "CNY",
}


def format_price_rate(value: Decimal) -> str:
    """量化到 8 位四舍五入，用固定小数格式去掉末尾 0。"""
    quantized = value.quantize(PRICE_SCALE, rounding=ROUND_HALF_UP)
    text = format(quantized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _as_positive_decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, Decimal):
        number = value
    elif isinstance(value, int):
        number = Decimal(value)
    elif isinstance(value, str):
        try:
            number = Decimal(value)
        except InvalidOperation:
            return None
    else:
        return None
    if number <= 0:
        return None
    return number


def cny_rates_from_safe_rows(rows: Iterable[Any]) -> dict[str, Decimal]:
    """从外汇局行得到 1 外币等于多少人民币。跳过非法行。"""
    rates: dict[str, Decimal] = {}
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) != 4:
            continue
        base_qty, base_name, quote_qty, quote_name = row
        if not isinstance(base_name, str) or not isinstance(quote_name, str):
            continue
        base_code = SAFE_CURRENCY_NAMES.get(base_name)
        quote_code = SAFE_CURRENCY_NAMES.get(quote_name)
        if base_code is None or quote_code is None:
            continue
        base_amount = _as_positive_decimal(base_qty)
        quote_amount = _as_positive_decimal(quote_qty)
        if base_amount is None or quote_amount is None:
            continue
        if quote_code == "CNY" and base_code != "CNY":
            rates[base_code] = quote_amount / base_amount
        elif base_code == "CNY" and quote_code != "CNY":
            rates[quote_code] = base_amount / quote_amount
    return rates


def operating_rates_from_cny(
    cny_rates: dict[str, Decimal],
    *,
    operating: str,
    currencies: Iterable[str],
) -> dict[str, Decimal] | None:
    """把人民币牌价换成 1 外币对主币种。主币种无法换算时返回 None。"""
    operating = operating.upper()
    rates = dict(cny_rates)
    rates.setdefault("CNY", Decimal("1"))
    if operating == "CNY":
        operating_cny = Decimal("1")
    else:
        operating_cny = rates.get(operating)
        if operating_cny is None or operating_cny <= 0:
            return None
    converted: dict[str, Decimal] = {}
    for code in currencies:
        currency = code.upper()
        if currency == operating:
            continue
        foreign_cny = rates.get(currency)
        if foreign_cny is None or foreign_cny <= 0:
            continue
        converted[currency] = foreign_cny / operating_cny
    return converted


def existing_pair_currencies(
    entries: Iterable[Any],
    *,
    effective_date: date,
    operating: str,
    currencies: Iterable[str],
) -> set[str]:
    """当月 1 日已有该币种与主币种任一方向 price 的币种。"""
    wanted = {code.upper() for code in currencies}
    operating = operating.upper()
    found: set[str] = set()
    for entry in entries:
        if not isinstance(entry, Price) or entry.date != effective_date:
            continue
        base = str(entry.currency or "").upper()
        quote = str(getattr(entry.amount, "currency", "") or "").upper()
        if base == operating and quote in wanted:
            found.add(quote)
        elif quote == operating and base in wanted:
            found.add(base)
    return found


def should_catch_up_monthly_fx(now: datetime) -> bool:
    """调度时区 1 日 10:00 之后、次日 0:00 之前才补跑。"""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    if now.day != 1:
        return False
    return now > now.replace(hour=10, minute=0, second=0, microsecond=0)


def _empty_result(
    *,
    effective_date: date,
    source_date: date | None,
    written: list[str],
    skipped: list[str],
    missing: list[str],
    status: str,
) -> dict[str, Any]:
    return {
        "effective_date": effective_date.isoformat(),
        "source_date": source_date.isoformat() if source_date else None,
        "written": written,
        "skipped": skipped,
        "missing": missing,
        "status": status,
    }


class MonthlyExchangeRateService:
    """调度与手工按钮共用的当月汇率生成。"""

    def __init__(
        self,
        db: Session,
        ledger_path: Path | str | None = None,
        *,
        fx_client: SafeFxClient | None = None,
        timezone: str | None = None,
    ) -> None:
        self.db = db
        self.ledger_path = Path(ledger_path or settings.LEDGER_FILE)
        self.fx_client = fx_client or SafeFxClient()
        self.timezone = timezone or settings.SCHEDULER_TIMEZONE

    def generate_current_month(self, *, now: datetime | None = None) -> dict[str, Any]:
        current = now or datetime.now(ZoneInfo(self.timezone))
        if current.tzinfo is None:
            current = current.replace(tzinfo=ZoneInfo(self.timezone))
        else:
            current = current.astimezone(ZoneInfo(self.timezone))
        effective_date = date(current.year, current.month, 1)

        quotes = self.fx_client.fetch_first_quote_day(
            effective_date,
            max_lookback_days=DEFAULT_MAX_LOOKBACK_DAYS,
        )
        if quotes is None:
            enabled = self._enabled_foreign_codes()
            logger.info(
                "monthly_fx status=%s effective_date=%s source_date= missing=%d",
                STATUS_UNAVAILABLE,
                effective_date.isoformat(),
                len(enabled),
            )
            return _empty_result(
                effective_date=effective_date,
                source_date=None,
                written=[],
                skipped=[],
                missing=enabled,
                status=STATUS_UNAVAILABLE,
            )

        source_date, rows = quotes
        cny_rates = cny_rates_from_safe_rows(rows)
        return self._commit_quotes(
            effective_date=effective_date,
            source_date=source_date,
            cny_rates=cny_rates,
        )

    def _enabled_foreign_codes(self, operating: str | None = None) -> list[str]:
        beancount = BeancountServiceProvider.get_service(self.ledger_path)
        operating_code = (operating or beancount.get_operating_currency() or "CNY").upper()
        catalog = CurrencyCatalogService(
            self.db,
            operating_currency=operating_code,
            beancount_service=beancount,
        )
        return [
            item["code"].upper()
            for item in catalog.list_currencies(enabled_only=True)
            if item["code"].upper() != operating_code
        ]

    def _commit_quotes(
        self,
        *,
        effective_date: date,
        source_date: date,
        cny_rates: dict[str, Decimal],
    ) -> dict[str, Any]:
        ledger_path = self.ledger_path.resolve()
        with ledger_lock(ledger_path):
            if has_pending_write(ledger_path):
                raise LedgerWriteConflict("Pending ledger recovery blocks new writes")
            beancount = BeancountServiceProvider.get_service(ledger_path)
            operating = (beancount.get_operating_currency() or "CNY").upper()
            catalog = CurrencyCatalogService(
                self.db,
                operating_currency=operating,
                beancount_service=beancount,
            )
            enabled = [
                item["code"].upper()
                for item in catalog.list_currencies(enabled_only=True)
                if item["code"].upper() != operating
            ]
            converted = operating_rates_from_cny(
                cny_rates,
                operating=operating,
                currencies=enabled,
            )
            if converted is None:
                logger.info(
                    "monthly_fx status=%s effective_date=%s source_date=%s reason=operating_cny_missing",
                    STATUS_UNAVAILABLE,
                    effective_date.isoformat(),
                    source_date.isoformat(),
                )
                return _empty_result(
                    effective_date=effective_date,
                    source_date=source_date,
                    written=[],
                    skipped=[],
                    missing=enabled,
                    status=STATUS_UNAVAILABLE,
                )

            skipped = sorted(
                existing_pair_currencies(
                    beancount.entries,
                    effective_date=effective_date,
                    operating=operating,
                    currencies=enabled,
                )
            )
            skipped_set = set(skipped)
            written: list[str] = []
            missing: list[str] = []
            lines: list[str] = []
            for code in enabled:
                if code in skipped_set:
                    continue
                rate = converted.get(code)
                if rate is None or rate <= 0:
                    missing.append(code)
                    continue
                rate_text = format_price_rate(rate)
                if Decimal(rate_text) <= 0:
                    missing.append(code)
                    continue
                written.append(code)
                lines.append(
                    f"{effective_date.isoformat()} price {code} {rate_text} {operating}\n"
                )

            result = _empty_result(
                effective_date=effective_date,
                source_date=source_date,
                written=written,
                skipped=skipped,
                missing=missing,
                status=STATUS_COMPLETED,
            )
            if not lines:
                logger.info(
                    "monthly_fx status=%s effective_date=%s source_date=%s written=%d skipped=%d missing=%d",
                    STATUS_COMPLETED,
                    effective_date.isoformat(),
                    source_date.isoformat(),
                    len(written),
                    len(skipped),
                    len(missing),
                )
                return result

            content = ledger_path.read_text(encoding="utf-8")
            if content and not content.endswith("\n"):
                content += "\n"
            if content and not content.endswith("\n\n"):
                content += "\n"
            content += "".join(lines)

            projection = LedgerProjectionService(self.db, ledger_path)
            validated = None
            committed = False

            def before_commit():
                projection.mark_dirty_files([ledger_path])

            def after_commit(parsed_files):
                nonlocal validated
                validated = parsed_files
                projection.refresh_files(
                    [ledger_path],
                    parsed_files=parsed_files,
                    candidate_snapshot=parsed_files.candidate_snapshot,
                )

            try:
                committed = commit_ledger_files(
                    ledger_path,
                    {ledger_path: content},
                    before_commit=before_commit,
                    after_commit=after_commit,
                    validation_context=(beancount.entries, beancount.options),
                )
            finally:
                if (
                    committed
                    and validated is not None
                    and validated.candidate_snapshot is not None
                    and validated.projection_receipt is not None
                ):
                    try:
                        published = BeancountServiceProvider.publish(
                            validated.candidate_snapshot,
                            validated.projection_receipt,
                        )
                    except Exception:
                        published = False
                        logger.info("ledger_provider status=fallback reason=publish_exception")
                    if not published:
                        BeancountServiceProvider.invalidate()
                else:
                    BeancountServiceProvider.invalidate()

            if not committed:
                raise LedgerWriteError("账本已写入，投影待恢复")

            logger.info(
                "monthly_fx status=%s effective_date=%s source_date=%s written=%d skipped=%d missing=%d",
                STATUS_COMPLETED,
                effective_date.isoformat(),
                source_date.isoformat(),
                len(written),
                len(skipped),
                len(missing),
            )
            return result
