# BeanMind Harness

统一验证入口为 `bash scripts/verify`（底层执行 [verify.sh](checks/verify.sh)），CI 使用相同入口。工程与产品细则见 [规则索引](rules/README.md)，协作与授权底线见根 `AGENTS.md`。Harness 提供自动验证证据，不代替设计确认、独立评审或人工验收。

## 入口与范围

环境要求：Python 3.10+、`uv`、`git`、`bash`、`perl`；Node 遵循 `frontend/package.json` 的 `engines`（`^20.19.0 || >=22.12.0`）。依赖安装是独立前置步骤，检查入口不隐式下载或升级依赖。

```bash
uv sync --frozen --dev
(cd frontend && npm ci)
bash harness/checks/check-local-rules.sh  # 规则文件、Markdown 链接/空白与 Shell 语法
git diff --check                          # 工作树未暂存差异空白检查
bash scripts/verify                       # all：静态治理 + 后端全量 + 前端全量 + 类型/构建/PWA
bash scripts/verify backend               # 静态治理 + 后端全量（临时数据隔离）
bash scripts/verify frontend              # 静态治理 + 前端全量 + 类型/构建/PWA
bash scripts/verify docs                  # 静态治理（Markdown 链接/空白 + Shell 语法 + Git 空白）
bash run_tests.sh                         # 兼容转发，等同 bash scripts/verify backend
```

| 命令 | 职责与边界 |
| --- | --- |
| [check-local-rules.sh](checks/check-local-rules.sh) | 检查 `README.md`、`harness/` 规则与本地 `AGENTS.md`、`docs/`（存在时）的非空、换行符、行尾空白、相对文件链接，以及入口脚本 Shell 语法 |
| [local-tests.sh](checks/local-tests.sh) | 执行环境预检、后端临时目录隔离 `pytest`、前端 `vitest` 与 `vue-tsc`/`vite`/PWA 构建校验；缺失或预检不满足时退出 `2` 并报告 `BLOCKED` |
| [verify.sh](checks/verify.sh) | 串联参数校验、预检、静态治理检查与 `local-tests.sh`；支持从任意工作目录及带空格路径调用，失败立即停止并保留原生退出码 |

## 本地测试适配与隔离

- **静态治理检查**：覆盖工作树与暂存区空白（`git diff --check`、`git diff --cached --check`）、Shell 语法（`bash -n`）以及工程 Markdown 链接与格式（`check-local-rules.sh` 与 `check_docs.py`）。本地忽略文档存在时一并检查，缺失不阻塞 CI。
- **后端隔离验证**：`local-tests.sh` 创建临时目录并在退出时自动清理，强制将 `DATA_DIR`、`LEDGER_FILE`、`DATABASE_FILE`、`LOG_DIR` 指向临时路径，设置 `SCHEDULER_ENABLED=false`、`LLM_ENABLED=false` 并清空 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`，再执行 `uv run --frozen --no-sync --offline pytest -q`。它不是 OS 级沙箱，测试严禁硬编码真实 `data/` 路径或读取真实 `.env`。
- **前端测试与构建**：在 `frontend/` 下串行执行 `npm run test:run`（Vitest + `jsdom`）与 `npm run build`（含 `vue-tsc -b`、`vite build` 及 `scripts/verify-pwa.mjs`）。
- **锁文件与缓存边界**：修改 `pyproject.toml`/`uv.lock` 或 `frontend/package*.json` 后须重新同步依赖；`--no-sync` 不证明本地虚拟环境与锁文件完全一致，CI 通过 `--frozen` 校验。检查仅写入临时目录、`.harness/uv-cache/`、测试缓存与 `frontend/dist/`，不触碰真实账本或数据库。

## 交付检查与人工验收边界

| 改动范围 | 必跑自动检查 | 额外场景与人工/外部验收边界 |
| --- | --- | --- |
| 纯文档、规则、注释、格式 | `docs` | 直接核对 Git 忽略文件（`AGENTS.md`、`docs/`）前后内容与本地链接 |
| 后端业务、API、领域、持久化 | `backend` | 受影响接口契约、错误码、领域边界与回归用例 |
| 前端页面、组件、路由、状态 | `frontend` | 加载态、空状态、错误与重试、URL 查询恢复、移动端安全区与导航返回 |
| 跨前后端、契约变更、Harness/CI | `all` | Harness 自测（`tests/harness/test_verify_entrypoint.py`）、前后端契约与 CI 一致性 |
| 账本写入、SQLite 投影 | `backend` | `Decimal` 精度、临时账本原子写、写失败回滚、投影 `READY`/`DIRTY` 与从账本重建恢复 |
| 数据库迁移（`scripts/migrate_v3.py`） | `backend` | 默认只读预览、WAL/孤儿关联阻断、失败回滚、幂等；实际执行前须确认外部停机备份与授权 |
| 性能基准（`scripts/benchmark_*.py`） | `backend` | 合成夹具仅验回归；正式性能结论须基于经授权的匿名真实账本 1× 与等分布 2× |
| LLM 月度复盘 | `backend` | 确定性代码计算财务事实、模型输出本地结构校验、超时/异常 `LlmUnavailableError` 降级 |
| PWA 壳层与更新提示 | `frontend` | 真实设备 HTTPS 下安装、发现新版本提示确认、`/api` 与 `/health` 永不缓存 |

多类改动叠加时取并集。开发迭代可带同等临时环境变量定向运行 `pytest` 或 `vitest run`，交付前运行对应组件全量检查。仅所选检查全部成功才输出 `PASS`，单项 `PASS` 不代表 `all` 通过；零测试执行、全跳过、缺适配或环境缺失均不算通过。设计确认、独立子代理评审与人工验收状态须在回复中分别说明。
