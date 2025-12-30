"""汇率仓储 Beancount 实现

从 Beancount 文件读取和写入汇率数据。
"""
import re
from pathlib import Path
from typing import Optional, List, Dict
from decimal import Decimal
from datetime import datetime, date

from beancount.core.data import Price
from beancount.core import amount
from beancount.parser import printer

from backend.domain.account.entities import ExchangeRate
from backend.domain.account.repositories import ExchangeRateRepository
from backend.infrastructure.persistence.beancount.beancount_service import BeancountService


class ExchangeRateRepositoryImpl(ExchangeRateRepository):
    """
    汇率仓储的 Beancount 实现
    
    从 Beancount 账本文件读取和写入汇率（price 指令）。
    """
    
    def __init__(self, beancount_service: BeancountService):
        """
        初始化汇率仓储
        
        Args:
            beancount_service: Beancount 服务实例
        """
        self.beancount_service = beancount_service
        self._load_exchange_rates()
    
    def _load_exchange_rates(self):
        """从 Beancount 加载所有汇率"""
        self._exchange_rates: List[ExchangeRate] = []
        
        for entry in self.beancount_service.entries:
            if isinstance(entry, Price):
                exchange_rate = ExchangeRate(
                    currency=entry.currency,
                    rate=entry.amount.number,
                    quote_currency=entry.amount.currency,
                    effective_date=entry.date
                )
                self._exchange_rates.append(exchange_rate)
    
    def reload(self):
        """重新加载汇率数据"""
        self.beancount_service.reload()
        self._load_exchange_rates()
    
    def find_by_currency(
        self,
        currency: str,
        quote_currency: str = "CNY"
    ) -> Optional[ExchangeRate]:
        """根据货币代码获取最新汇率"""
        currency = currency.upper()
        quote_currency = quote_currency.upper()
        
        matching = [
            er for er in self._exchange_rates
            if er.currency.upper() == currency and er.quote_currency.upper() == quote_currency
        ]
        
        if not matching:
            return None
        
        # 返回最新的汇率
        matching.sort(key=lambda x: x.effective_date, reverse=True)
        return matching[0]
    
    def find_all(self, quote_currency: str = "CNY") -> List[ExchangeRate]:
        """获取所有货币对主货币的最新汇率"""
        quote_currency = quote_currency.upper()
        
        # 按货币分组，取每种货币的最新汇率
        latest_rates: Dict[str, ExchangeRate] = {}
        
        for er in self._exchange_rates:
            if er.quote_currency.upper() != quote_currency:
                continue
            
            curr = er.currency.upper()
            if curr not in latest_rates or er.effective_date > latest_rates[curr].effective_date:
                latest_rates[curr] = er
        
        return list(latest_rates.values())
    
    def find_all_history(
        self,
        currency: str,
        quote_currency: str = "CNY"
    ) -> List[ExchangeRate]:
        """获取指定货币对的所有历史汇率"""
        currency = currency.upper()
        quote_currency = quote_currency.upper()
        
        matching = [
            er for er in self._exchange_rates
            if er.currency.upper() == currency and er.quote_currency.upper() == quote_currency
        ]
        
        # 按日期降序排列
        matching.sort(key=lambda x: x.effective_date, reverse=True)
        return matching
    
    def find_by_date(
        self,
        currency: str,
        effective_date: date,
        quote_currency: str = "CNY"
    ) -> Optional[ExchangeRate]:
        """获取指定日期的汇率"""
        currency = currency.upper()
        quote_currency = quote_currency.upper()
        
        for er in self._exchange_rates:
            if (er.currency.upper() == currency and 
                er.quote_currency.upper() == quote_currency and
                er.effective_date == effective_date):
                return er
        
        return None
    
    def create(self, exchange_rate: ExchangeRate) -> ExchangeRate:
        """创建新的汇率记录"""
        # 检查是否已存在相同日期的汇率
        existing = self.find_by_date(
            exchange_rate.currency,
            exchange_rate.effective_date,
            exchange_rate.quote_currency
        )
        
        if existing:
            raise ValueError(
                f"汇率 {exchange_rate.currency}/{exchange_rate.quote_currency} "
                f"在 {exchange_rate.effective_date} 已存在"
            )
        
        # 构建 Price 指令
        price_entry = Price(
            meta={},
            date=exchange_rate.effective_date,
            currency=exchange_rate.currency.upper(),
            amount=amount.Amount(exchange_rate.rate, exchange_rate.quote_currency.upper())
        )
        
        # 追加到文件
        with open(self.beancount_service.ledger_path, "a", encoding="utf-8") as f:
            f.write("\n")
            f.write(printer.format_entry(price_entry))
            f.write("\n")
        
        # 重新加载
        self.reload()
        
        return exchange_rate
    
    def update(
        self,
        currency: str,
        effective_date: date,
        new_rate: Decimal,
        quote_currency: str = "CNY"
    ) -> ExchangeRate:
        """更新指定日期的汇率"""
        currency = currency.upper()
        quote_currency = quote_currency.upper()
        
        # 检查汇率是否存在
        existing = self.find_by_date(currency, effective_date, quote_currency)
        if not existing:
            raise ValueError(
                f"汇率 {currency}/{quote_currency} 在 {effective_date} 不存在"
            )
        
        # 读取账本文件，查找并更新 Price 指令
        self._modify_price_in_files(
            currency=currency,
            quote_currency=quote_currency,
            effective_date=effective_date,
            new_rate=new_rate,
            delete=False
        )
        
        # 重新加载
        self.reload()
        
        # 返回更新后的汇率
        return self.find_by_date(currency, effective_date, quote_currency)
    
    def delete(
        self,
        currency: str,
        effective_date: date,
        quote_currency: str = "CNY"
    ) -> bool:
        """删除指定日期的汇率记录"""
        currency = currency.upper()
        quote_currency = quote_currency.upper()
        
        # 检查汇率是否存在
        existing = self.find_by_date(currency, effective_date, quote_currency)
        if not existing:
            return False
        
        # 读取账本文件，查找并删除 Price 指令
        result = self._modify_price_in_files(
            currency=currency,
            quote_currency=quote_currency,
            effective_date=effective_date,
            new_rate=None,
            delete=True
        )
        
        # 重新加载
        self.reload()
        
        return result
    
    def _modify_price_in_files(
        self,
        currency: str,
        quote_currency: str,
        effective_date: date,
        new_rate: Optional[Decimal],
        delete: bool
    ) -> bool:
        """
        在 Beancount 文件中修改或删除 Price 指令
        
        Args:
            currency: 源货币代码
            quote_currency: 目标货币代码
            effective_date: 生效日期
            new_rate: 新汇率（删除时为 None）
            delete: 是否删除
            
        Returns:
            是否成功修改
        """
        ledger_path = self.beancount_service.ledger_path
        
        # 获取所有需要检查的文件
        files_to_check = [ledger_path]
        
        # 检查主文件内的 include 语句
        ledger_dir = Path(ledger_path).parent
        with open(ledger_path, 'r', encoding='utf-8') as f:
            content = f.read()
            includes = re.findall(r'include\s+"([^"]+)"', content)
            for inc in includes:
                inc_path = ledger_dir / inc
                if inc_path.exists():
                    files_to_check.append(inc_path)
        
        # 构建匹配模式
        # 格式: 2025-01-01 price USD 7.13 CNY
        date_str = effective_date.strftime("%Y-%m-%d")
        pattern = re.compile(
            rf'^{date_str}\s+price\s+{currency}\s+[\d.]+\s+{quote_currency}\s*$',
            re.IGNORECASE
        )
        
        for file_path in files_to_check:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                new_lines = []
                modified = False
                
                for line in lines:
                    stripped = line.strip()
                    if pattern.match(stripped):
                        if delete:
                            # 删除此行
                            modified = True
                            continue
                        else:
                            # 更新此行
                            new_line = f"{date_str} price {currency} {new_rate} {quote_currency}\n"
                            new_lines.append(new_line)
                            modified = True
                    else:
                        new_lines.append(line)
                
                if modified:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.writelines(new_lines)
                    return True
                    
            except Exception:
                continue
        
        return False
    
    def get_rate(
        self,
        currency: str,
        quote_currency: str = "CNY",
        as_of_date: Optional[date] = None
    ) -> Optional[Decimal]:
        """获取汇率值"""
        if as_of_date is None:
            as_of_date = date.today()
        
        currency = currency.upper()
        quote_currency = quote_currency.upper()
        
        # 如果是同一货币，返回1
        if currency == quote_currency:
            return Decimal("1")
        
        # 查找最近的汇率（不超过截止日期）
        matching = [
            er for er in self._exchange_rates
            if (er.currency.upper() == currency and 
                er.quote_currency.upper() == quote_currency and
                er.effective_date <= as_of_date)
        ]
        
        if not matching:
            # 尝试反向查找
            reverse_matching = [
                er for er in self._exchange_rates
                if (er.currency.upper() == quote_currency and 
                    er.quote_currency.upper() == currency and
                    er.effective_date <= as_of_date)
            ]
            
            if not reverse_matching:
                return None
            
            # 取最新的反向汇率，取倒数
            reverse_matching.sort(key=lambda x: x.effective_date, reverse=True)
            return Decimal("1") / reverse_matching[0].rate
        
        # 按日期排序，取最新的
        matching.sort(key=lambda x: x.effective_date, reverse=True)
        return matching[0].rate
    
    def get_all_currencies(self) -> List[str]:
        """获取所有已定义汇率的货币代码"""
        currencies = set()
        for er in self._exchange_rates:
            currencies.add(er.currency.upper())
        return sorted(list(currencies))
