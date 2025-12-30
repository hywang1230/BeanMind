"""系统配置表模型

用于存储加密的敏感配置（如 GitHub Token）和其他系统配置
"""
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Boolean, DateTime

from backend.infrastructure.persistence.db.models.base import Base


class SystemConfig(Base):
    """系统配置表"""
    
    __tablename__ = "system_config"
    
    key = Column(String(100), primary_key=True, comment="配置键")
    value = Column(Text, nullable=False, default="", comment="配置值")
    encrypted = Column(Boolean, default=False, comment="是否加密存储")
    updated_at = Column(
        DateTime, 
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="更新时间"
    )
    
    def __repr__(self) -> str:
        return f"<SystemConfig(key={self.key}, encrypted={self.encrypted})>"
