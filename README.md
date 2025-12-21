# BeanMind

基于 Beancount 的个人财务管理系统

## 项目概述

BeanMind 是一个功能完整的个人记账软件，提供：
- ✅ 灵活的鉴权系统（单用户/无用户模式）
- 📝 完整的记账功能（收入/支出/转账）
- 💰 智能预算管理
- 🔄 周期任务自动化
- 📊 数据分析与可视化
- 🤖 AI 财务助手
- 💾 可插拔的数据备份

## 技术栈

**后端**：
- Python 3.10+
- FastAPI
- Beancount
- SQLite
- SQLAlchemy

**前端**：
- Vue 3
- Framework7-Vue
- Pinia
- Vite

## 项目结构

```
BeanMind/
├── backend/                 # 后端代码
│   ├── main.py             # 应用入口
│   ├── config/             # 配置管理
│   ├── interfaces/         # 接口层（API、DTO）
│   ├── application/        # 应用层（服务、编排）
│   ├── domain/             # 领域层（实体、服务、仓储接口）
│   └── infrastructure/     # 基础设施层（数据库、Beancount、备份）
├── frontend/               # 前端代码
│   └── src/
├── data/                   # 数据目录
│   ├── ledger/            # Beancount 账本文件
│   └── beanmind.db        # SQLite 数据库
└── design/                 # 设计文档
```

## 快速开始

### 方式一：一键启动（推荐）

```bash
# 首次运行会自动：
# - 检查并创建虚拟环境
# - 安装后端依赖
# - 安装前端依赖
# - 初始化数据文件
# - 同时启动后端和前端服务
./start.sh
```

启动成功后：
- 🌐 前端应用：http://localhost:5173
- 🔌 后端 API：http://localhost:8000
- 📚 API 文档：http://localhost:8000/docs

停止服务：
```bash
# 按 Ctrl+C 停止，或使用停止脚本
./stop.sh
```

### 方式二：手动启动

**后端**：

```bash
# 创建并激活虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动服务
cd backend
uvicorn main:app --reload
```

**前端**：

```bash
cd frontend
npm install
npm run dev
```

## 环境变量

复制 `.env.example` 为 `.env` 并配置：

```bash
# 鉴权模式
AUTH_MODE=single_user
SINGLE_USER_USERNAME=admin
SINGLE_USER_PASSWORD=your-password

# JWT 配置
JWT_SECRET_KEY=your-secret-key
JWT_EXPIRATION_HOURS=24

# 数据路径
DATA_DIR=./data
```

## 设计文档

详细的系统设计文档位于 `/design/` 目录：
- [系统架构设计](design/system_architecture.md)
- [数据库设计](design/database_design.md)
- [功能模块设计](design/module_design.md)
- [API 接口设计](design/api_design.md)
- [前端页面设计](design/frontend_design.md)

## 开发状态

🚧 当前处于开发阶段，正在按照执行计划逐步实施。

查看 [执行计划](design/execution_plan.md) 了解开发进度。

## License

MIT
