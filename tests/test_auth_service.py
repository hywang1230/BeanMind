"""认证领域服务单元测试

测试 AuthService 的所有认证逻辑，包括三种鉴权模式。
"""
import pytest
from datetime import timedelta
from typing import Optional, List, Dict

from backend.domain.auth.entities import User
from backend.domain.auth.repositories import UserRepository
from backend.domain.auth.services import AuthService
from backend.infrastructure.auth.password_utils import PasswordUtils
from backend.config import settings


class MockUserRepository(UserRepository):
    """用户仓储的 Mock 实现"""
    
    def __init__(self):
        self._users: Dict[str, User] = {}
        self._username_index: Dict[str, str] = {}
    
    def find_by_id(self, user_id: str) -> Optional[User]:
        return self._users.get(user_id)
    
    def find_by_username(self, username: str) -> Optional[User]:
        user_id = self._username_index.get(username)
        if user_id:
            return self._users.get(user_id)
        return None
    
    def find_all(self) -> List[User]:
        return list(self._users.values())
    
    def save(self, user: User) -> User:
        self._users[user.id] = user
        self._username_index[user.username] = user.id
        return user
    
    def create(self, user: User) -> User:
        if user.username in self._username_index:
            raise ValueError(f"用户名 '{user.username}' 已存在")
        return self.save(user)
    
    def update(self, user: User) -> User:
        if user.id not in self._users:
            raise ValueError(f"用户 ID '{user.id}' 不存在")
        return self.save(user)
    
    def delete(self, user_id: str) -> bool:
        if user_id not in self._users:
            return False
        user = self._users[user_id]
        del self._username_index[user.username]
        del self._users[user_id]
        return True
    
    def exists_by_username(self, username: str) -> bool:
        return username in self._username_index
    
    def count(self) -> int:
        return len(self._users)


@pytest.fixture
def mock_repository():
    """创建 Mock 仓储"""
    return MockUserRepository()


@pytest.fixture
def auth_service(mock_repository):
    """创建认证服务实例"""
    return AuthService(mock_repository)


class TestAuthService:
    """认证服务测试类"""
    
    def test_init(self, auth_service):
        """测试初始化"""
        assert auth_service is not None
        assert auth_service.auth_mode in ["none", "single_user", "multi_user"]
    
    def test_validate_auth_mode(self, auth_service):
        """测试验证鉴权模式"""
        assert auth_service.validate_auth_mode() is True
    
    def test_get_auth_mode(self, auth_service):
        """测试获取鉴权模式"""
        mode = auth_service.get_auth_mode()
        assert mode in ["none", "single_user", "multi_user"]
    
    def test_authenticate_none_mode(self, mock_repository):
        """测试无鉴权模式认证"""
        # 保存当前模式
        original_mode = settings.AUTH_MODE
        
        try:
            # 设置为无鉴权模式
            settings.AUTH_MODE = "none"
            
            # 创建默认用户
            default_user = User(id="default-id", username="default", display_name="默认用户")
            mock_repository.create(default_user)
            
            # 创建服务
            service = AuthService(mock_repository)
            
            # 无鉴权模式下，任何用户名密码都应该返回默认用户
            user = service.authenticate("anyone", "anything")
            
            assert user is not None
            assert user.username == "default"
        
        finally:
            # 恢复原模式
            settings.AUTH_MODE = original_mode
    
    def test_authenticate_single_user_success(self, mock_repository):
        """测试单用户模式认证成功"""
        original_mode = settings.AUTH_MODE
        original_username = settings.SINGLE_USER_USERNAME
        original_password = settings.SINGLE_USER_PASSWORD
        
        try:
            settings.AUTH_MODE = "single_user"
            settings.SINGLE_USER_USERNAME = "admin"
            settings.SINGLE_USER_PASSWORD = "password123"
            
            # 创建对应的用户
            admin_user = User(id="admin-id", username="admin", display_name="管理员")
            mock_repository.create(admin_user)
            
            service = AuthService(mock_repository)
            
            # 正确的用户名和密码
            user = service.authenticate("admin", "password123")
            
            assert user is not None
            assert user.username == "admin"
        
        finally:
            settings.AUTH_MODE = original_mode
            settings.SINGLE_USER_USERNAME = original_username
            settings.SINGLE_USER_PASSWORD = original_password
    
    def test_authenticate_single_user_wrong_password(self, mock_repository):
        """测试单用户模式认证失败（密码错误）"""
        original_mode = settings.AUTH_MODE
        original_username = settings.SINGLE_USER_USERNAME
        original_password = settings.SINGLE_USER_PASSWORD
        
        try:
            settings.AUTH_MODE = "single_user"
            settings.SINGLE_USER_USERNAME = "admin"
            settings.SINGLE_USER_PASSWORD = "password123"
            
            admin_user = User(id="admin-id", username="admin")
            mock_repository.create(admin_user)
            
            service = AuthService(mock_repository)
            
            # 错误的密码
            user = service.authenticate("admin", "wrong_password")
            
            assert user is None
        
        finally:
            settings.AUTH_MODE = original_mode
            settings.SINGLE_USER_USERNAME = original_username
            settings.SINGLE_USER_PASSWORD = original_password
    
    def test_authenticate_single_user_wrong_username(self, mock_repository):
        """测试单用户模式认证失败（用户名错误）"""
        original_mode = settings.AUTH_MODE
        
        try:
            settings.AUTH_MODE = "single_user"
            
            service = AuthService(mock_repository)
            
            # 错误的用户名
            user = service.authenticate("wrong_user", "password123")
            
            assert user is None
        
        finally:
            settings.AUTH_MODE = original_mode
    
    def test_authenticate_multi_user_success(self, mock_repository):
        """测试多用户模式认证成功"""
        original_mode = settings.AUTH_MODE
        
        try:
            settings.AUTH_MODE = "multi_user"
            
            # 创建用户并设置密码
            password_hash = PasswordUtils.hash_password("user_password")
            user = User(
                id="user-1",
                username="testuser",
                password_hash=password_hash,
                display_name="Test User"
            )
            mock_repository.create(user)
            
            service = AuthService(mock_repository)
            
            # 正确的用户名和密码
            authenticated_user = service.authenticate("testuser", "user_password")
            
            assert authenticated_user is not None
            assert authenticated_user.username == "testuser"
        
        finally:
            settings.AUTH_MODE = original_mode
    
    def test_authenticate_multi_user_wrong_password(self, mock_repository):
        """测试多用户模式认证失败（密码错误）"""
        original_mode = settings.AUTH_MODE
        
        try:
            settings.AUTH_MODE = "multi_user"
            
            password_hash = PasswordUtils.hash_password("correct_password")
            user = User(id="user-1", username="testuser", password_hash=password_hash)
            mock_repository.create(user)
            
            service = AuthService(mock_repository)
            
            # 错误的密码
            authenticated_user = service.authenticate("testuser", "wrong_password")
            
            assert authenticated_user is None
        
        finally:
            settings.AUTH_MODE = original_mode
    
    def test_authenticate_multi_user_not_found(self, mock_repository):
        """测试多用户模式认证失败（用户不存在）"""
        original_mode = settings.AUTH_MODE
        
        try:
            settings.AUTH_MODE = "multi_user"
            
            service = AuthService(mock_repository)
            
            # 不存在的用户
            user = service.authenticate("nonexistent", "password")
            
            assert user is None
        
        finally:
            settings.AUTH_MODE = original_mode
    
    def test_generate_token(self, auth_service):
        """测试生成 Token"""
        user = User(id="user-1", username="testuser", display_name="Test User")
        
        token = auth_service.generate_token(user)
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_generate_token_with_custom_expiry(self, auth_service):
        """测试生成自定义过期时间的 Token"""
        user = User(id="user-1", username="testuser")
        
        # 1 小时过期
        token = auth_service.generate_token(user, timedelta(hours=1))
        
        assert token is not None
    
    def test_verify_token(self, auth_service):
        """测试验证 Token"""
        user = User(id="user-1", username="testuser")
        token = auth_service.generate_token(user)
        
        payload = auth_service.verify_token(token)
        
        assert payload is not None
        assert payload["sub"] == "user-1"
        assert payload["username"] == "testuser"
    
    def test_verify_invalid_token(self, auth_service):
        """测试验证无效 Token"""
        payload = auth_service.verify_token("invalid_token")
        assert payload is None
    
    def test_get_user_from_token(self, auth_service, mock_repository):
        """测试从 Token 获取用户"""
        user = User(id="user-1", username="testuser", display_name="Test User")
        mock_repository.create(user)
        
        token = auth_service.generate_token(user)
        
        retrieved_user = auth_service.get_user_from_token(token)
        
        assert retrieved_user is not None
        assert retrieved_user.id == "user-1"
        assert retrieved_user.username == "testuser"
    
    def test_get_user_from_invalid_token(self, auth_service):
        """测试从无效 Token 获取用户"""
        user = auth_service.get_user_from_token("invalid_token")
        assert user is None
    
    def test_login_success(self, mock_repository):
        """测试登录成功"""
        original_mode = settings.AUTH_MODE
        
        try:
            settings.AUTH_MODE = "single_user"
            settings.SINGLE_USER_USERNAME = "admin"
            settings.SINGLE_USER_PASSWORD = "password"
            
            admin_user = User(id="admin-id", username="admin", display_name="管理员")
            mock_repository.create(admin_user)
            
            service = AuthService(mock_repository)
            
            result = service.login("admin", "password")
            
            assert result is not None
            assert "access_token" in result
            assert "token_type" in result
            assert result["token_type"] == "Bearer"
            assert "expires_in" in result
            assert "user" in result
            assert result["user"]["username"] == "admin"
        
        finally:
            settings.AUTH_MODE = original_mode
    
    def test_login_failure(self, auth_service):
        """测试登录失败"""
        result = auth_service.login("wrong_user", "wrong_password")
        assert result is None
    
    def test_refresh_token_success(self, auth_service, mock_repository):
        """测试刷新 Token 成功"""
        user = User(id="user-1", username="testuser", display_name="Test User")
        mock_repository.create(user)
        
        # 生成初始 Token
        old_token = auth_service.generate_token(user)
        
        # 刷新 Token
        result = auth_service.refresh_token(old_token)
        
        assert result is not None
        assert "access_token" in result
        # 注意：在快速连续调用时，新旧 Token 可能相同（因为时间戳相同）
        # 重要的是刷新成功并返回了有效的 Token
        assert isinstance(result["access_token"], str)
        assert len(result["access_token"]) > 0
        assert result["user"]["username"] == "testuser"
    
    def test_refresh_token_invalid(self, auth_service):
        """测试刷新无效 Token"""
        result = auth_service.refresh_token("invalid_token")
        assert result is None
    
    def test_complete_auth_flow(self, mock_repository):
        """测试完整的认证流程"""
        original_mode = settings.AUTH_MODE
        
        try:
            settings.AUTH_MODE = "multi_user"
            
            # 1. 创建用户
            password_hash = PasswordUtils.hash_password("mypassword")
            user = User(
                id="user-1",
                username="testuser",
                password_hash=password_hash,
                display_name="Test User"
            )
            mock_repository.create(user)
            
            service = AuthService(mock_repository)
            
            # 2. 登录
            login_result = service.login("testuser", "mypassword")
            assert login_result is not None
            token = login_result["access_token"]
            
            # 3. 使用 Token 获取用户
            retrieved_user = service.get_user_from_token(token)
            assert retrieved_user is not None
            assert retrieved_user.username == "testuser"
            
            # 4. 刷新 Token
            refresh_result = service.refresh_token(token)
            assert refresh_result is not None
            new_token = refresh_result["access_token"]
            
            # 5. 使用新 Token 获取用户
            user_from_new_token = service.get_user_from_token(new_token)
            assert user_from_new_token is not None
            assert user_from_new_token.username == "testuser"
        
        finally:
            settings.AUTH_MODE = original_mode
