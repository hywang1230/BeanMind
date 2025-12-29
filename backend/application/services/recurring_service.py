"""周期记账应用服务

负责执行周期记账任务的业务逻辑
"""
import logging
import json
from datetime import date
from typing import List, Dict, Any

from sqlalchemy.orm import Session

from backend.domain.recurring.entities.recurring_rule import RecurringRule as RecurringRuleDomain
from backend.domain.recurring.services.recurring_execution_service import RecurringExecutionService
from backend.domain.recurring.value_objects.frequency_config import FrequencyConfig, FrequencyType
from backend.infrastructure.persistence.db.models import RecurringRule, RecurringExecution
from backend.infrastructure.persistence.beancount.beancount_service import BeancountService

logger = logging.getLogger(__name__)


class RecurringApplicationService:
    """周期记账应用服务
    
    协调领域服务和基础设施，执行周期记账任务
    """
    
    def __init__(self, db: Session):
        """初始化服务
        
        Args:
            db: 数据库会话
        """
        self.db = db
        self.execution_service = RecurringExecutionService()
    
    def execute_due_rules(self, execution_date: date) -> List[Dict[str, Any]]:
        """执行当天应该执行的所有周期规则
        
        Args:
            execution_date: 执行日期
            
        Returns:
            执行结果列表
        """
        results = []
        
        # 获取所有启用的规则
        active_rules = self.db.query(RecurringRule).filter(
            RecurringRule.is_active == True
        ).all()
        
        logger.info(f"找到 {len(active_rules)} 个启用的周期规则")
        
        for rule in active_rules:
            result = self._process_rule(rule, execution_date)
            results.append(result)
        
        return results
    
    def _process_rule(self, rule: RecurringRule, execution_date: date) -> Dict[str, Any]:
        """处理单个规则
        
        Args:
            rule: 数据库规则模型
            execution_date: 执行日期
            
        Returns:
            执行结果
        """
        result = {
            "rule_id": rule.id,
            "rule_name": rule.name,
            "date": execution_date.isoformat(),
            "status": "PENDING",
            "message": "",
            "transaction_id": None,
        }
        
        try:
            # 检查是否已经执行过
            existing_execution = self.db.query(RecurringExecution).filter(
                RecurringExecution.rule_id == rule.id,
                RecurringExecution.executed_date == execution_date,
                RecurringExecution.status == "SUCCESS"
            ).first()
            
            if existing_execution:
                result["status"] = "SKIPPED"
                result["message"] = "今日已执行过"
                logger.info(f"规则 {rule.name} ({rule.id}) 今日已执行，跳过")
                return result
            
            # 转换为领域实体
            domain_rule = self._to_domain_entity(rule)
            
            # 检查是否应该执行
            if not self.execution_service.should_execute(domain_rule, execution_date):
                result["status"] = "SKIPPED"
                result["message"] = "不满足执行条件"
                logger.info(f"规则 {rule.name} ({rule.id}) 不满足执行条件，跳过")
                return result
            
            # 执行交易
            transaction_id = self._execute_transaction(rule, execution_date)
            
            # 记录执行成功
            execution = RecurringExecution(
                rule_id=rule.id,
                executed_date=execution_date,
                transaction_id=transaction_id,
                status="SUCCESS"
            )
            self.db.add(execution)
            self.db.commit()
            
            result["status"] = "SUCCESS"
            result["transaction_id"] = transaction_id
            result["message"] = "执行成功"
            
            logger.info(f"规则 {rule.name} ({rule.id}) 执行成功，交易ID: {transaction_id}")
            
        except Exception as e:
            # 记录执行失败
            execution = RecurringExecution(
                rule_id=rule.id,
                executed_date=execution_date,
                status="FAILED"
            )
            self.db.add(execution)
            self.db.commit()
            
            result["status"] = "FAILED"
            result["message"] = str(e)
            
            logger.error(f"规则 {rule.name} ({rule.id}) 执行失败: {str(e)}", exc_info=True)
        
        return result
    
    def _to_domain_entity(self, rule: RecurringRule) -> RecurringRuleDomain:
        """将数据库模型转换为领域实体
        
        Args:
            rule: 数据库规则模型
            
        Returns:
            领域规则实体
        """
        # 解析频率配置
        frequency_config_data = {}
        if rule.frequency_config:
            try:
                frequency_config_data = json.loads(rule.frequency_config)
            except json.JSONDecodeError:
                pass
        
        # 构建频率配置
        frequency_type = FrequencyType(rule.frequency.upper())
        frequency_config = FrequencyConfig(
            frequency_type=frequency_type,
            weekdays=frequency_config_data.get("weekdays"),
            month_days=frequency_config_data.get("month_days"),
            interval_days=frequency_config_data.get("interval_days"),
        )
        
        # 解析交易模板
        transaction_template = {}
        if rule.transaction_template:
            try:
                transaction_template = json.loads(rule.transaction_template)
            except json.JSONDecodeError:
                transaction_template = {"description": "未知交易", "postings": []}
        
        return RecurringRuleDomain(
            id=rule.id,
            user_id=rule.user_id,
            name=rule.name,
            frequency_config=frequency_config,
            transaction_template=transaction_template,
            start_date=rule.start_date,
            end_date=rule.end_date,
            is_active=rule.is_active,
            created_at=rule.created_at.date() if rule.created_at else None,
            updated_at=rule.updated_at.date() if rule.updated_at else None,
        )
    
    def _execute_transaction(self, rule: RecurringRule, execution_date: date) -> str:
        """执行交易
        
        Args:
            rule: 周期规则
            execution_date: 执行日期
            
        Returns:
            交易ID
        """
        from backend.config import get_beancount_service
        
        # 解析交易模板
        template = json.loads(rule.transaction_template)
        
        # 构建交易数据
        postings = []
        for posting in template.get("postings", []):
            postings.append({
                "account": posting["account"],
                "amount": float(posting["amount"]),
                "currency": posting["currency"]
            })
        
        transaction_data = {
            "date": execution_date.isoformat(),
            "description": template.get("description", "周期记账"),
            "postings": postings,
            "payee": template.get("payee"),
            "tags": template.get("tags", []) + ["recurring"],  # 添加 recurring 标签
        }
        
        # 创建交易
        beancount_service = get_beancount_service()
        transaction_id = beancount_service.append_transaction(transaction_data)
        
        return transaction_id
    
    def get_pending_rules(self, check_date: date) -> List[Dict[str, Any]]:
        """获取指定日期待执行的规则列表
        
        Args:
            check_date: 检查日期
            
        Returns:
            待执行规则列表
        """
        pending_rules = []
        
        active_rules = self.db.query(RecurringRule).filter(
            RecurringRule.is_active == True
        ).all()
        
        for rule in active_rules:
            # 检查是否已执行
            existing_execution = self.db.query(RecurringExecution).filter(
                RecurringExecution.rule_id == rule.id,
                RecurringExecution.executed_date == check_date,
                RecurringExecution.status == "SUCCESS"
            ).first()
            
            if existing_execution:
                continue
            
            # 转换并检查是否应该执行
            domain_rule = self._to_domain_entity(rule)
            if self.execution_service.should_execute(domain_rule, check_date):
                pending_rules.append({
                    "id": rule.id,
                    "name": rule.name,
                    "frequency": rule.frequency,
                    "template": json.loads(rule.transaction_template) if rule.transaction_template else {},
                })
        
        return pending_rules

