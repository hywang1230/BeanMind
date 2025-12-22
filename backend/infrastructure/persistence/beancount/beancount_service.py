"""Beancount 服务

封装 Beancount 账本操作
"""
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, date
from decimal import Decimal

from beancount import loader
from beancount.core import data, amount
from beancount.core.data import Open, Transaction, Posting, TxnPosting
from beancount.ops import summarize
from beancount.parser import printer


class BeancountService:
    """Beancount 账本服务"""
    
    def __init__(self, ledger_path: Path | str):
        """
        初始化 Beancount 服务
        
        Args:
            ledger_path: 账本文件路径
        """
        self.ledger_path = Path(ledger_path)
        self.entries = []
        self.errors = []
        self.options = {}
        
        # 加载账本
        self.reload()
    
    def reload(self) -> None:
        """重新加载账本文件"""
        if not self.ledger_path.exists():
            raise FileNotFoundError(f"Ledger file not found: {self.ledger_path}")
        
        self.entries, self.errors, self.options = loader.load_file(str(self.ledger_path))
        
        if self.errors:
            # 记录错误但不抛出异常
            print(f"⚠️  Beancount parsing warnings: {len(self.errors)} errors")
            for error in self.errors[:5]:  # 只显示前5个错误
                print(f"  - {error}")
    
    def get_accounts(self) -> List[Dict[str, any]]:
        """
        获取所有账户列表
        
        Returns:
            账户列表，包含账户名称、类型、开立日期等信息
        """
        accounts = []
        
        for entry in self.entries:
            if isinstance(entry, Open):
                account_info = {
                    "name": entry.account,
                    "currencies": list(entry.currencies) if entry.currencies else [],
                    "open_date": entry.date.isoformat(),
                    "meta": entry.meta or {},
                }
                accounts.append(account_info)
        
        return accounts
    
    def get_account_balances(self, account_name: Optional[str] = None, 
                            as_of_date: Optional[date] = None) -> Dict[str, Dict[str, Decimal]]:
        """
        获取账户余额
        
        Args:
            account_name: 账户名称，如果为 None 则返回所有账户
            as_of_date: 截止日期，如果为 None 则使用当前日期
        
        Returns:
            账户余额字典 {账户名: {币种: 余额}}
        """
        if as_of_date is None:
            as_of_date = date.today()
        
        # 过滤到指定日期的 entries
        filtered_entries = [
            entry for entry in self.entries
            if entry.date <= as_of_date
        ]
        
        # 使用 Beancount 的 summarize 功能计算余额
        from beancount.core import realization
        real_root = realization.realize(filtered_entries)
        
        result = {}
        
        def process_node(node):
            """递归处理树节点"""
            if hasattr(node, 'account') and node.account:
                # 如果指定了账户但不匹配，继续遍历子节点
                if account_name and node.account != account_name:
                    if hasattr(node, '__iter__'):
                        for child in node.values():
                            process_node(child)
                    return
                
                # 获取此账户的余额
                if hasattr(node, 'balance') and not node.balance.is_empty():
                    balances = {}
                    for pos in node.balance:
                        balances[pos.units.currency] = pos.units.number
                    
                    if balances:  # 只返回有余额的账户
                        result[node.account] = balances
            
            # 递归处理子节点（RealAccount 是一个字典）
            if hasattr(node, '__iter__'):
                for child in node.values():
                    process_node(child)
        
        process_node(real_root)
        return result
    
    def get_balance(self, account_name: str, currency: str = "CNY", 
                   as_of_date: Optional[date] = None) -> Decimal:
        """
        获取指定账户的指定币种余额
        
        Args:
            account_name: 账户名称
            currency: 币种
            as_of_date: 截止日期
        
        Returns:
            余额
        """
        balances = self.get_account_balances(account_name, as_of_date)
        
        if account_name not in balances:
            return Decimal(0)
        
        return balances[account_name].get(currency, Decimal(0))
    
    def append_transaction(self, transaction_data: Dict) -> str:
        """
        追加交易到账本文件
        
        Args:
            transaction_data: 交易数据，格式为:
                {
                    "date": "2025-01-15",
                    "description": "午餐",
                    "payee": "餐厅",
                    "postings": [
                        {"account": "Expenses:Food:Dining", "amount": 45.0, "currency": "CNY"},
                        {"account": "Assets:Cash:Wallet", "amount": -45.0, "currency": "CNY"}
                    ],
                    "tags": ["lunch", "dining"]
                }
        
        Returns:
            交易 ID（基于日期和描述生成）
        """
        # 构建 Beancount Transaction
        txn_date = datetime.strptime(transaction_data["date"], "%Y-%m-%d").date()
        
        postings = []
        for posting_data in transaction_data["postings"]:
            posting = Posting(
                account=posting_data["account"],
                units=amount.Amount(
                    Decimal(str(posting_data["amount"])),
                    posting_data["currency"]
                ),
                cost=None,
                price=None,
                flag=None,
                meta={}
            )
            postings.append(posting)
        
        # 创建交易
        txn = Transaction(
            meta={},
            date=txn_date,
            flag="*",  # 已清算标记
            payee=transaction_data.get("payee", ""),
            narration=transaction_data["description"],
            tags=set(transaction_data.get("tags", [])),
            links=set(),
            postings=postings
        )
        
        # 追加到文件
        with open(self.ledger_path, "a", encoding="utf-8") as f:
            f.write("\n")
            f.write(printer.format_entry(txn))
            f.write("\n")
        
        # 重新加载账本
        self.reload()
        
        # 生成交易 ID
        transaction_id = f"{txn_date.isoformat()}_{transaction_data['description']}"
        return transaction_id
    
    def get_transactions(self, start_date: Optional[date] = None,
                        end_date: Optional[date] = None,
                        account: Optional[str] = None) -> List[Dict]:
        """
        获取交易列表
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            account: 账户过滤
        
        Returns:
            交易列表
        """
        transactions = []
        
        for entry in self.entries:
            if not isinstance(entry, Transaction):
                continue
            
            # 日期过滤
            if start_date and entry.date < start_date:
                continue
            if end_date and entry.date > end_date:
                continue
            
            # 账户过滤
            if account:
                accounts_in_txn = [p.account for p in entry.postings]
                if account not in accounts_in_txn:
                    continue
            
            # 构建交易数据
            txn_data = {
                "date": entry.date.isoformat(),
                "description": entry.narration,
                "payee": entry.payee or "",
                "flag": entry.flag,
                "tags": list(entry.tags) if entry.tags else [],
                "postings": [
                    {
                        "account": p.account,
                        "amount": float(p.units.number),
                        "currency": p.units.currency,
                    }
                    for p in entry.postings
                ]
            }
            transactions.append(txn_data)
        
        return transactions
    
    def get_exchange_rate(
        self, 
        from_currency: str, 
        to_currency: str, 
        as_of_date: Optional[date] = None
    ) -> Optional[Decimal]:
        """
        获取汇率
        
        从 Beancount 的 price 指令中获取指定日期的最新汇率。
        
        Args:
            from_currency: 源货币（如 USD）
            to_currency: 目标货币（如 CNY）
            as_of_date: 截止日期，如果为 None 则使用当前日期
        
        Returns:
            汇率，如果找不到则返回 None
            
        Example:
            get_exchange_rate("USD", "CNY") -> Decimal("7.13")
            表示 1 USD = 7.13 CNY
        """
        from beancount.core.data import Price
        
        if as_of_date is None:
            as_of_date = date.today()
        
        # 收集所有符合条件的价格指令
        matching_prices = []
        
        for entry in self.entries:
            if not isinstance(entry, Price):
                continue
            
            # 跳过超过截止日期的价格
            if entry.date > as_of_date:
                continue
            
            # 检查是否匹配 from_currency -> to_currency
            if entry.currency == from_currency and entry.amount.currency == to_currency:
                matching_prices.append((entry.date, entry.amount.number))
            # 检查反向汇率 to_currency -> from_currency
            elif entry.currency == to_currency and entry.amount.currency == from_currency:
                # 反向汇率需要取倒数
                if entry.amount.number != 0:
                    matching_prices.append((entry.date, Decimal(1) / entry.amount.number))
        
        if not matching_prices:
            return None
        
        # 按日期排序，取最新的汇率
        matching_prices.sort(key=lambda x: x[0], reverse=True)
        return matching_prices[0][1]
    
    def get_all_exchange_rates(
        self, 
        to_currency: str = "CNY",
        as_of_date: Optional[date] = None
    ) -> Dict[str, Decimal]:
        """
        获取所有货币到目标货币的最新汇率
        
        Args:
            to_currency: 目标货币（默认 CNY）
            as_of_date: 截止日期
        
        Returns:
            汇率字典 {货币代码: 汇率}
            
        Example:
            {"USD": Decimal("7.13"), "EUR": Decimal("7.80")}
        """
        from beancount.core.data import Price
        
        if as_of_date is None:
            as_of_date = date.today()
        
        # 收集所有货币
        currencies = set()
        for entry in self.entries:
            if isinstance(entry, Price):
                currencies.add(entry.currency)
                currencies.add(entry.amount.currency)
        
        # 获取每种货币到目标货币的汇率
        rates = {}
        rates[to_currency] = Decimal(1)  # 目标货币自身汇率为1
        
        for currency in currencies:
            if currency == to_currency:
                continue
            rate = self.get_exchange_rate(currency, to_currency, as_of_date)
            if rate:
                rates[currency] = rate
        
        return rates
    
    def get_year_file_path(self, year: int) -> Path:
        """
        获取指定年份的交易文件路径
        
        Args:
            year: 年份（如 2025）
            
        Returns:
            年份对应的文件路径（如 /path/to/ledger/transactions_2025.beancount）
        """
        return self.ledger_path.parent / f"transactions_{year}.beancount"
    
    def ensure_year_file(self, year: int) -> Path:
        """
        确保年份对应的交易文件存在，并在 main.beancount 中被引用
        
        如果文件不存在，则创建一个带有注释头的空文件，
        并在 main.beancount 中添加 include 指令。
        
        Args:
            year: 年份（如 2025）
            
        Returns:
            年份对应的文件路径
        """
        year_file = self.get_year_file_path(year)
        
        if not year_file.exists():
            # 创建年份文件，添加注释头
            with open(year_file, "w", encoding="utf-8") as f:
                f.write(f"; {year} 年度交易记录\n")
                f.write(f"; 创建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("\n")
            
            # 在 main.beancount 中添加 include 指令
            self._add_include_to_main(year_file.name)
        
        return year_file
    
    def _add_include_to_main(self, filename: str) -> None:
        """
        在 main.beancount 中添加 include 指令
        
        Args:
            filename: 要包含的文件名
        """
        include_line = f'include "{filename}"'
        
        # 读取 main.beancount 内容
        with open(self.ledger_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 检查是否已经包含该文件
        if include_line in content:
            return
        
        # 查找现有的 include 部分，将新的 include 添加到其中
        lines = content.split("\n")
        insert_index = -1
        
        # 找到最后一个 include 语句的位置
        for i, line in enumerate(lines):
            if line.strip().startswith("include "):
                insert_index = i + 1
        
        if insert_index == -1:
            # 没有现有的 include，在文件开头添加
            lines.insert(0, include_line)
        else:
            # 在最后一个 include 之后添加
            lines.insert(insert_index, include_line)
        
        # 写回文件
        with open(self.ledger_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))


