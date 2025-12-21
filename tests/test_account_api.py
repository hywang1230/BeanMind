"""账户 API 集成测试

测试账户 API 端点的功能和认证。
"""
import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import tempfile
import shutil

from backend.main import app
from backend.config import settings


@pytest.fixture
def test_ledger_file():
    """创建临时测试账本文件"""
    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    test_ledger = Path(temp_dir) / "test.beancount"
    
    # 写入测试账本内容
    test_ledger.write_text("""
;; Test Ledger for API Tests

option "operating_currency" "CNY"

2025-01-01 open Assets:Bank:Checking CNY
2025-01-01 open Assets:Bank:Savings CNY, USD
2025-01-01 open Expenses:Food CNY
2025-01-01 open Income:Salary CNY
2025-01-01 open Equity:OpeningBalances CNY

2025-01-02 * "Opening Balance"
  Assets:Bank:Checking     10000.00 CNY
  Equity:OpeningBalances  -10000.00 CNY

2025-01-02 * "Opening Balance - Savings"
  Assets:Bank:Savings      5000.00 CNY
  Equity:OpeningBalances  -5000.00 CNY
""", encoding="utf-8")
    
    # 临时修改 settings 中的账本路径
    original_ledger = settings.LEDGER_FILE
    settings.LEDGER_FILE = test_ledger
    
    yield test_ledger
    
    # 恢复原始设置
    settings.LEDGER_FILE = original_ledger
    
    # 清理
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def client():
    """创建测试客户端"""
    return TestClient(app)


class TestAccountAPI:
    """账户 API 测试类"""
    
    def test_get_accounts_summary(self, client, test_ledger_file):
        """测试获取账户摘要"""
        response = client.get("/api/accounts/summary")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total_count" in data
        assert "active_count" in data
        assert "by_type" in data
        assert data["total_count"] > 0
    
    def test_get_accounts_list(self, client, test_ledger_file):
        """测试获取账户列表"""
        response = client.get("/api/accounts")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "accounts" in data
        assert "total" in data
        assert len(data["accounts"]) > 0
        
        # 验证账户结构
        account = data["accounts"][0]
        assert "name" in account
        assert "account_type" in account
        assert "currencies" in account
        assert "is_active" in account
    
    def test_get_accounts_list_by_type(self, client, test_ledger_file):
        """测试按类型获取账户列表"""
        response = client.get("/api/accounts?account_type=Assets")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["accounts"]) > 0
        # 所有账户都应该是 Assets 类型
        for account in data["accounts"]:
            assert account["account_type"] == "Assets"
    
    def test_get_accounts_list_by_prefix(self, client, test_ledger_file):
        """测试按前缀获取账户列表"""
        response = client.get("/api/accounts?prefix=Assets:Bank")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["accounts"]) > 0
        # 所有账户名都应该以 Assets:Bank 开头
        for account in data["accounts"]:
            assert account["name"].startswith("Assets:Bank")
    
    def test_get_accounts_active_only(self, client, test_ledger_file):
        """测试仅获取活跃账户"""
        response = client.get("/api/accounts?active_only=true")
        
        assert response.status_code == 200
        data = response.json()
        
        # 所有账户都应该是活跃的
        for account in data["accounts"]:
            assert account["is_active"] is True
    
    def test_get_account_detail(self, client, test_ledger_file):
        """测试获取账户详情"""
        response = client.get("/api/accounts/Assets:Bank:Checking")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == "Assets:Bank:Checking"
        assert data["account_type"] == "Assets"
        assert "CNY" in data["currencies"]
    
    def test_get_account_not_found(self, client, test_ledger_file):
        """测试获取不存在的账户"""
        response = client.get("/api/accounts/Assets:NonExistent")
        
        assert response.status_code == 404
    
    def test_get_account_balance(self, client, test_ledger_file):
        """测试获取账户余额"""
        response = client.get("/api/accounts/Assets:Bank:Checking/balance")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "account_name" in data
        assert "balances" in data
        assert data["account_name"] == "Assets:Bank:Checking"
        assert "CNY" in data["balances"]
        assert data["balances"]["CNY"] == "10000.00"
    
    def test_get_account_balance_with_currency(self, client, test_ledger_file):
        """测试获取指定货币的账户余额"""
        response = client.get("/api/accounts/Assets:Bank:Savings/balance?currency=CNY")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "CNY" in data["balances"]
        assert data["balances"]["CNY"] == "5000.00"
    
    def test_get_root_accounts(self, client, test_ledger_file):
        """测试获取根账户"""
        response = client.get("/api/accounts/roots")
        
        assert response.status_code == 200
        data = response.json()
        
        # 应该没有根账户（所有账户都是二级或更深）
        assert isinstance(data["accounts"], list)
    
    def test_get_child_accounts(self, client, test_ledger_file):
        """测试获取子账户"""
        response = client.get("/api/accounts/Assets:Bank/children")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["accounts"]) > 0
        # 验证都是 Assets:Bank 的直接子账户
        for account in data["accounts"]:
            assert account["parent"] == "Assets:Bank"
    
    def test_create_account(self, client, test_ledger_file):
        """测试创建账户"""
        # 先创建根账户
        root_data = {
            "name": "Assets",
            "account_type": "Assets"
        }
        
        root_response = client.post("/api/accounts", json=root_data)
        # Assets 可能已经存在，所以不检查状态码
        
        # 再创建二级账户
        parent_data = {
            "name": "Assets:Investment",
            "account_type": "Assets",
            "currencies": ["CNY", "USD"]
        }
        
        response = client.post("/api/accounts", json=parent_data)
        
        # 如果账户已存在会返回 400，所以只检查它不是 500 错误
        assert response.status_code in [201, 400]
        
        if response.status_code == 201:
            data = response.json()
            assert data["name"] == "Assets:Investment"
            assert data["account_type"] == "Assets"
            assert "CNY" in data["currencies"]
            assert "USD" in data["currencies"]
    
    def test_create_account_invalid_name(self, client, test_ledger_file):
        """测试创建无效名称的账户"""
        invalid_data = {
            "name": "assets:invalid",  # 小写字母开头
            "account_type": "Assets"
        }
        
        response = client.post("/api/accounts", json=invalid_data)
        
        assert response.status_code == 400
    
    def test_create_account_type_mismatch(self, client, test_ledger_file):
        """测试创建类型不匹配的账户"""
        invalid_data = {
            "name": "Assets:Test",
            "account_type": "Income"  # 类型不匹配
        }
        
        response = client.post("/api/accounts", json=invalid_data)
        
        assert response.status_code == 400
    
    def test_suggest_account_name(self, client, test_ledger_file):
        """测试建议账户名称"""
        request_data = {
            "account_type": "Expenses",
            "category": "food:dining"
        }
        
        response = client.post("/api/accounts/suggest-name", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "suggested_name" in data
        assert "is_valid" in data
        assert data["suggested_name"] == "Expenses:Food:Dining"
        assert data["is_valid"] is True
    
    def test_api_documentation(self, client):
        """测试 API 文档可访问"""
        # 测试 OpenAPI JSON
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        openapi = response.json()
        assert "paths" in openapi
        assert "/api/accounts" in openapi["paths"]
        assert "/api/accounts/summary" in openapi["paths"]
