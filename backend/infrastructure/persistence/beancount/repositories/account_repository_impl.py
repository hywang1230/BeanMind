"""账户仓储 Beancount 实现

从 Beancount 文件读取和写入账户数据。
"""
from pathlib import Path
from typing import Optional, List, Dict
from decimal import Decimal
from datetime import datetime

from beancount.core.data import Open, Close
from beancount.parser import printer

from backend.domain.account.entities import Account, AccountType
from backend.domain.account.repositories import AccountRepository
from backend.infrastructure.persistence.beancount.beancount_service import BeancountService


class AccountRepositoryImpl(AccountRepository):
    """
    账户仓储的 Beancount 实现
    
    从 Beancount 账本文件读取账户信息，支持查询余额。
    """
    
    def __init__(self, beancount_service: BeancountService):
        """
        初始化账户仓储
        
        Args:
            beancount_service: Beancount 服务实例
        """
        self.beancount_service = beancount_service
        self._load_accounts()
    
    def _load_accounts(self):
        """从 Beancount 加载所有账户"""
        self._accounts: Dict[str, Account] = {}
        
        for entry in self.beancount_service.entries:
            if isinstance(entry, Open):
                account = self._open_entry_to_account(entry)
                self._accounts[account.name] = account
            elif isinstance(entry, Close):
                # 处理关闭的账户
                if entry.account in self._accounts:
                    self._accounts[entry.account].close_account(
                        datetime.combine(entry.date, datetime.min.time())
                    )
    
    def _open_entry_to_account(self, entry: Open) -> Account:
        """
        将 Beancount Open 条目转换为 Account 实体
        
        Args:
            entry: Beancount Open 条目
            
        Returns:
            Account 实体
        """
        # 从账户名称提取账户类型
        account_type = self._extract_account_type(entry.account)
        
        # 转换日期
        open_date = datetime.combine(entry.date, datetime.min.time())
        
        return Account(
            name=entry.account,
            account_type=account_type,
            currencies=set(entry.currencies) if entry.currencies else set(),
            meta=entry.meta or {},
            open_date=open_date
        )
    
    def _extract_account_type(self, account_name: str) -> AccountType:
        """
        从账户名称提取账户类型
        
        Args:
            account_name: 账户名称（如 "Assets:Bank:Checking"）
            
        Returns:
            账户类型
        """
        root = account_name.split(":")[0]
        return AccountType.from_string(root)
    
    def reload(self):
        """重新加载账户数据"""
        self.beancount_service.reload()
        self._load_accounts()
    
    def find_by_name(self, name: str) -> Optional[Account]:
        """根据账户名称查找账户"""
        return self._accounts.get(name)
    
    def find_all(self) -> List[Account]:
        """获取所有账户"""
        return list(self._accounts.values())
    
    def find_by_type(self, account_type: AccountType) -> List[Account]:
        """根据账户类型查找账户"""
        return [
            acc for acc in self._accounts.values()
            if acc.account_type == account_type
        ]
    
    def find_by_prefix(self, prefix: str) -> List[Account]:
        """根据前缀查找账户"""
        return [
            acc for acc in self._accounts.values()
            if acc.name.startswith(prefix)
        ]
    
    def find_active_accounts(self) -> List[Account]:
        """获取所有活跃账户"""
        return [
            acc for acc in self._accounts.values()
            if acc.is_active()
        ]
    
    def get_balance(self, account_name: str, currency: Optional[str] = None) -> Dict[str, Decimal]:
        """
        获取账户余额
        
        使用 BeancountService 获取实时余额。
        """
        balances = self.beancount_service.get_account_balances(account_name)
        
        if account_name not in balances:
            return {} if currency is None else {currency: Decimal("0")}
        
        account_balances = balances[account_name]
        
        if currency:
            return {currency: account_balances.get(currency, Decimal("0"))}
        
        return account_balances
    
    def get_balances_by_type(
        self, 
        account_type: AccountType, 
        currency: Optional[str] = None
    ) -> Dict[str, Dict[str, Decimal]]:
        """获取指定类型所有账户的余额"""
        accounts = self.find_by_type(account_type)
        result = {}
        
        for acc in accounts:
            balance = self.get_balance(acc.name, currency)
            if balance:  # 只返回有余额的账户
                result[acc.name] = balance
        
        return result
    
    def get_balance_at_date(
        self, 
        account_name: str, 
        date: datetime, 
        currency: Optional[str] = None
    ) -> Dict[str, Decimal]:
        """获取指定日期的账户余额"""
        balances = self.beancount_service.get_account_balances(
            account_name, 
            as_of_date=date.date()
        )
        
        if account_name not in balances:
            return {} if currency is None else {currency: Decimal("0")}
        
        account_balances = balances[account_name]
        
        if currency:
            return {currency: account_balances.get(currency, Decimal("0"))}
        
        return account_balances
    
    def create(self, account: Account) -> Account:
        """
        创建新账户
        
        将账户写入 Beancount 文件。
        """
        if self.exists(account.name):
            raise ValueError(f"账户 '{account.name}' 已存在")
        
        # 构建 Open 指令
        open_entry = Open(
            meta=account.meta or {},
            date=account.open_date.date() if account.open_date else datetime.now().date(),
            account=account.name,
            currencies=list(account.currencies) if account.currencies else None,
            booking=None
        )
        
        # 追加到文件
        with open(self.beancount_service.ledger_path, "a", encoding="utf-8") as f:
            f.write("\n")
            f.write(printer.format_entry(open_entry))
            f.write("\n")
        
        # 重新加载
        self.reload()
        
        return self._accounts.get(account.name, account)
    
    def update(self, account: Account) -> Account:
        """
        更新账户信息
        
        注意：Beancount 不支持直接修改账户。
        如果需要修改账户，需要手动编辑 Beancount 文件。
        """
        if not self.exists(account.name):
            raise ValueError(f"账户 '{account.name}' 不存在")
        
        # 更新内存中的账户
        self._accounts[account.name] = account
        
        # 警告：实际文件未更新
        # 在实际应用中，可能需要重写整个 Beancount 文件
        # 或提供专门的账户修改接口
        
        return account
    
    def delete(self, account_name: str) -> bool:
        """
        删除账户（关闭账户）
        
        在 Beancount 中，删除账户意味着添加 Close 指令。
        """
        if not self.exists(account_name):
            return False
        
        account = self._accounts[account_name]
        
        if not account.is_active():
            # 账户已经关闭
            return True
        
        # 构建 Close 指令
        close_entry = Close(
            meta={},
            date=datetime.now().date(),
            account=account_name
        )
        
        # 追加到文件
        with open(self.beancount_service.ledger_path, "a", encoding="utf-8") as f:
            f.write("\n")
            f.write(printer.format_entry(close_entry))
            f.write("\n")
        
        # 重新加载
        self.reload()
        
        return True
    
    def reopen(self, account_name: str) -> bool:
        """
        重新开启账户（删除关闭记录）
        
        从 Beancount 文件中删除指定账户的 Close 指令。
        """
        if not self.exists(account_name):
            return False
        
        account = self._accounts[account_name]
        
        if account.is_active():
            # 账户未关闭，无需重新开启
            return True
        
        # 读取账本文件，删除 Close 指令
        ledger_path = self.beancount_service.ledger_path
        
        # 遍历所有 beancount 文件找到 Close 指令
        files_to_check = [ledger_path]
        
        # 检查主文件内的 include 语句，添加所有包含的文件
        ledger_dir = Path(ledger_path).parent
        with open(ledger_path, 'r', encoding='utf-8') as f:
            content = f.read()
            import re
            includes = re.findall(r'include\s+"([^"]+)"', content)
            for inc in includes:
                inc_path = ledger_dir / inc
                if inc_path.exists():
                    files_to_check.append(inc_path)
        
        # 在所有文件中查找并删除 Close 指令
        for file_path in files_to_check:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                new_lines = []
                i = 0
                modified = False
                while i < len(lines):
                    line = lines[i]
                    # 检查是否是 Close 指令
                    stripped = line.strip()
                    if stripped.startswith('close') or (len(stripped.split()) >= 3 and 
                        stripped.split()[1] == 'close' and 
                        stripped.split()[2] == account_name):
                        # 匹配格式: 日期 close 账户名
                        parts = stripped.split()
                        if len(parts) >= 3 and parts[1] == 'close' and parts[2] == account_name:
                            modified = True
                            i += 1
                            continue
                    new_lines.append(line)
                    i += 1
                
                if modified:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.writelines(new_lines)
                    break
            except Exception:
                continue
        
        # 重新加载
        self.reload()
        
        return True
    
    def exists(self, account_name: str) -> bool:
        """检查账户是否存在"""
        return account_name in self._accounts
    
    def count(self) -> int:
        """获取账户总数"""
        return len(self._accounts)
    
    def count_by_type(self, account_type: AccountType) -> int:
        """获取指定类型的账户数量"""
        return len(self.find_by_type(account_type))
    
    def get_root_accounts(self) -> List[Account]:
        """获取所有根账户"""
        return [
            acc for acc in self._accounts.values()
            if acc.get_depth() == 1
        ]
    
    def get_child_accounts(self, parent_name: str) -> List[Account]:
        """获取指定账户的直接子账户"""
        return [
            acc for acc in self._accounts.values()
            if acc.get_parent_account() == parent_name
        ]
    
    def get_all_descendants(self, parent_name: str) -> List[Account]:
        """获取指定账户的所有后代账户"""
        return [
            acc for acc in self._accounts.values()
            if acc.name.startswith(parent_name + ":")
        ]
