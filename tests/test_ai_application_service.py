"""AI 应用服务关键回归测试。"""

import asyncio
import json
from pathlib import Path
import shutil
import tempfile

import pytest

from backend.application.services.ai_service import AIApplicationService
from backend.application.services import AccountApplicationService
from backend.config import settings
from backend.config import dependencies
from backend.infrastructure.persistence.beancount.repositories import AccountRepositoryImpl
from backend.config.dependencies import get_db_session
from backend.infrastructure.persistence.db.models import (
    AIActionAudit,
    AIAgentInvocation,
    AISkillInvocation,
    AIToolInvocation,
    AIUserPreference,
)


@pytest.fixture
def test_ledger_file():
    """创建临时账本文件，避免污染真实账本。"""
    temp_dir = tempfile.mkdtemp()
    test_ledger = Path(temp_dir) / "ai_test.beancount"
    test_ledger.write_text(
        """
option "operating_currency" "CNY"

2026-01-01 open Assets:Bank:Checking CNY
2026-01-01 open Expenses:Meals CNY
2026-01-01 open Income:Salary CNY
2026-01-01 open Equity:OpeningBalances CNY

2026-01-02 * "Opening Balance"
  Assets:Bank:Checking   1000.00 CNY
  Equity:OpeningBalances  -1000.00 CNY
""".strip()
        + "\n",
        encoding="utf-8",
    )

    original_ledger = settings.LEDGER_FILE
    original_service = dependencies._beancount_service
    settings.LEDGER_FILE = test_ledger
    dependencies._beancount_service = None

    yield test_ledger

    settings.LEDGER_FILE = original_ledger
    dependencies._beancount_service = original_service
    shutil.rmtree(temp_dir, ignore_errors=True)


def _build_account_service() -> AccountApplicationService:
    return AccountApplicationService(
        AccountRepositoryImpl(dependencies.get_beancount_service())
    )


def test_session_history_includes_pending_action_for_transaction_draft(test_ledger_file):
    """记账草稿应能通过会话历史恢复待确认动作。"""
    service = AIApplicationService()

    result = service.chat("帮我记一笔今天午饭38元")
    session_id = result["session_id"]

    history = service.get_session_history(session_id)

    assert history is not None
    assert history["pending_action"] is not None
    assert history["pending_action"]["action_type"] == "transaction.record"
    assert history["pending_action"]["draft"]["postings"]

    service.resume_session_action(session_id, "cancel")
    service.delete_session(session_id)


def test_account_manage_confirm_creates_account(test_ledger_file):
    """账户草稿确认后应真实创建账户。"""
    service = AIApplicationService()
    account_name = "Assets:AITestManagedAccount"

    result = service.chat(f"新建账户 {account_name}")
    session_id = result["session_id"]

    confirm = service.resume_session_action(session_id, "confirm")
    assert "已确认并创建账户" in confirm["message"]["content"]

    account_service = _build_account_service()
    created = account_service.get_account(account_name)
    assert created is not None
    assert created["name"] == account_name

    # 清理测试数据，避免影响后续测试
    assert account_service.close_account(account_name) is True
    service.delete_session(session_id)


def test_ai_audits_are_written_for_account_manage(test_ledger_file):
    """账户草稿和确认后应写入 action/skill/agent 审计。"""
    service = AIApplicationService()
    account_name = "Assets:AITestAuditAccount"

    result = service.chat(f"新建账户 {account_name}")
    session_id = result["session_id"]
    service.resume_session_action(session_id, "confirm")

    db = get_db_session()
    try:
        action_audits = db.query(AIActionAudit).filter(AIActionAudit.session_id == session_id).all()
        skill_audits = db.query(AISkillInvocation).filter(AISkillInvocation.session_id == session_id).all()
        agent_audits = db.query(AIAgentInvocation).filter(AIAgentInvocation.session_id == session_id).all()
    finally:
        db.close()

    assert any(audit.action_type == "account.manage" and audit.status == "DRAFTED" for audit in action_audits)
    assert any(audit.action_type == "account.manage" and audit.status == "CONFIRMED" for audit in action_audits)
    assert any(audit.skill_id == "account.manage" for audit in skill_audits)
    assert any(audit.agent_id == "account_agent" for audit in agent_audits)

    account_service = _build_account_service()
    assert account_service.close_account(account_name) is True
    service.delete_session(session_id)


def test_account_close_requires_second_confirmation(test_ledger_file):
    """关闭账户应先经过一次 guardrail 二次确认。"""
    account_service = _build_account_service()
    account_name = "Assets:AITestCloseAccount"
    account_service.create_account(name=account_name, account_type="Assets", currencies=["CNY"], open_date="2026-04-08")

    service = AIApplicationService()
    result = service.chat(f"关闭账户 {account_name}")
    session_id = result["session_id"]

    first_confirm = service.resume_session_action(session_id, "confirm")
    assert "高风险操作" in first_confirm["message"]["content"]

    history = service.get_session_history(session_id)
    assert history is not None
    assert history["pending_action"] is not None
    assert history["pending_action"]["action_type"] == "account.manage"

    second_confirm = service.resume_session_action(session_id, "confirm")
    assert "已确认并关闭账户" in second_confirm["message"]["content"]

    closed = account_service.get_account(account_name)
    assert closed is not None
    assert closed["is_active"] is False

    service.delete_session(session_id)


def test_pending_action_can_resume_after_service_restart(test_ledger_file):
    """服务重建后，持久化的待确认草稿仍可恢复并继续执行。"""
    service = AIApplicationService()
    result = service.chat("帮我记一笔今天午饭42元")
    session_id = result["session_id"]

    AIApplicationService._sessions = {}
    restarted_service = AIApplicationService()

    history = restarted_service.get_session_history(session_id)
    assert history is not None
    assert history["pending_action"] is not None
    assert history["pending_action"]["action_type"] == "transaction.record"

    confirmed = restarted_service.resume_session_action(session_id, "confirm")
    assert "已确认并写入账本" in confirmed["message"]["content"]

    restarted_service.delete_session(session_id)


def test_chat_stream_emits_interrupt_sequence_for_transaction_draft(test_ledger_file):
    """交易草稿流式输出应包含关键事件序列。"""
    service = AIApplicationService()

    async def collect_events():
        events = []
        async for chunk in service.chat_stream("帮我记一笔今天午饭43元"):
            if not chunk.startswith("data: "):
                continue
            events.append(json.loads(chunk[len("data: "):]))
        return events

    events = asyncio.run(collect_events())
    event_types = [event["type"] for event in events]

    assert "session" in event_types
    assert "progress" in event_types
    assert "skill" in event_types
    assert "agent" in event_types
    assert "tool" in event_types
    assert "interrupt" in event_types
    assert event_types[-1] == "done"

    interrupt_event = next(event for event in events if event["type"] == "interrupt")
    assert interrupt_event["action_type"] == "transaction.record"
    assert interrupt_event["draft"]["postings"]

    service.resume_session_action(events[0]["session_id"], "cancel")
    service.delete_session(events[0]["session_id"])


def test_confirmed_transaction_writes_memory_preferences_and_tool_audit(test_ledger_file):
    """交易确认后应写入长期记忆，并记录工具调用审计。"""
    service = AIApplicationService()

    result = service.chat("帮我记一笔今天在楼下餐馆午饭58元")
    session_id = result["session_id"]
    service.resume_session_action(session_id, "confirm")

    db = get_db_session()
    try:
        preferences = db.query(AIUserPreference).all()
        tool_audits = db.query(AIToolInvocation).filter(AIToolInvocation.session_id == session_id).all()
    finally:
        db.close()

    preference_types = {item.preference_type for item in preferences}
    assert "preferred_asset_account" in preference_types
    assert "preferred_currency" in preference_types
    assert any(item.preference_type == "payee_account_map" for item in preferences)
    assert any(audit.tool_name == "draft_transaction" for audit in tool_audits)

    service.delete_session(session_id)


def test_memory_preferences_are_reused_for_next_transaction_draft(test_ledger_file):
    """长期记忆应能影响下一次交易草稿推荐。"""
    account_service = _build_account_service()
    preferred_asset_account = "Assets:Wallet"
    created = account_service.create_account(
        name=preferred_asset_account,
        account_type="Assets",
        currencies=["CNY"],
        open_date="2026-04-08",
    )
    assert created["name"] == preferred_asset_account

    db = get_db_session()
    try:
        db.add(
            AIUserPreference(
                user_id="default",
                preference_type="preferred_asset_account",
                preference_key=preferred_asset_account,
                value_json=json.dumps({"account": preferred_asset_account}, ensure_ascii=False),
                weight=5.0,
            )
        )
        db.commit()
    finally:
        db.close()

    service = AIApplicationService()
    second = service.chat("帮我记一笔今天午饭62元")
    second_session_id = second["session_id"]
    history = service.get_session_history(second_session_id)

    assert history is not None
    pending_action = history["pending_action"]
    assert pending_action is not None
    assert pending_action["draft"]["postings"][1]["account"] == preferred_asset_account
    assert pending_action["draft"]["postings"][1]["currency"] == "CNY"

    service.resume_session_action(second_session_id, "cancel")
    service.delete_session(second_session_id)
    assert account_service.close_account(preferred_asset_account) is True


def test_delete_last_confirmed_transaction_via_session_reference(test_ledger_file):
    """引用当前会话最近一条已确认交易时，应生成删除草稿并真正删除。"""
    service = AIApplicationService()

    create_result = service.chat("帮我记一笔今天午饭48元")
    session_id = create_result["session_id"]
    service.resume_session_action(session_id, "confirm")

    db = get_db_session()
    try:
        audit = (
            db.query(AIActionAudit)
            .filter(
                AIActionAudit.session_id == session_id,
                AIActionAudit.action_type == "transaction.record",
                AIActionAudit.status == "CONFIRMED",
            )
            .order_by(AIActionAudit.created_at.desc())
            .first()
        )
    finally:
        db.close()

    assert audit is not None
    transaction_id = json.loads(audit.final_payload)["id"]

    delete_result = service.chat("把这条记录删除", session_id=session_id)
    assert "删除交易草稿" in delete_result["message"]["content"]

    history = service.get_session_history(session_id)
    assert history is not None
    assert history["pending_action"] is not None
    assert history["pending_action"]["action_type"] == "transaction.delete"
    assert history["pending_action"]["draft"]["transaction_id"] == transaction_id

    confirmed = service.resume_session_action(session_id, "confirm")
    assert "已确认并删除交易" in confirmed["message"]["content"]

    transaction_service, db = service._build_transaction_service()
    try:
        deleted = transaction_service.get_transaction_by_id(transaction_id)
    finally:
        db.close()

    assert deleted is None
    service.delete_session(session_id)


def test_prepare_chat_history_appends_current_user_message(test_ledger_file):
    """传入外部 history 时，当前用户消息也应进入模型上下文。"""
    service = AIApplicationService()
    session = service.get_or_create_session()

    prepared = service._prepare_chat_history(
        [{"role": "user", "content": "本月支出分析"}],
        session,
        "具体分析下",
    )

    assert prepared[-1] == {"role": "user", "content": "具体分析下"}


def test_spending_fallback_reply_is_natural_and_detailed(test_ledger_file):
    """支出分析降级回复应避免原始结构体文本，并支持追问展开。"""
    service = AIApplicationService()

    reply = service._build_tool_fallback_reply(
        "具体分析下",
        [
            type(
                "Result",
                (),
                {
                    "skill_id": "analysis.spending",
                    "payload": {
                        "date_range": {"start_date": "2026-04-01", "end_date": "2026-04-30"},
                        "transaction_count": 2,
                        "total_expense": 3035.0,
                        "top_categories": [
                            {"category": "Meals", "amount": 3035.0, "percentage": 100.0},
                        ],
                    },
                },
            )()
        ],
    )

    assert "category" not in reply
    assert "percentage" not in reply
    assert "平均每笔约" in reply
    assert "如果你愿意，我可以继续按时间、商户或具体交易逐条展开。" in reply
