"""同步日志表模型

记录每次同步操作的历史
"""
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Boolean, DateTime, Integer

from backend.infrastructure.persistence.db.models.base import Base


class SyncLog(Base):
    """同步日志表"""
    
    __tablename__ = "sync_logs"
    
    id = Column(String(36), primary_key=True)
    direction = Column(String(20), nullable=False, comment="同步方向: push/pull/both")
    success = Column(Boolean, default=True, comment="是否成功")
    message = Column(Text, default="", comment="同步消息")
    pushed_files = Column(Text, default="", comment="推送的文件列表（JSON）")
    pulled_files = Column(Text, default="", comment="拉取的文件列表（JSON）")
    repo = Column(String(200), default="", comment="仓库名")
    branch = Column(String(100), default="main", comment="分支名")
    synced_at = Column(
        DateTime, 
        default=lambda: datetime.now(timezone.utc),
        comment="同步时间"
    )
    
    def __repr__(self) -> str:
        return f"<SyncLog(id={self.id}, direction={self.direction}, success={self.success})>"
