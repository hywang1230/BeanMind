"""Isolated filesystem fault tests for the ledger write protocol."""

import os
from pathlib import Path
import subprocess
import sys
import threading

import pytest

from backend.infrastructure.persistence.beancount import ledger_write as writer

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
    assert writer.commit_ledger_files(
        main, {year: changed}, before_commit=lambda: None, after_commit=result.update
    )
    assert set(result) == {str(year)}
    transaction = result[str(year)][0][0]
    assert transaction.meta["filename"] == str(year)
    assert len(transaction.postings) == 4
    assert all(p.meta["filename"] == str(year) for p in transaction.postings)
    assert year.read_text() == changed


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
