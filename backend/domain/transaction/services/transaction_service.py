"""交易领域服务

提供交易相关的业务逻辑和规则验证。
"""
from typing import List, Optional, Dict
from decimal import Decimal
from datetime import date

from backend.domain.transaction.entities import Transaction, Posting, TransactionType
from backend.domain.transaction.repositories import TransactionRepository
from backend.domain.account.repositories import AccountRepository


class TransactionService:
    """
    交易领域服务
    
    负责交易相关的核心业务逻辑，包括：
    - 交易创建验证
    - 交易类型判断
    - 借贷平衡验证
    - 账户存在性检查
    - 业务规则验证
    """
    
    def __init__(
        self,
        transaction_repository: TransactionRepository,
        account_repository: AccountRepository
    ):
        """
        初始化交易服务
        
        Args:
            transaction_repository: 交易仓储
            account_repository: 账户仓储
        """
        self.transaction_repository = transaction_repository
        self.account_repository = account_repository
    
    def create_transaction(
        self,
        txn_date: date,
        description: str,
        postings: List[Posting],
        payee: Optional[str] = None,
        tags: Optional[List[str]] = None,
        links: Optional[List[str]] = None,
        user_id: Optional[str] = None
    ) -> Transaction:
        """
        创建新交易
        
        包含完整的业务规则验证：
        - 记账分录数量验证
        - 借贷平衡验证
        - 账户存在性验证
        - 金额有效性验证
        
        Args:
            txn_date: 交易日期
            description: 交易描述
            postings: 记账分录列表
            payee: 收付款方
            tags: 标签列表
            links: 链接列表
            user_id: 用户 ID
            
        Returns:
            创建的交易实体
            
        Raises:
            ValueError: 如果验证失败
        """
        # 1. 验证基本信息
        self._validate_basic_info(txn_date, description)
        
        # 2. 验证记账分录
        self._validate_postings(postings)
        
        # 3. 验证借贷平衡
        self._validate_balance(postings)
        
        # 4. 验证账户存在性
        self._validate_accounts_exist(postings)
        
        # 5. 创建交易实体
        transaction = Transaction(
            date=txn_date,
            description=description,
            postings=postings,
            payee=payee,
            tags=set(tags) if tags else set(),
            links=set(links) if links else set()
        )
        
        # 6. 保存到仓储
        return self.transaction_repository.create(transaction, user_id=user_id)
    
    def _validate_basic_info(self, txn_date: date, description: str):
        """
        验证交易基本信息
        
        Args:
            txn_date: 交易日期
            description: 交易描述
            
        Raises:
            ValueError: 如果验证失败
        """
        if not txn_date:
            raise ValueError("交易日期不能为空")
        
        if not description or not description.strip():
            raise ValueError("交易描述不能为空")
        
        # 可以添加更多验证，如日期不能是未来日期等
        # if txn_date > date.today():
        #     raise ValueError("交易日期不能是未来日期")
    
    def _validate_postings(self, postings: List[Posting]):
        """
        验证记账分录
        
        Args:
            postings: 记账分录列表
            
        Raises:
            ValueError: 如果验证失败
        """
        if not postings or len(postings) < 2:
            raise ValueError("交易至少需要两个记账分录（复式记账原则）")
        
        # 验证每个 posting 的金额不为零
        for i, posting in enumerate(postings):
            if posting.amount == Decimal("0"):
                raise ValueError(f"第 {i+1} 个记账分录的金额不能为零")
    
    def _validate_balance(self, postings: List[Posting]):
        """
        验证借贷平衡
        
        Args:
            postings: 记账分录列表
            
        Raises:
            ValueError: 如果不平衡
        """
        # 按货币分组计算总和
        balances: Dict[str, Decimal] = {}
        
        for posting in postings:
            currency = posting.currency
            if currency not in balances:
                balances[currency] = Decimal("0")
            balances[currency] += posting.amount
        
        # 检查每种货币是否平衡（允许小误差）
        unbalanced_currencies = []
        for currency, total in balances.items():
            if abs(total) > Decimal("0.01"):  # 允许 0.01 的误差
                unbalanced_currencies.append(f"{currency}: {total}")
        
        if unbalanced_currencies:
            raise ValueError(
                f"交易不平衡，以下货币的借贷不相等: {', '.join(unbalanced_currencies)}"
            )
    
    def _validate_accounts_exist(self, postings: List[Posting]):
        """
        验证账户存在性
        
        Args:
            postings: 记账分录列表
            
        Raises:
            ValueError: 如果账户不存在
        """
        for posting in postings:
            if not self.account_repository.exists(posting.account):
                raise ValueError(f"账户 '{posting.account}' 不存在")
    
    def validate_transaction(self, transaction: Transaction) -> bool:
        """
        验证交易是否有效
        
        Args:
            transaction: 交易实体
            
        Returns:
            有效返回 True
            
        Raises:
            ValueError: 如果验证失败
        """
        self._validate_basic_info(transaction.date, transaction.description)
        self._validate_postings(transaction.postings)
        self._validate_balance(transaction.postings)
        self._validate_accounts_exist(transaction.postings)
        return True
    
    def detect_transaction_type(self, transaction: Transaction) -> TransactionType:
        """
        检测交易类型
        
        根据涉及的账户类型判断交易类型：
        - 支出：Expenses → Assets/Liabilities
        - 收入：Assets/Liabilities → Income
        - 转账：Assets ↔ Assets 或 Liabilities ↔ Liabilities
        - 期初余额：涉及 Equity
        - 其他
        
        Args:
            transaction: 交易实体
            
        Returns:
            交易类型
        """
        return transaction.detect_transaction_type()
    
    def is_balanced(self, transaction: Transaction) -> bool:
        """
        判断交易是否平衡
        
        Args:
            transaction: 交易实体
            
        Returns:
            平衡返回 True
        """
        try:
            self._validate_balance(transaction.postings)
            return True
        except ValueError:
            return False
    
    def get_involved_accounts(self, transaction: Transaction) -> List[str]:
        """
        获取交易涉及的所有账户
        
        Args:
            transaction: 交易实体
            
        Returns:
            账户名称列表
        """
        return transaction.get_accounts()
    
    def calculate_transaction_amount(
        self,
        transaction: Transaction,
        currency: str = "CNY"
    ) -> Decimal:
        """
        计算交易金额（指定货币）
        
        对于收入/支出交易，返回金额的一半（因为借贷总和为零）
        
        Args:
            transaction: 交易实体
            currency: 货币代码
            
        Returns:
            交易金额
        """
        total = transaction.get_total_amount(currency)
        # 借贷平衡，总金额是实际金额的两倍
        return total / Decimal("2")
    
    def validate_account_balance_sufficient(
        self,
        account_name: str,
        amount: Decimal,
        currency: str = "CNY"
    ) -> bool:
        """
        验证账户余额是否充足
        
        对于资产账户，验证扣款后余额是否为负
        
        Args:
            account_name: 账户名称
            amount: 要扣除的金额（正数）
            currency: 货币
            
        Returns:
            充足返回 True
        """
        balance = self.account_repository.get_balance(account_name, currency)
        current_balance = balance.get(currency, Decimal("0"))
        
        # 资产账户余额应该大于等于扣款金额
        if account_name.startswith("Assets:"):
            return current_balance >= amount
        
        # 其他账户类型不做限制
        return True
    
    def get_transaction_summary(
        self,
        start_date: date,
        end_date: date,
        user_id: Optional[str] = None
    ) -> Dict:
        """
        获取交易摘要
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            user_id: 用户 ID
            
        Returns:
            摘要信息字典
        """
        return self.transaction_repository.get_statistics(
            start_date,
            end_date,
            user_id
        )
    
    def find_duplicate_transactions(
        self,
        transaction: Transaction,
        tolerance_days: int = 1
    ) -> List[Transaction]:
        """
        查找重复交易
        
        根据日期、描述、金额等查找可能重复的交易。
        
        Args:
            transaction: 交易实体
            tolerance_days: 日期容差（天数）
            
        Returns:
            可能重复的交易列表
        """
        from datetime import timedelta
        
        # 查找日期范围内的交易
        start_date = transaction.date - timedelta(days=tolerance_days)
        end_date = transaction.date + timedelta(days=tolerance_days)
        
        similar_transactions = self.transaction_repository.find_by_date_range(
            start_date,
            end_date
        )
        
        # 过滤出相似的交易
        duplicates = []
        for txn in similar_transactions:
            if txn.id == transaction.id:
                continue
            
            # 检查描述相似度和金额
            if self._is_similar_transaction(transaction, txn):
                duplicates.append(txn)
        
        return duplicates
    
    def _is_similar_transaction(self, txn1: Transaction, txn2: Transaction) -> bool:
        """
        判断两个交易是否相似
        
        Args:
            txn1: 交易1
            txn2: 交易2
            
        Returns:
            相似返回 True
        """
        # 描述相同或相似
        if txn1.description.lower() != txn2.description.lower():
            return False
        
        # 货币相同
        if txn1.get_currencies() != txn2.get_currencies():
            return False
        
        # 金额相同
        for currency in txn1.get_currencies():
            amount1 = txn1.get_total_amount(currency)
            amount2 = txn2.get_total_amount(currency)
            if abs(amount1 - amount2) > Decimal("0.01"):
                return False
        
        return True
    
    def categorize_transaction(self, transaction: Transaction) -> str:
        """
        对交易进行分类
        
        基于涉及的账户返回主要分类。
        
        Args:
            transaction: 交易实体
            
        Returns:
            分类名称
        """
        txn_type = transaction.detect_transaction_type()
        
        if txn_type == TransactionType.EXPENSE:
            # 查找 Expenses 账户
            for account in transaction.get_accounts():
                if account.startswith("Expenses:"):
                    # 返回第二层级作为分类
                    parts = account.split(":")
                    if len(parts) >= 2:
                        return parts[1]
            return "Other"
        
        elif txn_type == TransactionType.INCOME:
            # 查找 Income 账户
            for account in transaction.get_accounts():
                if account.startswith("Income:"):
                    parts = account.split(":")
                    if len(parts) >= 2:
                        return parts[1]
            return "Other"
        
        elif txn_type == TransactionType.TRANSFER:
            return "Transfer"
        
        elif txn_type == TransactionType.OPENING:
            return "Opening"
        
        return "Other"
