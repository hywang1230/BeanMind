"""账户领域实体

定义账户的核心属性和业务规则。
遵循 DDD 原则，不包含任何基础设施依赖。
"""
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Set


class AccountType(str, Enum):
    """
    账户类型枚举
    
    遵循 Beancount 的账户分类系统。
    """
    ASSETS = "Assets"          # 资产账户
    LIABILITIES = "Liabilities"  # 负债账户
    EQUITY = "Equity"          # 权益账户
    INCOME = "Income"          # 收入账户
    EXPENSES = "Expenses"      # 支出账户
    
    @classmethod
    def from_string(cls, value: str) -> "AccountType":
        """
        从字符串转换为账户类型
        
        Args:
            value: 字符串值（如 "Assets"、"Liabilities" 等）
            
        Returns:
            对应的账户类型枚举
            
        Raises:
            ValueError: 如果值不是有效的账户类型
        """
        value = value.strip()
        for account_type in cls:
            if account_type.value == value:
                return account_type
        raise ValueError(f"无效的账户类型: {value}")
    
    def is_balance_sheet_account(self) -> bool:
        """
        判断是否为资产负债表账户
        
        资产负债表账户包括：Assets, Liabilities, Equity
        """
        return self in {self.ASSETS, self.LIABILITIES, self.EQUITY}
    
    def is_income_statement_account(self) -> bool:
        """
        判断是否为损益表账户
        
        损益表账户包括：Income, Expenses
        """
        return self in {self.INCOME, self.EXPENSES}


@dataclass
class Account:
    """
    账户领域实体
    
    表示 Beancount 中的一个账户。
    账户名称遵循层级结构，如：Assets:Bank:Checking
    """
    
    # 必需字段
    name: str = field(metadata={"description": "账户完整名称（如 Assets:Bank:Checking）"})
    account_type: AccountType = field(metadata={"description": "账户类型"})
    
    # 可选字段
    currencies: Set[str] = field(default_factory=set, metadata={"description": "支持的货币集合"})
    meta: dict = field(default_factory=dict, metadata={"description": "账户元数据"})
    open_date: Optional[datetime] = field(default=None, metadata={"description": "账户开户日期"})
    close_date: Optional[datetime] = field(default=None, metadata={"description": "账户关闭日期"})
    
    # 审计字段（可选，用于跟踪）
    created_at: Optional[datetime] = field(default=None)
    updated_at: Optional[datetime] = field(default=None)
    
    def __post_init__(self):
        """初始化后验证"""
        self._validate()
    
    def _validate(self):
        """验证账户数据"""
        # 验证账户名称
        if not self.name or not self.name.strip():
            raise ValueError("账户名称不能为空")
        
        # 验证账户名称格式
        if not self._is_valid_account_name(self.name):
            raise ValueError(f"无效的账户名称格式: {self.name}")
        
        # 验证账户类型与名称一致
        if not self.name.startswith(self.account_type.value):
            raise ValueError(
                f"账户名称 '{self.name}' 与账户类型 '{self.account_type.value}' 不匹配"
            )
        
        # 验证关闭日期
        if self.open_date and self.close_date:
            if self.close_date < self.open_date:
                raise ValueError("账户关闭日期不能早于开户日期")
    
    def _is_valid_account_name(self, name: str) -> bool:
        """
        验证账户名称格式
        
        账户名称应遵循：
        - 使用冒号分隔的层级结构
        - 至少两个层级
        - 第一层级必须是有效的账户类型（Assets, Liabilities, Equity, Income, Expenses）
        - 第二层必须以大写字母开头
        - 允许中文、字母、数字、下划线、中划线
        """
        if not name:
            return False
        
        parts = name.split(":")
        if len(parts) < 2:
            return False
        
        # 验证第一层级是有效的账户类型
        valid_root_types = {"Assets", "Liabilities", "Equity", "Income", "Expenses"}
        if parts[0] not in valid_root_types:
            return False
        
        # 验证第二层级是否以大写字母开头
        if not parts[1] or not parts[1][0].isupper():
            return False
        
        # 允许中文、字母、数字、下划线、中划线的正则表达式
        valid_pattern = re.compile(r'^[\u4e00-\u9fa5a-zA-Z0-9_-]+$')
        
        for part in parts:
            if not part:
                return False
            # 验证每一部分是否符合允许的字符规则
            if not valid_pattern.match(part):
                return False
        
        return True
    
    def is_active(self) -> bool:
        """
        判断账户是否处于活跃状态
        
        Returns:
            如果账户未关闭则返回 True
        """
        return self.close_date is None
    
    def get_root_account(self) -> str:
        """
        获取根账户名称
        
        Returns:
            根账户名称（即账户类型，如 "Assets"）
        """
        return self.name.split(":")[0]
    
    def get_account_levels(self) -> List[str]:
        """
        获取账户层级列表
        
        Returns:
            账户层级列表，如 ["Assets", "Bank", "Checking"]
        """
        return self.name.split(":")
    
    def get_parent_account(self) -> Optional[str]:
        """
        获取父账户名称
        
        Returns:
            父账户名称，如果是根账户则返回 None
        """
        parts = self.name.split(":")
        if len(parts) <= 1:
            return None
        return ":".join(parts[:-1])
    
    def get_depth(self) -> int:
        """
        获取账户层级深度
        
        Returns:
            账户层级深度（根账户为1）
        """
        return len(self.name.split(":"))
    
    def add_currency(self, currency: str):
        """
        添加支持的货币
        
        Args:
            currency: 货币代码（如 "CNY", "USD"）
        """
        if not currency or not currency.strip():
            raise ValueError("货币代码不能为空")
        
        currency = currency.strip().upper()
        if len(currency) != 3:
            raise ValueError(f"无效的货币代码: {currency}")
        
        self.currencies.add(currency)
    
    def supports_currency(self, currency: str) -> bool:
        """
        判断账户是否支持指定货币
        
        Args:
            currency: 货币代码
            
        Returns:
            如果支持则返回 True
        """
        return currency.upper() in self.currencies
    
    def close_account(self, close_date: datetime):
        """
        关闭账户
        
        Args:
            close_date: 关闭日期
        """
        if self.open_date and close_date < self.open_date:
            raise ValueError("账户关闭日期不能早于开户日期")
        
        self.close_date = close_date
    
    def to_dict(self) -> dict:
        """
        转换为字典格式
        
        Returns:
            字典表示
        """
        return {
            "name": self.name,
            "account_type": self.account_type.value,
            "currencies": list(self.currencies),
            "meta": self.meta,
            "open_date": self.open_date.isoformat() if self.open_date else None,
            "close_date": self.close_date.isoformat() if self.close_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Account":
        """
        从字典创建账户实体
        
        Args:
            data: 字典数据
            
        Returns:
            账户实体
        """
        account_type = AccountType.from_string(data["account_type"]) if isinstance(data.get("account_type"), str) else data.get("account_type")
        
        return cls(
            name=data["name"],
            account_type=account_type,
            currencies=set(data.get("currencies", [])),
            meta=data.get("meta", {}),
            open_date=datetime.fromisoformat(data["open_date"]) if data.get("open_date") else None,
            close_date=datetime.fromisoformat(data["close_date"]) if data.get("close_date") else None,
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
        )
    
    def __repr__(self) -> str:
        """字符串表示"""
        status = "active" if self.is_active() else "closed"
        currencies_str = ",".join(sorted(self.currencies)) if self.currencies else "none"
        return f"<Account({self.name}, type={self.account_type.value}, currencies={currencies_str}, status={status})>"
