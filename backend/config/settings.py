"""应用配置管理

使用 Pydantic Settings 从环境变量加载配置
"""
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    
    # ==================== 备份配置 ====================
    BACKUP_PROVIDER: Literal["github", "local", "s3"] = "github"
    BACKUP_AUTO_ENABLED: bool = False
    BACKUP_AUTO_INTERVAL: Literal["hourly", "daily", "weekly"] = "daily"
    
    # GitHub 备份配置
    GITHUB_REPO: str = ""
    GITHUB_TOKEN: str = ""
    GITHUB_BRANCH: str = "main"
    
    # 本地备份配置
    LOCAL_BACKUP_DIR: Path = Path("./backups")
    
    # ==================== AI 配置 ====================
    AI_ENABLED: bool = False
    AGENTUNIVERSE_CONFIG: Path = Path("./config/agent_config.yaml")
    
    # ==================== 服务器配置 ====================
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = True
    
    # CORS 允许的源
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    
    # ==================== Pydantic 配置 ====================
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )
    
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
        
        if self.BACKUP_PROVIDER == "local":
            self.LOCAL_BACKUP_DIR.mkdir(parents=True, exist_ok=True)


# 创建全局配置实例
settings = Settings()


# 应用启动时确保目录存在
settings.ensure_directories()


if __name__ == "__main__":
    # 测试配置加载
    print("=" * 60)
    print("BeanMind Configuration")
    print("=" * 60)
    print(f"Auth Mode: {settings.AUTH_MODE}")
    print(f"Database URL: {settings.database_url}")
    print(f"Ledger File: {settings.LEDGER_FILE}")
    print(f"JWT Secret Key: {'*' * 20} (hidden)")
    print(f"CORS Origins: {settings.cors_origins_list}")
    print(f"Backup Provider: {settings.BACKUP_PROVIDER}")
    print(f"AI Enabled: {settings.AI_ENABLED}")
    print(f"Debug Mode: {settings.DEBUG}")
    print("=" * 60)
