"""The save benchmark owns its isolation before importing any backend module."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.benchmark_transaction_save import distribution


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "benchmark_transaction_save.py"


def test_save_benchmark_nearest_rank():
    result = distribution(list(range(1, 31)))
    assert result == {"runs": 30, "median": 15.5, "p95": 29, "max": 30}


@pytest.mark.parametrize("mode", ["explicit", "mixed", "legacy"])
@pytest.mark.parametrize("plugin_mode", ["none", "auto_accounts"])
def test_save_benchmark_isolated_api_and_full_equivalence(tmp_path, mode, plugin_mode):
    protected = tmp_path / "protected"
    protected.mkdir()
    ledger = protected / "main.beancount"
    database = protected / "database.db"
    ledger.write_text("invalid sentinel ledger: must never be read", encoding="utf-8")
    database.write_bytes(b"invalid sentinel sqlite: must never be opened")
    before = {path.name: path.read_bytes() for path in protected.iterdir()}
    environment = dict(os.environ, DATA_DIR=str(protected), LEDGER_FILE=str(ledger),
                       DATABASE_FILE=str(database), LOG_DIR=str(protected / "logs"),
                       SCHEDULER_ENABLED="true", LLM_ENABLED="true", DEBUG="true")
    report = tmp_path / "result.json"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--sizes", "4", "7", "--iterations", "2",
         "--id-mode", mode, "--plugin-mode", plugin_mode, "--output", str(report)],
        env=environment, cwd=ROOT, capture_output=True, text=True, check=True,
    )
    payload = json.loads(result.stdout)
    assert json.loads(report.read_text()) == payload
    assert {path.name: path.read_bytes() for path in protected.iterdir()} == before
    assert payload["synthetic_only"] is True
    assert payload["p95_method"] == "nearest-rank"
    assert [case["initial_transactions"] for case in payload["cases"]] == [4, 7]
    for case in payload["cases"]:
        assert case["id_mode"] == mode
        assert case["plugin_mode"] == plugin_mode
        assert case["consistency"]["matched"] is True
        assert case["consistency"]["compared_rows"] == {
            "ledger_transactions": case["initial_transactions"],
            "ledger_postings": case["initial_transactions"] * 2,
            "ledger_tags": case["initial_transactions"],
        }
        assert set(case["scenarios"]) == {"create", "edit_beginning", "edit_middle", "edit_end", "delete"}
        for scenario in case["scenarios"].values():
            assert scenario["total_ms"]["runs"] == 2
            assert 0 < scenario["total_ms"]["median"] <= scenario["total_ms"]["p95"]
            assert set(scenario["sql_executions"]) == {"INSERT", "UPDATE", "DELETE", "SELECT"}
            assert scenario["sql_executions"]["SELECT"]["median"] > 0
    assert "Assets:Cash" not in result.stdout
    assert "fixture-" not in result.stdout


@pytest.mark.parametrize("arguments", [["--iterations", "0"], ["--sizes", "-1"]])
def test_save_benchmark_invalid_parameters_fail(arguments):
    result = subprocess.run([sys.executable, str(SCRIPT), *arguments], cwd=ROOT,
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert not result.stdout


def test_save_benchmark_consistency_failure_is_nonzero_and_redacted(tmp_path):
    report = tmp_path / "failed.json"
    program = (
        "import sys; from scripts import benchmark_transaction_save as benchmark; "
        "benchmark.compare_projection = lambda *args: "
        "(_ for _ in ()).throw(RuntimeError('SECRET-FINANCIAL-CONTENT')); "
        f"sys.argv = ['benchmark', '--worker', '--sizes', '2', '--iterations', '1', "
        f"'--output', {str(report)!r}]; "
        "raise SystemExit(benchmark.main())"
    )
    result = subprocess.run([sys.executable, "-c", program], cwd=ROOT,
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert not report.exists()
    assert not result.stdout
    assert "SECRET-FINANCIAL-CONTENT" not in result.stderr
    assert "No report produced" in result.stderr
