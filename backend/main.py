"""BeanMind - 基于 Beancount 的个人财务管理系统

FastAPI 应用入口
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件（确保在导入其他模块之前）
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.config import settings

# ==================== 配置日志系统（最早执行） ====================
from backend.config.logging_config import setup_logging

setup_logging(
    log_level=settings.LOG_LEVEL,
    log_dir=settings.LOG_DIR,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    
    # 1. 周期记账调度器
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
    
    # 2. GitHub 自动同步调度器
    if settings.GITHUB_SYNC_AUTO_ENABLED:
        from backend.infrastructure.scheduler import sync_scheduler
        
        sync_scheduler.start()
        sync_scheduler.add_sync_job(interval_seconds=settings.GITHUB_SYNC_AUTO_INTERVAL)
        logger.info(
            f"GitHub 自动同步调度器已启动: 每 {settings.GITHUB_SYNC_AUTO_INTERVAL} 秒执行"
        )
    
    yield
    
    # 关闭时
    if settings.SCHEDULER_ENABLED:
        from backend.infrastructure.scheduler import recurring_scheduler
        recurring_scheduler.shutdown()
        logger.info("周期记账调度器已关闭")
    
    if settings.GITHUB_SYNC_AUTO_ENABLED:
        from backend.infrastructure.scheduler import sync_scheduler
        sync_scheduler.shutdown()
        logger.info("GitHub 自动同步调度器已关闭")


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
from backend.interfaces.api import budget as budget_api
from backend.interfaces.api import sync as sync_api

app.include_router(auth_api.router)
app.include_router(account_api.router)
app.include_router(transaction_api.router)
app.include_router(statistics_api.router)
app.include_router(recurring_api.router)
app.include_router(ai_api.router)
app.include_router(reports_api.router)
app.include_router(exchange_rate_api.router)
app.include_router(budget_api.router)
app.include_router(sync_api.router)


@app.get("/api")
def read_root():
    """API 欢迎页"""
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
        "github_sync_enabled": bool(settings.GITHUB_TOKEN and settings.GITHUB_REPO),
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


# =============================================================================
# 静态文件服务 (用于 Docker 单容器部署)
# =============================================================================

# 前端构建产物目录
FRONTEND_DIST_DIR = Path(__file__).parent.parent / "frontend" / "dist"

if FRONTEND_DIST_DIR.exists():
    logger.info(f"前端静态文件目录存在: {FRONTEND_DIST_DIR}")
    
    # 挂载静态资源目录 (js, css, images 等)
    assets_dir = FRONTEND_DIST_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
    
    # 服务其他静态文件
    @app.get("/{path:path}")
    async def serve_spa(request: Request, path: str):
        """服务前端 SPA 应用"""
        # 如果路径以 /api 开头，说明是 API 请求但未匹配，返回 404
        if path.startswith("api/"):
            return {"detail": "Not Found"}
        
        # 尝试返回请求的静态文件
        file_path = FRONTEND_DIST_DIR / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        
        # 否则返回 index.html (SPA 路由)
        index_path = FRONTEND_DIST_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        
        return {"detail": "Frontend not built"}
else:
    logger.info("前端静态文件目录不存在，跳过静态文件服务配置（开发模式）")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
    )

