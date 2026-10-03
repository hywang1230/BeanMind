"""Incremental projection uses isolated ledgers and disk SQLite only."""
import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from backend.infrastructure.persistence.db.models import LedgerPosting, LedgerTransaction
from backend.infrastructure.persistence.ledger_projection import LedgerProjectionService, _fingerprint
from beancount.parser import parser


def txn(number, *, explicit=True, extra="", amount=1):
    identity = f'  id: "item-{number}"\n' if explicit else ""
    return (f'2025-01-01 * "item {number}" #food ^link\n' + identity + extra
            + f'  Expenses:Food  {amount} CNY\n  Assets:Cash  -{amount} CNY\n\n')


@pytest.fixture
def simple(tmp_path, db_session):
    main = tmp_path / "main.beancount"
    year = tmp_path / "2025.beancount"
    other = tmp_path / "2024.beancount"
    main.write_text('option "operating_currency" "CNY"\n2000-01-01 open Assets:Cash CNY\n2000-01-01 open Expenses:Food CNY\ninclude "2025.beancount"\ninclude "2024.beancount"\n')
    year.write_text(txn(1) + txn(2))
    other.write_text("")
    service = LedgerProjectionService(db_session, main)
    service.full_rebuild()
    return service, year, other


def snapshot(db):
    db.expire_all()
    return sorted((row.id, row.source_file, row.source_lineno, row.content_hash,
                   row.links_json, tuple((p.sequence, p.account, p.amount_text, p.currency,
                                         p.cost_text, p.price_text) for p in row.postings),
                   tuple(t.tag for t in row.tags)) for row in db.query(LedgerTransaction).all())


def assert_full_equivalent(service):
    before = snapshot(service.db)
    service.full_rebuild()
    assert snapshot(service.db) == before


def test_append_does_not_write_existing_children_or_construct_models(simple, monkeypatch):
    service, year, _ = simple
    created = service.db.get(LedgerTransaction, "item-1").created_at
    original = service._model_from_entry
    constructed = []
    monkeypatch.setattr(service, "_model_from_entry", lambda entry, *args: (constructed.append(entry.meta.get("id")), original(entry, *args))[1])
    statements = []
    def track(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(service.db.bind, "before_cursor_execute", track)
    try:
        year.write_text(year.read_text() + txn(3))
        assert service.refresh_file(year)["transactions"] == 3
    finally:
        event.remove(service.db.bind, "before_cursor_execute", track)
    assert constructed == ["item-3"]
    assert not any(stmt.lstrip().upper().startswith("DELETE") for stmt in statements)
    assert service.db.get(LedgerTransaction, "item-1").created_at == created
    assert_full_equivalent(service)


@pytest.mark.parametrize("explicit", [True, False])
def test_edit_position_and_historical_ids_match_full_rebuild(simple, explicit):
    service, year, _ = simple
    year.write_text(txn(1) + txn(2, explicit=explicit))
    service.full_rebuild()
    children = service.db.query(LedgerPosting.id).filter(LedgerPosting.transaction_id == "item-2").all()
    created = service.db.get(LedgerTransaction, "item-1").created_at
    year.write_text(txn(1, extra='  note: "preserved"\n', amount=2) + txn(2, explicit=explicit))
    service.refresh_files([year])
    assert service.db.get(LedgerTransaction, "item-1").created_at == created
    if explicit:
        assert service.db.query(LedgerPosting.id).filter(LedgerPosting.transaction_id == "item-2").all() == children
    assert_full_equivalent(service)


def test_cross_file_move_and_delete_are_atomic(simple):
    service, year, other = simple
    created = service.db.get(LedgerTransaction, "item-1").created_at
    year.write_text(txn(2))
    other.write_text(txn(1))
    service.refresh_files([year, other])
    assert service.db.get(LedgerTransaction, "item-1").created_at == created
    assert_full_equivalent(service)
    other.write_text("")
    service.refresh_files([other])
    assert service.db.get(LedgerTransaction, "item-1") is None
    assert_full_equivalent(service)


@pytest.mark.parametrize("directive", ['option "booking_method" "FIFO"\n', 'plugin "beancount.plugins.auto_accounts"\n'])
def test_global_semantics_uses_loader_difference(simple, monkeypatch, directive):
    service, year, _ = simple
    service.ledger_path.write_text(directive + service.ledger_path.read_text())
    calls = []
    monkeypatch.setattr(service, "_refresh_loaded_ledger", lambda started: calls.append(1) or {"fallback": True})
    assert service.refresh_files([year]) == {"fallback": True}
    assert calls == [1]


def test_duplicate_id_uses_loader_difference(simple, monkeypatch):
    service, year, other = simple
    other.write_text(txn(1))
    calls = []
    monkeypatch.setattr(service, "_refresh_loaded_ledger", lambda started: calls.append(1) or {"fallback": True})
    assert service.refresh_files([other]) == {"fallback": True}
    assert calls == [1]


def test_parsed_snapshot_is_reused_only_when_matching(simple, monkeypatch):
    service, year, _ = simple
    entries, errors, _ = parser.parse_file(str(year))
    assert not errors
    fp = _fingerprint(year)
    original = parser.parse_file
    calls = []
    monkeypatch.setattr(parser, "parse_file", lambda *a, **kw: (calls.append(1), original(*a, **kw))[1])
    service.refresh_files([year], parsed_files={str(year): (entries, fp)})
    assert not calls
    year.write_text(year.read_text() + txn(3))
    service.refresh_files([year], parsed_files={str(year): (entries, fp)})
    assert calls == [1]
    assert service.db.get(LedgerTransaction, "item-3") is not None


def test_failed_commit_rolls_back_all_changes_and_marks_dirty(simple, monkeypatch):
    service, year, other = simple
    before = snapshot(service.db)
    year.write_text(txn(2))
    other.write_text(txn(1, amount=2))
    original = service.db.commit
    calls = []
    def fail_once():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("commit fault")
        return original()
    monkeypatch.setattr(service.db, "commit", fail_once)
    with pytest.raises(RuntimeError, match="commit fault"):
        service.refresh_files([year, other])
    assert snapshot(service.db) == before
    assert service.status()["status"] == "DIRTY"


def test_strict_dirty_failure_is_propagated(simple, monkeypatch):
    service, year, _ = simple
    def fail():
        raise RuntimeError("cannot commit DIRTY")
    monkeypatch.setattr(service.db, "commit", fail)
    with pytest.raises(RuntimeError, match="cannot commit DIRTY"):
        service.mark_dirty_files([year])


def test_large_delete_is_chunked(simple):
    service, year, _ = simple
    year.write_text("".join(txn(i) for i in range(1100)))
    service.refresh_files([year])
    year.write_text("")
    statements = []
    def track(conn, cursor, stmt, params, ctx, many):
        if stmt.lstrip().upper().startswith("DELETE"):
            statements.append(len(params))
    event.listen(service.db.bind, "before_cursor_execute", track)
    try:
        service.refresh_files([year])
    finally:
        event.remove(service.db.bind, "before_cursor_execute", track)
    assert statements and max(statements) <= 400
    assert service.db.query(LedgerTransaction).count() == 0


def test_ready_check_and_reads_use_same_sqlite_snapshot(simple):
    service, _, _ = simple
    service.db.rollback()
    with service.db.bind.connect() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")
    service.assert_ready()
    raw = service.db.connection().connection.driver_connection
    assert raw.in_transaction
    with Session(service.db.bind) as writer:
        writer.query(LedgerTransaction).filter_by(id="item-1").update({"narration": "new"})
        writer.commit()
    assert service.db.get(LedgerTransaction, "item-1").narration == "item 1"
    service.db.rollback()
    assert service.db.get(LedgerTransaction, "item-1").narration == "new"


def test_interpolated_amount_uses_loader(simple, monkeypatch):
    service, year, _ = simple
    year.write_text(txn(1).replace("Assets:Cash  -1 CNY", "Assets:Cash"))
    calls = []
    original = service._refresh_loaded_ledger
    monkeypatch.setattr(service, "_refresh_loaded_ledger", lambda started: (calls.append(1), original(started))[1])
    service.refresh_files([year])
    assert calls == [1]
    assert service.db.query(LedgerPosting.amount_text).filter_by(account="Assets:Cash").scalar() == "-1"
    assert_full_equivalent(service)


def test_pending_recovery_precedes_rebuild(simple, monkeypatch):
    from backend.infrastructure.persistence.beancount import ledger_write

    service, _, _ = simple
    calls = []
    monkeypatch.setattr(ledger_write, "has_pending_write", lambda path: True)
    def recover(path, callback):
        calls.append("recover")
        callback()
        return True
    monkeypatch.setattr(ledger_write, "recover_ledger_write", recover)
    original = service._full_rebuild_impl
    monkeypatch.setattr(service, "_full_rebuild_impl", lambda: (calls.append("rebuild"), original())[1])
    service.ensure_current()
    assert calls == ["recover", "rebuild"]


def test_existing_balance_assertion_forces_full_validation(simple, monkeypatch):
    service, year, _ = simple
    service.ledger_path.write_text(service.ledger_path.read_text() + "\n2025-02-01 balance Assets:Cash -2 CNY\n")
    service.full_rebuild()
    year.write_text(txn(1, amount=2) + txn(2))
    calls = []
    original = service._refresh_loaded_ledger
    monkeypatch.setattr(service, "_refresh_loaded_ledger", lambda started: (calls.append(1), original(started))[1])
    with pytest.raises(ValueError):
        service.refresh_files([year])
    assert calls == [1]
    assert service.status()["status"] == "DIRTY"


@pytest.mark.parametrize("operation", ["create", "edit", "delete"])
def test_default_plugin_writes_only_changed_transactions(simple, monkeypatch, operation):
    service, year, _ = simple
    service.ledger_path.write_text('plugin "beancount.plugins.auto_accounts"\n' + service.ledger_path.read_text())
    service.full_rebuild()
    original = service._model_from_entry
    constructed = []
    monkeypatch.setattr(service, "_model_from_entry", lambda e, *a: (constructed.append(e.meta.get("id")), original(e, *a))[1])
    created = service.db.get(LedgerTransaction, "item-2").created_at
    child_ids = service.db.query(LedgerPosting.id).filter_by(transaction_id="item-2").all()
    if operation == "create":
        year.write_text(year.read_text() + txn(3))
    elif operation == "edit":
        year.write_text(txn(1, amount=2) + txn(2))
    else:
        year.write_text(txn(2))
    statements = []
    def track(conn, cursor, stmt, params, ctx, many):
        statements.append(stmt.upper())
    event.listen(service.db.bind, "before_cursor_execute", track)
    try:
        service.refresh_files([year])
    finally:
        event.remove(service.db.bind, "before_cursor_execute", track)
    assert constructed == {"create": ["item-3"], "edit": ["item-1"], "delete": []}[operation]
    assert all("WHERE" in stmt for stmt in statements if stmt.lstrip().startswith("DELETE"))
    assert service.db.get(LedgerTransaction, "item-2").created_at == created
    assert service.db.query(LedgerPosting.id).filter_by(transaction_id="item-2").all() == child_ids
    assert_full_equivalent(service)


@pytest.mark.parametrize("explicit", [True, False])
def test_loader_difference_duplicate_and_legacy_ids(simple, explicit):
    service, year, other = simple
    service.ledger_path.write_text('plugin "beancount.plugins.auto_accounts"\n' + service.ledger_path.read_text())
    other.write_text(txn(1, explicit=explicit))
    service.full_rebuild()
    year.write_text(txn(1, extra='  note: "position shift"\n', amount=2) + txn(2, explicit=explicit))
    service.refresh_files([year])
    assert_full_equivalent(service)
    other.write_text("")
    service.refresh_files([other])
    assert_full_equivalent(service)


def test_loader_difference_tracks_include_addition_and_removal(simple):
    from backend.infrastructure.persistence.db.models import LedgerIndexFile
    service, year, other = simple
    new = year.with_name("2026.beancount")
    new.write_text(txn(3))
    service.ledger_path.write_text(service.ledger_path.read_text() + 'include "2026.beancount"\n')
    service.refresh_files([service.ledger_path, new])
    assert service.db.get(LedgerTransaction, "item-3") is not None
    assert_full_equivalent(service)
    service.ledger_path.write_text(service.ledger_path.read_text().replace('include "2026.beancount"\n', ''))
    service.refresh_files([service.ledger_path])
    assert service.db.get(LedgerTransaction, "item-3") is None
    assert service.db.get(LedgerIndexFile, str(new)) is None
    assert_full_equivalent(service)


def test_plugin_changes_other_file_and_generates_virtual_transactions(simple, monkeypatch):
    import sys
    import types
    from beancount.core.data import Transaction

    service, year, other = simple
    other.write_text(txn(9))
    plugin = types.ModuleType("beanmind_projection_test_plugin")
    plugin.__plugins__ = ("transform",)
    def transform(entries, options):
        source = next((e for e in entries if isinstance(e, Transaction) and e.meta.get("id") == "item-1"), None)
        result = []
        for entry in entries:
            if isinstance(entry, Transaction) and entry.meta.get("id") == "item-9":
                entry = entry._replace(narration="source present" if source else "source absent")
            result.append(entry)
        if source:
            result.append(source._replace(meta={"filename": "<generated>", "lineno": 0, "id": "generated"}))
        return result, []
    plugin.transform = transform
    monkeypatch.setitem(sys.modules, plugin.__name__, plugin)
    service.ledger_path.write_text(f'plugin "{plugin.__name__}"\n' + service.ledger_path.read_text())
    service.full_rebuild()
    year.write_text(txn(2))
    service.refresh_files([year])
    assert service.db.get(LedgerTransaction, "item-9").narration == "source absent"
    assert service.db.get(LedgerTransaction, "generated") is None
    assert_full_equivalent(service)
    year.write_text(txn(1) + txn(2))
    service.refresh_files([year])
    assert service.db.get(LedgerTransaction, "item-9").narration == "source present"
    assert service.db.get(LedgerTransaction, "generated") is not None
    assert_full_equivalent(service)


def test_loader_difference_rejects_changed_source_during_load(simple, monkeypatch):
    from backend.infrastructure.persistence import ledger_projection
    service, year, _ = simple
    service.ledger_path.write_text('plugin "beancount.plugins.auto_accounts"\n' + service.ledger_path.read_text())
    service.full_rebuild()
    before = snapshot(service.db)
    original = ledger_projection.load_ledger_file
    def changing_load(*args, **kwargs):
        result = original(*args, **kwargs)
        year.write_text(year.read_text() + txn(3))
        return result
    monkeypatch.setattr(ledger_projection, "load_ledger_file", changing_load)
    with pytest.raises(ValueError, match="发生变化"):
        service.refresh_files([year])
    assert snapshot(service.db) == before
    assert service.status()["status"] == "DIRTY"


def test_loader_difference_commit_failure_preserves_projection(simple, monkeypatch):
    service, year, _ = simple
    service.ledger_path.write_text('plugin "beancount.plugins.auto_accounts"\n' + service.ledger_path.read_text())
    service.full_rebuild()
    before = snapshot(service.db)
    year.write_text(txn(2))
    original = service.db.commit
    calls = []
    def commit():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("commit fault")
        return original()
    monkeypatch.setattr(service.db, "commit", commit)
    with pytest.raises(RuntimeError, match="commit fault"):
        service.refresh_files([year])
    assert snapshot(service.db) == before
    assert service.status()["status"] == "DIRTY"


def test_loader_difference_recursive_wildcard_and_membership_change(simple, monkeypatch):
    from backend.infrastructure.persistence import ledger_projection
    service, year, _ = simple
    nested = year.parent / "nested" / "a" / "b"
    nested.mkdir(parents=True)
    included = nested / "one.beancount"
    included.write_text(txn(3))
    service.ledger_path.write_text(service.ledger_path.read_text() + 'include "nested/**/*.beancount"\n')
    service.refresh_files([service.ledger_path])
    assert service.db.get(LedgerTransaction, "item-3") is not None
    assert_full_equivalent(service)
    service.ledger_path.write_text('plugin "beancount.plugins.auto_accounts"\n' + service.ledger_path.read_text())
    service.full_rebuild()
    before = snapshot(service.db)
    original = ledger_projection.load_ledger_file
    def changing_membership(*args, **kwargs):
        result = original(*args, **kwargs)
        (nested / "two.beancount").write_text(txn(4))
        return result
    monkeypatch.setattr(ledger_projection, "load_ledger_file", changing_membership)
    with pytest.raises(ValueError, match="发生变化"):
        service.refresh_files([year])
    assert snapshot(service.db) == before
    assert service.status()["status"] == "DIRTY"


def test_plugin_physical_provenance_stays_tracked_and_new_sources_fail_closed(simple, monkeypatch):
    import sys
    import types
    from beancount.core.data import Transaction
    from backend.infrastructure.persistence.db.models import LedgerIndexFile

    service, year, _ = simple
    external = year.parent / "plugin-source.txt"
    external.write_text("first")
    plugin = types.ModuleType("beanmind_physical_provenance_test_plugin")
    plugin.__plugins__ = ("transform",)
    source_path = [external]
    def transform(entries, options):
        original = next(e for e in entries if isinstance(e, Transaction))
        generated = original._replace(
            meta={"filename": str(source_path[0]), "lineno": 1, "id": "physical-generated"},
            narration=source_path[0].read_text(),
        )
        return [*entries, generated], []
    plugin.transform = transform
    monkeypatch.setitem(sys.modules, plugin.__name__, plugin)
    service.ledger_path.write_text(f'plugin "{plugin.__name__}"\n' + service.ledger_path.read_text())
    service.full_rebuild()
    year.write_text(txn(1, amount=2) + txn(2))
    service.refresh_files([year])
    assert service.db.get(LedgerIndexFile, str(external)) is not None
    external.write_text("second")
    service.ensure_current()
    assert service.db.get(LedgerTransaction, "physical-generated").narration == "second"
    assert_full_equivalent(service)
    before = snapshot(service.db)
    new_source = external.with_name("new-plugin-source.txt")
    new_source.write_text("new source")
    source_path[0] = new_source
    with pytest.raises(ValueError, match="未验证的源文件"):
        service.refresh_files([year])
    assert snapshot(service.db) == before
    assert service.status()["status"] == "DIRTY"
    assert service.db.get(LedgerIndexFile, str(external)) is not None


def test_removed_plugin_provenance_is_still_verified_before_commit(simple, monkeypatch):
    import sys
    import types
    from beancount.core.data import Transaction
    from backend.infrastructure.persistence import ledger_projection
    service, year, _ = simple
    external = year.parent / "plugin-input.txt"
    external.write_text("emit")
    plugin = types.ModuleType("beanmind_removed_provenance_test_plugin")
    plugin.__plugins__ = ("transform",)
    def transform(entries, options):
        if external.read_text() == "emit":
            original = next(e for e in entries if isinstance(e, Transaction))
            return [*entries, original._replace(meta={"filename": str(external), "lineno": 1, "id": "generated"})], []
        return entries, []
    plugin.transform = transform
    monkeypatch.setitem(sys.modules, plugin.__name__, plugin)
    service.ledger_path.write_text(f'plugin "{plugin.__name__}"\n' + service.ledger_path.read_text())
    service.full_rebuild()
    before = snapshot(service.db)
    external.write_text("omit")
    original = ledger_projection.load_ledger_file
    def changing_input(*args, **kwargs):
        result = original(*args, **kwargs)
        external.write_text("emit")
        return result
    monkeypatch.setattr(ledger_projection, "load_ledger_file", changing_input)
    with pytest.raises(ValueError, match="发生变化"):
        service.refresh_files([year])
    assert snapshot(service.db) == before
    assert service.status()["status"] == "DIRTY"


def test_complete_candidate_checks_physical_source_once_and_reuses_final_record_sample(simple, monkeypatch):
    import time
    from pathlib import Path
    from beancount import loader
    from backend.infrastructure.persistence.beancount.ledger_write import (
        CandidateSnapshot, ValidatedFiles, sample_source_state,
    )

    service, year, _ = simple
    service.ledger_path.write_text('plugin "beancount.plugins.auto_accounts"\n' + service.ledger_path.read_text())
    year.write_text(''.join(txn(index) for index in range(20)))
    entries, errors, options = loader.load_file(str(service.ledger_path))
    assert not errors
    state = sample_source_state(service.ledger_path)
    candidate = CandidateSnapshot(entries, {path: value[2] for path, value in state.fingerprints.items()},
                                  options, service.ledger_path)
    parsed = ValidatedFiles({}, candidate)
    calls = []
    records = []
    original_is_file = Path.is_file
    original_record = service._record_file
    def is_file(path):
        calls.append(path)
        return original_is_file(path)
    def record(path, *args, **kwargs):
        records.append(kwargs.get('fingerprint'))
        return original_record(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'is_file', is_file)
    monkeypatch.setattr(service, '_record_file', record)
    service._refresh_loaded_ledger(time.perf_counter(), candidate, parsed)
    assert calls.count(year) == 1
    assert records and all(value is not None for value in records)
    assert parsed.projection_receipt.ready_committed
    assert_full_equivalent(service)
