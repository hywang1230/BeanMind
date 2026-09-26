import pytest

from backend.application.services import TransactionApplicationService
from backend.infrastructure.persistence.beancount.beancount_service import BeancountService
from backend.infrastructure.persistence.beancount.repositories import (
    AccountRepositoryImpl,
    TransactionRepositoryImpl,
)
from backend.infrastructure.persistence.db.models import LedgerTransaction
from backend.infrastructure.persistence.ledger_projection import (
    LedgerProjectionDirtyError,
    LedgerProjectionService,
    TransactionQueryService,
)


def _application_service(beancount, db_session, projection):
    repository = TransactionRepositoryImpl(
        beancount,
        db_session,
        projection,
        load_transactions=False,
    )
    return TransactionApplicationService(repository, AccountRepositoryImpl(beancount))


def test_create_cross_year_update_and_delete_refresh_only_affected_files(
    db_session, ledger_path, monkeypatch
):
    projection = LedgerProjectionService(db_session, ledger_path)
    projection.rebuild_all()
    beancount = BeancountService(ledger_path)
    monkeypatch.setattr(
        beancount,
        "reload",
        lambda: (_ for _ in ()).throw(AssertionError("写后不应完整 reload")),
    )

    created = _application_service(beancount, db_session, projection).create_transaction(
        txn_date="2025-04-01",
        description="命令测试",
        payee="测试商户",
        postings=[
            {"account": "Expenses:Food", "amount": "12.34", "currency": "CNY"},
            {"account": "Assets:Cash", "amount": "-12.34", "currency": "CNY"},
        ],
    )
    transaction_id = created["id"]
    assert len(transaction_id) == 32
    assert db_session.get(LedgerTransaction, transaction_id) is not None

    updated = _application_service(beancount, db_session, projection).update_transaction(
        transaction_id,
        txn_date="2024-04-01",
        description="跨年命令测试",
    )
    assert updated["id"] == transaction_id
    projected = db_session.get(LedgerTransaction, transaction_id)
    assert projected.date.isoformat() == "2024-04-01"
    assert projected.source_file.endswith("transactions_2024.beancount")

    deleted = _application_service(beancount, db_session, projection).delete_transaction(
        transaction_id
    )
    assert deleted is True
    assert db_session.get(LedgerTransaction, transaction_id) is None
    assert projection.check_consistency()["consistent"] is True


def test_projection_failure_keeps_beancount_write_and_marks_dirty(
    db_session, ledger_path, monkeypatch
):
    projection = LedgerProjectionService(db_session, ledger_path)
    projection.rebuild_all()
    beancount = BeancountService(ledger_path)
    year_file = ledger_path.parent / "transactions_2025.beancount"
    before = year_file.read_text(encoding="utf-8")
    monkeypatch.setattr(
        projection, "refresh_files", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    created = _application_service(beancount, db_session, projection).create_transaction(
        txn_date="2025-05-01",
        description="投影失败仍保留",
        postings=[
            {"account": "Expenses:Food", "amount": "1", "currency": "CNY"},
            {"account": "Assets:Cash", "amount": "-1", "currency": "CNY"},
        ],
    )

    assert created["id"]
    assert year_file.read_text(encoding="utf-8") != before
    assert "投影失败仍保留" in year_file.read_text(encoding="utf-8")
    with pytest.raises(LedgerProjectionDirtyError):
        TransactionQueryService(db_session, ledger_path).list_transactions()


def test_create_in_new_year_rebuilds_after_main_include_change(db_session, ledger_path):
    projection = LedgerProjectionService(db_session, ledger_path)
    projection.rebuild_all()
    beancount = BeancountService(ledger_path)

    created = _application_service(beancount, db_session, projection).create_transaction(
        txn_date="2026-01-01",
        description="新年度交易",
        postings=[
            {"account": "Expenses:Food", "amount": "2", "currency": "CNY"},
            {"account": "Assets:Cash", "amount": "-2", "currency": "CNY"},
        ],
    )

    assert 'include "transactions_2026.beancount"' in ledger_path.read_text(encoding="utf-8")
    projected = db_session.get(LedgerTransaction, created["id"])
    assert projected is not None
    assert projected.source_file.endswith("transactions_2026.beancount")
    assert projection.ensure_current()["status"] == "READY"


def test_update_uses_source_location_and_preserves_metadata_and_links(db_session, ledger_path):
    projection = LedgerProjectionService(db_session, ledger_path)
    projection.rebuild_all()
    beancount = BeancountService(ledger_path)

    updated = _application_service(beancount, db_session, projection).update_transaction(
        "fixed-salary-2025-01",
        description="工资已核对",
    )

    assert updated["links"] == ["payroll"]
    source = (ledger_path.parent / "transactions_2025.beancount").read_text(encoding="utf-8")
    assert 'id: "fixed-salary-2025-01"' in source
    assert 'note: "keep-me"' in source
    assert "^payroll" in source


def test_default_plugin_command_crud_never_recovers_its_own_manifest(
    db_session, ledger_path, monkeypatch
):
    from backend.infrastructure.persistence.beancount.ledger_write import has_pending_write

    ledger_path.write_text('plugin "beancount.plugins.auto_accounts"\n' + ledger_path.read_text())
    projection = LedgerProjectionService(db_session, ledger_path)
    projection.full_rebuild()
    beancount = BeancountService(ledger_path)
    def unexpected_rebuild():
        raise AssertionError("Normal plugin writes must use differences, not recovery/rebuild")
    monkeypatch.setattr(projection, "full_rebuild", unexpected_rebuild)
    created = _application_service(beancount, db_session, projection).create_transaction(
        txn_date="2025-04-01", description="plugin create",
        postings=[
            {"account": "Expenses:Food", "amount": "12.34", "currency": "CNY"},
            {"account": "Assets:Cash", "amount": "-12.34", "currency": "CNY"},
        ],
    )
    assert projection.status()["status"] == "READY"
    assert not has_pending_write(ledger_path)
    identity = created["id"]
    _application_service(beancount, db_session, projection).update_transaction(
        identity, txn_date="2026-04-01", description="plugin cross year",
    )
    assert db_session.get(LedgerTransaction, identity).date.year == 2026
    assert projection.status()["status"] == "READY"
    assert not has_pending_write(ledger_path)
    assert _application_service(beancount, db_session, projection).delete_transaction(identity)
    assert db_session.get(LedgerTransaction, identity) is None
    assert projection.status()["status"] == "READY"
    assert not has_pending_write(ledger_path)
    assert projection.check_consistency()["consistent"]
