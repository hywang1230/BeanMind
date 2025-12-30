"""汇率应用服务

协调领域服务和仓储，提供面向接口层的高层业务操作。
处理 DTO 转换。
"""
from typing import List, Dict, Optional
from decimal import Decimal
from datetime import date, datetime

from backend.domain.account.entities import ExchangeRate
from backend.domain.account.repositories import ExchangeRateRepository
from backend.domain.account.services import ExchangeRateService


class ExchangeRateApplicationService:
    """汇率应用服务
    
    负责：
    - 协调领域服务和仓储
    - DTO 转换（实体 <-> 字典）
    - 提供面向接口层的操作
    """
    
    def __init__(self, exchange_rate_repository: ExchangeRateRepository):
        """
        初始化应用服务
        
        Args:
            exchange_rate_repository: 汇率仓储
        """
        self.exchange_rate_repository = exchange_rate_repository
        self.exchange_rate_service = ExchangeRateService(exchange_rate_repository)
    
    def create_exchange_rate(
        self,
        currency: str,
        rate: str,
        quote_currency: str = "CNY",
        effective_date: Optional[str] = None
    ) -> Dict:
        """
        创建汇率
        
        Args:
            currency: 源货币代码
            rate: 汇率（字符串）
            quote_currency: 目标货币代码
            effective_date: 生效日期（ISO 格式字符串）
            
        Returns:
            汇率 DTO
        """
        # 解析日期
        parsed_date = None
        if effective_date:
            parsed_date = datetime.strptime(effective_date, "%Y-%m-%d").date()
        
        # 调用领域服务
        exchange_rate = self.exchange_rate_service.create_exchange_rate(
            currency=currency,
            rate=Decimal(rate),
            quote_currency=quote_currency,
            effective_date=parsed_date
        )
        
        return self._exchange_rate_to_dto(exchange_rate)
    
    def update_exchange_rate(
        self,
        currency: str,
        effective_date: str,
        new_rate: str,
        quote_currency: str = "CNY"
    ) -> Dict:
        """
        更新汇率
        
        Args:
            currency: 源货币代码
            effective_date: 生效日期（ISO 格式字符串）
            new_rate: 新汇率（字符串）
            quote_currency: 目标货币代码
            
        Returns:
            更新后的汇率 DTO
        """
        parsed_date = datetime.strptime(effective_date, "%Y-%m-%d").date()
        
        exchange_rate = self.exchange_rate_service.update_exchange_rate(
            currency=currency,
            effective_date=parsed_date,
            new_rate=Decimal(new_rate),
            quote_currency=quote_currency
        )
        
        return self._exchange_rate_to_dto(exchange_rate)
    
    def delete_exchange_rate(
        self,
        currency: str,
        effective_date: str,
        quote_currency: str = "CNY"
    ) -> bool:
        """
        删除汇率
        
        Args:
            currency: 源货币代码
            effective_date: 生效日期（ISO 格式字符串）
            quote_currency: 目标货币代码
            
        Returns:
            成功删除返回 True
        """
        parsed_date = datetime.strptime(effective_date, "%Y-%m-%d").date()
        
        return self.exchange_rate_service.delete_exchange_rate(
            currency=currency,
            effective_date=parsed_date,
            quote_currency=quote_currency
        )
    
    def get_exchange_rate(
        self,
        currency: str,
        quote_currency: str = "CNY"
    ) -> Optional[Dict]:
        """
        获取最新汇率
        
        Args:
            currency: 源货币代码
            quote_currency: 目标货币代码
            
        Returns:
            汇率 DTO，不存在返回 None
        """
        exchange_rate = self.exchange_rate_service.get_exchange_rate(
            currency=currency,
            quote_currency=quote_currency
        )
        
        if exchange_rate is None:
            return None
        
        return self._exchange_rate_to_dto(exchange_rate)
    
    def get_all_exchange_rates(
        self,
        quote_currency: str = "CNY"
    ) -> List[Dict]:
        """
        获取所有货币对主货币的最新汇率
        
        Args:
            quote_currency: 目标货币代码
            
        Returns:
            汇率 DTO 列表
        """
        exchange_rates = self.exchange_rate_service.get_all_exchange_rates(
            quote_currency=quote_currency
        )
        
        return [self._exchange_rate_to_dto(er) for er in exchange_rates]
    
    def get_exchange_rate_history(
        self,
        currency: str,
        quote_currency: str = "CNY"
    ) -> List[Dict]:
        """
        获取指定货币对的所有历史汇率
        
        Args:
            currency: 源货币代码
            quote_currency: 目标货币代码
            
        Returns:
            汇率 DTO 列表（按日期降序）
        """
        exchange_rates = self.exchange_rate_repository.find_all_history(
            currency=currency.upper(),
            quote_currency=quote_currency.upper()
        )
        
        return [self._exchange_rate_to_dto(er) for er in exchange_rates]
    
    def convert_amount(
        self,
        amount: str,
        from_currency: str,
        to_currency: str,
        as_of_date: Optional[str] = None
    ) -> Optional[str]:
        """
        货币换算
        
        Args:
            amount: 金额（字符串）
            from_currency: 源货币
            to_currency: 目标货币
            as_of_date: 截止日期（ISO 格式字符串）
            
        Returns:
            换算后的金额（字符串），如果找不到汇率返回 None
        """
        parsed_date = None
        if as_of_date:
            parsed_date = datetime.strptime(as_of_date, "%Y-%m-%d").date()
        
        result = self.exchange_rate_service.convert_amount(
            amount=Decimal(amount),
            from_currency=from_currency,
            to_currency=to_currency,
            as_of_date=parsed_date
        )
        
        if result is None:
            return None
        
        return str(result.quantize(Decimal("0.01")))
    
    def get_common_currencies(self) -> List[str]:
        """
        获取常用货币代码列表
        
        Returns:
            常用货币代码列表
        """
        return self.exchange_rate_service.get_common_currencies()
    
    def get_available_currencies(self) -> List[str]:
        """
        获取所有已定义汇率的货币代码
        
        Returns:
            货币代码列表
        """
        return self.exchange_rate_repository.get_all_currencies()
    
    def is_valid_currency_code(self, code: str) -> bool:
        """
        验证货币代码是否有效
        
        Args:
            code: 货币代码
            
        Returns:
            有效返回 True
        """
        return self.exchange_rate_service.is_valid_currency_code(code)
    
    def _exchange_rate_to_dto(self, exchange_rate: ExchangeRate) -> Dict:
        """
        将汇率实体转换为 DTO
        
        Args:
            exchange_rate: 汇率实体
            
        Returns:
            DTO 字典
        """
        return {
            "currency": exchange_rate.currency,
            "rate": str(exchange_rate.rate),
            "quote_currency": exchange_rate.quote_currency,
            "effective_date": exchange_rate.effective_date.isoformat(),
            "currency_pair": exchange_rate.currency_pair
        }
