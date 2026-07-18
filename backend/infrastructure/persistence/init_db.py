"""创建当前版本需要的 SQLite 表；不创建默认用户。"""

from pathlib import Path

from sqlalchemy import create_engine

from backend.infrastructure.persistence.db.models import Base


def init_database(db_path: str = "data/beanmind.db") -> None:
    database = Path(db_path)
    database.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{database}")
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Initialize BeanMind database")
    parser.add_argument("--db-path", default="data/beanmind.db")
    init_database(parser.parse_args().db_path)
