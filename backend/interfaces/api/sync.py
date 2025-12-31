"""同步 API 端点

提供 GitHub 同步相关的 HTTP 接口
配置从环境变量读取，日志保存到数据库
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session

from backend.config import get_db
from backend.application.services.sync_service import SyncApplicationService


# 创建路由
router = APIRouter(prefix="/api/sync", tags=["同步管理"])


# DTO 定义
class SyncTriggerRequest(BaseModel):
    """同步触发请求"""
    message: Optional[str] = None


class PullRequest(BaseModel):
    """拉取请求"""
    force: bool = False  # 是否强制覆盖本地文件（危险操作）


class SyncConfigResponse(BaseModel):
    """同步配置响应"""
    github_repo: str
    github_branch: str
    github_token_configured: bool
    auto_sync_enabled: bool
    auto_sync_interval: int


class SyncStatusResponse(BaseModel):
    """同步状态响应"""
    is_configured: bool
    is_syncing: bool
    last_sync_at: Optional[str]
    last_sync_message: str
    last_sync_success: bool = True
    has_local_changes: bool
    has_remote_changes: bool
    repo: str
    branch: str


class SyncResultResponse(BaseModel):
    """同步结果响应"""
    success: bool
    message: str
    direction: Optional[str] = None
    pushed_files: list = []
    pulled_files: list = []
    synced_at: Optional[str] = None


class TestConnectionResponse(BaseModel):
    """连接测试响应"""
    success: bool
    message: str


class SyncLogResponse(BaseModel):
    """同步日志响应"""
    id: str
    direction: str
    success: bool
    message: str
    pushed_files: list
    pulled_files: list
    repo: str
    branch: str
    synced_at: Optional[str]


class SyncHistoryResponse(BaseModel):
    """同步历史响应"""
    logs: List[SyncLogResponse]
    total: int


def get_sync_service(db: Session = Depends(get_db)) -> SyncApplicationService:
    """获取同步应用服务"""
    return SyncApplicationService(db)


@router.get(
    "/config",
    response_model=SyncConfigResponse,
    summary="获取同步配置",
    description="获取当前同步配置（从环境变量读取，不返回敏感信息）"
)
async def get_config(
    sync_service: SyncApplicationService = Depends(get_sync_service)
):
    """获取同步配置"""
    return sync_service.get_config()


@router.get(
    "/status",
    response_model=SyncStatusResponse,
    summary="获取同步状态",
    description="获取当前同步状态信息"
)
async def get_status(
    sync_service: SyncApplicationService = Depends(get_sync_service)
):
    """获取同步状态"""
    return sync_service.get_status()


@router.get(
    "/history",
    response_model=SyncHistoryResponse,
    summary="获取同步历史",
    description="获取同步操作历史记录"
)
async def get_history(
    limit: int = Query(20, ge=1, le=100, description="返回数量限制"),
    sync_service: SyncApplicationService = Depends(get_sync_service)
):
    """获取同步历史"""
    logs = sync_service.get_history(limit)
    return {"logs": logs, "total": len(logs)}


@router.post(
    "",
    response_model=SyncResultResponse,
    summary="触发同步",
    description="执行完整同步（先推送后拉取，保护本地数据）"
)
async def trigger_sync(
    request: SyncTriggerRequest = SyncTriggerRequest(),
    sync_service: SyncApplicationService = Depends(get_sync_service)
):
    """触发同步"""
    return sync_service.trigger_sync(request.message)


@router.post(
    "/push",
    response_model=SyncResultResponse,
    summary="推送到 GitHub",
    description="将本地变更推送到 GitHub"
)
async def push(
    request: SyncTriggerRequest = SyncTriggerRequest(),
    sync_service: SyncApplicationService = Depends(get_sync_service)
):
    """推送到 GitHub"""
    return sync_service.push(request.message)


@router.post(
    "/pull",
    response_model=SyncResultResponse,
    summary="从 GitHub 拉取",
    description="从 GitHub 拉取更新（智能拉取，默认不覆盖本地修改的文件）"
)
async def pull(
    request: PullRequest = PullRequest(),
    sync_service: SyncApplicationService = Depends(get_sync_service)
):
    """从 GitHub 拉取
    
    智能拉取策略：
    - 默认情况下，只拉取本地不存在的文件
    - 如果本地文件有修改，会跳过拉取以保护本地数据
    - 设置 force=True 可以强制覆盖本地文件（危险操作）
    """
    return sync_service.pull(force=request.force)


@router.post(
    "/test",
    response_model=TestConnectionResponse,
    summary="测试连接",
    description="测试 GitHub 连接是否正常"
)
async def test_connection(
    sync_service: SyncApplicationService = Depends(get_sync_service)
):
    """测试 GitHub 连接"""
    success, message = sync_service.test_connection()
    return {"success": success, "message": message}


# ========== 自动同步调度器 API ==========

class SchedulerStatusResponse(BaseModel):
    """调度器状态响应"""
    job_id: Optional[str]
    name: Optional[str]
    running: bool
    next_run_time: Optional[str]
    interval_seconds: Optional[float]


@router.get(
    "/scheduler/status",
    response_model=SchedulerStatusResponse,
    summary="获取自动同步调度器状态",
    description="获取 GitHub 自动同步调度器的运行状态"
)
async def get_scheduler_status():
    """获取调度器状态"""
    from backend.infrastructure.scheduler import sync_scheduler
    return sync_scheduler.get_job_info()


@router.post(
    "/scheduler/trigger",
    summary="手动触发自动同步",
    description="立即触发一次自动同步任务"
)
async def trigger_scheduler():
    """手动触发同步"""
    from backend.infrastructure.scheduler import sync_scheduler
    return sync_scheduler.trigger_now()

