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
        
        # 生成唯一 ID（基于日期和描述的哈希）
        transaction_id = self._generate_transaction_id(entry.date, entry.narration)
        
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
        
        return BeancountTransaction(
            meta=transaction.meta or {},
            date=transaction.date,
            flag=flag,
            payee=transaction.payee or "",
            narration=transaction.description,
            tags=transaction.tags or set(),
            links=transaction.links or set(),
            postings=postings
        )
    
    def _generate_transaction_id(self, txn_date: date, description: str) -> str:
        """
        生成交易 ID
        
        Args:
            txn_date: 交易日期
            description: 交易描述
            
        Returns:
            唯一的交易 ID
        """
        # 使用 UUID 确保唯一性
        unique_str = f"{txn_date.isoformat()}_{description}_{uuid.uuid4().hex[:8]}"
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
        
        注意：Beancount 不支持直接修改交易。
        这个方法需要重写整个文件或使用其他策略。
        目前的简化实现只更新缓存。
        """
        if not self.exists(transaction.id):
            raise ValueError(f"交易 '{transaction.id}' 不存在")
        
        # 更新缓存
        self._transactions_cache[transaction.id] = transaction
        
        # 警告：实际文件未更新
        # 在生产环境中，需要实现文件重写逻辑
        
        return transaction
    
    def delete(self, transaction_id: str) -> bool:
        """
        删除交易
        
        注意：Beancount 不支持直接删除交易。
        这个方法需要重写整个文件。
        目前的简化实现只从缓存中删除。
        """
        if not self.exists(transaction_id):
            return False
        
        # 从缓存中删除
        del self._transactions_cache[transaction_id]
        
        # 删除 SQLite 元数据
        metadata = self.db_session.query(TransactionMetadata).filter_by(
            beancount_id=transaction_id
        ).first()
        if metadata:
            self.db_session.delete(metadata)
            self.db_session.commit()
        
        # 警告：实际文件未更新
        # 在生产环境中，需要实现文件重写逻辑
        
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
