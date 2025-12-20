"""用户表 ORM 模型"""
from sqlalchemy import Column, String, DateTime
from .base import BaseModel


class User(BaseModel):
    """用户模型"""
    __tablename__ = "users"

    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)  # 无鉴权模式可为空
    display_name = Column(String(100), nullable=True)

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username})>"
