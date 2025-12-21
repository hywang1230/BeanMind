"""用户仓储实现单元测试

测试 UserRepositoryImpl 与数据库的交互。
使用实际的 SQLite 数据库进行集成测试。
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime

from backend.domain.auth.entities import User as UserEntity
from backend.infrastructure.persistence.db.models.base import Base
from backend.infrastructure.persistence.db.models.user import User as UserModel
from backend.infrastructure.persistence.db.repositories import UserRepositoryImpl


@pytest.fixture
def db_session():
    """创建测试数据库会话"""
    # 使用内存 SQLite 数据库
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()
    engine.dispose()


@pytest.fixture
def repository(db_session):
    """创建用户仓储实例"""
    return UserRepositoryImpl(db_session)


class TestUserRepositoryImpl:
    """用户仓储实现测试类"""
    
    def test_create_user(self, repository):
        """测试创建用户"""
        user = UserEntity(
            id="test-user-1",
            username="testuser",
            password_hash="hashed_password",
            display_name="Test User"
        )
        
        created_user = repository.create(user)
        
        assert created_user.id == "test-user-1"
        assert created_user.username == "testuser"
        assert created_user.password_hash == "hashed_password"
        assert created_user.display_name == "Test User"
        assert created_user.created_at is not None
        assert created_user.updated_at is not None
    
    def test_create_user_duplicate_username(self, repository):
        """测试创建重复用户名"""
        user1 = UserEntity(id="user-1", username="testuser")
        user2 = UserEntity(id="user-2", username="testuser")
        
        repository.create(user1)
        
        with pytest.raises(ValueError, match="用户名 'testuser' 已存在"):
            repository.create(user2)
    
    def test_find_by_id(self, repository):
        """测试根据 ID 查找用户"""
        user = UserEntity(id="test-user-1", username="testuser")
        repository.create(user)
        
        found_user = repository.find_by_id("test-user-1")
        
        assert found_user is not None
        assert found_user.id == "test-user-1"
        assert found_user.username == "testuser"
    
    def test_find_by_id_not_found(self, repository):
        """测试查找不存在的用户 ID"""
        found_user = repository.find_by_id("non-existent")
        assert found_user is None
    
    def test_find_by_username(self, repository):
        """测试根据用户名查找用户"""
        user = UserEntity(id="test-user-1", username="testuser")
        repository.create(user)
        
        found_user = repository.find_by_username("testuser")
        
        assert found_user is not None
        assert found_user.id == "test-user-1"
        assert found_user.username == "testuser"
    
    def test_find_by_username_not_found(self, repository):
        """测试查找不存在的用户名"""
        found_user = repository.find_by_username("non-existent")
        assert found_user is None
    
    def test_find_all(self, repository):
        """测试查找所有用户"""
        user1 = UserEntity(id="user-1", username="user1")
        user2 = UserEntity(id="user-2", username="user2")
        user3 = UserEntity(id="user-3", username="user3")
        
        repository.create(user1)
        repository.create(user2)
        repository.create(user3)
        
        all_users = repository.find_all()
        
        assert len(all_users) == 3
        usernames = {u.username for u in all_users}
        assert usernames == {"user1", "user2", "user3"}
    
    def test_find_all_empty(self, repository):
        """测试查找所有用户（空列表）"""
        all_users = repository.find_all()
        assert len(all_users) == 0
    
    def test_update_user(self, repository):
        """测试更新用户"""
        user = UserEntity(id="user-1", username="testuser", display_name="Old Name")
        repository.create(user)
        
        # 更新显示名称
        user.update_display_name("New Name")
        updated_user = repository.update(user)
        
        assert updated_user.display_name == "New Name"
        
        # 验证更新已持久化
        found_user = repository.find_by_id("user-1")
        assert found_user.display_name == "New Name"
    
    def test_update_user_not_found(self, repository):
        """测试更新不存在的用户"""
        user = UserEntity(id="non-existent", username="testuser")
        
        with pytest.raises(ValueError, match="用户 ID 'non-existent' 不存在"):
            repository.update(user)
    
    def test_update_user_change_username(self, repository):
        """测试更新用户名"""
        user = UserEntity(id="user-1", username="oldname")
        repository.create(user)
        
        # 创建新的实体对象，使用新用户名
        updated_user_data = UserEntity(
            id="user-1",
            username="newname",
            display_name=user.display_name,
            password_hash=user.password_hash
        )
        updated_user = repository.update(updated_user_data)
        
        assert updated_user.username == "newname"
        
        # 验证新用户名可以查找到
        found_user = repository.find_by_username("newname")
        assert found_user is not None
        assert found_user.id == "user-1"
        
        # 验证旧用户名找不到
        old_user = repository.find_by_username("oldname")
        assert old_user is None
    
    def test_update_user_duplicate_username(self, repository):
        """测试更新用户名为已存在的用户名"""
        user1 = UserEntity(id="user-1", username="user1")
        user2 = UserEntity(id="user-2", username="user2")
        
        repository.create(user1)
        repository.create(user2)
        
        # 尝试将 user2 的用户名改为 user1
        updated_user2 = UserEntity(
            id="user-2",
            username="user1",
            display_name=user2.display_name,
            password_hash=user2.password_hash
        )
        
        with pytest.raises(ValueError, match="用户名 'user1' 已存在"):
            repository.update(updated_user2)
    
    def test_save_create(self, repository):
        """测试 save 方法创建新用户"""
        user = UserEntity(id="user-1", username="testuser")
        
        saved_user = repository.save(user)
        
        assert saved_user.id == "user-1"
        assert repository.count() == 1
    
    def test_save_update(self, repository):
        """测试 save 方法更新已存在用户"""
        user = UserEntity(id="user-1", username="testuser", display_name="Old Name")
        repository.create(user)
        
        user.update_display_name("New Name")
        saved_user = repository.save(user)
        
        assert saved_user.display_name == "New Name"
        assert repository.count() == 1  # 仍然只有一个用户
    
    def test_delete_user(self, repository):
        """测试删除用户"""
        user = UserEntity(id="user-1", username="testuser")
        repository.create(user)
        
        result = repository.delete("user-1")
        
        assert result is True
        assert repository.find_by_id("user-1") is None
        assert repository.find_by_username("testuser") is None
        assert repository.count() == 0
    
    def test_delete_user_not_found(self, repository):
        """测试删除不存在的用户"""
        result = repository.delete("non-existent")
        assert result is False
    
    def test_exists_by_username(self, repository):
        """测试检查用户名是否存在"""
        user = UserEntity(id="user-1", username="testuser")
        repository.create(user)
        
        assert repository.exists_by_username("testuser") is True
        assert repository.exists_by_username("non-existent") is False
    
    def test_count(self, repository):
        """测试获取用户总数"""
        assert repository.count() == 0
        
        user1 = UserEntity(id="user-1", username="user1")
        user2 = UserEntity(id="user-2", username="user2")
        
        repository.create(user1)
        assert repository.count() == 1
        
        repository.create(user2)
        assert repository.count() == 2
        
        repository.delete("user-1")
        assert repository.count() == 1
    
    def test_entity_model_conversion(self, repository):
        """测试实体与模型之间的转换"""
        original_entity = UserEntity(
            id="user-1",
            username="testuser",
            password_hash="hashed_password",
            display_name="Test User"
        )
        
        # 创建并保存
        created_entity = repository.create(original_entity)
        
        # 所有字段应该被正确保存和恢复
        assert created_entity.id == original_entity.id
        assert created_entity.username == original_entity.username
        assert created_entity.password_hash == original_entity.password_hash
        assert created_entity.display_name == original_entity.display_name
        assert created_entity.created_at is not None
        assert created_entity.updated_at is not None
    
    def test_transaction_rollback_on_error(self, repository, db_session):
        """测试错误时的事务回滚"""
        user1 = UserEntity(id="user-1", username="testuser")
        repository.create(user1)
        
        # 尝试创建重复用户名的用户（会失败）
        user2 = UserEntity(id="user-2", username="testuser")
        try:
            repository.create(user2)
        except ValueError:
            pass
        
        # 验证数据库状态正确（只有一个用户）
        assert repository.count() == 1
        assert repository.find_by_id("user-1") is not None
        assert repository.find_by_id("user-2") is None
    
    def test_multiple_operations(self, repository):
        """测试多个操作的组合"""
        # 创建
        user1 = UserEntity(id="user-1", username="user1", display_name="User One")
        user2 = UserEntity(id="user-2", username="user2", display_name="User Two")
        
        repository.create(user1)
        repository.create(user2)
        assert repository.count() == 2
        
        # 更新
        user1.update_display_name("Updated User One")
        repository.update(user1)
        
        # 查找
        found = repository.find_by_username("user1")
        assert found.display_name == "Updated User One"
        
        # 删除
        repository.delete("user-2")
        assert repository.count() == 1
        
        # 验证最终状态
        all_users = repository.find_all()
        assert len(all_users) == 1
        assert all_users[0].username == "user1"
