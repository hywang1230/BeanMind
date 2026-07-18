import json

import httpx

from backend.ai.llm_client import LlmUnavailableError, OpenAICompatibleClient
from backend.infrastructure.persistence.ledger_projection import LedgerProjectionService
from backend.infrastructure.persistence.beancount.beancount_service import BeancountService
from backend.services.ledger_aggregation import LedgerAggregationService
from backend.services.monthly_budget import MonthlyBudgetService
from backend.services.monthly_review import MonthlyReviewService


def make_client(content: str) -> OpenAICompatibleClient:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer secret"
        payload = json.loads(request.content)
        assert payload["model"] == "test-model"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": content}}]},
        )

    return OpenAICompatibleClient(
        enabled=True,
        base_url="https://example.invalid/v1",
        api_key="secret",
        model="test-model",
        timeout_seconds=1,
        transport=httpx.MockTransport(handler),
    )


def test_openai_compatible_client_validates_json_and_ignores_extra_finance_fields() -> None:
    client = make_client(
        json.dumps(
            {
                "monthly_summary": "支出保持稳定",
                "next_month_suggestions": ["继续关注餐饮"],
                "total_expense": 1,
            }
        )
    )
    result = client.generate({"expense": "999"})
    assert result.monthly_summary == "支出保持稳定"
    assert not hasattr(result, "total_expense")


def test_openai_compatible_client_rejects_markdown() -> None:
    client = make_client("```json\n{}\n```")
    try:
        client.generate({})
    except LlmUnavailableError as error:
        assert "响应不可用" in str(error)
    else:
        raise AssertionError("invalid response was accepted")


def test_openai_compatible_client_handles_timeout_without_leaking_secret() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow model", request=request)

    client = OpenAICompatibleClient(
        enabled=True,
        base_url="https://example.invalid/v1",
        api_key="do-not-leak",
        model="test-model",
        timeout_seconds=0.01,
        transport=httpx.MockTransport(handler),
    )
    try:
        client.generate({"private": "do-not-log"})
    except LlmUnavailableError as error:
        assert "ReadTimeout" in str(error)
        assert "do-not-leak" not in str(error)
        assert "do-not-log" not in str(error)
    else:
        raise AssertionError("timeout was accepted")


def test_openai_compatible_client_disabled_makes_no_request() -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(500)

    client = OpenAICompatibleClient(
        enabled=False,
        base_url="https://example.invalid/v1",
        api_key="secret",
        model="test-model",
        timeout_seconds=1,
        transport=httpx.MockTransport(handler),
    )
    try:
        client.generate({})
    except LlmUnavailableError as error:
        assert "未启用" in str(error)
    else:
        raise AssertionError("disabled client made a request")
    assert called is False


def test_monthly_review_preserves_last_success_on_failed_regeneration(db_session, ledger_path) -> None:
    LedgerProjectionService(db_session, ledger_path).rebuild_all()
    aggregation = LedgerAggregationService(db_session, ledger_path)
    service = MonthlyReviewService(
        db_session,
        aggregation,
        MonthlyBudgetService(db_session, aggregation, BeancountService(ledger_path)),
        make_client(
            json.dumps(
                {
                    "monthly_summary": "一月复盘",
                    "next_month_suggestions": ["保持记录"],
                }
            )
        ),
        "CNY",
    )
    queued, should_run = service.queue("2025-01")
    assert should_run and queued["status"] == "PROCESSING"
    ready = service.process("2025-01")
    assert ready["status"] == "READY"

    failing = MonthlyReviewService(
        db_session,
        aggregation,
        MonthlyBudgetService(db_session, aggregation, BeancountService(ledger_path)),
        make_client("not-json"),
        "CNY",
    )
    _, should_run = failing.queue("2025-01", regenerate=True)
    assert should_run
    failed = failing.process("2025-01")
    assert failed["status"] == "FAILED"
    assert failed["monthly_summary"] == "一月复盘"
    assert failed["next_month_suggestions"] == ["保持记录"]
