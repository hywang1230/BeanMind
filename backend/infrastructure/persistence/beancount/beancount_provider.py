"""BeancountService 单例提供者

提供全局共享的 BeancountService 实例，避免每次请求重新加载账本文件。
使用文件修改时间检测变化，按需自动重新加载。
"""
from pathlib import Path
from threading import Lock
from typing import Optional
import os

from backend.infrastructure.persistence.beancount.beancount_service import BeancountService


class BeancountServiceProvider:
    """BeancountService 单例提供者
    
    特性：
    - 全局共享单例，减少账本文件重复加载
    - 基于文件修改时间自动检测变化
    - 线程安全
    - 支持强制刷新
    """
    
    _service: Optional[BeancountService] = None
    _last_mtime: Optional[float] = None
    _ledger_path: Optional[Path] = None
    _lock = Lock()
    
    @classmethod
    def get_service(cls, ledger_path: Path | str) -> BeancountService:
        """获取 BeancountService 实例
        
        如果账本文件未发生变化，返回缓存的实例；
        否则重新加载并更新缓存。
        
        Args:
            ledger_path: 账本文件路径
            
        Returns:
            BeancountService 实例
        """
        ledger_path = Path(ledger_path)
        
        with cls._lock:
            # 检查文件是否存在
            if not ledger_path.exists():
                raise FileNotFoundError(f"Ledger file not found: {ledger_path}")
            
            # 获取文件修改时间
            current_mtime = cls._get_file_mtime(ledger_path)
            
            # 判断是否需要重新加载
            need_reload = (
                cls._service is None or
                cls._ledger_path != ledger_path or
                cls._last_mtime != current_mtime
            )
            
            if need_reload:
                cls._service = BeancountService(ledger_path)
                cls._ledger_path = ledger_path
                cls._last_mtime = current_mtime
            
            return cls._service
    
    @classmethod
    def _get_file_mtime(cls, ledger_path: Path) -> float:
        """获取账本文件及其所有 include 文件的最新修改时间
        
        Args:
            ledger_path: 主账本文件路径
            
        Returns:
            最新的修改时间戳
        """
        latest_mtime = ledger_path.stat().st_mtime
        
        # 检查同目录下所有 .beancount 文件的修改时间
        # 这样可以捕获 include 的年份文件变化
        ledger_dir = ledger_path.parent
        for file in ledger_dir.glob("*.beancount"):
            file_mtime = file.stat().st_mtime
            if file_mtime > latest_mtime:
                latest_mtime = file_mtime
        
        return latest_mtime
    
    @classmethod
    def invalidate(cls) -> None:
        """强制使缓存失效
        
        在写入操作后调用，确保下次 get_service() 会重新加载。
        """
        with cls._lock:
            cls._last_mtime = None
    
    @classmethod
    def reload(cls) -> None:
        """强制重新加载账本
        
        立即重新加载账本文件，更新缓存。
        """
        with cls._lock:
            if cls._ledger_path and cls._ledger_path.exists():
                cls._service = BeancountService(cls._ledger_path)
                cls._last_mtime = cls._get_file_mtime(cls._ledger_path)
    
    @classmethod
    def clear(cls) -> None:
        """清除缓存
        
        主要用于测试场景。
        """
        with cls._lock:
            cls._service = None
            cls._last_mtime = None
            cls._ledger_path = None
