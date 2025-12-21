#!/bin/bash

# BeanMind 停止脚本
# 功能：停止所有运行中的 BeanMind 服务

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

echo -e "${BLUE}========================================${NC}"
log_info "🛑 停止 BeanMind 服务"
echo -e "${BLUE}========================================${NC}"

# 停止后端服务 (uvicorn)
BACKEND_PIDS=$(pgrep -f "uvicorn main:app")
if [ ! -z "$BACKEND_PIDS" ]; then
    log_info "正在停止后端服务..."
    echo "$BACKEND_PIDS" | xargs kill 2>/dev/null
    sleep 1
    log_success "后端服务已停止"
else
    log_warning "未找到运行中的后端服务"
fi

# 停止前端服务 (vite)
FRONTEND_PIDS=$(pgrep -f "vite")
if [ ! -z "$FRONTEND_PIDS" ]; then
    log_info "正在停止前端服务..."
    echo "$FRONTEND_PIDS" | xargs kill 2>/dev/null
    sleep 1
    log_success "前端服务已停止"
else
    log_warning "未找到运行中的前端服务"
fi

echo -e "${BLUE}========================================${NC}"
log_success "✨ 所有服务已停止"
echo -e "${BLUE}========================================${NC}"
