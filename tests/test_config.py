"""配置管理单元测试"""
import pytest
from pathlib import Path
from backend.config import settings, Settings


class TestSettings:
    """配置管理测试类"""
    
    def test_settings_instance(self):
        """测试配置实例可以正常访问"""
        assert settings is not None
        assert isinstance(settings, Settings)
    
    def test_auth_mode(self):
        """测试鉴权模式配置"""
        assert settings.AUTH_MODE in ["none", "single_user", "multi_user"]
    
    def test_jwt_config(self):
        """测试JWT配置"""
        assert len(settings.JWT_SECRET_KEY) > 0
        assert settings.JWT_ALGORITHM == "HS256"
        assert settings.JWT_EXPIRATION_HOURS > 0
    
    def test_data_paths(self):
        """测试数据路径配置"""
        assert isinstance(settings.DATA_DIR, Path)
        assert isinstance(settings.LEDGER_FILE, Path)
        assert isinstance(settings.DATABASE_FILE, Path)
    
    def test_database_url(self):
        """测试数据库URL生成"""
        db_url = settings.database_url
        assert db_url.startswith("sqlite:///")
        assert "beanmind.db" in db_url
    
    def test_cors_origins_list(self):
        """测试CORS源列表"""
        origins = settings.cors_origins_list
        assert isinstance(origins, list)
        assert len(origins) > 0
    
    def test_ensure_directories(self):
        """测试目录创建功能"""
        # 这个方法应该在启动时已经执行
        assert settings.DATA_DIR.exists()
        assert settings.LEDGER_FILE.parent.exists()
