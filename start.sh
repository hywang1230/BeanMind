#!/bin/bash

# BeanMind 一键启动脚本
# 功能：
# 1. 检查环境和依赖
# 2. 启动后端服务
# 3. 启动前端服务

set -e  # 遇到错误立即退出

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 打印分隔线
print_separator() {
    echo -e "${BLUE}========================================${NC}"
}

# 检查命令是否存在
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 停止所有服务
cleanup() {
    log_info "正在停止所有服务..."
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
        log_info "后端服务已停止 (PID: $BACKEND_PID)"
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
        log_info "前端服务已停止 (PID: $FRONTEND_PID)"
    fi
    exit 0
}

# 注册退出信号处理
trap cleanup SIGINT SIGTERM

print_separator
log_info "🚀 BeanMind 启动脚本"
print_separator

# ==================== 1. 环境检查 ====================
log_info "步骤 1/6: 检查环境依赖..."

# 检查 Python
if ! command_exists python3; then
    log_error "Python3 未安装！请先安装 Python 3.9+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
log_success "Python 版本: $PYTHON_VERSION"

# 检查 Node.js
if ! command_exists node; then
    log_error "Node.js 未安装！请先安装 Node.js 18+"
    exit 1
fi

NODE_VERSION=$(node --version)
log_success "Node.js 版本: $NODE_VERSION"

# 检查 npm
if ! command_exists npm; then
    log_error "npm 未安装！请先安装 npm"
    exit 1
fi

NPM_VERSION=$(npm --version)
log_success "npm 版本: $NPM_VERSION"

# ==================== 2. Python 虚拟环境 ====================
log_info "步骤 2/6: 检查 Python 虚拟环境..."

if [ ! -d "venv" ]; then
    log_warning "虚拟环境不存在，正在创建..."
    python3 -m venv venv
    log_success "虚拟环境创建完成"
fi

# 激活虚拟环境
source venv/bin/activate
log_success "虚拟环境已激活"

# 检查并安装 Python 依赖
if [ ! -f "venv/.dependencies_installed" ]; then
    log_info "正在安装 Python 依赖..."
    pip install --upgrade pip
    pip install -r requirements.txt
    touch venv/.dependencies_installed
    log_success "Python 依赖安装完成"
else
    log_success "Python 依赖已安装"
fi

# ==================== 3. 前端依赖 ====================
log_info "步骤 3/6: 检查前端依赖..."

cd frontend

if [ ! -d "node_modules" ]; then
    log_info "正在安装前端依赖..."
    npm install
    log_success "前端依赖安装完成"
else
    log_success "前端依赖已安装"
fi

cd "$SCRIPT_DIR"

# ==================== 4. 初始化数据文件 ====================
log_info "步骤 4/6: 初始化数据文件..."

# 检查 .env 文件
if [ ! -f ".env" ]; then
    log_warning ".env 文件不存在，正在从 .env.example 复制..."
    cp .env.example .env
    log_success ".env 文件已创建"
    log_warning "⚠️  请编辑 .env 文件，修改默认密码和其他配置！"
else
    log_success ".env 文件已存在"
fi

# 创建数据目录
mkdir -p data/ledger
mkdir -p data/backups

# 检查主账本文件
if [ ! -f "data/ledger/main.beancount" ]; then
    log_info "正在创建初始账本文件..."
    cat > data/ledger/main.beancount << 'EOF'
;; BeanMind 主账本文件
;; 创建日期: $(date +%Y-%m-%d)

option "title" "BeanMind 个人账本"
option "operating_currency" "CNY"

;; 账户定义
2024-01-01 open Assets:Cash CNY
2024-01-01 open Assets:Bank:Checking CNY
2024-01-01 open Income:Salary CNY
2024-01-01 open Expenses:Food CNY
2024-01-01 open Expenses:Transportation CNY
2024-01-01 open Expenses:Shopping CNY
2024-01-01 open Equity:Opening-Balances CNY

;; 初始余额（示例）
2024-01-01 * "初始余额"
  Assets:Cash         1000.00 CNY
  Assets:Bank:Checking 10000.00 CNY
  Equity:Opening-Balances
EOF
    log_success "初始账本文件已创建"
else
    log_success "账本文件已存在"
fi

log_success "数据文件初始化完成"

# ==================== 5. 启动后端服务 ====================
print_separator
log_info "步骤 5/6: 启动后端服务..."

# 使用 uvicorn 启动后端（在项目根目录运行）
log_info "后端服务正在启动，监听端口: 8000"
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload > logs/backend.log 2>&1 &
BACKEND_PID=$!

# 等待后端启动
sleep 3

if kill -0 $BACKEND_PID 2>/dev/null; then
    log_success "后端服务启动成功 (PID: $BACKEND_PID)"
    log_info "后端地址: http://localhost:8000"
    log_info "API 文档: http://localhost:8000/docs"
else
    log_error "后端服务启动失败！请查看日志: logs/backend.log"
    exit 1
fi

# ==================== 6. 启动前端服务 ====================
log_info "步骤 6/6: 启动前端服务..."

cd frontend

# 使用 Vite 启动前端
log_info "前端服务正在启动，监听端口: 5173"
npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!

# 等待前端启动
sleep 3

if kill -0 $FRONTEND_PID 2>/dev/null; then
    log_success "前端服务启动成功 (PID: $FRONTEND_PID)"
    log_info "前端地址: http://localhost:5173"
else
    log_error "前端服务启动失败！请查看日志: logs/frontend.log"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

cd "$SCRIPT_DIR"

# ==================== 启动完成 ====================
print_separator
log_success "✨ BeanMind 启动完成！"
print_separator
echo ""
echo -e "${GREEN}服务地址:${NC}"
echo -e "  🌐 前端应用: ${BLUE}http://localhost:5173${NC}"
echo -e "  🔌 后端 API: ${BLUE}http://localhost:8000${NC}"
echo -e "  📚 API 文档: ${BLUE}http://localhost:8000/docs${NC}"
echo ""
echo -e "${YELLOW}服务进程:${NC}"
echo -e "  后端 PID: $BACKEND_PID"
echo -e "  前端 PID: $FRONTEND_PID"
echo ""
echo -e "${YELLOW}日志文件:${NC}"
echo -e "  后端日志: logs/backend.log"
echo -e "  前端日志: logs/frontend.log"
echo ""
echo -e "${RED}按 Ctrl+C 停止所有服务${NC}"
print_separator

# 保持脚本运行，等待用户中断
wait
