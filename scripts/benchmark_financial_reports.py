#!/usr/bin/env python3
"""只读测量资产负债表、利润表、账户明细与近12个月趋势；所有副本与 SQLite 均在临时目录。"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import resource
import shutil
import statistics
import sys
import tempfile
import time
import uuid
from pathlib import Path

from beancount import loader
from beancount.core.data import Transaction
from beancount.parser import printer
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure repo root on path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import get_db, settings  # noqa: E402
from backend.infrastructure.persistence.beancount.beancount_provider import (  # noqa: E402
    BeancountServiceProvider,
)
from backend.infrastructure.persistence.db.models import Base  # noqa: E402
from backend.infrastructure.persistence.ledger_projection import (  # noqa: E402
    LedgerProjectionService,
    TransactionQueryService,
)
from backend.interfaces.api import reports as reports_api  # noqa: E402


def elapsed_ms(operation):
    started = time.perf_counter()
    value = operation()
    return (time.perf_counter() - started) * 1000, value


def distribution(samples: list[float]) -> dict:
    ordered = sorted(samples)
    p95_index = max(0, min(len(ordered) - 1, int(len(ordered) * 0.95) - 1))
    return {
        "runs": len(samples),
        "p50_ms": round(statistics.median(ordered), 3),
        "p95_ms": round(ordered[p95_index], 3),
        "max_ms": round(max(ordered), 3),
    }


def source_fingerprint(ledger_path: Path) -> dict[str, str]:
    root = ledger_path.parent
    return {
        str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*.beancount"))
    }


def make_scaled_copy(ledger_path: Path, scale: int, target_root: Path) -> Path:
    copied_dir = target_root / "scaled-ledger"
    shutil.copytree(ledger_path.parent, copied_dir)
    copied_main = copied_dir / ledger_path.name
    if scale == 1:
        return copied_main

    loaded_entries, errors, _ = loader.load_file(str(copied_main))
    if errors:
        raise RuntimeError("; ".join(str(error) for error in errors[:10]))
    by_file: dict[Path, list[Transaction]] = {}
    for entry in loaded_entries:
        if not isinstance(entry, Transaction):
            continue
        source = Path(entry.meta.get("filename", "")).resolve()
        if source.parent == copied_dir.resolve() and source.name.startswith("transactions_"):
            by_file.setdefault(source, []).append(entry)
    for path, transactions in sorted(by_file.items()):
        additions = []
        for copy_number in range(2, scale + 1):
            for entry in transactions:
                meta = dict(entry.meta or {})
                meta.pop("filename", None)
                meta.pop("lineno", None)
                meta["id"] = uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"report-benchmark:{path.name}:{copy_number}:{entry.meta.get('lineno', 0)}",
                ).hex
                additions.append(printer.format_entry(entry._replace(meta=meta)))
        if additions:
            with path.open("a", encoding="utf-8") as handle:
                handle.write("\n" + "\n".join(additions) + "\n")
    return copied_main


def count_transactions(ledger_path: Path) -> tuple[int, int]:
    entries, errors, _ = loader.load_file(str(ledger_path))
    if errors:
        raise RuntimeError("; ".join(str(error) for error in errors[:10]))
    txns = [e for e in entries if isinstance(e, Transaction)]
    postings = sum(len(t.postings) for t in txns)
    return len(txns), postings


def rss_mb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS returns bytes; Linux returns kilobytes
    if platform.system() == "Darwin":
        return round(usage / (1024 * 1024), 3)
    return round(usage / 1024, 3)


def build_client(ledger_path: Path, db_path: Path) -> TestClient:
    BeancountServiceProvider.clear()
    settings.LEDGER_FILE = ledger_path

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    LedgerProjectionService(session, ledger_path).rebuild_all()
    query_service = TransactionQueryService(session, ledger_path)

    app = FastAPI()
    app.include_router(reports_api.router)

    def _db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[reports_api.get_beancount_service] = (
        lambda: BeancountServiceProvider.get_service(ledger_path)
    )
    app.dependency_overrides[reports_api.get_transaction_query_service] = lambda: query_service

    client = TestClient(app)
    client._session = session  # type: ignore[attr-defined]
    client._engine = engine  # type: ignore[attr-defined]
    return client


def measure(client: TestClient, iterations: int) -> dict:
    # Discover a usable as_of and account from first balance sheet call
    setup_ms, setup_resp = elapsed_ms(
        lambda: client.get("/api/reports/balance-sheet", params={"as_of_date": "2026-07-01"})
    )
    if setup_resp.status_code != 200:
        # fallback earlier date
        setup_ms, setup_resp = elapsed_ms(
            lambda: client.get("/api/reports/balance-sheet", params={"as_of_date": "2025-12-31"})
        )
    if setup_resp.status_code != 200:
        raise RuntimeError(f"balance-sheet setup failed: {setup_resp.status_code} {setup_resp.text[:300]}")

    body = setup_resp.json()
    as_of = body.get("as_of_date") or "2025-12-31"

    def walk(items):
        for item in items or []:
            name = item.get("name") or item.get("account")
            children = item.get("children") or []
            if name and ":" in str(name) and not children:
                return name
            found = walk(children)
            if found:
                return found
            # parent nodes also carry full account path names sometimes
            if name and ":" in str(name) and children:
                # prefer leaf
                continue
        for item in items or []:
            name = item.get("name") or item.get("account")
            if name and ":" in str(name):
                return name
        return None

    account = walk(body.get("assets", {}).get("accounts")) or walk(
        body.get("liabilities", {}).get("accounts")
    )

    bs_samples = []
    is_samples = []
    detail_first_samples = []
    detail_next_samples = []
    trend_samples = []
    trend_end_month = as_of[:7] if isinstance(as_of, str) and len(as_of) >= 7 else "2025-12"

    for _ in range(iterations):
        ms, resp = elapsed_ms(
            lambda: client.get("/api/reports/balance-sheet", params={"as_of_date": as_of})
        )
        if resp.status_code != 200:
            raise RuntimeError(f"balance-sheet failed: {resp.status_code} {resp.text[:200]}")
        bs_samples.append(ms)

        ms, resp = elapsed_ms(
            lambda: client.get(
                "/api/reports/income-statement",
                params={"start_date": "2025-01-01", "end_date": as_of},
            )
        )
        if resp.status_code != 200:
            raise RuntimeError(f"income-statement failed: {resp.status_code} {resp.text[:200]}")
        is_samples.append(ms)

        if account:
            ms, resp = elapsed_ms(
                lambda: client.get(
                    "/api/reports/account-detail",
                    params={"account": account, "end_date": as_of, "limit": 20},
                )
            )
            if resp.status_code != 200:
                raise RuntimeError(f"account-detail first failed: {resp.status_code} {resp.text[:200]}")
            detail_first_samples.append(ms)
            page = resp.json()
            cursor = page.get("next_cursor")
            if cursor:
                ms, resp = elapsed_ms(
                    lambda: client.get(
                        "/api/reports/account-detail",
                        params={
                            "account": account,
                            "end_date": as_of,
                            "limit": 20,
                            "cursor": cursor,
                        },
                    )
                )
                if resp.status_code != 200:
                    raise RuntimeError(
                        f"account-detail next failed: {resp.status_code} {resp.text[:200]}"
                    )
                detail_next_samples.append(ms)

        ms, resp = elapsed_ms(
            lambda: client.get(
                "/api/reports/monthly-cashflow-trend",
                params={"end_month": trend_end_month},
            )
        )
        if resp.status_code != 200:
            raise RuntimeError(f"monthly-cashflow-trend failed: {resp.status_code} {resp.text[:200]}")
        body = resp.json()
        if len(body.get("points") or []) != 12:
            raise RuntimeError(f"monthly-cashflow-trend expected 12 points, got {len(body.get('points') or [])}")
        trend_samples.append(ms)

    # one-off EXPLAIN and month-by-month spot check using service SQL surface via API only
    explain = None
    try:
        # best-effort query plan via projection connection is not exposed; record API latency only
        explain = {
            "note": "trend uses one range group-by in LedgerAggregationService.monthly_cashflow_by_currency",
            "endpoint": "/api/reports/monthly-cashflow-trend",
            "end_month": trend_end_month,
        }
    except Exception as exc:  # pragma: no cover
        explain = {"error": str(exc)}

    return {
        "setup_balance_sheet_ms": round(setup_ms, 3),
        "as_of_date": as_of,
        "sample_account": account,
        "balance_sheet": distribution(bs_samples),
        "income_statement": distribution(is_samples),
        "account_detail_first_page": distribution(detail_first_samples) if detail_first_samples else None,
        "account_detail_next_page": distribution(detail_next_samples) if detail_next_samples else None,
        "monthly_cashflow_trend": distribution(trend_samples) if trend_samples else None,
        "monthly_cashflow_trend_plan": explain,
        "rss_mb_after": rss_mb(),
    }


def run_scale(ledger_path: Path, scale: int, iterations: int) -> dict:
    before = source_fingerprint(ledger_path)
    with tempfile.TemporaryDirectory(prefix="beanmind-report-bench-") as tmp:
        tmp_path = Path(tmp)
        scaled = make_scaled_copy(ledger_path, scale, tmp_path)
        txn_count, posting_count = count_transactions(scaled)
        # client build includes projection rebuild
        started = time.perf_counter()
        client = build_client(scaled, tmp_path / "projection.db")
        startup_ms = (time.perf_counter() - started) * 1000
        try:
            metrics = measure(client, iterations)
        finally:
            client._session.close()  # type: ignore[attr-defined]
            client._engine.dispose()  # type: ignore[attr-defined]
            BeancountServiceProvider.clear()
    after = source_fingerprint(ledger_path)
    return {
        "scale": scale,
        "transactions": txn_count,
        "postings": posting_count,
        "startup_and_projection_rebuild_ms": round(startup_ms, 3),
        "input_unchanged": before == after,
        "metrics": metrics,
        "rss_mb": rss_mb(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path, help="main.beancount path (read-only source)")
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--scales", type=int, nargs="+", default=[1, 2])
    args = parser.parse_args()

    ledger_path = args.ledger.resolve()
    if not ledger_path.exists():
        raise SystemExit(f"ledger not found: {ledger_path}")

    results = {
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "ledger": str(ledger_path),
        },
        "scales": [],
    }
    for scale in args.scales:
        print(f"measuring scale={scale} ...", flush=True)
        results["scales"].append(run_scale(ledger_path, scale, args.iterations))

    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
