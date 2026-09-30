# BeanMind 开发规则

模块落位、工程与产品规则在此维护；协作与授权见根 AGENTS.md，检查与验收见 [Harness](../README.md)。

## 模块、依赖与文件落位

| 路径 | 职责与新增代码位置 |
| --- | --- |
| `backend/main.py`、`backend/config/` | FastAPI 装配、配置、日志和依赖生命周期 |
| `backend/interfaces/api/`、`interfaces/dto/` | 按业务域组织路由、Pydantic 请求/响应及协议错误 |
| `backend/application/services/` | 账户、汇率、交易、周期规则的应用编排与 DTO 转换 |
| `backend/domain/<业务域>/` | entities、value_objects、services、repositories 接口 |
| `backend/infrastructure/persistence/` | Beancount 仓储实现、SQLite ORM、账本投影及查询 |
| `backend/infrastructure/scheduler/` | 周期任务调度与后台会话管理 |
| `backend/services/` | 现有预算、仪表盘、汇率换算、聚合、月度复盘服务；相关功能原位扩展 |
| `backend/ai/llm_client.py` | OpenAI-compatible 模型协议客户端 |
| `frontend/src/` | pages 页面、components 业务组件、api 请求、router 路由、stores UI 状态、utils 纯函数 |
| `tests/` | API、领域、投影、工具和 Harness 测试；账本夹具在 `tests/fixtures/` |
| `frontend/src/**/*.test.ts` | 就近 Vitest 测试；公共初始化在 `src/test/setup.ts` |
| `scripts/` | 检查转发、迁移、匿名夹具生成及性能工具 |

新增代码沿用当前业务域：接口调用 application/services 或现有 backend/services；domain 不依赖 interfaces；持久化实现 domain 仓储接口，装配层负责连接具体实现。现有路由依赖工厂会直接组装仓储与投影服务，不能将“完全无跨层引用”宣称为现状，也不据此扩大重构。

Python 文件和函数用 snake_case、类型用 PascalCase；沿用 `TransactionApplicationService`、`TransactionRepositoryImpl`、`CreateTransactionRequest`、`TransactionResponse` 等既有命名。请求、响应、ORM 模型、领域对象职责分开，不直接用 ORM 接收客户端输入。不新增无实际多实现需求的框架或空包。

配置通过 Settings 和环境变量提供，示例维护 `.env.example`，不读写或输出真实 `.env` 密钥。静态资源位于 `frontend/public/`、`frontend/src/assets/`；Vite 构建产物在 `frontend/dist/`。数据库迁移沿用 `scripts/migrate_v3.py`，不另造迁移入口。

## 后端与数据

- 路由负责协议校验、依赖和错误映射，业务约束复用 Service。保持错误 `code`、`message`、`details` 和 Decimal 传输契约，不新增生产 `/api/test/*`。
- 同步 SQLAlchemy 配合同步 Endpoint/Service；DB 依赖用 `yield` 关闭会话，后台调用者关闭自建会话，不吞异常。
- 写入先落 Beancount 再刷新投影，禁止 SQLite 反向覆盖账本；保留临时文件、写后解析、失败回滚、幂等和单写者保障。投影失败为 DIRTY，财务查询拒绝返回错误结果，从账本重建恢复；预算依赖 READY 投影。
- 金额使用 Decimal、NUMERIC 或十进制字符串；不以 float 做财务运算，缺失汇率显式返回，不按 1:1 兜底。流水保持 SQL 聚合、`(date, id)` Keyset Cursor 与稳定 UUID，不新增精确总数扫描或批量补写历史 UUID。
- 保留账户关闭/重开及历史交易、周期记账、币种、汇率、报表和账户明细，不因空夹具删能力。日志不输出完整账本、财务明细、Prompt 或密钥。
- AI 复盘默认关闭，使用 OpenAI-compatible Chat Completions；确定性代码提供财务事实，模型只生成总结和建议，输出本地校验，失败不影响核心功能。
- 登录、租户、远端同步、应用内备份必须有明确新需求。

## 前端

- 一级页面独立路由、异步加载；底栏取 `meta.tab`。筛选、搜索、月份优先进入 URL，检查前进后退恢复。
- Pinia 保存 UI 偏好和未提交草稿，服务端数据留在页面或局部 composable；直接使用 Vant，仅封装业务组件。
- 金额复用 `utils/decimal.ts`、`amountExpression.ts`，保持精度、舍入和字符串传输契约。
- 覆盖加载、空状态、错误与重试；布局改动检查安全区、底栏、滚动、弹层与返回。
- PWA 仅缓存静态壳层、不缓存财务 API，更新由用户选择；不新增离线记账、后台同步或失败写请求重放。

## 迁移、性能与验收

- 迁移默认只读预览；执行需明确目标授权、`--apply`、外部可恢复备份、`--confirm-drop-budgets`。核对解析、SQLite/WAL、保留数量和回退条件。
- 性能结论需要匿名真实数据 1× 与等分布 2×，合成夹具不能替代。
- 测试遵守根 AGENTS.md 的数据授权边界；保留原生 runner 对失败、零测试与跳过的语义。
