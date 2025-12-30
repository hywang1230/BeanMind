"""汇率领域服务

提供汇率相关的业务逻辑和规则验证。
"""
from typing import List, Optional
from decimal import Decimal
from datetime import date

from backend.domain.account.entities import ExchangeRate
from backend.domain.account.repositories import ExchangeRateRepository


class ExchangeRateService:
    """汇率领域服务
    
    负责汇率相关的核心业务逻辑，包括：
    - 汇率创建验证
    - 货币代码验证
    - 汇率换算
    - 业务规则验证
    """
    
    # 常用货币代码列表（用于验证和建议）
    COMMON_CURRENCIES = [
        "CNY",  # 人民币
        "USD",  # 美元
        "EUR",  # 欧元
        "GBP",  # 英镑
        "JPY",  # 日元
        "HKD",  # 港币
        "TWD",  # 新台币
        "SGD",  # 新加坡元
        "AUD",  # 澳元
        "CAD",  # 加元
        "CHF",  # 瑞士法郎
        "KRW",  # 韩元
    ]
    
    def __init__(self, exchange_rate_repository: ExchangeRateRepository):
        """
        初始化汇率服务
        
        Args:
            exchange_rate_repository: 汇率仓储
        """
        self.exchange_rate_repository = exchange_rate_repository
    
    def create_exchange_rate(
        self,
        currency: str,
        rate: Decimal,
        quote_currency: str = "CNY",
        effective_date: Optional[date] = None
    ) -> ExchangeRate:
        """
        创建新汇率
        
        业务规则：
        - 货币代码必须为有效的3位大写字母
        - 源货币和目标货币不能相同
        - 汇率必须大于0
        - 同一日期不能有重复的汇率记录
        
        Args:
            currency: 源货币代码
            rate: 汇率
            quote_currency: 目标货币代码（默认 CNY）
            effective_date: 生效日期（默认今天）
            
        Returns:
            创建的汇率实体
            
        Raises:
            ValueError: 如果验证失败
        """
        # 验证货币代码
        self._validate_currency_code(currency)
        self._validate_currency_code(quote_currency)
        
        if currency.upper() == quote_currency.upper():
            raise ValueError("源货币和目标货币不能相同")
        
        # 验证汇率
        if rate <= 0:
            raise ValueError("汇率必须大于0")
        
        # 设置默认日期
        if effective_date is None:
            effective_date = date.today()
        
        # 创建汇率实体
        exchange_rate = ExchangeRate(
            currency=currency.upper(),
            rate=rate,
            quote_currency=quote_currency.upper(),
            effective_date=effective_date
        )
        
        # 保存到仓储
        return self.exchange_rate_repository.create(exchange_rate)
    
    def update_exchange_rate(
        self,
        currency: str,
        effective_date: date,
        new_rate: Decimal,
        quote_currency: str = "CNY"
    ) -> ExchangeRate:
        """
        更新汇率
        
        Args:
            currency: 源货币代码
            effective_date: 生效日期
            new_rate: 新汇率
            quote_currency: 目标货币代码
            
        Returns:
            更新后的汇率实体
            
        Raises:
            ValueError: 如果验证失败或汇率不存在
        """
        # 验证汇率
        if new_rate <= 0:
            raise ValueError("汇率必须大于0")
        
        return self.exchange_rate_repository.update(
            currency=currency.upper(),
            effective_date=effective_date,
            new_rate=new_rate,
            quote_currency=quote_currency.upper()
        )
    
    def delete_exchange_rate(
        self,
        currency: str,
        effective_date: date,
        quote_currency: str = "CNY"
    ) -> bool:
        """
        删除汇率
        
        Args:
            currency: 源货币代码
            effective_date: 生效日期
            quote_currency: 目标货币代码
            
        Returns:
            成功删除返回 True
        """
        return self.exchange_rate_repository.delete(
            currency=currency.upper(),
            effective_date=effective_date,
            quote_currency=quote_currency.upper()
        )
    
    def get_exchange_rate(
        self,
        currency: str,
        quote_currency: str = "CNY"
    ) -> Optional[ExchangeRate]:
        """
        获取最新汇率
        
        Args:
            currency: 源货币代码
            quote_currency: 目标货币代码
            
        Returns:
            最新的汇率实体，不存在返回 None
        """
        return self.exchange_rate_repository.find_by_currency(
            currency.upper(),
            quote_currency.upper()
        )
    
    def get_all_exchange_rates(
        self,
        quote_currency: str = "CNY"
    ) -> List[ExchangeRate]:
        """
        获取所有货币对主货币的最新汇率
        
        Args:
            quote_currency: 目标货币代码
            
        Returns:
            汇率列表
        """
        return self.exchange_rate_repository.find_all(quote_currency.upper())
    
    def convert_amount(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        as_of_date: Optional[date] = None
    ) -> Optional[Decimal]:
        """
        货币换算
        
        Args:
            amount: 金额
            from_currency: 源货币
            to_currency: 目标货币
            as_of_date: 截止日期
            
        Returns:
            换算后的金额，如果找不到汇率返回 None
        """
        if from_currency.upper() == to_currency.upper():
            return amount
        
        rate = self.exchange_rate_repository.get_rate(
            from_currency.upper(),
            to_currency.upper(),
            as_of_date
        )
        
        if rate is None:
            return None
        
        return amount * rate
    
    def _validate_currency_code(self, code: str):
        """
        验证货币代码
        
        Args:
            code: 货币代码
            
        Raises:
            ValueError: 如果货币代码无效
        """
        import re
        if not code or not code.strip():
            raise ValueError("货币代码不能为空")
        
        if not re.match(r'^[A-Za-z]{3}$', code.strip()):
            raise ValueError(f"无效的货币代码: {code}（必须为3个字母）")
    
    def get_common_currencies(self) -> List[str]:
        """
        获取常用货币代码列表
        
        Returns:
            常用货币代码列表
        """
        return self.COMMON_CURRENCIES.copy()
    
    def is_valid_currency_code(self, code: str) -> bool:
        """
        检查货币代码是否有效
        
        Args:
            code: 货币代码
            
        Returns:
            有效返回 True
        """
        import re
        if not code or not code.strip():
            return False
        
        return bool(re.match(r'^[A-Za-z]{3}$', code.strip()))
