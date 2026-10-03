"""Single-process ledger file commit and crash recovery.

The manifest coordinates files only; callers own projection transactions and recovery.
No ledger content or exception text is emitted to logs by this module.
"""

from __future__ import annotations

import glob
import copy
import hashlib
import inspect
import json
import logging
import os
from pathlib import Path
import re
import stat
import tempfile
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable
import uuid
import time

import beancount
from beancount import loader
from beancount.core import data
from beancount.parser import parser, options as parser_options
from beancount.ops import validation

logger = logging.getLogger(__name__)
_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()
Fingerprint = tuple[int, int, str]
ParsedFiles = dict[str, tuple[list, Fingerprint]]


@dataclass(frozen=True)
class CandidateSnapshot:
    entries: list
    source_hashes: dict[Path, str]
    options: dict | None = None
    ledger_path: Path | None = None


@dataclass(frozen=True)
class SourceState:
    fingerprints: dict[Path, Fingerprint]
    sources: dict[Path, str]


@dataclass(frozen=True)
class ProjectionReceipt:
    snapshot: CandidateSnapshot
    source_version: dict[Path, Fingerprint]
    candidate_used: bool
    ready_committed: bool


class ValidatedFiles(dict):
    def __init__(self, files, candidate_snapshot=None, projection_receipt=None):
        super().__init__(files)
        self.candidate_snapshot = candidate_snapshot
        self.projection_receipt = projection_receipt

    def copy(self):
        return ValidatedFiles(self, self.candidate_snapshot, self.projection_receipt)


class LedgerWriteError(RuntimeError):
    """A ledger write could not complete safely."""


class LedgerValidationError(LedgerWriteError, ValueError):
    """Candidate content fails Beancount validation without changing source files."""


class LedgerWriteConflict(LedgerWriteError):
    """An unexpected file state requires manual resolution."""


class LedgerSourceUnsupported(LedgerWriteError):
    """The complete loader input cannot be bound to a reusable source graph."""


def load_ledger_file(filename, log_timings=None, log_errors=None, extra_validations=None, encoding=None):
    """Run the pinned full pipeline without the mtime/size-only pickle cache.

    Beancount's encrypted public entry point already bypasses that cache. The
    plaintext private adapter is deliberately version-bound and fails closed
    if the installed pipeline contract changes.
    """
    filename = os.path.abspath(os.path.expandvars(os.path.expanduser(os.fspath(filename))))
    if loader.encryption.is_encrypted_file(filename):
        return loader.load_file(filename, log_timings, log_errors, extra_validations, encoding)
    uncached = getattr(loader, "_uncached_load_file", None)
    pipeline = getattr(loader, "_load", None)
    error_logger = getattr(loader, "_log_errors", None)
    if beancount.__version__ != "3.2.0" or not all(callable(value) for value in (uncached, pipeline, error_logger)):
        raise LedgerWriteError("Unsupported Beancount complete loader contract")
    try:
        inspect.signature(uncached).bind(filename, log_timings, extra_validations, encoding)
        inspect.signature(pipeline).bind([(filename, True)], log_timings, extra_validations, encoding)
        inspect.signature(error_logger).bind([], log_errors)
    except (TypeError, ValueError) as exc:
        raise LedgerWriteError("Unsupported Beancount complete loader contract") from exc
    entries, errors, options = uncached(filename, log_timings, extra_validations, encoding)
    error_logger(errors, log_errors)
    return entries, errors, options


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
    filenames = {}
    for entry in entries:
        metadata = dict(entry.meta)
        source_name = metadata.get("filename", str(original))
        if source_name not in filenames:
            filename = Path(source_name)
            if mirror is None:
                filenames[source_name] = str(original)
            elif filename.is_relative_to(mirror):
                filenames[source_name] = str(original.parent / filename.relative_to(mirror))
            else:
                # Keep plugin-generated virtual provenance as virtual provenance.
                filenames[source_name] = str(filename)
        metadata["filename"] = filenames[source_name]
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


def _has_global_semantics(content: str) -> bool:
    return any(match.group(2) not in {"title", "operating_currency"} for match in _GLOBAL.finditer(content))


def _pure_transaction_source(content: str) -> bool:
    return all(
        not line or line[0].isspace() or line.startswith(";")
        or re.match(r"\d{4}-\d{2}-\d{2}\s+[*!]\s", line)
        for line in content.splitlines()
    )


def _reusable_sources(ledger_path: Path, changes: dict[Path, str], sources: dict[Path, str]) -> bool:
    if len(changes) != 1 or ledger_path in changes:
        return False
    changed = next(iter(changes))
    if changed not in sources or not changed.is_file():
        return False
    if not _pure_transaction_source(changes[changed]) or not _pure_transaction_source(changed.read_text(encoding="utf-8")):
        return False
    if not _trusted_source_syntax(sources):
        return False
    # The candidate must have the same physical source graph and unchanged inputs.
    original = _source_tree(ledger_path, {})
    return original.keys() == sources.keys() and all(
        original[path] == content for path, content in sources.items() if path != changed
    )


_AUTO_ACCOUNTS = 'plugin "beancount.plugins.auto_accounts"'


def _trusted_source_syntax(sources: dict[Path, str]) -> bool:
    plugins = 0
    for content in sources.values():
        for line in content.splitlines():
            if not line.strip() or line.lstrip().startswith(";"):
                continue
            if re.match(r"\s*plugin\b", line):
                if line != _AUTO_ACCOUNTS:
                    return False
                plugins += 1
                if plugins > 1:
                    return False
                continue
            if line[0].isspace():
                # Continuation plugin configuration is not a canonical declaration.
                if plugins and line.lstrip().startswith('"'):
                    return False
                continue
            if re.match(r'option\s+"(?:title|operating_currency)"\s', line):
                continue
            include = _INCLUDE.fullmatch(line)
            if include and not glob.has_magic(include.group(1)):
                continue
            if re.match(r"\d{4}-\d{2}-\d{2}\s+(?:[*!]|open\b|close\b|balance\b|custom\b|price\b|commodity\b)", line):
                continue
            return False
    return True


def trusted_full_view(state: SourceState, options: dict) -> bool:
    """Admit only fully tracked configuration and the exact supported plugin tuple."""
    if not state.sources or not _trusted_source_syntax(state.sources):
        return False
    declarations = sum(line == _AUTO_ACCOUNTS for text in state.sources.values() for line in text.splitlines())
    expected = [("beancount.plugins.auto_accounts", None)] if declarations else []
    if options.get("plugin", []) != expected:
        return False
    known = set(parser_options.OPTIONS_DEFAULTS) | {"pythonpath", "input_hash"}
    if set(options) - known or options.get("pythonpath") or options.get("insert_pythonpath"):
        return False
    try:
        if {Path(name).resolve() for name in options.get("include", [])} != set(state.sources):
            return False
        if Path(options["filename"]).resolve() not in state.sources:
            return False
    except (KeyError, TypeError, ValueError):
        return False
    return True


def sample_source_state(ledger_path) -> SourceState:
    """Read the current include graph and content once, rejecting unstable samples."""
    started = time.perf_counter()
    ledger_path = Path(ledger_path).resolve()
    root = ledger_path.parent
    sources, fingerprints, stable_stats = {}, {}, {}
    pending = [ledger_path]
    def signature(value):
        return value.st_mtime_ns, value.st_size, value.st_ino, value.st_ctime_ns
    try:
        while pending:
            path = pending.pop()
            if path in sources:
                continue
            if not path.is_relative_to(root):
                raise LedgerSourceUnsupported("External include input")
            current = root
            for part in path.relative_to(root).parts:
                current /= part
                if current.is_symlink():
                    raise LedgerSourceUnsupported("Symlink include input")
            before = path.stat()
            raw = path.read_bytes()
            after = path.stat()
            if signature(before) != signature(after):
                raise LedgerWriteConflict("Ledger changed while sampling")
            stable_stats[path] = signature(after)
            sources[path] = raw.decode("utf-8")
            fingerprints[path] = (after.st_mtime_ns, after.st_size, hashlib.sha256(raw).hexdigest())
            for pattern in _INCLUDE.findall(sources[path]):
                if glob.has_magic(pattern) or Path(pattern).is_absolute():
                    raise LedgerSourceUnsupported("Untracked include input")
                target = Path(os.path.abspath(path.parent / pattern))
                if not target.is_relative_to(root):
                    raise LedgerSourceUnsupported("External include input")
                pending.append(target)
        # Verify all metadata after the graph traversal, rather than accepting an
        # early source which changed while a later include was being read.
        for path in fingerprints:
            current = path.stat()
            if signature(current) != stable_stats[path]:
                raise LedgerWriteConflict("Ledger changed while sampling")
        return SourceState(fingerprints, sources)
    finally:
        logger.info("ledger_source_verify duration_ms=%.1f", (time.perf_counter() - started) * 1000)


def _formal_options(options, mirror: Path, ledger_path: Path, sources):
    formal = copy.deepcopy(options)
    known = set(parser_options.OPTIONS_DEFAULTS) | {"pythonpath", "input_hash"}
    if set(formal) - known:
        return None
    def physical(name, directory=False):
        path = Path(name)
        if not path.is_absolute() or not path.is_relative_to(mirror):
            raise ValueError("Unverified candidate path")
        target = ledger_path.parent / path.relative_to(mirror)
        if target not in (set(p.parent for p in sources) if directory else sources):
            raise ValueError("Unverified candidate input")
        return str(target)
    try:
        formal["filename"] = physical(formal["filename"])
        if formal["filename"] != str(ledger_path):
            return None
        formal["include"] = [physical(name) for name in formal.get("include", [])]
        formal["pythonpath"] = [physical(name, True) for name in formal.get("pythonpath", [])]
    except (KeyError, TypeError, ValueError):
        return None
    formal.pop("input_hash", None)  # Provider recomputes this only on the formal version.
    if not trusted_full_view(SourceState({}, sources), formal):
        return None
    return formal


def _candidate_snapshot(entries, options, mirror: Path, sources: dict[Path, str], ledger_path: Path):
    formal_options = _formal_options(options, mirror, ledger_path, sources)
    if formal_options is None:
        return None
    included = {mirror / ledger_path.name}
    for filename in options.get("include", []):
        path = Path(filename)
        if not path.is_relative_to(mirror):
            return None
        included.add(path)
    if included != {mirror / path.relative_to(ledger_path.parent) for path in sources}:
        return None
    # The mirror graph already enumerates every accepted physical source. Build
    # its mapping once in this phase; each entry still validates its own metadata.
    physical_sources = {
        str(mirror / path.relative_to(ledger_path.parent)): path for path in sources
    }
    for entry in entries:
        metadata = entry.meta or {}
        filename = metadata.get("filename")
        if not isinstance(filename, str) or not filename:
            return None
        if filename.startswith("<") and filename.endswith(">"):
            if isinstance(entry, data.Transaction):
                return None
            continue
        if filename not in physical_sources:
            return None
        if not isinstance(entry, data.Transaction):
            continue
        if not isinstance(metadata.get("lineno"), int):
            return None
        for posting in entry.postings:
            posting_file = (posting.meta or {}).get("filename")
            if posting_file is not None and posting_file != filename:
                return None
    return CandidateSnapshot(
        _formal_entries(entries, ledger_path, mirror),
        {path: hashlib.sha256(text.encode("utf-8")).hexdigest() for path, text in sources.items()},
        formal_options, ledger_path,
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
        return all(not _has_global_semantics(content) for content in sources.values())
    except (OSError, LedgerWriteError, ValueError):
        return False


def _validate_candidates(
    ledger_path: Path, changes: dict[Path, str], candidates: dict, validation_context=None
):
    sources = _source_tree(ledger_path, changes)
    global_semantics = any(_has_global_semantics(text) for text in sources.values())
    if not global_semantics:
        # Removing a global directive also changes semantics; stale locked loader
        # context must not validate the candidate as if the directive remained.
        global_semantics = any(
            path.is_file() and _has_global_semantics(path.read_text(encoding="utf-8"))
            for path in changes
        )
    parsed = {}
    full_loader_required = ledger_path in changes or global_semantics or validation_context is None
    pure = not full_loader_required
    # With global directives the complete loader below already parses every candidate.
    # Do not parse large changed files twice; its errors still reject before DIRTY.
    for path, temporary in candidates.items():
        # A changed file outside the candidate include graph is not read by the
        # loader; preserve its standalone syntax check before touching the source.
        if full_loader_required and path in sources:
            continue
        entries, errors, options = parser.parse_file(str(temporary))
        if errors:
            raise LedgerValidationError("Candidate ledger syntax is invalid")
        parsed[str(path)] = _formal_entries(entries, path)
        pure = pure and _pure_transactions(entries) and not options.get("include")
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
        return parsed, None
    # Validate the complete candidate graph in isolation, including accounts and plugins.
    with tempfile.TemporaryDirectory(prefix=".beanmind-validate-", dir=ledger_path.parent) as name:
        mirror = Path(name)
        mirror_started = time.perf_counter()
        for path, content in {**sources, **changes}.items():
            target = mirror / path.relative_to(ledger_path.parent)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            target.chmod(0o600)
        load_started = time.perf_counter()
        entries, errors, options = loader.load_file(str(mirror / ledger_path.name))
        logger.info("ledger_candidate_full mirror_ms=%.1f loader_ms=%.1f",
                    (load_started - mirror_started) * 1000,
                    (time.perf_counter() - load_started) * 1000)
        if errors:
            raise LedgerValidationError("Candidate ledger validation failed")
        reusable = _reusable_sources(ledger_path, changes, sources)
        snapshot = _candidate_snapshot(entries, options, mirror, sources, ledger_path) if reusable else None
        formal = snapshot.entries if snapshot else _formal_entries(entries, ledger_path, mirror)
        return {
            str(path): [e for e in formal if e.meta["filename"] == str(path)] for path in changes
        }, snapshot


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

    ``before_commit`` must durably mark the projection DIRTY and may be called again
    after projection if an external source conflict is detected. A caller must recover a
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
        prepare_started = time.perf_counter()
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
            logger.info("ledger_write_prepare duration_ms=%.1f", (time.perf_counter() - prepare_started) * 1000)
            validation_started = time.perf_counter()
            parsed, snapshot = _validate_candidates(ledger_path, changes, candidates, validation_context)
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
            dirty_started = time.perf_counter()
            try:
                before_commit()
            except Exception:
                # No official file was touched; discard the marker before its backups.
                (workspace / "manifest.json").unlink()
                _sync_directory(workspace)
                prepared = False
                raise
            logger.info("ledger_write_dirty duration_ms=%.1f", (time.perf_counter() - dirty_started) * 1000)
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
            parsed_files = ValidatedFiles({
                path: (entries, file_fingerprint(Path(path))) for path, entries in parsed.items()
            }, snapshot)
            try:
                after_commit(parsed_files)
            except Exception:
                logger.error("Ledger files committed; projection recovery required")
                return False
            try:
                assert_ledger_readable(ledger_path)
            except Exception:
                logger.error("Ledger changed after projection; recovery required")
                try:
                    before_commit()
                except Exception:
                    logger.exception("Unable to mark projection DIRTY after ledger conflict")
                return False
            cleanup_started = time.perf_counter()
            _cleanup(ledger_path, workspace, manifest)
            logger.info("ledger_write_cleanup duration_ms=%.1f", (time.perf_counter() - cleanup_started) * 1000)
            return True
        finally:
            if not prepared:
                for candidate in candidates.values():
                    candidate.unlink(missing_ok=True)
                for item in manifest["files"]:
                    (workspace / item["backup"]).unlink(missing_ok=True)
