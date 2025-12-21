"""周期任务执行引擎"""
from datetime import date, timedelta
from calendar import monthrange
from typing import List

from backend.domain.recurring.entities.recurring_rule import RecurringRule
from backend.domain.recurring.value_objects.frequency_config import FrequencyType


class RecurringExecutionService:
    """周期任务执行引擎
    
    负责判断周期规则是否应该在指定日期执行
    """
    
    def should_execute(self, rule: RecurringRule, check_date: date) -> bool:
        """判断规则是否应该在指定日期执行
        
        Args:
            rule: 周期规则
            check_date: 检查日期
            
        Returns:
            是否应该执行
        """
        # 首先检查规则是否在该日期有效
        if not rule.is_valid_on_date(check_date):
            return False
        
        # 根据频率类型判断
        frequency = rule.frequency_config.frequency_type
        
        if frequency == FrequencyType.DAILY:
            return self._should_execute_daily(rule, check_date)
        elif frequency == FrequencyType.WEEKLY:
            return self._should_execute_weekly(rule, check_date)
        elif frequency == FrequencyType.MONTHLY:
            return self._should_execute_monthly(rule, check_date)
        elif frequency == FrequencyType.YEARLY:
            return self._should_execute_yearly(rule, check_date)
        elif frequency == FrequencyType.INTERVAL:
            return self._should_execute_interval(rule, check_date)
        
        return False
    
    def _should_execute_daily(self, rule: RecurringRule, check_date: date) -> bool:
        """判断每日频率是否应该执行
        
        Args:
            rule: 周期规则
            check_date: 检查日期
            
        Returns:
            是否应该执行
        """
        # 每日任务在有效期内每天都执行
        return True
    
    def _should_execute_weekly(self, rule: RecurringRule, check_date: date) -> bool:
        """判断每周频率是否应该执行
        
        Args:
            rule: 周期规则
            check_date: 检查日期
            
        Returns:
            是否应该执行
        """
        # 获取星期几 (1=周一, 7=周日)
        weekday = check_date.isoweekday()
        
        # 检查是否在配置的星期列表中
        return weekday in rule.frequency_config.weekdays
    
    def _should_execute_monthly(self, rule: RecurringRule, check_date: date) -> bool:
        """判断每月频率是否应该执行
        
        Args:
            rule: 周期规则
            check_date: 检查日期
            
        Returns:
            是否应该执行
        """
        day = check_date.day
        
        # 获取当月的天数
        last_day_of_month = monthrange(check_date.year, check_date.month)[1]
        
        # 检查是否在配置的日期列表中
        for month_day in rule.frequency_config.month_days:
            if month_day == -1:
                # -1 表示月末
                if day == last_day_of_month:
                    return True
            elif month_day == day:
                return True
            elif month_day > last_day_of_month and day == last_day_of_month:
                # 如果配置的日期大于当月最大天数，则在月末执行
                # 例如：配置31号，但2月只有28/29天，则在28/29号执行
                return True
        
        return False
    
    def _should_execute_yearly(self, rule: RecurringRule, check_date: date) -> bool:
        """判断每年频率是否应该执行
        
        Args:
            rule: 周期规则
            check_date: 检查日期
            
        Returns:
            是否应该执行
        """
        # 每年在开始日期的同一天执行
        return (check_date.month == rule.start_date.month and 
                check_date.day == rule.start_date.day)
    
    def _should_execute_interval(self, rule: RecurringRule, check_date: date) -> bool:
        """判断间隔频率是否应该执行
        
        Args:
            rule: 周期规则
            check_date: 检查日期
            
        Returns:
            是否应该执行
        """
        # 计算从开始日期到检查日期的天数差
        days_diff = (check_date - rule.start_date).days
        
        # 检查是否是间隔天数的倍数
        interval = rule.frequency_config.interval_days
        return days_diff % interval == 0
    
    def get_next_execution_dates(
        self,
        rule: RecurringRule,
        start_date: date,
        count: int = 10
    ) -> List[date]:
        """获取接下来的执行日期列表
        
        Args:
            rule: 周期规则
            start_date: 开始日期
            count: 返回的日期数量
            
        Returns:
            执行日期列表
        """
        execution_dates = []
        current_date = start_date
        max_days = 365  # 最多检查一年
        days_checked = 0
        
        while len(execution_dates) < count and days_checked < max_days:
            if self.should_execute(rule, current_date):
                execution_dates.append(current_date)
            
            current_date += timedelta(days=1)
            days_checked += 1
        
        return execution_dates
    
    def get_execution_dates_in_range(
        self,
        rule: RecurringRule,
        start_date: date,
        end_date: date
    ) -> List[date]:
        """获取指定日期范围内的所有执行日期
        
        Args:
            rule: 周期规则
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            执行日期列表
        """
        execution_dates = []
        current_date = start_date
        
        while current_date <= end_date:
            if self.should_execute(rule, current_date):
                execution_dates.append(current_date)
            
            current_date += timedelta(days=1)
        
        return execution_dates
