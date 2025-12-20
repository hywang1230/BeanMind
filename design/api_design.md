# BeanMind API 接口设计

## 1. API 设计原则

### 1.1 RESTful 规范
- 使用标准HTTP方法：GET、POST、PUT、PATCH、DELETE
- 资源导向的URL设计
- 统一的响应格式
- 合理的HTTP状态码

### 1.2 统一响应格式

```typescript
// 成功响应
{
  "success": true,
  "data": any,
  "message": string | null
}

// 错误响应
{
  "success": false,
  "error": {
    "code": string,
    "message": string,
    "details": any
  }
}
```

### 1.3 分页响应

```typescript
{
  "success": true,
  "data": {
    "items": any[],
    "pagination": {
      "page": number,
      "page_size": number,
      "total": number,
      "total_pages": number
    }
  }
}
```

## 2. 认证接口

### 2.1 POST /api/auth/login
登录获取访问令牌

**请求**：
```json
{
  "username": "admin",
  "password": "password"
}
```

**响应**：
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "Bearer",
    "expires_in": 86400,
    "user": {
      "id": "uuid",
      "username": "admin",
      "display_name": "管理员"
    }
  }
}
```

### 2.2 POST /api/auth/refresh
刷新访问令牌

**请求头**：
```
Authorization: Bearer <access_token>
```

**响应**：同登录响应

### 2.3 GET /api/auth/me
获取当前用户信息

**响应**：
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "username": "admin",
    "display_name": "管理员",
    "created_at": "2025-01-01T00:00:00Z"
  }
}
```

## 3. 账户接口

### 3.1 GET /api/accounts
获取账户列表（树形结构）

**查询参数**：
- `type`: 账户类型（Assets, Liabilities, Equity, Income, Expenses）
- `include_closed`: 是否包含已关闭账户（默认false）

**响应**：
```json
{
  "success": true,
  "data": [
    {
      "name": "Assets",
      "full_name": "Assets",
      "type": "Assets",
      "currencies": ["CNY", "USD"],
      "is_closed": false,
      "children": [
        {
          "name": "Bank",
          "full_name": "Assets:Bank",
          "type": "Assets",
          "currencies": ["CNY"],
          "children": [
            {
              "name": "ICBC",
              "full_name": "Assets:Bank:ICBC",
              "type": "Assets",
              "currencies": ["CNY"],
              "balance": {
                "CNY": 15000.00
              },
              "is_closed": false,
              "children": []
            }
          ]
        }
      ]
    }
  ]
}
```

### 3.2 POST /api/accounts
创建新账户

**请求**：
```json
{
  "name": "Assets:Bank:CMB",
  "currencies": ["CNY"],
  "open_date": "2025-01-01",
  "description": "招商银行储蓄卡"
}
```

**响应**：
```json
{
  "success": true,
  "data": {
    "name": "CMB",
    "full_name": "Assets:Bank:CMB",
    "currencies": ["CNY"],
    "open_date": "2025-01-01",
    "is_closed": false
  },
  "message": "账户创建成功"
}
```

### 3.3 GET /api/accounts/{account_name}/balance
获取账户余额

**路径参数**：
- `account_name`: 账户全名，如 `Assets:Bank:ICBC`

**查询参数**：
- `date`: 查询日期（默认今天）

**响应**：
```json
{
  "success": true,
  "data": {
    "account": "Assets:Bank:ICBC",
    "balances": {
      "CNY": 15000.00
    },
    "as_of_date": "2025-01-15"
  }
}
```

### 3.4 GET /api/accounts/{account_name}/history
获取账户历史统计

**查询参数**：
- `start_date`: 开始日期
- `end_date`: 结束日期
- `interval`: 统计间隔（daily, weekly, monthly）

**响应**：
```json
{
  "success": true,
  "data": {
    "account": "Assets:Bank:ICBC",
    "history": [
      {"date": "2025-01-01", "balance": 10000.00},
      {"date": "2025-01-10", "balance": 25000.00},
      {"date": "2025-01-15", "balance": 15000.00}
    ]
  }
}
```

### 3.5 PATCH /api/accounts/{account_name}/close
关闭账户

**请求**：
```json
{
  "close_date": "2025-12-31"
}
```

## 4. 交易接口

### 4.1 GET /api/transactions
获取交易列表

**查询参数**：
- `page`: 页码（默认1）
- `page_size`: 每页数量（默认20）
- `start_date`: 开始日期
- `end_date`: 结束日期
- `account`: 账户过滤
- `type`: 交易类型（EXPENSE, INCOME, TRANSFER）
- `tags`: 标签过滤（逗号分隔）
- `search`: 搜索关键词

**响应**：
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "uuid",
        "date": "2025-01-15",
        "description": "午餐",
        "payee": "公司楼下餐厅",
        "type": "EXPENSE",
        "amount": 45.00,
        "currency": "CNY",
        "postings": [
          {
            "account": "Expenses:Food:Dining",
            "amount": 45.00,
            "currency": "CNY"
          },
          {
            "account": "Assets:Cash:Wallet",
            "amount": -45.00,
            "currency": "CNY"
          }
        ],
        "tags": ["lunch", "dining"],
        "created_at": "2025-01-15T12:30:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 150,
      "total_pages": 8
    }
  }
}
```

### 4.2 POST /api/transactions
创建交易

**请求**：
```json
{
  "date": "2025-01-15",
  "description": "超市购物",
  "payee": "沃尔玛",
  "postings": [
    {
      "account": "Expenses:Food:Groceries",
      "amount": 235.50,
      "currency": "CNY"
    },
    {
      "account": "Assets:Invest:Alipay",
      "amount": -235.50,
      "currency": "CNY"
    }
  ],
  "tags": ["groceries", "shopping"]
}
```

**响应**：
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "date": "2025-01-15",
    "description": "超市购物",
    "type": "EXPENSE"
  },
  "message": "交易创建成功"
}
```

### 4.3 GET /api/transactions/{id}
获取交易详情

**响应**：同交易列表中的单个交易对象

### 4.4 PUT /api/transactions/{id}
更新交易

**请求**：同创建交易

### 4.5 DELETE /api/transactions/{id}
删除交易

**响应**：
```json
{
  "success": true,
  "message": "交易已删除"
}
```

### 4.6 GET /api/transactions/statistics
获取交易统计

**查询参数**：
- `start_date`: 开始日期
- `end_date`: 结束日期
- `group_by`: 分组方式（category, date, month）

**响应**：
```json
{
  "success": true,
  "data": {
    "total_income": 15000.00,
    "total_expense": 3250.50,
    "net": 11749.50,
    "by_category": [
      {"category": "Expenses:Food", "amount": 1250.50},
      {"category": "Expenses:Transport", "amount": 350.00}
    ],
    "by_month": [
      {"month": "2025-01", "income": 15000.00, "expense": 3250.50}
    ]
  }
}
```

## 5. 预算接口

### 5.1 GET /api/budgets
获取预算列表

**查询参数**：
- `is_active`: 是否仅显示激活的预算
- `period_type`: 周期类型

**响应**：
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "name": "2025年1月预算",
      "period_type": "MONTHLY",
      "start_date": "2025-01-01",
      "end_date": "2025-01-31",
      "is_active": true,
      "items": [
        {
          "id": "uuid",
          "account_pattern": "Expenses:Food:*",
          "amount": 2000.00,
          "currency": "CNY",
          "spent": 856.50,
          "remaining": 1143.50,
          "percentage": 42.83,
          "status": "NORMAL"
        }
      ],
      "total_budget": 5000.00,
      "total_spent": 1856.50,
      "created_at": "2025-01-01T00:00:00Z"
    }
  ]
}
```

### 5.2 POST /api/budgets
创建预算

**请求**：
```json
{
  "name": "2025年1月预算",
  "period_type": "MONTHLY",
  "start_date": "2025-01-01",
  "end_date": "2025-01-31",
  "items": [
    {
      "account_pattern": "Expenses:Food:*",
      "amount": 2000.00,
      "currency": "CNY"
    },
    {
      "account_pattern": "Expenses:Transport:*",
      "amount": 500.00,
      "currency": "CNY"
    }
  ]
}
```

### 5.3 GET /api/budgets/{id}/execution
获取预算执行详情

**响应**：
```json
{
  "success": true,
  "data": {
    "budget_id": "uuid",
    "name": "2025年1月预算",
    "execution": [
      {
        "account_pattern": "Expenses:Food:*",
        "budget": 2000.00,
        "spent": 856.50,
        "remaining": 1143.50,
        "percentage": 42.83,
        "status": "NORMAL",
        "transactions": [
          {
            "date": "2025-01-05",
            "description": "超市购物",
            "amount": 235.50
          }
        ]
      }
    ]
  }
}
```

### 5.4 PUT /api/budgets/{id}
更新预算

### 5.5 DELETE /api/budgets/{id}
删除预算

## 6. 周期任务接口

### 6.1 GET /api/recurring-rules
获取周期规则列表

**响应**：
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "name": "每月房租",
      "frequency": "MONTHLY",
      "frequency_config": {
        "month_days": [1]
      },
      "start_date": "2025-01-01",
      "end_date": null,
      "is_active": true,
      "transaction_template": {
        "description": "房租",
        "payee": "房东张三",
        "postings": [...]
      },
      "last_executed": "2025-01-01",
      "next_execution": "2025-02-01"
    },
    {
      "id": "uuid",
      "name": "每周健身",
      "frequency": "WEEKLY",
      "frequency_config": {
        "weekdays": [1, 3, 5]
      },
      "start_date": "2025-01-01",
      "is_active": true,
      "transaction_template": {
        "description": "健身房",
        "payee": "XX健身中心",
        "postings": [...]
      },
      "last_executed": "2025-01-17",
      "next_execution": "2025-01-20"
    }
  ]
}
```

### 6.2 POST /api/recurring-rules
创建周期规则

**请求示例1 - 按月（单日）**：
```json
{
  "name": "每月房租",
  "frequency": "MONTHLY",
  "frequency_config": {
    "month_days": [1]
  },
  "start_date": "2025-01-01",
  "transaction_template": {
    "description": "房租",
    "payee": "房东张三",
    "postings": [
      {"account": "Expenses:Housing:Rent", "amount": 3000, "currency": "CNY"},
      {"account": "Assets:Bank:ICBC", "amount": -3000, "currency": "CNY"}
    ],
    "tags": ["rent", "recurring"]
  }
}
```

**请求示例2 - 按周（多日）**：
```json
{
  "name": "每周健身",
  "frequency": "WEEKLY",
  "frequency_config": {
    "weekdays": [1, 3, 5]
  },
  "start_date": "2025-01-01",
  "transaction_template": {
    "description": "健身房",
    "payee": "XX健身中心",
    "postings": [
      {"account": "Expenses:Health:Fitness", "amount": 50, "currency": "CNY"},
      {"account": "Assets:Invest:Alipay", "amount": -50, "currency": "CNY"}
    ],
    "tags": ["fitness", "recurring"]
  }
}
```

**请求示例3 - 按月（多日+月末）**：
```json
{
  "name": "信用卡还款",
  "frequency": "MONTHLY",
  "frequency_config": {
    "month_days": [15, -1]
  },
  "start_date": "2025-01-01",
  "transaction_template": {
    "description": "信用卡还款",
    "payee": "工商银行",
    "postings": [
      {"account": "Liabilities:CreditCard:ICBC", "amount": -5000, "currency": "CNY"},
      {"account": "Assets:Bank:ICBC", "amount": 5000, "currency": "CNY"}
    ],
    "tags": ["creditcard", "recurring"]
  }
}
```

### 6.3 POST /api/recurring-rules/{id}/execute
手动执行周期规则

**请求**：
```json
{
  "execution_date": "2025-01-15"
}
```

**响应**：
```json
{
  "success": true,
  "data": {
    "execution_id": "uuid",
    "transaction_id": "uuid",
    "executed_date": "2025-01-15"
  },
  "message": "周期任务已执行"
}
```

### 6.4 GET /api/recurring-rules/{id}/executions
获取执行历史

**响应**：
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "rule_id": "uuid",
      "executed_date": "2025-01-01",
      "transaction_id": "uuid",
      "status": "SUCCESS",
      "created_at": "2025-01-01T00:00:00Z"
    }
  ]
}
```

### 6.5 PATCH /api/recurring-rules/{id}/toggle
暂停/恢复规则

**请求**：
```json
{
  "is_active": false
}
```

## 7. 备份接口

### 7.1 GET /api/backups
获取备份历史

**响应**：
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "provider": "github",
      "backup_location": "https://github.com/user/repo/commit/abc123",
      "file_size": 1024000,
      "backup_at": "2025-01-15T12:00:00Z",
      "status": "SUCCESS"
    }
  ]
}
```

### 7.2 POST /api/backups
执行备份

**请求**：
```json
{
  "provider": "github"  // 可选，默认使用配置的提供者
}
```

**响应**：
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "provider": "github",
    "backup_location": "https://github.com/user/repo/commit/abc123",
    "file_size": 1024000,
    "backup_at": "2025-01-15T12:00:00Z"
  },
  "message": "备份成功"
}
```

### 7.3 POST /api/backups/{id}/restore
恢复备份

**响应**：
```json
{
  "success": true,
  "message": "备份已恢复，请重启应用"
}
```

### 7.4 DELETE /api/backups/{id}
删除备份

## 8. 分析接口

### 8.1 GET /api/analysis/reports/{type}
获取财务报表

**路径参数**：
- `type`: 报表类型（monthly, yearly, custom）

**查询参数**：
- `start_date`: 开始日期
- `end_date`: 结束日期

**响应**：
```json
{
  "success": true,
  "data": {
    "period": "2025-01",
    "income": 15000.00,
    "expense": 3250.50,
    "net": 11749.50,
    "savings_rate": 78.33,
    "expense_breakdown": [
      {"category": "Food", "amount": 1250.50, "percentage": 38.47},
      {"category": "Transport", "amount": 350.00, "percentage": 10.77}
    ],
    "income_sources": [
      {"category": "Salary", "amount": 15000.00, "percentage": 100}
    ]
  }
}
```

### 8.2 GET /api/analysis/trends
获取趋势分析

**查询参数**：
- `metric`: 指标（expense, income, savings）
- `period`: 周期（6months, 1year, 2years）

**响应**：
```json
{
  "success": true,
  "data": {
    "metric": "expense",
    "trend": "INCREASING",
    "data_points": [
      {"month": "2024-07", "value": 2800.00},
      {"month": "2024-08", "value": 3100.00},
      {"month": "2025-01", "value": 3250.50}
    ],
    "average": 3050.17,
    "growth_rate": 16.09
  }
}
```

### 8.3 POST /api/analysis/ai/insights
AI 生成财务洞察

**请求**：
```json
{
  "period": "2025-01",
  "focus_areas": ["spending", "budget", "savings"]
}
```

**响应**：
```json
{
  "success": true,
  "data": {
    "insights": [
      {
        "type": "WARNING",
        "title": "食品支出偏高",
        "description": "本月食品支出占总支出的38.5%，高于推荐比例30%",
        "suggestion": "建议减少外出就餐频率，增加在家做饭"
      },
      {
        "type": "INFO",
        "title": "储蓄率良好",
        "description": "本月储蓄率达78.3%，保持良好",
        "suggestion": "可考虑将部分储蓄用于投资"
      }
    ],
    "generated_at": "2025-01-15T12:00:00Z"
  }
}
```

### 8.4 POST /api/analysis/ai/chat
自然语言查询

**请求**：
```json
{
  "question": "我这个月在餐饮上花了多少钱？"
}
```

**响应**：
```json
{
  "success": true,
  "data": {
    "answer": "根据您的账本记录，2025年1月您在餐饮（Expenses:Food:Dining）上共花费856.50元，包括15笔交易。",
    "data": {
      "amount": 856.50,
      "currency": "CNY",
      "transaction_count": 15,
      "category": "Expenses:Food:Dining"
    }
  }
}
```

## 9. 错误码定义

| 错误码 | 说明 |
|--------|------|
| AUTH_001 | 未认证 |
| AUTH_002 | 认证失败 |
| AUTH_003 | Token 过期 |
| VALIDATION_001 | 参数验证失败 |
| RESOURCE_001 | 资源不存在 |
| RESOURCE_002 | 资源已存在 |
| BEANCOUNT_001 | Beancount 解析错误 |
| BEANCOUNT_002 | 账户不存在 |
| BEANCOUNT_003 | 借贷不平衡 |
| BUDGET_001 | 预算周期重叠 |
| BACKUP_001 | 备份失败 |
| BACKUP_002 | 恢复失败 |
| AI_001 | AI 服务不可用 |

## 10. 请求头规范

```
# 认证
Authorization: Bearer <access_token>

# 内容类型
Content-Type: application/json

# API版本（可选）
X-API-Version: v1
```
