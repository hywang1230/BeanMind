from datetime import date
from decimal import Decimal

import pytest

from backend.infrastructure.persistence.db.models import (
    Base,
    LedgerIndexFile,
    LedgerPosting,
    LedgerTransaction,
    MonthlyBudget,
)
from backend.infrastructure.persistence.ledger_projection import (
    InvalidTransactionCursorError,
    LedgerProjectionDirtyError,
    LedgerProjectionService,
    TransactionQueryService,
    decode_transaction_cursor,
    encode_transaction_cursor,
)


def test_fixture_rebuild_is_idempotent_and_preserves_decimal(db_session, ledger_path):
    projection = LedgerProjectionService(db_session, ledger_path)

    first = projection.rebuild_all()
    old_id = (
        db_session.query(LedgerTransaction.id)
        .filter(LedgerTransaction.narration == "年末采购")
        .scalar()
    )
    second = projection.rebuild_all()

    assert first["transactions"] == second["transactions"] == 6
    assert db_session.query(LedgerTransaction).count() == 6
    assert (
        db_session.query(LedgerTransaction.id)
        .filter(LedgerTransaction.narration == "年末采购")
        .scalar()
        == old_id
    )
    amount_text = (
        db_session.query(LedgerPosting.amount_text)
        .filter(LedgerPosting.amount_text.like("123.456%"))
        .scalar()
    )
    assert Decimal(amount_text) == Decimal("123.456789123456789")
    assert projection.check_consistency()["consistent"] is True


def test_create_all_is_idempotent_and_preserves_existing_business_data(db_session):
    budget = MonthlyBudget(id="existing-budget", month="2025-01", currency="CNY")
    db_session.add(budget)
    db_session.commit()

    Base.metadata.create_all(db_session.bind)

    assert db_session.get(MonthlyBudget, "existing-budget").month == "2025-01"


def test_cursor_round_trip_and_validation():
    cursor = encode_transaction_cursor(date(2025, 1, 15), "fixed-id")
    assert decode_transaction_cursor(cursor) == (date(2025, 1, 15), "fixed-id")

    for invalid in ("%%", "e30", "eyJ2IjoyLCJkYXRlIjoiMjAyNS0wMS0xNSIsImlkIjoieCJ9"):
        with pytest.raises(InvalidTransactionCursorError):
            decode_transaction_cursor(invalid)


def test_keyset_paging_has_no_duplicates_or_omissions(db_session, ledger_path):
    LedgerProjectionService(db_session, ledger_path).rebuild_all()
    query = TransactionQueryService(db_session, ledger_path)
    ids = []
    cursor = None
    while True:
        page = query.list_transactions(limit=1, cursor=cursor)
        ids.extend(item["id"] for item in page["items"])
        if not page["has_more"]:
            assert page["next_cursor"] is None
            break
        cursor = page["next_cursor"]

    assert len(ids) == 6
    assert len(set(ids)) == 6
    assert ids[0] not in {"fixed-lunch-2025-01-15", "fixed-salary-2025-01"}


def test_newer_transaction_inserted_between_pages_does_not_shift_cursor(db_session, ledger_path):
    LedgerProjectionService(db_session, ledger_path).rebuild_all()
    query = TransactionQueryService(db_session, ledger_path)
    first = query.list_transactions(limit=2)
    first_ids = {item["id"] for item in first["items"]}

    db_session.add(
        LedgerTransaction(
            id="inserted-after-first-page",
            date=date(2026, 1, 1),
            flag="*",
            narration="翻页期间新增",
            transaction_type="other",
            source_file=str(ledger_path),
            source_lineno=999,
            content_hash="inserted-after-first-page",
            links_json="[]",
        )
    )
    db_session.commit()

    second = query.list_transactions(limit=2, cursor=first["next_cursor"])
    second_ids = {item["id"] for item in second["items"]}

    assert "inserted-after-first-page" not in second_ids
    assert first_ids.isdisjoint(second_ids)


def test_filters_are_combined_with_and(db_session, ledger_path):
    LedgerProjectionService(db_session, ledger_path).rebuild_all()
    query = TransactionQueryService(db_session, ledger_path)

    result = query.list_transactions(
        account="Expenses:Travel",
        transaction_type="expense",
        tags=["travel", "missing"],
        description="酒店",
        start_date="2025-01-01",
        end_date="2025-12-31",
    )
    assert [item["description"] for item in result["items"]] == ["出差住宿"]
    assert "total" not in result
    assert query.list_transactions(description="不存在")["items"] == []


def test_refresh_replaces_only_changed_file(db_session, ledger_path):
    projection = LedgerProjectionService(db_session, ledger_path)
    projection.rebuild_all()
    unchanged_id = (
        db_session.query(LedgerTransaction.id)
        .filter(LedgerTransaction.narration == "年末采购")
        .scalar()
    )
    year_file = ledger_path.parent / "transactions_2025.beancount"
    with year_file.open("a", encoding="utf-8") as handle:
        handle.write(
            '\n2025-03-01 * "咖啡店" "咖啡" #food\n'
            "  Expenses:Food  20 CNY\n"
            "  Assets:Cash   -20 CNY\n"
        )

    result = projection.refresh_file(year_file)

    assert result["transactions"] == 4
    assert db_session.query(LedgerTransaction).count() == 7
    assert db_session.get(LedgerTransaction, unchanged_id) is not None
    assert projection.check_consistency()["consistent"] is True


def test_unchanged_startup_reuses_projection_and_main_change_rebuilds(
    db_session, ledger_path, monkeypatch
):
    projection = LedgerProjectionService(db_session, ledger_path)
    projection.rebuild_all()
    indexed_at = {row.path: row.indexed_at for row in db_session.query(LedgerIndexFile).all()}

    assert projection.ensure_current()["status"] == "READY"
    assert {
        row.path: row.indexed_at for row in db_session.query(LedgerIndexFile).all()
    } == indexed_at

    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write("\n; global change\n")
    calls = []
    monkeypatch.setattr(projection, "full_rebuild", lambda: calls.append(True) or {"full": True})
    assert projection.ensure_current() == {"full": True}
    assert calls == [True]


def test_unsafe_file_refresh_falls_back_to_full_rebuild(db_session, ledger_path, monkeypatch):
    projection = LedgerProjectionService(db_session, ledger_path)
    projection.rebuild_all()
    year_file = ledger_path.parent / "transactions_2025.beancount"
    with year_file.open("a", encoding="utf-8") as handle:
        handle.write('\noption "operating_currency" "USD"\n')
    called = []
    monkeypatch.setattr(projection, "full_rebuild", lambda: called.append(True) or {"full": True})

    assert projection.refresh_file(year_file) == {"full": True}
    assert called == [True]


def test_missing_or_dirty_projection_is_not_read(db_session, ledger_path):
    query = TransactionQueryService(db_session, ledger_path)
    with pytest.raises(LedgerProjectionDirtyError):
        query.list_transactions()

    projection = query.projection
    projection.rebuild_all()
    projection.mark_dirty(ledger_path, "test failure")
    with pytest.raises(LedgerProjectionDirtyError):
        query.list_transactions()

    projection.rebuild_all()
    assert query.list_transactions(limit=1)["items"]


def test_consistency_difference_is_explicit_and_marks_dirty(db_session, ledger_path):
    projection = LedgerProjectionService(db_session, ledger_path)
    projection.rebuild_all()
    db_session.query(LedgerPosting).first().amount_text = "999"
    db_session.commit()

    with pytest.raises(ValueError, match="amounts expected="):
        projection.check_consistency()
    assert (
        db_session.query(LedgerIndexFile.status)
        .filter(LedgerIndexFile.path == str(ledger_path.resolve()))
        .scalar()
        == "DIRTY"
    )
