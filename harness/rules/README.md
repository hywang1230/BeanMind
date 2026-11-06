# BeanMind 开发规则索引

按任务范围加载直接相关的领域规则；链接指向的专项规则在涉及该领域时一并遵守，普通局部任务不必通读全部文件。协作与授权底线见根 `AGENTS.md`，验证命令、隔离机制与交付边界统一见 [Harness](../README.md)。

| 任务范围 | 必须核对的规则 |
| --- | --- |
| 设计文档、迁移方案/SQL 或测试用例设计的新增与维护 | [documents.md](documents.md)：设计确认与修改授权、`docs/` 三类文档、复用与回复交付 |
| 架构设计、高风险独立评审、模块职责、前后端分层与文件落位 | [architecture.md](architecture.md)：独立子代理架构评审、Python+Vue 模块边界与产品范围 |
| 后端 Python/FastAPI/Beancount 与前端 Vue/TS/Vant/Pinia/PWA 编码 | [coding.md](coding.md)：命名、分层对象、`Decimal` 财务精度、账本写入不变量与前端交互状态 |
| SQLite ORM 模型、Beancount 查询投影、游标分页与数据迁移 | [database.md](database.md)：账本真源与投影分离、`READY`/`DIRTY` 状态机、`BaseModel` 与 `migrate_v3.py` |
| 测试设计/代码、行为变更、独立子代理用例评审、隔离验证与验收 | [testing.md](testing.md)：pytest/Vitest 复用、独立用例评审、临时数据隔离与人工验收边界 |
| FastAPI 路由、错误契约、中间件链、单机安全边界与 `.env` 保护 | [api-security.md](api-security.md)：`ApiError`/写冲突/投影错误映射、真实中间件链与配置隔离 |
| LLM 月度复盘、周期记账调度、超时降级与财务日志脱敏 | [integration-logging.md](integration-logging.md)：确定性财务事实、模型输出校验、后台会话与日志脱敏 |
