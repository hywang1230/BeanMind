"""日志配置模块

提供统一的日志配置，支持：
- 控制台输出（带颜色）
- 文件输出（支持日志轮转）
- 灵活的日志级别配置
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """带颜色的日志格式化器（仅用于控制台输出）"""
    
    # ANSI 颜色代码
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
    }
    RESET = '\033[0m'
    
    def format(self, record):
        # 添加颜色
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logging(
    log_level: str = "INFO",
    log_dir: Optional[Path] = None,
    log_file: str = "beanmind.log",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> None:
    """配置应用日志系统
    
    Args:
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: 日志目录路径，如果为 None 则不输出到文件
        log_file: 日志文件名
        max_bytes: 单个日志文件最大字节数（超过后轮转）
        backup_count: 保留的历史日志文件数量
    """
    # 获取根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())
    
    # 清除已有的处理器（避免重复配置）
    root_logger.handlers.clear()
    
    # 日志格式
    detailed_format = (
        "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"
    )
    simple_format = "%(asctime)s | %(levelname)-8s | %(message)s"
    
    # ==================== 1. 控制台处理器（带颜色） ====================
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level.upper())
    console_formatter = ColoredFormatter(
        simple_format,
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # ==================== 2. 文件处理器（如果指定了日志目录） ====================
    if log_dir:
        # 确保日志目录存在
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建详细日志文件处理器（所有日志）
        log_file_path = log_dir / log_file
        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8',
        )
        file_handler.setLevel(logging.DEBUG)  # 文件记录所有级别
        file_formatter = logging.Formatter(
            detailed_format,
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        # 创建错误日志文件处理器（仅 ERROR 及以上）
        error_log_file_path = log_dir / "error.log"
        error_file_handler = RotatingFileHandler(
            error_log_file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8',
        )
        error_file_handler.setLevel(logging.ERROR)
        error_file_handler.setFormatter(file_formatter)
        root_logger.addHandler(error_file_handler)
        
        logging.info(f"日志配置完成 - 文件输出: {log_file_path}")
    else:
        logging.info("日志配置完成 - 仅控制台输出")
    
    # ==================== 3. 第三方库日志级别调整 ====================
    # 降低第三方库的日志级别，避免过多噪音
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("git").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    logging.info(f"日志级别设置为: {log_level.upper()}")
