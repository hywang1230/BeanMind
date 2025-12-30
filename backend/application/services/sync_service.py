"""同步应用服务

协调同步基础设施，配置从环境变量读取，日志保存到数据库
"""
from typing import Optional, Tuple, List
from datetime import datetime
import logging

from sqlalchemy.orm import Session

from backend.config.settings import settings
from backend.infrastructure.backup.github_sync_service import GitHubSyncService
from backend.infrastructure.backup.sync_models import (
    SyncStatus, SyncResult, SyncConfig, SyncDirection
)
from backend.infrastructure.persistence.db.repositories.sync_log_repository import SyncLogRepository

logger = logging.getLogger(__name__)


class SyncApplicationService:
    """同步应用服务
    
    配置从环境变量读取，同步日志保存到数据库
    """
    
    def __init__(self, session: Session):
        """初始化同步服务
        
        Args:
            session: 数据库会话
        """
        self._session = session
        self._log_repo = SyncLogRepository(session)
        self._sync_service: Optional[GitHubSyncService] = None
    
    def _get_config_from_env(self) -> SyncConfig:
        """从环境变量读取同步配置"""
        return SyncConfig(
            github_token=settings.GITHUB_TOKEN,
            github_repo=settings.GITHUB_REPO,
            github_branch=settings.GITHUB_BRANCH,
            auto_sync_enabled=settings.GITHUB_SYNC_AUTO_ENABLED,
            auto_sync_interval=settings.GITHUB_SYNC_AUTO_INTERVAL
        )
    
    def _get_sync_service(self) -> GitHubSyncService:
        """获取或创建同步服务实例"""
        if self._sync_service is None:
            config = self._get_config_from_env()
            self._sync_service = GitHubSyncService(config)
        return self._sync_service
    
    def get_config(self) -> dict:
        """获取同步配置（不返回敏感信息）
        
        Returns:
            配置字典（Token 仅返回是否已配置）
        """
        config = self._get_config_from_env()
        return {
            "github_repo": config.github_repo,
            "github_branch": config.github_branch,
            "github_token_configured": bool(config.github_token),
            "auto_sync_enabled": config.auto_sync_enabled,
            "auto_sync_interval": config.auto_sync_interval
        }
    
    def test_connection(self) -> Tuple[bool, str]:
        """测试 GitHub 连接
        
        Returns:
            (成功与否, 消息)
        """
        service = self._get_sync_service()
        return service.test_connection()
    
    def get_status(self) -> dict:
        """获取同步状态
        
        Returns:
            状态字典
        """
        service = self._get_sync_service()
        status = service.get_status()
        
        # 获取上次同步信息
        last_log = self._log_repo.get_last()
        
        return {
            "is_configured": status.is_configured,
            "is_syncing": status.is_syncing,
            "last_sync_at": last_log.get("synced_at") if last_log else None,
            "last_sync_message": last_log.get("message", "") if last_log else "",
            "last_sync_success": last_log.get("success", True) if last_log else True,
            "has_local_changes": status.has_local_changes,
            "has_remote_changes": status.has_remote_changes,
            "repo": status.repo,
            "branch": status.branch
        }
    
    def get_history(self, limit: int = 20) -> List[dict]:
        """获取同步历史
        
        Args:
            limit: 返回数量限制
            
        Returns:
            同步日志列表
        """
        return self._log_repo.get_recent(limit)
    
    def trigger_sync(self, message: Optional[str] = None) -> dict:
        """触发同步
        
        Args:
            message: 可选的提交消息
            
        Returns:
            同步结果字典
        """
        service = self._get_sync_service()
        
        if not service.is_configured:
            return {
                "success": False,
                "message": "请先配置 GitHub 同步（设置环境变量 GITHUB_TOKEN 和 GITHUB_REPO）"
            }
        
        commit_message = message or f"Sync from BeanMind at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        result = service.sync(commit_message)
        
        # 保存同步日志
        config = self._get_config_from_env()
        self._log_repo.add(
            direction=result.direction.value,
            success=result.success,
            message=result.message,
            pushed_files=result.pushed_files,
            pulled_files=result.pulled_files,
            repo=config.github_repo,
            branch=config.github_branch
        )
        
        return {
            "success": result.success,
            "message": result.message,
            "direction": result.direction.value,
            "pushed_files": result.pushed_files,
            "pulled_files": result.pulled_files,
            "synced_at": result.synced_at.isoformat()
        }
    
    def push(self, message: Optional[str] = None) -> dict:
        """推送到 GitHub
        
        Args:
            message: 可选的提交消息
            
        Returns:
            推送结果字典
        """
        service = self._get_sync_service()
        commit_message = message or f"Push from BeanMind at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        result = service.push(commit_message)
        
        # 保存同步日志
        if result.success:
            config = self._get_config_from_env()
            self._log_repo.add(
                direction=SyncDirection.PUSH.value,
                success=result.success,
                message=result.message,
                pushed_files=result.pushed_files,
                pulled_files=[],
                repo=config.github_repo,
                branch=config.github_branch
            )
        
        return {
            "success": result.success,
            "message": result.message,
            "pushed_files": result.pushed_files
        }
    
    def pull(self) -> dict:
        """从 GitHub 拉取
        
        Returns:
            拉取结果字典
        """
        service = self._get_sync_service()
        result = service.pull()
        
        # 保存同步日志
        if result.success:
            config = self._get_config_from_env()
            self._log_repo.add(
                direction=SyncDirection.PULL.value,
                success=result.success,
                message=result.message,
                pushed_files=[],
                pulled_files=result.pulled_files,
                repo=config.github_repo,
                branch=config.github_branch
            )
        
        return {
            "success": result.success,
            "message": result.message,
            "pulled_files": result.pulled_files
        }
