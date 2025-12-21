"""认证领域服务

处理用户认证相关的业务逻辑，包括登录验证、Token 生成等。
支持三种鉴权模式：none（无鉴权）、single_user（单用户）、multi_user（多用户）。
"""
from typing import Optional, Dict, Literal
from datetime import datetime, timedelta

from backend.config import settings
from backend.domain.auth.entities import User
from backend.domain.auth.repositories import UserRepository
from backend.infrastructure.auth.password_utils import PasswordUtils
from backend.infrastructure.auth.jwt_utils import JWTUtils


class AuthService:
    """
    认证领域服务
    
    负责处理用户认证相关的核心业务逻辑。
    """
    
    def __init__(self, user_repository: UserRepository):
        """
        初始化认证服务
        
        Args:
            user_repository: 用户仓储
        """
        self.user_repository = user_repository
        self.auth_mode = settings.AUTH_MODE
    
    def authenticate(self, username: str, password: Optional[str] = None) -> Optional[User]:
        """
        认证用户
        
        根据配置的鉴权模式进行用户认证。
        
        Args:
            username: 用户名
            password: 密码（在 none 模式下可选）
            
        Returns:
            认证成功返回用户实体，失败返回 None
        """
        if self.auth_mode == "none":
            # 无鉴权模式：返回默认用户
            return self._authenticate_none()
        
        elif self.auth_mode == "single_user":
            # 单用户模式：验证用户名和密码
            return self._authenticate_single_user(username, password)
        
        elif self.auth_mode == "multi_user":
            # 多用户模式：从数据库验证
            return self._authenticate_multi_user(username, password)
        
        else:
            raise ValueError(f"不支持的认证模式: {self.auth_mode}")
    
    def _authenticate_none(self) -> Optional[User]:
        """
        无鉴权模式认证
        
        Returns:
            默认用户
        """
        # 查找或创建默认用户
        default_user = self.user_repository.find_by_username("default")
        if not default_user:
            # 如果默认用户不存在，应该在系统初始化时创建
            # 这里返回 None，由上层处理
            return None
        return default_user
    
    def _authenticate_single_user(self, username: str, password: Optional[str]) -> Optional[User]:
        """
        单用户模式认证
        
        验证用户名和密码是否与配置中的单用户凭据匹配。
        
        Args:
            username: 用户名
            password: 密码
            
        Returns:
            认证成功返回用户实体，失败返回 None
        """
        if not password:
            return None
        
        # 验证用户名
        if username != settings.SINGLE_USER_USERNAME:
            return None
        
        # 验证密码
        if password != settings.SINGLE_USER_PASSWORD:
            return None
        
        # 查找或创建单用户
        user = self.user_repository.find_by_username(username)
        if not user:
            # 如果用户不存在，应该在系统初始化时创建
            return None
        
        return user
    
    def _authenticate_multi_user(self, username: str, password: Optional[str]) -> Optional[User]:
        """
        多用户模式认证
        
        从数据库中查找用户并验证密码。
        
        Args:
            username: 用户名
            password: 密码
            
        Returns:
            认证成功返回用户实体，失败返回 None
        """
        if not password:
            return None
        
        # 从数据库查找用户
        user = self.user_repository.find_by_username(username)
        if not user:
            return None
        
        # 验证密码
        if not user.has_password():
            # 用户没有设置密码
            return None
        
        if not PasswordUtils.verify_password(password, user.password_hash):
            return None
        
        return user
    
    def generate_token(self, user: User, expires_delta: Optional[timedelta] = None) -> str:
        """
        为用户生成访问令牌
        
        Args:
            user: 用户实体
            expires_delta: 过期时间增量，如果为 None 则使用默认值
            
        Returns:
            JWT Token 字符串
        """
        token_data = {
            "sub": user.id,  # subject: 用户 ID
            "username": user.username,
            "auth_mode": self.auth_mode,
        }
        
        return JWTUtils.create_access_token(token_data, expires_delta)
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """
        验证访问令牌
        
        Args:
            token: JWT Token 字符串
            
        Returns:
            解析后的 payload，验证失败返回 None
        """
        return JWTUtils.verify_token(token)
    
    def get_user_from_token(self, token: str) -> Optional[User]:
        """
        从 Token 中获取用户
        
        Args:
            token: JWT Token 字符串
            
        Returns:
            用户实体，Token 无效或用户不存在返回 None
        """
        payload = self.verify_token(token)
        if not payload:
            return None
        
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        return self.user_repository.find_by_id(user_id)
    
    def login(self, username: str, password: Optional[str] = None) -> Optional[Dict]:
        """
        用户登录
        
        执行完整的登录流程：认证用户 + 生成 Token。
        
        Args:
            username: 用户名
            password: 密码
            
        Returns:
            包含用户信息和 Token 的字典，登录失败返回 None
            
        Example:
            result = auth_service.login("admin", "password")
            if result:
                token = result["access_token"]
                user = result["user"]
        """
        # 认证用户
        user = self.authenticate(username, password)
        if not user:
            return None
        
        # 生成 Token
        access_token = self.generate_token(user)
        
        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": settings.JWT_EXPIRATION_HOURS * 3600,  # 转换为秒
            "user": {
                "id": user.id,
                "username": user.username,
                "display_name": user.display_name,
            }
        }
    
    def refresh_token(self, old_token: str) -> Optional[Dict]:
        """
        刷新访问令牌
        
        验证旧 Token 并生成新 Token。
        
        Args:
            old_token: 旧的 JWT Token
            
        Returns:
            包含新 Token 和用户信息的字典，刷新失败返回 None
        """
        # 从旧 Token 获取用户
        user = self.get_user_from_token(old_token)
        if not user:
            return None
        
        # 生成新 Token
        access_token = self.generate_token(user)
        
        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": settings.JWT_EXPIRATION_HOURS * 3600,
            "user": {
                "id": user.id,
                "username": user.username,
                "display_name": user.display_name,
            }
        }
    
    def validate_auth_mode(self) -> bool:
        """
        验证当前鉴权模式配置是否有效
        
        Returns:
            配置有效返回 True，否则返回 False
        """
        valid_modes = ["none", "single_user", "multi_user"]
        return self.auth_mode in valid_modes
    
    def get_auth_mode(self) -> Literal["none", "single_user", "multi_user"]:
        """
        获取当前鉴权模式
        
        Returns:
            当前的鉴权模式
        """
        return self.auth_mode
