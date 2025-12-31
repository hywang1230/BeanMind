"""应用配置管理

使用 Pydantic Settings 从环境变量加载配置
"""
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

# 项目根目录（backend 目录的父目录）
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()


class Settings(BaseSettings):
    """应用配置"""
    
    # ==================== 鉴权配置 ====================
    AUTH_MODE: Literal["none", "single_user", "multi_user"] = "single_user"
    SINGLE_USER_USERNAME: str = "admin"
    SINGLE_USER_PASSWORD: str = "changeme"
    
    # JWT 配置
    JWT_SECRET_KEY: str = "your-super-secret-key-change-this-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # ==================== 数据配置 ====================
    DATA_DIR: Path = Path("./data")
    LEDGER_FILE: Path = Path("./data/ledger/main.beancount")
    DATABASE_FILE: Path = Path("./data/beanmind.db")
    
    # ==================== GitHub 同步配置 ====================
    GITHUB_REPO: str = ""
    GITHUB_TOKEN: str = ""
    GITHUB_BRANCH: str = "main"
    GITHUB_SYNC_AUTO_ENABLED: bool = False
    GITHUB_SYNC_AUTO_INTERVAL: int = 300  # 秒
    
    # ==================== AI 配置 ====================
    AI_ENABLED: bool = False
    
    # ==================== 周期记账调度配置 ====================
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_HOUR: int = 12  # 执行时间（小时，24小时制）
    SCHEDULER_MINUTE: int = 0  # 执行时间（分钟）
    SCHEDULER_TIMEZONE: str = "Asia/Shanghai"  # 时区
    
    # ==================== 服务器配置 ====================
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = True
    
    # CORS 允许的源
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    
    # ==================== 日志配置 ====================
    LOG_LEVEL: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    LOG_DIR: Path = Path("./logs")  # 日志目录
    
    # ==================== Pydantic 配置 ====================
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )
    
    @model_validator(mode='after')
    def resolve_paths(self) -> 'Settings':
        """将相对路径转换为基于项目根目录的绝对路径"""
        # 如果路径是相对路径，转换为基于项目根目录的绝对路径
        if not self.DATA_DIR.is_absolute():
            object.__setattr__(self, 'DATA_DIR', (PROJECT_ROOT / self.DATA_DIR).resolve())
        if not self.LEDGER_FILE.is_absolute():
            object.__setattr__(self, 'LEDGER_FILE', (PROJECT_ROOT / self.LEDGER_FILE).resolve())
        if not self.DATABASE_FILE.is_absolute():
            object.__setattr__(self, 'DATABASE_FILE', (PROJECT_ROOT / self.DATABASE_FILE).resolve())
        if not self.LOG_DIR.is_absolute():
            object.__setattr__(self, 'LOG_DIR', (PROJECT_ROOT / self.LOG_DIR).resolve())
        return self
    
    # ==================== 辅助方法 ====================
    @property
    def cors_origins_list(self) -> list[str]:
        """获取 CORS 源列表"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    @property
    def database_url(self) -> str:
        """获取数据库连接 URL"""
        return f"sqlite:///{self.DATABASE_FILE}"
    
    def ensure_directories(self) -> None:
        """确保所有必要的目录存在"""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)


# 创建全局配置实例
settings = Settings()


# 应用启动时确保目录存在
settings.ensure_directories()


