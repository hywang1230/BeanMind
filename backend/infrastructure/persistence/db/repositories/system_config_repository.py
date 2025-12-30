"""系统配置仓储

提供系统配置的 CRUD 操作，支持加密存储敏感数据
"""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from backend.infrastructure.persistence.db.models.system_config import SystemConfig
from backend.infrastructure.backup.encryption_service import encryption_service


class SystemConfigRepository:
    """系统配置仓储"""
    
    def __init__(self, session: Session):
        self._session = session
    
    def get(self, key: str) -> Optional[str]:
        """获取配置值
        
        Args:
            key: 配置键
            
        Returns:
            配置值，如果配置已加密则自动解密
        """
        config = self._session.query(SystemConfig).filter_by(key=key).first()
        if not config:
            return None
        
        if config.encrypted:
            return encryption_service.decrypt(config.value)
        return config.value
    
    def set(self, key: str, value: str, encrypted: bool = False) -> None:
        """设置配置值
        
        Args:
            key: 配置键
            value: 配置值
            encrypted: 是否加密存储
        """
        config = self._session.query(SystemConfig).filter_by(key=key).first()
        
        stored_value = encryption_service.encrypt(value) if encrypted else value
        
        if config:
            config.value = stored_value
            config.encrypted = encrypted
        else:
            config = SystemConfig(
                key=key,
                value=stored_value,
                encrypted=encrypted
            )
            self._session.add(config)
        
        self._session.commit()
    
    def delete(self, key: str) -> bool:
        """删除配置
        
        Args:
            key: 配置键
            
        Returns:
            是否成功删除
        """
        config = self._session.query(SystemConfig).filter_by(key=key).first()
        if config:
            self._session.delete(config)
            self._session.commit()
            return True
        return False
    
    def get_all(self, prefix: Optional[str] = None) -> Dict[str, str]:
        """获取所有配置
        
        Args:
            prefix: 可选前缀过滤
            
        Returns:
            配置字典（值已自动解密）
        """
        query = self._session.query(SystemConfig)
        if prefix:
            query = query.filter(SystemConfig.key.like(f"{prefix}%"))
        
        configs = query.all()
        result = {}
        for config in configs:
            value = encryption_service.decrypt(config.value) if config.encrypted else config.value
            result[config.key] = value
        
        return result
    
    def has(self, key: str) -> bool:
        """检查配置是否存在
        
        Args:
            key: 配置键
            
        Returns:
            是否存在
        """
        return self._session.query(SystemConfig).filter_by(key=key).first() is not None
