"""Shared full ledger views bound to a verified, current source graph."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import logging
from pathlib import Path
from threading import Lock
from time import perf_counter

from beancount import loader
from beancount.core import data
from beancount.core.amount import Amount
from beancount.core.position import Cost, CostSpec

from .beancount_service import BeancountService
from .ledger_write import (
    Fingerprint, LedgerSourceUnsupported, LedgerWriteConflict, SourceState,
    assert_ledger_readable, has_pending_write, ledger_lock,
    sample_source_state, trusted_full_view,
)

logger = logging.getLogger(__name__)


def _immutable_amount(value):
    return value is None or (
        type(value) is Amount and type(value.number) in (Decimal, type(None))
        and type(value.currency) is str
    )


def _immutable_cost(value):
    return value is None or (
        type(value) in (Cost, CostSpec)
        and all(type(field) in (Decimal, str, date, bool, type(None)) for field in value)
    )


def _clone_entry(entry):
    """Copy mutable 3.2.0 Transaction containers; unknown shapes use deepcopy.

    NamedTuple alone does not prove its fields immutable. Exact scalar/types
    checks exclude subclasses with mutable state and atypical plugin output.
    """
    if (
        type(entry) is not data.Transaction or type(entry.date) is not date
        or type(entry.flag) not in (str, type(None))
        or type(entry.payee) not in (str, type(None))
        or type(entry.narration) not in (str, type(None))
        or type(entry.tags) is not frozenset or type(entry.links) is not frozenset
        or any(type(value) is not str for value in entry.tags)
        or any(type(value) is not str for value in entry.links)
        or type(entry.postings) is not list
    ):
        return deepcopy(entry)
    for posting in entry.postings:
        if (
            type(posting) is not data.Posting or type(posting.account) is not str
            or type(posting.flag) not in (str, type(None))
            or not _immutable_amount(posting.units) or not _immutable_amount(posting.price)
            or not _immutable_cost(posting.cost)
        ):
            return deepcopy(entry)
    return entry._replace(
        meta=deepcopy(entry.meta),
        postings=[posting._replace(meta=deepcopy(posting.meta)) for posting in entry.postings],
    )


@dataclass(frozen=True)
class _CacheState:
    ledger_path: Path
    service: BeancountService
    generation: int
    version: dict[Path, Fingerprint] | None
    valid: bool


@dataclass
class _Timing:
    sample_count: int = 0
    sample_ms: float = 0
    construct_ms: float = 0
    load_ms: float = 0

    def log(self, event: str, reason: str, publish_ms: float = 0):
        logger.info(
            "ledger_provider event=%s reason=%s sample_count=%d sample_ms=%.1f "
            "construct_ms=%.1f load_ms=%.1f publish_ms=%.1f",
            event, reason, self.sample_count, self.sample_ms,
            self.construct_ms, self.load_ms, publish_ms,
        )


class BeancountServiceProvider:
    """Single view cache; always acquire ledger_lock before the Provider lock."""

    _state: _CacheState | None = None
    _lock = Lock()

    @classmethod
    def _invalidate_locked(cls):
        state = cls._state
        if state is not None:
            cls._state = _CacheState(
                state.ledger_path, state.service, state.generation, None, False,
            )

    @staticmethod
    def _sample(path: Path, timing: _Timing) -> SourceState | None:
        started = perf_counter()
        try:
            return sample_source_state(path)
        except (LedgerSourceUnsupported, OSError, UnicodeError):
            # The official loader owns unsupported and missing-input semantics.
            return None
        finally:
            timing.sample_count += 1
            timing.sample_ms += (perf_counter() - started) * 1000

    @staticmethod
    def _sources_match(entries, state: SourceState) -> bool:
        accepted = {}
        for entry in entries:
            metadata = [entry.meta]
            metadata.extend(getattr(posting, "meta", None)
                            for posting in getattr(entry, "postings", ()))
            for meta in metadata:
                filename = (meta or {}).get("filename")
                if not isinstance(filename, str):
                    return False
                if filename not in accepted:
                    path = Path(filename)
                    accepted[filename] = (
                        filename.startswith("<") and filename.endswith(">")
                        or path.is_absolute() and path.resolve() in state.fingerprints
                    )
                if not accepted[filename]:
                    return False
        return True

    @classmethod
    def _load_locked(cls, path: Path, before: SourceState | None, timing: _Timing):
        cls._invalidate_locked()
        service = BeancountService.__new__(BeancountService)
        started = perf_counter()
        try:
            service.__init__(path)
        finally:
            elapsed = (perf_counter() - started) * 1000
            load_ms = getattr(service, "load_duration_ms", 0.0)
            timing.load_ms += load_ms
            timing.construct_ms += max(0.0, elapsed - load_ms)
        after = cls._sample(path, timing)
        if before is not None and before != after:
            raise LedgerWriteConflict("Ledger changed while loading")
        valid = (
            before is not None and after is not None and not service.errors
            and trusted_full_view(after, service.options)
            and Path(service.options["filename"]).resolve() == path
            and cls._sources_match(service.entries, after)
        )
        cls._state = _CacheState(
            path, service, service.load_generation,
            dict(after.fingerprints) if valid else None, valid,
        )
        timing.log("load" if valid else "fallback", "verified" if valid else "untrusted_view")
        return service

    @classmethod
    def get_service(cls, ledger_path: Path | str) -> BeancountService:
        path = Path(ledger_path).resolve()
        timing = _Timing()
        with ledger_lock(path), cls._lock:
            try:
                assert_ledger_readable(path)
                before = cls._sample(path, timing)
                state = cls._state
                if (
                    state is not None and state.valid and state.ledger_path == path
                    and state.service.ledger_path == path
                    and state.service.load_generation == state.generation
                    and before is not None and state.version == before.fingerprints
                    and not state.service.errors
                    and trusted_full_view(before, state.service.options)
                    and Path(state.service.options["filename"]).resolve() == path
                ):
                    timing.log("hit", "verified")
                    return state.service
                return cls._load_locked(path, before, timing)
            except Exception:
                cls._invalidate_locked()
                timing.log("fallback", "load_failed")
                raise

    @classmethod
    def invalidate(cls) -> None:
        with cls._lock:
            cls._invalidate_locked()

    @classmethod
    def reload(cls) -> None:
        # Snapshot the path without ever acquiring the ledger lock under _lock.
        with cls._lock:
            state = cls._state
        if state is None:
            return
        path = state.ledger_path
        timing = _Timing()
        with ledger_lock(path), cls._lock:
            if cls._state is None or cls._state.ledger_path != path:
                return
            try:
                cls._invalidate_locked()
                assert_ledger_readable(path)
                cls._load_locked(path, cls._sample(path, timing), timing)
            except Exception:
                cls._invalidate_locked()
                timing.log("fallback", "load_failed")
                raise

    @classmethod
    def clear(cls) -> None:
        with cls._lock:
            cls._state = None

    @classmethod
    def publish(cls, snapshot, receipt) -> bool:
        """Publish only the actually committed candidate; acceleration never raises."""
        timing = _Timing()
        started = perf_counter()
        reason = "publish_failed"
        try:
            path = Path(snapshot.ledger_path).resolve()
            with ledger_lock(path), cls._lock:
                cls._invalidate_locked()
                if cls._state is not None and cls._state.ledger_path != path:
                    reason = "ledger_mismatch"
                elif (
                    receipt is None or receipt.snapshot is not snapshot
                    or not receipt.candidate_used or not receipt.ready_committed
                ):
                    reason = "receipt_rejected"
                elif has_pending_write(path):
                    reason = "pending_write"
                else:
                    before = cls._sample(path, timing)
                    if (
                        before is None or before.fingerprints != receipt.source_version
                        or snapshot.source_hashes != {
                            source: fingerprint[2]
                            for source, fingerprint in before.fingerprints.items()
                        }
                    ):
                        reason = "source_mismatch"
                    elif (
                        snapshot.options is None
                        or not trusted_full_view(before, snapshot.options)
                        or Path(snapshot.options["filename"]).resolve() != path
                        or not cls._sources_match(snapshot.entries, before)
                    ):
                        reason = "untrusted_view"
                    else:
                        copied = perf_counter()
                        service = BeancountService.__new__(BeancountService)
                        service.ledger_path = path
                        service.entries = [_clone_entry(entry) for entry in snapshot.entries]
                        service.options = deepcopy(snapshot.options)
                        service.errors = []
                        service.load_generation = 1
                        service.load_duration_ms = 0.0
                        service.options["input_hash"] = loader.compute_input_hash(
                            service.options["include"],
                        )
                        timing.construct_ms = (perf_counter() - copied) * 1000
                        after = cls._sample(path, timing)
                        if after != before:
                            reason = "source_mismatch"
                        else:
                            cls._state = _CacheState(
                                path, service, service.load_generation,
                                dict(after.fingerprints), True,
                            )
                            timing.log("publish", "verified", (perf_counter() - started) * 1000)
                            return True
        except Exception:
            # No exception details: paths, plugin config and entries are private.
            cls.invalidate()
        timing.log("fallback", reason, (perf_counter() - started) * 1000)
        return False
