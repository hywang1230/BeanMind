"""BeanMind - 基于 Beancount 的个人财务管理系统

FastAPI 应用入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="BeanMind API",
    description="基于 Beancount 的个人财务管理系统",
    version="0.1.0",
)

# CORS 配置（开发环境）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
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
        "status": "healthy"
    }


@app.get("/health")
def health_check():
    """健康检查端点"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
