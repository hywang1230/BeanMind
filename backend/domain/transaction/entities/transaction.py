"""Transaction 领域实体

表示一笔完整的会计交易。
在 Beancount 中，一笔交易包含多个 Posting（记账分录），遵循复式记账原则。
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import List, Set, Optional, Dict, Any
from enum import Enum

from .posting import Posting


class TransactionType(str, Enum):
    """
    交易类型枚举
    """
    EXPENSE = "expense"      # 支出
    INCOME = "income"        # 收入
    TRANSFER = "transfer"    # 转账
    OPENING = "opening"      # 期初余额
    OTHER = "other"          # 其他


class TransactionFlag(str, Enum):
    """
    交易标记枚举
    """
    CLEARED = "*"      # 已清算
    PENDING = "!"      # 待清算


@dataclass
class Transaction:
    """
    交易领域实体
    
    表示一笔完整的会计交易。
    一个 Transaction 包含多个 Posting，且所有 Posting 的金额总和必须为零（借贷平衡）。
    """
    
    # 必需字段
    date: date = field(metadata={"description": "交易日期"})
    postings: List[Posting] = field(default_factory=list, metadata={"description": "记账分录列表"})
    
    # 可选字段
    description: Optional[str] = field(default=None, metadata={"description": "交易描述/摘要"})
    payee: Optional[str] = field(default=None, metadata={"description": "收付款方"})
    flag: TransactionFlag = field(default=TransactionFlag.CLEARED, metadata={"description": "交易标记"})
    tags: Set[str] = field(default_factory=set, metadata={"description": "标签集合"})
    links: Set[str] = field(default_factory=set, metadata={"description": "链接集合"})
    meta: Dict[str, Any] = field(default_factory=dict, metadata={"description": "元数据"})
    
    # 系统字段（可选，用于与基础设施层集成）
    id: Optional[str] = field(default=None, metadata={"description": "交易唯一标识"})
    created_at: Optional[datetime] = field(default=None, metadata={"description": "创建时间"})
    updated_at: Optional[datetime] = field(default=None, metadata={"description": "更新时间"})
    
    def __post_init__(self):
        """初始化后验证"""
        self._validate()
    
    def _validate(self):
        """验证交易数据"""
        # 验证日期
        if not self.date:
            raise ValueError("交易日期不能为空")
        
        # 验证至少有两个 Posting（复式记账）
        if len(self.postings) < 2:
            raise ValueError("交易至少需要两个记账分录（复式记账原则）")
        
        # 验证借贷平衡
        if not self._is_balanced():
            raise ValueError(
                f"交易不平衡：所有记账分录的金额总和必须为零。"
                f"当前总和：{self._get_balance_summary()}"
            )
    
    def _is_balanced(self) -> bool:
        """
        验证借贷是否平衡
        
        Returns:
            如果所有 Posting 的金额总和为零则返回 True
        """
        # 按货币分组计算总和
        balances = self._calculate_balances()
        
        # 所有货币的余额都必须为零
        for currency, total in balances.items():
            # 使用一个很小的误差范围来处理浮点数精度问题
            if abs(total) > Decimal("0.01"):
                return False
        
        return True
    
    def _calculate_balances(self) -> Dict[str, Decimal]:
        """
        计算每种货币的余额
        
        Returns:
            {货币: 总金额} 字典
        """
        balances = {}
        
        for posting in self.postings:
            currency = posting.currency
            if currency not in balances:
                balances[currency] = Decimal(0)
            balances[currency] += posting.amount
        
        return balances
    
    def _get_balance_summary(self) -> str:
        """
        获取余额摘要字符串（用于错误信息）
        
        Returns:
            余额摘要字符串
        """
        balances = self._calculate_balances()
        parts = [f"{amount} {currency}" for currency, amount in balances.items()]
        return ", ".join(parts)
    
    def add_posting(self, posting: Posting):
        """
        添加记账分录
        
        Args:
            posting: 记账分录
        """
        self.postings.append(posting)
        # 重新验证平衡
        if len(self.postings) >= 2 and not self._is_balanced():
            # 不自动回滚，让调用者决定如何处理
            pass
    
    def remove_posting(self, posting: Posting):
        """
        移除记账分录
        
        Args:
            posting: 记账分录
        """
        self.postings.remove(posting)
    
    def add_tag(self, tag: str):
        """
        添加标签
        
        Args:
            tag: 标签名称
        """
        if not tag or not tag.strip():
            raise ValueError("标签不能为空")
        self.tags.add(tag.strip())
    
    def remove_tag(self, tag: str):
        """
        移除标签
        
        Args:
            tag: 标签名称
        """
        self.tags.discard(tag)
    
    def has_tag(self, tag: str) -> bool:
        """
        判断是否包含指定标签
        
        Args:
            tag: 标签名称
            
        Returns:
            如果包含则返回 True
        """
        return tag in self.tags
    
    def add_link(self, link: str):
        """
        添加链接
        
        Args:
            link: 链接名称
        """
        if not link or not link.strip():
            raise ValueError("链接不能为空")
        self.links.add(link.strip())
    
    def remove_link(self, link: str):
        """
        移除链接
        
        Args:
            link: 链接名称
        """
        self.links.discard(link)
    
    def has_link(self, link: str) -> bool:
        """
        判断是否包含指定链接
        
        Args:
            link: 链接名称
            
        Returns:
            如果包含则返回 True
        """
        return link in self.links
    
    def get_accounts(self) -> List[str]:
        """
        获取交易涉及的所有账户
        
        Returns:
            账户名称列表
        """
        return [posting.account for posting in self.postings]
    
    def get_currencies(self) -> Set[str]:
        """
        获取交易涉及的所有货币
        
        Returns:
            货币集合
        """
        return {posting.currency for posting in self.postings}
    
    def get_total_amount(self, currency: str) -> Decimal:
        """
        获取指定货币的总金额（绝对值之和）
        
        Args:
            currency: 货币代码
            
        Returns:
            总金额
        """
        total = Decimal(0)
        for posting in self.postings:
            if posting.currency == currency:
                total += abs(posting.amount)
        return total
    
    def detect_transaction_type(self) -> TransactionType:
        """
        自动检测交易类型
        
        根据 Posting 涉及的账户类型判断交易类型：
        - 支出：Expenses → Assets/Liabilities
        - 收入：Assets/Liabilities → Income
        - 转账：Assets ↔ Assets 或 Liabilities ↔ Liabilities
        - 其他
        
        Returns:
            交易类型
        """
        accounts = self.get_accounts()
        
        # 提取账户类型（根账户）
        account_types = set()
        for account in accounts:
            root = account.split(":")[0]
            account_types.add(root)
        
        # 检测支出：涉及 Expenses
        if "Expenses" in account_types:
            return TransactionType.EXPENSE
        
        # 检测收入：涉及 Income
        if "Income" in account_types:
            return TransactionType.INCOME
        
        # 检测转账：只涉及资产或负债账户
        if account_types <= {"Assets", "Liabilities"}:
            return TransactionType.TRANSFER
        
        # 检测期初余额：涉及 Equity
        if "Equity" in account_types:
            return TransactionType.OPENING
        
        return TransactionType.OTHER
    
    def is_cleared(self) -> bool:
        """
        判断交易是否已清算
        
        Returns:
            如果标记为已清算则返回 True
        """
        return self.flag == TransactionFlag.CLEARED
    
    def is_pending(self) -> bool:
        """
        判断交易是否待清算
        
        Returns:
            如果标记为待清算则返回 True
        """
        return self.flag == TransactionFlag.PENDING
    
    def mark_as_cleared(self):
        """标记为已清算"""
        self.flag = TransactionFlag.CLEARED
    
    def mark_as_pending(self):
        """标记为待清算"""
        self.flag = TransactionFlag.PENDING
    
    def to_dict(self) -> dict:
        """
        转换为字典格式
        
        Returns:
            字典表示
        """
        return {
            "id": self.id,
            "date": self.date.isoformat(),
            "description": self.description,
            "payee": self.payee,
            "flag": self.flag.value,
            "postings": [posting.to_dict() for posting in self.postings],
            "tags": list(self.tags),
            "links": list(self.links),
            "meta": self.meta,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "transaction_type": self.detect_transaction_type().value,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Transaction":
        """
        从字典创建 Transaction 实体
        
        Args:
            data: 字典数据
            
        Returns:
            Transaction 实体
        """
        return cls(
            id=data.get("id"),
            date=date.fromisoformat(data["date"]) if isinstance(data["date"], str) else data["date"],
            description=data["description"],
            payee=data.get("payee"),
            flag=TransactionFlag(data.get("flag", "*")),
            postings=[Posting.from_dict(p) for p in data.get("postings", [])],
            tags=set(data.get("tags", [])),
            links=set(data.get("links", [])),
            meta=data.get("meta", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
        )
    
    def __repr__(self) -> str:
        """字符串表示"""
        txn_type = self.detect_transaction_type().value
        currencies = ", ".join(sorted(self.get_currencies()))
        return (
            f"<Transaction({self.date.isoformat()}, "
            f"'{self.description}', "
            f"type={txn_type}, "
            f"postings={len(self.postings)}, "
            f"currencies={currencies})>"
        )
