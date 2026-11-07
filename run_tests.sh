#!/usr/bin/env bash
# 兼容旧入口：临时数据隔离后运行后端 pytest。
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
[[ $# -eq 0 ]] || { echo 'Usage: bash run_tests.sh' >&2; exit 2; }

blocked() { echo "BLOCKED: $*" >&2; exit 2; }
command -v uv >/dev/null || blocked '需要 uv；先执行 uv sync --frozen --dev'
[[ -x .venv/bin/python ]] || blocked '缺少 .venv；先执行 uv sync --frozen --dev'

VERIFY_TMP="$(mktemp -d "${TMPDIR:-/tmp}/beanmind-verify.XXXXXX")"
trap 'rm -rf -- "$VERIFY_TMP"' EXIT
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export DATA_DIR="$VERIFY_TMP/data"
export LEDGER_FILE="$VERIFY_TMP/data/ledger/main.beancount"
export DATABASE_FILE="$VERIFY_TMP/data/beanmind.db"
export LOG_DIR="$VERIFY_TMP/logs"
export SCHEDULER_ENABLED=false
export LLM_ENABLED=false
export LLM_API_KEY=''
export LLM_BASE_URL=''
export LLM_MODEL=''
uv run --frozen --no-sync --offline pytest -q
