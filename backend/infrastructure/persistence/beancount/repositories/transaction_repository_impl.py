"""交易仓储 Beancount + SQLite 实现

从 Beancount 文件读取交易数据，并同步元数据到 SQLite。
"""
from pathlib import Path
from typing import Optional, List, Dict
from decimal import Decimal
from datetime import date
import logging
import uuid
from contextlib import contextmanager
from functools import wraps
import time
import re

from beancount.core.data import Transaction as BeancountTransaction, Posting as BeancountPosting
from beancount.core import amount
from beancount.core.position import Cost
from beancount.parser import parser, printer
from sqlalchemy.orm import Session, selectinload

from backend.domain.transaction.entities import Transaction, Posting, TransactionType, TransactionFlag
from backend.domain.transaction.repositories import TransactionRepository
from backend.infrastructure.persistence.beancount.beancount_service import BeancountService
from backend.infrastructure.persistence.db.models import LedgerTransaction, LedgerIndexFile
from backend.infrastructure.persistence.ledger_projection import (
    LedgerProjectionService, LedgerProjectionDirtyError, _fingerprint, _content_hash,
)
from backend.infrastructure.persistence.beancount.ledger_write import (
    ledger_lock, commit_ledger_files, has_pending_write,
)



logger = logging.getLogger(__name__)


def _command(method):
    @wraps(method)
    def coordinated(self, *args, **kwargs):
        with self.command_context():
            return method(self, *args, **kwargs)
    return coordinated


def _read(method):
    @wraps(method)
    def coordinated(self, *args, **kwargs):
        with ledger_lock(self.beancount_service.ledger_path):
            if self.projection_service and not self._command_depth:
                self.projection_service.assert_ready()
            return method(self, *args, **kwargs)
    return coordinated


class TransactionRepositoryImpl(TransactionRepository):
    """
    交易仓储的 Beancount + SQLite 实现
    
    - 交易数据存储在 Beancount 文件中
    - 交易元数据存储在 SQLite 数据库中
    - 确保两者的一致性
    """
    
    def __init__(
        self,
        beancount_service: BeancountService,
        db_session: Session,
        projection_service: Optional[LedgerProjectionService] = None,
        load_transactions: bool = True,
    ):
        """
        初始化交易仓储
        
        Args:
            beancount_service: Beancount 服务实例
            db_session: SQLAlchemy 数据库会话
        """
        self.beancount_service = beancount_service
        self.db_session = db_session
        self.projection_service = projection_service
        self._transactions_cache: Dict[str, Transaction] = {}
        self._cache_loaded = False
        self._command_depth = 0
        self._source_snapshots = {}
        self._source_fingerprints = {}
        if load_transactions:
            self._load_transactions()
    
    @contextmanager
    def command_context(self, account_repository=None):
        """锁内刷新依赖，避免使用等待锁之前取得的源位置和账户状态。"""
        started = time.perf_counter()
        with ledger_lock(self.beancount_service.ledger_path):
            if self._command_depth:
                yield
                return
            waited = (time.perf_counter() - started) * 1000
            self._command_depth = 1
            try:
                if self.db_session.new or self.db_session.dirty or self.db_session.deleted:
                    raise RuntimeError("账本命令不能携带尚未提交的数据库修改")
                from backend.infrastructure.persistence.beancount.beancount_provider import BeancountServiceProvider
                self.db_session.rollback()
                if self.projection_service:
                    if has_pending_write(self.beancount_service.ledger_path):
                        self.projection_service.full_rebuild()
                    records = self.db_session.query(LedgerIndexFile).all()
                    if not records:
                        self.projection_service.full_rebuild()
                    elif any(row.status != "READY" for row in records):
                        raise LedgerProjectionDirtyError("账本查询投影不可用，请重建后重试")
                    elif any(
                        not Path(row.path).exists()
                        or _fingerprint(Path(row.path)) != (row.mtime_ns, row.size, row.content_hash)
                        for row in records
                    ):
                        self.projection_service.ensure_current()
                        BeancountServiceProvider.invalidate()
                elif has_pending_write(self.beancount_service.ledger_path):
                    raise RuntimeError("账本存在未完成恢复，不能继续写入")
                load_started = time.perf_counter()
                self.beancount_service = BeancountServiceProvider.get_service(
                    self.beancount_service.ledger_path
                )
                logger.info("ledger_source_load duration_ms=%.1f", (time.perf_counter() - load_started) * 1000)
                if self.beancount_service.errors:
                    raise ValueError("账本校验失败，拒绝写入")
                self._transactions_cache.clear()
                self._cache_loaded = False
                if self.projection_service is None:
                    self._load_transactions()
                self._source_snapshots.clear()
                self._source_fingerprints.clear()
                if account_repository is not None and hasattr(account_repository, "_load_accounts"):
                    account_repository.beancount_service = self.beancount_service
                    account_repository._load_accounts()
                yield
            finally:
                self._command_depth = 0
                self._source_snapshots.clear()
                logger.info("ledger_command total_ms=%.1f lock_wait_ms=%.1f",
                            (time.perf_counter() - started) * 1000, waited)

    def _read_source(self, path, *, parse_entries=True):
        path = Path(path).resolve()
        if path not in self._source_snapshots:
            before = _fingerprint(path)
            content = path.read_text(encoding="utf-8")
            if _fingerprint(path) != before:
                raise ValueError("交易源文件在读取期间已改变")
            self._source_snapshots[path] = (content, None)
            self._source_fingerprints[path] = before
        content, entries = self._source_snapshots[path]
        if parse_entries and entries is None:
            parse_started = time.perf_counter()
            entries, errors, _ = parser.parse_string(content, report_filename=str(path))
            if errors:
                raise ValueError("交易源文件无法安全解析")
            self._source_snapshots[path] = (content, entries)
            logger.info("ledger_source_parse duration_ms=%.1f", (time.perf_counter() - parse_started) * 1000)
        return self._source_snapshots[path]

    def _load_transactions(self):
        """从 Beancount 加载所有交易"""
        self._transactions_cache.clear()
        
        for entry in self.beancount_service.entries:
            if isinstance(entry, BeancountTransaction):
                transaction = self._beancount_to_domain(entry)
                self._transactions_cache[transaction.id] = transaction
        self._cache_loaded = True

    def _ensure_cache(self) -> None:
        if not self._cache_loaded:
            self._load_transactions()
    
    def _beancount_to_domain(self, entry: BeancountTransaction) -> Transaction:
        """
        将 Beancount 交易转换为领域实体
        
        Args:
            entry: Beancount 交易条目
            
        Returns:
            Transaction 领域实体
        """
        # 转换 Postings
        postings = []
        for p in entry.postings:
            posting = Posting(
                account=p.account,
                amount=p.units.number,
                currency=p.units.currency,
                cost=p.cost.number if p.cost else None,
                cost_currency=p.cost.currency if p.cost else None,
                price=p.price.number if p.price else None,
                price_currency=p.price.currency if p.price else None,
                flag=p.flag,
                meta=p.meta or {}
            )
            postings.append(posting)
        
        # 优先使用元数据中的 ID（如果存在且不仅是占位）
        # 这确保了即使内容修改（导致哈希变化），ID 也能保持不变
        if entry.meta and 'id' in entry.meta:
            transaction_id = entry.meta['id']
        else:
            # 否则，基于交易完整内容生成稳定的哈希 ID
            transaction_id = self._generate_transaction_id(
                entry.date, 
                entry.narration, 
                entry.payee, 
                entry.postings
            )
        
        # 转换 Flag
        flag = TransactionFlag.CLEARED if entry.flag == "*" else TransactionFlag.PENDING
        
        return Transaction(
            id=transaction_id,
            date=entry.date,
            description=entry.narration,
            payee=entry.payee or None,
            flag=flag,
            postings=postings,
            tags=set(entry.tags) if entry.tags else set(),
            links=set(entry.links) if entry.links else set(),
            meta=entry.meta or {}
        )
    
    def _domain_to_beancount(self, transaction: Transaction) -> BeancountTransaction:
        """
        将领域实体转换为 Beancount 交易
        
        Args:
            transaction: Transaction 领域实体
            
        Returns:
            Beancount 交易条目
        """
        # 转换 Postings
        postings = []
        for p in transaction.postings:
            posting = BeancountPosting(
                account=p.account,
                units=amount.Amount(p.amount, p.currency),
                cost=Cost(p.cost, p.cost_currency, None, None) if p.cost is not None else None,
                price=amount.Amount(p.price, p.price_currency) if p.price is not None else None,
                flag=p.flag,
                meta=p.meta or {}
            )
            postings.append(posting)
        
        # 转换 Flag
        flag = transaction.flag.value if transaction.flag else "*"
        
        # 准备元数据
        meta = transaction.meta.copy() if transaction.meta else {}
        
        # 智能 ID 持久化策略：
        # 计算基于当前内容的哈希 ID
        content_hash_id = self._generate_transaction_id(
            transaction.date,
            transaction.description,
            transaction.payee,
            transaction.postings
        )
        
        # 如果当前 ID 与 内容哈希 ID 不一致，说明这是一个已有 ID 但内容被修改过的交易（或者ID通过其他方式生成）
        # 此时必须将 ID 写入元数据，以保证 ID 不变性（First Principle）
        if transaction.id and transaction.id != content_hash_id:
            meta['id'] = transaction.id
        else:
            # 如果一致（新交易或未修改关键内容），则不需要在文件中冗余存储 ID
            # 保持文件整洁
            if 'id' in meta:
                del meta['id']
            
        # 移除内部字段，确保不要写入文件
        for internal_key in ['filename', 'lineno']:
            if internal_key in meta:
                del meta[internal_key]
        
        return BeancountTransaction(
            meta=meta,
            date=transaction.date,
            flag=flag,
            payee=transaction.payee or "",
            narration=transaction.description,
            tags=transaction.tags or set(),
            links=transaction.links or set(),
            postings=postings
        )
    
    def _generate_transaction_id(
        self, 
        txn_date: date, 
        description: str, 
        payee: Optional[str] = None,
        postings: Optional[List] = None
    ) -> str:
        """
        生成交易 ID
        
        基于交易的完整内容生成稳定的哈希值，确保每次加载后相同的交易会获得相同的 ID。
        
        Args:
            txn_date: 交易日期
            description: 交易描述
            payee: 交易方
            postings: 记账分录列表
            
        Returns:
            唯一的交易 ID
        """
        # 使用交易的完整内容生成稳定的哈希
        content_parts = [
            txn_date.isoformat(),
            description or "",
            payee or ""
        ]
        
        # 包含分录信息以区分相同日期、描述的不同交易
        if postings:
            for p in postings:
                # For BeancountPosting objects, access units.number and units.currency
                if hasattr(p, 'units') and hasattr(p.units, 'number') and hasattr(p.units, 'currency'):
                    content_parts.append(f"{p.account}:{p.units.number}:{p.units.currency}")
                # For domain Posting objects, access amount and currency directly
                elif hasattr(p, 'amount') and hasattr(p, 'currency'):
                    content_parts.append(f"{p.account}:{p.amount}:{p.currency}")
        
        unique_str = "|".join(content_parts)
        return uuid.uuid5(uuid.NAMESPACE_DNS, unique_str).hex
    
    def reload(self):
        """重新加载交易数据"""
        self.beancount_service.reload()
        self._load_transactions()

    def _refresh_projection(self, *files: Path | str) -> None:
        """写后刷新派生投影；失败不回滚已经成功的 Beancount 写入。"""
        if not self.projection_service:
            return
        for file in dict.fromkeys(str(Path(item).resolve()) for item in files):
            try:
                self.projection_service.refresh_file(file)
            except Exception as exc:
                logger.exception("Beancount 写入成功，但投影刷新失败: %s", file)
                self.projection_service.mark_dirty(file, exc)
                break
    
    @_read
    def find_by_id(self, transaction_id: str) -> Optional[Transaction]:
        """根据 ID 查找交易"""
        cached = self._transactions_cache.get(transaction_id)
        if cached:
            return cached
        if self.projection_service:
            row = (
                self.db_session.query(LedgerTransaction)
                .options(
                    selectinload(LedgerTransaction.postings),
                    selectinload(LedgerTransaction.tags),
                )
                .filter(LedgerTransaction.id == transaction_id)
                .first()
            )
            if row:
                content = self._read_source(row.source_file, parse_entries=False)[0]
                source_entry = None
                # 常规记录只解析目标块。存在 parser 上下文指令或摘要不符时，
                # 仍解析完整源快照，保留 pushtag/pushmeta 等历史语义。
                if not re.search(r"(?m)^\s*(?:pushtag|poptag|pushmeta|popmeta)\b", content):
                    lines = content.splitlines(keepends=True)
                    start = row.source_lineno - 1
                    end = start + 1
                    while end < len(lines):
                        line = lines[end]
                        if line.strip() and not line[0].isspace() and not line.lstrip().startswith(";"):
                            break
                        end += 1
                    if 0 <= start < len(lines):
                        parsed, errors, _ = parser.parse_string(
                            "".join(lines[start:end]), report_filename=row.source_file,
                            report_firstline=row.source_lineno,
                        )
                        if not errors and len(parsed) == 1 and isinstance(parsed[0], BeancountTransaction):
                            try:
                                if _content_hash(parsed[0]) == row.content_hash:
                                    source_entry = parsed[0]
                            except (AttributeError, TypeError):
                                pass  # booking/interpolation requires the complete source below.
                if source_entry is None:
                    _, source_entries = self._read_source(row.source_file)
                    source_entry = next(
                        (
                            entry for entry in source_entries
                            if isinstance(entry, BeancountTransaction)
                            and entry.meta.get("lineno") == row.source_lineno
                        ),
                        None,
                    )
                if source_entry is None:
                    raise ValueError(
                        f"无法在源位置找到交易: {row.source_file}:{row.source_lineno}"
                    )
                # 行号必须仍指向同一内容，不能将另一笔源元数据写回。
                try:
                    source_hash = _content_hash(source_entry)
                except (AttributeError, TypeError):
                    # 成本/推导分录使用完整 loader 已验证的业务内容。
                    source_hash = None
                if source_hash is None or source_hash != row.content_hash:
                    # 全局插件/booking 可以改变分录；用完整 loader 结果核对身份。
                    matching = (
                        entry for entry in self.beancount_service.entries
                        if isinstance(entry, BeancountTransaction)
                        and str(Path(entry.meta.get("filename", "")).resolve()) == row.source_file
                        and entry.meta.get("lineno") == row.source_lineno
                    )
                    if not any(_content_hash(entry) == row.content_hash for entry in matching):
                        raise ValueError("交易源文件与投影不一致，请刷新后重试")
                transaction = Transaction(
                    id=row.id,
                    date=row.date,
                    description=row.narration,
                    payee=row.payee,
                    flag=(
                        TransactionFlag.CLEARED
                        if row.flag == "*"
                        else TransactionFlag.PENDING
                    ),
                    postings=[
                        Posting(
                            account=posting.account,
                            amount=Decimal(posting.amount_text),
                            currency=posting.currency,
                            cost=Decimal(posting.cost_text) if posting.cost_text else None,
                            cost_currency=posting.cost_currency,
                            price=Decimal(posting.price_text) if posting.price_text else None,
                            price_currency=posting.price_currency,
                            flag=posting.flag,
                            meta=(
                                source_entry.postings[index].meta or {}
                                if index < len(source_entry.postings)
                                else {}
                            ),
                        )
                        for index, posting in enumerate(row.postings)
                    ],
                    tags=set(source_entry.tags or []),
                    links=set(source_entry.links or []),
                    meta=dict(source_entry.meta or {}),
                )
                self._transactions_cache[transaction_id] = transaction
                return transaction
        return None
    
    def find_all(
        self,
        limit: Optional[int] = None,
    ) -> List[Transaction]:
        """查找所有交易（支持分页）"""
        self._ensure_cache()
        transactions = list(self._transactions_cache.values())
        
        # 按日期倒序排列
        transactions.sort(key=lambda t: t.date, reverse=True)
        
        # 分页
        if limit:
            transactions = transactions[:limit]
        
        return transactions
    
    def find_by_date_range(
        self,
        start_date: date,
        end_date: date,
    ) -> List[Transaction]:
        """查找指定日期范围内的交易"""
        self._ensure_cache()
        return [
            t for t in self._transactions_cache.values()
            if start_date <= t.date <= end_date
        ]
    
    def find_by_account(
        self,
        account_name: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Transaction]:
        """查找涉及指定账户的交易"""
        self._ensure_cache()
        transactions = [
            t for t in self._transactions_cache.values()
            if account_name in t.get_accounts()
        ]
        
        # 日期过滤
        if start_date:
            transactions = [t for t in transactions if t.date >= start_date]
        if end_date:
            transactions = [t for t in transactions if t.date <= end_date]
        
        return transactions
    
    def find_by_type(
        self,
        transaction_type: TransactionType,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Transaction]:
        """查找指定类型的交易"""
        self._ensure_cache()
        transactions = [
            t for t in self._transactions_cache.values()
            if t.detect_transaction_type() == transaction_type
        ]
        
        # 日期过滤
        if start_date:
            transactions = [t for t in transactions if t.date >= start_date]
        if end_date:
            transactions = [t for t in transactions if t.date <= end_date]
        
        return transactions
    
    def find_by_tags(
        self,
        tags: List[str],
        match_all: bool = False
    ) -> List[Transaction]:
        """根据标签查找交易"""
        self._ensure_cache()
        if match_all:
            # AND 逻辑：必须包含所有标签
            return [
                t for t in self._transactions_cache.values()
                if all(tag in t.tags for tag in tags)
            ]
        else:
            # OR 逻辑：包含任一标签
            return [
                t for t in self._transactions_cache.values()
                if any(tag in t.tags for tag in tags)
            ]
    
    def find_by_description(
        self,
        keyword: str,
        case_sensitive: bool = False
    ) -> List[Transaction]:
        """根据描述关键词搜索交易"""
        self._ensure_cache()
        if case_sensitive:
            return [
                t for t in self._transactions_cache.values()
                if keyword in t.description
            ]
        else:
            keyword_lower = keyword.lower()
            return [
                t for t in self._transactions_cache.values()
                if keyword_lower in t.description.lower()
            ]
    
    def find_by_keyword(
        self,
        keyword: str,
        case_sensitive: bool = False
    ) -> List[Transaction]:
        """根据关键词搜索交易（同时搜索描述和付款方）"""
        self._ensure_cache()
        if case_sensitive:
            return [
                t for t in self._transactions_cache.values()
                if keyword in t.description or (t.payee and keyword in t.payee)
            ]
        else:
            keyword_lower = keyword.lower()
            return [
                t for t in self._transactions_cache.values()
                if keyword_lower in t.description.lower() or 
                   (t.payee and keyword_lower in t.payee.lower())
            ]
    
    def _year_changes(self, transaction, changes):
        target = self.beancount_service.get_year_file_path(transaction.date.year).resolve()
        if target not in changes:
            if target.exists():
                changes[target] = self._read_source(target, parse_entries=False)[0]
            else:
                changes[target] = f"; {transaction.date.year} 年度交易记录\n"
                self._source_fingerprints[target] = None
                main = self.beancount_service.ledger_path.resolve()
                content = self._read_source(main, parse_entries=False)[0]
                include = f'include "{target.name}"'
                if include not in content.splitlines():
                    changes[main] = content.rstrip("\n") + "\n" + include + "\n"
        return target

    @staticmethod
    def _replace_block(content, lineno, replacement):
        lines = content.splitlines(keepends=True)
        start = int(lineno) - 1
        if start < 0 or start >= len(lines):
            raise ValueError("交易源位置已失效")
        end = start + 1
        # 空行和注释可以位于交易内部；下一个非缩进指令才是边界。
        while end < len(lines):
            line = lines[end]
            if line.strip() and not line[0].isspace() and not line.lstrip().startswith(";"):
                break
            end += 1
        # 保留交易后面的空行/注释，避免破坏相邻说明。
        while end > start + 1 and (not lines[end - 1].strip() or lines[end - 1].lstrip().startswith(";")):
            end -= 1
        return "".join(lines[:start]) + replacement + "".join(lines[end:])

    def _commit_changes(self, changes):
        started = time.perf_counter()
        def before_commit():
            if self.projection_service:
                self.projection_service.mark_dirty_files(changes)
        def after_commit(parsed_files):
            if self.projection_service:
                self.projection_service.refresh_files(changes, parsed_files=parsed_files)
        try:
            return commit_ledger_files(
                self.beancount_service.ledger_path, changes,
                before_commit=before_commit, after_commit=after_commit,
                expected_fingerprints={str(path): self._source_fingerprints[path] for path in changes},
                validation_context=(self.beancount_service.entries, self.beancount_service.options),
            )
        finally:
            from backend.infrastructure.persistence.beancount.beancount_provider import BeancountServiceProvider
            BeancountServiceProvider.invalidate()
            self._source_snapshots.clear()
            logger.info("ledger_save files=%d total_ms=%.1f", len(changes),
                        (time.perf_counter() - started) * 1000)

    @_command
    def create(self, transaction: Transaction) -> Transaction:
        if not transaction.id:
            transaction.id = uuid.uuid4().hex
        changes = {}
        target = self._year_changes(transaction, changes)
        changes[target] += "\n" + printer.format_entry(self._domain_to_beancount(transaction)) + "\n"
        self._commit_changes(changes)
        self._transactions_cache[transaction.id] = transaction
        return transaction

    @_command
    def update(self, transaction: Transaction) -> Transaction:
        original = self.find_by_id(transaction.id)
        if original is None:
            raise ValueError(f"交易 '{transaction.id}' 不存在")
        meta = original.meta or {}
        if not meta.get("filename") or not meta.get("lineno"):
            raise ValueError("无法定位原始交易文件位置")
        source = Path(meta["filename"]).resolve()
        content = self._read_source(source, parse_entries=False)[0]
        target = self.beancount_service.get_year_file_path(transaction.date.year).resolve()
        formatted = printer.format_entry(self._domain_to_beancount(transaction)).rstrip("\n") + "\n"
        if source == target:
            changes = {source: self._replace_block(content, meta["lineno"], formatted)}
        else:
            changes = {source: self._replace_block(content, meta["lineno"], "")}
            self._year_changes(transaction, changes)
            changes[target] += "\n" + formatted + "\n"
        self._commit_changes(changes)
        self._transactions_cache[transaction.id] = transaction
        return transaction

    @_command
    def delete(self, transaction_id: str) -> bool:
        transaction = self.find_by_id(transaction_id)
        if transaction is None:
            return False
        meta = transaction.meta or {}
        if not meta.get("filename") or not meta.get("lineno"):
            raise ValueError("无法定位原始交易文件位置")
        source = Path(meta["filename"]).resolve()
        content = self._read_source(source, parse_entries=False)[0]
        self._commit_changes({source: self._replace_block(content, meta["lineno"], "")})
        self._transactions_cache.pop(transaction_id, None)
        return True

    def _is_target_transaction(self, lines: list, start_index: int, transaction: Transaction) -> bool:
        """
        检查从 start_index 开始的交易块是否是目标交易
        
        Args:
            lines: 文件行列表
            start_index: 交易开始行的索引
            transaction: 目标交易实体
            
        Returns:
            是否匹配
        """
        line = lines[start_index]
        
        # 检查日期
        if not line.startswith(transaction.date.isoformat()):
            return False
        
        # 检查是否是交易（包含 * 或 !）
        if " * " not in line and " ! " not in line:
            return False
        
        # 检查描述/narration
        description = transaction.description or ""
        if description and f'"{description}"' not in line:
            return False
        
        # 检查 Payee（如果有）
        payee = transaction.payee or ""
        if payee and f'"{payee}"' not in line:
            return False
        
        # 收集交易块的所有 posting 行
        posting_lines = []
        for j in range(start_index + 1, len(lines)):
            posting_line = lines[j]
            if posting_line.strip() == "":
                break
            if posting_line and posting_line[0].isdigit():
                break
            if posting_line.startswith("  ") or posting_line.startswith("\t"):
                posting_lines.append(posting_line.strip())
        
        # 检查 postings 数量是否匹配
        if len(posting_lines) != len(transaction.postings):
            return False
        
        # 检查每个 posting 的账户和金额
        for posting in transaction.postings:
            found_match = False
            for pl in posting_lines:
                if posting.account in pl:
                    # 检查金额
                    amount_str = str(posting.amount)
                    # 处理可能的格式差异（如 100.00 vs 100）
                    if amount_str in pl or f"{posting.amount:.2f}" in pl:
                        found_match = True
                        break
            if not found_match:
                return False
        
        return True
    
    def exists(self, transaction_id: str) -> bool:
        """检查交易是否存在"""
        return self.find_by_id(transaction_id) is not None
    
    def count(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> int:
        """统计交易数量"""
        self._ensure_cache()
        if start_date or end_date:
            transactions = self.find_by_date_range(
                start_date or date.min,
                end_date or date.max
            )
            return len(transactions)
        
        return len(self._transactions_cache)
    
    def get_statistics(
        self,
        start_date: date,
        end_date: date,
    ) -> Dict[str, any]:
        """获取交易统计信息"""
        self._ensure_cache()
        transactions = self.find_by_date_range(start_date, end_date)
        
        # 按类型统计
        by_type = {}
        for t in transactions:
            t_type = t.detect_transaction_type().value
            by_type[t_type] = by_type.get(t_type, 0) + 1
        
        # 按货币统计
        by_currency = {}
        income_total = {}
        expense_total = {}
        
        for t in transactions:
            t_type = t.detect_transaction_type()
            
            # 遍历每个 posting，根据账户类型直接累加
            for posting in t.postings:
                currency = posting.currency
                amount = posting.amount
                
                if currency not in by_currency:
                    by_currency[currency] = {"income": Decimal(0), "expense": Decimal(0)}
                if currency not in income_total:
                    income_total[currency] = Decimal(0)
                if currency not in expense_total:
                    expense_total[currency] = Decimal(0)
                
                # 根据账户类型累加
                # Income 账户：Beancount 中收入为负数表示流入，取反后为正数
                # 投资亏损时 Income 账户为正数，取反后为负数（正确反映亏损）
                if posting.account.startswith("Income:"):
                    income_amount = -amount  # 取反
                    by_currency[currency]["income"] += income_amount
                    income_total[currency] += income_amount
                # Expenses 账户：Beancount 中支出为正数表示流出
                elif posting.account.startswith("Expenses:"):
                    by_currency[currency]["expense"] += amount
                    expense_total[currency] += amount
        
        # 转换 Decimal 为 float 便于 JSON 序列化
        return {
            "total_count": len(transactions),
            "by_type": by_type,
            "by_currency": {
                curr: {
                    "income": float(vals["income"]),
                    "expense": float(vals["expense"])
                }
                for curr, vals in by_currency.items()
            },
            "income_total": {curr: float(val) for curr, val in income_total.items()},
            "expense_total": {curr: float(val) for curr, val in expense_total.items()}
        }

    @_read
    def get_all_payees(self) -> List[str]:
        """获取所有历史交易方（Payee）"""
        if self.projection_service:
            return [
                row[0]
                for row in self.db_session.query(LedgerTransaction.payee)
                .filter(LedgerTransaction.payee.isnot(None))
                .filter(LedgerTransaction.payee != "")
                .distinct()
                .order_by(LedgerTransaction.payee)
                .all()
            ]
        self._ensure_cache()
        payees = set()
        for t in self._transactions_cache.values():
            if t.payee:
                payees.add(t.payee)
        return sorted(list(payees))
