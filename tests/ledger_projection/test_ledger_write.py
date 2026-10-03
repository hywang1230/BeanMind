"""Isolated filesystem fault tests for the ledger write protocol."""

import os
import logging
from decimal import Decimal
from pathlib import Path
import subprocess
import sys
import threading

import pytest
from beancount.core import data

from backend.infrastructure.persistence.beancount import ledger_write as writer
from backend.infrastructure.persistence.db.models import LedgerTransaction
from backend.infrastructure.persistence.ledger_projection import LedgerProjectionService
from backend.infrastructure.persistence import ledger_projection as projection_module

OLD = '2025-01-01 * "old"\n  Assets:Cash  1 CNY\n  Expenses:Food  -1 CNY\n'
NEW = OLD.replace('"old"', '"new"')


@pytest.fixture
def files(tmp_path):
    main = tmp_path / "main.beancount"
    year = tmp_path / "year.beancount"
    main.write_text(
        'option "operating_currency" "CNY"\ninclude "accounts.beancount"\ninclude "year.beancount"\n'
    )
    (tmp_path / "accounts.beancount").write_text(
        "2020-01-01 open Assets:Cash CNY\n2020-01-01 open Expenses:Food CNY\n"
    )
    year.write_text(OLD)
    year.chmod(0o600)
    return main, year


def test_commit_preserves_permissions_and_official_metadata(files):
    main, year = files
    phases = []

    def dirty():
        assert year.read_text() == OLD
        assert writer.has_pending_write(main)
        phases.append("dirty")

    def projection(parsed):
        assert year.read_text() == NEW
        entry = parsed[str(year)][0][0]
        assert entry.meta["filename"] == str(year)
        assert entry.meta["lineno"] == 1
        assert entry.postings[0].meta["filename"] == str(year)
        assert parsed[str(year)][1] == writer.file_fingerprint(year)
        assert parsed.candidate_snapshot is not None
        assert parsed.copy().candidate_snapshot is parsed.candidate_snapshot
        phases.append("ready")

    assert writer.commit_ledger_files(
        main, {year: NEW}, before_commit=dirty, after_commit=projection
    )
    assert phases == ["dirty", "ready"]
    assert year.stat().st_mode & 0o777 == 0o600
    assert not writer.has_pending_write(main)


def test_syntax_and_dirty_failure_never_replace_source(files):
    main, year = files

    def fail():
        raise RuntimeError("dirty failed")

    with pytest.raises(writer.LedgerWriteError):
        writer.commit_ledger_files(
            main, {year: "not a beancount file"}, before_commit=fail, after_commit=lambda _: None
        )
    assert year.read_text() == OLD
    assert not writer.has_pending_write(main)
    with pytest.raises(RuntimeError, match="dirty failed"):
        writer.commit_ledger_files(
            main, {year: NEW}, before_commit=fail, after_commit=lambda _: None
        )
    assert year.read_text() == OLD
    assert not writer.has_pending_write(main)


def test_projection_failure_recovers_committed_source(files):
    main, year = files

    def fail(_):
        raise RuntimeError("financial details must not be logged")

    assert not writer.commit_ledger_files(
        main, {year: NEW}, before_commit=lambda: None, after_commit=fail
    )
    assert year.read_text() == NEW
    with pytest.raises(writer.LedgerWriteConflict):
        writer.commit_ledger_files(
            main, {year: OLD}, before_commit=lambda: None, after_commit=lambda _: None
        )
    calls = []
    assert writer.recover_ledger_write(main, lambda: calls.append(year.read_text()))
    assert calls == [NEW]
    assert not writer.recover_ledger_write(main, lambda: calls.append("duplicate"))


@pytest.mark.parametrize("failure_index", [1, 2])
def test_each_multifile_replacement_failure_rolls_back(files, monkeypatch, failure_index):
    main, year = files
    other = main.parent / "other.beancount"
    main.write_text(main.read_text() + 'include "other.beancount"\n')
    other.write_text(OLD)
    replace = os.replace
    count = 0

    def fail_selected(source, destination):
        nonlocal count
        if Path(destination) in {year, other}:
            count += 1
            if count == failure_index:
                raise OSError("simulated rename failure")
        return replace(source, destination)

    monkeypatch.setattr(writer.os, "replace", fail_selected)
    with pytest.raises(OSError):
        writer.commit_ledger_files(
            main, {year: NEW, other: NEW}, before_commit=lambda: None, after_commit=lambda _: None
        )
    assert year.read_text() == OLD
    assert other.read_text() == OLD
    assert writer.has_pending_write(main)
    assert writer.recover_ledger_write(main, lambda: None)
    assert not writer.has_pending_write(main)


def test_external_fingerprint_change_blocks_commit_and_recovery(files):
    main, year = files
    expected = writer.file_fingerprint(year)
    year.write_text(NEW)
    with pytest.raises(writer.LedgerWriteConflict):
        writer.commit_ledger_files(
            main,
            {year: OLD},
            before_commit=lambda: None,
            after_commit=lambda _: None,
            expected_fingerprints={year: expected},
        )

    def failed_projection(_):
        raise RuntimeError

    writer.commit_ledger_files(
        main, {year: OLD}, before_commit=lambda: None, after_commit=failed_projection
    )
    year.write_text(OLD + "\n; external edit\n")
    with pytest.raises(writer.LedgerWriteConflict):
        writer.recover_ledger_write(
            main, lambda: pytest.fail("must not rebuild conflicting source")
        )
    assert "external edit" in year.read_text()
    assert writer.has_pending_write(main)


def test_new_year_full_loader_validates_and_returns_formal_paths(files):
    main, _ = files
    new_year = main.parent / "new.beancount"
    changes = {main: main.read_text() + 'include "new.beancount"\n', new_year: NEW}
    result = {}
    assert writer.commit_ledger_files(
        main, changes, before_commit=lambda: None, after_commit=result.update
    )
    assert result[str(new_year)][0][0].meta["filename"] == str(new_year)
    assert new_year.stat().st_mode & 0o777 == 0o600


def test_unknown_global_option_uses_complete_validation(files):
    main, year = files
    main.write_text('option "booking_method" "STRICT"\n' + main.read_text())
    assert not writer.supports_local_parse(main)
    invalid = NEW.replace("Assets:Cash", "Assets:Missing")
    with pytest.raises(writer.LedgerWriteError, match="validation failed"):
        writer.commit_ledger_files(
            main, {year: invalid}, before_commit=lambda: None, after_commit=lambda _: None
        )
    assert year.read_text() == OLD
    assert not writer.has_pending_write(main)


def test_local_parse_for_normal_include_graph(files, monkeypatch):
    main, year = files
    assert writer.supports_local_parse(main)
    entries, errors, options = writer.loader.load_file(str(main))
    assert not errors
    monkeypatch.setattr(
        writer.loader,
        "load_file",
        lambda *_: pytest.fail("ordinary save must not load the entire ledger"),
    )
    assert writer.commit_ledger_files(
        main,
        {year: NEW},
        before_commit=lambda: None,
        after_commit=lambda _: None,
        validation_context=(entries, options),
    )


@pytest.mark.parametrize("stage", ["PREPARED", "FILES_COMMITTED"])
def test_process_interruption_recovers_idempotently(files, stage):
    main, year = files
    script = """
import os, sys
from pathlib import Path
from backend.infrastructure.persistence.beancount import ledger_write as w
main, year, stage = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
def before():
    if stage == "PREPARED":
        # Terminate after one rename while durable manifest still says PREPARED.
        ws, manifest = w._read_manifest(main)
        os.replace(main.parent / manifest["files"][0]["candidate"], year)
        os._exit(73)
def after(_):
    os._exit(73)
w.commit_ledger_files(main, {year: year.read_text().replace('"old"', '"new"')}, before_commit=before, after_commit=after)
"""
    result = subprocess.run([sys.executable, "-c", script, str(main), str(year), stage])
    assert result.returncode == 73
    assert writer.has_pending_write(main)
    observed = []
    assert writer.recover_ledger_write(main, lambda: observed.append(year.read_text()))
    assert observed == [OLD if stage == "PREPARED" else NEW]
    assert not writer.recover_ledger_write(main, lambda: pytest.fail("duplicate recovery"))


def test_cleanup_failure_keeps_recoverable_marker(files, monkeypatch):
    main, year = files
    unlink = Path.unlink

    def fail_backup(path, *args, **kwargs):
        if str(path).endswith(".before"):
            raise OSError("cleanup failure")
        return unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_backup)
    assert writer.commit_ledger_files(
        main, {year: NEW}, before_commit=lambda: None, after_commit=lambda _: None
    )
    assert writer.has_pending_write(main)
    monkeypatch.setattr(Path, "unlink", unlink)
    assert writer.recover_ledger_write(main, lambda: None)
    assert year.read_text() == NEW


def test_canonical_reentrant_lock_serializes_threads(files):
    main, _ = files
    order = []
    acquired = threading.Event()

    def second():
        acquired.set()
        with writer.ledger_lock(main):
            order.append("second")

    with writer.ledger_lock(main):
        with writer.ledger_lock(main.parent / "." / main.name):
            thread = threading.Thread(target=second)
            thread.start()
            assert acquired.wait(2)
            order.append("first")
    thread.join(2)
    assert not thread.is_alive()
    assert order == ["first", "second"]


def test_committed_marker_fsync_failure_restores_prepared_before_rollback(files, monkeypatch):
    main, year = files
    save = writer._save_manifest
    failed = False

    def fail_once(workspace, manifest):
        nonlocal failed
        save(workspace, manifest)
        if manifest["stage"] == "FILES_COMMITTED" and not failed:
            failed = True
            raise OSError("failure after committed manifest publication")

    monkeypatch.setattr(writer, "_save_manifest", fail_once)
    with pytest.raises(OSError):
        writer.commit_ledger_files(
            main, {year: NEW}, before_commit=lambda: None, after_commit=lambda _: None
        )
    assert year.read_text() == OLD
    assert writer._read_manifest(main)[1]["stage"] == "PREPARED"
    assert writer.recover_ledger_write(main, lambda: None)
    assert year.read_text() == OLD


def test_prepared_marker_publication_failure_keeps_backups(files, monkeypatch):
    main, year = files
    save = writer._save_manifest

    def fail(workspace, manifest):
        save(workspace, manifest)
        raise OSError("failure after prepared manifest publication")

    monkeypatch.setattr(writer, "_save_manifest", fail)
    with pytest.raises(OSError):
        writer.commit_ledger_files(
            main, {year: NEW}, before_commit=lambda: None, after_commit=lambda _: None
        )
    assert writer.has_pending_write(main)
    monkeypatch.setattr(writer, "_save_manifest", save)
    assert writer.recover_ledger_write(main, lambda: None)
    assert year.read_text() == OLD


def test_recovery_rebuild_failure_keeps_committed_marker(files):
    main, year = files

    def fail(_=None):
        raise RuntimeError("projection unavailable")

    assert not writer.commit_ledger_files(
        main, {year: NEW}, before_commit=lambda: None, after_commit=fail
    )
    with pytest.raises(RuntimeError):
        writer.recover_ledger_write(main, fail)
    assert writer.has_pending_write(main)
    assert year.read_text() == NEW
    assert writer.recover_ledger_write(main, lambda: None)


def test_new_source_is_deleted_when_multifile_commit_fails(files, monkeypatch):
    main, _ = files
    new_year = main.parent / "new.beancount"
    original_main = main.read_text()
    replace = os.replace

    def fail_main_once(source, destination):
        if Path(destination) == main:
            raise OSError("cannot install main include")
        return replace(source, destination)

    monkeypatch.setattr(writer.os, "replace", fail_main_once)
    with pytest.raises(OSError):
        writer.commit_ledger_files(
            main,
            {new_year: NEW, main: original_main + 'include "new.beancount"\n'},
            before_commit=lambda: None,
            after_commit=lambda _: None,
            expected_fingerprints={new_year: None},
        )
    assert not new_year.exists()
    assert main.read_text() == original_main
    assert writer.recover_ledger_write(main, lambda: None)


def test_source_symlink_is_rejected_without_writing_target(files):
    main, year = files
    target = main.parent / "private.beancount"
    year.rename(target)
    year.symlink_to(target)
    with pytest.raises(writer.LedgerWriteConflict, match="Symlink"):
        writer.commit_ledger_files(
            main, {year: NEW}, before_commit=lambda: None, after_commit=lambda _: None
        )
    assert target.read_text() == OLD


def test_inferred_posting_uses_loader_and_keeps_formal_metadata(files):
    main, year = files
    inferred = NEW.replace("Expenses:Food  -1 CNY", "Expenses:Food")
    result = {}
    assert writer.commit_ledger_files(
        main, {year: inferred}, before_commit=lambda: None, after_commit=result.update
    )
    assert result[str(year)][0][0].postings[1].units.number == -1
    assert result[str(year)][0][0].postings[1].meta["filename"] == str(year)


@pytest.mark.parametrize("directive", [
    "2025-02-01 balance Assets:Cash 1 CNY\n",
    '2025-02-01 custom "benchmark" "marker"\n',
])
def test_global_validation_parses_candidate_only_with_complete_loader(files, monkeypatch, directive):
    main, year = files
    main.write_text(main.read_text() + directive)
    original = writer.parser.parse_file
    parsed_paths = []

    def track(path, *args, **kwargs):
        parsed_paths.append(Path(path))
        return original(path, *args, **kwargs)

    monkeypatch.setattr(writer.parser, "parse_file", track)
    assert writer.commit_ledger_files(
        main, {year: NEW}, before_commit=lambda: None, after_commit=lambda _: None
    )
    assert not any(path.name.startswith(".beanmind-") for path in parsed_paths)
    assert year.read_text() == NEW


@pytest.mark.parametrize("main_changes", [False, True])
def test_known_full_loader_branch_skips_included_candidate_preparse(files, monkeypatch, main_changes):
    main, year = files
    changes = {year: NEW}
    if main_changes:
        changes[main] = main.read_text() + "; harmless comment\n"
    parsed_paths = []
    original = writer.parser.parse_file

    def track(path, *args, **kwargs):
        parsed_paths.append(Path(path))
        return original(path, *args, **kwargs)

    monkeypatch.setattr(writer.parser, "parse_file", track)
    assert writer.commit_ledger_files(
        main, changes, before_commit=lambda: None, after_commit=lambda _: None,
    )
    assert not any(path.name.startswith(".beanmind-") for path in parsed_paths)


def test_global_validation_rejects_invalid_syntax_before_dirty(files):
    main, year = files
    main.write_text(main.read_text() + "2025-02-01 balance Assets:Cash 1 CNY\n")
    calls = []
    with pytest.raises(writer.LedgerValidationError):
        writer.commit_ledger_files(
            main, {year: "invalid directive\n"},
            before_commit=lambda: calls.append("dirty"), after_commit=lambda _: None,
        )
    assert calls == []
    assert year.read_text() == OLD
    assert not writer.has_pending_write(main)


def test_global_validation_checks_unincluded_changed_file(files):
    main, year = files
    main.write_text(main.read_text() + "2025-02-01 balance Assets:Cash 1 CNY\n")
    unindexed = main.parent / "unindexed.beancount"
    with pytest.raises(writer.LedgerValidationError):
        writer.commit_ledger_files(
            main, {unindexed: "invalid directive\n"},
            before_commit=lambda: pytest.fail("invalid source must not become DIRTY"),
            after_commit=lambda _: None,
        )
    assert not unindexed.exists()
    assert year.read_text() == OLD


def test_removing_global_directive_uses_candidate_loader_not_stale_context(files):
    main, year = files
    balance = "2025-01-02 balance Assets:Cash 1 CNY\n"
    year.write_text(OLD + balance)
    changed = OLD.replace(" 1 CNY", " 2 CNY").replace(" -1 CNY", " -2 CNY")
    from beancount import loader

    context_entries, errors, options = loader.load_file(str(main))
    assert not errors
    observed = []
    original = writer.loader.load_file

    def track(path, *args, **kwargs):
        observed.append(Path(path))
        return original(path, *args, **kwargs)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(writer.loader, "load_file", track)
        assert writer.commit_ledger_files(
            main, {year: changed}, before_commit=lambda: None, after_commit=lambda _: None,
            validation_context=(context_entries, options),
        )
    assert len(observed) == 1
    assert year.read_text() == changed


def test_later_balance_assertion_forces_full_validation_before_source_commit(files):
    main, year = files
    assertion = main.parent / "assertions.beancount"
    assertion.write_text("2025-02-01 balance Assets:Cash 1 CNY\n")
    main.write_text(main.read_text() + 'include "assertions.beancount"\n')
    assert not writer.supports_local_parse(main)
    changed = NEW.replace("1 CNY", "2 CNY")
    with pytest.raises(writer.LedgerWriteError, match="validation failed"):
        writer.commit_ledger_files(
            main,
            {year: changed},
            before_commit=lambda: pytest.fail("invalid source must not become DIRTY"),
            after_commit=lambda _: None,
        )
    assert year.read_text() == OLD
    assert not writer.has_pending_write(main)


def test_later_balance_candidate_matches_formal_rebuild_after_each_write(files, db_session):
    main, year = files
    main.write_text(main.read_text() + "2025-02-01 balance Assets:Cash 1 CNY\n")
    projection = LedgerProjectionService(db_session, main)
    projection.full_rebuild()
    later = '2025-03-01 * "later"\n  Assets:Cash  2 CNY\n  Expenses:Food  -2 CNY\n'

    def verify():
        db_session.expire_all()
        before = sorted((row.id, row.content_hash, row.source_file, row.source_lineno,
                         tuple((p.account, p.amount_text, p.currency) for p in row.postings))
                        for row in db_session.query(LedgerTransaction).all())
        projection.full_rebuild()
        db_session.expire_all()
        after = sorted((row.id, row.content_hash, row.source_file, row.source_lineno,
                        tuple((p.account, p.amount_text, p.currency) for p in row.postings))
                       for row in db_session.query(LedgerTransaction).all())
        assert before == after

    def save(content):
        def after(parsed):
            assert parsed.candidate_snapshot is not None
            projection.refresh_files([year], parsed_files=parsed,
                                     candidate_snapshot=parsed.candidate_snapshot)

        assert writer.commit_ledger_files(
            main, {year: content},
            before_commit=lambda: projection.mark_dirty_files([year]),
            after_commit=after,
        )
        verify()

    save(OLD + later)
    save(NEW + later)
    save(NEW)
    assert projection.status()["status"] == "READY"


def test_later_pad_change_uses_formal_loader_and_matches_rebuild(files, db_session):
    main, year = files
    accounts = main.parent / "accounts.beancount"
    accounts.write_text(accounts.read_text() + "2020-01-01 open Equity:Opening CNY\n")
    main.write_text(main.read_text()
                    + "2025-02-01 pad Assets:Cash Equity:Opening\n"
                    + "2025-02-02 balance Assets:Cash 2 CNY\n")
    projection = LedgerProjectionService(db_session, main)
    projection.full_rebuild()
    changed = OLD.replace(" 1 CNY", " 3 CNY").replace(" -1 CNY", " -3 CNY")

    def after(parsed):
        assert parsed.candidate_snapshot is None
        projection.refresh_files([year], parsed_files=parsed)

    assert writer.commit_ledger_files(
        main, {year: changed},
        before_commit=lambda: projection.mark_dirty_files([year]),
        after_commit=after,
    )
    db_session.expire_all()
    before = sorted((row.id, row.content_hash, row.source_file, row.source_lineno)
                    for row in db_session.query(LedgerTransaction).all())
    projection.full_rebuild()
    db_session.expire_all()
    after = sorted((row.id, row.content_hash, row.source_file, row.source_lineno)
                   for row in db_session.query(LedgerTransaction).all())
    assert before == after
    assert not writer.has_pending_write(main)


def test_loader_plugin_virtual_sources_do_not_reject_valid_save(files):
    main, year = files
    main.write_text(
        'plugin "beancount.plugins.currency_accounts" "Equity:Currency"\n' + main.read_text()
    )
    (main.parent / "accounts.beancount").write_text(
        "2020-01-01 open Assets:Cash CNY,USD\n2020-01-01 open Expenses:Food CNY,USD\n"
    )
    changed = '2025-01-01 * "exchange"\n  Assets:Cash  1 USD @ 7 CNY\n  Expenses:Food  -7 CNY\n'
    result = {}
    def collect(parsed):
        assert parsed.candidate_snapshot is None
        result.update(parsed)
    assert writer.commit_ledger_files(
        main, {year: changed}, before_commit=lambda: None, after_commit=collect
    )
    assert set(result) == {str(year)}
    transaction = result[str(year)][0][0]
    assert transaction.meta["filename"] == str(year)
    assert len(transaction.postings) == 4
    assert all(p.meta["filename"] == str(year) for p in transaction.postings)
    assert year.read_text() == changed


@pytest.mark.parametrize("scenario", ["price", "inferred", "commodity", "fifo"])
def test_candidate_booking_matches_formal_loader_and_rebuild(files, db_session, caplog, scenario):
    main, year = files
    accounts = main.parent / "accounts.beancount"
    if scenario == "price":
        accounts.write_text(accounts.read_text().replace("Cash CNY", "Cash CNY,USD"))
        main.write_text(main.read_text() +
                        '2024-12-31 price USD 7 CNY\n2025-01-01 custom "benchmark" "marker"\n')
        changed = ('2025-01-01 * "priced"\n  Assets:Cash  1 USD @ 7 CNY\n'
                   '  Expenses:Food  -7 CNY\n')
    elif scenario == "inferred":
        main.write_text(main.read_text() + '2025-01-01 custom "benchmark" "marker"\n')
        changed = NEW.replace("Expenses:Food  -1 CNY", "Expenses:Food")
    elif scenario == "commodity":
        main.write_text(main.read_text() +
                        '2020-01-01 commodity CNY\n  precision: 2\n'
                        '2025-01-01 custom "benchmark" "marker"\n')
        changed = NEW.replace(" 1 CNY", " 1.23 CNY").replace(" -1 CNY", " -1.23 CNY")
    else:
        accounts.write_text(
            "2020-01-01 open Assets:Inventory USD \"FIFO\"\n"
            "2020-01-01 open Equity:Opening CNY\n"
        )
        main.write_text(main.read_text() +
                        'include "sell.beancount"\n2025-01-01 custom "benchmark" "marker"\n')
        sell = main.parent / "sell.beancount"
        sell.write_text('2025-01-02 * "sell"\n  Assets:Inventory  -1 USD {}\n  Equity:Opening\n')
        year.write_text('2025-01-01 * "buy"\n  Assets:Inventory  2 USD {5 CNY}\n  Equity:Opening  -10 CNY\n')
        changed = year.read_text().replace("{5 CNY}", "{6 CNY}").replace("-10 CNY", "-12 CNY")

    projection = LedgerProjectionService(db_session, main)
    projection.full_rebuild()
    candidate = []

    def after(parsed):
        snapshot = parsed.candidate_snapshot
        assert snapshot is not None
        official, errors, _ = writer.loader.load_file(str(main))
        assert not errors
        expected = [entry for entry in official if isinstance(entry, data.Transaction)]
        actual = [entry for entry in snapshot.entries if isinstance(entry, data.Transaction)]
        assert actual == expected
        if scenario == "price":
            assert actual[0].postings[0].price.number == Decimal("7")
        elif scenario == "inferred":
            assert actual[0].postings[1].units.number == Decimal("-1")
        elif scenario == "commodity":
            assert actual[0].postings[0].units.number == Decimal("1.23")
        else:
            sell_transaction = next(entry for entry in actual if entry.narration == "sell")
            assert sell_transaction.postings[0].cost.number == Decimal("6")
            assert sell_transaction.postings[1].units.number == Decimal("6")
        candidate.extend(actual)
        projection.refresh_files([year], parsed_files=parsed, candidate_snapshot=snapshot)

    with caplog.at_level(logging.INFO, logger="backend.infrastructure.persistence.ledger_projection"):
        assert writer.commit_ledger_files(
            main, {year: changed}, before_commit=lambda: projection.mark_dirty_files([year]),
            after_commit=after,
        )
    assert "mode=candidate_diff" in caplog.text
    db_session.expire_all()
    before = sorted((row.id, row.content_hash, row.source_file, row.source_lineno,
                     tuple((p.account, p.amount_text, p.currency, p.cost_text, p.price_text)
                           for p in row.postings))
                    for row in db_session.query(LedgerTransaction).all())
    projection.full_rebuild()
    db_session.expire_all()
    after = sorted((row.id, row.content_hash, row.source_file, row.source_lineno,
                    tuple((p.account, p.amount_text, p.currency, p.cost_text, p.price_text)
                          for p in row.postings))
                   for row in db_session.query(LedgerTransaction).all())
    assert before == after
    assert candidate


@pytest.mark.parametrize("change_at", [1, 3])
@pytest.mark.parametrize("manifest_source_changed", [False, True])
def test_late_candidate_source_change_retries_only_with_intact_manifest(
    files, db_session, monkeypatch, caplog, manifest_source_changed, change_at
):
    main, year = files
    accounts = main.parent / "accounts.beancount"
    main.write_text(main.read_text() + '2025-01-01 custom "benchmark" "marker"\n')
    projection = LedgerProjectionService(db_session, main)
    projection.full_rebuild()
    original = projection_module._source_fingerprints
    calls = 0

    def changing_graph(path):
        nonlocal calls
        calls += 1
        if calls == change_at:
            target = year if manifest_source_changed else accounts
            target.write_text(target.read_text() + "; concurrent edit\n")
        return original(path)

    def after(parsed):
        assert parsed.candidate_snapshot is not None
        with monkeypatch.context() as patch:
            patch.setattr(projection_module, "_source_fingerprints", changing_graph)
            projection.refresh_files([year], parsed_files=parsed,
                                     candidate_snapshot=parsed.candidate_snapshot)

    with caplog.at_level(logging.INFO, logger="backend.infrastructure.persistence.ledger_projection"):
        committed = writer.commit_ledger_files(
            main, {year: NEW}, before_commit=lambda: projection.mark_dirty_files([year]),
            after_commit=after,
        )
    assert calls >= change_at
    if manifest_source_changed:
        assert committed is False
        assert projection.status()["status"] == "DIRTY"
        assert writer.has_pending_write(main)
        assert "mode=loader_diff" not in caplog.text
    else:
        assert committed is True
        assert projection.status()["status"] == "READY"
        reason = "source_graph_or_fingerprint" if change_at == 1 else "late_invalidated"
        assert f"reason={reason}" in caplog.text
        assert "mode=loader_diff" in caplog.text
        assert not writer.has_pending_write(main)


def test_candidate_entry_conversion_failure_retries_formal_loader(files, db_session, monkeypatch, caplog):
    main, year = files
    main.write_text(main.read_text() + '2025-01-01 custom "benchmark" "marker"\n')
    second = '2025-01-02 * "second"\n  Assets:Cash  2 CNY\n  Expenses:Food  -2 CNY\n'
    year.write_text(OLD + second)
    projection = LedgerProjectionService(db_session, main)
    projection.full_rebuild()
    original = projection._model_from_entry
    calls = 0

    def fail_once(entry):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("candidate-only conversion fault")
        return original(entry)

    monkeypatch.setattr(projection, "_model_from_entry", fail_once)

    def after(parsed):
        assert parsed.candidate_snapshot is not None
        parsed.projection_receipt = object()  # Refresh must clear any stale receipt.
        projection.refresh_files([year], parsed_files=parsed,
                                 candidate_snapshot=parsed.candidate_snapshot)
        assert parsed.projection_receipt is None

    with caplog.at_level(logging.INFO, logger="backend.infrastructure.persistence.ledger_projection"):
        assert writer.commit_ledger_files(
            main, {year: NEW + second.replace('"second"', '"second edited"')},
            before_commit=lambda: projection.mark_dirty_files([year]),
            after_commit=after,
        )
    assert calls >= 4
    assert "reason=late_invalidated" in caplog.text
    assert "mode=loader_diff" in caplog.text
    assert projection.status()["status"] == "READY"
    monkeypatch.setattr(projection, "_model_from_entry", original)
    db_session.expire_all()
    before = sorted((row.id, row.content_hash, row.source_file, row.source_lineno)
                    for row in db_session.query(LedgerTransaction).all())
    projection.full_rebuild()
    db_session.expire_all()
    assert before == sorted((row.id, row.content_hash, row.source_file, row.source_lineno)
                            for row in db_session.query(LedgerTransaction).all())


def test_candidate_fallback_loader_failure_stays_dirty(files, db_session, monkeypatch, caplog):
    main, year = files
    main.write_text(main.read_text() + '2025-01-01 custom "benchmark" "marker"\n')
    projection = LedgerProjectionService(db_session, main)
    projection.full_rebuild()
    original_rows = [(row.id, row.content_hash) for row in db_session.query(LedgerTransaction).all()]

    def after(parsed):
        assert parsed.candidate_snapshot is not None
        with monkeypatch.context() as patch:
            patch.setattr(projection, "_model_from_entry",
                          lambda _: (_ for _ in ()).throw(ValueError("candidate conversion failed")))
            patch.setattr(projection_module, "load_ledger_file",
                          lambda *_: (_ for _ in ()).throw(ValueError("formal loader failed")))
            projection.refresh_files([year], parsed_files=parsed,
                                     candidate_snapshot=parsed.candidate_snapshot)

    with caplog.at_level(logging.INFO, logger="backend.infrastructure.persistence.ledger_projection"):
        assert not writer.commit_ledger_files(
            main, {year: NEW}, before_commit=lambda: projection.mark_dirty_files([year]),
            after_commit=after,
        )
    assert year.read_text() == NEW
    assert projection.status()["status"] == "DIRTY"
    assert writer.has_pending_write(main)
    assert "reason=late_invalidated" in caplog.text
    assert "mode=loader_diff" not in caplog.text
    db_session.expire_all()
    assert [(row.id, row.content_hash) for row in db_session.query(LedgerTransaction).all()] == original_rows


@pytest.mark.parametrize("dirty_retry_fails", [False, True])
def test_post_projection_source_conflict_keeps_manifest(files, db_session, dirty_retry_fails):
    main, year = files
    projection = LedgerProjectionService(db_session, main)
    projection.full_rebuild()
    dirty_calls = 0

    def mark_dirty():
        nonlocal dirty_calls
        dirty_calls += 1
        if dirty_retry_fails and dirty_calls == 2:
            raise OSError("dirty status unavailable")
        projection.mark_dirty_files([year])

    def after(parsed):
        projection.refresh_files([year], parsed_files=parsed,
                                 candidate_snapshot=parsed.candidate_snapshot)
        year.write_text(year.read_text() + "; external edit\n")

    assert not writer.commit_ledger_files(
        main, {year: NEW}, before_commit=mark_dirty, after_commit=after,
    )
    assert dirty_calls == 2
    assert writer.has_pending_write(main)
    assert projection.status()["status"] == "DIRTY"
    with pytest.raises(projection_module.LedgerProjectionDirtyError):
        projection.assert_ready()
    with pytest.raises(writer.LedgerWriteConflict):
        writer.recover_ledger_write(main, lambda: pytest.fail("must not overwrite external edit"))
    assert "; external edit" in year.read_text()


def test_candidate_database_failure_stays_dirty_without_loader_retry(files, db_session, monkeypatch, caplog):
    main, year = files
    main.write_text(main.read_text() + '2025-01-01 custom "benchmark" "marker"\n')
    projection = LedgerProjectionService(db_session, main)
    projection.full_rebuild()
    monkeypatch.setattr(
        projection, "_apply_difference",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("database unavailable")),
    )

    def after(parsed):
        assert parsed.candidate_snapshot is not None
        projection.refresh_files([year], parsed_files=parsed,
                                 candidate_snapshot=parsed.candidate_snapshot)

    with caplog.at_level(logging.INFO, logger="backend.infrastructure.persistence.ledger_projection"):
        assert not writer.commit_ledger_files(
            main, {year: NEW}, before_commit=lambda: projection.mark_dirty_files([year]),
            after_commit=after,
        )
    assert projection.status()["status"] == "DIRTY"
    assert writer.has_pending_write(main)
    assert "reason=late_invalidated" not in caplog.text
    assert "mode=loader_diff" not in caplog.text


@pytest.mark.parametrize("invalid_kind", ["inactive", "currency"])
def test_pure_candidate_validates_account_semantics_in_locked_context(
    files, monkeypatch, invalid_kind
):
    main, year = files
    if invalid_kind == "inactive":
        accounts = main.parent / "accounts.beancount"
        accounts.write_text(accounts.read_text().replace("2020-01-01", "2025-01-15"))
        year.write_text(OLD.replace("2025-01-01", "2025-01-20"))
        candidate = OLD
    else:
        candidate = OLD.replace("CNY", "USD")
    before = year.read_text()
    entries, errors, options = writer.loader.load_file(str(main))
    assert not errors
    monkeypatch.setattr(
        writer.loader, "load_file", lambda *_: pytest.fail("context validation must remain local")
    )
    with pytest.raises(writer.LedgerWriteError, match="validation failed"):
        writer.commit_ledger_files(
            main,
            {year: candidate},
            before_commit=lambda: pytest.fail("invalid candidate must not mark DIRTY"),
            after_commit=lambda _: None,
            validation_context=(entries, options),
        )
    assert year.read_text() == before
    assert not writer.has_pending_write(main)


@pytest.mark.parametrize("declaration", [
    'plugin "beancount.plugins.auto_accounts"\n',
    'plugin "beancount.plugins.auto_accounts" "config"\n',
    'plugin "beancount.plugins.auto_accounts"\nplugin "beancount.plugins.auto_accounts"\n',
    '  plugin "beancount.plugins.auto_accounts"\n',
    'plugin "auto_accounts"\n',
    'plugin "beancount.plugins.auto_accounts"\nplugin "other.plugin"\n',
    'plugin "beancount.plugins.auto_accounts"\n  "config"\n',
])
def test_trusted_plugin_configuration_requires_exact_single_declaration(files, declaration):
    main, year = files
    main.write_text(declaration + main.read_text())
    state = writer.sample_source_state(main)
    options = {"filename": str(main), "include": [str(p) for p in state.sources],
               "plugin": [("beancount.plugins.auto_accounts", None)], "pythonpath": []}
    assert writer.trusted_full_view(state, options) is (declaration == writer._AUTO_ACCOUNTS + "\n")
    for plugins in ([('beancount.plugins.auto_accounts', 'config')],
                    [('beancount.plugins.auto_accounts', None), ('other.plugin', None)], []):
        assert not writer.trusted_full_view(state, {**options, "plugin": plugins})


def test_source_state_detects_preserved_mtime_and_include_membership(files):
    main, year = files
    before = writer.sample_source_state(main)
    old_stat = year.stat()
    year.write_text(NEW)
    os.utime(year, ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns))
    after = writer.sample_source_state(main)
    assert before.fingerprints[year][:2] == after.fingerprints[year][:2]
    assert before.fingerprints[year][2] != after.fingerprints[year][2]
    other = main.parent / 'other.beancount'
    other.write_text('; member\n')
    main.write_text(main.read_text() + 'include "other.beancount"\n')
    assert set(writer.sample_source_state(main).sources) == set(before.sources) | {other}


@pytest.mark.parametrize("pattern", ['*.beancount', '../external.beancount'])
def test_source_state_rejects_untracked_include_inputs(files, pattern):
    main, _ = files
    main.write_text(f'include "{pattern}"\n')
    with pytest.raises(writer.LedgerSourceUnsupported):
        writer.sample_source_state(main)


def test_auto_accounts_candidate_paths_and_ready_receipt(files, db_session, monkeypatch):
    main, year = files
    main.write_text('plugin "beancount.plugins.auto_accounts"\n' + main.read_text())
    # Require the plugin to actually synthesize an Open, preserving virtual provenance.
    changed = NEW.replace('Expenses:Food', 'Expenses:New')
    projection = LedgerProjectionService(db_session, main)
    projection.full_rebuild()
    captured = []
    original_loader = writer.loader._load
    loader_calls = []
    def counted_loader(*args, **kwargs):
        loader_calls.append(1)
        return original_loader(*args, **kwargs)
    monkeypatch.setattr(writer.loader, "_load", counted_loader)

    def after(parsed):
        snapshot = parsed.candidate_snapshot
        assert snapshot is not None
        assert snapshot.ledger_path == main
        assert snapshot.options['filename'] == str(main)
        assert set(map(Path, snapshot.options['include'])) == set(snapshot.source_hashes)
        assert snapshot.options['pythonpath'] == []
        assert 'input_hash' not in snapshot.options
        generated = [entry for entry in snapshot.entries if entry.meta['filename'] == '<auto_accounts>']
        assert any(isinstance(entry, data.Open) and entry.account == 'Expenses:New' for entry in generated)
        for entry in snapshot.entries:
            assert '.beanmind-validate-' not in entry.meta['filename']
            for posting in getattr(entry, 'postings', []):
                assert '.beanmind-validate-' not in posting.meta['filename']
        assert parsed.projection_receipt is None
        projection.refresh_files([year], parsed_files=parsed, candidate_snapshot=snapshot)
        receipt = parsed.projection_receipt
        assert receipt.snapshot is snapshot
        assert receipt.candidate_used and receipt.ready_committed
        assert receipt.source_version == writer.sample_source_state(main).fingerprints
        assert parsed.copy().projection_receipt is receipt
        captured.append(receipt)

    assert writer.commit_ledger_files(main, {year: changed},
                                     before_commit=lambda: projection.mark_dirty_files([year]),
                                     after_commit=after)
    assert captured
    assert len(loader_calls) == 1  # Candidate loader is reused by the projection.
    before = sorted((row.id, row.content_hash) for row in db_session.query(LedgerTransaction).all())
    projection.full_rebuild()
    assert before == sorted((row.id, row.content_hash) for row in db_session.query(LedgerTransaction).all())


def test_trusted_view_rejects_unknown_options_and_external_paths(files):
    main, _ = files
    state = writer.sample_source_state(main)
    options = {'filename': str(main), 'include': list(map(str, state.sources)), 'plugin': [], 'pythonpath': []}
    assert writer.trusted_full_view(state, options)
    for changed in ({'external_path': '/tmp/input'}, {'pythonpath': [str(main.parent)]},
                    {'include': [str(main)]}, {'filename': '/tmp/input'}):
        assert not writer.trusted_full_view(state, {**options, **changed})


def test_source_sampling_rejects_earlier_source_change_with_preserved_mtime(files, monkeypatch):
    main, year = files
    original_read = Path.read_bytes
    changed = False
    main_stat = main.stat()
    def read_bytes(path):
        nonlocal changed
        raw = original_read(path)
        if path == year and not changed:
            changed = True
            # The main source was already traversed. Alter its include graph while
            # preserving its mtime and size; ctime/inode still invalidate the sample.
            content = main.read_text()
            main.write_text(content.replace('year.beancount', 'none.beancount'))
            os.utime(main, ns=(main_stat.st_atime_ns, main_stat.st_mtime_ns))
        return raw
    monkeypatch.setattr(Path, 'read_bytes', read_bytes)
    with pytest.raises(writer.LedgerWriteConflict, match='changed while sampling'):
        writer.sample_source_state(main)


def test_formal_loader_forwards_parameters_and_error_logging(files, monkeypatch):
    main, _ = files
    calls = []
    errors = [object()]
    expected = ([], errors, {})
    timings, error_log, validations = object(), object(), [object()]
    def uncached(filename, log_timings, extra_validations, encoding):
        calls.append((filename, log_timings, extra_validations, encoding))
        return expected
    monkeypatch.setattr(writer.loader, '_uncached_load_file', uncached)
    monkeypatch.setattr(writer.loader, '_log_errors', lambda value, target: calls.append((value, target)))
    monkeypatch.setenv('BEANMIND_TEST_LEDGER', str(main))
    assert writer.load_ledger_file('$BEANMIND_TEST_LEDGER', timings, error_log, validations, 'utf-8') is not None
    assert calls == [(str(main), timings, validations, 'utf-8'), (errors, error_log)]


@pytest.mark.parametrize('broken', ['missing', 'signature', 'version'])
def test_formal_loader_contract_failure_never_falls_back(files, monkeypatch, broken):
    main, _ = files
    if broken == 'missing':
        monkeypatch.delattr(writer.loader, '_uncached_load_file')
    elif broken == 'signature':
        monkeypatch.setattr(writer.loader, '_uncached_load_file', lambda filename: None)
    else:
        monkeypatch.setattr(writer.beancount, '__version__', 'unsupported')
    monkeypatch.setattr(writer.loader, 'load_file', lambda *args: pytest.fail('unsafe cached fallback'))
    with pytest.raises(writer.LedgerWriteError, match='loader contract'):
        writer.load_ledger_file(main)


def test_formal_loader_encrypted_entry_preserves_public_contract(files, monkeypatch):
    main, _ = files
    calls = []
    expected = ([], [], {})
    monkeypatch.setattr(writer.loader.encryption, 'is_encrypted_file', lambda filename: True)
    monkeypatch.setattr(writer.loader, 'load_file', lambda *args: calls.append(args) or expected)
    monkeypatch.setattr(writer.loader, '_uncached_load_file', lambda *args: pytest.fail('encrypted private loader'))
    assert writer.load_ledger_file(main, 'timings', 'errors', ['validation'], 'encoding') is expected
    assert calls == [(str(main), 'timings', 'errors', ['validation'], 'encoding')]


def test_formal_loader_runs_extra_validations_and_logs_errors(files):
    import io
    main, year = files
    validations = []
    def extra(entries, options):
        validations.append((entries, options))
        return []
    entries, errors, options = writer.load_ledger_file(main, extra_validations=[extra])
    assert not errors and validations == [(entries, options)]
    year.write_text('invalid directive\n')
    error_output = io.StringIO()
    _, errors, _ = writer.load_ledger_file(main, log_errors=error_output)
    assert errors and error_output.getvalue()


@pytest.mark.parametrize('mode', ['rebuild', 'fallback', 'consistency'])
def test_formal_projection_ignores_stale_pickle_without_touching_cache(files, db_session, monkeypatch, mode):
    import builtins
    main, year = files
    main.write_text('plugin "beancount.plugins.auto_accounts"\n' + main.read_text())
    projection = LedgerProjectionService(db_session, main)
    projection.full_rebuild()
    cache = main.parent / '.forced.picklecache'
    cached_load = writer.loader.pickle_cache_function(lambda _: str(cache), 0, writer.loader._uncached_load_file)
    cached_entries, errors, _ = cached_load(str(main), None, None, None)
    assert not errors and cache.exists()
    before_cache = cache.read_bytes()
    before_stat = cache.stat()
    previous = year.stat()
    year.write_text(OLD.replace(' 1 CNY', ' 2 CNY').replace(' -1 CNY', ' -2 CNY')
                   .replace('2025-01-01', '2025-02-01'))
    os.utime(year, ns=(previous.st_atime_ns, previous.st_mtime_ns))
    # The real Beancount wrapper proves the preserved-mtime cache is stale.
    stale_entries, _, _ = cached_load(str(main), None, None, None)
    assert stale_entries == cached_entries
    original_open = builtins.open
    original_remove = os.remove
    def open_file(path, *args, **kwargs):
        if not isinstance(path, int) and Path(path) == cache:
            pytest.fail('formal projection must not read or write picklecache')
        return original_open(path, *args, **kwargs)
    def remove_file(path, *args, **kwargs):
        if Path(path) == cache:
            pytest.fail('formal projection must not delete picklecache')
        return original_remove(path, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(builtins, 'open', open_file)
        patch.setattr(os, 'remove', remove_file)
        patch.setattr(writer.loader, 'load_file',
                      lambda *args, **kwargs: pytest.fail('formal projection used the cached public loader'))
        if mode == 'consistency':
            with pytest.raises(ValueError, match='核对失败'):
                projection.check_consistency()
            projection.full_rebuild()
        elif mode == 'fallback':
            projection.refresh_files([year])
        else:
            projection.full_rebuild()
        assert projection.check_consistency()['consistent']
        row = db_session.query(LedgerTransaction).one()
        assert {posting.amount_text for posting in row.postings} == {'2', '-2'}
        assert row.date.isoformat() == '2025-02-01'
    assert cache.read_bytes() == before_cache
    after_stat = cache.stat()
    assert (after_stat.st_mtime_ns, after_stat.st_ino, after_stat.st_size) == (
        before_stat.st_mtime_ns, before_stat.st_ino, before_stat.st_size)


def test_final_graph_early_source_change_cannot_issue_stale_ready_receipt(files, db_session, monkeypatch, caplog):
    main, year = files
    accounts = main.parent / 'accounts.beancount'
    # LIFO traversal reads accounts before year, making year the last graph source.
    main.write_text('plugin "beancount.plugins.auto_accounts"\n'
                    'include "year.beancount"\ninclude "accounts.beancount"\n')
    projection = LedgerProjectionService(db_session, main)
    projection.full_rebuild()
    original_graph = projection_module._source_fingerprints
    original_fingerprint = projection_module._fingerprint
    phase = 0
    changed = False
    receipts = []
    def graph(path):
        nonlocal phase
        phase += 1
        return original_graph(path)
    def fingerprint(path):
        nonlocal changed
        value = original_fingerprint(path)
        if phase == 3 and path == year and not changed:
            changed = True
            previous = accounts.stat()
            accounts.write_text(accounts.read_text().replace('2020-01-01', '2021-01-01'))
            os.utime(accounts, ns=(previous.st_atime_ns, previous.st_mtime_ns))
        return value
    def after(parsed):
        with monkeypatch.context() as patch:
            patch.setattr(projection_module, '_source_fingerprints', graph)
            patch.setattr(projection_module, '_fingerprint', fingerprint)
            projection.refresh_files([year], parsed_files=parsed, candidate_snapshot=parsed.candidate_snapshot)
        receipts.append(parsed.projection_receipt)
    with caplog.at_level(logging.INFO, logger='backend.infrastructure.persistence.ledger_projection'):
        assert writer.commit_ledger_files(main, {year: NEW},
                                         before_commit=lambda: projection.mark_dirty_files([year]),
                                         after_commit=after)
    assert changed and receipts == [None]
    assert 'reason=late_invalidated' in caplog.text
    assert 'mode=loader_diff' in caplog.text
    assert projection.status()['status'] == 'READY'
    assert projection.check_consistency()['consistent']


def test_candidate_rechecks_later_posting_provenance_after_filename_mapping_hit(files, tmp_path):
    main, year = files
    year.write_text(OLD + NEW.replace('2025-01-01', '2025-01-02'))
    sources = writer._source_tree(main, {})
    mirror = tmp_path / 'candidate-mirror'
    mirror.mkdir()
    for path, content in sources.items():
        target = mirror / path.relative_to(main.parent)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    entries, errors, options = writer.loader.load_file(str(mirror / main.name))
    assert not errors
    assert writer._candidate_snapshot(entries, options, mirror, sources, main) is not None
    transactions = [entry for entry in entries if isinstance(entry, data.Transaction)]
    assert len(transactions) == 2
    first, later = transactions
    assert first.meta['filename'] == later.meta['filename']
    bad_meta = {**later.postings[0].meta, 'filename': str(mirror / 'accounts.beancount')}
    bad_posting = later.postings[0]._replace(meta=bad_meta)
    damaged = later._replace(postings=[bad_posting, *later.postings[1:]])
    damaged_entries = [damaged if entry is later else entry for entry in entries]
    assert writer._candidate_snapshot(damaged_entries, options, mirror, sources, main) is None
