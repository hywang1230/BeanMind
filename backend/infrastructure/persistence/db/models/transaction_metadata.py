"""交易元数据表 ORM 模型"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Index
from .base import BaseModel


class TransactionMetadata(BaseModel):
    """交易元数据模型"""
    __tablename__ = "transaction_metadata"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    beancount_id = Column(String(100), nullable=False, index=True)
    sync_at = Column(DateTime, nullable=False, index=True)
    notes = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_transaction_metadata_user", "user_id"),
        Index("idx_transaction_metadata_beancount", "beancount_id"),
        Index("idx_transaction_metadata_sync", "sync_at"),
    )

    def __repr__(self):
        return f"<TransactionMetadata(id={self.id}, beancount_id={self.beancount_id})>"
