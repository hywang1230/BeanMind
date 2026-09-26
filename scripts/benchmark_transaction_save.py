#!/usr/bin/env python3
"""隔离合成账本保存基准；真实 API/依赖/磁盘 SQLite，不接受真实账本输入。

默认使用初始化模板的 auto_accounts 插件；无插件对照可传 --plugin-mode none。
删除场景删除本轮新增的稳定 ID 交易（文件尾部），不代表历史派生 ID 的前部删除。
例如：python scripts/benchmark_transaction_save.py --sizes 1000 5000 10000 20000
每规模在独立子进程运行，backend 导入之前覆盖所有数据路径并关闭外部服务。
SQL 指标是 DBAPI 执行次数（executemany 计一次），并非影响行数。
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time
import uuid


def distribution(samples):
    ordered = sorted(samples)
    return {
        "runs": len(ordered),
        "median": round(statistics.median(ordered), 3),
        "p95": round(ordered[math.ceil(len(ordered) * 0.95) - 1], 3),
        "max": round(ordered[-1], 3),
    }


def configure_isolation(root):
    os.environ.update({
        "DATA_DIR": str(root),
        "LEDGER_FILE": str(root / "ledger" / "main.beancount"),
        "DATABASE_FILE": str(root / "benchmark.db"),
        "LOG_DIR": str(root / "logs"),
        "SCHEDULER_ENABLED": "false", "LLM_ENABLED": "false",
        "LLM_BASE_URL": "", "LLM_API_KEY": "", "LLM_MODEL": "benchmark-disabled",
        "DEBUG": "false", "LOG_LEVEL": "ERROR",
    })


def generate_ledger(path, size, id_mode, plugin_mode="none"):
    path.parent.mkdir(parents=True, exist_ok=True)
    plugin = 'plugin "beancount.plugins.auto_accounts"\n' if plugin_mode == "auto_accounts" else ""
    path.write_text(
        plugin + 'option "operating_currency" "CNY"\n'
        '2025-01-01 open Assets:Cash CNY\n'
        '2025-01-01 open Expenses:Food CNY\n'
        'include "transactions_2025.beancount"\n', encoding="utf-8",
    )
    with (path.parent / "transactions_2025.beancount").open("w", encoding="utf-8") as handle:
        for index in range(size):
            handle.write(f'2025-02-01 * "Synthetic" "fixture-{index}" #benchmark ^fixture\n')
            if id_mode == "explicit" or (id_mode == "mixed" and index % 2 == 0):
                identifier = uuid.uuid5(uuid.NAMESPACE_URL, f"beanmind-benchmark:{index}").hex
                handle.write(f'  id: "{identifier}"\n')
            handle.write("  Expenses:Food  1.23 CNY\n  Assets:Cash  -1.23 CNY\n\n")


def compare_projection(actual_engine, expected_engine):
    """逐行比较全部业务列；仅忽略生成时间和子表自增主键。"""
    from sqlalchemy import select
    from backend.infrastructure.persistence.db.models import (
        LedgerTransaction, LedgerPosting, LedgerTag,
    )
    counts = {}
    with actual_engine.connect() as actual, expected_engine.connect() as expected:
        for model, order, excluded in (
            (LedgerTransaction, ("id",), {"created_at", "updated_at"}),
            (LedgerPosting, ("transaction_id", "sequence"), {"id"}),
            (LedgerTag, ("transaction_id", "tag"), {"id"}),
        ):
            columns = [col for col in model.__table__.columns if col.name not in excluded]
            statement = select(*columns).order_by(*(getattr(model, key) for key in order))
            actual_rows = actual.execute(statement).fetchall()
            expected_rows = expected.execute(statement).fetchall()
            if actual_rows != expected_rows:
                raise RuntimeError(f"full-rebuild mismatch: {model.__tablename__}")
            counts[model.__tablename__] = len(actual_rows)
    return {"matched": True, "compared_rows": counts}


def run_worker(size, iterations, id_mode, positions, plugin_mode="none"):
    with tempfile.TemporaryDirectory(prefix="beanmind-save-benchmark-") as directory:
        root = Path(directory).resolve()
        configure_isolation(root)
        # No backend import is permitted above isolation configuration.
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from sqlalchemy import create_engine, event
        from sqlalchemy.orm import sessionmaker
        from backend.config import settings
        from backend.config.dependencies import engine, SessionLocal
        from backend.infrastructure.persistence.db.models import Base, LedgerTransaction
        from backend.infrastructure.persistence.ledger_projection import LedgerProjectionService
        from backend.interfaces.api.transaction import router
        from backend.services.currency_catalog import CurrencyCatalogService

        generate_ledger(settings.LEDGER_FILE, size, id_mode, plugin_mode)
        Base.metadata.create_all(engine)
        with SessionLocal() as session:
            CurrencyCatalogService(session).ensure_seeded()
            LedgerProjectionService(session, settings.LEDGER_FILE).rebuild_all()
        app = FastAPI()
        app.include_router(router)  # Real dependencies; each HTTP request owns its session.
        sql_counts = Counter()

        def count_sql(connection, cursor, statement, parameters, context, executemany):
            verb = statement.lstrip().split(None, 1)[0].upper()
            if verb in {"INSERT", "UPDATE", "DELETE", "SELECT"}:
                sql_counts[verb] += 1

        event.listen(engine, "before_cursor_execute", count_sql)
        payload = {
            "date": "2025-02-01", "description": "synthetic-save", "tags": ["benchmark"],
            "links": ["saved"], "postings": [
                {"account": "Expenses:Food", "amount": "1.23", "currency": "CNY"},
                {"account": "Assets:Cash", "amount": "-1.23", "currency": "CNY"},
            ],
        }
        results = {}
        try:
            with TestClient(app) as client:
                def save(method, url, body):
                    sql_counts.clear()
                    started = time.perf_counter()
                    response = client.request(method, url, json=body)
                    elapsed = (time.perf_counter() - started) * 1000
                    counts = dict(sql_counts)
                    if response.status_code not in (200, 201):
                        # Never print response bodies, SQL parameters or ledger contents.
                        raise RuntimeError(f"save API status {response.status_code}")
                    return elapsed, counts, response.json()

                _, _, warm = save("POST", "/api/transactions", payload)
                save("PUT", f'/api/transactions/{warm["id"]}', {"description": "warm-edit"})
                save("DELETE", f'/api/transactions/{warm["id"]}', None)
                created_ids = []
                scenarios = ["create"] + [f"edit_{position}" for position in positions] + ["delete"]
                indices = {"beginning": 0, "middle": size // 2, "end": size - 1}
                for scenario in scenarios:
                    elapsed_samples, sql_samples = [], []
                    for iteration in range(iterations):
                        if scenario == "create":
                            method, url, body = "POST", "/api/transactions", payload
                        elif scenario == "delete":
                            method, url, body = "DELETE", f"/api/transactions/{created_ids[iteration]}", None
                        else:
                            # Resolve again: legacy IDs can change when preceding source lines move.
                            position = scenario.removeprefix("edit_")
                            with SessionLocal() as session:
                                # Visit neighbouring originals so historical ID edits remain represented.
                                offset = -iteration if position == "end" else iteration
                                index = (indices[position] + offset) % size
                                # Exact prefix boundary avoids fixture-1 matching fixture-10.
                                prefix = f"fixture-{index}"
                                target = session.query(LedgerTransaction.id).filter(
                                    (LedgerTransaction.narration == prefix)
                                    | LedgerTransaction.narration.like(prefix + ":%")
                                ).one()[0]
                            method, url = "PUT", f"/api/transactions/{target}"
                            body = {"description": f"{prefix}:edit-{iteration}"}
                        elapsed, counts, response = save(method, url, body)
                        if scenario == "create":
                            created_ids.append(response["id"])
                        elapsed_samples.append(elapsed)
                        sql_samples.append(counts)
                    results[scenario] = {
                        "total_ms": distribution(elapsed_samples),
                        "sql_executions": {
                            verb: distribution([sample.get(verb, 0) for sample in sql_samples])
                            for verb in ("INSERT", "DELETE", "UPDATE", "SELECT")
                        },
                    }
            event.remove(engine, "before_cursor_execute", count_sql)
            expected_engine = create_engine(
                f"sqlite:///{root / 'full-rebuild.db'}", connect_args={"check_same_thread": False}
            )
            try:
                Base.metadata.create_all(expected_engine)
                with sessionmaker(bind=expected_engine, autoflush=False)() as session:
                    LedgerProjectionService(session, settings.LEDGER_FILE).rebuild_all()
                consistency = compare_projection(engine, expected_engine)
            finally:
                expected_engine.dispose()
            return {"initial_transactions": size, "id_mode": id_mode, "plugin_mode": plugin_mode,
                    "delete_targets": "created stable IDs at file end",
                    "iterations": iterations, "scenarios": results, "consistency": consistency}
        finally:
            engine.dispose()


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", nargs="+", type=positive_int, default=[1000, 5000, 10000, 20000])
    parser.add_argument("--iterations", type=positive_int, default=30)
    parser.add_argument("--id-mode", choices=["explicit", "mixed", "legacy"], default="explicit")
    parser.add_argument("--plugin-mode", choices=["none", "auto_accounts"], default="auto_accounts")
    parser.add_argument("--edit-positions", nargs="+", choices=["beginning", "middle", "end"],
                        default=["beginning", "middle", "end"])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.worker:
            result = run_worker(args.sizes[0], args.iterations, args.id_mode, args.edit_positions, args.plugin_mode)
        else:
            cases = []
            for size in args.sizes:
                completed = subprocess.run(
                    [sys.executable, str(Path(__file__).resolve()), "--worker", "--sizes", str(size),
                     "--iterations", str(args.iterations), "--id-mode", args.id_mode,
                     "--plugin-mode", args.plugin_mode, "--edit-positions", *args.edit_positions],
                    capture_output=True, text=True, check=False,
                )
                if completed.returncode:
                    raise RuntimeError(f"isolated worker failed for size {size}")
                cases.append(json.loads(completed.stdout))
            result = {
                "synthetic_only": True, "database": "temporary disk SQLite",
                "api_dependencies": "production, one session per request",
                "environment": {"python": platform.python_version(), "platform": platform.platform()},
                "p95_method": "nearest-rank", "sql_unit": "DBAPI executions, not affected rows",
                "timing_scope": "total HTTP request; nested phases not instrumented", "cases": cases,
            }
        output = json.dumps(result, ensure_ascii=False, indent=2)
        if args.output:
            args.output.write_text(output + "\n", encoding="utf-8")
        print(output)
        return 0
    except Exception as error:
        print(f"Save benchmark failed ({type(error).__name__}). No report produced.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
