"""BeanMind - 基于 Beancount 的个人财务管理系统

FastAPI 应用入口
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件（确保在导入其他模块之前）
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    if settings.SCHEDULER_ENABLED:
        from backend.infrastructure.scheduler import recurring_scheduler
        
        recurring_scheduler.start()
        recurring_scheduler.add_recurring_job(
            hour=settings.SCHEDULER_HOUR,
            minute=settings.SCHEDULER_MINUTE,
            timezone=settings.SCHEDULER_TIMEZONE,
        )
        logger.info(
            f"周期记账调度器已启动: 每天 {settings.SCHEDULER_HOUR:02d}:{settings.SCHEDULER_MINUTE:02d} "
            f"({settings.SCHEDULER_TIMEZONE}) 执行"
        )
    
    yield
    
    # 关闭时
    if settings.SCHEDULER_ENABLED:
        from backend.infrastructure.scheduler import recurring_scheduler
        recurring_scheduler.shutdown()
        logger.info("周期记账调度器已关闭")


app = FastAPI(
    title="BeanMind API",
    description="基于 Beancount 的个人财务管理系统",
    version="0.1.0",
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 注册 API 路由
from backend.interfaces.api import auth as auth_api
from backend.interfaces.api import account as account_api
from backend.interfaces.api import transaction as transaction_api
from backend.interfaces.api import statistics as statistics_api
from backend.interfaces.api import recurring as recurring_api
from backend.interfaces.api import ai as ai_api
from backend.interfaces.api import reports as reports_api
from backend.interfaces.api import exchange_rate as exchange_rate_api

app.include_router(auth_api.router)
app.include_router(account_api.router)
app.include_router(transaction_api.router)
app.include_router(statistics_api.router)
app.include_router(recurring_api.router)
app.include_router(ai_api.router)
app.include_router(reports_api.router)
app.include_router(exchange_rate_api.router)


@app.get("/")
def read_root():
    """健康检查"""
    return {
        "message": "Welcome to BeanMind API",
        "version": "0.1.0",
        "status": "healthy",
        "auth_mode": settings.AUTH_MODE,
    }


@app.get("/health")
def health_check():
    """健康检查端点"""
    return {"status": "ok"}


@app.get("/api/config")
def get_config():
    """获取公开配置信息（不包含敏感信息）"""
    return {
        "auth_mode": settings.AUTH_MODE,
        "ai_enabled": settings.AI_ENABLED,
        "backup_provider": settings.BACKUP_PROVIDER,
    }


@app.get("/api/test/db")
def test_database():
    """测试数据库连接"""
    from backend.config import get_db
    from backend.infrastructure.persistence.db.models import User
    
    db = next(get_db())
    try:
        # 查询用户数量
        user_count = db.query(User).count()
        return {
            "status": "ok",
            "message": "Database connection successful",
            "user_count": user_count,
        }
    finally:
        db.close()


@app.get("/api/test/beancount")
def test_beancount():
    """测试 Beancount 服务"""
    from backend.config import get_beancount_service
    
    service = get_beancount_service()
    accounts = service.get_accounts()
    balances = service.get_account_balances()
    
    return {
        "status": "ok",
        "message": "Beancount service working",
        "ledger_file": str(service.ledger_path),
        "total_entries": len(service.entries),
        "total_accounts": len(accounts),
        "accounts": accounts,
        "balances": {
            account: {currency: float(amount) for currency, amount in bal.items()}
            for account, bal in balances.items()
        },
    }


@app.post("/api/test/jwt/create")
def test_jwt_create(user_id: str = "test_user", username: str = "admin"):
    """测试 JWT Token 创建"""
    from backend.infrastructure.auth.jwt_utils import JWTUtils
    
    token = JWTUtils.create_access_token({
        "sub": user_id,
        "username": username,
    })
    
    expiry = JWTUtils.get_token_expiry(token)
    
    return {
        "status": "ok",
        "message": "JWT token created",
        "token": token,
        "expiry": expiry.isoformat() if expiry else None,
    }


@app.get("/api/test/jwt/verify")
def test_jwt_verify(token: str):
    """测试 JWT Token 验证"""
    from backend.infrastructure.auth.jwt_utils import JWTUtils
    
    payload = JWTUtils.verify_token(token)
    
    if payload:
        return {
            "status": "ok",
            "message": "Token is valid",
            "payload": payload,
            "is_expired": JWTUtils.is_token_expired(token),
        }
    else:
        return {
            "status": "error",
            "message": "Token is invalid",
        }


@app.post("/api/test/password/hash")
def test_password_hash(password: str):
    """测试密码加密"""
    from backend.infrastructure.auth.password_utils import PasswordUtils
    
    hashed = PasswordUtils.hash_password(password)
    
    return {
        "status": "ok",
        "message": "Password hashed",
        "original_length": len(password),
        "hash": hashed,
        "hash_length": len(hashed),
    }


@app.post("/api/test/password/verify")
def test_password_verify(password: str, hashed: str):
    """测试密码验证"""
    from backend.infrastructure.auth.password_utils import PasswordUtils
    
    is_valid = PasswordUtils.verify_password(password, hashed)
    
    return {
        "status": "ok",
        "message": "Password verified",
        "is_valid": is_valid,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
    )

