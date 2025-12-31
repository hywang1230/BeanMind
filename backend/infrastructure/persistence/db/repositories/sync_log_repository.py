"""同步日志仓储

提供同步日志的 CRUD 操作
"""
import json
import uuid
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

# 东八区时区
TIMEZONE_CN = timezone(timedelta(hours=8))

from backend.infrastructure.persistence.db.models.sync_log import SyncLog


class SyncLogRepository:
    """同步日志仓储"""
    
    def __init__(self, session: Session):
        self._session = session
    
    def add(
        self,
        direction: str,
        success: bool,
        message: str,
        pushed_files: List[str],
        pulled_files: List[str],
        repo: str,
        branch: str
    ) -> SyncLog:
        """添加同步日志
        
        Args:
            direction: 同步方向
            success: 是否成功
            message: 同步消息
            pushed_files: 推送的文件列表
            pulled_files: 拉取的文件列表
            repo: 仓库名
            branch: 分支名
            
        Returns:
            新创建的日志记录
        """
        log = SyncLog(
            id=str(uuid.uuid4()),
            direction=direction,
            success=success,
            message=message,
            pushed_files=json.dumps(pushed_files),
            pulled_files=json.dumps(pulled_files),
            repo=repo,
            branch=branch,
            synced_at=datetime.now(TIMEZONE_CN)
        )
        self._session.add(log)
        self._session.commit()
        return log
    
    def get_recent(self, limit: int = 20) -> List[dict]:
        """获取最近的同步日志
        
        Args:
            limit: 返回数量限制
            
        Returns:
            日志列表
        """
        logs = (
            self._session.query(SyncLog)
            .order_by(SyncLog.synced_at.desc())
            .limit(limit)
            .all()
        )
        
        return [self._to_dict(log) for log in logs]
    
    def get_last(self) -> Optional[dict]:
        """获取最后一条同步日志
        
        Returns:
            最后一条日志记录，如果没有返回 None
        """
        log = (
            self._session.query(SyncLog)
            .order_by(SyncLog.synced_at.desc())
            .first()
        )
        return self._to_dict(log) if log else None
    
    def _to_dict(self, log: SyncLog) -> dict:
        """转换为字典"""
        return {
            "id": log.id,
            "direction": log.direction,
            "success": log.success,
            "message": log.message,
            "pushed_files": json.loads(log.pushed_files) if log.pushed_files else [],
            "pulled_files": json.loads(log.pulled_files) if log.pulled_files else [],
            "repo": log.repo,
            "branch": log.branch,
            "synced_at": log.synced_at.isoformat() if log.synced_at else None
        }
