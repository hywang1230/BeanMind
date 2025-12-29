"""周期记账 API"""
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from backend.config import get_db, get_beancount_service
from backend.infrastructure.persistence.db.models import RecurringRule, RecurringExecution
from sqlalchemy.orm import Session
import json


router = APIRouter(prefix="/api/recurring", tags=["recurring"])


# Request/Response Models
class PostingTemplate(BaseModel):
    account: str
    amount: float
    currency: str


class TransactionTemplate(BaseModel):
    description: str
    postings: List[PostingTemplate]
    payee: Optional[str] = None
    tags: Optional[List[str]] = None


class FrequencyConfigModel(BaseModel):
    weekdays: Optional[List[int]] = None  # 1-7 (周一到周日)
    month_days: Optional[List[int]] = None  # 1-31 或 -1 表示月末
    interval_days: Optional[int] = None


class CreateRecurringRuleRequest(BaseModel):
    name: str
    frequency: str  # daily, weekly, biweekly, monthly, yearly
    frequency_config: FrequencyConfigModel
    transaction_template: TransactionTemplate
    start_date: date
    end_date: Optional[date] = None
    is_active: bool = True


class UpdateRecurringRuleRequest(BaseModel):
    name: Optional[str] = None
    frequency: Optional[str] = None
    frequency_config: Optional[FrequencyConfigModel] = None
    transaction_template: Optional[TransactionTemplate] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_active: Optional[bool] = None


class RecurringRuleResponse(BaseModel):
    id: str
    name: str
    frequency: str
    frequency_config: dict
    transaction_template: dict
    start_date: date
    end_date: Optional[date]
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class RecurringExecutionResponse(BaseModel):
    id: str
    rule_id: str
    execution_date: date
    transaction_id: Optional[str]
    status: str
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class ExecuteRuleRequest(BaseModel):
    date: date


def db_model_to_response(rule: RecurringRule) -> RecurringRuleResponse:
    """将数据库模型转换为响应模型"""
    frequency_config = {}
    if rule.frequency_config:
        try:
            frequency_config = json.loads(rule.frequency_config)
        except json.JSONDecodeError:
            frequency_config = {}
    
    transaction_template = {}
    if rule.transaction_template:
        try:
            transaction_template = json.loads(rule.transaction_template)
        except json.JSONDecodeError:
            transaction_template = {}
    
    return RecurringRuleResponse(
        id=rule.id,
        name=rule.name,
        frequency=rule.frequency.lower() if rule.frequency else "monthly",
        frequency_config=frequency_config,
        transaction_template=transaction_template,
        start_date=rule.start_date,
        end_date=rule.end_date,
        is_active=rule.is_active,
        created_at=rule.created_at.isoformat() if rule.created_at else None,
        updated_at=rule.updated_at.isoformat() if rule.updated_at else None
    )


@router.get("/rules", response_model=List[RecurringRuleResponse])
def get_recurring_rules(db: Session = Depends(get_db)):
    """获取所有周期规则"""
    rules = db.query(RecurringRule).order_by(RecurringRule.created_at.desc()).all()
    return [db_model_to_response(rule) for rule in rules]


@router.post("/rules", response_model=RecurringRuleResponse)
def create_recurring_rule(
    request: CreateRecurringRuleRequest,
    db: Session = Depends(get_db)
):
    """创建周期规则"""
    # 将频率转换为大写存储
    frequency = request.frequency.upper()
    
    # 验证频率配置
    if frequency == "WEEKLY" or frequency == "BIWEEKLY":
        if not request.frequency_config.weekdays:
            raise HTTPException(status_code=400, detail="周频率必须指定weekdays")
    elif frequency == "MONTHLY":
        if not request.frequency_config.month_days:
            raise HTTPException(status_code=400, detail="月频率必须指定month_days")
    
    rule = RecurringRule(
        user_id="default_user",  # TODO: 从认证中获取
        name=request.name,
        frequency=frequency,
        frequency_config=json.dumps(request.frequency_config.model_dump(), ensure_ascii=False),
        transaction_template=json.dumps(request.transaction_template.model_dump(), ensure_ascii=False),
        start_date=request.start_date,
        end_date=request.end_date,
        is_active=request.is_active
    )
    
    db.add(rule)
    db.commit()
    db.refresh(rule)
    
    return db_model_to_response(rule)


@router.get("/rules/{rule_id}", response_model=RecurringRuleResponse)
def get_recurring_rule(rule_id: str, db: Session = Depends(get_db)):
    """获取单个周期规则"""
    rule = db.query(RecurringRule).filter(RecurringRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    return db_model_to_response(rule)


@router.put("/rules/{rule_id}", response_model=RecurringRuleResponse)
def update_recurring_rule(
    rule_id: str,
    request: UpdateRecurringRuleRequest,
    db: Session = Depends(get_db)
):
    """更新周期规则"""
    rule = db.query(RecurringRule).filter(RecurringRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    
    if request.name is not None:
        rule.name = request.name
    
    if request.frequency is not None:
        rule.frequency = request.frequency.upper()
    
    if request.frequency_config is not None:
        rule.frequency_config = json.dumps(request.frequency_config.model_dump(), ensure_ascii=False)
    
    if request.transaction_template is not None:
        rule.transaction_template = json.dumps(request.transaction_template.model_dump(), ensure_ascii=False)
    
    if request.start_date is not None:
        rule.start_date = request.start_date
    
    if request.end_date is not None:
        rule.end_date = request.end_date
    
    if request.is_active is not None:
        rule.is_active = request.is_active
    
    db.commit()
    db.refresh(rule)
    
    return db_model_to_response(rule)


@router.delete("/rules/{rule_id}")
def delete_recurring_rule(rule_id: str, db: Session = Depends(get_db)):
    """删除周期规则"""
    rule = db.query(RecurringRule).filter(RecurringRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    
    db.delete(rule)
    db.commit()
    
    return {"message": "删除成功"}


@router.post("/rules/{rule_id}/execute", response_model=RecurringExecutionResponse)
def execute_recurring_rule(
    rule_id: str,
    request: ExecuteRuleRequest,
    db: Session = Depends(get_db)
):
    """手动执行周期规则"""
    rule = db.query(RecurringRule).filter(RecurringRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    
    # 获取交易模板
    try:
        template = json.loads(rule.transaction_template)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="交易模板格式错误")
    
    # 构建交易
    beancount_service = get_beancount_service()
    
    postings = []
    for posting in template.get("postings", []):
        postings.append({
            "account": posting["account"],
            "amount": str(posting["amount"]),
            "currency": posting["currency"]
        })
    
    try:
        # 构建交易数据字典
        transaction_data = {
            "date": request.date.isoformat(),
            "description": template.get("description", ""),
            "postings": [
                {
                    "account": p["account"],
                    "amount": float(p["amount"]),
                    "currency": p["currency"]
                }
                for p in postings
            ],
            "payee": template.get("payee"),
            "tags": template.get("tags")
        }
        
        # 创建交易
        transaction_id = beancount_service.append_transaction(transaction_data)
        
        # 记录执行历史
        execution = RecurringExecution(
            rule_id=rule.id,
            executed_date=request.date,
            transaction_id=transaction_id,
            status="SUCCESS"
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)
        
        return RecurringExecutionResponse(
            id=execution.id,
            rule_id=execution.rule_id,
            execution_date=execution.executed_date,
            transaction_id=execution.transaction_id,
            status=execution.status,
            created_at=execution.created_at.isoformat() if execution.created_at else None
        )
    except Exception as e:
        # 记录失败的执行
        execution = RecurringExecution(
            rule_id=rule.id,
            executed_date=request.date,
            status="FAILED"
        )
        db.add(execution)
        db.commit()
        
        raise HTTPException(status_code=500, detail=f"执行失败: {str(e)}")


@router.get("/executions", response_model=List[RecurringExecutionResponse])
def get_recurring_executions(
    rule_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取执行历史"""
    query = db.query(RecurringExecution)
    
    if rule_id:
        query = query.filter(RecurringExecution.rule_id == rule_id)
    
    executions = query.order_by(RecurringExecution.created_at.desc()).limit(100).all()
    
    return [
        RecurringExecutionResponse(
            id=ex.id,
            rule_id=ex.rule_id,
            execution_date=ex.executed_date,
            transaction_id=ex.transaction_id,
            status=ex.status,
            created_at=ex.created_at.isoformat() if ex.created_at else None
        )
        for ex in executions
    ]


# ==================== 调度器相关 API ====================

@router.get("/scheduler/status")
def get_scheduler_status():
    """获取调度器状态"""
    from backend.infrastructure.scheduler import recurring_scheduler
    
    job_info = recurring_scheduler.get_job_info()
    
    return {
        "enabled": True,
        "running": job_info.get("running", False),
        "job_id": job_info.get("id"),
        "job_name": job_info.get("name"),
        "next_run_time": job_info.get("next_run_time"),
    }


@router.post("/scheduler/execute")
def trigger_scheduler_execution(db: Session = Depends(get_db)):
    """手动触发调度器执行当天的周期任务"""
    from backend.application.services.recurring_service import RecurringApplicationService
    
    today = date.today()
    service = RecurringApplicationService(db)
    
    results = service.execute_due_rules(today)
    
    success_count = sum(1 for r in results if r.get("status") == "SUCCESS")
    fail_count = sum(1 for r in results if r.get("status") == "FAILED")
    skip_count = sum(1 for r in results if r.get("status") == "SKIPPED")
    
    return {
        "message": "执行完成",
        "date": today.isoformat(),
        "summary": {
            "total": len(results),
            "success": success_count,
            "failed": fail_count,
            "skipped": skip_count,
        },
        "results": results,
    }


@router.get("/scheduler/pending")
def get_pending_rules(db: Session = Depends(get_db)):
    """获取今天待执行的规则列表"""
    from backend.application.services.recurring_service import RecurringApplicationService
    
    today = date.today()
    service = RecurringApplicationService(db)
    
    pending_rules = service.get_pending_rules(today)
    
    return {
        "date": today.isoformat(),
        "count": len(pending_rules),
        "rules": pending_rules,
    }
