"""备份历史表 ORM 模型"""
from sqlalchemy import Column, String, ForeignKey, BigInteger, DateTime, Text, Index
from .base import BaseModel


class BackupHistory(BaseModel):
    """备份历史模型"""
    __tablename__ = "backup_history"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(50), nullable=False)  # github, local, s3
    backup_location = Column(Text, nullable=False)
    file_size = Column(BigInteger, nullable=True)
    backup_at = Column(DateTime, nullable=False)
    status = Column(String(20), nullable=False)  # SUCCESS, FAILED
    error_message = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_backup_history_user", "user_id"),
        Index("idx_backup_history_time", "backup_at"),
        Index("idx_backup_history_provider", "provider"),
    )

    def __repr__(self):
        return f"<BackupHistory(id={self.id}, provider={self.provider}, status={self.status})>"
