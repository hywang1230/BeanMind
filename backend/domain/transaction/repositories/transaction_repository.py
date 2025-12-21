"""交易仓储接口

定义交易数据访问的抽象接口，遵循 DDD 的仓储模式。
具体实现由基础设施层提供（Beancount + SQLite）。
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict
from datetime import date, datetime
from decimal import Decimal

from backend.domain.transaction.entities import Transaction, TransactionType


class TransactionRepository(ABC):
    """
    交易仓储接口
    
    定义所有交易数据访问方法的抽象接口。
    这是领域层的接口，不依赖于任何具体的数据存储技术。
    
    实现注意事项：
    - 交易数据保存在 Beancount 文件中
    - 交易元数据保存在 SQLite 数据库中
    - 需要保证两者的一致性
    """
    
    @abstractmethod
    def find_by_id(self, transaction_id: str) -> Optional[Transaction]:
        """
        根据 ID 查找交易
        
        Args:
            transaction_id: 交易 ID
            
        Returns:
            找到的交易实体，不存在则返回 None
        """
        pass
    
    @abstractmethod
    def find_all(
        self,
        user_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Transaction]:
        """
        查找所有交易（支持分页）
        
        Args:
            user_id: 可选，用户 ID，用于多用户场景
            limit: 可选，限制返回数量
            offset: 可选，偏移量
            
        Returns:
            交易列表
        """
        pass
    
    @abstractmethod
    def find_by_date_range(
        self,
        start_date: date,
        end_date: date,
        user_id: Optional[str] = None
    ) -> List[Transaction]:
        """
        查找指定日期范围内的交易
        
        Args:
            start_date: 开始日期（包含）
            end_date: 结束日期（包含）
            user_id: 可选，用户 ID
            
        Returns:
            交易列表，按日期升序排列
        """
        pass
    
    @abstractmethod
    def find_by_account(
        self,
        account_name: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Transaction]:
        """
        查找涉及指定账户的交易
        
        Args:
            account_name: 账户名称
            start_date: 可选，开始日期
            end_date: 可选，结束日期
            
        Returns:
            涉及该账户的交易列表
        """
        pass
    
    @abstractmethod
    def find_by_type(
        self,
        transaction_type: TransactionType,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Transaction]:
        """
        查找指定类型的交易
        
        Args:
            transaction_type: 交易类型
            start_date: 可选，开始日期
            end_date: 可选，结束日期
            
        Returns:
            指定类型的交易列表
        """
        pass
    
    @abstractmethod
    def find_by_tags(
        self,
        tags: List[str],
        match_all: bool = False
    ) -> List[Transaction]:
        """
        根据标签查找交易
        
        Args:
            tags: 标签列表
            match_all: 是否匹配所有标签（True: AND, False: OR）
            
        Returns:
            包含指定标签的交易列表
        """
        pass
    
    @abstractmethod
    def find_by_description(
        self,
        keyword: str,
        case_sensitive: bool = False
    ) -> List[Transaction]:
        """
        根据描述关键词搜索交易
        
        Args:
            keyword: 搜索关键词
            case_sensitive: 是否区分大小写
            
        Returns:
            描述中包含关键词的交易列表
        """
        pass
    
    @abstractmethod
    def create(self, transaction: Transaction, user_id: Optional[str] = None) -> Transaction:
        """
        创建新交易
        
        Args:
            transaction: 交易实体
            user_id: 可选，用户 ID
            
        Returns:
            创建后的交易实体（包含生成的 ID）
            
        Raises:
            ValueError: 如果交易数据无效
            
        注意：
        - 会同时写入 Beancount 文件和 SQLite 数据库
        - 需要保证事务一致性
        """
        pass
    
    @abstractmethod
    def update(self, transaction: Transaction) -> Transaction:
        """
        更新交易
        
        Args:
            transaction: 交易实体
            
        Returns:
            更新后的交易实体
            
        Raises:
            ValueError: 如果交易不存在或数据无效
            
        注意：
        - 会同时更新 Beancount 文件和 SQLite 数据库
        """
        pass
    
    @abstractmethod
    def delete(self, transaction_id: str) -> bool:
        """
        删除交易
        
        Args:
            transaction_id: 交易 ID
            
        Returns:
            删除成功返回 True，交易不存在返回 False
            
        注意：
        - 会同时从 Beancount 文件和 SQLite 数据库删除
        """
        pass
    
    @abstractmethod
    def exists(self, transaction_id: str) -> bool:
        """
        检查交易是否存在
        
        Args:
            transaction_id: 交易 ID
            
        Returns:
            存在返回 True，否则返回 False
        """
        pass
    
    @abstractmethod
    def count(
        self,
        user_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> int:
        """
        统计交易数量
        
        Args:
            user_id: 可选，用户 ID
            start_date: 可选，开始日期
            end_date: 可选，结束日期
            
        Returns:
            交易总数
        """
        pass
    
    @abstractmethod
    def get_statistics(
        self,
        start_date: date,
        end_date: date,
        user_id: Optional[str] = None
    ) -> Dict[str, any]:
        """
        获取交易统计信息
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            user_id: 可选，用户 ID
            
        Returns:
            统计信息字典，包含：
            - total_count: 总交易数
            - by_type: 按类型统计
            - by_currency: 按货币统计金额
            - income_total: 总收入
            - expense_total: 总支出
            
        Example:
            {
                "total_count": 100,
                "by_type": {
                    "expense": 60,
                    "income": 30,
                    "transfer": 10
                },
                "by_currency": {
                    "CNY": {"income": 10000, "expense": 8000},
                    "USD": {"income": 500, "expense": 300}
                },
                "income_total": {"CNY": 10000, "USD": 500},
                "expense_total": {"CNY": 8000, "USD": 300}
            }
        """
        pass
