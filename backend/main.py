"""BeanMind - 基于 Beancount 的个人财务管理系统

FastAPI 应用入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import settings

app = FastAPI(
    title="BeanMind API",
    description="基于 Beancount 的个人财务管理系统",
    version="0.1.0",
    debug=settings.DEBUG,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
    )

