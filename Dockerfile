# =============================================================================
# BeanMind Docker 镜像 - 多阶段构建
# 包含：前端 (Vue + Vite) + 后端 (Python FastAPI)
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: 构建前端
# -----------------------------------------------------------------------------
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# 复制 package 文件并安装依赖
COPY frontend/package*.json ./
RUN npm ci

# 复制前端源码
COPY frontend/ ./

# 设置 API 基础 URL 为空（使用相对路径，因为前后端在同一容器）
ENV VITE_API_BASE_URL=""

# 构建前端
RUN npm run build

# -----------------------------------------------------------------------------
# Stage 2: 生产环境镜像
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS production

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/home/app/project \
    TZ=Asia/Shanghai

# 使用更深的目录结构以满足 AgentUniverse 对 parents[1] 的要求
# AgentUniverse 使用 current_work_directory.parents[1] 获取项目根路径
# /home/app/project 的 parents: [0]=/home/app, [1]=/home, [2]=/
WORKDIR /home/app/project

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 复制 Python 依赖文件
COPY requirements.txt ./

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY backend/ ./backend/
COPY pyproject.toml ./

# 从前端构建阶段复制构建产物
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# 复制入口脚本
COPY docker-entrypoint.sh /home/app/project/docker-entrypoint.sh

# 创建数据目录
RUN mkdir -p /home/app/project/data/ledger /home/app/project/data/backups /home/app/project/logs

# 使用 root 用户运行（解决开发环境权限问题）
RUN chmod +x /home/app/project/docker-entrypoint.sh

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1


# 设置入口脚本
ENTRYPOINT ["/home/app/project/docker-entrypoint.sh"]

# 默认启动命令
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
