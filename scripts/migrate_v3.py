#!/usr/bin/env python3
"""BeanMind 3.0.0 发布迁移：预览、保留周期记账、重建流水投影。"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from beancount import loader  # noqa: E402
from beancount.core.data import Transaction as BeancountTransaction  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from backend.infrastructure.persistence.db.models import (  # noqa: E402
    Base,
    LedgerPosting,
    LedgerTransaction,
    MonthlyBudget,
    MonthlyBudgetItem,
    RecurringExecution,
    RecurringRule,
)
from backend.infrastructure.persistence.ledger_projection import (  # noqa: E402
    LedgerProjectionService,
)


MIGRATION_ID = "beanmind-v3"
MIGRATION_TABLE = "schema_migrations"

BUDGET_TABLES = (
    "budget_cycles",
    "budget_items",
    "budgets",
    "monthly_budget_items",
    "monthly_budgets",
)
REMOVED_TABLES = (
    "transaction_metadata",
    "monthly_reports_legacy",
    "monthly_reports",
    "chat_messages",
    "chat_sessions",
    "ai_action_audits",
    "ai_agent_invocations",
    "ai_pending_actions",
    "ai_sessions",
    "ai_skill_invocations",
    "ai_tool_invocations",
    "ai_user_preferences",
    "backup_history",
    "sync_logs",
    "system_config",
    "users",
)
PROJECTION_TABLES = (
    "ledger_postings",
    "ledger_tags",
    "ledger_transactions",
    "ledger_index_files",
)
RECURRING_RULE_COLUMNS = (
    "name",
    "frequency",
    "frequency_config",
    "transaction_template",
    "start_date",
    "end_date",
    "is_active",
    "id",
    "created_at",
    "updated_at",
)


def fingerprint(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def file_summary(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    resolved = path.resolve()
    exists = resolved.is_file()
    return {
        "path": str(resolved),
        "exists": exists,
        "bytes": resolved.stat().st_size if exists else 0,
        "sha256": fingerprint(resolved) if exists else None,
    }


def sqlite_sidecars(path: Path) -> dict[str, dict[str, Any]]:
    return {
        suffix: file_summary(Path(f"{path}{suffix}"))
        for suffix in ("-wal", "-shm")
    }


def connect(path: Path, *, readonly: bool) -> sqlite3.Connection:
    if readonly:
        database = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
        database.execute("PRAGMA query_only=ON")
    else:
        database = sqlite3.connect(path)
    database.row_factory = sqlite3.Row
    return database


def table_names(database: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in database.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }


def table_columns(database: sqlite3.Connection, name: str) -> list[str]:
    if name not in table_names(database):
        return []
    return [row[1] for row in database.execute(f'PRAGMA table_info("{name}")')]


def table_counts(
    database: sqlite3.Connection, names: tuple[str, ...]
) -> dict[str, int]:
    existing = table_names(database)
    return {
        name: int(database.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0])
        for name in names
        if name in existing
    }


def migration_applied(database: sqlite3.Connection) -> bool:
    if MIGRATION_TABLE not in table_names(database):
        return False
    return (
        database.execute(
            f'SELECT 1 FROM "{MIGRATION_TABLE}" WHERE id = ?', (MIGRATION_ID,)
        ).fetchone()
        is not None
    )


def recurring_snapshot(database: sqlite3.Connection) -> dict[str, Any]:
    existing = table_names(database)
    rules = (
        [dict(row) for row in database.execute("SELECT * FROM recurring_rules ORDER BY id")]
        if "recurring_rules" in existing
        else []
    )
    executions = (
        [
            dict(row)
            for row in database.execute("SELECT * FROM recurring_executions ORDER BY id")
        ]
        if "recurring_executions" in existing
        else []
    )
    rule_ids = {str(row["id"]) for row in rules}
    orphan_rule_ids = sorted(
        {
            str(row["rule_id"])
            for row in executions
            if str(row["rule_id"]) not in rule_ids
        }
    )
    return {
        "rules": len(rules),
        "executions": len(executions),
        "rule_ids": sorted(rule_ids),
        "execution_ids": sorted(str(row["id"]) for row in executions),
        "execution_links": sorted(
            (str(row["id"]), str(row["rule_id"])) for row in executions
        ),
        "orphan_rule_ids": orphan_rule_ids,
        "has_user_id": "user_id" in table_columns(database, "recurring_rules"),
    }


def ledger_summary(ledger_path: Path) -> dict[str, Any]:
    ledger = ledger_path.resolve()
    before = fingerprint(ledger)
    started = time.perf_counter()
    entries, errors, options = loader.load_file(str(ledger))
    transactions = [
        entry for entry in entries if isinstance(entry, BeancountTransaction)
    ]
    files = {ledger}
    files.update(
        Path(path).resolve()
        for path in options.get("include", [])
        if Path(path).is_file()
    )
    files.update(
        Path(entry.meta["filename"]).resolve()
        for entry in entries
        if getattr(entry, "meta", None) and entry.meta.get("filename")
    )
    result = {
        "entrypoint": str(ledger),
        "entrypoint_sha256": before,
        "transactions": len(transactions),
        "postings": sum(len(entry.postings) for entry in transactions),
        "files": [
            {"path": str(path), "sha256": fingerprint(path)}
            for path in sorted(files)
        ],
        "errors": [str(error) for error in errors],
        "elapsed_seconds": round(time.perf_counter() - started, 6),
    }
    if fingerprint(ledger) != before:
        raise RuntimeError("只读解析期间 Beancount 入口账本发生变化")
    return result


def preview(
    database_path: Path,
    ledger_path: Path,
    checkpoint: Path | None = None,
) -> dict[str, Any]:
    database_before = fingerprint(database_path)
    checkpoint_before = file_summary(checkpoint)
    ledger = ledger_summary(ledger_path)
    with connect(database_path, readonly=True) as database:
        applied = migration_applied(database)
        recurring = recurring_snapshot(database)
        report = {
            "migration": MIGRATION_ID,
            "state": "CURRENT" if applied else "PENDING",
            "database": file_summary(database_path),
            "database_sidecars": sqlite_sidecars(database_path),
            "ledger": ledger,
            "recurring": recurring,
            "drop_budgets": {} if applied else table_counts(database, BUDGET_TABLES),
            "remove": {} if applied else table_counts(database, REMOVED_TABLES),
            "rebuild_projection": False
            if applied
            else bool(table_counts(database, PROJECTION_TABLES)),
            "checkpoint": checkpoint_before,
        }
    if fingerprint(database_path) != database_before:
        raise RuntimeError("只读预览期间 SQLite 数据库发生变化")
    if file_summary(checkpoint) != checkpoint_before:
        raise RuntimeError("只读预览期间 checkpoint 发生变化")
    return report


def _drop_tables(database: sqlite3.Connection, names: tuple[str, ...]) -> None:
    existing = table_names(database)
    for name in names:
        if name in existing:
            database.execute(f'DROP TABLE "{name}"')


def _migrate_recurring_rules(database: sqlite3.Connection) -> None:
    columns = table_columns(database, "recurring_rules")
    if not columns or "user_id" not in columns:
        return
    missing = sorted(set(RECURRING_RULE_COLUMNS) - set(columns))
    if missing:
        raise ValueError(f"recurring_rules 结构未知，缺少列: {', '.join(missing)}")
    database.execute('DROP TABLE IF EXISTS "recurring_rules_v3"')
    database.execute(
        """
        CREATE TABLE recurring_rules_v3 (
            name VARCHAR(100) NOT NULL,
            frequency VARCHAR(50) NOT NULL,
            frequency_config TEXT,
            transaction_template TEXT NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE,
            is_active BOOLEAN NOT NULL,
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        )
        """
    )
    selected = ", ".join(f'"{name}"' for name in RECURRING_RULE_COLUMNS)
    database.execute(
        f"INSERT INTO recurring_rules_v3 ({selected}) "
        f"SELECT {selected} FROM recurring_rules"
    )
    database.execute('DROP TABLE "recurring_rules"')
    database.execute(
        'ALTER TABLE "recurring_rules_v3" RENAME TO "recurring_rules"'
    )
    database.execute(
        'CREATE INDEX "idx_recurring_rules_active" '
        'ON "recurring_rules" ("is_active")'
    )


def _structural_migration(
    database_path: Path,
    expected_recurring: dict[str, Any],
    expected_database_sha256: str,
    *,
    fail_after_drop: bool,
) -> None:
    with connect(database_path, readonly=False) as database:
        database.execute("PRAGMA foreign_keys=OFF")
        try:
            database.execute("BEGIN IMMEDIATE")
            if fingerprint(database_path) != expected_database_sha256:
                raise RuntimeError("预览后 SQLite 数据库发生变化，拒绝迁移")
            _migrate_recurring_rules(database)
            _drop_tables(database, BUDGET_TABLES)
            _drop_tables(database, REMOVED_TABLES)
            _drop_tables(database, PROJECTION_TABLES)
            if fail_after_drop:
                raise RuntimeError("故障注入：结构迁移回滚")

            after = recurring_snapshot(database)
            for key in (
                "rules",
                "executions",
                "rule_ids",
                "execution_ids",
                "execution_links",
            ):
                if after[key] != expected_recurring[key]:
                    raise RuntimeError(f"周期记账核对失败: {key}")
            if after["has_user_id"]:
                raise RuntimeError("周期规则 user_id 未移除")
            if after["orphan_rule_ids"]:
                raise RuntimeError("周期执行存在孤儿关联")
            foreign_key_errors = database.execute("PRAGMA foreign_key_check").fetchall()
            if foreign_key_errors:
                raise RuntimeError(f"数据库外键核对失败: {foreign_key_errors[:10]}")
            database.commit()
        except Exception:
            database.rollback()
            raise
        finally:
            database.execute("PRAGMA foreign_keys=ON")


def _create_schema_and_rebuild_projection(
    database_path: Path, ledger_path: Path, expected_ledger: dict[str, Any]
) -> dict[str, Any]:
    engine = create_engine(f"sqlite:///{database_path}")
    try:
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        try:
            projection = LedgerProjectionService(session, ledger_path)
            rebuild = projection.full_rebuild()
            consistency = projection.check_consistency()
            actual = {
                "transactions": session.query(LedgerTransaction).count(),
                "postings": session.query(LedgerPosting).count(),
            }
            expected = {
                "transactions": expected_ledger["transactions"],
                "postings": expected_ledger["postings"],
            }
            if actual != expected:
                raise RuntimeError(
                    f"流水投影数量核对失败: expected={expected}, actual={actual}"
                )
            if session.query(MonthlyBudget).count() != 0:
                raise RuntimeError("迁移后月度预算主表不为空")
            if session.query(MonthlyBudgetItem).count() != 0:
                raise RuntimeError("迁移后月度预算分类表不为空")
            recurring = {
                "rules": session.query(RecurringRule).count(),
                "executions": session.query(RecurringExecution).count(),
            }
            return {
                "rebuild": rebuild,
                "consistency": consistency,
                "projection": actual,
                "recurring": recurring,
                "budgets": {"monthly_budgets": 0, "monthly_budget_items": 0},
            }
        finally:
            session.close()
    finally:
        engine.dispose()


def _record_migration(database_path: Path) -> None:
    with connect(database_path, readonly=False) as database:
        database.execute(
            f"""
            CREATE TABLE IF NOT EXISTS "{MIGRATION_TABLE}" (
                id TEXT NOT NULL PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        database.execute(
            f'INSERT OR IGNORE INTO "{MIGRATION_TABLE}" (id) VALUES (?)',
            (MIGRATION_ID,),
        )
        database.commit()


def apply(
    database_path: Path,
    ledger_path: Path,
    backup: Path,
    *,
    confirm_drop_budgets: bool,
    checkpoint: Path | None = None,
    checkpoint_backup: Path | None = None,
    fail_after_drop: bool = False,
) -> dict[str, Any]:
    before = preview(database_path, ledger_path, checkpoint)
    if before["state"] == "CURRENT":
        return {"migrated": False, "preview": before}
    if before["ledger"]["errors"]:
        raise ValueError("Beancount 账本存在解析错误，拒绝迁移")
    if before["recurring"]["orphan_rule_ids"]:
        raise ValueError("周期执行存在孤儿关联，拒绝迁移")
    wal = before["database_sidecars"]["-wal"]
    if wal["exists"] and wal["bytes"]:
        raise ValueError("检测到非空 SQLite WAL，请停止服务并完成 checkpoint 后重试")
    if before["drop_budgets"] and not confirm_drop_budgets:
        raise ValueError("存在待丢弃预算表，必须显式传入 --confirm-drop-budgets")
    if not backup.is_file() or fingerprint(database_path) != fingerprint(backup):
        raise ValueError("外部数据库备份与迁移前源数据库不一致")
    if checkpoint is not None and checkpoint.is_file():
        if checkpoint_backup is None or not checkpoint_backup.is_file():
            raise ValueError("清理 checkpoint 必须提供可读取的外部备份")
        if fingerprint(checkpoint) != fingerprint(checkpoint_backup):
            raise ValueError("checkpoint 外部备份与源文件不一致")

    ledger_before = before["ledger"]["files"]
    _structural_migration(
        database_path,
        before["recurring"],
        before["database"]["sha256"],
        fail_after_drop=fail_after_drop,
    )
    verification = _create_schema_and_rebuild_projection(
        database_path, ledger_path, before["ledger"]
    )
    ledger_after = ledger_summary(ledger_path)
    if ledger_after["files"] != ledger_before:
        raise RuntimeError("迁移期间 Beancount 账本文件发生变化")
    if checkpoint is not None and checkpoint.is_file():
        checkpoint.unlink()
    _record_migration(database_path)
    after = preview(database_path, ledger_path, checkpoint)
    return {
        "migrated": True,
        "before": before,
        "verification": verification,
        "after": after,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="迁移 BeanMind 数据到 3.0.0")
    parser.add_argument("database", type=Path)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--confirm-drop-budgets", action="store_true")
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--checkpoint-backup", type=Path)
    args = parser.parse_args()
    if args.apply:
        if args.backup is None:
            parser.error("--apply 必须同时提供 --backup")
        result = apply(
            args.database,
            args.ledger,
            args.backup,
            confirm_drop_budgets=args.confirm_drop_budgets,
            checkpoint=args.checkpoint,
            checkpoint_backup=args.checkpoint_backup,
        )
    else:
        result = preview(args.database, args.ledger, args.checkpoint)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
