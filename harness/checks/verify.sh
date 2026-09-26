#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
usage() { echo 'Usage: bash scripts/verify [all|backend|frontend|docs]'; }
blocked() { echo "BLOCKED: $*" >&2; exit 2; }
[[ $# -le 1 ]] || { usage >&2; exit 2; }
SCOPE="${1:-all}"
case "$SCOPE" in
  all|backend|frontend|docs) ;;
  -h|--help) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
esac
command -v git >/dev/null || blocked '需要 git'
command -v python3 >/dev/null || blocked '需要 Python 3.10+'
# 所有环境预检完成后才运行测试与构建；不在检查入口隐式安装依赖。
if [[ "$SCOPE" == all || "$SCOPE" == backend ]]; then
  command -v uv >/dev/null || blocked '需要 uv；先执行 uv sync --frozen --dev'
  [[ -x .venv/bin/python ]] || blocked '缺少 .venv；先执行 uv sync --frozen --dev'
  .venv/bin/python -c 'import pytest, fastapi, sqlalchemy, pydantic, beancount, httpx, apscheduler' \
    || blocked '后端依赖不完整；先执行 uv sync --frozen --dev'
fi
if [[ "$SCOPE" == all || "$SCOPE" == frontend ]]; then
  command -v node >/dev/null || blocked '需要符合 frontend/package.json engines 的 Node'
  command -v npm >/dev/null || blocked '需要 npm'
  node -e 'const [a,b]=process.versions.node.split(".").map(Number); process.exit((a===20&&b>=19)||(a===22&&b>=12)||a>22?0:1)' \
    || blocked 'Node 版本不符合 ^20.19.0 || >=22.12.0'
  for tool in vitest vue-tsc vite; do
    [[ -x "frontend/node_modules/.bin/$tool" ]] || blocked '前端依赖不完整；先在 frontend 执行 npm ci'
  done
fi
printf '\n== Static checks ==\n'
for script in scripts/verify harness/checks/verify.sh run_tests.sh; do
  bash -n "$script"
done
git diff --check
git diff --cached --check
python3 harness/checks/check_docs.py
if [[ "$SCOPE" == all || "$SCOPE" == backend ]]; then
  VERIFY_TMP="$(mktemp -d "${TMPDIR:-/tmp}/beanmind-verify.XXXXXX")"
  trap 'rm -rf -- "$VERIFY_TMP"' EXIT
  export DATA_DIR="$VERIFY_TMP/data" LEDGER_FILE="$VERIFY_TMP/data/ledger/main.beancount"
  export DATABASE_FILE="$VERIFY_TMP/data/beanmind.db" LOG_DIR="$VERIFY_TMP/logs"
  export SCHEDULER_ENABLED=false LLM_ENABLED=false LLM_API_KEY='' LLM_BASE_URL='' LLM_MODEL=''
  export UV_CACHE_DIR="$ROOT/.harness/uv-cache"
  printf '\n== Backend tests (temporary data) ==\n'
  uv run --frozen --no-sync --offline pytest -q
fi
if [[ "$SCOPE" == all || "$SCOPE" == frontend ]]; then
  printf '\n== Frontend tests ==\n'
  (cd frontend && npm run test:run)
  printf '\n== Frontend build, types and PWA ==\n'
  (cd frontend && npm run build)
fi
printf '\nPASS: %s 自动检查；人工验收与设计确认另行记录。\n' "$SCOPE"
