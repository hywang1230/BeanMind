"""经营币种折算：首页与报表趋势共用。"""

from __future__ import annotations

from decimal import Decimal


def convert_currency_totals(
    values: dict[str, Decimal],
    *,
    operating_currency: str,
    rates: dict[str, Decimal | str | int | float],
) -> tuple[Decimal, list[str]]:
    """将逐币种金额折算到经营币种；缺汇率不静默 1:1。"""
    total = Decimal("0")
    missing: list[str] = []
    for currency, amount in values.items():
        if currency == operating_currency:
            total += amount
            continue
        rate = rates.get(currency)
        if rate is None:
            missing.append(currency)
            continue
        total += amount * Decimal(str(rate))
    return total, sorted(missing)
