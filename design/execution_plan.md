# BeanMind 详细执行计划

## 计划说明

本执行计划将 BeanMind 项目开发分解为 **6 个大阶段**，每个阶段包含多个可独立完成和 review 的小步骤。

**执行原则**：
- ✅ 每完成一个步骤，提交代码并请求 review
- ✅ 通过 review 后，再进行下一步
- ✅ 每个步骤都有明确的交付物和验收标准
- ✅ 遵循依赖关系，按顺序执行

---

## 阶段 0️⃣：项目初始化（4 步）

### 步骤 0.1：创建项目目录结构
**目标**：搭建完整的项目骨架

**交付物**：
- `backend/` 目录及所有子目录
- `frontend/` 目录及所有子目录
- `data/` 目录
- 根目录配置文件

**验收标准**：
- 目录结构符合 `system_architecture.md` 的规划
- 所有目录都有 `__init__.py`（Python）或 `index.ts`（TypeScript）
- README.md 包含项目说明

**具体任务**：
```bash
BeanMind/
├── backend/
│   ├── main.py
│   ├── config/
│   ├── interfaces/
│   ├── application/
│   ├── domain/
│   └── infrastructure/
├── frontend/
│   └── src/
├── data/
│   ├── ledger/
│   └── .gitkeep
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

---

### 步骤 0.2：配置开发环境
**目标**：设置 Python 虚拟环境和依赖

**交付物**：
- `requirements.txt` 包含所有核心依赖
- `pyproject.toml` 项目配置
- `.env.example` 环境变量模板

**验收标准**：
- `pip install -r requirements.txt` 成功执行
- 环境变量模板包含所有必需配置项

**核心依赖**：
```txt
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.5.0
pydantic-settings==2.1.0
sqlalchemy==2.0.25
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6
beancount==2.3.6
dependency-injector==4.41.0
```

---

### 步骤 0.3：初始化数据库
**目标**：创建 SQLite 数据库和初始化脚本

**交付物**：
- `infrastructure/persistence/sqlalchemy/models/` 所有 ORM 模型
- `infrastructure/persistence/init_db.py` 初始化脚本
- `data/beanmind.db`（空数据库）

**验收标准**：
- 执行 `python -m infrastructure.persistence.init_db` 成功创建数据库
- 数据库包含所有 7 张表
- 表结构符合 `database_design.md`

**涉及的表**：
1. users
2. transaction_metadata
3. budgets
4. budget_items
5. recurring_rules
6. recurring_executions
7. backup_history

---

### 步骤 0.4：初始化 Beancount 账本
**目标**：创建账本文件和初始化逻辑

**交付物**：
- `infrastructure/persistence/beancount/init_ledger.py`
- `data/ledger/main.beancount`（初始账本）

**验收标准**：
- 执行初始化脚本成功创建账本文件
- 账本文件符合 Beancount 语法
- 包含基本配置和默认账户

**账本内容**：
- option 配置
- 默认账户（Assets:Unknown, Equity:OpeningBalances）

---

## 阶段 1️⃣：核心基础设施（8 步）

### 步骤 1.1：实现配置管理
**目标**：环境变量和配置加载

**交付物**：
- `config/settings.py`（Pydantic Settings）
- 支持所有环境变量

**验收标准**：
- 可从 `.env` 文件加载配置
- 配置包含鉴权、数据库路径、备份等所有设置
- 配置有类型验证

**配置项**：
```python
class Settings(BaseSettings):
    AUTH_MODE: str = "single_user"
    SINGLE_USER_USERNAME: str
    SINGLE_USER_PASSWORD: str
    JWT_SECRET_KEY: str
    DATA_DIR: Path = "./data"
    # ...
```

---

### 步骤 1.2：实现依赖注入容器
**目标**：配置 DI 容器

**交付物**：
- `config/container.py`（Dependency Injector）

**验收标准**：
- 容器包含所有服务和仓储的注册
- 可以正确解析依赖关系

---

### 步骤 1.3：实现 Beancount Service
**目标**：封装 Beancount 操作

**交付物**：
- `infrastructure/persistence/beancount/beancount_service.py`

**验收标准**：
- 可以加载账本文件
- 可以查询账户列表
- 可以查询账户余额
- 可以追加交易

**核心方法**：
```python
class BeancountService:
    def load_ledger(self) -> Entries
    def get_accounts(self) -> List[Account]
    def get_balance(self, account: str, date: datetime) -> Amount
    def append_transaction(self, transaction: Transaction) -> str
```

---

### 步骤 1.4：实现数据库会话管理
**目标**：SQLAlchemy 会话工厂

**交付物**：
- `infrastructure/persistence/sqlalchemy/database.py`

**验收标准**：
- 可以创建数据库会话
- 支持事务管理
- 连接池配置正确

---

### 步骤 1.5：实现 ORM 基类
**目标**：所有模型的基类

**交付物**：
- `infrastructure/persistence/sqlalchemy/models/base.py`

**验收标准**：
- 包含通用字段（id, created_at, updated_at）
- 提供 to_dict() 方法

---

### 步骤 1.6：实现 User ORM 模型
**目标**：用户表模型

**交付物**：
- `infrastructure/persistence/sqlalchemy/models/user.py`

**验收标准**：
- 字段符合数据库设计
- 密码字段使用 bcrypt 加密
- 包含索引定义

---

### 步骤 1.7：实现 JWT 工具类
**目标**：Token 生成和验证

**交付物**：
- `infrastructure/auth/jwt_utils.py`

**验收标准**：
- 可以生成 JWT Token
- 可以验证 Token 有效性
- 可以解析 Token 获取用户信息

---

### 步骤 1.8：实现密码加密工具
**目标**：密码哈希和验证

**交付物**：
- `infrastructure/auth/password_utils.py`

**验收标准**：
- 使用 bcrypt 加密
- 可以验证密码

---

## 阶段 2️⃣：认证模块（6 步）

### 步骤 2.1：实现 User 领域实体
**目标**：用户领域模型

**交付物**：
- `domain/auth/entities/user.py`

**验收标准**：
- 包含用户属性和业务规则
- 无数据库依赖

---

### 步骤 2.2：实现 User Repository 接口
**目标**：用户仓储抽象

**交付物**：
- `domain/auth/repositories/user_repository.py`（接口）

**验收标准**：
- 定义所有用户数据访问方法
- 仅包含接口，不包含实现

---

### 步骤 2.3：实现 User Repository 实现
**目标**：SQLAlchemy 用户仓储

**交付物**：
- `infrastructure/persistence/sqlalchemy/repositories/user_repository_impl.py`

**验收标准**：
- 实现所有仓储接口方法
- 包含单元测试

---

### 步骤 2.4：实现认证领域服务
**目标**：登录验证逻辑

**交付物**：
- `domain/auth/services/auth_service.py`

**验收标准**：
- 支持三种鉴权模式（none/single_user/multi_user）
- 可以验证用户名密码
- 可以生成 Token

---

### 步骤 2.5：实现认证应用服务
**目标**：认证用例编排

**交付物**：
- `application/services/auth_service.py`

**验收标准**：
- 实现 login、refresh、get_current_user
- 包含 DTO 转换

---

### 步骤 2.6：实现认证 API
**目标**：登录接口

**交付物**：
- `interfaces/api/auth.py`
- `interfaces/dto/request/auth.py`
- `interfaces/dto/response/auth.py`

**验收标准**：
- `POST /api/auth/login` 可以登录
- `POST /api/auth/refresh` 可以刷新 Token
- `GET /api/auth/me` 可以获取当前用户
- 符合 `api_design.md` 规范

**测试用例**：
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password"}'
```

---

## 阶段 3️⃣：账户模块（7 步）

### 步骤 3.1：实现 Account 领域实体
**交付物**：`domain/account/entities/account.py`

**验收标准**：
- 包含账户属性（name, type, currencies）
- 账户类型枚举（Assets, Liabilities, Equity, Income, Expenses）

---

### 步骤 3.2：实现 Account Repository 接口
**交付物**：`domain/account/repositories/account_repository.py`

**验收标准**：
- 定义查询账户、获取余额等方法

---

### 步骤 3.3：实现 Account Repository 实现
**交付物**：`infrastructure/persistence/beancount/account_repository_impl.py`

**验收标准**：
- 从 Beancount 文件读取账户
- 可以创建新账户（写入 Beancount）
- 可以查询账户余额

---

### 步骤 3.4：实现账户领域服务
**交付物**：`domain/account/services/account_service.py`

**验收标准**：
- 账户创建业务规则验证
- 账户名称格式验证

---

### 步骤 3.5：实现账户应用服务
**交付物**：`application/services/account_service.py`

**验收标准**：
- 实现 create_account, get_accounts, get_balance

---

### 步骤 3.6：实现账户 DTO
**交付物**：
- `interfaces/dto/request/account.py`
- `interfaces/dto/response/account.py`

**验收标准**：
- 符合 API 设计文档

---

### 步骤 3.7：实现账户 API
**交付物**：`interfaces/api/accounts.py`

**验收标准**：
- `GET /api/accounts` 返回账户树
- `POST /api/accounts` 创建账户
- `GET /api/accounts/{name}/balance` 获取余额
- 需要认证

**测试用例**：
```bash
curl http://localhost:8000/api/accounts \
  -H "Authorization: Bearer $TOKEN"
```

---

## 阶段 4️⃣：交易模块（9 步）

### 步骤 4.1：实现 Transaction 领域实体
**交付物**：
- `domain/transaction/entities/transaction.py`
- `domain/transaction/entities/posting.py`

**验收标准**：
- Transaction 包含 date, description, postings, tags
- Posting 包含 account, amount, currency
- 借贷平衡验证规则

---

### 步骤 4.2：实现 TransactionMetadata ORM 模型
**交付物**：`infrastructure/persistence/sqlalchemy/models/transaction_metadata.py`

**验收标准**：
- 符合数据库表设计
- 与 users 表关联

---

### 步骤 4.3：实现 Transaction Repository 接口
**交付物**：`domain/transaction/repositories/transaction_repository.py`

**验收标准**：
- 定义 create, update, delete, find 方法

---

### 步骤 4.4：实现 Transaction Repository 实现
**交付物**：`infrastructure/persistence/beancount/transaction_repository_impl.py`

**验收标准**：
- 写入 Beancount 文件
- 同时保存元数据到 SQLite
- 事务一致性保证

---

### 步骤 4.5：实现交易领域服务
**交付物**：`domain/transaction/services/transaction_service.py`

**验收标准**：
- 交易类型判断（支出/收入/转账）
- 借贷平衡验证
- 账户存在性检查

---

### 步骤 4.6：实现交易应用服务
**交付物**：`application/services/transaction_service.py`

**验收标准**：
- create_transaction
- get_transactions（分页、筛选）
- get_transaction_by_id
- update_transaction
- delete_transaction
- get_statistics

---

### 步骤 4.7：实现交易 DTO
**交付物**：
- `interfaces/dto/request/transaction.py`
- `interfaces/dto/response/transaction.py`

---

### 步骤 4.8：实现交易 API
**交付物**：`interfaces/api/transactions.py`

**验收标准**：
- `GET /api/transactions` 支持分页和筛选
- `POST /api/transactions` 创建交易
- `GET /api/transactions/{id}` 获取详情
- `PUT /api/transactions/{id}` 更新
- `DELETE /api/transactions/{id}` 删除
- `GET /api/transactions/statistics` 统计

---

### 步骤 4.9：编写交易模块集成测试
**交付物**：`tests/integration/test_transactions.py`

**验收标准**：
- 测试创建支出/收入/转账
- 测试查询和筛选
- 测试统计功能

---

## 阶段 5️⃣：预算与周期任务（10 步）

### 步骤 5.1：实现 Budget 相关 ORM 模型
**交付物**：
- `infrastructure/persistence/sqlalchemy/models/budget.py`
- `infrastructure/persistence/sqlalchemy/models/budget_item.py`

---

### 步骤 5.2：实现 Budget 领域实体
**交付物**：
- `domain/budget/entities/budget.py`
- `domain/budget/entities/budget_item.py`
- `domain/budget/value_objects/budget_execution.py`

---

### 步骤 5.3：实现预算 Repository
**交付物**：
- `domain/budget/repositories/budget_repository.py`（接口）
- `infrastructure/persistence/sqlalchemy/repositories/budget_repository_impl.py`（实现）

---

### 步骤 5.4：实现预算执行计算服务
**交付物**：`domain/budget/services/budget_execution_service.py`

**验收标准**：
- 可以计算预算执行情况
- 支持账户模式匹配
- 状态判断（正常/警告/超支）

---

### 步骤 5.5：实现预算应用服务和 API
**交付物**：
- `application/services/budget_service.py`
- `interfaces/api/budgets.py`

**验收标准**：
- 符合 API 设计文档的所有接口

---

### 步骤 5.6：实现 RecurringRule ORM 模型
**交付物**：
- `infrastructure/persistence/sqlalchemy/models/recurring_rule.py`
- `infrastructure/persistence/sqlalchemy/models/recurring_execution.py`

**验收标准**：
- frequency_config 字段存储 JSON
- 符合细化的频率类型设计

---

### 步骤 5.7：实现周期规则领域实体
**交付物**：
- `domain/recurring/entities/recurring_rule.py`
- `domain/recurring/value_objects/frequency_config.py`

**验收标准**：
- 支持5种频率类型
- FrequencyConfig 包含 weekdays, month_days 等配置

---

### 步骤 5.8：实现周期任务执行引擎
**交付物**：`domain/recurring/services/recurring_execution_service.py`

**验收标准**：
- 可以判断某个规则在某天是否应该执行
- 支持按周多选、按月多选
- 支持月末特殊值（-1）

**核心逻辑**：
```python
def should_execute(rule: RecurringRule, date: datetime) -> bool:
    if rule.frequency == "WEEKLY":
        return date.isoweekday() in rule.frequency_config.weekdays
    elif rule.frequency == "MONTHLY":
        # 处理月末逻辑...
```

---

### 步骤 5.9：实现周期任务应用服务和 API
**交付物**：
- `application/services/recurring_service.py`
- `interfaces/api/recurring.py`

**验收标准**：
- 创建规则时验证 frequency_config
- 手动执行周期任务
- 查看执行历史

---

### 步骤 5.10：实现定时任务调度
**目标**：每天自动执行周期任务

**交付物**：
- `infrastructure/scheduler/recurring_task_scheduler.py`

**验收标准**：
- 使用 APScheduler 或类似库
- 每天扫描应执行的规则
- 自动生成交易

---

## 阶段 6️⃣：前端开发（16 步）

### 步骤 6.1：初始化 Vue3 + Framework7 项目
**交付物**：
- `frontend/` 项目结构
- `package.json` 依赖配置

**验收标准**：
- `npm install` 成功
- `npm run dev` 可以启动开发服务器

---

### 步骤 6.2：配置路由
**交付物**：`frontend/src/router/index.ts`

**验收标准**：
- 配置所有9个页面路由
- 懒加载配置

---

### 步骤 6.3：配置 Pinia 状态管理
**交付物**：`frontend/src/stores/index.ts`

---

### 步骤 6.4：实现 API 客户端
**交付物**：
- `frontend/src/api/client.ts`（Axios 封装）
- `frontend/src/api/auth.ts`
- `frontend/src/api/accounts.ts`
- `frontend/src/api/transactions.ts`

**验收标准**：
- 统一请求拦截器（添加 Token）
- 统一响应拦截器（错误处理）

---

### 步骤 6.5：实现 authStore
**交付物**：`frontend/src/stores/auth.ts`

**验收标准**：
- login、logout、refreshToken actions
- Token 持久化到 localStorage

---

### 步骤 6.6：实现登录页
**交付物**：`frontend/src/pages/auth/LoginPage.vue`

**验收标准**：
- UI 符合前端设计文档
- 可以成功登录
- 登录后跳转到仪表盘

---

### 步骤 6.7：实现公共组件 - AmountInput
**交付物**：`frontend/src/components/AmountInput.vue`

---

### 步骤 6.8：实现公共组件 - AccountPicker
**交付物**：`frontend/src/components/AccountPicker.vue`

**验收标准**：
- 支持树形账户选择

---

### 步骤 6.9：实现公共组件 - CategoryPicker
**交付物**：`frontend/src/components/CategoryPicker.vue`

---

### 步骤 6.10：实现仪表盘页面
**交付物**：`frontend/src/pages/dashboard/DashboardPage.vue`

**验收标准**：
- 显示总资产概览
- 显示本月收支
- 显示预算执行
- 显示最近交易
- 快捷操作按钮

---

### 步骤 6.11：实现 transactionStore
**交付物**：`frontend/src/stores/transaction.ts`

---

### 步骤 6.12：实现记账页 - 交易列表
**交付物**：`frontend/src/pages/transactions/TransactionsPage.vue`

**验收标准**：
- 虚拟滚动
- 分页加载
- 筛选功能

---

### 步骤 6.13：实现记账页 - 新增交易
**交付物**：`frontend/src/pages/transactions/AddTransactionPage.vue`

**验收标准**：
- 快速金额按钮
- 分类和账户选择
- 表单验证

---

### 步骤 6.14：实现账户页
**交付物**：`frontend/src/pages/accounts/AccountsPage.vue`

**验收标准**：
- 树形账户展示
- 显示余额

---

### 步骤 6.15：实现预算管理页
**交付物**：`frontend/src/pages/budgets/BudgetsPage.vue`

**验收标准**：
- 预算列表
- 进度条显示
- 颜色标识

---

### 步骤 6.16：实现周期任务页
**交付物**：`frontend/src/pages/recurring/RecurringPage.vue`

**验收标准**：
- 规则列表
- 显示频率配置（按周、按月）
- 新增/编辑周期任务
- 按周/按月多选界面

---

## 验收总结

每个阶段完成后，进行以下验收：

1. **代码质量**：
   - Lint 检查通过
   - 类型检查通过（mypy）
   - 单元测试覆盖率 > 80%

2. **功能验收**：
   - API 接口符合设计文档
   - 前端页面符合 UI 设计
   - 核心流程可以走通

3. **文档同步**：
   - 更新 README.md
   - 更新 API 文档（如有变化）

---

## 下一步

请确认此执行计划，我们将从 **阶段 0️⃣ 步骤 0.1** 开始逐步实施。

每完成一个步骤，我会：
1. 提交代码
2. 说明已完成的内容
3. 请求您的 review
4. 等待确认后进入下一步
