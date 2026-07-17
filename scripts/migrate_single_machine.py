#!/usr/bin/env python3
"""预览或清理单机化后不再使用的 SQLite 元数据表。"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path


REMOVED_TABLES = (
    "users",
    "sync_logs",
    "backup_history",
    "ai_action_audits",
    "ai_agent_invocations",
    "ai_pending_actions",
    "ai_sessions",
    "ai_skill_invocations",
    "ai_tool_invocations",
    "ai_user_preferences",
    "chat_messages",
    "chat_sessions",
    "transaction_metadata",
    "system_config",
    "budget_cycles",
    "budget_items",
    "budgets",
    "monthly_reports",
    "monthly_reports_legacy",
)
PRESERVED_TABLES = (
    "ledger_index_files",
    "ledger_transactions",
    "ledger_postings",
    "ledger_tags",
    "monthly_budgets",
    "monthly_budget_items",
    "monthly_reviews",
    "recurring_rules",
    "recurring_executions",
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def connect(path: Path, readonly: bool) -> sqlite3.Connection:
    if readonly:
        database = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
        database.execute("PRAGMA query_only=ON")
        return database
    return sqlite3.connect(path)


def table_counts(connection: sqlite3.Connection, names: tuple[str, ...]) -> dict[str, int]:
    existing = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    return {
        name: connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        for name in names
        if name in existing
    }


def table_columns(connection: sqlite3.Connection, name: str) -> list[str]:
    return [row[1] for row in connection.execute(f'PRAGMA table_info("{name}")')]


def pending_schema_changes(connection: sqlite3.Connection) -> list[str]:
    changes = []
    if "user_id" in table_columns(connection, "recurring_rules"):
        changes.append("recurring_rules:remove_user_id")
    return changes


def checkpoint_preview(path: Path | None) -> dict | None:
    if path is None:
        return None
    return {
        "path": str(path.resolve()),
        "exists": path.is_file(),
        "bytes": path.stat().st_size if path.is_file() else 0,
        "sha256": digest(path) if path.is_file() else None,
    }


def preview(path: Path, checkpoint: Path | None = None) -> dict:
    before = digest(path)
    checkpoint_before = checkpoint_preview(checkpoint)
    with connect(path, readonly=True) as connection:
        report = {
            "database": str(path.resolve()),
            "sha256": before,
            "remove": table_counts(connection, REMOVED_TABLES),
            "preserve": table_counts(connection, PRESERVED_TABLES),
            "schema_changes": pending_schema_changes(connection),
            "checkpoint": checkpoint_before,
        }
    if digest(path) != before:
        raise RuntimeError("只读预览期间数据库发生变化")
    if checkpoint_preview(checkpoint) != checkpoint_before:
        raise RuntimeError("只读预览期间 checkpoint 发生变化")
    return report


def migrate_recurring_rules(connection: sqlite3.Connection) -> None:
    if "user_id" not in table_columns(connection, "recurring_rules"):
        return
    connection.execute(
        """
        CREATE TABLE recurring_rules_single_machine (
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
    connection.execute(
        """
        INSERT INTO recurring_rules_single_machine (
            name, frequency, frequency_config, transaction_template,
            start_date, end_date, is_active, id, created_at, updated_at
        )
        SELECT name, frequency, frequency_config, transaction_template,
               start_date, end_date, is_active, id, created_at, updated_at
        FROM recurring_rules
        """
    )
    connection.execute('DROP TABLE "recurring_rules"')
    connection.execute(
        'ALTER TABLE "recurring_rules_single_machine" RENAME TO "recurring_rules"'
    )
    connection.execute(
        'CREATE INDEX "idx_recurring_rules_active" ON "recurring_rules" ("is_active")'
    )


def apply(
    path: Path,
    backup: Path,
    fail_after_drop: bool = False,
    checkpoint: Path | None = None,
    checkpoint_backup: Path | None = None,
) -> dict:
    if not backup.is_file():
        raise ValueError("必须提供可读取的外部数据库备份")
    source_preview = preview(path, checkpoint)
    backup_preview = preview(backup)
    if (
        source_preview["remove"] != backup_preview["remove"]
        or source_preview["preserve"] != backup_preview["preserve"]
        or source_preview["schema_changes"] != backup_preview["schema_changes"]
    ):
        raise ValueError("外部备份与源数据库表计数不一致")
    if checkpoint is not None and source_preview["checkpoint"]["exists"]:
        if checkpoint_backup is None or not checkpoint_backup.is_file():
            raise ValueError("清理 checkpoint 必须提供可读取的外部备份")
        if digest(checkpoint) != digest(checkpoint_backup):
            raise ValueError("checkpoint 外部备份与源文件校验和不一致")
    with connect(path, readonly=False) as connection:
        before_preserved = table_counts(connection, PRESERVED_TABLES)
        try:
            connection.execute("BEGIN IMMEDIATE")
            for name in source_preview["remove"]:
                connection.execute(f'DROP TABLE "{name}"')
            migrate_recurring_rules(connection)
            if fail_after_drop:
                raise RuntimeError("故障注入")
            after_preserved = table_counts(connection, PRESERVED_TABLES)
            if after_preserved != before_preserved:
                raise RuntimeError("保留表核对失败")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    if checkpoint is not None and checkpoint.is_file():
        checkpoint.unlink()
    return preview(path, checkpoint)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--checkpoint-backup", type=Path)
    args = parser.parse_args()
    if args.apply:
        if args.backup is None:
            parser.error("--apply 必须同时提供 --backup")
        result = apply(
            args.database,
            args.backup,
            checkpoint=args.checkpoint,
            checkpoint_backup=args.checkpoint_backup,
        )
    else:
        result = preview(args.database, args.checkpoint)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
