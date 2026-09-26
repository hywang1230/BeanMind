"""Shell orchestration regressions; native tools are stubbed in a temporary repo."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


def executable(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('#!/usr/bin/env bash\nset -eu\n' + body, encoding='utf-8')
    path.chmod(0o755)


@pytest.fixture
def shell_repo(tmp_path: Path):
    root = tmp_path / 'repository with spaces'
    for name in ('scripts/verify', 'harness/checks/verify.sh',
                 'harness/checks/check_docs.py', 'run_tests.sh'):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    (root / 'README.md').write_text('# Fixture\n')
    executable(root / '.venv/bin/python', 'exit 0\n')
    for tool in ('vitest', 'vite', 'vue-tsc'):
        executable(root / 'frontend/node_modules/.bin' / tool, 'exit 0\n')
    bins = tmp_path / 'bin'
    executable(bins / 'git', 'exit 0\n')
    executable(bins / 'node', 'exit "${NODE_EXIT:-0}"\n')
    executable(bins / 'uv', '''
[[ "$*" == 'run --frozen --no-sync --offline pytest -q' ]]
[[ "$LEDGER_FILE" == "$DATA_DIR/ledger/main.beancount" ]]
[[ "$DATABASE_FILE" == "$DATA_DIR/beanmind.db" ]]
[[ "$SCHEDULER_ENABLED" == false && "$LLM_ENABLED" == false && -z "$LLM_API_KEY" ]]
printf 'uv\n' >> "$CALL_LOG"
printf '%s' "$DATA_DIR" > "$DATA_LOG"
exit "${UV_EXIT:-0}"
''')
    executable(bins / 'npm', '''
printf 'npm %s\n' "$*" >> "$CALL_LOG"
exit "${NPM_EXIT:-0}"
''')
    env = dict(os.environ, PATH=f'{bins}:{os.environ["PATH"]}',
               CALL_LOG=str(tmp_path / 'calls'), DATA_LOG=str(tmp_path / 'data'),
               DATA_DIR='/never-use-real-data', LLM_ENABLED='true', LLM_API_KEY='test-key')
    return root, env


def run(shell_repo, *args, **overrides):
    root, env = shell_repo
    return subprocess.run(['bash', str(root / 'scripts/verify'), *args],
                          cwd=root.parent, env=dict(env, **overrides),
                          capture_output=True, text=True)


def calls(shell_repo):
    path = Path(shell_repo[1]['CALL_LOG'])
    return path.read_text().splitlines() if path.exists() else []


def test_success_order_and_temporary_data_cleanup(shell_repo):
    result = run(shell_repo)
    assert result.returncode == 0, result.stderr
    assert calls(shell_repo) == ['uv', 'npm run test:run', 'npm run build']
    data = Path(Path(shell_repo[1]['DATA_LOG']).read_text())
    assert not data.parent.exists()


@pytest.mark.parametrize('tool,code,expected', [
    ('UV_EXIT', '7', ['uv']),
    ('NPM_EXIT', '9', ['uv', 'npm run test:run']),
])
def test_native_failure_is_preserved_and_stops_next_step(shell_repo, tool, code, expected):
    result = run(shell_repo, **{tool: code})
    assert result.returncode == int(code)
    assert calls(shell_repo) == expected
    assert 'PASS:' not in result.stdout
    data = Path(Path(shell_repo[1]['DATA_LOG']).read_text())
    assert not data.parent.exists()


def test_missing_frontend_dependency_blocks_before_backend_test(shell_repo):
    (shell_repo[0] / 'frontend/node_modules/.bin/vite').unlink()
    result = run(shell_repo)
    assert result.returncode == 2
    assert 'BLOCKED' in result.stderr
    assert calls(shell_repo) == []


def test_unsupported_node_blocks_before_tests(shell_repo):
    result = run(shell_repo, NODE_EXIT='1')
    assert result.returncode == 2
    assert calls(shell_repo) == []


@pytest.mark.parametrize('args', [('unknown',), ('all', 'extra')])
def test_unknown_arguments_rejected_without_running_tools(shell_repo, args):
    assert run(shell_repo, *args).returncode == 2
    assert calls(shell_repo) == []


def test_docs_does_not_require_component_dependencies(shell_repo):
    shutil.rmtree(shell_repo[0] / '.venv')
    shutil.rmtree(shell_repo[0] / 'frontend')
    result = run(shell_repo, 'docs')
    assert result.returncode == 0, result.stderr
    assert calls(shell_repo) == []


def test_legacy_test_entry_propagates_failure(shell_repo):
    root, env = shell_repo
    result = subprocess.run(['bash', str(root / 'run_tests.sh')], cwd=root.parent,
                            env=dict(env, UV_EXIT='7'), capture_output=True, text=True)
    assert result.returncode == 7
    assert calls(shell_repo) == ['uv']


def test_docs_rejects_syntax_error_in_legacy_entry(shell_repo):
    (shell_repo[0] / 'run_tests.sh').write_text('if then\n')
    result = run(shell_repo, 'docs')
    assert result.returncode != 0
    assert 'PASS:' not in result.stdout
    assert calls(shell_repo) == []
