# BeanMind

BeanMind 是基于 Beancount 的单机个人财务系统，固定为单部署、单账本、单写者。

- Beancount 是账户、交易、分录和汇率的唯一真值。
- SQLite 保存应用数据和可从 Beancount 重建的查询投影。
- 后端使用 FastAPI、同步 SQLAlchemy；前端使用 Vue 3、TypeScript、Vue Router、Vant 4 和 Vite。
- 可选 AI 月度复盘通过 OpenAI-compatible Chat Completions 调用模型。
- 不提供登录、权限、远端同步或应用内备份；备份由 NAS 或部署环境负责。

## 启动

需要 Python 3.10+、uv，以及 Node.js 20.19+ 或 22.12+。

```bash
cp .env.example .env
./start.sh
```

启动后访问：

- 前端：<http://localhost:5173>
- API：<http://localhost:8000>
- API 文档：<http://localhost:8000/docs>

停止服务：

```bash
./stop.sh
```

也可以分别启动：

```bash
~/.local/bin/uv sync --dev
~/.local/bin/uv run uvicorn backend.main:app --reload
cd frontend && npm install && npm run dev
```

## 数据与恢复

默认账本入口是 `data/ledger/main.beancount`，数据库是 `data/beanmind.db`。流水、预算执行和报表查询依赖 SQLite 投影；投影异常会进入 `DIRTY` 状态并拒绝返回可能错误的财务结果。

投影可通过以下接口从 Beancount 重建：

```bash
curl -X POST http://localhost:8000/api/transactions/projection/rebuild
```

迁移或性能测试应先使用真实账本副本或匿名化数据。SQLite 投影不得反向覆盖 Beancount。

## LLM 配置

默认关闭。启用时在 `.env` 配置：

```dotenv
LLM_ENABLED=true
LLM_BASE_URL=https://example.com/v1
LLM_API_KEY=your-api-key
LLM_MODEL=your-model
LLM_TIMEOUT_SECONDS=30
```

模型只生成月度总结和建议，金额、预算和趋势由确定性代码计算。模型失败不影响记账、查询和预算。

## 验证

```bash
~/.local/bin/uv run pytest tests/ -v
cd frontend && npm run test:run && npm run build
openspec validate complete-beanmind-core-reform --type change --strict --no-interactive
```

改革目标和边界见 `docs/BeanMind-Reform-Plan.md`。

## License

MIT
