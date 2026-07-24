from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend.application.services.recurring_service import RecurringApplicationService
from backend.config import get_db
from backend.infrastructure.persistence.db.models import (
    LedgerTransaction,
    RecurringExecution,
    RecurringRule,
)
from backend.infrastructure.persistence.ledger_projection import (
    LedgerProjectionDirtyError,
    LedgerProjectionService,
    TransactionQueryService,
)
from backend.main import app


def payload():
    return {
        "name": "每月房租",
        "frequency": "monthly",
        "frequency_config": {"month_days": [1]},
        "transaction_template": {
            "description": "支付房租",
            "postings": [
                {"account": "Expenses:Food", "amount": "1000.123456789", "currency": "CNY"},
                {"account": "Assets:Cash", "amount": "-1000.123456789", "currency": "CNY"},
            ],
        },
        "start_date": "2025-01-01",
        "is_active": True,
    }


def test_single_machine_recurring_rule_crud_has_no_user_identity(db_session) -> None:
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        created = client.post("/api/recurring/rules", json=payload())
        listed = client.get("/api/recurring/rules")
        rule_id = created.json()["id"]
        updated = client.put(
            f"/api/recurring/rules/{rule_id}", json={"is_active": False}
        )
    finally:
        app.dependency_overrides.clear()

    assert created.status_code == 200
    assert "user_id" not in created.json()
    assert created.json()["transaction_template"]["postings"][0]["amount"] == "1000.123456789"
    assert listed.status_code == 200
    assert [rule["name"] for rule in listed.json()] == ["每月房租"]
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False


def test_recurring_rule_rejects_missing_month_days(db_session) -> None:
    invalid = payload()
    invalid["frequency_config"] = {}
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        response = TestClient(app).post("/api/recurring/rules", json=invalid)
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 400


def test_manual_recurring_execution_refreshes_projection_immediately(
    temp_ledger_env, db_session
) -> None:
    ledger_path = temp_ledger_env["ledger_path"]
    projection = LedgerProjectionService(db_session, ledger_path)
    projection.rebuild_all()
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        created_rule = client.post("/api/recurring/rules", json=payload())
        rule_id = created_rule.json()["id"]

        executed = client.post(
            f"/api/recurring/rules/{rule_id}/execute",
            json={"date": "2025-04-01"},
        )
        transaction_id = executed.json()["transaction_id"]
        listed = client.get(
            "/api/transactions",
            params={"description": "支付房租"},
        )
    finally:
        app.dependency_overrides.clear()

    assert created_rule.status_code == 200
    assert executed.status_code == 200
    assert len(transaction_id) == 32
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [transaction_id]

    projected = db_session.get(LedgerTransaction, transaction_id)
    assert projected is not None
    assert [posting.amount_text for posting in projected.postings] == [
        "1000.123456789",
        "-1000.123456789",
    ]
    assert projection.check_consistency()["consistent"] is True


def test_scheduled_recurring_execution_refreshes_projection_and_records_stable_id(
    temp_ledger_env, db_session
) -> None:
    ledger_path = temp_ledger_env["ledger_path"]
    projection = LedgerProjectionService(db_session, ledger_path)
    projection.rebuild_all()
    rule = RecurringRule(
        name="每月房租",
        frequency="MONTHLY",
        frequency_config='{"month_days": [1]}',
        transaction_template=(
            '{"description": "调度房租", "postings": ['
            '{"account": "Expenses:Food", "amount": "1000.123456789", "currency": "CNY"},'
            '{"account": "Assets:Cash", "amount": "-1000.123456789", "currency": "CNY"}'
            "]}"
        ),
        start_date=date(2025, 1, 1),
        is_active=True,
    )
    db_session.add(rule)
    db_session.commit()

    results = RecurringApplicationService(db_session).execute_due_rules(
        date(2025, 5, 1)
    )

    assert len(results) == 1
    assert results[0]["status"] == "SUCCESS"
    transaction_id = results[0]["transaction_id"]
    assert len(transaction_id) == 32
    projected = db_session.get(LedgerTransaction, transaction_id)
    execution = (
        db_session.query(RecurringExecution)
        .filter(RecurringExecution.rule_id == rule.id)
        .one()
    )
    assert projected is not None
    assert execution.transaction_id == transaction_id
    assert [posting.amount_text for posting in projected.postings] == [
        "1000.123456789",
        "-1000.123456789",
    ]
    assert projection.check_consistency()["consistent"] is True


def test_recurring_projection_failure_keeps_ledger_dirty_until_recovery(
    temp_ledger_env, db_session, monkeypatch
) -> None:
    ledger_path = temp_ledger_env["ledger_path"]
    projection = LedgerProjectionService(db_session, ledger_path)
    projection.rebuild_all()
    rule = RecurringRule(
        name="投影失败测试",
        frequency="MONTHLY",
        frequency_config='{"month_days": [1]}',
        transaction_template=(
            '{"description": "投影失败仍保留", "postings": ['
            '{"account": "Expenses:Food", "amount": "8.765432109", "currency": "CNY"},'
            '{"account": "Assets:Cash", "amount": "-8.765432109", "currency": "CNY"}'
            "]}"
        ),
        start_date=date(2025, 1, 1),
        is_active=True,
    )
    db_session.add(rule)
    db_session.commit()
    original_refresh = LedgerProjectionService.refresh_file
    monkeypatch.setattr(
        LedgerProjectionService,
        "refresh_file",
        lambda self, path: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    results = RecurringApplicationService(db_session).execute_due_rules(
        date(2025, 6, 1)
    )
    transaction_id = results[0]["transaction_id"]
    written_files = list(ledger_path.parent.glob("*.beancount"))

    assert results[0]["status"] == "SUCCESS"
    assert any(
        "投影失败仍保留" in path.read_text(encoding="utf-8")
        for path in written_files
    )
    with pytest.raises(LedgerProjectionDirtyError):
        TransactionQueryService(db_session, ledger_path).list_transactions()

    monkeypatch.setattr(LedgerProjectionService, "refresh_file", original_refresh)
    recovered = projection.ensure_current()
    items = TransactionQueryService(db_session, ledger_path).list_transactions(
        description="投影失败仍保留"
    )

    assert recovered["status"] == "READY"
    assert [item["id"] for item in items["items"]] == [transaction_id]
    assert projection.check_consistency()["consistent"] is True


def test_recurring_write_validation_failure_records_failed_without_ledger_change(
    temp_ledger_env, db_session
) -> None:
    ledger_path = temp_ledger_env["ledger_path"]
    projection = LedgerProjectionService(db_session, ledger_path)
    projection.rebuild_all()
    before = {
        path: path.read_text(encoding="utf-8")
        for path in ledger_path.parent.glob("*.beancount")
    }
    rule = RecurringRule(
        name="无效账户测试",
        frequency="MONTHLY",
        frequency_config='{"month_days": [1]}',
        transaction_template=(
            '{"description": "不应写入账本", "postings": ['
            '{"account": "Expenses:Missing", "amount": "1.23", "currency": "CNY"},'
            '{"account": "Assets:Cash", "amount": "-1.23", "currency": "CNY"}'
            "]}"
        ),
        start_date=date(2025, 1, 1),
        is_active=True,
    )
    db_session.add(rule)
    db_session.commit()

    results = RecurringApplicationService(db_session).execute_due_rules(
        date(2025, 7, 1)
    )
    execution = (
        db_session.query(RecurringExecution)
        .filter(RecurringExecution.rule_id == rule.id)
        .one()
    )

    assert results[0]["status"] == "FAILED"
    assert results[0]["transaction_id"] is None
    assert execution.status == "FAILED"
    assert execution.transaction_id is None
    assert before == {
        path: path.read_text(encoding="utf-8")
        for path in ledger_path.parent.glob("*.beancount")
    }
    assert projection.check_consistency()["consistent"] is True
