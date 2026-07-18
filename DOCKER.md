# Docker 部署指南

本文档对应仓库内当前 Docker 文件：`Dockerfile`、`docker-compose.yml`、`docker-entrypoint.sh`。

BeanMind 为**单机、单账本、单写者**部署：不提供登录、权限、远端同步或应用内备份中心。备份由 NAS 或部署环境负责。

## 前置要求

- Docker 20.10+
- Docker Compose v2+

## 镜像内容

多阶段构建的一体化镜像：

1. **前端**：`node:20-alpine` 构建 Vue 3 + Vite，产物复制到 `frontend/dist`
2. **后端**：`python:3.11-slim`，用 `uv` 按 `pyproject.toml` / `uv.lock` 安装依赖
3. **运行**：同一进程内用 FastAPI 提供 API，并托管前端静态资源

| 项 | 值 |
|----|-----|
| 镜像名 | `pionnerwang/beanmind` |
| 默认标签 | `latest` |
| 容器工作目录 | `/home/app/project` |
| 对外端口 | `8000` |
| 启动命令 | `uvicorn backend.main:app --host 0.0.0.0 --port 8000` |
| 健康检查 | `GET /health` → `{"status":"ok"}` |

镜像内 `VITE_API_BASE_URL` 为空，前端使用相对路径访问同源 API。

## 快速开始

### 方式一：Docker Compose（推荐）

1. **准备环境变量**

   ```bash
   cp .env.example .env
   ```

   按需编辑 `.env`（见下方环境变量表）。compose 会读取同目录 `.env`。

2. **启动**

   ```bash
   # 使用已发布镜像
   docker compose up -d

   # 或本地构建后启动
   docker compose up -d --build
   ```

3. **访问**

   - 应用：http://localhost:8000
   - API 文档：http://localhost:8000/docs
   - 健康检查：http://localhost:8000/health

### 方式二：Docker Run

```bash
docker run -d \
  --name beanmind \
  -p 8000:8000 \
  -v "$(pwd)/data:/home/app/project/data" \
  -v "$(pwd)/logs:/home/app/project/logs" \
  -e DATA_DIR=/home/app/project/data \
  -e LEDGER_FILE=/home/app/project/data/ledger/main.beancount \
  -e DATABASE_FILE=/home/app/project/data/beanmind.db \
  -e LOG_DIR=/home/app/project/logs \
  -e CORS_ORIGINS='*' \
  -e DEBUG=false \
  pionnerwang/beanmind:latest
```

启用可选 AI 月度复盘时再传入 `LLM_*` 变量（见下表）。

## 数据持久化

容器内路径以 **`/home/app/project`** 为根（不是历史文档中的 `/app`）。

| 容器路径 | 说明 |
|---------|------|
| `/home/app/project/data/ledger/` | Beancount 账本（真值） |
| `/home/app/project/data/beanmind.db` | SQLite（应用数据 + 可重建查询投影） |
| `/home/app/project/logs/` | 应用日志 |

`docker-compose.yml` 默认挂载：

```yaml
volumes:
  - ./data:/home/app/project/data
  - ./logs:/home/app/project/logs
```

约定：

- Beancount 是账户与交易唯一真值；SQLite 投影可删后重建。
- 禁止从 SQLite 反向覆盖 Beancount。
- 投影异常时系统会标记 `DIRTY`，不返回可能错误的预算/统计结果。
- 需要全量重建投影时：

  ```bash
  curl -X POST http://localhost:8000/api/transactions/projection/rebuild
  ```

### 从 `main` 升级到 3.0.0

升级必须在旧容器停止后进行，避免 SQLite WAL 或周期调度器继续写入：

```bash
docker compose down
cp ./data/beanmind.db /外部备份目录/beanmind-before-v3.db
cp -R ./data/ledger /外部备份目录/ledger-before-v3
```

先在同一版本代码目录执行只读预览：

```bash
uv run python scripts/migrate_v3.py ./data/beanmind.db \
  --ledger ./data/ledger/main.beancount
```

确认以下内容后再应用：

- `ledger.errors` 为空，交易数和分录数符合账本实际情况；
- `recurring.orphan_rule_ids` 为空，周期规则数和执行数正确；
- `drop_budgets` 是允许永久丢弃的旧预算数据；
- `--backup` 指向停机后生成、与源数据库 SHA-256 完全一致的外部备份。
- `database_sidecars.-wal` 不存在或为空；非空 WAL 说明仍有未合并写入，迁移会拒绝执行。

```bash
uv run python scripts/migrate_v3.py ./data/beanmind.db \
  --ledger ./data/ledger/main.beancount \
  --apply \
  --backup /外部备份目录/beanmind-before-v3.db \
  --confirm-drop-budgets
docker compose up -d
```

迁移脚本不会修改 Beancount。成功报告必须显示流水投影核对通过、周期规则和执行记录数量不变、当前月度预算表为空。结构事务失败会自动回滚；若提交后投影或启动核对失败，停止容器并用外部备份恢复 `beanmind.db`，不要用 SQLite 覆盖账本。

`main` 到 3.0.0 的数据库覆盖关系如下：

| `main` / 中间版本数据 | 3.0.0 处理方式 | 核对标准 |
|---|---|---|
| Beancount 流水 | 原文件只读保留；删除旧 `transaction_metadata` 和投影后重建 | 文件指纹不变，交易数、分录数和 Decimal 汇总一致，投影 `READY` |
| `recurring_rules` | 仅移除 `user_id`，其余字段按原 ID 复制 | 规则数量与 ID 集合不变 |
| `recurring_executions` | 原表原记录保留 | 执行数量、ID、`rule_id` 关联不变，无孤儿外键 |
| `budgets` / `budget_items` / `budget_cycles` | 删除，不转换 | 预览列出删除数量 |
| 中间版本 `monthly_budgets` / `monthly_budget_items` | 删除并创建当前空结构 | 两张当前表存在且均为 0 条 |
| 用户、同步、备份、旧配置、旧 AI、旧月报 | 删除 | 迁移后废弃表不存在 |
| 币种、月度复盘等 3.0.0 新表 | 由当前 SQLAlchemy 模型创建 | 当前应用可启动并正常查询 |

## 自动初始化

入口脚本 `docker-entrypoint.sh` 在启动 uvicorn 前执行：

1. **数据库**：若 `DATABASE_FILE` 不存在，运行  
   `python -m backend.infrastructure.persistence.init_db --db-path ...`
2. **账本**：若 `LEDGER_FILE` 不存在，运行  
   `python -m backend.infrastructure.persistence.beancount.init_ledger --ledger-path ...`
3. **应用**：执行镜像默认 CMD（uvicorn）

应用启动生命周期内还会再次确保数据库表与账本查询投影就绪（投影失败记日志并标记 DIRTY，不阻断容器进程）。

### 查看启动日志

```bash
docker compose logs -f beanmind
```

首次启动大致输出：

```text
==========================================
🚀 BeanMind 容器启动中...
==========================================

[1/3] 检查数据库...
...
[2/3] 检查账本文件...
...
[3/3] 启动应用...
==========================================
🎉 初始化完成，正在启动服务...
==========================================
```

### 重新初始化（会清空数据）

```bash
docker compose down
rm -rf ./data/   # 谨慎：删除账本与数据库
docker compose up -d
```

## 环境变量

配置源：`.env.example`、`backend/config/settings.py`。未知变量会被忽略（`extra="ignore"`）。

### 数据路径

| 变量名 | 容器内建议值 | 说明 |
|--------|--------------|------|
| `DATA_DIR` | `/home/app/project/data` | 数据根目录 |
| `LEDGER_FILE` | `/home/app/project/data/ledger/main.beancount` | Beancount 入口账本 |
| `DATABASE_FILE` | `/home/app/project/data/beanmind.db` | SQLite 路径 |
| `LOG_DIR` | `/home/app/project/logs` | 日志目录 |

相对路径会相对于项目根解析；容器内请使用上表绝对路径（compose 已写好）。

### 周期记账调度

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `SCHEDULER_ENABLED` | `true` | 是否启用周期记账调度 |
| `SCHEDULER_HOUR` | `12` | 每日执行小时 |
| `SCHEDULER_MINUTE` | `0` | 每日执行分钟 |
| `SCHEDULER_TIMEZONE` | `Asia/Shanghai` | 调度时区 |

### 可选 LLM（月度复盘）

默认关闭。仅用于生成月度总结与建议；金额/预算/趋势由确定性代码计算。失败不影响记账与查询。

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `LLM_ENABLED` | `false` | 是否启用 |
| `LLM_BASE_URL` | 空 | OpenAI-compatible 接口 base URL |
| `LLM_API_KEY` | 空 | API Key |
| `LLM_MODEL` | `gpt-4o-mini` | 模型名 |
| `LLM_TIMEOUT_SECONDS` | `30` | 超时秒数 |

### 服务

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `API_HOST` | `0.0.0.0` | 监听地址（镜像内 uvicorn 已固定 0.0.0.0） |
| `API_PORT` | `8000` | 端口（容器内） |
| `DEBUG` | 本地示例为 `true`；生产建议 `false` | 调试模式 |
| `CORS_ORIGINS` | 本地开发多源；compose 默认可为 `*` | 逗号分隔的 CORS 源 |
| `LOG_LEVEL` | `INFO` | 日志级别 |

### 已移除、勿再配置

以下能力已从当前单机架构删除；写入环境变量也不会生效：

- `AUTH_MODE` / `SINGLE_USER_*` / `JWT_*`（无登录鉴权）

> 说明：环境变量以 `backend/config/settings.py` 与 `.env.example` 为准；`docker-compose.yml` 会为容器内数据/日志路径写入绝对路径。

## 本地构建

```bash
docker compose build
docker compose up -d --build
```

构建要点：

- 前端：`npm ci` + `npm run build`（`VITE_API_BASE_URL=""`）
- 后端：`uv sync --frozen --no-dev --no-install-project`
- 本地非 Docker 开发优先 `uv sync` / `uv run`，不要再使用 `requirements.txt` + pip

## 常用命令

```bash
# 状态
docker compose ps

# 日志
docker compose logs -f beanmind

# 停止
docker compose down

# 重建并启动
docker compose up -d --build

# 进入容器
docker compose exec beanmind /bin/bash

# 健康检查
curl -f http://localhost:8000/health
```

## 故障排除

### 容器无法启动

```bash
docker compose logs beanmind
```

常见原因：入口脚本初始化失败、挂载目录权限、端口占用、镜像构建时前端/依赖失败。

### 数据目录权限

镜像以 root 运行（便于开发环境写挂载卷）。若宿主机目录权限异常，可调整宿主机 `./data`、`./logs` 的所有者或权限，确保容器可写。

### 端口冲突

修改 `docker-compose.yml`：

```yaml
ports:
  - "8080:8000"
```

### 投影 / 统计异常

```bash
curl -X POST http://localhost:8000/api/transactions/projection/rebuild
```

仍异常时优先检查 Beancount 账本语法与挂载路径是否指向正确文件，不要用手工改 SQLite 去“对齐”账本。

### 前端空白或 404

确认镜像构建包含 `frontend/dist`（完整 `docker compose build`），且访问的是容器 `8000` 端口而不是本地 Vite 开发端口。

## 相关文件

| 文件 | 作用 |
|------|------|
| `Dockerfile` | 多阶段构建 |
| `docker-compose.yml` | 本地/部署编排与卷挂载 |
| `docker-entrypoint.sh` | 首次启动初始化 DB/账本 |
| `.dockerignore` | 构建上下文忽略项 |
| `.env.example` | 环境变量模板 |
