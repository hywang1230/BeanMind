"""数据库初始化脚本

从项目根目录运行: PYTHONPATH=. python backend/infrastructure/persistence/init_db.py
或使用: python -m backend.infrastructure.persistence.init_db
"""
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.infrastructure.persistence.db.models import (
    Base,
    User,
)


def init_database(db_path: str = "data/beanmind.db"):
    """初始化数据库
    
    Args:
        db_path: 数据库文件路径
    """
    # 确保 data 目录存在
    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 创建数据库引擎
    engine = create_engine(f"sqlite:///{db_path}", echo=True)
    
    # 创建所有表
    print("Creating all tables...")
    Base.metadata.create_all(engine)
    print("✅ All tables created successfully!")
    
    # 创建会话
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # 检查是否已有默认用户
        existing_user = session.query(User).filter_by(
            id="00000000-0000-0000-0000-000000000000"
        ).first()
        
        if not existing_user:
            # 创建默认用户（用于无鉴权模式）
            default_user = User(
                id="00000000-0000-0000-0000-000000000000",
                username="default",
                display_name="默认用户",
                password_hash=None
            )
            session.add(default_user)
            session.commit()
            print("✅ Default user created successfully!")
        else:
            print("ℹ️  Default user already exists, skipping...")
        
    except Exception as e:
        print(f"❌ Error creating default user: {e}")
        session.rollback()
        raise
    finally:
        session.close()
    
    print("\n🎉 Database initialization completed!")
    print(f"📁 Database file: {db_file.absolute()}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Initialize BeanMind database")
    parser.add_argument(
        "--db-path",
        default="data/beanmind.db",
        help="Database file path (default: data/beanmind.db)"
    )
    
    args = parser.parse_args()
    init_database(args.db_path)
