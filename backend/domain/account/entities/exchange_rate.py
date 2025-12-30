"""汇率领域实体

定义汇率的核心属性和业务规则。
遵循 DDD 原则，不包含任何基础设施依赖。
"""
from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
import re


@dataclass
class ExchangeRate:
    """汇率领域实体
    
    表示 Beancount 中的一条价格（汇率）记录。
    格式: 2025-01-01 price USD 7.13 CNY
    表示: 1 USD = 7.13 CNY
    
    Attributes:
        currency: 源货币代码（如 USD）
        rate: 汇率（对主货币的比率）
        quote_currency: 目标货币/主货币代码（如 CNY）
        effective_date: 生效日期
    """
    
    currency: str = field(metadata={"description": "源货币代码"})
    rate: Decimal = field(metadata={"description": "汇率"})
    quote_currency: str = field(default="CNY", metadata={"description": "目标货币（主货币）"})
    effective_date: date = field(default_factory=date.today, metadata={"description": "生效日期"})
    
    def __post_init__(self):
        """初始化后验证"""
        self._validate()
        
        # 确保 rate 是 Decimal 类型
        if not isinstance(self.rate, Decimal):
            object.__setattr__(self, 'rate', Decimal(str(self.rate)))
        
        # 确保 effective_date 是 date 类型
        if isinstance(self.effective_date, datetime):
            object.__setattr__(self, 'effective_date', self.effective_date.date())
        elif isinstance(self.effective_date, str):
            object.__setattr__(self, 'effective_date', datetime.strptime(self.effective_date, "%Y-%m-%d").date())
    
    def _validate(self):
        """验证汇率数据"""
        # 验证货币代码
        if not self.currency or not self.currency.strip():
            raise ValueError("源货币代码不能为空")
        
        if not self.quote_currency or not self.quote_currency.strip():
            raise ValueError("目标货币代码不能为空")
        
        # 货币代码应为大写字母，长度为3
        currency_pattern = re.compile(r'^[A-Z]{3}$')
        if not currency_pattern.match(self.currency.upper()):
            raise ValueError(f"无效的源货币代码: {self.currency}")
        
        if not currency_pattern.match(self.quote_currency.upper()):
            raise ValueError(f"无效的目标货币代码: {self.quote_currency}")
        
        # 源货币和目标货币不能相同
        if self.currency.upper() == self.quote_currency.upper():
            raise ValueError("源货币和目标货币不能相同")
        
        # 验证汇率
        rate_value = Decimal(str(self.rate)) if not isinstance(self.rate, Decimal) else self.rate
        if rate_value <= 0:
            raise ValueError("汇率必须大于0")
    
    @property
    def currency_pair(self) -> str:
        """获取货币对标识
        
        Returns:
            货币对字符串，如 "USD/CNY"
        """
        return f"{self.currency}/{self.quote_currency}"
    
    def to_beancount_format(self) -> str:
        """转换为 Beancount price 指令格式
        
        Returns:
            Beancount 格式的价格指令，如 "2025-01-01 price USD 7.13 CNY"
        """
        date_str = self.effective_date.strftime("%Y-%m-%d")
        return f"{date_str} price {self.currency} {self.rate} {self.quote_currency}"
    
    def to_dict(self) -> dict:
        """转换为字典格式
        
        Returns:
            字典表示
        """
        return {
            "currency": self.currency,
            "rate": str(self.rate),
            "quote_currency": self.quote_currency,
            "effective_date": self.effective_date.isoformat(),
            "currency_pair": self.currency_pair
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ExchangeRate":
        """从字典创建汇率实体
        
        Args:
            data: 字典数据
            
        Returns:
            汇率实体
        """
        return cls(
            currency=data["currency"].upper(),
            rate=Decimal(str(data["rate"])),
            quote_currency=data.get("quote_currency", "CNY").upper(),
            effective_date=(
                datetime.strptime(data["effective_date"], "%Y-%m-%d").date()
                if isinstance(data.get("effective_date"), str)
                else data.get("effective_date", date.today())
            )
        )
    
    def __repr__(self) -> str:
        """字符串表示"""
        return f"ExchangeRate({self.currency}={self.rate} {self.quote_currency}, date={self.effective_date})"
