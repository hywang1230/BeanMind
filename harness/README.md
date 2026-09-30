# BeanMind Harness

统一入口为 `bash scripts/verify`，CI 使用相同入口。工程与产品规则见 [开发规则](rules/README.md)；本地设计与授权见根 AGENTS.md。Harness 提供自动证据，不代替设计确认或人工验收。

## 使用

环境：Python 3.10+、uv、Git、Bash；Node 遵循 frontend/package.json engines（`^20.19.0 || >=22.12.0`）。依赖安装是独立步骤，检查不下载或升级依赖。

```bash
uv sync --frozen --dev
(cd frontend && npm ci)
bash scripts/verify            # all：静态 + 后端全量 + 前端全量 + 类型/构建/PWA
bash scripts/verify backend    # 静态 + 后端全量
bash scripts/verify frontend   # 静态 + 前端全量 + 类型/构建/PWA
bash scripts/verify docs       # 工程 Markdown 链接/空白 + Shell 语法 + Git 空白
bash run_tests.sh              # 兼容转发，等同 backend
```

可从其他工作目录调用，支持带空格的路径。所选组件全部预检后才运行；失败立即停止并保留原生退出码。环境缺失输出 BLOCKED 并退出 2；未知参数也退出 2。仅所选检查全部成功才输出 PASS，组件 PASS 不代表 all PASS。

- 静态检查包含工作树和暂存区空白，以及维护中的工程 Markdown；存在的本地忽略文档也检查，缺失不阻塞 CI。没有全量 lint Gate，不把依赖声明当作已通过的检查。
- 后端执行 `uv run --frozen --no-sync --offline pytest -q`，将 DATA_DIR、LEDGER_FILE、DATABASE_FILE、LOG_DIR 指向新建临时目录，关闭调度器与 LLM，并清空模型连接配置，退出清理目录。它不是 OS 沙箱，测试不得硬编码真实路径。
- 前端使用 jsdom 测试；build 已包含 vue-tsc、Vite 和 PWA 校验，不重复执行。后端没有独立构建 Gate。
- 修改锁文件后重新安装依赖；`--no-sync` 不证明本地与锁一致，CI 使用 frozen 同步。
- 结果输出到终端，不生成状态机报告。检查会写临时目录、.harness/uv-cache/、pytest 与前端缓存/产物，不执行迁移、真实外部调用、生产服务启动或发布。

## 交付检查

| 改动 | 自动检查 | 额外场景与人工边界 |
| --- | --- | --- |
| 纯文档、注释、格式 | docs | 直接核对忽略文件前后内容与引用 |
| 后端 | backend | 受影响功能场景 |
| 前端 | frontend | 加载/空/错/重试、返回及布局 |
| 跨前后端、Harness/CI | all | Harness 自测、入口与 CI 一致性 |
| 账本写入、投影 | backend | 金额精度、临时账本、写失败、投影一致性/DIRTY/恢复；纯投影改动按实际影响选择写入场景 |
| 迁移 | backend | 只读预览、回滚、幂等；实际执行前确认外部可恢复备份 |
| 性能 | backend | 经授权的匿名真实账本 1×/等分布 2× |
| LLM | backend | 确定性事实、本地校验、模型不可用降级 |
| PWA | frontend | 真实设备 HTTPS 安装、更新、API 不缓存 |

风险叠加取并集。迭代可定向运行 pytest/Vitest，交付运行对应全量组件；定向后端测试须使用同等临时环境隔离。保留 runner 的零测试失败语义；必需场景缺失、全跳过或未覆盖，不能宣称验收完成。额外场景核对实际测试，文件名和 PASS 不证明覆盖。

自动 PASS 只证明本轮选定检查。设计确认、只读 Reviewer 和必需人工验收分别说明；未完成项保持待完成/阻塞。需要留证时记录实际命令、退出码、摘要与未覆盖项，CI 保留任务日志，不把旧报告当作本轮证据。
