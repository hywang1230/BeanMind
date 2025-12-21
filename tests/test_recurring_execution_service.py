"""周期任务执行服务单元测试"""
import pytest
from datetime import date

from backend.domain.recurring.entities.recurring_rule import RecurringRule
from backend.domain.recurring.value_objects.frequency_config import FrequencyConfig, FrequencyType
from backend.domain.recurring.services.recurring_execution_service import RecurringExecutionService


@pytest.fixture
def execution_service():
    """创建执行服务实例"""
    return RecurringExecutionService()


@pytest.fixture
def daily_rule():
    """创建每日规则"""
    return RecurringRule(
        id="rule1",
        user_id="user1",
        name="每日记账",
        frequency_config=FrequencyConfig.daily(),
        transaction_template={
            "description": "每日记账",
            "postings": []
        },
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31)
    )


@pytest.fixture
def weekly_rule():
    """创建每周规则（周一、周三、周五）"""
    return RecurringRule(
        id="rule2",
        user_id="user1",
        name="每周记账",
        frequency_config=FrequencyConfig.weekly([1, 3, 5]),  # 周一、周三、周五
        transaction_template={
            "description": "每周记账",
            "postings": []
        },
        start_date=date(2025, 1, 1),
        is_active=True
    )


@pytest.fixture
def monthly_rule():
    """创建每月规则（每月1号和15号）"""
    return RecurringRule(
        id="rule3",
        user_id="user1",
        name="每月记账",
        frequency_config=FrequencyConfig.monthly([1, 15]),
        transaction_template={
            "description": "每月记账",
            "postings": []
        },
        start_date=date(2025, 1, 1),
        is_active=True
    )


@pytest.fixture
def month_end_rule():
    """创建月末规则"""
    return RecurringRule(
        id="rule4",
        user_id="user1",
        name="月末记账",
        frequency_config=FrequencyConfig.monthly([-1]),  # 月末
        transaction_template={
            "description": "月末记账",
            "postings": []
        },
        start_date=date(2025, 1, 1),
        is_active=True
    )


class TestRecurringExecutionService:
    """周期任务执行服务测试"""
    
    def test_daily_execution(self, execution_service, daily_rule):
        """测试每日执行"""
        # 在有效期内，每天都应该执行
        assert execution_service.should_execute(daily_rule, date(2025, 1, 1)) is True
        assert execution_service.should_execute(daily_rule, date(2025, 1, 15)) is True
        assert execution_service.should_execute(daily_rule, date(2025, 1, 31)) is True
        
        # 超出有效期，不应该执行
        assert execution_service.should_execute(daily_rule, date(2025, 2, 1)) is False
    
    def test_weekly_execution(self, execution_service, weekly_rule):
        """测试每周执行"""
        # 2025-01-06 是周一，应该执行
        assert execution_service.should_execute(weekly_rule, date(2025, 1, 6)) is True
        
        # 2025-01-08 是周三，应该执行
        assert execution_service.should_execute(weekly_rule, date(2025, 1, 8)) is True
        
        # 2025-01-10 是周五，应该执行
        assert execution_service.should_execute(weekly_rule, date(2025, 1, 10)) is True
        
        # 2025-01-07 是周二，不应该执行
        assert execution_service.should_execute(weekly_rule, date(2025, 1, 7)) is False
        
        # 2025-01-11 是周六，不应该执行
        assert execution_service.should_execute(weekly_rule, date(2025, 1, 11)) is False
    
    def test_monthly_execution(self, execution_service, monthly_rule):
        """测试每月执行"""
        # 1号应该执行
        assert execution_service.should_execute(monthly_rule, date(2025, 1, 1)) is True
        assert execution_service.should_execute(monthly_rule, date(2025, 2, 1)) is True
        
        # 15号应该执行
        assert execution_service.should_execute(monthly_rule, date(2025, 1, 15)) is True
        assert execution_service.should_execute(monthly_rule, date(2025, 2, 15)) is True
        
        # 其他日期不应该执行
        assert execution_service.should_execute(monthly_rule, date(2025, 1, 10)) is False
        assert execution_service.should_execute(monthly_rule, date(2025, 1, 20)) is False
    
    def test_month_end_execution(self, execution_service, month_end_rule):
        """测试月末执行"""
        # 1月31号（月末）应该执行
        assert execution_service.should_execute(month_end_rule, date(2025, 1, 31)) is True
        
        # 2月28号（月末）应该执行
        assert execution_service.should_execute(month_end_rule, date(2025, 2, 28)) is True
        
        # 非月末日期不应该执行
        assert execution_service.should_execute(month_end_rule, date(2025, 1, 30)) is False
        assert execution_service.should_execute(month_end_rule, date(2025, 2, 27)) is False
    
    def test_yearly_execution(self, execution_service):
        """测试每年执行"""
        yearly_rule = RecurringRule(
            id="rule5",
            user_id="user1",
            name="每年记账",
            frequency_config=FrequencyConfig.yearly(),
            transaction_template={
                "description": "每年记账",
                "postings": []
            },
            start_date=date(2025, 1, 15),  # 1月15号
            is_active=True
        )
        
        # 每年的1月15号应该执行
        assert execution_service.should_execute(yearly_rule, date(2025, 1, 15)) is True
        assert execution_service.should_execute(yearly_rule, date(2026, 1, 15)) is True
        
        # 其他日期不应该执行
        assert execution_service.should_execute(yearly_rule, date(2025, 1, 16)) is False
        assert execution_service.should_execute(yearly_rule, date(2025, 2, 15)) is False
    
    def test_interval_execution(self, execution_service):
        """测试间隔执行"""
        interval_rule = RecurringRule(
            id="rule6",
            user_id="user1",
            name="每3天记账",
            frequency_config=FrequencyConfig.interval(3),
            transaction_template={
                "description": "每3天记账",
                "postings": []
            },
            start_date=date(2025, 1, 1),
            is_active=True
        )
        
        # 开始日期应该执行
        assert execution_service.should_execute(interval_rule, date(2025, 1, 1)) is True
        
        # 间隔3天后应该执行
        assert execution_service.should_execute(interval_rule, date(2025, 1, 4)) is True
        assert execution_service.should_execute(interval_rule, date(2025, 1, 7)) is True
        assert execution_service.should_execute(interval_rule, date(2025, 1, 10)) is True
        
        # 非间隔日不应该执行
        assert execution_service.should_execute(interval_rule, date(2025, 1, 2)) is False
        assert execution_service.should_execute(interval_rule, date(2025, 1, 3)) is False
        assert execution_service.should_execute(interval_rule, date(2025, 1, 5)) is False
    
    def test_inactive_rule(self, execution_service, daily_rule):
        """测试未激活的规则"""
        daily_rule.deactivate()
        
        # 未激活的规则不应该执行
        assert execution_service.should_execute(daily_rule, date(2025, 1, 15)) is False
    
    def test_get_next_execution_dates(self, execution_service, weekly_rule):
        """测试获取接下来的执行日期"""
        # 从2025-01-01开始，获取接下来5次执行日期
        dates = execution_service.get_next_execution_dates(
            weekly_rule,
            date(2025, 1, 1),
            count=5
        )
        
        # 应该返回5个日期
        assert len(dates) == 5
        
        # 第一个日期应该是2025-01-01（周三）
        assert dates[0] == date(2025, 1, 1)
        
        # 第二个日期应该是2025-01-03（周五）
        assert dates[1] == date(2025, 1, 3)
    
    def test_get_execution_dates_in_range(self, execution_service, monthly_rule):
        """测试获取日期范围内的执行日期"""
        # 获取1月1日到2月28日之间的执行日期
        dates = execution_service.get_execution_dates_in_range(
            monthly_rule,
            date(2025, 1, 1),
            date(2025, 2, 28)
        )
        
        # 应该有4个日期：1/1, 1/15, 2/1, 2/15
        assert len(dates) == 4
        assert date(2025, 1, 1) in dates
        assert date(2025, 1, 15) in dates
        assert date(2025, 2, 1) in dates
        assert date(2025, 2, 15) in dates
    
    def test_monthly_with_31_in_february(self, execution_service):
        """测试2月处理31号的情况"""
        # 配置每月31号执行
        rule = RecurringRule(
            id="rule7",
            user_id="user1",
            name="每月31号",
            frequency_config=FrequencyConfig.monthly([31]),
            transaction_template={
                "description": "每月31号",
                "postings": []
            },
            start_date=date(2025, 1, 1),
            is_active=True
        )
        
        # 1月31号应该执行
        assert execution_service.should_execute(rule, date(2025, 1, 31)) is True
        
        # 2月28号应该执行（2月没有31号，在月末执行）
        assert execution_service.should_execute(rule, date(2025, 2, 28)) is True
        
        # 2月27号不应该执行
        assert execution_service.should_execute(rule, date(2025, 2, 27)) is False
