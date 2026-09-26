#!/usr/bin/env bash
# 兼容旧入口：统一前置检查、临时数据隔离和失败退出码。
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
[[ $# -eq 0 ]] || { echo 'Usage: bash run_tests.sh' >&2; exit 2; }
exec bash "$ROOT/scripts/verify" backend
