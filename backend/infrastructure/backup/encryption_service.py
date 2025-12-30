"""加密服务

使用 Fernet 对称加密保护敏感数据（如 GitHub Token）
"""
import base64
import hashlib
from typing import Optional

from cryptography.fernet import Fernet

from backend.config.settings import settings


class EncryptionService:
    """敏感数据加密服务"""
    
    def __init__(self, secret_key: Optional[str] = None):
        """初始化加密服务
        
        Args:
            secret_key: 用于派生加密密钥的密钥，默认使用 JWT_SECRET_KEY
        """
        key = secret_key or settings.JWT_SECRET_KEY
        # 使用 SHA256 从密钥派生固定长度的 Fernet 密钥
        derived_key = hashlib.sha256(key.encode()).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(derived_key))
    
    def encrypt(self, plaintext: str) -> str:
        """加密明文
        
        Args:
            plaintext: 待加密的明文
            
        Returns:
            加密后的密文（Base64 编码）
        """
        if not plaintext:
            return ""
        encrypted = self._fernet.encrypt(plaintext.encode())
        return encrypted.decode()
    
    def decrypt(self, ciphertext: str) -> str:
        """解密密文
        
        Args:
            ciphertext: 待解密的密文
            
        Returns:
            解密后的明文
        """
        if not ciphertext:
            return ""
        decrypted = self._fernet.decrypt(ciphertext.encode())
        return decrypted.decode()


# 全局加密服务实例
encryption_service = EncryptionService()
