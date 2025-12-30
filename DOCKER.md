# Docker 部署指南

本文档介绍如何使用 Docker 部署 BeanMind 应用。

## 前置要求

- Docker 20.10+
- Docker Compose v2+

## 快速开始

### 方式一：使用 Docker Compose（推荐）

1. **复制环境变量配置文件**
   ```bash
   cp .env.example .env
   ```

2. **编辑 `.env` 文件**，修改必要的配置：
   ```bash
   # 必须修改的配置
   JWT_SECRET_KEY=your-super-secret-key   # 修改为安全的密钥
   SINGLE_USER_PASSWORD=your-password     # 修改为安全的密码
   ```

3. **启动服务**
   ```bash
   docker compose up -d
   ```

4. **访问应用**
   - 应用地址: http://localhost:8000
   - API 文档: http://localhost:8000/docs

### 方式二：使用 Docker Run

```bash
docker run -d \
  --name beanmind \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -e AUTH_MODE=single_user \
  -e SINGLE_USER_USERNAME=admin \
  -e SINGLE_USER_PASSWORD=your-password \
  -e JWT_SECRET_KEY=your-super-secret-key \
  pionnerwang/beanmind:latest
```

## 数据持久化

应用数据存储在以下目录：

| 容器路径 | 说明 |
|---------|------|
| `/app/data/ledger/` | Beancount 账本文件 |
| `/app/data/beanmind.db` | SQLite 数据库 |
| `/app/logs/` | 应用日志 |

确保挂载这些目录以持久化数据：

```yaml
volumes:
  - ./data:/app/data
  - ./logs:/app/logs
```

## 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `AUTH_MODE` | `single_user` | 认证模式：`none`、`single_user`、`multi_user` |
| `SINGLE_USER_USERNAME` | `admin` | 单用户模式用户名 |
| `SINGLE_USER_PASSWORD` | `changeme` | 单用户模式密码 |
| `JWT_SECRET_KEY` | - | JWT 密钥（**必须修改**） |
| `JWT_EXPIRATION_HOURS` | `24` | JWT 过期时间（小时） |
| `AI_ENABLED` | `false` | 是否启用 AI 功能 |
| `DEBUG` | `false` | 调试模式 |

## 本地构建

如果需要本地构建镜像：

```bash
# 构建镜像
docker compose build

# 或直接构建后运行
docker compose up -d --build
```

## 常用命令

```bash
# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f

# 停止服务
docker compose down

# 重新构建并启动
docker compose up -d --build

# 进入容器
docker compose exec beanmind /bin/bash
```

## 健康检查

应用提供健康检查端点：

```bash
curl http://localhost:8000/health
# 返回: {"status": "ok"}
```

## GitHub Actions CI/CD

项目配置了 GitHub Actions 自动构建流程：

- **触发条件**: 推送到 `main` 分支
- **构建内容**: 自动构建 Docker 镜像并推送到 Docker Hub

### 配置 GitHub Secrets

在 GitHub 仓库设置中添加以下 Secrets：

| Secret 名称 | 说明 |
|-------------|------|
| `DOCKERHUB_USERNAME` | Docker Hub 用户名 |
| `DOCKERHUB_TOKEN` | Docker Hub Access Token |

### 获取 Docker Hub Token

1. 登录 [Docker Hub](https://hub.docker.com/)
2. 进入 Account Settings → Security
3. 点击 "New Access Token"
4. 创建一个具有 Read & Write 权限的 Token

## 故障排除

### 容器无法启动

检查日志：
```bash
docker compose logs beanmind
```

### 数据目录权限问题

确保数据目录有正确的权限：
```bash
sudo chown -R 1000:1000 ./data ./logs
```

### 端口冲突

如果 8000 端口被占用，修改 `docker-compose.yml` 中的端口映射：
```yaml
ports:
  - "8080:8000"  # 改为其他端口
```
