#!/usr/bin/env python3
"""将当前多币种月度预算安全收敛为经营币种唯一预算。"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from decimal import Decimal
from pathlib import Path


def fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def connect(path: Path, readonly: bool) -> sqlite3.Connection:
    if readonly:
        connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
        connection.execute("PRAGMA query_only=ON")
    else:
        connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def _summary(database: sqlite3.Connection, budget: sqlite3.Row) -> dict:
    items = database.execute(
        "SELECT amount_text FROM monthly_budget_items WHERE budget_id = ?",
        (budget["id"],),
    ).fetchall()
    total = sum((Decimal(str(item["amount_text"])) for item in items), Decimal("0"))
    return {
        "budget_id": budget["id"],
        "month": budget["month"],
        "currency": budget["currency"],
        "item_count": len(items),
        "total": format(total, "f"),
    }


def analyze(path: Path, operating_currency: str) -> dict:
    operating = operating_currency.strip().upper()
    if not operating:
        raise ValueError("经营币种不能为空")
    before = fingerprint(path)
    with connect(path, True) as database:
        tables = {
            row[0]
            for row in database.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if "monthly_budgets" not in tables:
            report = {
                "database": str(path.resolve()),
                "sha256": before,
                "operating_currency": operating,
                "schema_state": "ABSENT",
                "keep": [],
                "remove": [],
                "blocked": [],
                "target_constraint": "UNIQUE(month)",
            }
        else:
            columns = {
                row[1] for row in database.execute("PRAGMA table_info(monthly_budgets)")
            }
            if "currency" not in columns:
                count = database.execute("SELECT COUNT(*) FROM monthly_budgets").fetchone()[0]
                item_count = database.execute(
                    "SELECT COUNT(*) FROM monthly_budget_items"
                ).fetchone()[0]
                report = {
                    "database": str(path.resolve()),
                    "sha256": before,
                    "operating_currency": operating,
                    "schema_state": "OPERATING_CURRENCY_ONLY",
                    "keep": [],
                    "remove": [],
                    "blocked": [],
                    "preserved": {"budgets": count, "items": item_count},
                    "target_constraint": "UNIQUE(month)",
                }
            else:
                budgets = database.execute(
                    "SELECT * FROM monthly_budgets ORDER BY month, currency, id"
                ).fetchall()
                by_month: dict[str, list[sqlite3.Row]] = {}
                for budget in budgets:
                    by_month.setdefault(budget["month"], []).append(budget)
                keep: list[dict] = []
                remove: list[dict] = []
                blocked: list[dict] = []
                for month, month_budgets in by_month.items():
                    operating_budgets = [
                        budget
                        for budget in month_budgets
                        if str(budget["currency"]).upper() == operating
                    ]
                    if len(operating_budgets) != 1:
                        blocked.append(
                            {
                                "month": month,
                                "currencies": sorted(
                                    str(budget["currency"]).upper()
                                    for budget in month_budgets
                                ),
                                "reason": (
                                    "仅有非经营币种预算"
                                    if not operating_budgets
                                    else "同月存在多个经营币种预算"
                                ),
                            }
                        )
                        continue
                    selected = operating_budgets[0]
                    keep.append(_summary(database, selected))
                    remove.extend(
                        _summary(database, budget)
                        for budget in month_budgets
                        if budget["id"] != selected["id"]
                    )
                report = {
                    "database": str(path.resolve()),
                    "sha256": before,
                    "operating_currency": operating,
                    "schema_state": "MULTI_CURRENCY",
                    "keep": keep,
                    "remove": remove,
                    "blocked": blocked,
                    "target_constraint": "UNIQUE(month)",
                }
    if fingerprint(path) != before:
        raise RuntimeError("预算预览期间数据库发生变化")
    return report


def apply(
    path: Path,
    backup: Path,
    operating_currency: str,
    *,
    confirm_removals: bool = False,
    fail_after_rebuild: bool = False,
) -> dict:
    report = analyze(path, operating_currency)
    if report["schema_state"] != "MULTI_CURRENCY":
        return {"migrated": False, "preview": report}
    if report["blocked"]:
        raise ValueError("存在仅有非经营币种或重复经营币种的月份，拒绝迁移")
    if report["remove"] and not confirm_removals:
        raise ValueError("存在待移除的非经营币种预算，必须显式确认")
    if fingerprint(path) != fingerprint(backup):
        raise ValueError("外部备份与迁移前数据库不一致")

    keep_ids = [item["budget_id"] for item in report["keep"]]
    placeholders = ",".join("?" for _ in keep_ids) or "NULL"
    with connect(path, False) as database:
        database.execute("PRAGMA foreign_keys=OFF")
        try:
            database.execute("BEGIN IMMEDIATE")
            database.execute(
                """
                CREATE TABLE monthly_budgets_new (
                    month VARCHAR(7) NOT NULL,
                    id VARCHAR(36) NOT NULL PRIMARY KEY,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    CONSTRAINT uq_monthly_budget_month UNIQUE (month)
                )
                """
            )
            database.execute(
                """
                CREATE TABLE monthly_budget_items_new (
                    budget_id VARCHAR(36) NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    account_pattern TEXT NOT NULL,
                    amount_text TEXT NOT NULL,
                    display_order INTEGER NOT NULL,
                    id VARCHAR(36) NOT NULL PRIMARY KEY,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    FOREIGN KEY(budget_id) REFERENCES monthly_budgets_new (id) ON DELETE CASCADE
                )
                """
            )
            if keep_ids:
                database.execute(
                    f"""
                    INSERT INTO monthly_budgets_new(month, id, created_at, updated_at)
                    SELECT month, id, created_at, updated_at
                    FROM monthly_budgets WHERE id IN ({placeholders})
                    """,
                    keep_ids,
                )
                database.execute(
                    f"""
                    INSERT INTO monthly_budget_items_new(
                        budget_id, name, account_pattern, amount_text, display_order,
                        id, created_at, updated_at
                    )
                    SELECT budget_id, name, account_pattern, amount_text, display_order,
                           id, created_at, updated_at
                    FROM monthly_budget_items WHERE budget_id IN ({placeholders})
                    """,
                    keep_ids,
                )

            expected_budgets = len(report["keep"])
            expected_items = sum(item["item_count"] for item in report["keep"])
            actual_budgets = database.execute(
                "SELECT COUNT(*) FROM monthly_budgets_new"
            ).fetchone()[0]
            actual_items = database.execute(
                "SELECT COUNT(*) FROM monthly_budget_items_new"
            ).fetchone()[0]
            if (actual_budgets, actual_items) != (expected_budgets, expected_items):
                raise RuntimeError("迁移核对失败：预算或分类数量不一致")

            database.execute("DROP TABLE monthly_budget_items")
            database.execute("DROP TABLE monthly_budgets")
            if fail_after_rebuild:
                raise RuntimeError("故障注入：预算表重建后回滚")
            database.execute("ALTER TABLE monthly_budgets_new RENAME TO monthly_budgets")
            database.execute(
                "ALTER TABLE monthly_budget_items_new RENAME TO monthly_budget_items"
            )
            database.execute(
                "CREATE INDEX idx_monthly_budgets_month ON monthly_budgets (month)"
            )
            database.execute(
                "CREATE INDEX idx_monthly_budget_items_budget_order ON monthly_budget_items (budget_id, display_order)"
            )
            database.commit()
        except Exception:
            database.rollback()
            raise
        finally:
            database.execute("PRAGMA foreign_keys=ON")

    after = analyze(path, operating_currency)
    if after["schema_state"] != "OPERATING_CURRENCY_ONLY":
        raise RuntimeError("迁移后预算结构核对失败")
    return {
        "migrated": True,
        "kept_budgets": len(report["keep"]),
        "kept_items": sum(item["item_count"] for item in report["keep"]),
        "removed_budgets": len(report["remove"]),
        "preview": report,
        "after": after,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="迁移预算为经营币种唯一结构")
    parser.add_argument("database", type=Path)
    parser.add_argument("--operating-currency", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--confirm-remove-non-operating", action="store_true")
    args = parser.parse_args()
    if args.apply:
        if args.backup is None:
            parser.error("--apply 必须同时提供 --backup")
        result = apply(
            args.database,
            args.backup,
            args.operating_currency,
            confirm_removals=args.confirm_remove_non_operating,
        )
    else:
        result = analyze(args.database, args.operating_currency)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
