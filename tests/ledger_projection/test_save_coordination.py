"""保存命令跨会话、外部变更及共享写锁回归，全部使用临时账本。"""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.application.services import TransactionApplicationService
from backend.infrastructure.persistence.beancount.beancount_provider import BeancountServiceProvider
from backend.infrastructure.persistence.beancount.beancount_service import BeancountService
from backend.infrastructure.persistence.beancount.ledger_write import ledger_lock, has_pending_write
from backend.infrastructure.persistence.beancount.repositories import AccountRepositoryImpl, TransactionRepositoryImpl
from backend.infrastructure.persistence.db.models import Base, LedgerTransaction, LedgerPosting
from backend.infrastructure.persistence.ledger_projection import LedgerProjectionService


def service(db, path):
    bean = BeancountServiceProvider.get_service(path)
    return TransactionApplicationService(
        TransactionRepositoryImpl(bean, db, LedgerProjectionService(db, path), load_transactions=False),
        AccountRepositoryImpl(bean),
    )


def create(app, description='probe'):
    return app.create_transaction(
        txn_date='2025-04-01', description=description,
        postings=[{'account':'Expenses:Food','amount':'1.23456789','currency':'CNY'},
                  {'account':'Assets:Cash','amount':'-1.23456789','currency':'CNY'}],
    )


def test_concurrent_commands_keep_both_transactions_and_projection(tmp_path, ledger_path):
    engine = create_engine(f'sqlite:///{tmp_path / "concurrent.db"}')
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, autoflush=False)
    with factory() as db:
        LedgerProjectionService(db, ledger_path).full_rebuild()
    def save(index):
        with factory() as db:
            return create(service(db, ledger_path), f'concurrent-{index}')['id']
    with ThreadPoolExecutor(max_workers=2) as executor:
        ids = list(executor.map(save, range(2)))
    with factory() as db:
        assert db.query(LedgerTransaction).filter(LedgerTransaction.id.in_(ids)).count() == 2
        assert LedgerProjectionService(db, ledger_path).check_consistency()['consistent']
    assert not has_pending_write(ledger_path)
    engine.dispose()


def test_stale_service_refreshes_source_before_edit(db_session, ledger_path):
    projection = LedgerProjectionService(db_session, ledger_path)
    projection.full_rebuild()
    app = service(db_session, ledger_path)
    app.get_transaction_by_id('fixed-salary-2025-01')
    year = ledger_path.parent / 'transactions_2025.beancount'
    year.write_text('; external comment\n' + year.read_text())
    result = app.update_transaction('fixed-salary-2025-01', description='fresh location')
    assert result['id'] == 'fixed-salary-2025-01'
    assert 'fresh location' in year.read_text()
    assert projection.check_consistency()['consistent']


def test_file_change_during_candidate_construction_rejected(db_session, ledger_path, monkeypatch):
    projection = LedgerProjectionService(db_session, ledger_path)
    projection.full_rebuild()
    app = service(db_session, ledger_path)
    repo = app.transaction_repository
    real_commit = repo._commit_changes
    year = ledger_path.parent / 'transactions_2025.beancount'
    def changed(changes):
        year.write_text(year.read_text() + '\n; outside mutation\n')
        return real_commit(changes)
    monkeypatch.setattr(repo, '_commit_changes', changed)
    with pytest.raises(RuntimeError, match='changed'):
        create(app)
    assert 'probe' not in year.read_text()
    assert 'outside mutation' in year.read_text()


def test_save_does_not_replace_untouched_postings(db_session, ledger_path):
    LedgerProjectionService(db_session, ledger_path).full_rebuild()
    before = {row.id: row.transaction_id for row in db_session.query(LedgerPosting).all()}
    app = service(db_session, ledger_path)
    added = create(app)
    after = {row.id: row.transaction_id for row in db_session.query(LedgerPosting).all()}
    assert all(after[key] == value for key, value in before.items())
    app.update_transaction(added['id'], description='changed')
    after = {row.id: row.transaction_id for row in db_session.query(LedgerPosting).all()}
    assert all(after[key] == value for key, value in before.items())


def test_provider_read_waits_for_shared_write_lock(ledger_path):
    started, done = Event(), Event()
    def read():
        started.set()
        BeancountServiceProvider.get_service(ledger_path)
        done.set()
    with ThreadPoolExecutor(max_workers=1) as executor:
        with ledger_lock(ledger_path):
            future = executor.submit(read)
            assert started.wait(2)
            assert not done.wait(.05)
        future.result(timeout=3)
    assert done.is_set()


def test_external_change_with_preserved_mtime_invalidates_account_view(db_session, ledger_path):
    import os
    LedgerProjectionService(db_session, ledger_path).full_rebuild()
    app = service(db_session, ledger_path)
    accounts = ledger_path.parent / 'accounts.beancount'
    before_stat = accounts.stat()
    accounts.write_text(accounts.read_text() + '\n2025-03-01 close Assets:Cash\n')
    os.utime(accounts, ns=(before_stat.st_atime_ns, before_stat.st_mtime_ns))
    year = ledger_path.parent / 'transactions_2025.beancount'
    before = year.read_bytes()
    with pytest.raises(ValueError, match='validation failed'):
        create(app)
    assert year.read_bytes() == before


def test_api_rejects_pre_open_date_without_mutating_source(db_session, ledger_path):
    from tests.conftest import build_api_client
    client = build_api_client(ledger_path, db_session, rebuild_projection=True)
    before = {path.name: path.read_bytes() for path in ledger_path.parent.glob('*.beancount')}
    response = client.post('/api/transactions', json={
        'date': '2019-01-01', 'description': 'invalid date',
        'postings': [{'account':'Expenses:Food','amount':'1','currency':'CNY'},
                     {'account':'Assets:Cash','amount':'-1','currency':'CNY'}],
    })
    assert response.status_code == 400
    assert {path.name: path.read_bytes() for path in ledger_path.parent.glob('*.beancount')} == before
    assert not has_pending_write(ledger_path)


def test_edit_preserves_posting_metadata_when_request_omits_it(db_session, ledger_path):
    year = ledger_path.parent / 'transactions_2025.beancount'
    year.write_text(year.read_text().replace('  Assets:Bank    10000 CNY',
                                            '  Assets:Bank    10000 CNY\n    note: "preserve-posting"'))
    projection = LedgerProjectionService(db_session, ledger_path)
    projection.full_rebuild()
    app = service(db_session, ledger_path)
    app.update_transaction('fixed-salary-2025-01', postings=[
        {'account':'Assets:Bank','amount':'10001','currency':'CNY'},
        {'account':'Income:Salary','amount':'-10001','currency':'CNY'},
    ])
    assert 'preserve-posting' in year.read_text()
    assert 'keep-me' in year.read_text()
    assert '^payroll' in year.read_text()
    assert projection.check_consistency()['consistent']


def test_target_block_parse_falls_back_for_parser_context(db_session, ledger_path):
    year = ledger_path.parent / 'transactions_2025.beancount'
    year.write_text('pushtag #context-tag\n' + year.read_text() + '\npoptag #context-tag\n')
    projection = LedgerProjectionService(db_session, ledger_path)
    projection.full_rebuild()
    app = service(db_session, ledger_path)
    result = app.update_transaction('fixed-salary-2025-01', description='context preserved')
    assert 'context-tag' in result['tags']
    assert 'keep-me' in year.read_text()
    assert 'pushtag #context-tag' in year.read_text()
    assert projection.check_consistency()['consistent']
