"""周期规则频率配置值对象"""
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum


class FrequencyType(str, Enum):
    """频率类型"""
    DAILY = "DAILY"  # 每天
    WEEKLY = "WEEKLY"  # 每周
    MONTHLY = "MONTHLY"  # 每月
    YEARLY = "YEARLY"  # 每年
    INTERVAL = "INTERVAL"  # 间隔天数


@dataclass
class FrequencyConfig:
    """频率配置值对象
    
    用于配置周期任务的执行频率
    """
    frequency_type: FrequencyType
    weekdays: Optional[List[int]] = None  # 周几执行 (1-7, 1=周一)
    month_days: Optional[List[int]] = None  # 月中哪几天执行 (1-31, -1=月末)
    interval_days: Optional[int] = None  # 间隔天数
    
    def __post_init__(self):
        """验证频率配置"""
        if self.frequency_type == FrequencyType.WEEKLY:
            if not self.weekdays or len(self.weekdays) == 0:
                raise ValueError("周频率必须指定至少一个weekday")
            if not all(1 <= day <= 7 for day in self.weekdays):
                raise ValueError("weekday必须在1-7之间")
        
        elif self.frequency_type == FrequencyType.MONTHLY:
            if not self.month_days or len(self.month_days) == 0:
                raise ValueError("月频率必须指定至少一个month_day")
            if not all((1 <= day <= 31) or day == -1 for day in self.month_days):
                raise ValueError("month_day必须在1-31之间或为-1（月末）")
        
        elif self.frequency_type == FrequencyType.INTERVAL:
            if not self.interval_days or self.interval_days < 1:
                raise ValueError("间隔频率必须指定大于0的间隔天数")
    
    @classmethod
    def daily(cls) -> "FrequencyConfig":
        """创建每日频率配置"""
        return cls(frequency_type=FrequencyType.DAILY)
    
    @classmethod
    def weekly(cls, weekdays: List[int]) -> "FrequencyConfig":
        """创建每周频率配置"""
        return cls(frequency_type=FrequencyType.WEEKLY, weekdays=weekdays)
    
    @classmethod
    def monthly(cls, month_days: List[int]) -> "FrequencyConfig":
        """创建每月频率配置"""
        return cls(frequency_type=FrequencyType.MONTHLY, month_days=month_days)
    
    @classmethod
    def yearly(cls) -> "FrequencyConfig":
        """创建每年频率配置"""
        return cls(frequency_type=FrequencyType.YEARLY)
    
    @classmethod
    def interval(cls, days: int) -> "FrequencyConfig":
        """创建间隔频率配置"""
        return cls(frequency_type=FrequencyType.INTERVAL, interval_days=days)
    
    def to_dict(self) -> dict:
        """转换为字典（用于JSON存储）"""
        return {
            "frequency_type": self.frequency_type.value,
            "weekdays": self.weekdays,
            "month_days": self.month_days,
            "interval_days": self.interval_days
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "FrequencyConfig":
        """从字典创建（用于JSON读取）"""
        return cls(
            frequency_type=FrequencyType(data["frequency_type"]),
            weekdays=data.get("weekdays"),
            month_days=data.get("month_days"),
            interval_days=data.get("interval_days")
        )
