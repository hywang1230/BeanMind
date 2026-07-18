import hashlib
import json
from pathlib import Path
import subprocess
import sys


def _fingerprints(directory: Path) -> dict[str, str]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.glob("*.beancount"))
    }


def test_benchmark_script_is_read_only_and_reports_required_phases(ledger_path):
    before = _fingerprints(ledger_path.parent)
    result = subprocess.run(
        [
            sys.executable,
            "scripts/benchmark_ledger_projection.py",
            str(ledger_path),
            "--iterations",
            "2",
        ],
        cwd=Path(__file__).parents[2],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert _fingerprints(ledger_path.parent) == before
    assert payload["input_unchanged"] is True
    assert payload["ledger"]["transactions"] == 6
    assert payload["legacy"]["repository_construct_ms"] >= 0
    assert payload["projection"]["unchanged_startup_ms"] >= 0
    assert payload["projection"]["single_file_refresh_ms"] >= 0
    assert payload["projection"]["database_bytes"] > 0
    assert set(payload["projection"]["queries"]) == {
        "first_page",
        "date_range",
        "transaction_type",
        "keyword",
        "account",
        "tags",
        "combined",
    }
    assert set(payload["projection"]["api_queries"]) == set(payload["projection"]["queries"])
    assert payload["projection"]["api_p95_target_ms"] == 150
    assert payload["projection"]["api_p95_under_target"] is True
    combined = payload["projection"]["query_parameters"]["combined"]
    assert {"start_date", "end_date", "transaction_type", "description", "account", "tags"} <= set(
        combined
    )
    assert payload["projection"]["continuous_paging"]["rows"] == 6
    assert payload["projection"]["consistency"]["consistent"] is True
    assert set(payload["projection"]["core_queries"]) == {
        "dashboard", "budget", "monthly_review_facts"
    }
    assert payload["projection"]["core_p95_target_ms"] == 300
    assert payload["projection"]["core_p95_under_target"] is True
    assert payload["projection"]["aggregation_explain_plan"]
