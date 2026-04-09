"""只读 AI 工具测试。"""

from decimal import Decimal

from backend.infrastructure.intelligence.langgraph.tools.read_only_tools import ReadOnlyToolExecutor


def test_select_funding_account_prefers_matching_credit_card():
    """提到信用卡卡名时，应优先命中负债账户。"""
    executor = ReadOnlyToolExecutor()
    account_names = [
        "Assets:Bank:Checking",
        "Liabilities:CreditCard:CMB:Platinum",
        "Liabilities:CreditCard:ICBC:Travel",
    ]

    selected, decision = executor._select_funding_account(account_names, "今天午饭100，Platinum 信用卡支付")

    assert selected == "Liabilities:CreditCard:CMB:Platinum"
    assert decision["source"] == "account_name_match"


def test_select_funding_account_matches_numeric_account_hint():
    """消息包含账户显式片段时，应从真实账户树动态命中。"""
    executor = ReadOnlyToolExecutor()
    account_names = [
        "Assets:Bank:Checking",
        "Liabilities:CreditCard:CMB:5566",
        "Liabilities:CreditCard:CMB:8164",
    ]

    selected, decision = executor._select_funding_account(account_names, "晚饭100，8164 账户支付")

    assert selected == "Liabilities:CreditCard:CMB:8164"
    assert decision["source"] == "account_name_match"


def test_select_funding_account_ignores_test_asset_preference():
    """测试账户不应作为默认资金账户被复用。"""
    executor = ReadOnlyToolExecutor()
    account_names = [
        "Assets:AITestTempAccount",
        "Assets:Bank:Checking",
        "Assets:Wallet:Cash",
    ]

    selected, _ = executor._select_funding_account(
        account_names,
        "今天吃饭花了100",
        {"preferred_asset_account": "Assets:AITestTempAccount"},
    )

    assert selected != "Assets:AITestTempAccount"
    assert selected in {"Assets:Bank:Checking", "Assets:Wallet:Cash"}


def test_select_funding_account_prefers_user_memory_when_message_is_ambiguous():
    """消息不明确时，应优先复用用户偏好账户。"""
    executor = ReadOnlyToolExecutor()
    account_names = [
        "Assets:Bank:Checking",
        "Assets:Wallet:Cash",
    ]

    selected, decision = executor._select_funding_account(
        account_names,
        "午饭62元",
        {"preferred_asset_account": "Assets:Wallet:Cash"},
    )

    assert selected == "Assets:Wallet:Cash"
    assert decision["source"] == "preference"


def test_select_counterparty_account_prefers_payee_memory():
    """存在 payee 历史映射时，应优先复用对手方账户。"""
    executor = ReadOnlyToolExecutor()
    account_names = [
        "Expenses:Meals",
        "Expenses:Transport",
        "Income:Salary",
    ]

    selected, decision = executor._select_counterparty_account(
        account_names,
        "在楼下餐馆午饭58元",
        "expense",
        {"payee_account_map": {"楼下餐馆": "Expenses:Meals"}},
        payee="楼下餐馆",
    )

    assert selected == "Expenses:Meals"
    assert decision["source"] == "payee_preference"


def test_infer_description_falls_back_to_neutral_text_without_history():
    """没有明确商户和历史时，描述应退化为中性文案。"""
    executor = ReadOnlyToolExecutor()
    description, decision = executor._infer_description(
        "帮我记一笔 88 元",
        "expense",
        None,
        [],
        ["Assets:Bank:Checking", "Expenses:Meals"],
    )

    assert description == "支出"
    assert decision["source"] == "fallback"


def test_query_transactions_keeps_amount_in_simplified_payload(monkeypatch):
    """交易查询上下文应保留金额，避免回答层丢失消费额。"""
    executor = ReadOnlyToolExecutor()

    class _FakeService:
        def get_transactions(self, **kwargs):
            return [
                {
                    "id": "txn-1",
                    "date": "2026-04-09",
                    "description": "吃饭",
                    "payee": None,
                    "transaction_type": "expense",
                    "accounts": ["Expenses:Meals", "Assets:Bank:Checking"],
                    "currencies": ["CNY"],
                    "postings": [
                        {"account": "Expenses:Meals", "amount": "100.00", "currency": "CNY"},
                        {"account": "Assets:Bank:Checking", "amount": "-100.00", "currency": "CNY"},
                    ],
                }
            ]

    class _FakeDB:
        def close(self):
            return None

    monkeypatch.setattr(executor, "_build_transaction_service", lambda: (_FakeService(), _FakeDB()))

    result = executor.query_transactions("今日消费情况")

    assert result.payload["transactions"][0]["amount"] == 100.0
    assert result.payload["transactions"][0]["postings"][0]["amount"] == "100.00"


def test_explain_report_treats_account_balance_overview_as_balance_sheet(monkeypatch):
    """账户余额概览应返回余额类摘要，而不是期间损益。"""
    executor = ReadOnlyToolExecutor()

    class _FakeBeancountService:
        def get_all_exchange_rates(self, to_currency="CNY", as_of_date=None):
            return {"CNY": Decimal("1")}

        def get_account_balances(self, as_of_date=None):
            return {
                "Assets:Bank:Checking": {"CNY": Decimal("1000.00")},
                "Liabilities:CreditCard": {"CNY": Decimal("-200.00")},
                "Equity:OpeningBalances": {"CNY": Decimal("-800.00")},
            }

    monkeypatch.setattr(
        "backend.infrastructure.intelligence.langgraph.tools.read_only_tools.get_beancount_service",
        lambda: _FakeBeancountService(),
    )

    result = executor.explain_report("账户余额概览")

    assert result.payload["report_type"] == "balance_sheet"
    assert result.payload["total_assets_cny"] == 1000.0
    assert result.payload["total_liabilities_cny"] == 200.0
