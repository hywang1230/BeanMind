"""依赖注入容器

使用 FastAPI Depends 和工厂模式管理依赖
"""
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from backend.config import settings


# ==================== 数据库会话 ====================

# 创建数据库引擎
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # SQLite 特定配置
    echo=settings.DEBUG,
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    获取数据库会话
    
    用法:
        @app.get("/api/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== Beancount Service ====================

from backend.infrastructure.persistence.beancount.beancount_service import BeancountService

_beancount_service: BeancountService | None = None


def get_beancount_service() -> BeancountService:
    """获取 Beancount 服务单例"""
    global _beancount_service
    if _beancount_service is None:
        _beancount_service = BeancountService(settings.LEDGER_FILE)
    return _beancount_service


# ==================== 认证依赖 ====================

# 将在步骤 2.x 实现
# from fastapi import Depends, HTTPException, status
# from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# security = HTTPBearer()


# def get_current_user(
#     credentials: HTTPAuthorizationCredentials = Depends(security),
#     db: Session = Depends(get_db),
# ):
#     """获取当前用户"""
#     # 验证 JWT Token
#     # 返回用户对象
#     pass


# ==================== 辅助函数 ====================

def get_settings():
    """获取配置对象"""
    return settings


def get_db_session() -> Session:
    """
    获取数据库会话（非生成器版本）
    
    用于后台任务、调度器等非 FastAPI 上下文的场景
    调用者负责手动关闭会话
    
    用法:
        db = get_db_session()
        try:
            # 使用 db
        finally:
            db.close()
    """
    return SessionLocal()


# 导出所有依赖
__all__ = [
    "get_db",
    "get_db_session",
    "get_settings",
    "get_beancount_service",
    # "get_current_user",  # 将在步骤 2.x 实现
]
