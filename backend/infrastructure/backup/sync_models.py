"""GitHub 同步数据模型"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from enum import Enum


class SyncDirection(str, Enum):
    """同步方向"""
    PUSH = "push"
    PULL = "pull"
    BOTH = "both"


@dataclass
class SyncStatus:
    """同步状态"""
    is_configured: bool = False  # 是否已配置
    is_syncing: bool = False  # 是否正在同步
    last_sync_at: Optional[datetime] = None  # 上次同步时间
    last_sync_message: str = ""  # 上次同步消息
    has_local_changes: bool = False  # 是否有本地未同步变更
    has_remote_changes: bool = False  # 是否有远程未拉取变更
    repo: str = ""  # 仓库名
    branch: str = "main"  # 分支名


@dataclass
class SyncResult:
    """同步结果"""
    success: bool
    message: str
    direction: SyncDirection
    pushed_files: List[str] = field(default_factory=list)
    pulled_files: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    synced_at: datetime = field(default_factory=datetime.now)


@dataclass
class SyncConfig:
    """同步配置"""
    github_token: str = ""
    github_repo: str = ""
    github_branch: str = "main"
    auto_sync_enabled: bool = False
    auto_sync_interval: int = 300  # 秒

