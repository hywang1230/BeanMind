#!/usr/bin/env python3
"""旧预算到月度分类预算的一次性预览/确认迁移。"""

from __future__ import annotations

import argparse
import calendar
import json
import sqlite3
import uuid
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from migrate_single_machine import preview as database_preview


def connect(path: Path, readonly: bool) -> sqlite3.Connection:
    if readonly:
        connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
        connection.execute("PRAGMA query_only=ON")
    else:
        connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def analyze(path: Path, operating_currency: str | None = None) -> dict:
    operating = operating_currency.strip().upper() if operating_currency else None
    fingerprint = database_preview(path)["sha256"]
    convertible: list[dict] = []
    blocked: list[dict] = []
    with connect(path, True) as database:
        tables = {
            row[0]
            for row in database.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if not {"budgets", "budget_items"}.issubset(tables):
            return {"database": str(path.resolve()), "sha256": fingerprint, "convertible": [], "blocked": []}
        budgets = database.execute("SELECT * FROM budgets ORDER BY start_date, id").fetchall()
        by_target: dict[tuple[str, str], list[str]] = {}
        candidates: list[dict] = []
        for budget in budgets:
            items = database.execute(
                "SELECT * FROM budget_items WHERE budget_id = ? ORDER BY id", (budget["id"],)
            ).fetchall()
            reasons: list[str] = []
            try:
                start = date.fromisoformat(str(budget["start_date"]))
                end = date.fromisoformat(str(budget["end_date"]))
            except ValueError:
                reasons.append("日期格式无法识别")
                start = end = date.min
            if budget["period_type"] != "MONTHLY" or start.day != 1 or end != date(
                start.year, start.month, calendar.monthrange(start.year, start.month)[1]
            ):
                reasons.append("不是单一自然月")
            if budget["cycle_type"] != "NONE" or bool(budget["carry_over_enabled"]):
                reasons.append("包含循环或结转规则")
            if not items:
                reasons.append("没有分类项")
            currencies = {item["currency"] for item in items}
            if len(currencies) != 1:
                reasons.append("分类币种不唯一")
            if any("*" in item["account_pattern"] for item in items):
                reasons.append("旧通配模式无法无损映射")
            item_total = sum((Decimal(str(item["amount"])) for item in items), Decimal("0"))
            if item_total != Decimal(str(budget["amount"])):
                reasons.append("预算总额与分类求和不一致")
            month = start.strftime("%Y-%m") if start != date.min else "unknown"
            currency = next(iter(currencies), "unknown")
            candidate = {
                "source_id": budget["id"],
                "month": month,
                "currency": currency,
                "source_total": format(Decimal(str(budget["amount"])), "f"),
                "item_total": format(item_total, "f"),
                "items": [
                    {
                        "name": item["account_pattern"],
                        "account_pattern": item["account_pattern"],
                        "amount": format(Decimal(str(item["amount"])), "f"),
                    }
                    for item in items
                ],
                "reasons": reasons,
            }
            candidates.append(candidate)
            target = (month, operating) if operating else (month, currency)
            by_target.setdefault(target, []).append(budget["id"])
        for candidate in candidates:
            if operating and candidate["currency"].upper() != operating:
                candidate["reasons"].append("不是经营币种预算")
            target = (
                (candidate["month"], operating)
                if operating
                else (candidate["month"], candidate["currency"])
            )
            conflicts = by_target[target]
            if len(conflicts) > 1:
                candidate["reasons"].append("目标月份存在多个旧预算")
            (blocked if candidate["reasons"] else convertible).append(candidate)
    if database_preview(path)["sha256"] != fingerprint:
        raise RuntimeError("预算预览期间数据库发生变化")
    return {
        "database": str(path.resolve()),
        "sha256": fingerprint,
        "convertible": convertible,
        "blocked": blocked,
    }


def apply(path: Path, backup: Path, operating_currency: str) -> dict:
    report = analyze(path, operating_currency)
    if report["blocked"]:
        raise ValueError("存在无法唯一映射的旧预算，拒绝迁移")
    if database_preview(path)["remove"] != database_preview(backup)["remove"]:
        raise ValueError("外部备份与源数据库不匹配")
    with connect(path, False) as database:
        try:
            database.execute("BEGIN IMMEDIATE")
            database.execute(
                "CREATE TABLE IF NOT EXISTS monthly_budgets (id TEXT PRIMARY KEY, month TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(month))"
            )
            database.execute(
                "CREATE TABLE IF NOT EXISTS monthly_budget_items (id TEXT PRIMARY KEY, budget_id TEXT NOT NULL, name TEXT NOT NULL, account_pattern TEXT NOT NULL, amount_text TEXT NOT NULL, display_order INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
            )
            for candidate in report["convertible"]:
                budget_id = uuid.uuid4().hex
                now = datetime.now().isoformat()
                database.execute(
                    "INSERT INTO monthly_budgets(id, month, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (budget_id, candidate["month"], now, now),
                )
                for order, item in enumerate(candidate["items"]):
                    database.execute(
                        "INSERT INTO monthly_budget_items(id, budget_id, name, account_pattern, amount_text, display_order, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (uuid.uuid4().hex, budget_id, item["name"], item["account_pattern"], item["amount"], order, now, now),
                    )
            database.commit()
        except Exception:
            database.rollback()
            raise
    return {"migrated": len(report["convertible"]), "preview": report}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    parser.add_argument("--operating-currency", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    if args.apply:
        if args.backup is None:
            parser.error("--apply 必须同时提供 --backup")
        result = apply(args.database, args.backup, args.operating_currency)
    else:
        result = analyze(args.database, args.operating_currency)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
