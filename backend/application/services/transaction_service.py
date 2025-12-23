"""交易应用服务

协调领域服务和仓储，提供面向接口层的高层业务操作。
处理 DTO 转换。
"""
from typing import List, Dict, Optional
from decimal import Decimal
from datetime import date, datetime

from backend.domain.transaction.entities import Transaction, Posting, TransactionType
from backend.domain.transaction.repositories import TransactionRepository
from backend.domain.transaction.services import TransactionService
from backend.domain.account.repositories import AccountRepository


class TransactionApplicationService:
    """
    交易应用服务
    
    负责：
    - 协调领域服务和仓储
    - DTO 转换（实体 <-> 字典）
    - 提供面向接口层的操作
    """
    
    def __init__(
        self,
        transaction_repository: TransactionRepository,
        account_repository: AccountRepository
    ):
        """
        初始化应用服务
        
        Args:
            transaction_repository: 交易仓储
            account_repository: 账户仓储
        """
        self.transaction_repository = transaction_repository
        self.account_repository = account_repository
        self.transaction_service = TransactionService(
            transaction_repository,
            account_repository
        )
    
    def create_transaction(
        self,
        txn_date: str,
        description: str,
        postings: List[Dict],
        payee: Optional[str] = None,
        tags: Optional[List[str]] = None,
        links: Optional[List[str]] = None,
        user_id: Optional[str] = None
    ) -> Dict:
        """
        创建交易
        
        Args:
            txn_date: 交易日期（ISO 格式字符串）
            description: 交易描述
            postings: 记账分录列表（DTO）
            payee: 收付款方
            tags: 标签列表
            links: 链接列表
            user_id: 用户 ID
            
        Returns:
            交易 DTO
        """
        # 转换日期
        date_obj = date.fromisoformat(txn_date)
        
        # 转换 postings
        posting_entities = [self._dto_to_posting(p) for p in postings]
        
        # 创建交易
        transaction = self.transaction_service.create_transaction(
            txn_date=date_obj,
            description=description,
            postings=posting_entities,
            payee=payee,
            tags=tags,
            links=links,
            user_id=user_id
        )
        
        return self._transaction_to_dto(transaction)
    
    def get_transaction_by_id(self, transaction_id: str) -> Optional[Dict]:
        """
        根据 ID 获取交易
        
        Args:
            transaction_id: 交易 ID
            
        Returns:
            交易 DTO，不存在返回 None
        """
        transaction = self.transaction_repository.find_by_id(transaction_id)
        return self._transaction_to_dto(transaction) if transaction else None
    
    def get_transactions(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        account: Optional[str] = None,
        transaction_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        description: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        user_id: Optional[str] = None
    ) -> List[Dict]:
        """
        获取交易列表（支持分页和筛选）
        
        Args:
            start_date: 开始日期（ISO 格式）
            end_date: 结束日期（ISO 格式）
            account: 账户过滤
            transaction_type: 交易类型过滤
            tags: 标签过滤
            description: 描述关键词搜索
            limit: 限制返回数量
            offset: 偏移量
            user_id: 用户 ID
            
        Returns:
            交易 DTO 列表
        """
        # 转换日期参数
        start = date.fromisoformat(start_date) if start_date else None
        end = date.fromisoformat(end_date) if end_date else None
        
        # 首先获取基础数据集
        if start and end:
            # 日期范围查询作为基础
            transactions = self.transaction_repository.find_by_date_range(start, end, user_id)
        elif account:
            # 按账户查询
            transactions = self.transaction_repository.find_by_account(account, start, end)
        elif tags:
            # 按标签查询
            transactions = self.transaction_repository.find_by_tags(tags)
        elif description:
            # 按描述搜索
            transactions = self.transaction_repository.find_by_description(description)
        else:
            # 查询所有
            transactions = self.transaction_repository.find_all(user_id, None, None)
        
        # 应用额外的过滤条件（支持多条件组合）
        if transaction_type:
            txn_type = TransactionType(transaction_type)
            transactions = [t for t in transactions if t.detect_transaction_type() == txn_type]
        
        # 如果有日期范围但不是通过 find_by_date_range 获取的，需要再次过滤
        if start and not end:
            transactions = [t for t in transactions if t.date >= start]
        if end and not start:
            transactions = [t for t in transactions if t.date <= end]
        
        # 按日期倒序排序
        transactions.sort(key=lambda t: t.date, reverse=True)
        
        return [self._transaction_to_dto(txn) for txn in transactions]
    
    def get_all_payees(self) -> List[str]:
        """
        获取所有历史交易方
        
        Returns:
            交易方列表
        """
        return self.transaction_repository.get_all_payees()
    
    def update_transaction(
        self,
        transaction_id: str,
        txn_date: Optional[str] = None,
        description: Optional[str] = None,
        postings: Optional[List[Dict]] = None,
        payee: Optional[str] = None,
        tags: Optional[List[str]] = None,
        links: Optional[List[str]] = None
    ) -> Dict:
        """
        更新交易
        
        Args:
            transaction_id: 交易 ID
            txn_date: 交易日期（ISO 格式）
            description: 交易描述
            postings: 记账分录列表（DTO）
            payee: 收付款方
            tags: 标签列表
            links: 链接列表
            
        Returns:
            更新后的交易 DTO
            
        Raises:
            ValueError: 如果交易不存在
        """
        # 获取现有交易
        transaction = self.transaction_repository.find_by_id(transaction_id)
        if not transaction:
            raise ValueError(f"交易 '{transaction_id}' 不存在")
        
        # 更新字段
        if txn_date:
            transaction.date = date.fromisoformat(txn_date)
        if description:
            transaction.description = description
        if postings is not None:
            transaction.postings = [self._dto_to_posting(p) for p in postings]
            # 重新验证平衡
            self.transaction_service.validate_transaction(transaction)
        if payee is not None:
            transaction.payee = payee
        if tags is not None:
            transaction.tags = set(tags)
        if links is not None:
            transaction.links = set(links)
        
        # 保存更新
        updated = self.transaction_repository.update(transaction)
        return self._transaction_to_dto(updated)
    
    def delete_transaction(self, transaction_id: str) -> bool:
        """
        删除交易
        
        Args:
            transaction_id: 交易 ID
            
        Returns:
            成功删除返回 True
        """
        return self.transaction_repository.delete(transaction_id)
    
    def get_statistics(
        self,
        start_date: str,
        end_date: str,
        user_id: Optional[str] = None
    ) -> Dict:
        """
        获取交易统计信息
        
        Args:
            start_date: 开始日期（ISO 格式）
            end_date: 结束日期（ISO 格式）
            user_id: 用户 ID
            
        Returns:
            统计信息字典
        """
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        
        return self.transaction_service.get_transaction_summary(start, end, user_id)
    
    def validate_transaction(self, transaction_data: Dict) -> Dict:
        """
        验证交易数据
        
        Args:
            transaction_data: 交易数据 DTO
            
        Returns:
            验证结果 {"valid": bool, "errors": List[str]}
        """
        errors = []
        
        try:
            # 转换为实体
            txn_date = date.fromisoformat(transaction_data["date"])
            description = transaction_data["description"]
            postings = [self._dto_to_posting(p) for p in transaction_data["postings"]]
            
            # 构建临时交易实体
            transaction = Transaction(
                date=txn_date,
                description=description,
                postings=postings
            )
            
            # 验证
            self.transaction_service.validate_transaction(transaction)
            
        except ValueError as e:
            errors.append(str(e))
        except KeyError as e:
            errors.append(f"缺少必需字段: {e}")
        except Exception as e:
            errors.append(f"验证失败: {e}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def categorize_transaction(self, transaction_id: str) -> str:
        """
        对交易进行分类
        
        Args:
            transaction_id: 交易 ID
            
        Returns:
            分类名称
        """
        transaction = self.transaction_repository.find_by_id(transaction_id)
        if not transaction:
            raise ValueError(f"交易 '{transaction_id}' 不存在")
        
        return self.transaction_service.categorize_transaction(transaction)
    
    def find_duplicate_transactions(
        self,
        transaction_id: str,
        tolerance_days: int = 1
    ) -> List[Dict]:
        """
        查找重复交易
        
        Args:
            transaction_id: 交易 ID
            tolerance_days: 日期容差（天数）
            
        Returns:
            可能重复的交易 DTO 列表
        """
        transaction = self.transaction_repository.find_by_id(transaction_id)
        if not transaction:
            raise ValueError(f"交易 '{transaction_id}' 不存在")
        
        duplicates = self.transaction_service.find_duplicate_transactions(
            transaction,
            tolerance_days
        )
        
        return [self._transaction_to_dto(txn) for txn in duplicates]
    
    def _transaction_to_dto(self, transaction: Transaction) -> Dict:
        """
        将交易实体转换为 DTO
        
        Args:
            transaction: 交易实体
            
        Returns:
            交易 DTO
        """
        return {
            "id": transaction.id,
            "date": transaction.date.isoformat(),
            "description": transaction.description,
            "payee": transaction.payee,
            "flag": transaction.flag.value if transaction.flag else None,
            "postings": [self._posting_to_dto(p) for p in transaction.postings],
            "tags": list(transaction.tags),
            "links": list(transaction.links),
            "meta": transaction.meta if transaction.meta is not None else {},
            "transaction_type": transaction.detect_transaction_type().value,
            "accounts": transaction.get_accounts(),
            "currencies": list(transaction.get_currencies()),
            "created_at": transaction.created_at.isoformat() if transaction.created_at else None,
            "updated_at": transaction.updated_at.isoformat() if transaction.updated_at else None
        }
    
    def _posting_to_dto(self, posting: Posting) -> Dict:
        """
        将记账分录实体转换为 DTO
        
        Args:
            posting: 记账分录实体
            
        Returns:
            记账分录 DTO
        """
        return {
            "account": posting.account,
            "amount": str(posting.amount),
            "currency": posting.currency,
            "cost": str(posting.cost) if posting.cost else None,
            "cost_currency": posting.cost_currency,
            "price": str(posting.price) if posting.price else None,
            "price_currency": posting.price_currency,
            "flag": posting.flag,
            "meta": posting.meta if posting.meta is not None else {}
        }
    
    def _dto_to_posting(self, posting_dto: Dict) -> Posting:
        """
        将 DTO 转换为记账分录实体
        
        Args:
            posting_dto: 记账分录 DTO
            
        Returns:
            记账分录实体
        """
        return Posting(
            account=posting_dto["account"],
            amount=Decimal(posting_dto["amount"]),
            currency=posting_dto["currency"],
            cost=Decimal(posting_dto["cost"]) if posting_dto.get("cost") else None,
            cost_currency=posting_dto.get("cost_currency"),
            price=Decimal(posting_dto["price"]) if posting_dto.get("price") else None,
            price_currency=posting_dto.get("price_currency"),
            flag=posting_dto.get("flag"),
            meta=posting_dto.get("meta", {})
        )
