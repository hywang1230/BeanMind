"""周期记账调度器

使用 APScheduler 实现每天定时执行周期记账任务
"""
import logging
from datetime import date, datetime
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


class RecurringScheduler:
    """周期记账调度器
    
    负责在指定时间执行周期记账任务
    """
    
    _instance: Optional['RecurringScheduler'] = None
    _scheduler: Optional[BackgroundScheduler] = None
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._scheduler = BackgroundScheduler()
        return cls._instance
    
    @property
    def scheduler(self) -> BackgroundScheduler:
        """获取调度器实例"""
        return self._scheduler
    
    def start(self):
        """启动调度器"""
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("周期记账调度器已启动")
    
    def shutdown(self):
        """关闭调度器"""
        if self._scheduler.running:
            self._scheduler.shutdown()
            logger.info("周期记账调度器已关闭")
    
    def add_recurring_job(
        self,
        hour: int = 12,
        minute: int = 0,
        timezone: str = "Asia/Shanghai"
    ):
        """添加周期记账定时任务
        
        Args:
            hour: 执行时间（小时，24小时制）
            minute: 执行时间（分钟）
            timezone: 时区
        """
        from backend.application.services.recurring_service import RecurringApplicationService
        
        job_id = "recurring_transaction_job"
        
        # 移除已存在的同名任务
        existing_job = self._scheduler.get_job(job_id)
        if existing_job:
            self._scheduler.remove_job(job_id)
            logger.info(f"已移除旧的周期记账任务: {job_id}")
        
        # 添加新任务
        self._scheduler.add_job(
            func=self._execute_recurring_tasks,
            trigger=CronTrigger(
                hour=hour,
                minute=minute,
                timezone=timezone
            ),
            id=job_id,
            name="每日周期记账任务",
            replace_existing=True,
            misfire_grace_time=3600,  # 允许错过1小时内的任务
        )
        
        logger.info(f"已添加周期记账定时任务: 每天 {hour:02d}:{minute:02d} ({timezone}) 执行")
    
    def _execute_recurring_tasks(self):
        """执行周期记账任务"""
        logger.info("开始执行周期记账任务...")
        
        try:
            from backend.application.services.recurring_service import RecurringApplicationService
            from backend.config import get_db_session
            
            # 获取数据库会话
            db = get_db_session()
            
            try:
                service = RecurringApplicationService(db)
                today = date.today()
                
                # 执行今天应该执行的所有周期任务
                results = service.execute_due_rules(today)
                
                success_count = sum(1 for r in results if r.get("status") == "SUCCESS")
                fail_count = sum(1 for r in results if r.get("status") == "FAILED")
                skip_count = sum(1 for r in results if r.get("status") == "SKIPPED")
                
                logger.info(
                    f"周期记账任务执行完成: "
                    f"成功 {success_count}, 失败 {fail_count}, 跳过 {skip_count}"
                )
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"周期记账任务执行失败: {str(e)}", exc_info=True)
    
    def execute_now(self):
        """立即执行周期记账任务（用于手动触发或测试）"""
        logger.info("手动触发周期记账任务执行")
        self._execute_recurring_tasks()
    
    def get_next_run_time(self) -> Optional[datetime]:
        """获取下次执行时间"""
        job = self._scheduler.get_job("recurring_transaction_job")
        if job:
            return job.next_run_time
        return None
    
    def get_job_info(self) -> dict:
        """获取任务信息"""
        job = self._scheduler.get_job("recurring_transaction_job")
        if job:
            return {
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "running": self._scheduler.running,
            }
        return {
            "id": None,
            "name": None,
            "next_run_time": None,
            "running": self._scheduler.running,
        }


# 全局调度器实例
recurring_scheduler = RecurringScheduler()

