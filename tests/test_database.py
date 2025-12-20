"""数据库测试"""
import pytest
from sqlalchemy.orm import Session
from backend.config import get_db
from backend.infrastructure.persistence.db.models import User


class TestDatabase:
    """数据库连接测试类"""
    
    def test_get_db_session(self):
        """测试获取数据库会话"""
        db = next(get_db())
        
        assert db is not None
        assert isinstance(db, Session)
        
        db.close()
    
    def test_query_users(self):
        """测试查询用户"""
        db = next(get_db())
        
        try:
            users = db.query(User).all()
            assert isinstance(users, list)
            
            # 应该至少有一个默认用户
            assert len(users) >= 1
            
            # 检查第一个用户
            if users:
                user = users[0]
                assert hasattr(user, 'id')
                assert hasattr(user, 'username')
                assert hasattr(user, 'created_at')
        finally:
            db.close()
    
    def test_default_user_exists(self):
        """测试默认用户存在"""
        db = next(get_db())
        
        try:
            default_user = db.query(User).filter_by(username="default").first()
            
            assert default_user is not None
            assert default_user.username == "default"
            assert default_user.display_name == "默认用户"
        finally:
            db.close()
