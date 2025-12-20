"""密码工具单元测试"""
import pytest
from backend.infrastructure.auth.password_utils import PasswordUtils


class TestPasswordUtils:
    """密码工具测试类"""
    
    def test_hash_password(self):
        """测试密码加密"""
        password = "test_password_123"
        hashed = PasswordUtils.hash_password(password)
        
        assert hashed is not None
        assert isinstance(hashed, str)
        assert len(hashed) == 60  # bcrypt标准长度
        assert hashed.startswith("$2b$")  # bcrypt格式
    
    def test_verify_password_correct(self):
        """测试验证正确密码"""
        password = "test_password_123"
        hashed = PasswordUtils.hash_password(password)
        
        is_valid = PasswordUtils.verify_password(password, hashed)
        assert is_valid is True
    
    def test_verify_password_incorrect(self):
        """测试验证错误密码"""
        password = "test_password_123"
        wrong_password = "wrong_password"
        hashed = PasswordUtils.hash_password(password)
        
        is_valid = PasswordUtils.verify_password(wrong_password, hashed)
        assert is_valid is False
    
    def test_hash_uniqueness(self):
        """测试相同密码的哈希唯一性（使用盐值）"""
        password = "test_password_123"
        hash1 = PasswordUtils.hash_password(password)
        hash2 = PasswordUtils.hash_password(password)
        
        # 即使密码相同，哈希也应该不同（因为盐值不同）
        assert hash1 != hash2
        
        # 但都应该能验证相同的密码
        assert PasswordUtils.verify_password(password, hash1) is True
        assert PasswordUtils.verify_password(password, hash2) is True
    
    def test_needs_update(self):
        """测试密码哈希更新检查"""
        password = "test_password_123"
        hashed = PasswordUtils.hash_password(password)
        
        # bcrypt哈希通常不需要更新
        needs_update = PasswordUtils.needs_update(hashed)
        assert needs_update is False
