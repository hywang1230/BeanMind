"""币种目录 ORM：应用配置表，不是 Beancount 真值。"""

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from datetime import datetime

from .base import Base


class Currency(Base):
    __tablename__ = "currencies"

    code = Column(String(3), primary_key=True)
    name = Column(String(64), nullable=False)
    symbol = Column(String(16), nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "symbol": self.symbol,
            "enabled": bool(self.enabled),
            "sort_order": int(self.sort_order or 0),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
