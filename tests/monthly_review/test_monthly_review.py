import json
from decimal import Decimal

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


def valid_model_payload(**overrides) -> str:
    payload = {
        "monthly_summary": "本月收支总体平稳。\n\n餐饮支出仍是主要构成，建议继续观察。",
        "highlights": ["餐饮占比最高"],
        "next_month_suggestions": ["继续关注餐饮", "核对预算执行"],
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_openai_compatible_client_validates_json_and_ignores_extra_finance_fields() -> None:
    client = make_client(
        valid_model_payload(total_expense=1, fabricated_net="999")
    )
    result = client.generate({"expense": "999"})
    assert "平稳" in result.monthly_summary
    assert result.highlights == ["餐饮占比最高"]
    assert result.next_month_suggestions == ["继续关注餐饮", "核对预算执行"]
    assert not hasattr(result, "total_expense")


def test_openai_compatible_client_rejects_too_many_suggestions() -> None:
    client = make_client(
        valid_model_payload(
            next_month_suggestions=["a", "b", "c", "d", "e", "f"],
        )
    )
    try:
        client.generate({})
    except LlmUnavailableError as error:
        assert "响应不可用" in str(error)
    else:
        raise AssertionError("over-limit suggestions were accepted")


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


def _service(db_session, ledger_path, client=None, beancount=None) -> MonthlyReviewService:
    aggregation = LedgerAggregationService(db_session, ledger_path)
    bean = beancount or BeancountService(ledger_path)
    return MonthlyReviewService(
        db_session,
        aggregation,
        MonthlyBudgetService(db_session, aggregation, bean),
        client or make_client(valid_model_payload()),
        bean.get_operating_currency() if hasattr(bean, "get_operating_currency") else "CNY",
    )


def test_build_facts_uses_operating_currency_scalars(db_session, ledger_path) -> None:
    LedgerProjectionService(db_session, ledger_path).rebuild_all()
    service = _service(db_session, ledger_path)
    facts = service.build_facts("2025-01")
    assert facts["currency"] == "CNY"
    assert facts["current"]["income"] == "10000"
    assert facts["current"]["expense"] == "50"
    assert facts["current"]["net"] == "9950"
    assert facts["previous"]["income"] == "0"
    assert facts["previous"]["expense"] == "131.456789123456789"
    assert facts["changes"]["income_delta"] == "10000"
    assert facts["changes"]["expense_delta"] == "-81.456789123456789"
    assert facts["changes"]["income_change_rate"] is None
    assert facts["top_expense_categories"][0]["name"] == "Food"
    assert facts["top_expense_categories"][0]["amount"] == "50"
    assert facts["top_income_categories"][0]["name"] == "Salary"
    assert facts["top_income_categories"][0]["amount"] == "10000"
    assert facts["missing_exchange_rates"] == []
    assert isinstance(Decimal(facts["current"]["income"]), Decimal)


def test_build_facts_converts_foreign_currency_and_lists_missing_rates(
    db_session, ledger_path
) -> None:
    LedgerProjectionService(db_session, ledger_path).rebuild_all()
    service = _service(db_session, ledger_path)
    facts = service.build_facts("2025-02")
    # 99.99 USD * 7.20 = 719.928
    assert facts["currency"] == "CNY"
    assert Decimal(facts["current"]["expense"]) == Decimal("99.990000000000001") * Decimal("7.20")
    assert facts["top_expense_categories"][0]["name"] == "Travel"
    assert Decimal(facts["top_expense_categories"][0]["amount"]) == Decimal("99.990000000000001") * Decimal("7.20")

    class NoRateBean:
        def get_operating_currency(self):
            return "CNY"

        def get_all_exchange_rates(self, to_currency="CNY", as_of_date=None):
            return {"CNY": Decimal("1")}

    missing_service = _service(db_session, ledger_path, beancount=NoRateBean())
    missing_facts = missing_service.build_facts("2025-02")
    assert missing_facts["current"]["expense"] == "0"
    assert "USD" in missing_facts["missing_exchange_rates"]


def test_build_facts_empty_month_without_budget(db_session, ledger_path) -> None:
    LedgerProjectionService(db_session, ledger_path).rebuild_all()
    service = _service(db_session, ledger_path)
    facts = service.build_facts("2025-03")
    assert facts["current"] == {"income": "0", "expense": "0", "net": "0"}
    assert facts["top_expense_categories"] == []
    assert facts["top_income_categories"] == []
    assert facts["budget"]["total"] == "0"
    assert facts["budget"]["items"] == []
    assert facts["risk_items"] == []


def test_category_totals_come_from_sql_projection(db_session, ledger_path) -> None:
    LedgerProjectionService(db_session, ledger_path).rebuild_all()
    aggregation = LedgerAggregationService(db_session, ledger_path)
    totals = aggregation.monthly_category_currency_totals("2025-01", "Expenses")
    assert totals == {"Food": {"CNY": Decimal("50")}}
    income = aggregation.monthly_category_currency_totals("2025-01", "Income")
    assert income == {"Salary": {"CNY": Decimal("-10000")}}


def test_monthly_review_preserves_last_success_on_failed_regeneration(
    db_session, ledger_path
) -> None:
    LedgerProjectionService(db_session, ledger_path).rebuild_all()
    service = _service(
        db_session,
        ledger_path,
        client=make_client(
            valid_model_payload(
                monthly_summary="一月复盘",
                highlights=["结余稳定"],
                next_month_suggestions=["保持记录"],
            )
        ),
    )
    queued, should_run = service.queue("2025-01")
    assert should_run and queued["status"] == "PROCESSING"
    ready = service.process("2025-01")
    assert ready["status"] == "READY"
    assert ready["highlights"] == ["结余稳定"]
    assert ready["next_month_suggestions"] == ["保持记录"]
    assert ready["facts"]["currency"] == "CNY"

    failing = _service(db_session, ledger_path, client=make_client("not-json"))
    _, should_run = failing.queue("2025-01", regenerate=True)
    assert should_run
    failed = failing.process("2025-01")
    assert failed["status"] == "FAILED"
    assert failed["monthly_summary"] == "一月复盘"
    assert failed["highlights"] == ["结余稳定"]
    assert failed["next_month_suggestions"] == ["保持记录"]


def test_response_reads_legacy_suggestions_array(db_session, ledger_path) -> None:
    LedgerProjectionService(db_session, ledger_path).rebuild_all()
    service = _service(db_session, ledger_path)
    from backend.infrastructure.persistence.db.models import MonthlyReview
    from datetime import datetime

    record = MonthlyReview(
        report_month="2025-01",
        generation_status="READY",
        facts_json=json.dumps(service.build_facts("2025-01"), ensure_ascii=False),
        summary_text="旧总结",
        suggestions_json=json.dumps(["旧建议"], ensure_ascii=False),
        last_success_at=datetime.now(),
    )
    db_session.add(record)
    db_session.commit()
    response = service.response("2025-01")
    assert response["highlights"] == []
    assert response["next_month_suggestions"] == ["旧建议"]
