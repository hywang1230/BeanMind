# 🐛 前端 API 调用问题修复

## 问题描述

当通过 IP 地址访问 BeanMind 时（例如 `http://192.168.31.254:8000`），前端页面会被重定向到登录页，即使后端配置了 `auth_mode: "none"`。

## 根本原因

在 `frontend/src/api/client.ts` 中，使用了错误的逻辑运算符来处理 `baseURL` 配置：

```typescript
// 错误的写法
baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
```

当 `VITE_API_BASE_URL` 设置为空字符串 `""` 时（Dockerfile 中的配置），JavaScript 的 `||` 运算符会将其视为 `falsy` 值，导致使用后备值 `'http://localhost:8000'`。

**结果**：浏览器尝试向 `http://localhost:8000/api/config` 发起请求，而不是相对路径，导致 `ERR_CONNECTION_REFUSED` 错误。

## 解决方案

将 `||` 改为 `??`（空值合并运算符）：

```typescript
// 正确的写法
baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
```

这样当环境变量是空字符串时，会正确使用空字符串作为 baseURL（即使用相对路径）。

## 重新部署步骤

### 1. 停止并删除现有容器

```bash
docker-compose down
```

### 2. 重新构建 Docker 镜像

```bash
docker-compose build
```

### 3. 启动新容器

```bash
docker-compose up -d
```

### 4. 验证修复

访问以下 URL：

- **后端 API**: `http://192.168.31.254:8000/api`
  - 应该返回：`{"message":"Welcome to BeanMind API","version":"0.1.0","status":"healthy","auth_mode":"none"}`

- **前端页面**: `http://192.168.31.254:8000/`
  - 如果 `auth_mode` 是 `"none"`，应该直接显示主页
  - 如果是其他模式，应该显示登录页

- **配置接口**: `http://192.168.31.254:8000/api/config`
  - 应该返回：`{"auth_mode":"none","ai_enabled":true,"github_sync_enabled":true}`

### 5. 浏览器控制台检查

打开浏览器开发者工具（F12），切换到：

- **Console 标签**：应该不再有 `ERR_CONNECTION_REFUSED` 错误
- **Network 标签**：找到 `/api/config` 请求
  - Status: `200 OK`
  - Request URL: `http://192.168.31.254:8000/api/config` ✓

## 技术细节：|| vs ??

| 运算符 | 行为 | 示例 |
|--------|-----|------|
| `||` | 左侧为 falsy (`false`, `0`, `""`, `null`, `undefined`, `NaN`) 时返回右侧 | `"" || "default"` → `"default"` |
| `??` | 左侧为 `null` 或 `undefined` 时返回右侧 | `"" ?? "default"` → `""` |

对于我们的场景：
- **空字符串 `""`** 是有意义的值（表示使用相对路径）
- 应该使用 `??` 而不是 `||`

## 相关文件

- `frontend/src/api/client.ts` - 已修复
- `Dockerfile` - 环境变量配置
- `backend/main.py` - API 路由配置
