#!/bin/bash
# BeanMind 单元测试运行脚本

echo "=========================================="
echo "BeanMind Unit Tests"
echo "=========================================="
echo ""

# 检查 uv
UV_BIN="${HOME}/.local/bin/uv"
if command -v uv >/dev/null 2>&1; then
  UV_BIN="uv"
elif [ ! -x "$UV_BIN" ]; then
  echo "uv 未安装，请先安装 uv"
  exit 1
fi

# 同步依赖
$UV_BIN sync --dev

# 运行所有测试
$UV_BIN run pytest tests/ -v --tb=short --cov=backend --cov-report=term-missing

# 显示测试统计
echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
