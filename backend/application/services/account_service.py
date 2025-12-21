"""账户应用服务

协调领域服务和仓储，提供面向接口层的高层业务操作。
处理 DTO 转换。
"""
from typing import List, Dict, Optional
from decimal import Decimal
from datetime import datetime

from backend.domain.account.entities import Account, AccountType
from backend.domain.account.repositories import AccountRepository
from backend.domain.account.services import AccountService


class AccountApplicationService:
    """
    账户应用服务
    
    负责：
    - 协调领域服务和仓储
    - DTO 转换（实体 <-> 字典）
    - 提供面向接口层的操作
    """
    
    def __init__(self, account_repository: AccountRepository):
        """
        初始化应用服务
        
        Args:
            account_repository: 账户仓储
        """
        self.account_repository = account_repository
        self.account_service = AccountService(account_repository)
    
    def create_account(
        self,
        name: str,
        account_type: str,
        currencies: Optional[List[str]] = None,
        open_date: Optional[str] = None
    ) -> Dict:
        """
        创建账户
        
        Args:
            name: 账户名称
            account_type: 账户类型（字符串）
            currencies: 支持的货币列表
            open_date: 开户日期（ISO 格式字符串）
            
        Returns:
            账户 DTO
        """
        # 转换账户类型
        acc_type = AccountType.from_string(account_type)
        
        # 转换日期
        open_dt = datetime.fromisoformat(open_date) if open_date else None
        
        # 创建账户
        account = self.account_service.create_account(
            name=name,
            account_type=acc_type,
            currencies=currencies,
            open_date=open_dt
        )
        
        return self._account_to_dto(account)
    
    def get_account(self, account_name: str) -> Optional[Dict]:
        """
        获取账户信息
        
        Args:
            account_name: 账户名称
            
        Returns:
            账户 DTO，不存在返回 None
        """
        account = self.account_repository.find_by_name(account_name)
        return self._account_to_dto(account) if account else None
    
    def get_all_accounts(self, active_only: bool = False) -> List[Dict]:
        """
        获取所有账户
        
        Args:
            active_only: 是否只返回活跃账户
            
        Returns:
            账户 DTO 列表
        """
        if active_only:
            accounts = self.account_repository.find_active_accounts()
        else:
            accounts = self.account_repository.find_all()
        
        return [self._account_to_dto(acc) for acc in accounts]
    
    def get_accounts_by_type(self, account_type: str, active_only: bool = False) -> List[Dict]:
        """
        根据类型获取账户
        
        Args:
            account_type: 账户类型
            active_only: 是否只返回活跃账户
            
        Returns:
            账户 DTO 列表
        """
        acc_type = AccountType.from_string(account_type)
        accounts = self.account_repository.find_by_type(acc_type)
        
        if active_only:
            accounts = [acc for acc in accounts if acc.is_active()]
        
        return [self._account_to_dto(acc) for acc in accounts]
    
    def get_accounts_by_prefix(self, prefix: str) -> List[Dict]:
        """
        根据前缀获取账户
        
        Args:
            prefix: 账户名称前缀
            
        Returns:
            账户 DTO 列表
        """
        accounts = self.account_repository.find_by_prefix(prefix)
        return [self._account_to_dto(acc) for acc in accounts]
    
    def close_account(self, account_name: str, close_date: Optional[str] = None) -> bool:
        """
        关闭账户
        
        Args:
            account_name: 账户名称
            close_date: 关闭日期（ISO 格式字符串）
            
        Returns:
            成功返回 True
        """
        close_dt = datetime.fromisoformat(close_date) if close_date else None
        return self.account_service.close_account(account_name, close_dt)
    
    def get_account_balance(
        self,
        account_name: str,
        currency: Optional[str] = None
    ) -> Dict[str, str]:
        """
        获取账户余额
        
        Args:
            account_name: 账户名称
            currency: 可选，指定货币
            
        Returns:
            余额字典（货币 -> 金额字符串）
        """
        balances = self.account_repository.get_balance(account_name, currency)
        # 转换 Decimal 为字符串
        return {curr: str(amount) for curr, amount in balances.items()}
    
    def get_balances_by_type(
        self,
        account_type: str,
        currency: Optional[str] = None
    ) -> Dict[str, Dict[str, str]]:
        """
        获取指定类型所有账户的余额
        
        Args:
            account_type: 账户类型
            currency: 可选，指定货币
            
        Returns:
            嵌套字典（账户名 -> {货币 -> 金额字符串}）
        """
        acc_type = AccountType.from_string(account_type)
        balances = self.account_repository.get_balances_by_type(acc_type, currency)
        
        # 转换 Decimal 为字符串
        result = {}
        for account_name, account_balances in balances.items():
            result[account_name] = {
                curr: str(amount) for curr, amount in account_balances.items()
            }
        
        return result
    
    def get_account_hierarchy(self, root_account: Optional[str] = None) -> Dict:
        """
        获取账户层级结构
        
        Args:
            root_account: 根账户名称
            
        Returns:
            层级结构字典
        """
        return self.account_service.get_account_hierarchy(root_account)
    
    def get_account_summary(self, account_type: Optional[str] = None) -> Dict:
        """
        获取账户摘要统计
        
        Args:
            account_type: 可选，指定账户类型
            
        Returns:
            摘要统计字典
        """
        acc_type = AccountType.from_string(account_type) if account_type else None
        return self.account_service.get_account_summary(acc_type)
    
    def validate_account_balance(
        self,
        account_name: str,
        required_balance: str,
        currency: str = "CNY"
    ) -> bool:
        """
        验证账户余额是否满足要求
        
        Args:
            account_name: 账户名称
            required_balance: 要求的最小余额（字符串）
            currency: 货币
            
        Returns:
            满足要求返回 True
        """
        required = Decimal(required_balance)
        return self.account_service.validate_account_balance(
            account_name, required, currency
        )
    
    def suggest_account_name(self, account_type: str, category: str) -> str:
        """
        建议账户名称
        
        Args:
            account_type: 账户类型
            category: 分类
            
        Returns:
            建议的账户名称
        """
        acc_type = AccountType.from_string(account_type)
        return self.account_service.suggest_account_name(acc_type, category)
    
    def is_valid_account_name(self, name: str) -> bool:
        """
        验证账户名称是否有效
        
        Args:
            name: 账户名称
            
        Returns:
            有效返回 True
        """
        return self.account_service.is_valid_account_name(name)
    
    def get_child_accounts(self, parent_name: str) -> List[Dict]:
        """
        获取子账户
        
        Args:
            parent_name: 父账户名称
            
        Returns:
            子账户 DTO 列表
        """
        accounts = self.account_repository.get_child_accounts(parent_name)
        return [self._account_to_dto(acc) for acc in accounts]
    
    def get_root_accounts(self) -> List[Dict]:
        """
        获取根账户
        
        Returns:
            根账户 DTO 列表
        """
        accounts = self.account_repository.get_root_accounts()
        return [self._account_to_dto(acc) for acc in accounts]
    
    def _account_to_dto(self, account: Account) -> Dict:
        """
        将账户实体转换为 DTO
        
        Args:
            account: 账户实体
            
        Returns:
            账户 DTO
        """
        return {
            "name": account.name,
            "account_type": account.account_type.value,
            "currencies": list(account.currencies),
            "is_active": account.is_active(),
            "open_date": account.open_date.isoformat() if account.open_date else None,
            "close_date": account.close_date.isoformat() if account.close_date else None,
            "depth": account.get_depth(),
            "parent": account.get_parent_account(),
            "meta": account.meta
        }
