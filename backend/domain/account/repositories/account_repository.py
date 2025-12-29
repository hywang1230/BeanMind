"""账户仓储接口

定义账户数据访问的抽象接口。
遵循仓储模式，不包含具体实现。
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict
from decimal import Decimal
from datetime import datetime

from backend.domain.account.entities import Account, AccountType


class AccountRepository(ABC):
    """
    账户仓储接口
    
    定义账户数据访问的抽象方法。
    具体实现可能从 Beancount 文件、数据库或其他数据源读取。
    """
    
    @abstractmethod
    def find_by_name(self, name: str) -> Optional[Account]:
        """
        根据账户名称查找账户
        
        Args:
            name: 完整的账户名称（如 "Assets:Bank:Checking"）
            
        Returns:
            找到的账户实体，不存在则返回 None
        """
        pass
    
    @abstractmethod
    def find_all(self) -> List[Account]:
        """
        获取所有账户
        
        Returns:
            所有账户的列表
        """
        pass
    
    @abstractmethod
    def find_by_type(self, account_type: AccountType) -> List[Account]:
        """
        根据账户类型查找账户
        
        Args:
            account_type: 账户类型
            
        Returns:
            指定类型的所有账户列表
        """
        pass
    
    @abstractmethod
    def find_by_prefix(self, prefix: str) -> List[Account]:
        """
        根据前缀查找账户
        
        Args:
            prefix: 账户名称前缀（如 "Assets:Bank"）
            
        Returns:
            匹配前缀的所有账户列表
        """
        pass
    
    @abstractmethod
    def find_active_accounts(self) -> List[Account]:
        """
        获取所有活跃账户（未关闭的账户）
        
        Returns:
            所有活跃账户列表
        """
        pass
    
    @abstractmethod
    def get_balance(self, account_name: str, currency: Optional[str] = None) -> Dict[str, Decimal]:
        """
        获取账户余额
        
        Args:
            account_name: 账户名称
            currency: 可选，指定货币。如果为 None，返回所有货币的余额
            
        Returns:
            余额字典，键为货币代码，值为余额金额
            如果指定了货币，则只返回该货币的余额
            
        Example:
            {"CNY": Decimal("1000.00"), "USD": Decimal("100.00")}
        """
        pass
    
    @abstractmethod
    def get_balances_by_type(self, account_type: AccountType, currency: Optional[str] = None) -> Dict[str, Dict[str, Decimal]]:
        """
        获取指定类型所有账户的余额
        
        Args:
            account_type: 账户类型
            currency: 可选，指定货币
            
        Returns:
            嵌套字典，外层键为账户名称，内层键为货币代码，值为余额
            
        Example:
            {
                "Assets:Bank:Checking": {"CNY": Decimal("1000.00")},
                "Assets:Cash": {"CNY": Decimal("500.00"), "USD": Decimal("100.00")}
            }
        """
        pass
    
    @abstractmethod
    def get_balance_at_date(
        self, 
        account_name: str, 
        date: datetime, 
        currency: Optional[str] = None
    ) -> Dict[str, Decimal]:
        """
        获取指定日期的账户余额
        
        Args:
            account_name: 账户名称
            date: 查询日期
            currency: 可选，指定货币
            
        Returns:
            指定日期的余额字典
        """
        pass
    
    @abstractmethod
    def create(self, account: Account) -> Account:
        """
        创建新账户
        
        Args:
            account: 账户实体
            
        Returns:
            创建后的账户实体
            
        Raises:
            ValueError: 如果账户已存在
        """
        pass
    
    @abstractmethod
    def update(self, account: Account) -> Account:
        """
        更新账户信息
        
        Args:
            account: 账户实体
            
        Returns:
            更新后的账户实体
            
        Raises:
            ValueError: 如果账户不存在
        """
        pass
    
    @abstractmethod
    def delete(self, account_name: str) -> bool:
        """
        删除账户（通常是关闭账户）
        
        Args:
            account_name: 账户名称
            
        Returns:
            成功删除返回 True，账户不存在返回 False
        """
        pass
    
    @abstractmethod
    def reopen(self, account_name: str) -> bool:
        """
        重新开启账户（删除关闭记录）
        
        Args:
            account_name: 账户名称
            
        Returns:
            成功重新开启返回 True，账户不存在或未关闭返回 False
        """
        pass
    
    @abstractmethod
    def exists(self, account_name: str) -> bool:
        """
        检查账户是否存在
        
        Args:
            account_name: 账户名称
            
        Returns:
            存在返回 True，否则返回 False
        """
        pass
    
    @abstractmethod
    def count(self) -> int:
        """
        获取账户总数
        
        Returns:
            账户总数
        """
        pass
    
    @abstractmethod
    def count_by_type(self, account_type: AccountType) -> int:
        """
        获取指定类型的账户数量
        
        Args:
            account_type: 账户类型
            
        Returns:
            指定类型的账户数量
        """
        pass
    
    @abstractmethod
    def get_root_accounts(self) -> List[Account]:
        """
        获取所有根账户（顶层账户）
        
        Returns:
            所有根账户列表（通常是5个：Assets, Liabilities, Equity, Income, Expenses）
        """
        pass
    
    @abstractmethod
    def get_child_accounts(self, parent_name: str) -> List[Account]:
        """
        获取指定账户的直接子账户
        
        Args:
            parent_name: 父账户名称
            
        Returns:
            直接子账户列表
        """
        pass
    
    @abstractmethod
    def get_all_descendants(self, parent_name: str) -> List[Account]:
        """
        获取指定账户的所有后代账户（递归）
        
        Args:
            parent_name: 父账户名称
            
        Returns:
            所有后代账户列表
        """
        pass
