from __future__ import annotations

import shutil
import sqlite3
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str((Path(__file__).parents[1] / "scripts").resolve()))

from generate_test_ledger import generate  # noqa: E402
from migrate_v3 import apply, fingerprint, preview  # noqa: E402


LEDGER = Path("tests/fixtures/ledger_projection/main.beancount")


def create_main_database(path: Path, *, orphan_execution: bool = False) -> None:
    with sqlite3.connect(path) as database:
        database.executescript(
            """
            CREATE TABLE users (id TEXT PRIMARY KEY);
            CREATE TABLE sync_logs (id TEXT PRIMARY KEY);
            CREATE TABLE transaction_metadata (id TEXT PRIMARY KEY);
            CREATE TABLE budgets (id TEXT PRIMARY KEY);
            CREATE TABLE budget_items (id TEXT PRIMARY KEY, budget_id TEXT);
            CREATE TABLE recurring_rules (
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                frequency TEXT NOT NULL,
                frequency_config TEXT,
                transaction_template TEXT NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE,
                is_active BOOLEAN NOT NULL,
                id TEXT PRIMARY KEY,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            );
            CREATE TABLE recurring_executions (
                rule_id TEXT NOT NULL,
                executed_date DATE NOT NULL,
                transaction_id TEXT,
                status TEXT NOT NULL,
                id TEXT PRIMARY KEY,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY(rule_id) REFERENCES recurring_rules(id) ON DELETE CASCADE
            );
            INSERT INTO users VALUES ('user');
            INSERT INTO sync_logs VALUES ('sync');
            INSERT INTO transaction_metadata VALUES ('legacy-transaction-metadata');
            INSERT INTO budgets VALUES ('legacy-budget');
            INSERT INTO budget_items VALUES ('legacy-budget-item', 'legacy-budget');
            INSERT INTO recurring_rules VALUES (
                'user', '房租', 'MONTHLY', '{"month_days":[1]}',
                '{"description":"房租","postings":[]}', '2025-01-01', NULL,
                1, 'rule-1', '2025-01-01', '2025-01-01'
            );
            """
        )
        database.execute(
            "INSERT INTO recurring_executions VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "missing-rule" if orphan_execution else "rule-1",
                "2025-01-01",
                "transaction-1",
                "SUCCESS",
                "execution-1",
                "2025-01-01",
                "2025-01-01",
            ),
        )


def copy_backup(database: Path, backup: Path) -> None:
    shutil.copy2(database, backup)


def test_test_ledger_generation_is_deterministic(tmp_path: Path) -> None:
    first = generate(LEDGER, tmp_path / "first", 2)
    second = generate(LEDGER, tmp_path / "second", 2)
    assert first["transactions"] == second["transactions"]
    assert first["postings"] == second["postings"]
    assert first["fingerprint"] == second["fingerprint"]


def test_preview_is_read_only_and_covers_main_schema(tmp_path: Path) -> None:
    database = tmp_path / "beanmind.db"
    checkpoint = tmp_path / "ai_checkpoints.db"
    create_main_database(database)
    checkpoint.write_bytes(b"checkpoint")
    database_before = database.read_bytes()
    ledger_before = {
        path["path"]: path["sha256"]
        for path in preview(database, LEDGER)["ledger"]["files"]
    }

    report = preview(database, LEDGER, checkpoint)

    assert report["state"] == "PENDING"
    assert report["remove"] == {
        "transaction_metadata": 1,
        "sync_logs": 1,
        "users": 1,
    }
    assert report["drop_budgets"] == {"budget_items": 1, "budgets": 1}
    assert report["recurring"] == {
        "rules": 1,
        "executions": 1,
        "rule_ids": ["rule-1"],
        "execution_ids": ["execution-1"],
        "execution_links": [("execution-1", "rule-1")],
        "orphan_rule_ids": [],
        "has_user_id": True,
    }
    assert report["ledger"]["transactions"] > 0
    assert report["ledger"]["postings"] > report["ledger"]["transactions"]
    assert database.read_bytes() == database_before
    assert {
        path["path"]: path["sha256"] for path in report["ledger"]["files"]
    } == ledger_before
    assert checkpoint.read_bytes() == b"checkpoint"


def test_apply_requires_budget_confirmation_and_matching_backup(tmp_path: Path) -> None:
    database = tmp_path / "beanmind.db"
    backup = tmp_path / "backup.db"
    create_main_database(database)
    copy_backup(database, backup)

    with pytest.raises(ValueError, match="confirm-drop-budgets"):
        apply(database, LEDGER, backup, confirm_drop_budgets=False)

    backup.write_bytes(b"not-the-source-database")
    with pytest.raises(ValueError, match="备份.*不一致"):
        apply(database, LEDGER, backup, confirm_drop_budgets=True)

    assert preview(database, LEDGER)["state"] == "PENDING"


def test_nonempty_wal_blocks_migration(tmp_path: Path) -> None:
    database = tmp_path / "beanmind.db"
    backup = tmp_path / "backup.db"
    create_main_database(database)
    copy_backup(database, backup)
    Path(f"{database}-wal").write_bytes(b"uncheckpointed-data")

    report = preview(database, LEDGER)
    assert report["database_sidecars"]["-wal"]["bytes"] > 0
    with pytest.raises(ValueError, match="SQLite WAL"):
        apply(database, LEDGER, backup, confirm_drop_budgets=True)
    assert preview(database, LEDGER)["recurring"]["has_user_id"] is True


def test_apply_preserves_recurring_and_rebuilds_projection(tmp_path: Path) -> None:
    database = tmp_path / "beanmind.db"
    backup = tmp_path / "backup.db"
    checkpoint = tmp_path / "ai_checkpoints.db"
    checkpoint_backup = tmp_path / "ai_checkpoints.backup.db"
    create_main_database(database)
    checkpoint.write_bytes(b"checkpoint")
    copy_backup(database, backup)
    copy_backup(checkpoint, checkpoint_backup)
    ledger_before = fingerprint(LEDGER)
    expected = preview(database, LEDGER)

    result = apply(
        database,
        LEDGER,
        backup,
        confirm_drop_budgets=True,
        checkpoint=checkpoint,
        checkpoint_backup=checkpoint_backup,
    )

    assert result["migrated"] is True
    assert result["verification"]["projection"] == {
        "transactions": expected["ledger"]["transactions"],
        "postings": expected["ledger"]["postings"],
    }
    assert result["verification"]["recurring"] == {"rules": 1, "executions": 1}
    assert result["verification"]["budgets"] == {
        "monthly_budgets": 0,
        "monthly_budget_items": 0,
    }
    assert fingerprint(LEDGER) == ledger_before
    assert not checkpoint.exists()

    with sqlite3.connect(database) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        columns = [
            row[1] for row in connection.execute("PRAGMA table_info(recurring_rules)")
        ]
        assert "user_id" not in columns
        assert connection.execute("SELECT name FROM recurring_rules").fetchone() == ("房租",)
        assert connection.execute(
            "SELECT id, rule_id, transaction_id FROM recurring_executions"
        ).fetchone() == ("execution-1", "rule-1", "transaction-1")
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert {"monthly_budgets", "monthly_budget_items"} <= tables
        assert not ({"budgets", "budget_items", "users", "transaction_metadata"} & tables)


def test_structural_failure_rolls_back_all_changes(tmp_path: Path) -> None:
    database = tmp_path / "beanmind.db"
    backup = tmp_path / "backup.db"
    create_main_database(database)
    copy_backup(database, backup)

    with pytest.raises(RuntimeError, match="故障注入"):
        apply(
            database,
            LEDGER,
            backup,
            confirm_drop_budgets=True,
            fail_after_drop=True,
        )

    report = preview(database, LEDGER)
    assert report["state"] == "PENDING"
    assert report["recurring"]["has_user_id"] is True
    assert report["recurring"]["execution_links"] == [("execution-1", "rule-1")]
    assert report["drop_budgets"] == {"budget_items": 1, "budgets": 1}


def test_orphan_recurring_execution_blocks_migration(tmp_path: Path) -> None:
    database = tmp_path / "beanmind.db"
    backup = tmp_path / "backup.db"
    create_main_database(database, orphan_execution=True)
    copy_backup(database, backup)

    report = preview(database, LEDGER)
    assert report["recurring"]["orphan_rule_ids"] == ["missing-rule"]
    with pytest.raises(ValueError, match="孤儿关联"):
        apply(database, LEDGER, backup, confirm_drop_budgets=True)
    assert preview(database, LEDGER)["recurring"]["has_user_id"] is True


def test_invalid_ledger_blocks_before_database_write(tmp_path: Path) -> None:
    database = tmp_path / "beanmind.db"
    backup = tmp_path / "backup.db"
    ledger = tmp_path / "invalid.beancount"
    create_main_database(database)
    copy_backup(database, backup)
    ledger.write_text("2025-99-99 * invalid\n", encoding="utf-8")
    database_before = database.read_bytes()

    report = preview(database, ledger)
    assert report["ledger"]["errors"]
    with pytest.raises(ValueError, match="解析错误"):
        apply(database, ledger, backup, confirm_drop_budgets=True)
    assert database.read_bytes() == database_before


def test_completed_migration_is_idempotent_and_preserves_new_budget(tmp_path: Path) -> None:
    database = tmp_path / "beanmind.db"
    backup = tmp_path / "backup.db"
    create_main_database(database)
    copy_backup(database, backup)
    apply(database, LEDGER, backup, confirm_drop_budgets=True)

    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO monthly_budgets(month, id, created_at, updated_at) "
            "VALUES ('2026-07', 'new-budget', 'now', 'now')"
        )
    current = preview(database, LEDGER)
    assert current["state"] == "CURRENT"
    assert current["drop_budgets"] == {}

    result = apply(database, LEDGER, backup, confirm_drop_budgets=False)
    assert result["migrated"] is False
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT id FROM monthly_budgets"
        ).fetchall() == [("new-budget",)]
