# BeanMind Frontend

BeanMind 的前端应用，使用 Vue 3 + TypeScript + Vite 构建。

## 技术栈

- Vue 3 - 渐进式 JavaScript 框架
- TypeScript - 类型安全的 JavaScript 超集
- Vite - 下一代前端构建工具
- Vue Router - Vue.js 官方路由
- Pinia - Vue 状态管理库
- Axios - HTTP 客户端

## 开发

### Node.js 版本要求

- `>=20.19.0`（推荐 `22.12.0`，见 `.nvmrc`）

### 安装依赖

```bash
npm install
```

### 启动开发服务器

```bash
npm run dev
```

开发服务器将在 http://localhost:5173/ 启动

### 环境变量

复制 `.env.example` 到 `.env` 并配置：

```
VITE_API_BASE_URL=http://localhost:8000
```

## 构建

```bash
npm run build
```

构建输出将生成在 `dist/` 目录中。

## 项目结构

```
src/
├── api/          # API 客户端
├── components/   # 公共组件
├── pages/        # 页面组件
├── router/       # 路由配置
├── stores/       # Pinia stores
├── App.vue       # 根组件
└── main.ts       # 入口文件
```

## 主要功能

### 已完成
- ✅ 用户认证（登录/登出）
- ✅ 交易管理（列表、新增）
- ✅ 账户管理
- ✅ 仪表盘
- ✅ 预算管理（预算列表、创建、执行情况查看）
- ✅ 周期任务（规则管理、频率配置、执行控制）

### 待开发
- ⏳ 设置页面
- ⏳ 数据导入/导出
- ⏳ AI 分析
