"""认证应用服务单元测试

测试 AuthApplicationService 的所有应用层操作。
"""
import pytest
from typing import Optional, List, Dict
from datetime import datetime

from backend.domain.auth.entities import User
from backend.domain.auth.repositories import UserRepository
from backend.application.services import AuthApplicationService
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
def app_service(mock_repository):
    """创建应用服务实例"""
    return AuthApplicationService(mock_repository)


class TestAuthApplicationService:
    """认证应用服务测试类"""
    
    def test_init(self, app_service):
        """测试初始化"""
        assert app_service is not None
        assert app_service.user_repository is not None
        assert app_service.auth_service is not None
    
    def test_login_success(self, app_service, mock_repository):
        """测试登录成功"""
        original_mode = settings.AUTH_MODE
        
        try:
            settings.AUTH_MODE = "single_user"
            settings.SINGLE_USER_USERNAME = "admin"
            settings.SINGLE_USER_PASSWORD = "password"
            
            # 创建用户
            user = User(id="user-1", username="admin", display_name="管理员")
            mock_repository.create(user)
            
            # 重新创建服务以应用新配置
            service = AuthApplicationService(mock_repository)
            
            # 登录
            result = service.login("admin", "password")
            
            assert result is not None
            assert "access_token" in result
            assert "user" in result
            assert result["user"]["username"] == "admin"
        
        finally:
            settings.AUTH_MODE = original_mode
    
    def test_login_failure(self, app_service):
        """测试登录失败"""
        result = app_service.login("wrong_user", "wrong_password")
        assert result is None
    
    def test_refresh_token_success(self, app_service, mock_repository):
        """测试刷新 Token 成功"""
        # 创建用户
        user = User(id="user-1", username="testuser", display_name="Test User")
        mock_repository.create(user)
        
        # 生成初始 Token
        login_result = app_service.auth_service.login("testuser", None)
        assert login_result is None  # 需要密码
        
        # 直接生成 Token 用于测试
        token = app_service.auth_service.generate_token(user)
        
        # 刷新 Token
        result = app_service.refresh_token(token)
        
        assert result is not None
        assert "access_token" in result
        assert result["user"]["username"] == "testuser"
    
    def test_refresh_token_invalid(self, app_service):
        """测试刷新无效 Token"""
        result = app_service.refresh_token("invalid_token")
        assert result is None
    
    def test_get_current_user(self, app_service, mock_repository):
        """测试获取当前用户"""
        # 创建用户
        user = User(id="user-1", username="testuser", display_name="Test User")
        mock_repository.create(user)
        
        # 生成 Token
        token = app_service.auth_service.generate_token(user)
        
        # 获取当前用户
        user_info = app_service.get_current_user(token)
        
        assert user_info is not None
        assert user_info["id"] == "user-1"
        assert user_info["username"] == "testuser"
        assert user_info["display_name"] == "Test User"
    
    def test_get_current_user_invalid_token(self, app_service):
        """测试使用无效 Token 获取当前用户"""
        user_info = app_service.get_current_user("invalid_token")
        assert user_info is None
    
    def test_get_user_by_id(self, app_service, mock_repository):
        """测试根据 ID 获取用户"""
        user = User(id="user-1", username="testuser", display_name="Test User")
        mock_repository.create(user)
        
        user_info = app_service.get_user_by_id("user-1")
        
        assert user_info is not None
        assert user_info["id"] == "user-1"
        assert user_info["username"] == "testuser"
        assert user_info["display_name"] == "Test User"
    
    def test_get_user_by_id_not_found(self, app_service):
        """测试获取不存在的用户"""
        user_info = app_service.get_user_by_id("non-existent")
        assert user_info is None
    
    def test_get_user_by_username(self, app_service, mock_repository):
        """测试根据用户名获取用户"""
        user = User(id="user-1", username="testuser", display_name="Test User")
        mock_repository.create(user)
        
        user_info = app_service.get_user_by_username("testuser")
        
        assert user_info is not None
        assert user_info["id"] == "user-1"
        assert user_info["username"] == "testuser"
    
    def test_get_user_by_username_not_found(self, app_service):
        """测试获取不存在的用户名"""
        user_info = app_service.get_user_by_username("nonexistent")
        assert user_info is None
    
    def test_update_user_profile(self, app_service, mock_repository):
        """测试更新用户资料"""
        user = User(id="user-1", username="testuser", display_name="Old Name")
        mock_repository.create(user)
        
        # 更新显示名称
        updated_info = app_service.update_user_profile("user-1", display_name="New Name")
        
        assert updated_info is not None
        assert updated_info["display_name"] == "New Name"
        
        # 验证更新已持久化
        user_info = app_service.get_user_by_id("user-1")
        assert user_info["display_name"] == "New Name"
    
    def test_update_user_profile_not_found(self, app_service):
        """测试更新不存在的用户"""
        result = app_service.update_user_profile("non-existent", display_name="Name")
        assert result is None
    
    def test_change_password_success(self, app_service, mock_repository):
        """测试修改密码成功"""
        # 创建用户并设置密码
        old_password = "old_password"
        password_hash = PasswordUtils.hash_password(old_password)
        user = User(id="user-1", username="testuser", password_hash=password_hash)
        mock_repository.create(user)
        
        # 修改密码
        new_password = "new_password"
        result = app_service.change_password("user-1", old_password, new_password)
        
        assert result is True
        
        # 验证新密码可以使用
        updated_user = mock_repository.find_by_id("user-1")
        assert PasswordUtils.verify_password(new_password, updated_user.password_hash)
    
    def test_change_password_wrong_old_password(self, app_service, mock_repository):
        """测试修改密码失败（旧密码错误）"""
        password_hash = PasswordUtils.hash_password("correct_password")
        user = User(id="user-1", username="testuser", password_hash=password_hash)
        mock_repository.create(user)
        
        result = app_service.change_password("user-1", "wrong_password", "new_password")
        
        assert result is False
    
    def test_change_password_user_not_found(self, app_service):
        """测试修改不存在用户的密码"""
        result = app_service.change_password("non-existent", "old", "new")
        assert result is False
    
    def test_validate_token_valid(self, app_service, mock_repository):
        """测试验证有效 Token"""
        user = User(id="user-1", username="testuser")
        mock_repository.create(user)
        
        token = app_service.auth_service.generate_token(user)
        
        is_valid = app_service.validate_token(token)
        assert is_valid is True
    
    def test_validate_token_invalid(self, app_service):
        """测试验证无效 Token"""
        is_valid = app_service.validate_token("invalid_token")
        assert is_valid is False
    
    def test_get_auth_mode(self, app_service):
        """测试获取鉴权模式"""
        mode = app_service.get_auth_mode()
        assert mode in ["none", "single_user", "multi_user"]
    
    def test_user_to_dto_conversion(self, app_service, mock_repository):
        """测试用户实体到 DTO 的转换"""
        now = datetime.now()
        user = User(
            id="user-1",
            username="testuser",
            display_name="Test User",
            created_at=now,
            updated_at=now
        )
        mock_repository.create(user)
        
        dto = app_service._user_to_dto(user)
        
        assert dto["id"] == "user-1"
        assert dto["username"] == "testuser"
        assert dto["display_name"] == "Test User"
        assert dto["created_at"] == now.isoformat()
        assert dto["updated_at"] == now.isoformat()
    
    def test_user_to_dto_with_none_dates(self, app_service):
        """测试 DTO 转换（日期为 None）"""
        user = User(id="user-1", username="testuser")
        
        dto = app_service._user_to_dto(user)
        
        assert dto["id"] == "user-1"
        assert dto["username"] == "testuser"
        assert dto["created_at"] is None
        assert dto["updated_at"] is None
    
    def test_complete_workflow(self, app_service, mock_repository):
        """测试完整的应用流程"""
        original_mode = settings.AUTH_MODE
        
        try:
            # 设置多用户模式
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
            
            # 重新创建服务
            service = AuthApplicationService(mock_repository)
            
            # 2. 登录
            login_result = service.login("testuser", "mypassword")
            assert login_result is not None
            token = login_result["access_token"]
            
            # 3. 获取当前用户
            user_info = service.get_current_user(token)
            assert user_info is not None
            assert user_info["username"] == "testuser"
            
            # 4. 更新用户资料
            updated_info = service.update_user_profile("user-1", display_name="Updated Name")
            assert updated_info["display_name"] == "Updated Name"
            
            # 5. 修改密码
            result = service.change_password("user-1", "mypassword", "newpassword")
            assert result is True
            
            # 6. 使用新密码登录
            new_login = service.login("testuser", "newpassword")
            assert new_login is not None
            
            # 7. 刷新 Token
            refresh_result = service.refresh_token(token)
            assert refresh_result is not None
        
        finally:
            settings.AUTH_MODE = original_mode
