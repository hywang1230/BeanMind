"""同步调度器

提供 GitHub 自动同步的定时任务调度
"""
import logging
from typing import Optional
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from backend.config.settings import settings

logger = logging.getLogger(__name__)

# 东八区时区
TIMEZONE_CN = timezone(timedelta(hours=8))


class SyncScheduler:
    """同步调度器
    
    定时执行 GitHub 同步任务
    """
    
    _scheduler: Optional[BackgroundScheduler] = None
    _job_id = "github_sync_job"
    
    def __init__(self):
        if SyncScheduler._scheduler is None:
            SyncScheduler._scheduler = BackgroundScheduler()
    
    @property
    def scheduler(self) -> BackgroundScheduler:
        """获取调度器实例"""
        return self._scheduler
    
    def start(self):
        """启动调度器"""
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("同步调度器已启动")
    
    def shutdown(self):
        """关闭调度器"""
        if self._scheduler.running:
            self._scheduler.shutdown()
            logger.info("同步调度器已关闭")
    
    def add_sync_job(self, interval_seconds: int = 300):
        """添加同步任务
        
        Args:
            interval_seconds: 同步间隔（秒），默认 300 秒（5 分钟）
        """
        # 移除已存在的任务
        existing_job = self._scheduler.get_job(self._job_id)
        if existing_job:
            self._scheduler.remove_job(self._job_id)
            logger.info(f"移除旧的同步任务")
        
        # 添加新任务
        self._scheduler.add_job(
            self._execute_sync,
            trigger="interval",
            seconds=interval_seconds,
            id=self._job_id,
            name="GitHub 自动同步",
            replace_existing=True,
            max_instances=1,  # 同时只能运行一个实例
            coalesce=True,    # 合并错过的任务
        )
        
        logger.info(f"添加同步任务: 每 {interval_seconds} 秒执行一次")
    
    def remove_sync_job(self):
        """移除同步任务"""
        existing_job = self._scheduler.get_job(self._job_id)
        if existing_job:
            self._scheduler.remove_job(self._job_id)
            logger.info("同步任务已移除")
    
    def _execute_sync(self):
        """执行同步任务"""
        from backend.config import get_db
        from backend.application.services.sync_service import SyncApplicationService
        
        logger.info("开始执行自动同步...")
        
        # 创建数据库会话
        db = next(get_db())
        try:
            sync_service = SyncApplicationService(db)
            
            # 检查是否配置了同步
            if not sync_service._get_sync_service().is_configured:
                logger.warning("GitHub 同步未配置，跳过自动同步")
                return
            
            # 执行同步
            result = sync_service.trigger_sync(
                message=f"Auto sync at {datetime.now(TIMEZONE_CN).strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            if result["success"]:
                logger.info(f"自动同步成功: {result['message']}")
            else:
                logger.warning(f"自动同步失败: {result['message']}")
                
        except Exception as e:
            logger.error(f"自动同步出错: {e}", exc_info=True)
        finally:
            db.close()
    
    def get_job_info(self) -> dict:
        """获取任务信息"""
        job = self._scheduler.get_job(self._job_id)
        if job:
            next_run = job.next_run_time
            return {
                "job_id": self._job_id,
                "name": job.name,
                "running": self._scheduler.running,
                "next_run_time": next_run.isoformat() if next_run else None,
                "interval_seconds": job.trigger.interval.total_seconds() if hasattr(job.trigger, 'interval') else None,
            }
        return {
            "job_id": None,
            "name": None,
            "running": self._scheduler.running,
            "next_run_time": None,
            "interval_seconds": None,
        }
    
    def trigger_now(self) -> dict:
        """立即触发一次同步"""
        self._execute_sync()
        return {"message": "同步任务已触发"}


# 单例实例
sync_scheduler = SyncScheduler()
