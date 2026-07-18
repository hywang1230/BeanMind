"""Beancount 账本的可重建查询投影。"""

from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from .base import Base, BaseModel


class LedgerTransaction(BaseModel):
    """交易查询主表；数据只允许由 Beancount 重建。"""

    __tablename__ = "ledger_transactions"

    date = Column(Date, nullable=False, index=True)
    flag = Column(String(1), nullable=False)
    payee = Column(Text, nullable=True)
    narration = Column(Text, nullable=False, default="")
    transaction_type = Column(String(20), nullable=False, index=True)
    source_file = Column(Text, nullable=False)
    source_lineno = Column(Integer, nullable=False)
    content_hash = Column(String(64), nullable=False)
    links_json = Column(Text, nullable=False, default="[]")

    postings = relationship(
        "LedgerPosting",
        back_populates="transaction",
        cascade="all, delete-orphan",
        order_by="LedgerPosting.sequence",
    )
    tags = relationship(
        "LedgerTag",
        back_populates="transaction",
        cascade="all, delete-orphan",
        order_by="LedgerTag.tag",
    )

    __table_args__ = (
        Index("idx_ledger_transactions_date_id", "date", "id"),
        Index("idx_ledger_transactions_source", "source_file", "source_lineno"),
        Index("idx_ledger_transactions_type_date", "transaction_type", "date"),
    )


class LedgerPosting(Base):
    """投影中的交易分录，金额使用规范化十进制字符串。"""

    __tablename__ = "ledger_postings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(
        String(36),
        ForeignKey("ledger_transactions.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence = Column(Integer, nullable=False)
    account = Column(Text, nullable=False)
    amount_text = Column(Text, nullable=False)
    currency = Column(String(32), nullable=False)
    cost_text = Column(Text, nullable=True)
    cost_currency = Column(String(32), nullable=True)
    price_text = Column(Text, nullable=True)
    price_currency = Column(String(32), nullable=True)
    flag = Column(String(1), nullable=True)

    transaction = relationship("LedgerTransaction", back_populates="postings")

    __table_args__ = (
        Index("idx_ledger_postings_transaction", "transaction_id", "sequence"),
        Index("idx_ledger_postings_account_transaction", "account", "transaction_id"),
        Index("idx_ledger_postings_currency_account", "currency", "account"),
        {"sqlite_autoincrement": True},
    )


class LedgerTag(Base):
    """交易标签投影。"""

    __tablename__ = "ledger_tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(
        String(36),
        ForeignKey("ledger_transactions.id", ondelete="CASCADE"),
        nullable=False,
    )
    tag = Column(Text, nullable=False)

    transaction = relationship("LedgerTransaction", back_populates="tags")

    __table_args__ = (
        Index("idx_ledger_tags_tag_transaction", "tag", "transaction_id"),
        Index("idx_ledger_tags_transaction", "transaction_id"),
        {"sqlite_autoincrement": True},
    )


class LedgerIndexFile(Base):
    """投影所依据文件的指纹和一致性状态。"""

    __tablename__ = "ledger_index_files"

    path = Column(Text, primary_key=True)
    mtime_ns = Column(Integer, nullable=False)
    size = Column(Integer, nullable=False)
    content_hash = Column(String(64), nullable=False)
    indexed_at = Column(DateTime, nullable=False)
    status = Column(String(16), nullable=False, index=True)
    last_error = Column(Text, nullable=True)
