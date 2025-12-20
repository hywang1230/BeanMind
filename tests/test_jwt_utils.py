"""JWT工具单元测试"""
import pytest
from datetime import datetime, timedelta
from backend.infrastructure.auth.jwt_utils import JWTUtils


class TestJWTUtils:
    """JWT工具测试类"""
    
    def test_create_access_token(self):
        """测试创建访问令牌"""
        data = {"sub": "test_user", "username": "admin"}
        token = JWTUtils.create_access_token(data)
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_verify_token_success(self):
        """测试验证有效Token"""
        data = {"sub": "test_user", "username": "admin"}
        token = JWTUtils.create_access_token(data)
        
        payload = JWTUtils.verify_token(token)
        
        assert payload is not None
        assert payload["sub"] == "test_user"
        assert payload["username"] == "admin"
        assert "exp" in payload
    
    def test_verify_token_invalid(self):
        """测试验证无效Token"""
        payload = JWTUtils.verify_token("invalid.token.here")
        assert payload is None
    
    def test_get_token_expiry(self):
        """测试获取Token过期时间"""
        data = {"sub": "test_user"}
        token = JWTUtils.create_access_token(data)
        
        expiry = JWTUtils.get_token_expiry(token)
        
        assert expiry is not None
        assert isinstance(expiry, datetime)
        assert expiry > datetime.utcnow()
    
    def test_is_token_expired(self):
        """测试Token过期检查"""
        data = {"sub": "test_user"}
        token = JWTUtils.create_access_token(data)
        
        # 新创建的token不应该过期
        assert JWTUtils.is_token_expired(token) is False
        
        # 无效token应该被视为过期
        assert JWTUtils.is_token_expired("invalid.token") is True
    
    def test_custom_expiry(self):
        """测试自定义过期时间"""
        data = {"sub": "test_user"}
        expires_delta = timedelta(hours=2)
        token = JWTUtils.create_access_token(data, expires_delta)
        
        #验证Token可以被成功验证
        payload = JWTUtils.verify_token(token)
        assert payload is not None
        assert payload["sub"] == "test_user"
        
        # 验证Token有过期时间
        expiry = JWTUtils.get_token_expiry(token)
        assert expiry is not None
        assert expiry > datetime.utcnow()
