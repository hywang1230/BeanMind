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

## PWA 安装与更新

BeanMind 支持在手机或桌面浏览器中添加到主屏幕，并以独立窗口启动。PWA 仅缓存前端静态壳层；发现新版本时，页面会提示用户选择“立即更新”或“稍后”，不会在使用过程中静默切换版本。

- 本机可使用 `localhost` 验证 Service Worker。
- 手机或其他局域网设备访问时，部署环境必须提供 HTTPS，浏览器才会保证 Service Worker 和安装入口可用。
- 直接通过 `http://<局域网地址>:8000` 访问时，BeanMind 仍可作为普通 Web 应用使用，但不承诺可以安装。
- PWA 不缓存账户、流水、预算、报表等 API 响应，不支持离线查账、离线记账、后台同步或失败写请求自动重放。

后端不可访问时，财务页面会显示现有网络错误和重试入口，不会把缓存数据当作当前财务结果。

## 数据与恢复

默认账本入口是 `data/ledger/main.beancount`，数据库是 `data/beanmind.db`。流水、预算执行和报表查询依赖 SQLite 投影；投影异常会进入 `DIRTY` 状态并拒绝返回可能错误的财务结果。

投影可通过以下接口从 Beancount 重建：

```bash
curl -X POST http://localhost:8000/api/transactions/projection/rebuild
```

迁移或性能测试应先使用真实账本副本或匿名化数据。SQLite 投影不得反向覆盖 Beancount。

### 从 `main` 升级到 3.0.0

升级前先停止服务，分别备份完整 `data/ledger/` 和停机后的 `data/beanmind.db`。3.0.0 只保留一个迁移入口，默认命令只读预览：

```bash
cp data/beanmind.db /外部备份目录/beanmind-before-v3.db
uv run python scripts/migrate_v3.py data/beanmind.db \
  --ledger data/ledger/main.beancount
```

核对预览中的账本交易/分录数、周期规则/执行数和待删除预算数后，明确放弃旧预算并执行：

```bash
uv run python scripts/migrate_v3.py data/beanmind.db \
  --ledger data/ledger/main.beancount \
  --apply \
  --backup /外部备份目录/beanmind-before-v3.db \
  --confirm-drop-budgets
```

脚本会完整保留周期记账，删除旧预算和废弃元数据，并只从 Beancount 重建流水投影。备份与源数据库不是完全相同的停机副本、存在未 checkpoint 的非空 SQLite WAL、账本无法解析或周期执行存在孤儿关联时，迁移会拒绝开始。迁移后应确认报告中投影为 `READY`、流水数量一致、周期规则与执行数一致、月度预算为空；如需回退，先停止服务，再恢复已校验的 SQLite 外部备份，账本无需由 SQLite 回写。

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

### OpenSpec 变更 Harness

OpenSpec 负责描述变更意图与可观察行为，harness 负责运行受控检查并保存证据。新 change 在 `openspec/changes/<change>/verification.json` 中声明风险标签、`fast`/`full` 检查、规格场景映射和人工验收项；清单只能引用 `harness/checks.json` 中登记的检查，不能嵌入任意 shell 命令。

```bash
# 只校验 OpenSpec 状态、清单、风险规则和将要执行的命令
python scripts/change_harness.py check --change <change> --mode fast

# 开发迭代：严格 OpenSpec 校验、定向测试和基础检查
python scripts/change_harness.py run --change <change> --mode fast

# 交付门禁：风险策略要求的全量测试、构建和人工验收状态
python scripts/change_harness.py run --change <change> --mode full

# 将最新证据摘要显式发布到当前 change，不自动归档
python scripts/change_harness.py report --change <change> --publish
```

状态含义：`PASS` 表示本次要求全部满足，`FAIL` 表示自动检查失败，`BLOCKED` 表示必需环境或人工验收尚未满足，`NOT_RUN` 表示未执行。`fast PASS` 不能替代 `full`；`full PASS` 也只表示具备人工复核和归档条件，harness 不会自动修改 tasks、提交代码或执行 `openspec archive`。

运行证据保存在被 Git 忽略的 `.harness/runs/`。当前 `openspec/` 同样是本地控制面，CI 无法读取 change 清单，因此 CI 只通过 `baseline` 执行不依赖 OpenSpec 的后端测试、前端测试与生产构建。

账本写入、投影、迁移或性能变更必须使用临时账本、账本副本或匿名化数据。不得把默认真实账本或生产 SQLite 作为可写测试目标；缺少匿名化真实账本 1×/2× 或外部备份核对时，完整验证必须保持 `BLOCKED`。

### 直接运行底层检查

```bash
~/.local/bin/uv run pytest tests/ -v
cd frontend && npm run test:run && npm run build
cd frontend && npm run verify:pwa
openspec validate complete-beanmind-core-reform --type change --strict --no-interactive
```


## License

MIT
