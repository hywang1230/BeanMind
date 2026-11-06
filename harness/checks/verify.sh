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
if [[ "$SCOPE" != docs ]]; then
  [[ -s harness/checks/local-tests.sh ]] \
    || blocked '缺少 harness/checks/local-tests.sh；先配置并验证本地测试适配'
  bash harness/checks/local-tests.sh --preflight "$SCOPE"
fi
printf '\n== Static checks ==\n'
for script in scripts/verify harness/checks/*.sh run_tests.sh; do
  [[ -f "$script" ]] || continue
  bash -n "$script"
done
git diff --check
git diff --cached --check
if [[ -f harness/checks/check-local-rules.sh ]]; then
  bash harness/checks/check-local-rules.sh
fi
python3 harness/checks/check_docs.py
if [[ "$SCOPE" != docs ]]; then
  bash harness/checks/local-tests.sh "$SCOPE"
fi
printf '\nPASS: %s 自动检查；人工验收与设计确认另行记录。\n' "$SCOPE"
