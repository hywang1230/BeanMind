"""统一币种目录服务（SQLite 应用配置）。"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.infrastructure.persistence.db.models import (
    Currency,
    LedgerPosting,
    MonthlyBudget,
    RecurringRule,
)

CURRENCY_CODE_RE = re.compile(r"^[A-Z]{3}$")

# 仅预置常用两项；其余按需在「币种管理」中新增
DEFAULT_SEED_CODES: tuple[str, ...] = ("CNY", "USD")

# 预置/已知码显示名；未知码用 code 本身
SEED_CURRENCY_META: dict[str, tuple[str, str | None]] = {
    "CNY": ("人民币", "¥"),
    "USD": ("美元", "$"),
    "EUR": ("欧元", "€"),
    "GBP": ("英镑", "£"),
    "JPY": ("日元", "¥"),
    "HKD": ("港币", "HK$"),
    "TWD": ("新台币", "NT$"),
    "SGD": ("新加坡元", "S$"),
    "AUD": ("澳元", "A$"),
    "CAD": ("加元", "C$"),
    "CHF": ("瑞士法郎", "CHF"),
    "KRW": ("韩元", "₩"),
}


class CurrencyCatalogError(ValueError):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details


class CurrencyCatalogService:
    """具体服务：列表 / 新增 / 更新 / 删除 / 使用中校验 / require_enabled。"""

    def __init__(
        self,
        db: Session,
        operating_currency: str = "CNY",
        beancount_service: Any | None = None,
    ) -> None:
        self.db = db
        self.operating_currency = self.normalize_code(operating_currency, field="operating_currency")
        self.beancount_service = beancount_service

    @staticmethod
    def normalize_code(code: str, *, field: str = "code") -> str:
        value = (code or "").strip().upper()
        if not value:
            raise CurrencyCatalogError("INVALID_CURRENCY_CODE", "币种代码不能为空", {field: code})
        if not CURRENCY_CODE_RE.match(value):
            raise CurrencyCatalogError(
                "INVALID_CURRENCY_CODE",
                f"无效的币种代码: {code}（必须为 3 个大写字母）",
                {field: code},
            )
        return value

    def ensure_seeded(self) -> int:
        """幂等写入默认币种（人民币/美元），并确保经营币种存在且启用。返回本次新增条数。

        注意：项目 Session 使用 autoflush=False，pending 对象不会被后续 query 看到，
        因此新插入行必须立刻登记进 existing，禁止再走“查不到就再 insert”路径。
        """
        created = 0
        reenabled = False
        seed_codes = list(DEFAULT_SEED_CODES)
        if self.operating_currency not in seed_codes:
            seed_codes.append(self.operating_currency)

        existing = {
            row.code: row
            for row in self.db.query(Currency).filter(Currency.code.in_(seed_codes)).all()
        }

        now = datetime.now()
        for index, code in enumerate(seed_codes):
            if code in existing:
                continue
            name, symbol = SEED_CURRENCY_META.get(code, (code, None))
            row = Currency(
                code=code,
                name=name,
                symbol=symbol,
                enabled=True,
                sort_order=index,
                created_at=now,
                updated_at=now,
            )
            self.db.add(row)
            existing[code] = row
            created += 1

        # 经营币种必须存在且启用（优先复用上面刚加入的 pending 行）
        op = existing.get(self.operating_currency)
        if op is None:
            name, symbol = SEED_CURRENCY_META.get(
                self.operating_currency, (self.operating_currency, None)
            )
            op = Currency(
                code=self.operating_currency,
                name=name,
                symbol=symbol,
                enabled=True,
                sort_order=0,
                created_at=now,
                updated_at=now,
            )
            self.db.add(op)
            existing[self.operating_currency] = op
            created += 1
        elif not op.enabled:
            op.enabled = True
            op.updated_at = datetime.now()
            reenabled = True

        if created or reenabled:
            self.db.commit()
        return created

    def list_currencies(self, *, enabled_only: bool = False) -> list[dict]:
        self.ensure_seeded()
        query = self.db.query(Currency)
        if enabled_only:
            query = query.filter(Currency.enabled.is_(True))
        rows = query.order_by(Currency.sort_order.asc(), Currency.code.asc()).all()
        used = self.collect_used_currencies()
        items: list[dict] = []
        for row in rows:
            items.append(self._to_item(row, used=used))
        return items

    def get(self, code: str) -> Currency | None:
        try:
            normalized = self.normalize_code(code)
        except CurrencyCatalogError:
            return None
        return self.db.query(Currency).filter(Currency.code == normalized).first()

    def create(
        self,
        code: str,
        name: str,
        symbol: Optional[str] = None,
        *,
        enabled: bool = True,
        sort_order: Optional[int] = None,
    ) -> dict:
        normalized = self.normalize_code(code)
        display_name = (name or "").strip()
        if not display_name:
            raise CurrencyCatalogError("INVALID_CURRENCY_NAME", "币种名称不能为空")

        if self.db.query(Currency).filter(Currency.code == normalized).first() is not None:
            raise CurrencyCatalogError(
                "CURRENCY_ALREADY_EXISTS",
                f"币种 {normalized} 已存在",
                {"code": normalized},
            )

        if sort_order is None:
            max_order = self.db.query(Currency).count()
            sort_order = max_order

        row = Currency(
            code=normalized,
            name=display_name,
            symbol=(symbol or None),
            enabled=bool(enabled),
            sort_order=int(sort_order),
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self._to_item(row)

    def update(
        self,
        code: str,
        *,
        name: Optional[str] = None,
        symbol: Optional[str] = None,
        enabled: Optional[bool] = None,
        sort_order: Optional[int] = None,
    ) -> dict:
        normalized = self.normalize_code(code)
        row = self.db.query(Currency).filter(Currency.code == normalized).first()
        if row is None:
            raise CurrencyCatalogError(
                "CURRENCY_NOT_FOUND",
                f"币种 {normalized} 不存在",
                {"code": normalized},
            )

        if enabled is False:
            if normalized == self.operating_currency:
                raise CurrencyCatalogError(
                    "CANNOT_DISABLE_OPERATING_CURRENCY",
                    f"不能停用经营币种 {self.operating_currency}",
                    {"code": normalized, "operating_currency": self.operating_currency},
                )
            self.assert_not_in_use(normalized, action="停用")

        if name is not None:
            display_name = name.strip()
            if not display_name:
                raise CurrencyCatalogError("INVALID_CURRENCY_NAME", "币种名称不能为空")
            row.name = display_name
        if symbol is not None:
            row.symbol = symbol or None
        if enabled is not None:
            row.enabled = bool(enabled)
        if sort_order is not None:
            row.sort_order = int(sort_order)
        row.updated_at = datetime.now()
        self.db.commit()
        self.db.refresh(row)
        return self._to_item(row)

    def delete(self, code: str) -> None:
        """删除未使用的币种。"""
        normalized = self.normalize_code(code)
        row = self.db.query(Currency).filter(Currency.code == normalized).first()
        if row is None:
            raise CurrencyCatalogError(
                "CURRENCY_NOT_FOUND",
                f"币种 {normalized} 不存在",
                {"code": normalized},
            )
        if normalized == self.operating_currency:
            raise CurrencyCatalogError(
                "CANNOT_DELETE_OPERATING_CURRENCY",
                f"不能删除经营币种 {self.operating_currency}",
                {"code": normalized, "operating_currency": self.operating_currency},
            )
        self.assert_not_in_use(normalized, action="删除")
        self.db.delete(row)
        self.db.commit()

    def _to_item(self, row: Currency, *, used: set[str] | None = None) -> dict:
        """统一附加 in_use / is_operating 展示字段。"""
        if used is None:
            used = self.collect_used_currencies()
        item = row.to_dict()
        item["in_use"] = row.code in used
        item["is_operating"] = row.code == self.operating_currency
        return item

    def collect_used_currencies(self) -> set[str]:

        """汇总已被账户/交易/预算/周期/汇率等引用的币种代码。"""
        used: set[str] = {self.operating_currency}

        for value in self.db.query(LedgerPosting.currency).distinct():
            if value[0]:
                used.add(str(value[0]).strip().upper())
        for value in self.db.query(LedgerPosting.cost_currency).filter(
            LedgerPosting.cost_currency.isnot(None)
        ).distinct():
            if value[0]:
                used.add(str(value[0]).strip().upper())
        for value in self.db.query(LedgerPosting.price_currency).filter(
            LedgerPosting.price_currency.isnot(None)
        ).distinct():
            if value[0]:
                used.add(str(value[0]).strip().upper())

        for value in self.db.query(MonthlyBudget.currency).distinct():
            if value[0]:
                used.add(str(value[0]).strip().upper())

        for (template,) in self.db.query(RecurringRule.transaction_template).all():
            used.update(self._currencies_from_template(template))

        if self.beancount_service is not None:
            try:
                for account in self.beancount_service.get_accounts() or []:
                    for currency in account.get("currencies") or []:
                        if currency:
                            used.add(str(currency).strip().upper())
            except Exception:
                pass
            try:
                from beancount.core.data import Price

                for entry in getattr(self.beancount_service, "entries", None) or []:
                    if isinstance(entry, Price):
                        if entry.currency:
                            used.add(str(entry.currency).strip().upper())
                        amount = getattr(entry, "amount", None)
                        if amount is not None and getattr(amount, "currency", None):
                            used.add(str(amount.currency).strip().upper())
            except Exception:
                pass

        return {code for code in used if code}

    @staticmethod
    def _currencies_from_template(template: str | None) -> set[str]:
        if not template:
            return set()
        try:
            data = json.loads(template)
        except (TypeError, ValueError, json.JSONDecodeError):
            return set()
        found_set: set[str] = set()
        postings = []
        if isinstance(data, dict):
            postings = data.get("postings") or []
            if data.get("currency"):
                found_set.add(str(data["currency"]).strip().upper())
        if isinstance(postings, list):
            for posting in postings:
                if not isinstance(posting, dict):
                    continue
                for key in ("currency", "cost_currency", "price_currency"):
                    value = posting.get(key)
                    if value:
                        found_set.add(str(value).strip().upper())
        return found_set

    def assert_not_in_use(self, code: str, *, action: str) -> None:
        normalized = self.normalize_code(code)
        if normalized not in self.collect_used_currencies():
            return
        raise CurrencyCatalogError(
            "CURRENCY_IN_USE",
            f"币种 {normalized} 已在系统中使用，不能{action}",
            {"code": normalized, "action": action},
        )

    def require_enabled(self, code: str) -> str:
        """写路径校验：必须存在且启用。返回规范化 code。"""
        normalized = self.normalize_code(code)
        self.ensure_seeded()
        row = self.db.query(Currency).filter(Currency.code == normalized).first()
        if row is None:
            raise CurrencyCatalogError(
                "UNKNOWN_CURRENCY",
                f"未知币种: {normalized}",
                {"code": normalized},
            )
        if not row.enabled:
            raise CurrencyCatalogError(
                "CURRENCY_DISABLED",
                f"币种已停用: {normalized}",
                {"code": normalized},
            )
        return normalized

    def require_in_catalog(self, code: str) -> str:
        """至少存在于目录（汇率等可用；仍要求存在，不要求启用也可用本方法）。"""
        normalized = self.normalize_code(code)
        self.ensure_seeded()
        row = self.db.query(Currency).filter(Currency.code == normalized).first()
        if row is None:
            raise CurrencyCatalogError(
                "UNKNOWN_CURRENCY",
                f"未知币种: {normalized}",
                {"code": normalized},
            )
        return normalized
