"""Beancount服务单元测试"""
import pytest
from pathlib import Path
from backend.config import settings
from backend.infrastructure.persistence.beancount.beancount_service import BeancountService


class TestBeancountService:
    """Beancount服务测试类"""
    
    @pytest.fixture
    def service(self):
        """创建Beancount服务实例"""
        return BeancountService(settings.LEDGER_FILE)
    
    def test_service_initialization(self, service):
        """测试服务初始化"""
        assert service is not None
        assert service.ledger_path.exists()
        assert isinstance(service.entries, list)
    
    def test_get_accounts(self, service):
        """测试获取账户列表"""
        accounts = service.get_accounts()
        
        assert isinstance(accounts, list)
        assert len(accounts) >= 2  # 至少有默认的两个账户
        
        # 检查账户结构
        for account in accounts:
            assert "name" in account
            assert "currencies" in account
            assert "open_date" in account
    
    def test_get_account_balances(self, service):
        """测试获取账户余额"""
        balances = service.get_account_balances()
        
        assert isinstance(balances, dict)
        # 新账本可能没有余额，这是正常的
    
    def test_get_balance_specific_account(self, service):
        """测试获取特定账户余额"""
        from decimal import Decimal
        
        balance = service.get_balance("Assets:Unknown", "CNY")
        
        assert isinstance(balance, Decimal)
    
    def test_reload(self, service):
        """测试重新加载账本"""
        initial_count = len(service.entries)
        
        service.reload()
        
        # 重新加载后entries应该仍然可用
        assert isinstance(service.entries, list)
        assert len(service.entries) == initial_count
    
    def test_get_transactions(self, service):
        """测试获取交易列表"""
        transactions = service.get_transactions()
        
        assert isinstance(transactions, list)
        # 新账本可能没有交易
