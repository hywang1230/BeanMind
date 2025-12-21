"""账户领域服务

提供账户相关的业务逻辑和规则验证。
"""
from typing import List, Dict, Optional
from decimal import Decimal
from datetime import datetime

from backend.domain.account.entities import Account, AccountType
from backend.domain.account.repositories import AccountRepository


class AccountService:
    """
    账户领域服务
    
    负责账户相关的核心业务逻辑，包括：
    - 账户创建验证
    - 账户名称格式验证
    - 账户层级管理
    - 业务规则验证
    """
    
    def __init__(self, account_repository: AccountRepository):
        """
        初始化账户服务
        
        Args:
            account_repository: 账户仓储
        """
        self.account_repository = account_repository
    
    def create_account(
        self,
        name: str,
        account_type: AccountType,
        currencies: Optional[List[str]] = None,
        open_date: Optional[datetime] = None
    ) -> Account:
        """
        创建新账户
        
        包含完整的业务规则验证：
        - 账户名称格式验证
        - 账户类型与名称匹配验证
        - 父账户存在性验证
        - 账户重复性检查
        
        Args:
            name: 账户名称
            account_type: 账户类型
            currencies: 支持的货币列表
            open_date: 开户日期
            
        Returns:
            创建的账户实体
            
        Raises:
            ValueError: 如果验证失败
        """
        # 1. 验证账户名称格式
        self._validate_account_name(name)
        
        # 2. 验证账户类型与名称匹配
        self._validate_account_type_match(name, account_type)
        
        # 3. 检查账户是否已存在
        if self.account_repository.exists(name):
            raise ValueError(f"账户 '{name}' 已存在")
        
        # 4. 验证父账户存在（如果不是根账户）
        self._validate_parent_exists(name)
        
        # 5. 创建账户实体
        account = Account(
            name=name,
            account_type=account_type,
            currencies=set(currencies) if currencies else set(),
            open_date=open_date or datetime.now()
        )
        
        # 6. 保存到仓储
        return self.account_repository.create(account)
    
    def _validate_account_name(self, name: str):
        """
        验证账户名称格式
        
        规则：
        - 不能为空
        - 使用冒号分隔的层级结构
        - 每个层级以大写字母开头
        - 允许字母、数字、下划线、中划线
        
        Args:
            name: 账户名称
            
        Raises:
            ValueError: 如果格式无效
        """
        if not name or not name.strip():
            raise ValueError("账户名称不能为空")
        
        parts = name.split(":")
        if len(parts) < 1:
            raise ValueError("账户名称格式无效")
        
        for part in parts:
            if not part:
                raise ValueError("账户名称中不能有空的层级")
            
            # 每个部分应以大写字母开头
            if not part[0].isupper():
                raise ValueError(f"账户层级 '{part}' 必须以大写字母开头")
            
            # 允许字母、数字、下划线、中划线
            if not all(c.isalnum() or c in ('_', '-') for c in part):
                raise ValueError(f"账户层级 '{part}' 包含无效字符")
    
    def _validate_account_type_match(self, name: str, account_type: AccountType):
        """
        验证账户类型与名称匹配
        
        Args:
            name: 账户名称
            account_type: 账户类型
            
        Raises:
            ValueError: 如果不匹配
        """
        root = name.split(":")[0]
        if root != account_type.value:
            raise ValueError(
                f"账户名称 '{name}' 的根账户 '{root}' 与账户类型 '{account_type.value}' 不匹配"
            )
    
    def _validate_parent_exists(self, name: str):
        """
        验证父账户存在
        
        Args:
            name: 账户名称
            
        Raises:
            ValueError: 如果父账户不存在
        """
        parts = name.split(":")
        if len(parts) <= 1:
            # 根账户，无需验证
            return
        
        # 检查父账户
        parent_name = ":".join(parts[:-1])
        if not self.account_repository.exists(parent_name):
            raise ValueError(f"父账户 '{parent_name}' 不存在")
    
    def close_account(self, account_name: str, close_date: Optional[datetime] = None) -> bool:
        """
        关闭账户
        
        业务规则：
        - 账户必须存在
        - 账户必须处于活跃状态
        - 如果有子账户，子账户也必须先关闭
        
        Args:
            account_name: 账户名称
            close_date: 关闭日期
            
        Returns:
            成功关闭返回 True
            
        Raises:
            ValueError: 如果验证失败
        """
        # 1. 检查账户存在
        account = self.account_repository.find_by_name(account_name)
        if not account:
            raise ValueError(f"账户 '{account_name}' 不存在")
        
        # 2. 检查账户状态
        if not account.is_active():
            raise ValueError(f"账户 '{account_name}' 已经关闭")
        
        # 3. 检查是否有活跃的子账户
        children = self.account_repository.get_child_accounts(account_name)
        active_children = [c for c in children if c.is_active()]
        if active_children:
            child_names = ", ".join([c.name for c in active_children])
            raise ValueError(f"账户 '{account_name}' 有活跃的子账户，请先关闭: {child_names}")
        
        # 4. 关闭账户
        return self.account_repository.delete(account_name)
    
    def get_account_hierarchy(self, root_account: Optional[str] = None) -> Dict:
        """
        获取账户层级结构
        
        Args:
            root_account: 根账户名称，如果为 None 则返回所有账户
            
        Returns:
            层级结构字典
        """
        if root_account:
            accounts = self.account_repository.get_all_descendants(root_account)
            root = self.account_repository.find_by_name(root_account)
            if root:
                accounts.insert(0, root)
        else:
            accounts = self.account_repository.find_all()
        
        # 构建层级结构
        hierarchy = {}
        for account in accounts:
            self._add_to_hierarchy(hierarchy, account)
        
        return hierarchy
    
    def _add_to_hierarchy(self, hierarchy: Dict, account: Account):
        """
        将账户添加到层级结构
        
        Args:
            hierarchy: 层级结构字典
            account: 账户实体
        """
        parts = account.name.split(":")
        current = hierarchy
        
        for i, part in enumerate(parts):
            if part not in current:
                current[part] = {
                    "_account": account if i == len(parts) - 1 else None,
                    "_children": {}
                }
            
            if i == len(parts) - 1:
                current[part]["_account"] = account
            else:
                current = current[part]["_children"]
    
    def validate_account_balance(
        self,
        account_name: str,
        required_balance: Decimal,
        currency: str = "CNY"
    ) -> bool:
        """
        验证账户余额是否满足要求
        
        Args:
            account_name: 账户名称
            required_balance: 要求的最小余额
            currency: 货币
            
        Returns:
            满足要求返回 True
        """
        balance = self.account_repository.get_balance(account_name, currency)
        current_balance = balance.get(currency, Decimal("0"))
        return current_balance >= required_balance
    
    def get_account_summary(self, account_type: Optional[AccountType] = None) -> Dict:
        """
        获取账户摘要信息
        
        Args:
            account_type: 可选，指定账户类型
            
        Returns:
            摘要信息字典，包含账户数量、余额统计等
        """
        if account_type:
            accounts = self.account_repository.find_by_type(account_type)
        else:
            accounts = self.account_repository.find_all()
        
        active_accounts = [acc for acc in accounts if acc.is_active()]
        closed_accounts = [acc for acc in accounts if not acc.is_active()]
        
        summary = {
            "total_count": len(accounts),
            "active_count": len(active_accounts),
            "closed_count": len(closed_accounts),
            "by_type": {}
        }
        
        # 按类型统计
        for acc_type in AccountType:
            type_accounts = [acc for acc in accounts if acc.account_type == acc_type]
            summary["by_type"][acc_type.value] = {
                "count": len(type_accounts),
                "active": len([a for a in type_accounts if a.is_active()])
            }
        
        return summary
    
    def suggest_account_name(self, account_type: AccountType, category: str) -> str:
        """
        建议账户名称
        
        根据账户类型和分类建议合适的账户名称。
        
        Args:
            account_type: 账户类型
            category: 分类
            
        Returns:
            建议的账户名称
        """
        # 确保分类首字母大写
        category_parts = category.split(":")
        capitalized_parts = [part.capitalize() for part in category_parts]
        category = ":".join(capitalized_parts)
        
        # 构建账户名称
        suggested_name = f"{account_type.value}:{category}"
        
        return suggested_name
    
    def is_valid_account_name(self, name: str) -> bool:
        """
        检查账户名称是否有效
        
        Args:
            name: 账户名称
            
        Returns:
            有效返回 True
        """
        try:
            self._validate_account_name(name)
            return True
        except ValueError:
            return False
