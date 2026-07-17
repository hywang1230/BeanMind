"""BeanMind 单机 FastAPI 应用入口。"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.config.logging_config import setup_logging
from backend.interfaces.errors import ApiError


setup_logging(log_level=settings.LOG_LEVEL, log_dir=settings.LOG_DIR)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """初始化应用数据和可重建账本投影。"""
    from backend.config.dependencies import get_db_session
    from backend.infrastructure.persistence.init_db import init_database
    from backend.infrastructure.persistence.ledger_projection import LedgerProjectionService

    init_database(str(settings.DATABASE_FILE))
    database = get_db_session()
    try:
        result = LedgerProjectionService(database, settings.LEDGER_FILE).ensure_current()
        logger.info("账本查询投影已就绪: %s", result)
    except Exception:
        logger.exception("账本查询投影初始化失败，已标记为 DIRTY")
    finally:
        database.close()

    recurring_scheduler = None
    if settings.SCHEDULER_ENABLED:
        try:
            from backend.infrastructure.scheduler.recurring_scheduler import (
                recurring_scheduler as configured_scheduler,
            )
        except ModuleNotFoundError as exc:
            if exc.name != "apscheduler":
                raise
            logger.warning("未安装 apscheduler，跳过周期记账调度器")
        else:
            recurring_scheduler = configured_scheduler
            recurring_scheduler.start()
            recurring_scheduler.add_recurring_job(
                hour=settings.SCHEDULER_HOUR,
                minute=settings.SCHEDULER_MINUTE,
                timezone=settings.SCHEDULER_TIMEZONE,
            )

    yield

    if recurring_scheduler is not None:
        recurring_scheduler.shutdown()


app = FastAPI(
    title="BeanMind API",
    description="基于 Beancount 的单机个人财务系统",
    version="0.2.0",
    debug=settings.DEBUG,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ApiError)
def handle_api_error(request: Request, error: ApiError):
    return JSONResponse(
        status_code=error.status_code,
        content={"code": error.code, "message": error.message, "details": error.details},
    )

from backend.interfaces.api import account as account_api
from backend.interfaces.api import budget as budget_api
from backend.interfaces.api import dashboard as dashboard_api
from backend.interfaces.api import exchange_rate as exchange_rate_api
from backend.interfaces.api import monthly_report as monthly_report_api
from backend.interfaces.api import recurring as recurring_api
from backend.interfaces.api import reports as reports_api
from backend.interfaces.api import statistics as statistics_api
from backend.interfaces.api import transaction as transaction_api


for router in (
    account_api.router,
    transaction_api.router,
    statistics_api.router,
    recurring_api.router,
    reports_api.router,
    exchange_rate_api.router,
    budget_api.router,
    dashboard_api.router,
    monthly_report_api.router,
):
    app.include_router(router)


@app.get("/api")
def read_root():
    return {"message": "Welcome to BeanMind API", "version": "0.2.0", "status": "healthy"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/config")
def get_config():
    """仅公开前端展示需要的非敏感状态。"""
    return {
        "single_machine": True,
        "backup_managed_externally": True,
        "recurring_enabled": settings.SCHEDULER_ENABLED,
        "llm_enabled": settings.LLM_ENABLED,
        "llm_model": settings.LLM_MODEL if settings.LLM_ENABLED else None,
    }


FRONTEND_DIST_DIR = Path(__file__).parent.parent / "frontend" / "dist"
if FRONTEND_DIST_DIR.exists():
    assets_dir = FRONTEND_DIST_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{path:path}")
    def serve_spa(request: Request, path: str):
        if path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        file_path = FRONTEND_DIST_DIR / path
        if file_path.is_file():
            return FileResponse(file_path)
        index_path = FRONTEND_DIST_DIR / "index.html"
        if index_path.is_file():
            return FileResponse(index_path)
        return JSONResponse(status_code=404, content={"detail": "Frontend not built"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host=settings.API_HOST, port=settings.API_PORT, reload=settings.DEBUG)
