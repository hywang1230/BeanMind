# BeanMind Harness

默认入口为 `bash scripts/verify`，不依赖 OpenSpec。开发规则见 [rules/README.md](rules/README.md)。本地设计流程见根目录 AGENTS.md 与 docs/README.md；它们被 Git 忽略，不是 CI 的前置条件。

## 命令与环境

先准备 Python 3.10+、uv、Git、Bash，以及符合 `frontend/package.json` engines（`^20.19.0 || >=22.12.0`）的 Node/npm。

```bash
uv sync --frozen --dev
(cd frontend && npm ci)
bash scripts/verify               # all：静态检查、后端全量、前端全量、生产构建
bash scripts/verify backend       # 静态检查 + 后端全量
bash scripts/verify frontend      # 静态检查 + 前端全量 + 类型/构建/PWA
bash scripts/verify docs          # 仅工程文档链接/空白、Shell 语法、Git 空白
bash run_tests.sh                 # 兼容旧入口，等同 backend
```

入口可从其他工作目录调用，支持带空格的仓库路径；未知参数非零退出。依赖安装是独立显式步骤，检查不自动下载或升级依赖；后端用 `uv run --frozen --no-sync --offline pytest -q`。更换锁文件后应重新执行准备步骤，`--no-sync` 本身不证明本地依赖与锁一致，CI 每次用 frozen 同步。

静态阶段检查脚本语法、Git 工作树与暂存区空白，并直接检查维护中的工程 Markdown（包括存在的忽略文件）。项目目前没有配置全量 lint Gate；不把 Black/mypy 的依赖声明冒充已经通过的检查，也不借此格式化历史业务代码。

后端运行前覆盖 `DATA_DIR`、`LEDGER_FILE`、`DATABASE_FILE`、`LOG_DIR` 到新建临时目录，关闭调度器与 LLM，清空模型连接配置；退出时清理该目录。pytest 仍使用已有 `tmp_path` 夹具。这不是 OS 沙箱，新增测试仍须遵守数据边界，禁止硬编码真实路径。前端测试使用 jsdom；build 已包含 vue-tsc、Vite 与 `verify-pwa.mjs`，不再重复执行 PWA 校验。后端暂无独立构建 Gate，不虚构构建步骤。

检查写入本地临时目录、`.harness/uv-cache/`、pytest 缓存、前端构建/类型缓存，不执行迁移、真实外部调用、启动生产服务或发布。所有所选组件的环境预检均先于测试/构建；失败立即停止并保留原生退出码。缺必要命令或依赖输出 `BLOCKED` 并退出 2；未知参数也退出 2，因此需结合文字判断。只有本轮所选检查全部成功才输出 PASS，组件 PASS 不代表 all PASS。

原生结果输出到终端；pytest 缓存在 `.pytest_cache/`，前端产物在 `frontend/dist/`。新入口不生成 JSON 状态机，不把缓存或旧报告当成本轮证据。需要留证时将实际命令、退出码及摘要记入设计旁的验证记录；CI 保留任务日志。

## 按影响选择交付检查

| 改动 | 必需自动检查 | 额外场景与人工边界 |
| --- | --- | --- |
| 纯文档、注释、格式 | docs | 直接核对忽略文件前后内容及引用 |
| 后端 | backend | 受影响功能场景 |
| 前端 | frontend | 加载/空/错/重试、返回及布局人工检查 |
| 跨前后端、Harness/CI | all | Harness 自测、入口与 CI 一致性 |
| 账本写入 | backend | 金额精度、临时账本、写失败、投影一致性/DIRTY/恢复 |
| 投影 | backend | 金额精度、一致性、DIRTY、恢复 |
| 迁移 | backend | 只读预览、回滚、幂等；实际执行前人工确认外部备份 |
| 性能 | backend | 匿名真实账本 1×/2× 另行授权并核验 |
| LLM | backend | 确定性事实、本地校验、模型不可用降级 |
| PWA | frontend | 真实设备 HTTPS 安装、更新与 API 不缓存 |

叠加多个风险时取并集。迭代可定向运行 pytest/Vitest，但交付仍执行对应全量组件 Gate；账本测试必须带同等临时环境隔离，不直接使用真实配置。原生 runner 的零测试非零退出不能忽略；必需场景缺失、全跳过或未覆盖时不能宣称验收完成。上述额外场景需要核对实际测试覆盖，不靠文件名或 PASS 字样自动证明。

自动 PASS 只证明选定自动检查；未完成的必需人工验收保持“待完成/阻塞”，不得报整体完成。设计确认、自动结果、只读 Reviewer 结论与人工验收分别记录，Gate 不替开发者审批、签字或归档。

## 历史兼容

`scripts/change_harness.py`、`harness/checks.json`、`harness/policy.json` 及其测试保留原样，供明确指定的旧 change 使用。它们不再定义默认流程，CI 已切换到 Shell 入口；旧风险要求已保留在上表。历史目录不自动删除、搬迁或归档，不安装 OpenSpec CLI。旧入口不具备新 Shell 入口的统一环境隔离，不作为日常运行建议。
