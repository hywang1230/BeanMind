"""汇率仓储接口

定义汇率数据访问的抽象接口。
遵循仓储模式，不包含具体实现。
"""
from abc import ABC, abstractmethod
from typing import Optional, List
from datetime import date
from decimal import Decimal

from backend.domain.account.entities import ExchangeRate


class ExchangeRateRepository(ABC):
    """汇率仓储接口
    
    定义汇率数据访问的抽象方法。
    具体实现可能从 Beancount 文件、数据库或其他数据源读取。
    """
    
    @abstractmethod
    def find_by_currency(
        self, 
        currency: str, 
        quote_currency: str = "CNY"
    ) -> Optional[ExchangeRate]:
        """
        根据货币代码获取最新汇率
        
        Args:
            currency: 源货币代码（如 USD）
            quote_currency: 目标货币代码（默认 CNY）
            
        Returns:
            最新的汇率实体，不存在则返回 None
        """
        pass
    
    @abstractmethod
    def find_all(self, quote_currency: str = "CNY") -> List[ExchangeRate]:
        """
        获取所有货币对主货币的最新汇率
        
        Args:
            quote_currency: 目标货币代码（默认 CNY）
            
        Returns:
            所有汇率的列表（每种货币只返回最新的一条）
        """
        pass
    
    @abstractmethod
    def find_all_history(
        self, 
        currency: str, 
        quote_currency: str = "CNY"
    ) -> List[ExchangeRate]:
        """
        获取指定货币对的所有历史汇率
        
        Args:
            currency: 源货币代码
            quote_currency: 目标货币代码
            
        Returns:
            所有历史汇率列表，按日期降序排列
        """
        pass
    
    @abstractmethod
    def find_by_date(
        self, 
        currency: str, 
        effective_date: date,
        quote_currency: str = "CNY"
    ) -> Optional[ExchangeRate]:
        """
        获取指定日期的汇率
        
        Args:
            currency: 源货币代码
            effective_date: 生效日期
            quote_currency: 目标货币代码
            
        Returns:
            指定日期的汇率，不存在则返回 None
        """
        pass
    
    @abstractmethod
    def create(self, exchange_rate: ExchangeRate) -> ExchangeRate:
        """
        创建新的汇率记录
        
        Args:
            exchange_rate: 汇率实体
            
        Returns:
            创建后的汇率实体
        """
        pass
    
    @abstractmethod
    def update(
        self, 
        currency: str, 
        effective_date: date,
        new_rate: Decimal,
        quote_currency: str = "CNY"
    ) -> ExchangeRate:
        """
        更新指定日期的汇率
        
        Args:
            currency: 源货币代码
            effective_date: 生效日期
            new_rate: 新汇率
            quote_currency: 目标货币代码
            
        Returns:
            更新后的汇率实体
            
        Raises:
            ValueError: 如果汇率记录不存在
        """
        pass
    
    @abstractmethod
    def delete(
        self, 
        currency: str, 
        effective_date: date,
        quote_currency: str = "CNY"
    ) -> bool:
        """
        删除指定日期的汇率记录
        
        Args:
            currency: 源货币代码
            effective_date: 生效日期
            quote_currency: 目标货币代码
            
        Returns:
            成功删除返回 True，记录不存在返回 False
        """
        pass
    
    @abstractmethod
    def get_rate(
        self, 
        currency: str, 
        quote_currency: str = "CNY",
        as_of_date: Optional[date] = None
    ) -> Optional[Decimal]:
        """
        获取汇率值
        
        Args:
            currency: 源货币代码
            quote_currency: 目标货币代码
            as_of_date: 截止日期，如果为 None 则使用当前日期
            
        Returns:
            汇率值，如果找不到则返回 None
        """
        pass
    
    @abstractmethod
    def get_all_currencies(self) -> List[str]:
        """
        获取所有已定义汇率的货币代码
        
        Returns:
            货币代码列表
        """
        pass
