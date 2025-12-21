"""Posting 领域实体

表示交易中的一笔记账分录（Posting）。
在 Beancount 中，一笔交易由多个 Posting 组成，遵循复式记账原则。
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Dict, Any


@dataclass
class Posting:
    """
    记账分录领域实体
    
    表示交易中的单笔分录。
    一个 Transaction 包含多个 Posting，且所有 Posting 的金额总和必须为零（借贷平衡）。
    """
    
    # 必需字段
    account: str = field(metadata={"description": "账户名称（如 Assets:Bank:Checking）"})
    amount: Decimal = field(metadata={"description": "金额（正数表示借记，负数表示贷记）"})
    currency: str = field(metadata={"description": "货币代码（如 CNY, USD）"})
    
    # 可选字段
    cost: Optional[Decimal] = field(default=None, metadata={"description": "成本价格（用于投资账户）"})
    cost_currency: Optional[str] = field(default=None, metadata={"description": "成本货币"})
    price: Optional[Decimal] = field(default=None, metadata={"description": "市场价格"})
    price_currency: Optional[str] = field(default=None, metadata={"description": "价格货币"})
    flag: Optional[str] = field(default=None, metadata={"description": "标记（! 或 *）"})
    meta: Dict[str, Any] = field(default_factory=dict, metadata={"description": "元数据"})
    
    def __post_init__(self):
        """初始化后验证"""
        self._validate()
    
    def _validate(self):
        """验证 Posting 数据"""
        # 验证账户名称
        if not self.account or not self.account.strip():
            raise ValueError("账户名称不能为空")
        
        # 验证货币代码
        if not self.currency or not self.currency.strip():
            raise ValueError("货币代码不能为空")
        
        self.currency = self.currency.strip().upper()
        # 货币代码长度应在 2-10 之间（支持标准货币代码和股票代码等）
        if not (2 <= len(self.currency) <= 10):
            raise ValueError(f"无效的货币代码: {self.currency}")
        
        # 转换 amount 为 Decimal（如果不是）
        if not isinstance(self.amount, Decimal):
            self.amount = Decimal(str(self.amount))
        
        # 验证 cost 和 cost_currency 必须同时存在或同时不存在
        if (self.cost is None) != (self.cost_currency is None):
            raise ValueError("成本价格和成本货币必须同时指定或同时为空")
        
        # 验证 price 和 price_currency 必须同时存在或同时不存在
        if (self.price is None) != (self.price_currency is None):
            raise ValueError("市场价格和价格货币必须同时指定或同时为空")
        
        # 转换 cost 为 Decimal
        if self.cost is not None and not isinstance(self.cost, Decimal):
            self.cost = Decimal(str(self.cost))
        
        # 转换 price 为 Decimal
        if self.price is not None and not isinstance(self.price, Decimal):
            self.price = Decimal(str(self.price))
        
        # 验证 flag
        if self.flag and self.flag not in ("*", "!"):
            raise ValueError(f"无效的标记: {self.flag}，必须是 * 或 !")
    
    def is_debit(self) -> bool:
        """
        判断是否为借记分录
        
        Returns:
            如果金额为正则返回 True
        """
        return self.amount > 0
    
    def is_credit(self) -> bool:
        """
        判断是否为贷记分录
        
        Returns:
            如果金额为负则返回 True
        """
        return self.amount < 0
    
    def get_absolute_amount(self) -> Decimal:
        """
        获取金额的绝对值
        
        Returns:
            金额的绝对值
        """
        return abs(self.amount)
    
    def has_cost(self) -> bool:
        """
        判断是否有成本价格
        
        Returns:
            如果有成本价格则返回 True
        """
        return self.cost is not None
    
    def has_price(self) -> bool:
        """
        判断是否有市场价格
        
        Returns:
            如果有市场价格则返回 True
        """
        return self.price is not None
    
    def get_total_cost(self) -> Optional[Decimal]:
        """
        获取总成本（金额 × 成本价格）
        
        Returns:
            总成本，如果没有成本价格则返回 None
        """
        if not self.has_cost():
            return None
        return abs(self.amount) * self.cost
    
    def get_total_value(self) -> Optional[Decimal]:
        """
        获取总市值（金额 × 市场价格）
        
        Returns:
            总市值，如果没有市场价格则返回 None
        """
        if not self.has_price():
            return None
        return abs(self.amount) * self.price
    
    def to_dict(self) -> dict:
        """
        转换为字典格式
        
        Returns:
            字典表示
        """
        result = {
            "account": self.account,
            "amount": str(self.amount),
            "currency": self.currency,
        }
        
        if self.cost is not None:
            result["cost"] = str(self.cost)
            result["cost_currency"] = self.cost_currency
        
        if self.price is not None:
            result["price"] = str(self.price)
            result["price_currency"] = self.price_currency
        
        if self.flag:
            result["flag"] = self.flag
        
        if self.meta:
            result["meta"] = self.meta
        
        return result
    
    @classmethod
    def from_dict(cls, data: dict) -> "Posting":
        """
        从字典创建 Posting 实体
        
        Args:
            data: 字典数据
            
        Returns:
            Posting 实体
        """
        return cls(
            account=data["account"],
            amount=Decimal(str(data["amount"])),
            currency=data["currency"],
            cost=Decimal(str(data["cost"])) if data.get("cost") else None,
            cost_currency=data.get("cost_currency"),
            price=Decimal(str(data["price"])) if data.get("price") else None,
            price_currency=data.get("price_currency"),
            flag=data.get("flag"),
            meta=data.get("meta", {}),
        )
    
    def __repr__(self) -> str:
        """字符串表示"""
        amount_str = f"{self.amount:,.2f} {self.currency}"
        if self.has_cost():
            cost_str = f" @ {self.cost} {self.cost_currency}"
        else:
            cost_str = ""
        return f"<Posting({self.account}, {amount_str}{cost_str})>"
