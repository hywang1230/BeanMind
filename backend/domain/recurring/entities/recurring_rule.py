"""周期规则领域实体"""
from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Dict, Any
import json

from backend.domain.recurring.value_objects.frequency_config import FrequencyConfig, FrequencyType


@dataclass
class RecurringRule:
    """周期规则实体
    
    定义周期性自动执行的交易规则
    """
    id: str
    user_id: str
    name: str
    frequency_config: FrequencyConfig
    transaction_template: Dict[str, Any]  # 交易模板（JSON格式）
    start_date: date
    end_date: Optional[date] = None
    is_active: bool = True
    created_at: Optional[date] = None
    updated_at: Optional[date] = None
    
    def __post_init__(self):
        """验证周期规则"""
        # 验证名称
        if not self.name or not self.name.strip():
            raise ValueError("周期规则名称不能为空")
        
        # 验证日期
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("结束日期不能早于开始日期")
        
        # 验证交易模板
        if not self.transaction_template:
            raise ValueError("交易模板不能为空")
        
        # 验证交易模板必须包含的字段
        required_fields = ["description", "postings"]
        for field_name in required_fields:
            if field_name not in self.transaction_template:
                raise ValueError(f"交易模板缺少必需字段: {field_name}")
    
    def activate(self):
        """启用规则"""
        self.is_active = True
    
    def deactivate(self):
        """停用规则"""
        self.is_active = False
    
    def is_valid_on_date(self, check_date: date) -> bool:
        """检查规则在指定日期是否有效
        
        Args:
            check_date: 检查日期
            
        Returns:
            是否有效
        """
        if not self.is_active:
            return False
        
        if check_date < self.start_date:
            return False
        
        if self.end_date and check_date > self.end_date:
            return False
        
        return True
    
    def update_transaction_template(self, template: Dict[str, Any]):
        """更新交易模板
        
        Args:
            template: 新的交易模板
        """
        # 验证模板
        required_fields = ["description", "postings"]
        for field_name in required_fields:
            if field_name not in template:
                raise ValueError(f"交易模板缺少必需字段: {field_name}")
        
        self.transaction_template = template
    
    def get_transaction_template_json(self) -> str:
        """获取JSON格式的交易模板"""
        return json.dumps(self.transaction_template, ensure_ascii=False)
    
    def get_frequency_config_json(self) -> str:
        """获取JSON格式的频率配置"""
        return json.dumps(self.frequency_config.to_dict(), ensure_ascii=False)
