"""AI API 集成测试。"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.application.services.ai_service import AIApplicationService
from backend.config import dependencies, settings
from backend.interfaces.api import ai as ai_api
from backend.main import app


@pytest.fixture
def test_ledger_file():
    """创建临时测试账本，避免污染真实数据。"""
    temp_dir = tempfile.mkdtemp()
    test_ledger = Path(temp_dir) / "ai_api_test.beancount"
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
    original_ai_service = ai_api._ai_service

    settings.LEDGER_FILE = test_ledger
    dependencies._beancount_service = None
    ai_api._ai_service = None
    AIApplicationService._sessions = {}

    yield test_ledger

    settings.LEDGER_FILE = original_ledger
    dependencies._beancount_service = original_service
    ai_api._ai_service = original_ai_service
    AIApplicationService._sessions = {}
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def client():
    """创建测试客户端。"""
    return TestClient(app)


def _parse_sse_events(body: str) -> list[dict]:
    events = []
    for block in body.split("\n\n"):
        block = block.strip()
        if not block.startswith("data: "):
            continue
        events.append(json.loads(block[len("data: ") :]))
    return events


def test_chat_stream_returns_interrupt_sequence(client, test_ledger_file):
    """流式接口应返回交易草稿的关键事件序列。"""
    response = client.post(
        "/api/ai/chat/stream",
        json={"message": "帮我记一笔今天午饭44元", "context": {"source_page": "/ai"}},
    )

    assert response.status_code == 200

    events = _parse_sse_events(response.text)
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


def test_session_history_and_resume_work_via_api(client, test_ledger_file):
    """通过 API 应能恢复待确认草稿并继续确认。"""
    chat_response = client.post(
        "/api/ai/chat",
        json={"message": "帮我记一笔今天午饭45元", "context": {"source_page": "/ai"}},
    )
    assert chat_response.status_code == 200

    chat_data = chat_response.json()
    session_id = chat_data["session_id"]

    history_response = client.get(f"/api/ai/sessions/{session_id}")
    assert history_response.status_code == 200
    history_data = history_response.json()
    assert history_data["pending_action"] is not None
    assert history_data["pending_action"]["action_type"] == "transaction.record"

    resume_response = client.post(
        f"/api/ai/sessions/{session_id}/resume",
        json={"action": "confirm"},
    )
    assert resume_response.status_code == 200
    assert "已确认并写入账本" in resume_response.json()["message"]["content"]

    list_response = client.get("/api/ai/sessions")
    assert list_response.status_code == 200
    assert any(session["id"] == session_id for session in list_response.json()["sessions"])

    delete_response = client.delete(f"/api/ai/sessions/{session_id}")
    assert delete_response.status_code == 200


def test_delete_last_confirmed_transaction_via_api(client, test_ledger_file):
    """API 应支持基于当前会话引用删除最近一条已确认交易。"""
    chat_response = client.post(
        "/api/ai/chat",
        json={"message": "帮我记一笔今天午饭46元", "context": {"source_page": "/ai"}},
    )
    assert chat_response.status_code == 200
    session_id = chat_response.json()["session_id"]

    confirm_response = client.post(
        f"/api/ai/sessions/{session_id}/resume",
        json={"action": "confirm"},
    )
    assert confirm_response.status_code == 200

    delete_response = client.post(
        "/api/ai/chat",
        json={"session_id": session_id, "message": "把这条记录删除", "context": {"source_page": "/ai"}},
    )
    assert delete_response.status_code == 200
    assert "删除交易草稿" in delete_response.json()["message"]["content"]

    history_response = client.get(f"/api/ai/sessions/{session_id}")
    assert history_response.status_code == 200
    pending_action = history_response.json()["pending_action"]
    assert pending_action is not None
    assert pending_action["action_type"] == "transaction.delete"
    assert pending_action["draft"]["transaction_id"]

    final_confirm = client.post(
        f"/api/ai/sessions/{session_id}/resume",
        json={"action": "confirm"},
    )
    assert final_confirm.status_code == 200
    assert "已确认并删除交易" in final_confirm.json()["message"]["content"]


def test_capabilities_exposes_memory_and_tool_observability(client, test_ledger_file):
    """能力接口应暴露长期记忆与工具观测摘要。"""
    response = client.get("/api/ai/capabilities")

    assert response.status_code == 200
    data = response.json()

    assert data["graph_enabled"] is True
    assert data["skills_enabled"] is True
    assert data["subagents_enabled"] is True
    assert data["memory_enabled"] is True
    assert data["tool_observability_enabled"] is True
    assert "memory_summary" in data
    assert isinstance(data["memory_summary"], dict)
