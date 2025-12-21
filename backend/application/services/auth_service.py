"""认证应用服务

应用服务层负责编排领域服务、处理 DTO 转换、协调业务用例。
提供面向接口层的高层业务操作。
"""
from typing import Optional, Dict
from datetime import timedelta

from backend.domain.auth.entities import User
from backend.domain.auth.repositories import UserRepository
from backend.domain.auth.services import AuthService


class AuthApplicationService:
    """
    认证应用服务
    
    提供认证相关的应用层操作，包括登录、刷新 Token、获取当前用户等。
    负责协调领域服务和数据转换。
    """
    
    def __init__(self, user_repository: UserRepository):
        """
        初始化认证应用服务
        
        Args:
            user_repository: 用户仓储
        """
        self.user_repository = user_repository
        self.auth_service = AuthService(user_repository)
    
    def login(self, username: str, password: Optional[str] = None) -> Optional[Dict]:
        """
        用户登录
        
        执行用户登录流程，返回包含 Token 和用户信息的响应。
        
        Args:
            username: 用户名
            password: 密码（在 none 模式下可选）
            
        Returns:
            登录成功返回包含 access_token 和用户信息的字典，失败返回 None
            
        Example:
            result = service.login("admin", "password")
            if result:
                token = result["access_token"]
                user_info = result["user"]
        """
        # 调用领域服务执行登录
        result = self.auth_service.login(username, password)
        
        if not result:
            return None
        
        # 应用层可以在这里添加额外的业务逻辑
        # 例如：记录登录日志、更新最后登录时间等
        
        return result
    
    def refresh_token(self, old_token: str) -> Optional[Dict]:
        """
        刷新访问令牌
        
        验证旧 Token 并生成新的访问令牌。
        
        Args:
            old_token: 旧的 JWT Token
            
        Returns:
            刷新成功返回包含新 Token 和用户信息的字典，失败返回 None
        """
        # 调用领域服务刷新 Token
        result = self.auth_service.refresh_token(old_token)
        
        if not result:
            return None
        
        # 应用层可以在这里添加额外的业务逻辑
        # 例如：记录 Token 刷新日志等
        
        return result
    
    def get_current_user(self, token: str) -> Optional[Dict]:
        """
        从 Token 获取当前用户信息
        
        验证 Token 并返回用户信息（DTO 格式）。
        
        Args:
            token: JWT Token
            
        Returns:
            用户信息字典，Token 无效或用户不存在返回 None
        """
        # 从 Token 获取用户实体
        user = self.auth_service.get_user_from_token(token)
        
        if not user:
            return None
        
        # 转换为 DTO
        return self._user_to_dto(user)
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """
        根据 ID 获取用户信息
        
        Args:
            user_id: 用户 ID
            
        Returns:
            用户信息字典，用户不存在返回 None
        """
        user = self.user_repository.find_by_id(user_id)
        
        if not user:
            return None
        
        return self._user_to_dto(user)
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """
        根据用户名获取用户信息
        
        Args:
            username: 用户名
            
        Returns:
            用户信息字典，用户不存在返回 None
        """
        user = self.user_repository.find_by_username(username)
        
        if not user:
            return None
        
        return self._user_to_dto(user)
    
    def update_user_profile(self, user_id: str, display_name: Optional[str] = None) -> Optional[Dict]:
        """
        更新用户资料
        
        Args:
            user_id: 用户 ID
            display_name: 新的显示名称
            
        Returns:
            更新后的用户信息字典，用户不存在返回 None
        """
        user = self.user_repository.find_by_id(user_id)
        
        if not user:
            return None
        
        # 更新显示名称
        if display_name is not None:
            user.update_display_name(display_name)
        
        # 保存更新
        updated_user = self.user_repository.update(user)
        
        return self._user_to_dto(updated_user)
    
    def change_password(
        self,
        user_id: str,
        old_password: str,
        new_password: str
    ) -> bool:
        """
        修改密码
        
        Args:
            user_id: 用户 ID
            old_password: 旧密码
            new_password: 新密码
            
        Returns:
            修改成功返回 True，失败返回 False
        """
        # 获取用户
        user = self.user_repository.find_by_id(user_id)
        if not user:
            return False
        
        # 验证旧密码
        from backend.infrastructure.auth.password_utils import PasswordUtils
        
        if not user.has_password() or not PasswordUtils.verify_password(old_password, user.password_hash):
            return False
        
        # 生成新密码哈希
        new_hash = PasswordUtils.hash_password(new_password)
        
        # 更新密码
        user.update_password_hash(new_hash)
        
        # 保存更新
        self.user_repository.update(user)
        
        return True
    
    def validate_token(self, token: str) -> bool:
        """
        验证 Token 是否有效
        
        Args:
            token: JWT Token
            
        Returns:
            Token 有效返回 True，否则返回 False
        """
        payload = self.auth_service.verify_token(token)
        return payload is not None
    
    def get_auth_mode(self) -> str:
        """
        获取当前鉴权模式
        
        Returns:
            当前的鉴权模式（none/single_user/multi_user）
        """
        return self.auth_service.get_auth_mode()
    
    def _user_to_dto(self, user: User) -> Dict:
        """
        将用户实体转换为 DTO
        
        Args:
            user: 用户实体
            
        Returns:
            用户信息字典
        """
        return {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        }
