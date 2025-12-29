"""测试 TransactionTool"""
import sys
from pathlib import Path
from datetime import date

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.infrastructure.intelligence.agentic.tool.transaction_tool import TransactionTool
from backend.domain.transaction.entities import Transaction, Posting, TransactionFlag
from decimal import Decimal


class TestTransactionTool:
    """测试 TransactionTool"""
    
    def test_format_transactions_to_beancount(self):
        """测试格式化交易为 beancount 文本"""
        tool = TransactionTool()
        
        # 创建测试交易
        transactions = [
            Transaction(
                id="test-001",
                date=date(2025, 12, 25),
                description="测试交易",
                payee="测试商家",
                flag=TransactionFlag.CLEARED,
                postings=[
                    Posting(
                        account="Expenses:Food:Restaurant",
                        amount=Decimal("100.00"),
                        currency="CNY"
                    ),
                    Posting(
                        account="Assets:Bank:Checking",
                        amount=Decimal("-100.00"),
                        currency="CNY"
                    )
                ],
                tags={"餐饮", "聚餐"},
                links=set()
            ),
            Transaction(
                id="test-002",
                date=date(2025, 12, 26),
                description="工资收入",
                payee="公司",
                flag=TransactionFlag.CLEARED,
                postings=[
                    Posting(
                        account="Assets:Bank:Checking",
                        amount=Decimal("10000.00"),
                        currency="CNY"
                    ),
                    Posting(
                        account="Income:Salary",
                        amount=Decimal("-10000.00"),
                        currency="CNY"
                    )
                ],
                tags=set(),
                links=set()
            )
        ]
        
        # 格式化为 beancount 文本
        result = tool._format_transactions_to_beancount(transactions)
        
        # 验证结果
        assert "共找到 2 笔交易" in result
        assert "2025-12-25 * \"测试商家\" \"测试交易\"" in result
        assert "Expenses:Food:Restaurant" in result
        assert "100.00 CNY" in result
        assert "Assets:Bank:Checking" in result
        assert "-100.00 CNY" in result
        assert "2025-12-26 * \"公司\" \"工资收入\"" in result
        assert "10000.00 CNY" in result
        assert "Income:Salary" in result
        assert "-10000.00 CNY" in result
        
        # 验证标签
        assert "餐饮" in result or "聚餐" in result
        
        print("\n格式化结果：")
        print(result)
    
    def test_format_empty_transactions(self):
        """测试格式化空交易列表"""
        tool = TransactionTool()
        result = tool._format_transactions_to_beancount([])
        assert result == "未找到符合条件的交易记录"
    
    def test_format_transaction_with_tags_and_links(self):
        """测试格式化带标签和链接的交易"""
        tool = TransactionTool()
        
        # 创建一个带标签和链接的交易
        transaction = Transaction(
            id="test-003",
            date=date(2025, 12, 27),
            description="购物",
            payee="超市",
            flag=TransactionFlag.PENDING,
            postings=[
                Posting(
                    account="Expenses:Shopping",
                    amount=Decimal("200.00"),
                    currency="CNY"
                ),
                Posting(
                    account="Assets:Bank:Checking",
                    amount=Decimal("-200.00"),
                    currency="CNY"
                )
            ],
            tags={"生活", "日用品"},
            links={"receipt-001"}
        )
        
        result = tool._format_transactions_to_beancount([transaction])
        
        # 验证结果包含标签和链接
        assert "生活" in result or "日用品" in result
        assert "receipt-001" in result
        assert "!" in result  # PENDING 标记
        
        print("\n带标签和链接的交易格式化结果：")
        print(result)


if __name__ == "__main__":
    # 运行测试
    test = TestTransactionTool()
    test.test_format_transactions_to_beancount()
    test.test_format_empty_transactions()
    test.test_format_transaction_with_tags_and_links()
    print("\n所有测试通过！")

