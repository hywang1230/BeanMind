"""Transaction 领域实体单元测试

测试 Transaction 实体的所有功能。
"""
import pytest
from datetime import date, datetime
from decimal import Decimal

from backend.domain.transaction.entities import (
    Transaction,
    TransactionType,
    TransactionFlag,
    Posting
)


class TestTransactionType:
    """交易类型枚举测试类"""
    
    def test_transaction_types(self):
        """测试所有交易类型"""
        assert TransactionType.EXPENSE.value == "expense"
        assert TransactionType.INCOME.value == "income"
        assert TransactionType.TRANSFER.value == "transfer"
        assert TransactionType.OPENING.value == "opening"
        assert TransactionType.OTHER.value == "other"


class TestTransactionFlag:
    """交易标记枚举测试类"""
    
    def test_transaction_flags(self):
        """测试所有交易标记"""
        assert TransactionFlag.CLEARED.value == "*"
        assert TransactionFlag.PENDING.value == "!"


class TestTransaction:
    """Transaction 实体测试类"""
    
    def test_create_transaction_minimal(self):
        """测试创建交易（最小数据）"""
        postings = [
            Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
            Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
        ]
        
        txn = Transaction(
            date=date(2025, 1, 15),
            description="午餐",
            postings=postings
        )
        
        assert txn.date == date(2025, 1, 15)
        assert txn.description == "午餐"
        assert len(txn.postings) == 2
        assert txn.payee is None
        assert txn.flag == TransactionFlag.CLEARED
        assert len(txn.tags) == 0
        assert len(txn.links) == 0
    
    def test_create_transaction_full(self):
        """测试创建交易（完整数据）"""
        postings = [
            Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
            Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
        ]
        
        now = datetime.now()
        txn = Transaction(
            id="txn-001",
            date=date(2025, 1, 15),
            description="午餐",
            payee="麦当劳",
            flag=TransactionFlag.PENDING,
            postings=postings,
            tags={"lunch", "fastfood"},
            links={"receipt-123"},
            meta={"source": "import"},
            created_at=now,
            updated_at=now
        )
        
        assert txn.id == "txn-001"
        assert txn.payee == "麦当劳"
        assert txn.flag == TransactionFlag.PENDING
        assert "lunch" in txn.tags
        assert "receipt-123" in txn.links
        assert txn.meta["source"] == "import"
    
    def test_date_validation_empty(self):
        """测试日期验证（空日期）"""
        with pytest.raises(ValueError, match="交易日期不能为空"):
            Transaction(
                date=None,
                description="测试",
                postings=[]
            )
    
    def test_description_optional(self):
        """测试描述可选（空描述不抛错）"""
        postings = [
            Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
            Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
        ]
        
        # 空描述应该不会抛错
        txn = Transaction(
            date=date.today(),
            postings=postings
        )
        assert txn.description is None
        
        # 空字符串描述也应该允许
        txn2 = Transaction(
            date=date.today(),
            description="",
            postings=postings
        )
        assert txn2.description == ""
    
    def test_postings_validation_insufficient(self):
        """测试记账分录验证（少于两个）"""
        with pytest.raises(ValueError, match="交易至少需要两个记账分录"):
            Transaction(
                date=date.today(),
                description="测试",
                postings=[
                    Posting(account="Assets:Bank", amount=Decimal("100"), currency="CNY")
                ]
            )
    
    def test_balance_validation_unbalanced(self):
        """测试借贷平衡验证（不平衡）"""
        postings = [
            Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
            Posting(account="Assets:Cash", amount=Decimal("-40"), currency="CNY")  # 不平衡
        ]
        
        with pytest.raises(ValueError, match="交易不平衡"):
            Transaction(
                date=date.today(),
                description="测试",
                postings=postings
            )
    
    def test_balance_validation_balanced(self):
        """测试借贷平衡验证（平衡）"""
        postings = [
            Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
            Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
        ]
        
        txn = Transaction(
            date=date.today(),
            description="测试",
            postings=postings
        )
        
        assert txn is not None
    
    def test_balance_validation_multi_currency(self):
        """测试多货币借贷平衡验证"""
        postings = [
            Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
            Posting(account="Expenses:Shopping", amount=Decimal("10"), currency="USD"),
            Posting(account="Assets:Cash:CNY", amount=Decimal("-50"), currency="CNY"),
            Posting(account="Assets:Cash:USD", amount=Decimal("-10"), currency="USD")
        ]
        
        txn = Transaction(
            date=date.today(),
            description="多货币交易",
            postings=postings
        )
        
        assert txn is not None
    
    def test_balance_validation_multi_currency_unbalanced(self):
        """测试多货币借贷平衡验证（不平衡）"""
        postings = [
            Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
            Posting(account="Expenses:Shopping", amount=Decimal("10"), currency="USD"),
            Posting(account="Assets:Cash:CNY", amount=Decimal("-50"), currency="CNY"),
            Posting(account="Assets:Cash:USD", amount=Decimal("-5"), currency="USD")  # 不平衡
        ]
        
        with pytest.raises(ValueError, match="交易不平衡"):
            Transaction(
                date=date.today(),
                description="测试",
                postings=postings
            )
    
    def test_add_posting(self):
        """测试添加记账分录"""
        postings = [
            Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
            Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
        ]
        
        txn = Transaction(
            date=date.today(),
            description="测试",
            postings=postings
        )
        
        # 添加新的分录（此时会不平衡，但不会自动抛异常）
        new_posting = Posting(account="Expenses:Tax", amount=Decimal("5"), currency="CNY")
        txn.add_posting(new_posting)
        
        assert len(txn.postings) == 3
    
    def test_remove_posting(self):
        """测试移除记账分录"""
        posting1 = Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY")
        posting2 = Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
        
        txn = Transaction(
            date=date.today(),
            description="测试",
            postings=[posting1, posting2]
        )
        
        txn.remove_posting(posting1)
        assert len(txn.postings) == 1
    
    def test_add_tag(self):
        """测试添加标签"""
        txn = Transaction(
            date=date.today(),
            description="测试",
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
        
        txn.add_tag("lunch")
        txn.add_tag("dining")
        
        assert txn.has_tag("lunch")
        assert txn.has_tag("dining")
    
    def test_add_tag_validation_empty(self):
        """测试添加标签验证（空标签）"""
        txn = Transaction(
            date=date.today(),
            description="测试",
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
        
        with pytest.raises(ValueError, match="标签不能为空"):
            txn.add_tag("")
    
    def test_remove_tag(self):
        """测试移除标签"""
        txn = Transaction(
            date=date.today(),
            description="测试",
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ],
            tags={"lunch", "dining"}
        )
        
        txn.remove_tag("lunch")
        assert not txn.has_tag("lunch")
        assert txn.has_tag("dining")
    
    def test_add_link(self):
        """测试添加链接"""
        txn = Transaction(
            date=date.today(),
            description="测试",
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
        
        txn.add_link("receipt-123")
        assert txn.has_link("receipt-123")
    
    def test_remove_link(self):
        """测试移除链接"""
        txn = Transaction(
            date=date.today(),
            description="测试",
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ],
            links={"receipt-123"}
        )
        
        txn.remove_link("receipt-123")
        assert not txn.has_link("receipt-123")
    
    def test_get_accounts(self):
        """测试获取涉及的账户"""
        postings = [
            Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
            Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
        ]
        
        txn = Transaction(
            date=date.today(),
            description="测试",
            postings=postings
        )
        
        accounts = txn.get_accounts()
        assert "Expenses:Food" in accounts
        assert "Assets:Cash" in accounts
    
    def test_get_currencies(self):
        """测试获取涉及的货币"""
        postings = [
            Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
            Posting(account="Expenses:Shopping", amount=Decimal("10"), currency="USD"),
            Posting(account="Assets:Cash:CNY", amount=Decimal("-50"), currency="CNY"),
            Posting(account="Assets:Cash:USD", amount=Decimal("-10"), currency="USD")
        ]
        
        txn = Transaction(
            date=date.today(),
            description="测试",
            postings=postings
        )
        
        currencies = txn.get_currencies()
        assert "CNY" in currencies
        assert "USD" in currencies
    
    def test_get_total_amount(self):
        """测试获取指定货币的总金额"""
        postings = [
            Posting(account="Expenses:Food", amount=Decimal("30"), currency="CNY"),
            Posting(account="Expenses:Transport", amount=Decimal("20"), currency="CNY"),
            Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
        ]
        
        txn = Transaction(
            date=date.today(),
            description="测试",
            postings=postings
        )
        
        total = txn.get_total_amount("CNY")
        assert total == Decimal("100")  # |30| + |20| + |-50| = 100
    
    def test_detect_transaction_type_expense(self):
        """测试检测交易类型（支出）"""
        postings = [
            Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
            Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
        ]
        
        txn = Transaction(
            date=date.today(),
            description="午餐",
            postings=postings
        )
        
        assert txn.detect_transaction_type() == TransactionType.EXPENSE
    
    def test_detect_transaction_type_income(self):
        """测试检测交易类型（收入）"""
        postings = [
            Posting(account="Assets:Bank", amount=Decimal("5000"), currency="CNY"),
            Posting(account="Income:Salary", amount=Decimal("-5000"), currency="CNY")
        ]
        
        txn = Transaction(
            date=date.today(),
            description="工资",
            postings=postings
        )
        
        assert txn.detect_transaction_type() == TransactionType.INCOME
    
    def test_detect_transaction_type_transfer(self):
        """测试检测交易类型（转账）"""
        postings = [
            Posting(account="Assets:Bank:Checking", amount=Decimal("1000"), currency="CNY"),
            Posting(account="Assets:Bank:Savings", amount=Decimal("-1000"), currency="CNY")
        ]
        
        txn = Transaction(
            date=date.today(),
            description="转账",
            postings=postings
        )
        
        assert txn.detect_transaction_type() == TransactionType.TRANSFER
    
    def test_detect_transaction_type_opening(self):
        """测试检测交易类型（期初余额）"""
        postings = [
            Posting(account="Assets:Bank", amount=Decimal("10000"), currency="CNY"),
            Posting(account="Equity:OpeningBalances", amount=Decimal("-10000"), currency="CNY")
        ]
        
        txn = Transaction(
            date=date.today(),
            description="期初余额",
            postings=postings
        )
        
        assert txn.detect_transaction_type() == TransactionType.OPENING
    
    def test_is_cleared(self):
        """测试判断是否已清算"""
        txn = Transaction(
            date=date.today(),
            description="测试",
            flag=TransactionFlag.CLEARED,
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
        
        assert txn.is_cleared() is True
        assert txn.is_pending() is False
    
    def test_is_pending(self):
        """测试判断是否待清算"""
        txn = Transaction(
            date=date.today(),
            description="测试",
            flag=TransactionFlag.PENDING,
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
        
        assert txn.is_pending() is True
        assert txn.is_cleared() is False
    
    def test_mark_as_cleared(self):
        """测试标记为已清算"""
        txn = Transaction(
            date=date.today(),
            description="测试",
            flag=TransactionFlag.PENDING,
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
        
        txn.mark_as_cleared()
        assert txn.is_cleared() is True
    
    def test_mark_as_pending(self):
        """测试标记为待清算"""
        txn = Transaction(
            date=date.today(),
            description="测试",
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
        
        txn.mark_as_pending()
        assert txn.is_pending() is True
    
    def test_to_dict(self):
        """测试转换为字典"""
        now = datetime(2025, 1, 15, 12, 0, 0)
        postings = [
            Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
            Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
        ]
        
        txn = Transaction(
            id="txn-001",
            date=date(2025, 1, 15),
            description="午餐",
            payee="麦当劳",
            flag=TransactionFlag.CLEARED,
            postings=postings,
            tags={"lunch"},
            links={"receipt-123"},
            meta={"note": "test"},
            created_at=now,
            updated_at=now
        )
        
        data = txn.to_dict()
        
        assert data["id"] == "txn-001"
        assert data["date"] == "2025-01-15"
        assert data["description"] == "午餐"
        assert data["payee"] == "麦当劳"
        assert data["flag"] == "*"
        assert len(data["postings"]) == 2
        assert "lunch" in data["tags"]
        assert "receipt-123" in data["links"]
        assert data["transaction_type"] == "expense"
    
    def test_from_dict(self):
        """测试从字典创建"""
        now = datetime(2025, 1, 15, 12, 0, 0)
        data = {
            "id": "txn-001",
            "date": "2025-01-15",
            "description": "午餐",
            "payee": "麦当劳",
            "flag": "*",
            "postings": [
                {"account": "Expenses:Food", "amount": "50", "currency": "CNY"},
                {"account": "Assets:Cash", "amount": "-50", "currency": "CNY"}
            ],
            "tags": ["lunch"],
            "links": ["receipt-123"],
            "meta": {"note": "test"},
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }
        
        txn = Transaction.from_dict(data)
        
        assert txn.id == "txn-001"
        assert txn.date == date(2025, 1, 15)
        assert txn.description == "午餐"
        assert txn.payee == "麦当劳"
        assert txn.flag == TransactionFlag.CLEARED
        assert len(txn.postings) == 2
        assert "lunch" in txn.tags
        assert "receipt-123" in txn.links
    
    def test_repr(self):
        """测试字符串表示"""
        postings = [
            Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
            Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
        ]
        
        txn = Transaction(
            date=date(2025, 1, 15),
            description="午餐",
            postings=postings
        )
        
        repr_str = repr(txn)
        assert "2025-01-15" in repr_str
        assert "午餐" in repr_str
        assert "expense" in repr_str
        assert "CNY" in repr_str
