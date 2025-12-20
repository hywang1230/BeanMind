#!/bin/bash
# BeanMind 单元测试运行脚本

echo "=========================================="
echo "BeanMind Unit Tests"
echo "=========================================="
echo ""

# 激活虚拟环境 
source venv/bin/activate

# 运行所有测试
pytest tests/ -v --tb=short --cov=backend --cov-report=term-missing

# 显示测试统计
echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
