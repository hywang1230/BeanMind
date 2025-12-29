"""交易仓储 Beancount + SQLite 实现

从 Beancount 文件读取交易数据，并同步元数据到 SQLite。
"""
from pathlib import Path
from typing import Optional, List, Dict
from decimal import Decimal
from datetime import date, datetime
import uuid

from beancount.core.data import Transaction as BeancountTransaction, Posting as BeancountPosting
from beancount.core import amount
from beancount.parser import printer
from sqlalchemy.orm import Session

from backend.domain.transaction.entities import Transaction, Posting, TransactionType, TransactionFlag
from backend.domain.transaction.repositories import TransactionRepository
from backend.infrastructure.persistence.beancount.beancount_service import BeancountService
from backend.infrastructure.persistence.db.models import TransactionMetadata


class TransactionRepositoryImpl(TransactionRepository):
    """
    交易仓储的 Beancount + SQLite 实现
    
    - 交易数据存储在 Beancount 文件中
    - 交易元数据存储在 SQLite 数据库中
    - 确保两者的一致性
    """
    
    def __init__(self, beancount_service: BeancountService, db_session: Session):
        """
        初始化交易仓储
        
        Args:
            beancount_service: Beancount 服务实例
            db_session: SQLAlchemy 数据库会话
        """
        self.beancount_service = beancount_service
        self.db_session = db_session
        self._transactions_cache: Dict[str, Transaction] = {}
        self._load_transactions()
    
    def _load_transactions(self):
        """从 Beancount 加载所有交易"""
        self._transactions_cache.clear()
        
        for entry in self.beancount_service.entries:
            if isinstance(entry, BeancountTransaction):
                transaction = self._beancount_to_domain(entry)
                self._transactions_cache[transaction.id] = transaction
    
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
        
        # 确定交易 ID
        # 1. 优先使用元数据中存储的持久化 ID
        if entry.meta and 'id' in entry.meta:
            transaction_id = entry.meta['id']
        else:
            # 2. 如果没有持久化 ID，则生成基于内容的哈希 ID（兼容旧数据）
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
                cost=amount.Amount(p.cost, p.cost_currency) if p.cost else None,
                price=amount.Amount(p.price, p.price_currency) if p.price else None,
                flag=p.flag,
                meta=p.meta or {}
            )
            postings.append(posting)
        
        # 转换 Flag
        flag = transaction.flag.value if transaction.flag else "*"
        
        # 准备元数据，确保包含 ID 以实现持久化
        meta = transaction.meta.copy() if transaction.meta else {}
        if transaction.id:
            meta['id'] = transaction.id
        
        # 移除内部使用的位置信息，避免写回文件
        if 'filename' in meta:
            del meta['filename']
        if 'lineno' in meta:
            del meta['lineno']

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
    
    def find_by_id(self, transaction_id: str) -> Optional[Transaction]:
        """根据 ID 查找交易"""
        return self._transactions_cache.get(transaction_id)
    
    def find_all(
        self,
        user_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Transaction]:
        """查找所有交易（支持分页）"""
        transactions = list(self._transactions_cache.values())
        
        # 按日期倒序排列
        transactions.sort(key=lambda t: t.date, reverse=True)
        
        # 分页
        if offset:
            transactions = transactions[offset:]
        if limit:
            transactions = transactions[:limit]
        
        return transactions
    
    def find_by_date_range(
        self,
        start_date: date,
        end_date: date,
        user_id: Optional[str] = None
    ) -> List[Transaction]:
        """查找指定日期范围内的交易"""
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
    
    def create(self, transaction: Transaction, user_id: Optional[str] = None) -> Transaction:
        """
        创建新交易
        
        同时写入 Beancount 文件和 SQLite 数据库。
        交易根据日期年份保存到对应的年份文件中（如 transactions_2025.beancount）。
        """
        # 生成 ID（如果没有）
        if not transaction.id:
            transaction.id = self._generate_transaction_id(transaction.date, transaction.description)
        
        # 转换为 Beancount 格式
        beancount_txn = self._domain_to_beancount(transaction)
        
        # 根据交易日期获取对应年份的文件，并确保文件存在
        year = transaction.date.year
        year_file = self.beancount_service.ensure_year_file(year)
        
        # 写入到对应年份的 Beancount 文件
        with open(year_file, "a", encoding="utf-8") as f:
            f.write("\n")
            f.write(printer.format_entry(beancount_txn))
            f.write("\n")
        
        # 保存元数据到 SQLite
        if user_id:
            metadata = TransactionMetadata(
                user_id=user_id,
                beancount_id=transaction.id,
                sync_at=datetime.now(),
                notes=transaction.meta.get("notes", "")
            )
            self.db_session.add(metadata)
            self.db_session.commit()
        
        # 重新加载
        self.reload()
        
        return self._transactions_cache.get(transaction.id, transaction)

    
    def update(self, transaction: Transaction) -> Transaction:
        """
        更新交易
        
        策略：
        1. 根据元数据中的位置信息删除原有交易
        2. 将更新后的交易写入（可能是新文件）
        3. 更新缓存和元数据
        """
        if not self.exists(transaction.id):
            raise ValueError(f"交易 '{transaction.id}' 不存在")
            
        # 获取原有交易的元数据（位置信息）
        # 尝试从传入的对象获取，如果缺失则回退到缓存查找
        if not transaction.meta or 'filename' not in transaction.meta or 'lineno' not in transaction.meta:
            cached_txn = self._transactions_cache.get(transaction.id)
            if cached_txn and cached_txn.meta and 'filename' in cached_txn.meta:
                # 复制元数据位置信息
                if not transaction.meta:
                    transaction.meta = {}
                transaction.meta['filename'] = cached_txn.meta['filename']
                transaction.meta['lineno'] = cached_txn.meta['lineno']
            else:
                raise ValueError("无法定位原始交易文件位置，更新失败")
            
        filename = transaction.meta['filename']
        lineno = transaction.meta['lineno']
        
        # 获取关联的用户ID（从DB元数据）
        metadata = self.db_session.query(TransactionMetadata).filter_by(
            beancount_id=transaction.id
        ).first()
        user_id = metadata.user_id if metadata else None
        
        # 1. 从文件中删除原交易
        if not self._remove_transaction_from_file(filename, lineno):
             raise ValueError(f"无法从文件中删除原交易: {filename}:{lineno}")
             
        # 2. 删除旧的元数据
        if metadata:
            self.db_session.delete(metadata)
            self.db_session.flush()
            
        # 3. 创建新交易（写入文件的同时生成新 ID，创建新元数据）
        # 注意：不再清除 transaction.id，而是将其作为 persistent ID 写入新条目的元数据
        try:
            new_transaction = self.create(transaction, user_id)
        except Exception as e:
            raise RuntimeError(f"更新交易失败（旧数据已删除，新数据写入失败）: {e}")
        
        return new_transaction

    def _remove_transaction_from_file(self, filename: str, lineno: int) -> bool:
        """
        从文件中删除指定行号的交易块
        
        Args:
            filename: 文件路径
            lineno: 交易起始行号（1-based）
        """
        path = Path(filename)
        if not path.exists():
            return False
            
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                
            if lineno < 1 or lineno > len(lines):
                return False
                
            # Beancount lineno 是 1-based，转换为 list index
            start_idx = lineno - 1
            
            # 确定交易块的结束位置
            end_idx = start_idx + 1
            while end_idx < len(lines):
                line = lines[end_idx]
                stripped = line.strip()
                
                # 空行视为 Entry 结束符
                if not stripped:
                    break
                    
                # 缩进的行属于当前 Entry
                if line[0] == ' ' or line[0] == '\t':
                    end_idx += 1
                    continue
                
                # 非缩进且非空行，说明是下一个 Entry
                break
            
            # 删除内容
            del lines[start_idx:end_idx]
            
            # 写回文件
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines)
                
            return True
            
        except Exception as e:
            return False
    
    def delete(self, transaction_id: str) -> bool:
        """
        删除交易
        
        从 Beancount 文件和 SQLite 数据库中删除交易。
        """
        if not self.exists(transaction_id):
            return False
        
        # 获取交易实体
        transaction = self._transactions_cache[transaction_id]
        
        # 根据交易日期确定年份文件
        year = transaction.date.year
        year_file = self.beancount_service.get_year_file_path(year)
        
        if not year_file.exists():
            # 文件不存在，可能在主文件中
            year_file = self.beancount_service.ledger_path
        
        # 读取文件内容
        with open(year_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 查找并删除交易块
        # 交易格式类似于:
        # 2025-12-23 * "Payee" "Description"
        #   Account:One  100 CNY
        #   Account:Two  -100 CNY
        
        lines = content.split("\n")
        new_lines = []
        skip_until_next_entry = False
        found = False
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # 检查是否是交易行的开始（日期开头）
            if line and len(line) >= 10 and line[0].isdigit():
                # 可能是一个新的 entry（交易、余额等）
                # 检查是否是我们要删除的交易
                if self._is_target_transaction(lines, i, transaction):
                    # 跳过这个交易块
                    skip_until_next_entry = True
                    found = True
                    i += 1
                    continue
            
            if skip_until_next_entry:
                # 检查是否到达下一个 entry
                if line and len(line) >= 10 and line[0].isdigit():
                    # 这是一个新的 entry，停止跳过
                    skip_until_next_entry = False
                    new_lines.append(line)
                elif line.strip() == "" and i + 1 < len(lines):
                    # 空行，检查下一行是否是新 entry
                    next_line = lines[i + 1]
                    if next_line and len(next_line) >= 10 and next_line[0].isdigit():
                        skip_until_next_entry = False
                        # 不加入这个空行，让下一个 entry 保持正常间距
                # 如果仍在跳过中，不添加此行
            else:
                new_lines.append(line)
            
            i += 1
        
        if not found:
            # 尝试在主文件中查找
            if year_file != self.beancount_service.ledger_path:
                main_file = self.beancount_service.ledger_path
                with open(main_file, "r", encoding="utf-8") as f:
                    content = f.read()
                
                lines = content.split("\n")
                new_lines = []
                skip_until_next_entry = False
                
                i = 0
                while i < len(lines):
                    line = lines[i]
                    
                    if line and len(line) >= 10 and line[0].isdigit():
                        if self._is_target_transaction(lines, i, transaction):
                            skip_until_next_entry = True
                            found = True
                            i += 1
                            continue
                    
                    if skip_until_next_entry:
                        if line and len(line) >= 10 and line[0].isdigit():
                            skip_until_next_entry = False
                            new_lines.append(line)
                        elif line.strip() == "" and i + 1 < len(lines):
                            next_line = lines[i + 1]
                            if next_line and len(next_line) >= 10 and next_line[0].isdigit():
                                skip_until_next_entry = False
                    else:
                        new_lines.append(line)
                    
                    i += 1
                
                if found:
                    year_file = main_file
        
        if found:
            # 写回文件
            with open(year_file, "w", encoding="utf-8") as f:
                f.write("\n".join(new_lines))
        
        # 从缓存中删除
        del self._transactions_cache[transaction_id]
        
        # 删除 SQLite 元数据
        metadata = self.db_session.query(TransactionMetadata).filter_by(
            beancount_id=transaction_id
        ).first()
        if metadata:
            self.db_session.delete(metadata)
            self.db_session.commit()
        
        # 重新加载
        self.reload()
        
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
        return transaction_id in self._transactions_cache
    
    def count(
        self,
        user_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> int:
        """统计交易数量"""
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
        user_id: Optional[str] = None
    ) -> Dict[str, any]:
        """获取交易统计信息"""
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

    def get_all_payees(self) -> List[str]:
        """获取所有历史交易方（Payee）"""
        payees = set()
        for t in self._transactions_cache.values():
            if t.payee:
                payees.add(t.payee)
        return sorted(list(payees))
