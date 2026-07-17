from pathlib import Path
import shutil

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.infrastructure.persistence.db.models import Base


@pytest.fixture
def ledger_path(tmp_path: Path) -> Path:
    source = Path(__file__).parent / "fixtures" / "ledger_projection"
    target = tmp_path / "ledger"
    shutil.copytree(source, target)
    return target / "main.beancount"


@pytest.fixture
def db_session(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'projection.db'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
