#!/usr/bin/env python3
"""只读评估旧流水链路与 SQLite 投影；所有数据库和扩容副本都在临时目录。"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import statistics
import tempfile
import time
import uuid
from collections import Counter
from pathlib import Path

from beancount import loader
from beancount.core.data import Transaction
from beancount.parser import parser, printer
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.infrastructure.persistence.beancount.beancount_service import BeancountService
from backend.infrastructure.persistence.beancount.repositories import TransactionRepositoryImpl
from backend.infrastructure.persistence.db.models import Base, LedgerTransaction
from backend.infrastructure.persistence.ledger_projection import (
    LedgerProjectionService,
    TransactionQueryService,
)
from backend.ai.llm_client import OpenAICompatibleClient
from backend.services.dashboard import DashboardService
from backend.services.ledger_aggregation import LedgerAggregationService
from backend.services.monthly_budget import MonthlyBudgetService
from backend.services.monthly_review import MonthlyReviewService
from backend.interfaces.api.transaction import (
    get_transaction_query_service,
    router as transaction_router,
)


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


def source_fingerprint(root: Path) -> dict[str, str]:
    return {
        str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.parent.rglob("*.beancount"))
    }


def make_scaled_copy(ledger_path: Path, scale: int, target_root: Path) -> Path:
    """在临时目录复制账本并按原交易分布扩容，不修改输入。"""
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
                    f"benchmark:{path.name}:{copy_number}:{entry.meta.get('lineno', 0)}",
                ).hex
                clone = entry._replace(meta=meta)
                additions.append(printer.format_entry(clone))
        if additions:
            with path.open("a", encoding="utf-8") as handle:
                handle.write("\n" + "\n".join(additions) + "\n")
    return copied_main


def representative_query_parameters(session) -> dict:
    """从实际分布选择一笔交易，生成可复现的单条件与组合查询集合。"""
    sample = (
        session.query(LedgerTransaction)
        .filter(LedgerTransaction.tags.any())
        .order_by(LedgerTransaction.date.desc(), LedgerTransaction.id.desc())
        .first()
    )
    if sample is None:
        sample = (
            session.query(LedgerTransaction)
            .order_by(LedgerTransaction.date.desc(), LedgerTransaction.id.desc())
            .first()
        )
    if sample is None:
        raise RuntimeError("账本不含可用于基准查询的交易")

    keyword = sample.payee or sample.narration
    account = sample.postings[0].account if sample.postings else None
    tag = sample.tags[0].tag if sample.tags else None
    year = sample.date.year
    parameters = {
        "first_page": {"limit": 20},
        "date_range": {
            "limit": 20,
            "start_date": f"{year}-01-01",
            "end_date": f"{year}-12-31",
        },
        "transaction_type": {
            "limit": 20,
            "transaction_type": sample.transaction_type,
        },
    }
    if keyword:
        parameters["keyword"] = {"limit": 20, "description": keyword}
    if account:
        parameters["account"] = {"limit": 20, "account": account}
    if tag:
        parameters["tags"] = {"limit": 20, "tags": [tag]}

    combined = dict(parameters["date_range"])
    combined["transaction_type"] = sample.transaction_type
    if keyword:
        combined["description"] = keyword
    if account:
        combined["account"] = account
    if tag:
        combined["tags"] = [tag]
    parameters["combined"] = combined
    return parameters


def request_api_page(client: TestClient, parameters: dict) -> dict:
    query_parameters = dict(parameters)
    if "tags" in query_parameters:
        query_parameters["tags"] = ",".join(query_parameters["tags"])
    response = client.get("/api/transactions", params=query_parameters)
    if response.status_code != 200:
        raise RuntimeError(f"流水 API 基准请求失败: {response.status_code} {response.text[:500]}")
    return response.json()


def benchmark(ledger_path: Path, iterations: int, scale: int) -> dict:
    original_fingerprint = source_fingerprint(ledger_path)
    with tempfile.TemporaryDirectory(prefix="beanmind-projection-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        effective_ledger = make_scaled_copy(ledger_path, scale, temp_dir)

        load_ms, loaded = elapsed_ms(lambda: loader.load_file(str(effective_ledger)))
        entries, errors, options = loaded
        if errors:
            raise RuntimeError("; ".join(str(error) for error in errors[:10]))
        transactions = [entry for entry in entries if isinstance(entry, Transaction)]
        if not transactions:
            raise RuntimeError("账本不含交易，无法执行流水基准")
        files = sorted({Path(path).resolve() for path in options.get("include", [])})
        total_bytes = sum(path.stat().st_size for path in files if path.exists())
        years = Counter(str(entry.date.year) for entry in transactions)

        database_path = temp_dir / "benchmark.db"
        engine = create_engine(
            f"sqlite:///{database_path}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        try:
            legacy_construct_ms, legacy_repository = elapsed_ms(
                lambda: TransactionRepositoryImpl(BeancountService(effective_ledger), session)
            )
            legacy_query_samples = [
                elapsed_ms(lambda: legacy_repository.find_by_keyword("a"))[0]
                for _ in range(iterations)
            ]
            legacy_reload_ms = elapsed_ms(legacy_repository.reload)[0]

            projection = LedgerProjectionService(session, effective_ledger)
            rebuild_ms, rebuild_result = elapsed_ms(projection.rebuild_all)
            unchanged_ms, _ = elapsed_ms(projection.ensure_current)
            refresh_candidates = [
                path
                for path in files
                if path != effective_ledger.resolve() and "transactions_" in path.name
            ]
            refresh_candidates = [
                path
                for path in refresh_candidates
                if all(isinstance(entry, Transaction) for entry in parser.parse_file(str(path))[0])
            ]
            refresh_ms = None
            if refresh_candidates:
                refresh_ms, _ = elapsed_ms(lambda: projection.refresh_file(refresh_candidates[0]))

            query = TransactionQueryService(session, effective_ledger)
            query_parameters = representative_query_parameters(session)
            query_results = {
                name: distribution(
                    [
                        elapsed_ms(lambda current=parameters: query.list_transactions(**current))[0]
                        for _ in range(iterations)
                    ]
                )
                for name, parameters in query_parameters.items()
            }
            app = FastAPI()
            app.include_router(transaction_router)
            app.dependency_overrides[get_transaction_query_service] = lambda: query
            with TestClient(app) as client:
                api_query_results = {
                    name: distribution(
                        [
                            elapsed_ms(
                                lambda current=parameters: request_api_page(client, current)
                            )[0]
                            for _ in range(iterations)
                        ]
                    )
                    for name, parameters in query_parameters.items()
                }
            page_ids = []
            cursor = None
            paging_samples = []
            while True:
                duration, page = elapsed_ms(
                    lambda current=cursor: query.list_transactions(limit=100, cursor=current)
                )
                paging_samples.append(duration)
                page_ids.extend(item["id"] for item in page["items"])
                if not page["has_more"]:
                    break
                cursor = page["next_cursor"]
            consistency = projection.check_consistency()
            latest_month = session.query(LedgerTransaction.date).order_by(
                LedgerTransaction.date.desc()
            ).first()[0].strftime("%Y-%m")
            aggregation = LedgerAggregationService(session, effective_ledger)
            budget_service = MonthlyBudgetService(session, aggregation)
            budget_service.save(
                latest_month,
                "CNY",
                [{"name": "支出", "account_pattern": "Expenses", "amount": "999999999"}],
            )
            beancount_service = BeancountService(effective_ledger)
            dashboard_service = DashboardService(
                session, aggregation, beancount_service, llm_enabled=False
            )
            review_service = MonthlyReviewService(
                session,
                aggregation,
                budget_service,
                OpenAICompatibleClient(
                    enabled=False,
                    base_url="",
                    api_key="",
                    model="benchmark-disabled",
                    timeout_seconds=1,
                ),
                beancount_service.get_operating_currency(),
            )
            core_queries = {
                "dashboard": distribution([
                    elapsed_ms(lambda: dashboard_service.get(latest_month))[0]
                    for _ in range(iterations)
                ]),
                "budget": distribution([
                    elapsed_ms(lambda: budget_service.get(latest_month, "CNY"))[0]
                    for _ in range(iterations)
                ]),
                "monthly_review_facts": distribution([
                    elapsed_ms(lambda: review_service.build_facts(latest_month))[0]
                    for _ in range(iterations)
                ]),
            }
            explain_plan = [
                row[-1]
                for row in session.connection().exec_driver_sql(
                    """
                    EXPLAIN QUERY PLAN
                    SELECT p.currency, decimal_sum(p.amount_text)
                    FROM ledger_postings p
                    JOIN ledger_transactions t ON t.id = p.transaction_id
                    WHERE t.date BETWEEN ? AND ?
                      AND (p.account = ? OR p.account LIKE ? ESCAPE '\\')
                    GROUP BY p.currency
                    """,
                    (f"{latest_month}-01", f"{latest_month}-31", "Expenses", "Expenses:%"),
                ).all()
            ]
            database_bytes = database_path.stat().st_size
        finally:
            session.close()
            engine.dispose()

    if source_fingerprint(ledger_path) != original_fingerprint:
        raise RuntimeError("输入账本在基准执行期间发生变化")
    return {
        "input": str(ledger_path.resolve()),
        "scale": scale,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "iterations": iterations,
        },
        "ledger": {
            "files": len(files),
            "transactions": len(transactions),
            "postings": sum(len(entry.postings) for entry in transactions),
            "years": dict(sorted(years.items())),
            "bytes": total_bytes,
        },
        "legacy": {
            "full_load_ms": round(load_ms, 3),
            "repository_construct_ms": round(legacy_construct_ms, 3),
            "keyword_query": distribution(legacy_query_samples),
            "write_followup_reload_proxy_ms": round(legacy_reload_ms, 3),
        },
        "projection": {
            "rebuild_ms": round(rebuild_ms, 3),
            "unchanged_startup_ms": round(unchanged_ms, 3),
            "single_file_refresh_ms": round(refresh_ms, 3) if refresh_ms is not None else None,
            "rebuild_result": rebuild_result,
            "database_bytes": database_bytes,
            "query_parameters": query_parameters,
            "queries": query_results,
            "api_queries": api_query_results,
            "api_p95_target_ms": 150,
            "api_p95_under_target": all(
                result["p95_ms"] < 150 for result in api_query_results.values()
            ),
            "continuous_paging": {
                **distribution(paging_samples),
                "rows": len(page_ids),
                "unique_rows": len(set(page_ids)),
            },
            "consistency": consistency,
            "core_queries": core_queries,
            "core_p95_target_ms": 300,
            "core_p95_under_target": all(
                result["p95_ms"] < 300 for result in core_queries.values()
            ),
            "aggregation_explain_plan": explain_plan,
        },
        "input_unchanged": True,
    }


def main() -> None:
    parser_ = argparse.ArgumentParser()
    parser_.add_argument("ledger", type=Path, help="main.beancount 路径")
    parser_.add_argument("--iterations", type=int, default=30)
    parser_.add_argument("--scale", type=int, default=1, choices=range(1, 5))
    args = parser_.parse_args()
    print(
        json.dumps(
            benchmark(args.ledger.resolve(), args.iterations, args.scale),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
