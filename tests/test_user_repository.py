"""用户仓储接口单元测试"""
import pytest
from datetime import datetime
from typing import Optional, List, Dict
from backend.domain.auth.entities import User
from backend.domain.auth.repositories import UserRepository


class MockUserRepository(UserRepository):
    """用户仓储的 Mock 实现，用于测试"""
    
    def __init__(self):
        self._users: Dict[str, User] = {}
        self._username_index: Dict[str, str] = {}  # username -> user_id
    
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
        if user.id in self._users:
            return self.update(user)
        else:
            return self.create(user)
    
    def create(self, user: User) -> User:
        if user.username in self._username_index:
            raise ValueError(f"用户名 '{user.username}' 已存在")
        
        # 使用 object.__setattr__ 来修改 dataclass 的属性
        if not user.created_at:
            object.__setattr__(user, 'created_at', datetime.now())
        if not user.updated_at:
            object.__setattr__(user, 'updated_at', datetime.now())
        
        self._users[user.id] = user
        self._username_index[user.username] = user.id
        return user
    
    def update(self, user: User) -> User:
        if user.id not in self._users:
            raise ValueError(f"用户 ID '{user.id}' 不存在")
        
        old_user = self._users[user.id]
        if old_user.username != user.username:
            # 如果用户名改变，更新索引
            del self._username_index[old_user.username]
            if user.username in self._username_index:
                raise ValueError(f"用户名 '{user.username}' 已存在")
            self._username_index[user.username] = user.id
        
        object.__setattr__(user, 'updated_at', datetime.now())
        self._users[user.id] = user
        return user
    
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


class TestUserRepository:
    """用户仓储接口测试类"""
    
    def setup_method(self):
        """每个测试方法执行前的设置"""
        self.repository = MockUserRepository()
    
    def test_create_user(self):
        """测试创建用户"""
        user = User(
            id="user-1",
            username="testuser",
            password_hash="hashed_password",
            display_name="Test User"
        )
        
        created_user = self.repository.create(user)
        
        assert created_user.id == "user-1"
        assert created_user.username == "testuser"
        assert created_user.created_at is not None
        assert created_user.updated_at is not None
    
    def test_create_user_duplicate_username(self):
        """测试创建重复用户名的用户"""
        user1 = User(id="user-1", username="testuser")
        user2 = User(id="user-2", username="testuser")
        
        self.repository.create(user1)
        
        with pytest.raises(ValueError, match="用户名 'testuser' 已存在"):
            self.repository.create(user2)
    
    def test_find_by_id(self):
        """测试根据 ID 查找用户"""
        user = User(id="user-1", username="testuser")
        self.repository.create(user)
        
        found_user = self.repository.find_by_id("user-1")
        
        assert found_user is not None
        assert found_user.id == "user-1"
        assert found_user.username == "testuser"
    
    def test_find_by_id_not_found(self):
        """测试查找不存在的用户 ID"""
        found_user = self.repository.find_by_id("non-existent")
        assert found_user is None
    
    def test_find_by_username(self):
        """测试根据用户名查找用户"""
        user = User(id="user-1", username="testuser")
        self.repository.create(user)
        
        found_user = self.repository.find_by_username("testuser")
        
        assert found_user is not None
        assert found_user.id == "user-1"
        assert found_user.username == "testuser"
    
    def test_find_by_username_not_found(self):
        """测试查找不存在的用户名"""
        found_user = self.repository.find_by_username("non-existent")
        assert found_user is None
    
    def test_find_all(self):
        """测试查找所有用户"""
        user1 = User(id="user-1", username="user1")
        user2 = User(id="user-2", username="user2")
        user3 = User(id="user-3", username="user3")
        
        self.repository.create(user1)
        self.repository.create(user2)
        self.repository.create(user3)
        
        all_users = self.repository.find_all()
        
        assert len(all_users) == 3
        assert any(u.username == "user1" for u in all_users)
        assert any(u.username == "user2" for u in all_users)
        assert any(u.username == "user3" for u in all_users)
    
    def test_find_all_empty(self):
        """测试查找所有用户（空列表）"""
        all_users = self.repository.find_all()
        assert len(all_users) == 0
    
    def test_update_user(self):
        """测试更新用户"""
        user = User(id="user-1", username="testuser", display_name="Old Name")
        self.repository.create(user)
        
        # 更新显示名称
        user.update_display_name("New Name")
        updated_user = self.repository.update(user)
        
        assert updated_user.display_name == "New Name"
        assert updated_user.updated_at is not None
        
        # 验证更新已持久化
        found_user = self.repository.find_by_id("user-1")
        assert found_user.display_name == "New Name"
    
    def test_update_user_not_found(self):
        """测试更新不存在的用户"""
        user = User(id="non-existent", username="testuser")
        
        with pytest.raises(ValueError, match="用户 ID 'non-existent' 不存在"):
            self.repository.update(user)
    
    def test_update_user_change_username(self):
        """测试更新用户名"""
        user = User(id="user-1", username="oldname")
        self.repository.create(user)
        
        # 创建一个新的 User 对象，使用新的用户名
        updated_user_data = User(id="user-1", username="newname", display_name=user.display_name)
        updated_user = self.repository.update(updated_user_data)
        
        assert updated_user.username == "newname"
        
        # 验证新用户名可以查找到
        found_user = self.repository.find_by_username("newname")
        assert found_user is not None
        assert found_user.id == "user-1"
        
        # 验证旧用户名找不到
        old_user = self.repository.find_by_username("oldname")
        assert old_user is None
    
    def test_update_user_duplicate_username(self):
        """测试更新用户名为已存在的用户名"""
        user1 = User(id="user-1", username="user1")
        user2 = User(id="user-2", username="user2")
        
        self.repository.create(user1)
        self.repository.create(user2)
        
        # 尝试将 user2 的用户名改为 user1（创建新的 User 对象）
        updated_user2 = User(id="user-2", username="user1", display_name=user2.display_name)
        
        with pytest.raises(ValueError, match="用户名 'user1' 已存在"):
            self.repository.update(updated_user2)
    
    def test_save_create(self):
        """测试 save 方法创建新用户"""
        user = User(id="user-1", username="testuser")
        
        saved_user = self.repository.save(user)
        
        assert saved_user.id == "user-1"
        assert self.repository.count() == 1
    
    def test_save_update(self):
        """测试 save 方法更新已存在用户"""
        user = User(id="user-1", username="testuser", display_name="Old Name")
        self.repository.create(user)
        
        user.update_display_name("New Name")
        saved_user = self.repository.save(user)
        
        assert saved_user.display_name == "New Name"
        assert self.repository.count() == 1  # 仍然只有一个用户
    
    def test_delete_user(self):
        """测试删除用户"""
        user = User(id="user-1", username="testuser")
        self.repository.create(user)
        
        result = self.repository.delete("user-1")
        
        assert result is True
        assert self.repository.find_by_id("user-1") is None
        assert self.repository.find_by_username("testuser") is None
        assert self.repository.count() == 0
    
    def test_delete_user_not_found(self):
        """测试删除不存在的用户"""
        result = self.repository.delete("non-existent")
        assert result is False
    
    def test_exists_by_username(self):
        """测试检查用户名是否存在"""
        user = User(id="user-1", username="testuser")
        self.repository.create(user)
        
        assert self.repository.exists_by_username("testuser") is True
        assert self.repository.exists_by_username("non-existent") is False
    
    def test_count(self):
        """测试获取用户总数"""
        assert self.repository.count() == 0
        
        user1 = User(id="user-1", username="user1")
        user2 = User(id="user-2", username="user2")
        
        self.repository.create(user1)
        assert self.repository.count() == 1
        
        self.repository.create(user2)
        assert self.repository.count() == 2
        
        self.repository.delete("user-1")
        assert self.repository.count() == 1
    
    def test_repository_interface_methods(self):
        """测试仓储接口是否定义了所有必需的方法"""
        required_methods = [
            'find_by_id',
            'find_by_username',
            'find_all',
            'save',
            'create',
            'update',
            'delete',
            'exists_by_username',
            'count'
        ]
        
        for method_name in required_methods:
            assert hasattr(UserRepository, method_name), f"UserRepository 缺少方法: {method_name}"
            assert callable(getattr(UserRepository, method_name)), f"{method_name} 不是可调用的方法"
