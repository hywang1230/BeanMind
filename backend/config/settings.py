"""BeanMind 单机应用配置。"""

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()


class Settings(BaseSettings):
    """只保留单机运行、账本、可选周期任务和 LLM 所需配置。"""

    DATA_DIR: Path = Path("./data")
    LEDGER_FILE: Path = Path("./data/ledger/main.beancount")
    DATABASE_FILE: Path = Path("./data/beanmind.db")

    SCHEDULER_ENABLED: bool = True
    SCHEDULER_HOUR: int = 12
    SCHEDULER_MINUTE: int = 0
    SCHEDULER_TIMEZONE: str = "Asia/Shanghai"

    LLM_ENABLED: bool = False
    LLM_BASE_URL: str = ""
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TIMEOUT_SECONDS: float = 30.0

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = True
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    LOG_LEVEL: str = "INFO"
    LOG_DIR: Path = Path("./logs")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @model_validator(mode="after")
    def resolve_paths(self) -> "Settings":
        for name in ("DATA_DIR", "LEDGER_FILE", "DATABASE_FILE", "LOG_DIR"):
            path = getattr(self, name)
            if not path.is_absolute():
                object.__setattr__(self, name, (PROJECT_ROOT / path).resolve())
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.DATABASE_FILE}"

    def ensure_directories(self) -> None:
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
