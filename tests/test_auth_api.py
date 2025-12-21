"""认证 API 集成测试

测试认证 API 端点的完整功能。
使用 FastAPI TestClient 进行测试。
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.config import get_db, settings
from backend.infrastructure.persistence.db.models.base import Base
from backend.infrastructure.persistence.db.models.user import User as UserModel
from backend.infrastructure.auth.password_utils import PasswordUtils


# 创建测试数据库
@pytest.fixture
def test_db():
    """创建测试数据库"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},  # 允许多线程访问
        echo=False
    )
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()
    engine.dispose()


@pytest.fixture
def client(test_db):
    """创建测试客户端"""
    def override_get_db():
        try:
            yield test_db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    test_client = TestClient(app)
    yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(test_db):
    """创建测试用户"""
    password_hash = PasswordUtils.hash_password("testpassword")
    user = UserModel(
        id="test-user-id",
        username="testuser",
        password_hash=password_hash,
        display_name="Test User"
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


class TestAuthAPI:
    """认证 API 测试类"""
    
    def test_get_auth_config(self, client):
        """测试获取认证配置"""
        response = client.get("/api/auth/config")
        
        assert response.status_code == 200
        data = response.json()
        assert "auth_mode" in data
        assert data["auth_mode"] in ["none", "single_user", "multi_user"]
    
    def test_login_multi_user_success(self, client, test_user):
        """测试多用户模式登录成功"""
        original_mode = settings.AUTH_MODE
        
        try:
            settings.AUTH_MODE = "multi_user"
            
            response = client.post(
                "/api/auth/login",
                json={"username": "testuser", "password": "testpassword"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert "token_type" in data
            assert data["token_type"] == "Bearer"
            assert "user" in data
            assert data["user"]["username"] == "testuser"
        
        finally:
            settings.AUTH_MODE = original_mode
    
    def test_login_wrong_password(self, client, test_user):
        """测试登录失败（密码错误）"""
        original_mode = settings.AUTH_MODE
        
        try:
            settings.AUTH_MODE = "multi_user"
            
            response = client.post(
                "/api/auth/login",
                json={"username": "testuser", "password": "wrongpassword"}
            )
            
            assert response.status_code == 401
            data = response.json()
            assert "detail" in data
        
        finally:
            settings.AUTH_MODE = original_mode
    
    def test_login_user_not_found(self, client):
        """测试登录失败（用户不存在）"""
        response = client.post(
            "/api/auth/login",
            json={"username": "nonexistent", "password": "password"}
        )
        
        assert response.status_code == 401
    
    def test_get_current_user(self, client, test_user):
        """测试获取当前用户"""
        original_mode = settings.AUTH_MODE
        
        try:
            settings.AUTH_MODE = "multi_user"
            
            # 先登录获取 Token
            login_response = client.post(
                "/api/auth/login",
                json={"username": "testuser", "password": "testpassword"}
            )
            token = login_response.json()["access_token"]
            
            # 使用 Token 获取用户信息
            response = client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["username"] == "testuser"
            assert data["display_name"] == "Test User"
        
        finally:
            settings.AUTH_MODE = original_mode
    
    def test_get_current_user_without_token(self, client):
        """测试未提供 Token 获取用户"""
        response = client.get("/api/auth/me")
        
        assert response.status_code == 403  # FastAPI HTTPBearer 返回 403
    
    def test_get_current_user_invalid_token(self, client):
        """测试使用无效 Token 获取用户"""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid_token"}
        )
        
        assert response.status_code == 401
    
    def test_refresh_token(self, client, test_user):
        """测试刷新 Token"""
        original_mode = settings.AUTH_MODE
        
        try:
            settings.AUTH_MODE = "multi_user"
            
            # 先登录获取 Token
            login_response = client.post(
                "/api/auth/login",
                json={"username": "testuser", "password": "testpassword"}
            )
            old_token = login_response.json()["access_token"]
            
            # 刷新 Token
            response = client.post(
                "/api/auth/refresh",
                headers={"Authorization": f"Bearer {old_token}"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert "user" in data
            assert data["user"]["username"] == "testuser"
        
        finally:
            settings.AUTH_MODE = original_mode
    
    def test_refresh_token_invalid(self, client):
        """测试刷新无效 Token"""
        response = client.post(
            "/api/auth/refresh",
            json={"token": "invalid_token"}
        )
        
        assert response.status_code == 401
    
    def test_update_profile(self, client, test_user):
        """测试更新用户资料"""
        original_mode = settings.AUTH_MODE
        
        try:
            settings.AUTH_MODE = "multi_user"
            
            # 登录
            login_response = client.post(
                "/api/auth/login",
                json={"username": "testuser", "password": "testpassword"}
            )
            token = login_response.json()["access_token"]
            
            # 更新资料
            response = client.put(
                "/api/auth/profile",
                headers={"Authorization": f"Bearer {token}"},
                json={"display_name": "Updated Name"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["display_name"] == "Updated Name"
        
        finally:
            settings.AUTH_MODE = original_mode
    
    def test_change_password(self, client, test_user):
        """测试修改密码"""
        original_mode = settings.AUTH_MODE
        
        try:
            settings.AUTH_MODE = "multi_user"
            
            # 登录
            login_response = client.post(
                "/api/auth/login",
                json={"username": "testuser", "password": "testpassword"}
            )
            token = login_response.json()["access_token"]
            
            # 修改密码
            response = client.post(
                "/api/auth/change-password",
                headers={"Authorization": f"Bearer {token}"},
                json={"old_password": "testpassword", "new_password": "newpassword"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            
            # 使用新密码登录
            new_login_response = client.post(
                "/api/auth/login",
                json={"username": "testuser", "password": "newpassword"}
            )
            assert new_login_response.status_code == 200
        
        finally:
            settings.AUTH_MODE = original_mode
    
    def test_change_password_wrong_old(self, client, test_user):
        """测试修改密码失败（旧密码错误）"""
        original_mode = settings.AUTH_MODE
        
        try:
            settings.AUTH_MODE = "multi_user"
            
            # 登录
            login_response = client.post(
                "/api/auth/login",
                json={"username": "testuser", "password": "testpassword"}
            )
            token = login_response.json()["access_token"]
            
            # 修改密码（旧密码错误）
            response = client.post(
                "/api/auth/change-password",
                headers={"Authorization": f"Bearer {token}"},
                json={"old_password": "wrongpassword", "new_password": "newpassword"}
            )
            
            assert response.status_code == 400
        
        finally:
            settings.AUTH_MODE = original_mode
    
    def test_complete_auth_flow(self, client, test_user):
        """测试完整的认证流程"""
        original_mode = settings.AUTH_MODE
        
        try:
            settings.AUTH_MODE = "multi_user"
            
            # 1. 登录
            login_response = client.post(
                "/api/auth/login",
                json={"username": "testuser", "password": "testpassword"}
            )
            assert login_response.status_code == 200
            token = login_response.json()["access_token"]
            
            # 2. 获取用户信息
            me_response = client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert me_response.status_code == 200
            assert me_response.json()["username"] == "testuser"
            
            # 3. 更新资料
            profile_response = client.put(
                "/api/auth/profile",
                headers={"Authorization": f"Bearer {token}"},
                json={"display_name": "New Name"}
            )
            assert profile_response.status_code == 200
            
            # 4. 刷新 Token
            refresh_response = client.post(
                "/api/auth/refresh",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert refresh_response.status_code == 200
            new_token = refresh_response.json()["access_token"]
            
            # 5. 使用新 Token 获取信息
            new_me_response = client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {new_token}"}
            )
            assert new_me_response.status_code == 200
            assert new_me_response.json()["display_name"] == "New Name"
        
        finally:
            settings.AUTH_MODE = original_mode
