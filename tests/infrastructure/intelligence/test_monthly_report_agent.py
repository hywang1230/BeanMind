from backend.infrastructure.intelligence.skills.monthly_report.agent import (
    MonthlyReportAgent,
    MonthlyReportModelConfig,
)


class FakeResponse:
    def __init__(self, content):
        self.content = content


class FakeChatModel:
    def __init__(self, response_text: str):
        self._response_text = response_text
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        return FakeResponse(self._response_text)


def build_facts():
    return {
        "report_month": "2026-04",
        "summary_metrics": {
            "income": "1000.00",
            "expense": "300.00",
            "balance": "700.00",
            "savings_rate": "70.00",
            "daily_expense": "10.00",
            "net_worth_change": "700.00",
            "trend_label": "改善",
            "currency": "CNY",
        },
        "spending_structure": {
            "top_categories": [{"category": "餐饮", "amount": "300.00"}],
            "fixed_expenses": [],
            "variable_expenses": [{"category": "餐饮", "amount": "300.00"}],
            "one_time_expenses": [],
        },
        "change_analysis": {
            "vs_previous_month": {"income_change": "0.00", "expense_change": "100.00"},
            "vs_recent_average": {"expense_average": "200.00", "expense_change": "100.00"},
            "drivers": [],
        },
        "anomalies": [{"type": "category_focus", "message": "支出集中在 餐饮", "amount": "300.00"}],
        "cash_flow": {
            "income": "1000.00",
            "expense": "300.00",
            "net_cash_flow": "700.00",
            "transfer_amount": "0.00",
            "repayment_amount": "0.00",
        },
        "investment": {
            "net_inflow": "0.00",
            "return": "0.00",
            "current_value": "0.00",
        },
    }


def test_monthly_report_agent_invokes_llm_and_merges_facts(monkeypatch):
    agent = MonthlyReportAgent(
        MonthlyReportModelConfig(
            provider="openai_compatible",
            model="test-model",
            base_url="https://example.com/v1",
            api_key="test-key",
        )
    )
    fake_model = FakeChatModel(
        """
        {
          "monthly_summary": "4 月支出集中在餐饮，整体仍有结余，财务表现稳定。",
          "next_month_suggestions": ["减少餐饮随手消费", "继续保持结余", "复盘异常支出"]
        }
        """
    )
    monkeypatch.setattr(agent, "_create_chat_model", lambda: fake_model)

    report = agent.generate(build_facts())

    assert fake_model.messages is not None
    assert report["monthly_summary"] == "4 月支出集中在餐饮，整体仍有结余，财务表现稳定。"
    assert report["next_month_suggestions"] == ["减少餐饮随手消费", "继续保持结余", "复盘异常支出"]
    assert report["core_metrics"]["income"] == "1000.00"
    assert report["spending_structure"]["top_categories"][0]["category"] == "餐饮"
