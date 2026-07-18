"""Beancount 到 SQLite 的可重建查询投影。"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import uuid
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Optional

from beancount import loader
from beancount.core.data import Transaction as BeancountTransaction
from beancount.parser import parser
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, selectinload

from backend.infrastructure.persistence.db.models import (
    LedgerIndexFile,
    LedgerPosting,
    LedgerTag,
    LedgerTransaction,
)

logger = logging.getLogger(__name__)

PROJECTION_READY = "READY"
PROJECTION_DIRTY = "DIRTY"


class LedgerProjectionDirtyError(RuntimeError):
    """查询投影不可安全读取。"""

    code = "LEDGER_PROJECTION_DIRTY"


class InvalidTransactionCursorError(ValueError):
    """交易游标非法。"""

    code = "INVALID_TRANSACTION_CURSOR"


def _decimal_text(value: Optional[Decimal]) -> Optional[str]:
    if value is None:
        return None
    return format(value, "f")


def _posting_weight(posting: LedgerPosting) -> tuple[Decimal, str]:
    """按 Beancount convert.get_weight 规则计算投影分录权重。"""
    units = Decimal(posting.amount_text)
    if posting.cost_text is not None and posting.cost_currency:
        return units * Decimal(posting.cost_text), posting.cost_currency
    if posting.price_text is not None and posting.price_currency:
        return units * Decimal(posting.price_text), posting.price_currency
    return units, posting.currency


def _display_amounts(transaction_type: str, postings: Iterable[LedgerPosting]) -> list[dict]:
    """返回流水列表逐币种金额；符号表示相对用户账户的实际方向。"""
    posting_list = list(postings)
    direction = Decimal("1")
    if transaction_type == "expense":
        selected = [posting for posting in posting_list if posting.account.startswith("Expenses:")]
        direction = Decimal("-1")
    elif transaction_type == "income":
        selected = [posting for posting in posting_list if posting.account.startswith("Income:")]
        direction = Decimal("-1")
    else:
        weighted = [(posting, *_posting_weight(posting)) for posting in posting_list]
        selected_weighted = [item for item in weighted if item[1] < 0]
        if not selected_weighted:
            selected_weighted = [item for item in weighted if item[1] > 0] or weighted
        totals: dict[str, Decimal] = {}
        for _, amount, currency in selected_weighted:
            totals[currency] = totals.get(currency, Decimal("0")) + amount
        return [
            {"currency": currency, "amount": _decimal_text(total if total else Decimal("0"))}
            for currency, total in sorted(totals.items())
        ]

    totals: dict[str, Decimal] = {}
    for posting in selected:
        amount, currency = _posting_weight(posting)
        totals[currency] = totals.get(currency, Decimal("0")) + amount
    return [
        {
            "currency": currency,
            "amount": _decimal_text(
                total * direction if total * direction else Decimal("0")
            ),
        }
        for currency, total in sorted(totals.items())
    ]


def _entry_payload(entry: BeancountTransaction) -> dict:
    postings = []
    for posting in entry.postings:
        cost = posting.cost
        price = posting.price
        postings.append(
            {
                "account": posting.account,
                "amount": _decimal_text(posting.units.number),
                "currency": posting.units.currency,
                "cost": _decimal_text(cost.number) if cost else None,
                "cost_currency": cost.currency if cost else None,
                "price": _decimal_text(price.number) if price else None,
                "price_currency": price.currency if price else None,
                "flag": posting.flag,
            }
        )
    return {
        "date": entry.date.isoformat(),
        "flag": entry.flag,
        "payee": entry.payee,
        "narration": entry.narration,
        "tags": sorted(entry.tags or []),
        "links": sorted(entry.links or []),
        "postings": postings,
    }


def _content_hash(entry: BeancountTransaction) -> str:
    payload = json.dumps(
        _entry_payload(entry), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _transaction_type(entry: BeancountTransaction) -> str:
    account_types = {posting.account.split(":", 1)[0] for posting in entry.postings}
    if "Expenses" in account_types:
        return "expense"
    if "Income" in account_types:
        return "income"
    if account_types and account_types <= {"Assets", "Liabilities"}:
        return "transfer"
    if "Equity" in account_types:
        return "opening"
    return "other"


def _source_path(entry: BeancountTransaction) -> Path:
    filename = entry.meta.get("filename") if entry.meta else None
    if not filename:
        raise ValueError("交易缺少 filename 元数据，无法建立投影")
    return Path(filename).resolve()


def _transaction_id(entry: BeancountTransaction, content_hash: str) -> str:
    explicit_id = entry.meta.get("id") if entry.meta else None
    if explicit_id:
        return str(explicit_id)
    source = f"{_source_path(entry)}:{entry.meta.get('lineno', 0)}:{content_hash}"
    return uuid.uuid5(uuid.NAMESPACE_URL, source).hex


def _fingerprint(path: Path) -> tuple[int, int, str]:
    stat = path.stat()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return stat.st_mtime_ns, stat.st_size, digest


def encode_transaction_cursor(
    txn_date: date, source_lineno: int, transaction_id: str
) -> str:
    """编码列表游标：date + source_lineno + id。"""
    payload = json.dumps(
        {
            "v": 2,
            "date": txn_date.isoformat(),
            "lineno": int(source_lineno),
            "id": transaction_id,
        },
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_transaction_cursor(cursor: str) -> tuple[date, int, str]:
    try:
        padding = "=" * (-len(cursor) % 4)
        raw = base64.b64decode(cursor + padding, altchars=b"-_", validate=True)
        payload = json.loads(raw.decode("utf-8"))
        if set(payload) != {"v", "date", "lineno", "id"} or payload["v"] != 2:
            raise ValueError("unsupported cursor")
        if not isinstance(payload["id"], str) or not payload["id"]:
            raise ValueError("missing id")
        lineno = payload["lineno"]
        if not isinstance(lineno, int) or isinstance(lineno, bool) or lineno < 0:
            raise ValueError("invalid lineno")
        return date.fromisoformat(payload["date"]), lineno, payload["id"]
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise InvalidTransactionCursorError("交易游标无效") from exc


class LedgerProjectionService:
    """构建、刷新并检查 SQLite 账本查询投影。"""

    def __init__(self, db: Session, ledger_path: Path | str):
        self.db = db
        self.ledger_path = Path(ledger_path).resolve()

    def _model_from_entry(
        self, entry: BeancountTransaction, used_ids: set[str] | None = None
    ) -> LedgerTransaction:
        content_hash = _content_hash(entry)
        source_path = _source_path(entry)
        transaction_id = _transaction_id(entry, content_hash)
        if used_ids is not None and transaction_id in used_ids:
            # 兼容历史账本中重复的显式 ID；新写入仍使用并持久化 UUID。
            transaction_id = uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"duplicate:{source_path}:{entry.meta.get('lineno', 0)}:"
                f"{content_hash}:{transaction_id}",
            ).hex
            logger.warning(
                "检测到重复交易 ID，投影使用源位置派生 ID: %s:%s",
                source_path,
                entry.meta.get("lineno", 0),
            )
        if used_ids is not None:
            used_ids.add(transaction_id)
        transaction = LedgerTransaction(
            id=transaction_id,
            date=entry.date,
            flag=entry.flag,
            payee=entry.payee or None,
            narration=entry.narration or "",
            transaction_type=_transaction_type(entry),
            source_file=str(source_path),
            source_lineno=int(entry.meta.get("lineno", 0)),
            content_hash=content_hash,
            links_json=json.dumps(sorted(entry.links or []), ensure_ascii=False),
        )
        for sequence, posting in enumerate(entry.postings):
            cost = posting.cost
            price = posting.price
            transaction.postings.append(
                LedgerPosting(
                    sequence=sequence,
                    account=posting.account,
                    amount_text=_decimal_text(posting.units.number) or "0",
                    currency=posting.units.currency,
                    cost_text=_decimal_text(cost.number) if cost else None,
                    cost_currency=cost.currency if cost else None,
                    price_text=_decimal_text(price.number) if price else None,
                    price_currency=price.currency if price else None,
                    flag=posting.flag,
                )
            )
        for tag in sorted(entry.tags or []):
            transaction.tags.append(LedgerTag(tag=tag))
        return transaction

    def _record_file(self, path: Path, status: str = PROJECTION_READY, error: str | None = None):
        path = path.resolve()
        mtime_ns, size, content_hash = _fingerprint(path)
        record = self.db.get(LedgerIndexFile, str(path))
        if record is None:
            record = LedgerIndexFile(path=str(path))
            self.db.add(record)
        record.mtime_ns = mtime_ns
        record.size = size
        record.content_hash = content_hash
        record.indexed_at = datetime.now()
        record.status = status
        record.last_error = error

    def mark_dirty(self, path: Path | str, error: Exception | str) -> None:
        """记录投影错误；该操作不改变 Beancount 真源。"""
        self.db.rollback()
        target = Path(path).resolve()
        try:
            if target.exists():
                self._record_file(target, PROJECTION_DIRTY, str(error))
            else:
                record = self.db.get(LedgerIndexFile, str(target))
                if record is None:
                    record = LedgerIndexFile(
                        path=str(target),
                        mtime_ns=0,
                        size=0,
                        content_hash="",
                        indexed_at=datetime.now(),
                        status=PROJECTION_DIRTY,
                    )
                    self.db.add(record)
                record.status = PROJECTION_DIRTY
                record.last_error = str(error)
                record.indexed_at = datetime.now()
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("无法记录账本投影 DIRTY 状态")

    def _delete_transactions_for_files(self, paths: Iterable[Path | str]) -> None:
        normalized = [str(Path(path).resolve()) for path in paths]
        if not normalized:
            return
        ids = [
            row[0]
            for row in self.db.query(LedgerTransaction.id)
            .filter(LedgerTransaction.source_file.in_(normalized))
            .all()
        ]
        if ids:
            self.db.query(LedgerPosting).filter(LedgerPosting.transaction_id.in_(ids)).delete(
                synchronize_session=False
            )
            self.db.query(LedgerTag).filter(LedgerTag.transaction_id.in_(ids)).delete(
                synchronize_session=False
            )
            self.db.query(LedgerTransaction).filter(LedgerTransaction.id.in_(ids)).delete(
                synchronize_session=False
            )

    def full_rebuild(self) -> dict:
        """从完整 Beancount 账本原子重建投影。"""
        try:
            entries, errors, options = loader.load_file(str(self.ledger_path))
            if errors:
                raise ValueError("; ".join(str(error) for error in errors[:10]))
            used_ids: set[str] = set()
            transactions = [
                self._model_from_entry(entry, used_ids)
                for entry in entries
                if isinstance(entry, BeancountTransaction)
            ]
            files = {self.ledger_path}
            files.update(
                Path(path).resolve() for path in options.get("include", []) if Path(path).exists()
            )
            files.update(
                _source_path(entry) for entry in entries if isinstance(entry, BeancountTransaction)
            )

            self.db.query(LedgerPosting).delete(synchronize_session=False)
            self.db.query(LedgerTag).delete(synchronize_session=False)
            self.db.query(LedgerTransaction).delete(synchronize_session=False)
            self.db.query(LedgerIndexFile).delete(synchronize_session="fetch")
            self.db.add_all(transactions)
            for path in sorted(files):
                self._record_file(path)
            self.db.commit()
            return {
                "status": PROJECTION_READY,
                "transactions": len(transactions),
                "files": len(files),
            }
        except Exception as exc:
            self.mark_dirty(self.ledger_path, exc)
            raise

    def rebuild_all(self) -> dict:
        """OpenSpec 约定名称；保持具体服务而不增加抽象层。"""
        return self.full_rebuild()

    def refresh_file(self, path: Path | str) -> dict:
        """刷新一个可独立解析的交易文件；主文件变化时执行全量重建。"""
        target = Path(path).resolve()
        if target == self.ledger_path:
            return self.full_rebuild()
        if target.suffix != ".beancount" or not target.exists():
            error = ValueError(f"无法安全增量刷新文件: {target}")
            self.mark_dirty(target, error)
            raise error
        try:
            entries, errors, _ = parser.parse_file(str(target))
            if errors:
                raise ValueError("; ".join(str(error) for error in errors[:10]))
            if any(not isinstance(entry, BeancountTransaction) for entry in entries):
                logger.info("文件包含全局或非交易指令，回退全量重建: %s", target)
                return self.full_rebuild()
            directives = ("include ", "plugin ", "option ")
            if any(
                line.strip().lower().startswith(directives)
                for line in target.read_text(encoding="utf-8").splitlines()
            ):
                logger.info("文件包含全局配置，回退全量重建: %s", target)
                return self.full_rebuild()
            if any(
                _source_path(entry) != target
                for entry in entries
                if isinstance(entry, BeancountTransaction)
            ):
                raise ValueError(f"文件无法独立投影: {target}")
            self._delete_transactions_for_files([target])
            used_ids = {row[0] for row in self.db.query(LedgerTransaction.id).all()}
            transactions = [
                self._model_from_entry(entry, used_ids)
                for entry in entries
                if isinstance(entry, BeancountTransaction)
            ]
            self.db.add_all(transactions)
            self._record_file(target)
            self.db.commit()
            return {
                "status": PROJECTION_READY,
                "transactions": len(transactions),
                "file": str(target),
            }
        except Exception as exc:
            self.mark_dirty(target, exc)
            raise

    def ensure_current(self) -> dict:
        """启动时复用未变化投影，只刷新安全变化，否则全量重建。"""
        records = self.db.query(LedgerIndexFile).all()
        if not records or any(record.status != PROJECTION_READY for record in records):
            return self.full_rebuild()

        changed: list[Path] = []
        removed: list[Path] = []
        for record in records:
            path = Path(record.path)
            if not path.exists():
                removed.append(path)
                continue
            mtime_ns, size, content_hash = _fingerprint(path)
            if (mtime_ns, size, content_hash) != (
                record.mtime_ns,
                record.size,
                record.content_hash,
            ):
                changed.append(path)

        if not changed and not removed:
            return self.status()
        if self.ledger_path in changed or self.ledger_path in removed:
            return self.full_rebuild()

        try:
            for path in removed:
                self._delete_transactions_for_files([path])
                self.db.query(LedgerIndexFile).filter(LedgerIndexFile.path == str(path)).delete(
                    synchronize_session=False
                )
            self.db.commit()
            for path in changed:
                self.refresh_file(path)
            return self.status()
        except Exception:
            raise

    def status(self) -> dict:
        records = self.db.query(LedgerIndexFile).order_by(LedgerIndexFile.path).all()
        ready = bool(records) and all(record.status == PROJECTION_READY for record in records)
        return {
            "status": PROJECTION_READY if ready else PROJECTION_DIRTY,
            "transactions": self.db.query(LedgerTransaction).count(),
            "files": len(records),
            "errors": [
                {"file": record.path, "error": record.last_error}
                for record in records
                if record.status != PROJECTION_READY
            ],
        }

    @staticmethod
    def _summary_entries(entries: Iterable[BeancountTransaction]) -> dict:
        transaction_count = 0
        posting_count = 0
        dates: list[date] = []
        amounts: dict[str, Decimal] = {}
        for entry in entries:
            transaction_count += 1
            dates.append(entry.date)
            for posting in entry.postings:
                posting_count += 1
                currency = posting.units.currency
                amounts[currency] = amounts.get(currency, Decimal("0")) + posting.units.number
        return {
            "transactions": transaction_count,
            "postings": posting_count,
            "min_date": min(dates).isoformat() if dates else None,
            "max_date": max(dates).isoformat() if dates else None,
            "amounts": {key: _decimal_text(value) for key, value in sorted(amounts.items())},
        }

    def _summary_projection(self) -> dict:
        rows = self.db.query(LedgerTransaction).all()
        dates = [row.date for row in rows]
        amounts: dict[str, Decimal] = {}
        for amount_text, currency in self.db.query(
            LedgerPosting.amount_text, LedgerPosting.currency
        ).all():
            amounts[currency] = amounts.get(currency, Decimal("0")) + Decimal(amount_text)
        return {
            "transactions": len(rows),
            "postings": self.db.query(LedgerPosting).count(),
            "min_date": min(dates).isoformat() if dates else None,
            "max_date": max(dates).isoformat() if dates else None,
            "amounts": {key: _decimal_text(value) for key, value in sorted(amounts.items())},
        }

    def check_consistency(self) -> dict:
        """只读解析真源并核对投影的关键摘要。"""
        entries, errors, _ = loader.load_file(str(self.ledger_path))
        if errors:
            error = ValueError("; ".join(str(item) for item in errors[:10]))
            self.mark_dirty(self.ledger_path, error)
            raise error
        expected = self._summary_entries(
            entry for entry in entries if isinstance(entry, BeancountTransaction)
        )
        actual = self._summary_projection()
        differences = {
            field: {"expected": expected[field], "actual": actual[field]}
            for field in expected
            if expected[field] != actual[field]
        }
        if differences:
            error = ValueError(
                "账本投影核对失败: "
                + "; ".join(
                    f"{field} expected={values['expected']} actual={values['actual']}"
                    for field, values in differences.items()
                )
            )
            self.mark_dirty(self.ledger_path, error)
            raise error
        return {"status": PROJECTION_READY, "consistent": True, "summary": actual}

    def assert_ready(self) -> None:
        records = self.db.query(LedgerIndexFile).all()
        if not records or any(record.status != PROJECTION_READY for record in records):
            raise LedgerProjectionDirtyError("账本查询投影不可用，请重建后重试")


class TransactionQueryService:
    """基于 SQLite 投影的交易游标查询。"""

    def __init__(self, db: Session, ledger_path: Path | str):
        self.db = db
        self.projection = LedgerProjectionService(db, ledger_path)

    def list_transactions(
        self,
        *,
        limit: int = 20,
        cursor: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        account: str | None = None,
        transaction_type: str | None = None,
        tags: list[str] | None = None,
        description: str | None = None,
    ) -> dict:
        self.projection.assert_ready()
        query = self.db.query(LedgerTransaction).options(
            selectinload(LedgerTransaction.postings),
            selectinload(LedgerTransaction.tags),
        )
        if start_date:
            query = query.filter(LedgerTransaction.date >= date.fromisoformat(start_date))
        if end_date:
            query = query.filter(LedgerTransaction.date <= date.fromisoformat(end_date))
        if account:
            query = query.filter(LedgerTransaction.postings.any(LedgerPosting.account == account))
        if transaction_type:
            query = query.filter(LedgerTransaction.transaction_type == transaction_type)
        if tags:
            query = query.filter(LedgerTransaction.tags.any(LedgerTag.tag.in_(tags)))
        if description:
            keyword = f"%{description.lower()}%"
            query = query.filter(
                or_(
                    func.lower(LedgerTransaction.narration).like(keyword),
                    func.lower(func.coalesce(LedgerTransaction.payee, "")).like(keyword),
                )
            )
        if cursor:
            cursor_date, cursor_lineno, cursor_id = decode_transaction_cursor(cursor)
            # 排序：date DESC, source_lineno DESC, id DESC
            query = query.filter(
                or_(
                    LedgerTransaction.date < cursor_date,
                    and_(
                        LedgerTransaction.date == cursor_date,
                        LedgerTransaction.source_lineno < cursor_lineno,
                    ),
                    and_(
                        LedgerTransaction.date == cursor_date,
                        LedgerTransaction.source_lineno == cursor_lineno,
                        LedgerTransaction.id < cursor_id,
                    ),
                )
            )
        rows = (
            query.order_by(
                LedgerTransaction.date.desc(),
                LedgerTransaction.source_lineno.desc(),
                LedgerTransaction.id.desc(),
            )
            .limit(limit + 1)
            .all()
        )
        has_more = len(rows) > limit
        page_rows = rows[:limit]
        next_cursor = None
        if has_more and page_rows:
            last = page_rows[-1]
            next_cursor = encode_transaction_cursor(
                last.date, last.source_lineno, last.id
            )
        return {
            "items": [self._to_dto(row) for row in page_rows],
            "next_cursor": next_cursor,
            "has_more": has_more,
        }

    @staticmethod
    def _to_dto(transaction: LedgerTransaction) -> dict:
        postings = [
            {
                "account": posting.account,
                "amount": posting.amount_text,
                "currency": posting.currency,
                "cost": posting.cost_text,
                "cost_currency": posting.cost_currency,
                "price": posting.price_text,
                "price_currency": posting.price_currency,
                "flag": posting.flag,
                "meta": {},
            }
            for posting in transaction.postings
        ]
        return {
            "id": transaction.id,
            "date": transaction.date.isoformat(),
            "description": transaction.narration,
            "payee": transaction.payee,
            "flag": transaction.flag,
            "postings": postings,
            "tags": [tag.tag for tag in transaction.tags],
            "links": json.loads(transaction.links_json),
            "meta": {
                "filename": transaction.source_file,
                "lineno": transaction.source_lineno,
            },
            "transaction_type": transaction.transaction_type,
            "display_amounts": _display_amounts(
                transaction.transaction_type, transaction.postings
            ),
            "accounts": [posting.account for posting in transaction.postings],
            "currencies": sorted({posting.currency for posting in transaction.postings}),
            "created_at": None,
            "updated_at": None,
        }
