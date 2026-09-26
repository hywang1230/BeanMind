"""Single-process ledger file commit and crash recovery.

The manifest coordinates files only; callers own projection transactions and recovery.
No ledger content or exception text is emitted to logs by this module.
"""

from __future__ import annotations

import glob
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import stat
import tempfile
import threading
from contextlib import contextmanager
from decimal import Decimal
from typing import Callable
import uuid
import time

from beancount import loader
from beancount.core import data
from beancount.parser import parser
from beancount.ops import validation

logger = logging.getLogger(__name__)
_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()
Fingerprint = tuple[int, int, str]
ParsedFiles = dict[str, tuple[list, Fingerprint]]


class LedgerWriteError(RuntimeError):
    """A ledger write could not complete safely."""


class LedgerValidationError(LedgerWriteError, ValueError):
    """Candidate content fails Beancount validation without changing source files."""


class LedgerWriteConflict(LedgerWriteError):
    """An unexpected file state requires manual resolution."""


@contextmanager
def ledger_lock(ledger_path):
    """Coordinate every writer using the canonical main ledger path."""
    key = str(Path(ledger_path).resolve())
    with _LOCKS_GUARD:
        lock = _LOCKS.setdefault(key, threading.RLock())
    with lock:
        yield


def file_fingerprint(path: Path) -> Fingerprint | None:
    path = Path(path)
    try:
        before = path.stat()
        content = path.read_bytes()
        after = path.stat()
    except FileNotFoundError:
        return None
    if (before.st_mtime_ns, before.st_size, before.st_ino) != (
        after.st_mtime_ns,
        after.st_size,
        after.st_ino,
    ):
        raise LedgerWriteConflict("Ledger changed while reading")
    return after.st_mtime_ns, after.st_size, hashlib.sha256(content).hexdigest()


def _workspace(ledger_path: Path) -> Path:
    key = hashlib.sha256(str(ledger_path).encode()).hexdigest()[:16]
    return ledger_path.parent / (".beanmind-write-" + key)


def has_pending_write(ledger_path) -> bool:
    return (_workspace(Path(ledger_path).resolve()) / "manifest.json").exists()


def _sync_directory(directory: Path):
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_temp(directory: Path, content: bytes, mode: int = 0o600) -> Path:
    descriptor, name = tempfile.mkstemp(prefix=".beanmind-", dir=directory)
    path = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            os.fchmod(stream.fileno(), mode & 0o777)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def _save_manifest(workspace: Path, manifest: dict):
    candidate = _write_temp(workspace, json.dumps(manifest).encode())
    try:
        os.replace(candidate, workspace / "manifest.json")
        _sync_directory(workspace)
    finally:
        candidate.unlink(missing_ok=True)


def _safe_path(root: Path, relative: str) -> Path:
    path = root / relative
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise LedgerWriteConflict("Unsafe recovery path")
    # Existing symlinks, including intermediate directories, may not redirect writes.
    current = root
    for part in Path(relative).parts:
        current = current / part
        if current.is_symlink():
            raise LedgerWriteConflict("Symlink ledger path is not writable")
    if not path.resolve().is_relative_to(root):
        raise LedgerWriteConflict("Ledger path lies outside ledger directory")
    return path


def _matches(actual, expected) -> bool:
    return (
        actual is None
        and expected is None
        or (
            actual is not None and expected is not None and tuple(actual)[1:] == tuple(expected)[1:]
        )
    )


def _formal_entries(entries, original: Path, mirror: Path | None = None):
    result = []
    for entry in entries:
        metadata = dict(entry.meta)
        filename = Path(metadata.get("filename", original))
        if mirror is None:
            metadata["filename"] = str(original)
        elif filename.is_relative_to(mirror):
            metadata["filename"] = str(original.parent / filename.relative_to(mirror))
        else:
            # Plugins may create synthetic directives (e.g. <currency_accounts>).
            # Preserve their provenance; they are not entries from a changed source.
            metadata["filename"] = str(filename)
        if isinstance(entry, data.Transaction):
            postings = []
            for posting in entry.postings:
                posting_meta = dict(posting.meta or {})
                posting_meta["filename"] = metadata["filename"]
                postings.append(posting._replace(meta=posting_meta))
            entry = entry._replace(postings=postings)
        result.append(entry._replace(meta=metadata))
    return result


def _pure_transactions(entries) -> bool:
    return all(
        isinstance(entry, data.Transaction)
        and all(
            posting.units is not None
            and isinstance(getattr(posting.units, "number", None), Decimal)
            and isinstance(getattr(posting.units, "currency", None), str)
            and posting.cost is None
            and posting.price is None
            for posting in entry.postings
        )
        for entry in entries
    )


_INCLUDE = re.compile(r'^\s*include\s+"([^"\n]+)"', re.MULTILINE)
_GLOBAL = re.compile(
    r'^\s*(plugin\b|option\s+"([^"]+)"|\d{4}-\d{2}-\d{2}\s+(?:pad|custom|balance)\b)', re.MULTILINE
)


def _source_tree(ledger_path: Path, changes: dict[Path, str]):
    """Read referenced sources without parsing large unchanged annual files."""
    root = ledger_path.parent
    sources = {}
    pending = [ledger_path]
    while pending:
        path = pending.pop()
        if path in sources:
            continue
        path = _safe_path(root, str(path.relative_to(root)))
        content = changes.get(path)
        if content is None:
            content = path.read_text(encoding="utf-8")
        sources[path] = content
        for pattern in _INCLUDE.findall(content):
            relative = path.parent / pattern
            if Path(pattern).is_absolute() or not relative.resolve().is_relative_to(root):
                raise LedgerWriteConflict("External includes cannot be safely staged")
            matches = set(Path(name).resolve() for name in glob.glob(str(relative)))
            # New files can be included before they exist on disk.
            matches.update(p for p in changes if p.match(str(relative)))
            if not matches:
                raise LedgerWriteError("Ledger include has no matching source")
            pending.extend(matches)
    return sources


def supports_local_parse(ledger_path) -> bool:
    """Conservative global-configuration gate shared with projection refresh."""
    try:
        sources = _source_tree(Path(ledger_path).resolve(), {})
        return all(
            not any(
                match.group(2) not in {"title", "operating_currency"}
                for match in _GLOBAL.finditer(content)
            )
            for content in sources.values()
        )
    except (OSError, LedgerWriteError, ValueError):
        return False


def _validate_candidates(
    ledger_path: Path, changes: dict[Path, str], candidates: dict, validation_context=None
):
    parsed = {}
    pure = ledger_path not in changes
    for path, temporary in candidates.items():
        entries, errors, options = parser.parse_file(str(temporary))
        if errors:
            raise LedgerValidationError("Candidate ledger syntax is invalid")
        parsed[str(path)] = _formal_entries(entries, path)
        pure = pure and _pure_transactions(entries) and not options.get("include")
    sources = _source_tree(ledger_path, changes)
    pure = pure and all(
        not any(
            match.group(2) not in {"title", "operating_currency"}
            for match in _GLOBAL.finditer(text)
        )
        for text in sources.values()
    )
    if pure and validation_context is not None:
        context_entries, context_options = validation_context
        # Retain lifecycle/currency/global declarations from the locked valid view,
        # and validate every candidate transaction against them. Syntax parsing alone
        # cannot reject postings before account opening or unsupported currencies.
        validation_entries = [
            entry for entry in context_entries if not isinstance(entry, data.Transaction)
        ]
        validation_entries.extend(entry for entries in parsed.values() for entry in entries)
        validation_entries.sort(key=data.entry_sortkey)
        if validation.validate(validation_entries, context_options):
            raise LedgerValidationError("Candidate ledger validation failed")
        return parsed
    # Validate the complete candidate graph in isolation, including accounts and plugins.
    with tempfile.TemporaryDirectory(prefix=".beanmind-validate-", dir=ledger_path.parent) as name:
        mirror = Path(name)
        for path, content in {**sources, **changes}.items():
            target = mirror / path.relative_to(ledger_path.parent)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            target.chmod(0o600)
        entries, errors, _ = loader.load_file(str(mirror / ledger_path.name))
        if errors:
            raise LedgerValidationError("Candidate ledger validation failed")
        formal = _formal_entries(entries, ledger_path, mirror)
        return {
            str(path): [e for e in formal if e.meta["filename"] == str(path)] for path in changes
        }


def _read_manifest(ledger_path: Path):
    workspace = _workspace(ledger_path)
    if workspace.is_symlink() or (workspace / "manifest.json").is_symlink():
        raise LedgerWriteConflict("Unsafe recovery directory")
    try:
        manifest = json.loads((workspace / "manifest.json").read_text(encoding="utf-8"))
        if manifest["ledger"] != str(ledger_path) or manifest["stage"] not in {
            "PREPARED",
            "FILES_COMMITTED",
        }:
            raise ValueError
        if not isinstance(manifest["files"], list) or not manifest["files"]:
            raise ValueError
        for item in manifest["files"]:
            _safe_path(ledger_path.parent, item["path"])
            _safe_path(workspace, item["backup"])
            _safe_path(ledger_path.parent, item["candidate"])
    except (KeyError, ValueError, TypeError, OSError) as exc:
        raise LedgerWriteConflict("Recovery manifest is invalid") from exc
    return workspace, manifest


def assert_ledger_readable(ledger_path) -> None:
    """Reject source reads while recovery could expose a partially replaced ledger."""
    ledger_path = Path(ledger_path).resolve()
    with ledger_lock(ledger_path):
        if not has_pending_write(ledger_path):
            return
        _, manifest = _read_manifest(ledger_path)
        if manifest["stage"] != "FILES_COMMITTED":
            raise LedgerWriteError("Ledger recovery must complete before source reads")
        for item in manifest["files"]:
            path = _safe_path(ledger_path.parent, item["path"])
            if not _matches(file_fingerprint(path), item["after"]):
                raise LedgerWriteConflict("Unknown ledger modification prevents source reads")


def _rollback(ledger_path: Path, workspace: Path, manifest: dict):
    # Preflight every source and backup before touching any official file.
    for item in manifest["files"]:
        path = _safe_path(ledger_path.parent, item["path"])
        actual = file_fingerprint(path)
        if not (_matches(actual, item["before"]) or _matches(actual, item["after"])):
            raise LedgerWriteConflict("Unknown ledger modification prevents recovery")
        if item["before"] is not None:
            backup = _safe_path(workspace, item["backup"])
            if not _matches(file_fingerprint(backup), item["before"]):
                raise LedgerWriteConflict("Recovery copy is missing or changed")
    for item in manifest["files"]:
        path = _safe_path(ledger_path.parent, item["path"])
        if not _matches(file_fingerprint(path), item["before"]):
            if item["before"] is None:
                path.unlink(missing_ok=True)
            else:
                content = _safe_path(workspace, item["backup"]).read_bytes()
                temporary = _write_temp(path.parent, content, item["mode"])
                try:
                    os.replace(temporary, path)
                finally:
                    temporary.unlink(missing_ok=True)
            _sync_directory(path.parent)
        if not _matches(file_fingerprint(path), item["before"]):
            raise LedgerWriteConflict("Recovered source fingerprint mismatch")


def _cleanup(ledger_path: Path, workspace: Path, manifest: dict):
    """Only FILES_COMMITTED manifests can be cleaned without their recovery copies."""
    removed = False
    try:
        for item in manifest["files"]:
            _safe_path(ledger_path.parent, item["candidate"]).unlink(missing_ok=True)
            _safe_path(workspace, item["backup"]).unlink(missing_ok=True)
        _sync_directory(workspace)
        (workspace / "manifest.json").unlink(missing_ok=True)
        removed = True
        _sync_directory(workspace)
    except OSError:
        if removed:
            # FILES_COMMITTED recovery needs no backup; restore its marker on fsync failure.
            try:
                _save_manifest(workspace, manifest)
            except OSError:
                logger.error("Ledger recovery marker persistence failed")
        logger.warning("Ledger recovery cleanup deferred")


def recover_ledger_write(ledger_path, rebuild_callback: Callable[[], None]) -> bool:
    """Recover interrupted files, then rebuild the projection before clearing the marker."""
    ledger_path = Path(ledger_path).resolve()
    with ledger_lock(ledger_path):
        if not has_pending_write(ledger_path):
            return False
        workspace, manifest = _read_manifest(ledger_path)
        if manifest["stage"] == "PREPARED":
            _rollback(ledger_path, workspace, manifest)
            # Persist the restored source as the authoritative FILES_COMMITTED version.
            for item in manifest["files"]:
                item["after"] = item["before"]
            manifest["stage"] = "FILES_COMMITTED"
            _save_manifest(workspace, manifest)
        else:
            for item in manifest["files"]:
                path = _safe_path(ledger_path.parent, item["path"])
                if not _matches(file_fingerprint(path), item["after"]):
                    raise LedgerWriteConflict("Unknown ledger modification prevents recovery")
        rebuild_callback()
        _cleanup(ledger_path, workspace, manifest)
        return True


def commit_ledger_files(
    ledger_path,
    changes: dict[Path, str],
    *,
    before_commit: Callable[[], None],
    after_commit: Callable[[ParsedFiles], None],
    expected_fingerprints: dict[Path, Fingerprint | None] | None = None,
    validation_context: tuple[list, dict] | None = None,
) -> bool:
    """Validate and commit candidates; False means source committed, projection deferred.

    ``before_commit`` must durably mark the projection DIRTY. A caller must recover a
    pending operation before starting this one. All source paths stay under the ledger
    directory and callbacks execute under the common reentrant lock. ``validation_context``
    must be a complete valid loader view obtained by the caller under this same lock;
    without it candidate verification uses the full loader.
    """
    ledger_path = Path(ledger_path).resolve()
    root = ledger_path.parent
    with ledger_lock(ledger_path):
        if has_pending_write(ledger_path):
            raise LedgerWriteConflict("Pending ledger recovery blocks new writes")
        changes = {Path(path).absolute(): text for path, text in changes.items()}
        if not changes:
            return True
        for path in changes:
            _safe_path(root, str(path.relative_to(root)))
        expected = {
            Path(path).absolute(): value for path, value in (expected_fingerprints or {}).items()
        }
        workspace = _workspace(ledger_path)
        workspace.mkdir(mode=0o700, exist_ok=True)
        if workspace.is_symlink():
            raise LedgerWriteConflict("Unsafe recovery directory")
        workspace.chmod(0o700)
        _sync_directory(root)
        manifest = {
            "version": 1,
            "operation": uuid.uuid4().hex,
            "ledger": str(ledger_path),
            "stage": "PREPARED",
            "files": [],
        }
        candidates = {}
        prepared = False
        try:
            for index, (path, content) in enumerate(changes.items()):
                before = file_fingerprint(path)
                if path in expected and before != expected[path]:
                    raise LedgerWriteConflict("Ledger source changed before commit")
                mode = stat.S_IMODE(path.stat().st_mode) if before is not None else 0o600
                candidate = _write_temp(path.parent, content.encode("utf-8"), mode)
                candidates[path] = candidate
                backup_name = f'{manifest["operation"]}-{index}.before'
                item = {
                    "path": str(path.relative_to(root)),
                    "candidate": str(candidate.relative_to(root)),
                    "backup": backup_name,
                    "before": before,
                    "after": file_fingerprint(candidate),
                    "mode": mode,
                }
                manifest["files"].append(item)
                if before is not None:
                    backup = _write_temp(workspace, path.read_bytes())
                    os.replace(backup, workspace / backup_name)
                    if not _matches(file_fingerprint(workspace / backup_name), before):
                        raise LedgerWriteConflict("Ledger changed during candidate preparation")
            validation_started = time.perf_counter()
            parsed = _validate_candidates(ledger_path, changes, candidates, validation_context)
            logger.info("ledger_candidate_validate duration_ms=%.1f files=%d",
                        (time.perf_counter() - validation_started) * 1000, len(changes))
            for item in manifest["files"]:
                if file_fingerprint(root / item["path"]) != item["before"]:
                    raise LedgerWriteConflict("Ledger changed during validation")
            _sync_directory(workspace)
            try:
                _save_manifest(workspace, manifest)
            finally:
                # A directory fsync can fail after atomic manifest publication.
                prepared = has_pending_write(ledger_path)
            try:
                before_commit()
            except Exception:
                # No official file was touched; discard the marker before its backups.
                (workspace / "manifest.json").unlink()
                _sync_directory(workspace)
                prepared = False
                raise
            files_started = time.perf_counter()
            try:
                for item in manifest["files"]:
                    path = root / item["path"]
                    if file_fingerprint(path) != item["before"]:
                        raise LedgerWriteConflict("Ledger changed before replacement")
                    os.replace(candidates[path], path)
                    _sync_directory(path.parent)
                    if not _matches(file_fingerprint(path), item["after"]):
                        raise LedgerWriteConflict("Committed ledger fingerprint mismatch")
            except Exception:
                _rollback(ledger_path, workspace, manifest)
                raise
            manifest["stage"] = "FILES_COMMITTED"
            try:
                _save_manifest(workspace, manifest)
            except Exception:
                # Publication may have succeeded before its directory fsync failed.
                # Durably reinstate PREPARED before restoring any official source.
                manifest["stage"] = "PREPARED"
                _save_manifest(workspace, manifest)
                _rollback(ledger_path, workspace, manifest)
                raise
            logger.info("ledger_files_commit duration_ms=%.1f files=%d",
                        (time.perf_counter() - files_started) * 1000, len(changes))
            parsed_files = {
                path: (entries, file_fingerprint(Path(path))) for path, entries in parsed.items()
            }
            try:
                after_commit(parsed_files)
            except Exception:
                logger.error("Ledger files committed; projection recovery required")
                return False
            _cleanup(ledger_path, workspace, manifest)
            return True
        finally:
            if not prepared:
                for candidate in candidates.values():
                    candidate.unlink(missing_ok=True)
                for item in manifest["files"]:
                    (workspace / item["backup"]).unlink(missing_ok=True)
