"""TransactionMetadata ORM 模型单元测试

测试 TransactionMetadata 模型的所有功能。
"""
import pytest
from datetime import datetime
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.infrastructure.persistence.db.models import (
    Base,
    User,
    TransactionMetadata
)


@pytest.fixture
def db_session():
    """创建测试数据库会话"""
    # 使用内存数据库
    engine = create_engine("sqlite:///:memory:")
    
    # 在 SQLite 中启用外键约束
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    yield session
    
    session.close()


@pytest.fixture
def test_user(db_session):
    """创建测试用户"""
    user = User(
        username="testuser",
        password_hash="hashed_password",
        display_name="Test User"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestTransactionMetadata:
    """TransactionMetadata 模型测试类"""
    
    def test_create_transaction_metadata(self, db_session, test_user):
        """测试创建交易元数据"""
        sync_time = datetime.now()
        metadata = TransactionMetadata(
            user_id=test_user.id,
            beancount_id="txn-001",
            sync_at=sync_time,
            notes="测试交易"
        )
        
        db_session.add(metadata)
        db_session.commit()
        db_session.refresh(metadata)
        
        assert metadata.id is not None
        assert metadata.user_id == test_user.id
        assert metadata.beancount_id == "txn-001"
        assert metadata.sync_at == sync_time
        assert metadata.notes == "测试交易"
        assert metadata.created_at is not None
        assert metadata.updated_at is not None
    
    def test_transaction_metadata_without_notes(self, db_session, test_user):
        """测试创建不带备注的交易元数据"""
        metadata = TransactionMetadata(
            user_id=test_user.id,
            beancount_id="txn-002",
            sync_at=datetime.now()
        )
        
        db_session.add(metadata)
        db_session.commit()
        db_session.refresh(metadata)
        
        assert metadata.notes is None
    
    def test_user_relationship(self, db_session, test_user):
        """测试与 User 的关系"""
        metadata = TransactionMetadata(
            user_id=test_user.id,
            beancount_id="txn-003",
            sync_at=datetime.now()
        )
        
        db_session.add(metadata)
        db_session.commit()
        db_session.refresh(metadata)
        
        # 测试正向关系
        assert metadata.user is not None
        assert metadata.user.id == test_user.id
        assert metadata.user.username == "testuser"
        
        # 测试反向关系（backref）
        db_session.refresh(test_user)
        assert len(test_user.transaction_metadata) > 0
        assert metadata in test_user.transaction_metadata
    
    def test_cascade_delete(self, db_session, test_user):
        """测试级联删除（删除用户时，关联的交易元数据也会被删除）"""
        metadata1 = TransactionMetadata(
            user_id=test_user.id,
            beancount_id="txn-004",
            sync_at=datetime.now()
        )
        metadata2 = TransactionMetadata(
            user_id=test_user.id,
            beancount_id="txn-005",
            sync_at=datetime.now()
        )
        
        db_session.add(metadata1)
        db_session.add(metadata2)
        db_session.commit()
        
        # 确认已创建
        count_before = db_session.query(TransactionMetadata).filter_by(user_id=test_user.id).count()
        assert count_before == 2
        
        # 删除交易元数据（测试外键约束）
        db_session.delete(metadata1)
        db_session.commit()
        
        # 验证删除成功
        count_after = db_session.query(TransactionMetadata).filter_by(user_id=test_user.id).count()
        assert count_after == 1
    
    def test_query_by_user_id(self, db_session, test_user):
        """测试按用户 ID 查询"""
        # 创建多个交易元数据
        for i in range(5):
            metadata = TransactionMetadata(
                user_id=test_user.id,
                beancount_id=f"txn-{i:03d}",
                sync_at=datetime.now()
            )
            db_session.add(metadata)
        
        db_session.commit()
        
        # 查询
        results = db_session.query(TransactionMetadata).filter_by(user_id=test_user.id).all()
        assert len(results) == 5
    
    def test_query_by_beancount_id(self, db_session, test_user):
        """测试按 beancount_id 查询"""
        metadata = TransactionMetadata(
            user_id=test_user.id,
            beancount_id="txn-unique-123",
            sync_at=datetime.now()
        )
        
        db_session.add(metadata)
        db_session.commit()
        
        # 查询
        result = db_session.query(TransactionMetadata).filter_by(
            beancount_id="txn-unique-123"
        ).first()
        
        assert result is not None
        assert result.beancount_id == "txn-unique-123"
    
    def test_update_notes(self, db_session, test_user):
        """测试更新备注"""
        metadata = TransactionMetadata(
            user_id=test_user.id,
            beancount_id="txn-006",
            sync_at=datetime.now(),
            notes="原始备注"
        )
        
        db_session.add(metadata)
        db_session.commit()
        
        # 更新备注
        metadata.notes = "更新后的备注"
        db_session.commit()
        db_session.refresh(metadata)
        
        assert metadata.notes == "更新后的备注"
        assert metadata.updated_at > metadata.created_at
    
    def test_to_dict(self, db_session, test_user):
        """测试转换为字典"""
        sync_time = datetime.now()
        metadata = TransactionMetadata(
            user_id=test_user.id,
            beancount_id="txn-007",
            sync_at=sync_time,
            notes="测试字典转换"
        )
        
        db_session.add(metadata)
        db_session.commit()
        db_session.refresh(metadata)
        
        data = metadata.to_dict()
        
        assert "id" in data
        assert data["user_id"] == test_user.id
        assert data["beancount_id"] == "txn-007"
        assert data["sync_at"] == sync_time
        assert data["notes"] == "测试字典转换"
        assert "created_at" in data
        assert "updated_at" in data
    
    def test_repr(self, db_session, test_user):
        """测试字符串表示"""
        metadata = TransactionMetadata(
            user_id=test_user.id,
            beancount_id="txn-008",
            sync_at=datetime.now()
        )
        
        db_session.add(metadata)
        db_session.commit()
        db_session.refresh(metadata)
        
        repr_str = repr(metadata)
        assert "TransactionMetadata" in repr_str
        assert metadata.id in repr_str
        assert "txn-008" in repr_str
    
    def test_order_by_sync_at(self, db_session, test_user):
        """测试按同步时间排序"""
        import time
        
        # 创建多个交易元数据，确保时间不同
        metadata_list = []
        for i in range(3):
            metadata = TransactionMetadata(
                user_id=test_user.id,
                beancount_id=f"txn-{i:03d}",
                sync_at=datetime.now()
            )
            db_session.add(metadata)
            metadata_list.append(metadata)
            time.sleep(0.01)  # 确保时间不同
        
        db_session.commit()
        
        # 按 sync_at 倒序查询
        results = db_session.query(TransactionMetadata).filter_by(
            user_id=test_user.id
        ).order_by(TransactionMetadata.sync_at.desc()).all()
        
        assert len(results) == 3
        # 验证顺序（最新的在前）
        for i in range(len(results) - 1):
            assert results[i].sync_at >= results[i + 1].sync_at
