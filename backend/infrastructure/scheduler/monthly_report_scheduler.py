"""月报调度器"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.application.services.monthly_report_service import MonthlyReportApplicationService
from backend.config import get_beancount_service, get_db_session, settings
from backend.domain.analysis.monthly_report_facts_service import MonthlyReportFactsService
from backend.infrastructure.intelligence.skills.monthly_report import (
    MonthlyReportAgent,
    MonthlyReportModelConfig,
)
from backend.infrastructure.persistence.beancount.repositories.transaction_repository_impl import (
    TransactionRepositoryImpl,
)
from backend.infrastructure.persistence.db.repositories.monthly_report_repository import (
    MonthlyReportRepository,
)

logger = logging.getLogger(__name__)


class MonthlyReportScheduler:
    """月报定时任务调度器"""

    _instance: Optional["MonthlyReportScheduler"] = None
    _scheduler: Optional[BackgroundScheduler] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._scheduler = BackgroundScheduler()
        return cls._instance

    @property
    def scheduler(self) -> BackgroundScheduler:
        return self._scheduler

    def start(self):
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("月报调度器已启动")

    def shutdown(self):
        if self._scheduler.running:
            self._scheduler.shutdown()
            logger.info("月报调度器已关闭")

    def add_monthly_job(self, day: int, hour: int, minute: int, timezone: str):
        job_id = "monthly_report_job"
        existing_job = self._scheduler.get_job(job_id)
        if existing_job:
            self._scheduler.remove_job(job_id)

        self._scheduler.add_job(
            func=self._execute_monthly_report,
            trigger=CronTrigger(day=day, hour=hour, minute=minute, timezone=timezone),
            id=job_id,
            name="月报自动生成任务",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        logger.info("已添加月报定时任务")

    def _build_service(self, db_session) -> MonthlyReportApplicationService:
        beancount_service = get_beancount_service()
        transaction_repository = TransactionRepositoryImpl(beancount_service, db_session)
        report_repository = MonthlyReportRepository(db_session)
        facts_service = MonthlyReportFactsService()
        agent = MonthlyReportAgent(
            MonthlyReportModelConfig(
                provider=settings.LLM_PROVIDER,
                model=settings.LLM_MODEL_NAME,
                base_url=settings.LLM_BASE_URL,
                api_key=settings.LLM_API_KEY,
                temperature=settings.LLM_TEMPERATURE,
            )
        )
        return MonthlyReportApplicationService(
            report_repository=report_repository,
            transaction_repository=transaction_repository,
            beancount_service=beancount_service,
            facts_service=facts_service,
            agent=agent,
        )

    def _execute_monthly_report(self):
        db = get_db_session()
        try:
            service = self._build_service(db)
            last_month_end = date.today().replace(day=1) - timedelta(days=1)
            target_month = last_month_end.strftime("%Y-%m")
            service.try_generate_report(target_month, regenerate=True)
            logger.info("月报自动生成完成: %s", target_month)
        except Exception as exc:
            logger.error("月报自动生成失败: %s", exc, exc_info=True)
        finally:
            db.close()

    def execute_now(self):
        self._execute_monthly_report()

    def get_next_run_time(self) -> Optional[datetime]:
        job = self._scheduler.get_job("monthly_report_job")
        if job:
            return job.next_run_time
        return None


monthly_report_scheduler = MonthlyReportScheduler()
