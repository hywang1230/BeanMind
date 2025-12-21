"""用户领域实体单元测试"""
import pytest
from datetime import datetime
from backend.domain.auth.entities.user import User


class TestUserEntity:
    """用户领域实体测试类"""
    
    def test_create_user_with_minimal_data(self):
        """测试使用最少数据创建用户"""
        user = User(
            id="test-user-id",
            username="testuser"
        )
        
        assert user.id == "test-user-id"
        assert user.username == "testuser"
        assert user.password_hash is None
        assert user.display_name is None
        assert user.created_at is None
        assert user.updated_at is None
    
    def test_create_user_with_full_data(self):
        """测试使用完整数据创建用户"""
        now = datetime.now()
        user = User(
            id="test-user-id",
            username="testuser",
            password_hash="hashed_password",
            display_name="Test User",
            created_at=now,
            updated_at=now
        )
        
        assert user.id == "test-user-id"
        assert user.username == "testuser"
        assert user.password_hash == "hashed_password"
        assert user.display_name == "Test User"
        assert user.created_at == now
        assert user.updated_at == now
    
    def test_username_validation_empty(self):
        """测试用户名为空的验证"""
        with pytest.raises(ValueError, match="用户名不能为空"):
            User(id="test-id", username="")
    
    def test_username_validation_too_short(self):
        """测试用户名过短的验证"""
        with pytest.raises(ValueError, match="用户名长度不能少于3个字符"):
            User(id="test-id", username="ab")
    
    def test_username_validation_too_long(self):
        """测试用户名过长的验证"""
        long_username = "a" * 51
        with pytest.raises(ValueError, match="用户名长度不能超过50个字符"):
            User(id="test-id", username=long_username)
    
    def test_username_validation_invalid_characters(self):
        """测试用户名包含非法字符的验证"""
        with pytest.raises(ValueError, match="用户名只能包含字母、数字、下划线和中划线"):
            User(id="test-id", username="test@user")
        
        with pytest.raises(ValueError, match="用户名只能包含字母、数字、下划线和中划线"):
            User(id="test-id", username="test user")
        
        with pytest.raises(ValueError, match="用户名只能包含字母、数字、下划线和中划线"):
            User(id="test-id", username="test#user")
    
    def test_username_validation_valid_characters(self):
        """测试用户名合法字符的验证"""
        # 这些都应该成功创建
        User(id="test-id", username="testuser")
        User(id="test-id", username="test_user")
        User(id="test-id", username="test-user")
        User(id="test-id", username="test123")
        User(id="test-id", username="123test")
        User(id="test-id", username="test_user-123")
    
    def test_has_password(self):
        """测试检查是否设置了密码"""
        user_without_password = User(id="test-id", username="testuser")
        assert user_without_password.has_password() is False
        
        user_with_empty_password = User(id="test-id", username="testuser", password_hash="")
        assert user_with_empty_password.has_password() is False
        
        user_with_password = User(id="test-id", username="testuser", password_hash="hashed")
        assert user_with_password.has_password() is True
    
    def test_update_display_name(self):
        """测试更新显示名称"""
        user = User(id="test-id", username="testuser")
        
        user.update_display_name("New Name")
        assert user.display_name == "New Name"
        assert user.updated_at is not None
    
    def test_update_display_name_too_long(self):
        """测试更新过长的显示名称"""
        user = User(id="test-id", username="testuser")
        
        long_name = "a" * 101
        with pytest.raises(ValueError, match="显示名称长度不能超过100个字符"):
            user.update_display_name(long_name)
    
    def test_update_password_hash(self):
        """测试更新密码哈希"""
        user = User(id="test-id", username="testuser")
        
        user.update_password_hash("new_hashed_password")
        assert user.password_hash == "new_hashed_password"
        assert user.updated_at is not None
    
    def test_update_password_hash_empty(self):
        """测试更新空密码哈希"""
        user = User(id="test-id", username="testuser", password_hash="old_hash")
        
        with pytest.raises(ValueError, match="密码哈希不能为空"):
            user.update_password_hash("")
        
        with pytest.raises(ValueError, match="密码哈希不能为空"):
            user.update_password_hash(None)
    
    def test_to_dict(self):
        """测试转换为字典"""
        now = datetime.now()
        user = User(
            id="test-id",
            username="testuser",
            password_hash="hashed",
            display_name="Test User",
            created_at=now,
            updated_at=now
        )
        
        user_dict = user.to_dict()
        
        assert user_dict["id"] == "test-id"
        assert user_dict["username"] == "testuser"
        assert user_dict["password_hash"] == "hashed"
        assert user_dict["display_name"] == "Test User"
        assert user_dict["created_at"] == now.isoformat()
        assert user_dict["updated_at"] == now.isoformat()
    
    def test_to_dict_with_none_values(self):
        """测试包含 None 值的转换为字典"""
        user = User(id="test-id", username="testuser")
        user_dict = user.to_dict()
        
        assert user_dict["id"] == "test-id"
        assert user_dict["username"] == "testuser"
        assert user_dict["password_hash"] is None
        assert user_dict["display_name"] is None
        assert user_dict["created_at"] is None
        assert user_dict["updated_at"] is None
    
    def test_from_dict(self):
        """测试从字典创建用户"""
        now = datetime.now()
        data = {
            "id": "test-id",
            "username": "testuser",
            "password_hash": "hashed",
            "display_name": "Test User",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }
        
        user = User.from_dict(data)
        
        assert user.id == "test-id"
        assert user.username == "testuser"
        assert user.password_hash == "hashed"
        assert user.display_name == "Test User"
        assert isinstance(user.created_at, datetime)
        assert isinstance(user.updated_at, datetime)
    
    def test_from_dict_with_minimal_data(self):
        """测试从最少数据的字典创建用户"""
        data = {
            "id": "test-id",
            "username": "testuser"
        }
        
        user = User.from_dict(data)
        
        assert user.id == "test-id"
        assert user.username == "testuser"
        assert user.password_hash is None
        assert user.display_name is None
        assert user.created_at is None
        assert user.updated_at is None
    
    def test_from_dict_with_datetime_objects(self):
        """测试从包含 datetime 对象的字典创建用户"""
        now = datetime.now()
        data = {
            "id": "test-id",
            "username": "testuser",
            "created_at": now,
            "updated_at": now
        }
        
        user = User.from_dict(data)
        
        assert user.created_at == now
        assert user.updated_at == now
    
    def test_repr(self):
        """测试字符串表示"""
        user = User(id="test-id", username="testuser")
        repr_str = repr(user)
        
        assert "User" in repr_str
        assert "test-id" in repr_str
        assert "testuser" in repr_str
    
    def test_chinese_display_name(self):
        """测试中文显示名称"""
        user = User(
            id="test-id",
            username="testuser",
            display_name="测试用户"
        )
        
        assert user.display_name == "测试用户"
        
        user.update_display_name("新用户名")
        assert user.display_name == "新用户名"
