from __future__ import annotations

import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str((Path(__file__).parents[1] / "scripts").resolve()))

from generate_test_ledger import generate  # noqa: E402
from migrate_single_machine import apply, preview  # noqa: E402
from migrate_monthly_budgets import analyze  # noqa: E402
from migrate_budget_operating_currency import (  # noqa: E402
    analyze as analyze_operating_currency_budgets,
    apply as apply_operating_currency_budgets,
)


def create_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE users (id TEXT PRIMARY KEY)")
        connection.execute("CREATE TABLE sync_logs (id TEXT PRIMARY KEY)")
        connection.execute("CREATE TABLE transaction_metadata (id TEXT PRIMARY KEY)")
        connection.execute("CREATE TABLE ledger_transactions (id TEXT PRIMARY KEY)")
        connection.execute("INSERT INTO users VALUES ('user')")
        connection.execute("INSERT INTO sync_logs VALUES ('sync')")
        connection.execute("INSERT INTO transaction_metadata VALUES ('tx')")
        connection.execute("INSERT INTO ledger_transactions VALUES ('ledger-tx')")


def test_test_ledger_generation_is_deterministic(tmp_path: Path) -> None:
    source = Path("tests/fixtures/ledger_projection/main.beancount")
    first = generate(source, tmp_path / "first", 2)
    second = generate(source, tmp_path / "second", 2)
    assert first["transactions"] == second["transactions"]
    assert first["postings"] == second["postings"]
    assert first["fingerprint"] == second["fingerprint"]


def test_single_machine_preview_is_read_only_and_apply_preserves_core(tmp_path: Path) -> None:
    database = tmp_path / "beanmind.db"
    backup = tmp_path / "backup.db"
    create_database(database)
    before = database.read_bytes()
    report = preview(database)
    assert report["remove"] == {"users": 1, "sync_logs": 1, "transaction_metadata": 1}
    assert report["preserve"] == {"ledger_transactions": 1}
    assert database.read_bytes() == before
    shutil.copy2(database, backup)

    applied = apply(database, backup)
    assert applied["remove"] == {}
    assert applied["preserve"] == {"ledger_transactions": 1}


def test_single_machine_apply_rolls_back_on_failure(tmp_path: Path) -> None:
    database = tmp_path / "beanmind.db"
    backup = tmp_path / "backup.db"
    create_database(database)
    shutil.copy2(database, backup)
    with pytest.raises(RuntimeError, match="故障注入"):
        apply(database, backup, fail_after_drop=True)
    assert preview(database)["remove"] == {
        "users": 1, "sync_logs": 1, "transaction_metadata": 1
    }


def test_single_machine_migrates_recurring_owner_and_cleans_checkpoint(tmp_path: Path) -> None:
    database = tmp_path / "beanmind.db"
    backup = tmp_path / "backup.db"
    checkpoint = tmp_path / "ai_checkpoints.db"
    checkpoint_backup = tmp_path / "ai_checkpoints.backup.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE recurring_rules (
                user_id TEXT NOT NULL, name TEXT NOT NULL, frequency TEXT NOT NULL,
                frequency_config TEXT, transaction_template TEXT NOT NULL,
                start_date DATE NOT NULL, end_date DATE, is_active BOOLEAN NOT NULL,
                id TEXT PRIMARY KEY, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO recurring_rules VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "old-user", "房租", "MONTHLY", '{"month_days":[1]}',
                '{"description":"房租","postings":[]}', "2025-01-01", None,
                1, "rule-1", "2025-01-01", "2025-01-01",
            ),
        )
    checkpoint.write_bytes(b"checkpoint-data")
    shutil.copy2(database, backup)
    shutil.copy2(checkpoint, checkpoint_backup)

    before = database.read_bytes()
    report = preview(database, checkpoint)
    assert report["schema_changes"] == ["recurring_rules:remove_user_id"]
    assert report["checkpoint"]["sha256"]
    assert database.read_bytes() == before

    result = apply(
        database,
        backup,
        checkpoint=checkpoint,
        checkpoint_backup=checkpoint_backup,
    )
    assert result["schema_changes"] == []
    assert result["checkpoint"]["exists"] is False
    with sqlite3.connect(database) as connection:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(recurring_rules)")]
        assert "user_id" not in columns
        assert connection.execute("SELECT name FROM recurring_rules").fetchone()[0] == "房租"


def test_recurring_schema_migration_rolls_back_with_database_cleanup(tmp_path: Path) -> None:
    database = tmp_path / "beanmind.db"
    backup = tmp_path / "backup.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE recurring_rules (
                user_id TEXT NOT NULL, name TEXT NOT NULL, frequency TEXT NOT NULL,
                frequency_config TEXT, transaction_template TEXT NOT NULL,
                start_date DATE NOT NULL, end_date DATE, is_active BOOLEAN NOT NULL,
                id TEXT PRIMARY KEY, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL
            )
            """
        )
    shutil.copy2(database, backup)
    with pytest.raises(RuntimeError, match="故障注入"):
        apply(database, backup, fail_after_drop=True)
    assert preview(database)["schema_changes"] == ["recurring_rules:remove_user_id"]


def test_monthly_budget_preview_blocks_ambiguous_data_without_writing(tmp_path: Path) -> None:
    database = tmp_path / "beanmind.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE budgets (id TEXT, amount TEXT, period_type TEXT, cycle_type TEXT, carry_over_enabled INTEGER, start_date TEXT, end_date TEXT)"
        )
        connection.execute(
            "CREATE TABLE budget_items (id TEXT, budget_id TEXT, account_pattern TEXT, amount TEXT, currency TEXT)"
        )
        connection.execute(
            "INSERT INTO budgets VALUES ('b1', '100', 'YEARLY', 'YEARLY', 1, '2025-01-01', '2025-12-31')"
        )
        connection.execute(
            "INSERT INTO budget_items VALUES ('i1', 'b1', 'Expenses:Food:*', '50', 'CNY')"
        )
    before = database.read_bytes()
    report = analyze(database)
    assert report["convertible"] == []
    assert report["blocked"][0]["reasons"]
    assert database.read_bytes() == before


def create_multicurrency_monthly_budgets(path: Path, *, include_cny: bool = True) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE monthly_budgets (
                month TEXT NOT NULL, currency TEXT NOT NULL,
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(month, currency)
            );
            CREATE TABLE monthly_budget_items (
                budget_id TEXT NOT NULL, name TEXT NOT NULL, account_pattern TEXT NOT NULL,
                amount_text TEXT NOT NULL, display_order INTEGER NOT NULL,
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            """
        )
        if include_cny:
            connection.execute(
                "INSERT INTO monthly_budgets VALUES ('2025-01', 'CNY', 'cny', 'now', 'now')"
            )
            connection.execute(
                "INSERT INTO monthly_budget_items VALUES ('cny', '餐饮', 'Expenses:Food', '100.10', 0, 'cny-item', 'now', 'now')"
            )
        connection.execute(
            "INSERT INTO monthly_budgets VALUES ('2025-01', 'USD', 'usd', 'now', 'now')"
        )
        connection.execute(
            "INSERT INTO monthly_budget_items VALUES ('usd', '差旅', 'Expenses:Travel', '20.20', 0, 'usd-item', 'now', 'now')"
        )


def test_operating_currency_budget_preview_is_read_only_and_reports_removals(
    tmp_path: Path,
) -> None:
    database = tmp_path / "beanmind.db"
    create_multicurrency_monthly_budgets(database)
    before = database.read_bytes()

    report = analyze_operating_currency_budgets(database, "CNY")

    assert report["schema_state"] == "MULTI_CURRENCY"
    assert report["keep"] == [
        {
            "budget_id": "cny",
            "month": "2025-01",
            "currency": "CNY",
            "item_count": 1,
            "total": "100.10",
        }
    ]
    assert report["remove"][0]["currency"] == "USD"
    assert report["blocked"] == []
    assert database.read_bytes() == before


def test_operating_currency_budget_preview_blocks_foreign_only_month(
    tmp_path: Path,
) -> None:
    database = tmp_path / "beanmind.db"
    create_multicurrency_monthly_budgets(database, include_cny=False)

    report = analyze_operating_currency_budgets(database, "CNY")

    assert report["keep"] == []
    assert report["blocked"] == [
        {"month": "2025-01", "currencies": ["USD"], "reason": "仅有非经营币种预算"}
    ]


def test_operating_currency_budget_apply_requires_confirmation_and_is_atomic(
    tmp_path: Path,
) -> None:
    database = tmp_path / "beanmind.db"
    backup = tmp_path / "backup.db"
    create_multicurrency_monthly_budgets(database)
    shutil.copy2(database, backup)

    with pytest.raises(ValueError, match="显式确认"):
        apply_operating_currency_budgets(database, backup, "CNY")
    with pytest.raises(RuntimeError, match="故障注入"):
        apply_operating_currency_budgets(
            database,
            backup,
            "CNY",
            confirm_removals=True,
            fail_after_rebuild=True,
        )
    assert analyze_operating_currency_budgets(database, "CNY")["schema_state"] == "MULTI_CURRENCY"

    result = apply_operating_currency_budgets(
        database,
        backup,
        "CNY",
        confirm_removals=True,
    )
    assert result["migrated"] is True
    assert result["removed_budgets"] == 1
    with sqlite3.connect(database) as connection:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(monthly_budgets)")]
        assert "currency" not in columns
        assert connection.execute("SELECT month FROM monthly_budgets").fetchall() == [("2025-01",)]
        assert connection.execute("SELECT amount_text FROM monthly_budget_items").fetchall() == [("100.10",)]
