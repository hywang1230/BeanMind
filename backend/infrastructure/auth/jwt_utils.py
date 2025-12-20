"""JWT 工具类

用于生成和验证 JWT Token
"""
from datetime import datetime, timedelta
from typing import Dict, Optional
from jose import jwt, JWTError
from backend.config import settings


class JWTUtils:
    """JWT Token 工具类"""
    
    @staticmethod
    def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
        """
        创建访问令牌
        
        Args:
            data: 要编码的数据（通常包含用户ID等信息）
            expires_delta: 过期时间增量，如果为 None 则使用配置的默认值
        
        Returns:
            JWT Token 字符串
        
        Example:
            token = JWTUtils.create_access_token({"sub": "user_id", "username": "admin"})
        """
        to_encode = data.copy()
        
        # 设置过期时间
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRATION_HOURS)
        
        to_encode.update({"exp": expire})
        
        # 编码 JWT
        encoded_jwt = jwt.encode(
            to_encode,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str) -> Optional[Dict]:
        """
        验证并解析 Token
        
        Args:
            token: JWT Token 字符串
        
        Returns:
            解析后的 payload，如果验证失败则返回 None
        
        Example:
            payload = JWTUtils.verify_token(token)
            if payload:
                user_id = payload.get("sub")
        """
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            return payload
        except JWTError as e:
            print(f"JWT verification failed: {e}")
            return None
    
    @staticmethod
    def decode_token(token: str) -> Optional[Dict]:
        """
        解码 Token（不验证签名，仅用于调试）
        
        Args:
            token: JWT Token 字符串
        
        Returns:
            解码后的 payload
        """
        try:
            # 不验证签名
            payload = jwt.decode(
                token,
                options={"verify_signature": False}
            )
            return payload
        except Exception as e:
            print(f"JWT decode failed: {e}")
            return None
    
    @staticmethod
    def get_token_expiry(token: str) -> Optional[datetime]:
        """
        获取 Token 过期时间
        
        Args:
            token: JWT Token 字符串
        
        Returns:
            过期时间（datetime），如果 Token 无效则返回 None
        """
        payload = JWTUtils.verify_token(token)
        if payload and "exp" in payload:
            return datetime.fromtimestamp(payload["exp"])
        return None
    
    @staticmethod
    def is_token_expired(token: str) -> bool:
        """
        检查 Token 是否过期
        
        Args:
            token: JWT Token 字符串
        
        Returns:
            True 如果过期，False 如果仍有效
        """
        expiry = JWTUtils.get_token_expiry(token)
        if expiry:
            return datetime.utcnow() > expiry
        return True  # 无法获取过期时间，视为已过期


