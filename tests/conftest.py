from __future__ import annotations

from pathlib import Path
import shutil
from typing import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.config import settings
from backend.infrastructure.persistence.beancount.beancount_provider import BeancountServiceProvider
from backend.infrastructure.persistence.db.models import Base
from backend.interfaces.api import account as account_api
from backend.interfaces.api import reports as reports_api
from backend.interfaces.api import transaction as transaction_api
from backend.infrastructure.persistence.ledger_projection import (
    LedgerProjectionService,
    TransactionQueryService,
)
from backend.config import get_db


CORE_FIXTURE = Path(__file__).parent / "fixtures" / "core_financial"
PROJECTION_FIXTURE = Path(__file__).parent / "fixtures" / "ledger_projection"


@pytest.fixture
def ledger_path(tmp_path: Path) -> Path:
    """Default projection fixture ledger for existing projection tests."""
    source = PROJECTION_FIXTURE
    target = tmp_path / "ledger"
    shutil.copytree(source, target)
    return target / "main.beancount"


@pytest.fixture
def core_ledger_path(tmp_path: Path) -> Path:
    """Core financial fixture: multi-posting, multi-currency, open/close, reports."""
    target = tmp_path / "core_ledger"
    shutil.copytree(CORE_FIXTURE, target)
    return target / "main.beancount"


@pytest.fixture
def db_session(tmp_path: Path) -> Iterator[Session]:
    engine = create_engine(f"sqlite:///{tmp_path / 'projection.db'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def temp_ledger_env(core_ledger_path: Path, db_session: Session, monkeypatch: pytest.MonkeyPatch):
    """
    Point settings.LEDGER_FILE at a temp core fixture and clear Beancount cache.
    Guarantees no real LEDGER_FILE is used.
    """
    BeancountServiceProvider.clear()
    monkeypatch.setattr(settings, "LEDGER_FILE", core_ledger_path)
    yield {
        "ledger_path": core_ledger_path,
        "db_session": db_session,
    }
    BeancountServiceProvider.clear()


def build_api_client(
    ledger_path: Path,
    db_session: Session,
    *,
    include_accounts: bool = True,
    include_transactions: bool = True,
    include_reports: bool = True,
    rebuild_projection: bool = False,
) -> TestClient:
    """Build a TestClient bound to a temporary ledger and in-memory-like sqlite session."""
    BeancountServiceProvider.clear()
    settings.LEDGER_FILE = ledger_path

    app = FastAPI()
    if include_accounts:
        app.include_router(account_api.router)
    if include_transactions:
        app.include_router(transaction_api.router)
    if include_reports:
        app.include_router(reports_api.router)

    def _db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _db
    query = TransactionQueryService(db_session, ledger_path)
    app.dependency_overrides[transaction_api.get_transaction_query_service] = lambda: query
    app.dependency_overrides[transaction_api.get_projection_service] = lambda: query.projection
    app.dependency_overrides[reports_api.get_beancount_service] = (
        lambda: BeancountServiceProvider.get_service(ledger_path)
    )
    app.dependency_overrides[reports_api.get_transaction_query_service] = lambda: query

    if rebuild_projection:
        LedgerProjectionService(db_session, ledger_path).rebuild_all()

    return TestClient(app)


@pytest.fixture
def core_api_client(temp_ledger_env) -> TestClient:
    env = temp_ledger_env
    return build_api_client(
        env["ledger_path"],
        env["db_session"],
        rebuild_projection=True,
    )
