from agentuniverse.agent.action.tool.tool import Tool
from datetime import datetime, date
from typing import List, Optional
from decimal import Decimal
import logging

from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from backend.domain.budget.entities.budget import Budget, PeriodType
from backend.domain.budget.entities.budget_item import BudgetItem
from backend.domain.budget.services.budget_execution_service import BudgetExecutionService
from backend.infrastructure.persistence.beancount.repositories.transaction_repository_impl import TransactionRepositoryImpl
from backend.infrastructure.persistence.db.models.budget import Budget as BudgetModel
from backend.config.dependencies import get_beancount_service, get_db

logger = logging.getLogger(__name__)


class BudgetTool(Tool):
    """
    预算工具，用于查询预算信息及执行情况
    """
    
    def execute(self, start_date: str, end_date: str) -> str:
        """
        执行工具，查询预算信息及执行情况
        
        Args:
            start_date: 开始日期，格式为 YYYY-MM-DD
            end_date: 结束日期，格式为 YYYY-MM-DD
            
        Returns:
            格式化的预算执行情况文本
        """
        try:
            # 解析日期
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
            
            # 获取服务和会话
            beancount_service = get_beancount_service()
            db_session = next(get_db())
            
            try:
                transaction_repo = TransactionRepositoryImpl(beancount_service, db_session)
                budget_execution_service = BudgetExecutionService(transaction_repo)
                
                # 同步查询预算
                budgets = self._find_budgets_sync(db_session, start, end)
                
                if not budgets:
                    return "未找到符合日期范围的预算记录"
                
                # 计算执行情况 (会更新 budget 对象中的 items 状态)
                budget_execution_service.calculate_all_budgets_execution(budgets)
                
                # 格式化输出
                return self._format_budgets(budgets)
            finally:
                db_session.close()
                
        except Exception as e:
            logger.error(f"查询预算失败: {e}")
            return f"查询预算失败: {str(e)}"
    
    def _find_budgets_sync(self, session, start_date: date, end_date: date) -> List[Budget]:
        """同步方式查询预算"""
        stmt = select(BudgetModel).options(
            selectinload(BudgetModel.items)
        ).where(
            and_(
                BudgetModel.start_date <= end_date,
                (BudgetModel.end_date == None) | (BudgetModel.end_date >= start_date)
            )
        )
        
        result = session.execute(stmt)
        models = result.scalars().all()
        
        return [self._to_entity(model) for model in models]

    def _to_entity(self, model: BudgetModel) -> Budget:
        """将ORM模型转换为领域实体"""
        items = []
        for item_model in model.items:
            item = BudgetItem(
                id=item_model.id,
                budget_id=item_model.budget_id,
                account_pattern=item_model.account_pattern,
                amount=Decimal(str(item_model.amount)),
                currency=item_model.currency,
                spent=Decimal(str(item_model.spent)),
                created_at=item_model.created_at,
                updated_at=item_model.updated_at
            )
            items.append(item)
        
        return Budget(
            id=model.id,
            user_id=model.user_id,
            name=model.name,
            amount=Decimal(str(model.amount)),
            period_type=PeriodType(model.period_type),
            start_date=model.start_date,
            end_date=model.end_date,
            is_active=model.is_active,
            items=items,
            created_at=model.created_at,
            updated_at=model.updated_at
        )

    def _format_budgets(self, budgets: List[Budget]) -> str:
        """格式化预算详情"""
        lines = []
        lines.append(f"共找到 {len(budgets)} 个相关预算:\n")
        
        for budget in budgets:
            # 预算总体情况
            total_amount = budget.get_total_amount()
            total_spent = budget.get_total_spent()
            execution_rate = budget.get_execution_rate()
            remaining = total_amount - total_spent
            
            # 状态判定
            if execution_rate >= 100:
                status_text = "超支"
            elif execution_rate >= 80:
                status_text = "预警"
            else:
                status_text = "正常"
                
            lines.append(f"预算: {budget.name} [{status_text}]")
            lines.append(f"  总进度: {execution_rate:.1f}% (总额: {total_amount:,.2f} | 已用: {total_spent:,.2f} | 剩余: {remaining:,.2f})")
            
            # 分项详情
            lines.append("  分项详情:")
            for item in budget.items:
                if item.amount > 0:
                    # 有独立额度的项目
                    item_rate = item.get_usage_rate()
                    item_remaining = item.amount - item.spent
                    
                    # 分项状态
                    if item_rate >= 100:
                        item_status = "!"  # 超支标记
                    elif item_rate >= 80:
                        item_status = "*"  # 预警标记
                    else:
                        item_status = " "
                    
                    lines.append(f"    {item_status} [{item.account_pattern}] 进度: {item_rate:.1f}%")
                    lines.append(f"      额度: {item.amount:,.2f} | 已用: {item.spent:,.2f} | 剩余: {item_remaining:,.2f} {item.currency}")
                else:
                    # 共享额度的项目（额度为0）
                    lines.append(f"    - [{item.account_pattern}]")
                    lines.append(f"      已用: {item.spent:,.2f} {item.currency} (共享总额度)")
            
            lines.append("")
        
        return "\n".join(lines)
