from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import change_harness as harness


CHANGE = "sample-change"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _base_manifest() -> dict[str, object]:
    return {
        "version": 1,
        "change": CHANGE,
        "affected_paths": ["scripts/change_harness.py", "tests/harness/"],
        "risk_tags": ["backend"],
        "checks": {
            "fast": [
                "openspec-change-strict",
                {"id": "backend-targeted", "args": ["tests/harness/test_sample.py"]},
                "diff-check",
            ],
            "full": ["openspec-change-strict", "backend-full", "diff-check"],
        },
        "scenario_links": {"manifest-validation": ["backend-targeted"]},
        "manual_acceptance": [],
    }


@pytest.fixture()
def harness_root(tmp_path: Path) -> Path:
    project_root = Path(__file__).resolve().parents[2]
    (tmp_path / "harness").mkdir()
    (tmp_path / "tests" / "harness").mkdir(parents=True)
    (tmp_path / "frontend" / "src").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "tests" / "harness" / "test_sample.py").write_text(
        "def test_sample():\n    assert True\n", encoding="utf-8"
    )
    (tmp_path / "scripts" / "change_harness.py").write_text("# fixture\n", encoding="utf-8")
    (tmp_path / "frontend" / "src" / "sample.test.ts").write_text("// fixture\n", encoding="utf-8")
    for name in ("checks.json", "policy.json"):
        (tmp_path / "harness" / name).write_text(
            (project_root / "harness" / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    _write_json(
        tmp_path / "openspec" / "changes" / CHANGE / "verification.json", _base_manifest()
    )
    (tmp_path / "openspec" / "changes" / CHANGE / "tasks.md").write_text(
        "- [ ] do not edit\n", encoding="utf-8"
    )
    return tmp_path


def _manifest_path(root: Path) -> Path:
    return root / "openspec" / "changes" / CHANGE / "verification.json"


def _mutate_manifest(root: Path, mutator) -> None:
    path = _manifest_path(root)
    value = json.loads(path.read_text(encoding="utf-8"))
    mutator(value)
    _write_json(path, value)


def test_catalog_and_policy_are_structurally_safe() -> None:
    root = Path(__file__).resolve().parents[2]
    catalog = harness.load_catalog(root)
    policies = harness.load_policy(root)

    assert {
        "openspec-change-strict",
        "backend-targeted",
        "backend-full",
        "frontend-targeted",
        "frontend-full",
        "frontend-build",
        "pwa-verify",
        "diff-check",
    } <= set(catalog)
    assert {
        "backend",
        "frontend",
        "pwa",
        "ledger-write",
        "projection",
        "migration",
        "performance",
        "llm",
    } == set(policies)
    for definition in catalog.values():
        cwd = (root / definition["cwd"]).resolve()
        cwd.relative_to(root.resolve())
        assert isinstance(definition["argv"], list)


def test_valid_manifest_builds_deterministic_fast_plan(harness_root: Path) -> None:
    plan, manifest, path, required_manual = harness.build_plan(
        CHANGE, "fast", harness_root, validate_openspec=False
    )

    assert [item.check_id for item in plan] == [
        "openspec-change-strict",
        "backend-targeted",
        "diff-check",
    ]
    assert plan[1].argv[-1] == "tests/harness/test_sample.py"
    assert manifest["change"] == CHANGE
    assert path == _manifest_path(harness_root)
    assert required_manual == []


def test_unknown_risk_tag_is_rejected(harness_root: Path) -> None:
    _mutate_manifest(harness_root, lambda value: value.update(risk_tags=["unknown"]))

    with pytest.raises(harness.HarnessError, match="未知风险标签"):
        harness.build_plan(CHANGE, "fast", harness_root, validate_openspec=False)


def test_missing_required_check_is_rejected(harness_root: Path) -> None:
    def mutate(value: dict[str, object]) -> None:
        value["checks"]["full"] = ["openspec-change-strict", "diff-check"]

    _mutate_manifest(harness_root, mutate)

    with pytest.raises(harness.HarnessError, match="缺少 full 检查"):
        harness.build_plan(CHANGE, "fast", harness_root, validate_openspec=False)


def test_projection_risk_requires_consistency_dirty_and_recovery_scenarios(
    harness_root: Path,
) -> None:
    def mutate(value: dict[str, object]) -> None:
        value["risk_tags"] = ["projection"]

    _mutate_manifest(harness_root, mutate)

    with pytest.raises(harness.HarnessError, match="projection-consistency"):
        harness.build_plan(CHANGE, "fast", harness_root, validate_openspec=False)


@pytest.mark.parametrize(
    "unsafe_path",
    ["../outside.py", "/tmp/outside.py", "tests/harness/test_sample.py;whoami"],
)
def test_targeted_test_path_cannot_escape_repository(
    harness_root: Path, unsafe_path: str
) -> None:
    def mutate(value: dict[str, object]) -> None:
        value["checks"]["fast"][1]["args"] = [unsafe_path]

    _mutate_manifest(harness_root, mutate)

    with pytest.raises(harness.HarnessError, match="不安全|越界"):
        harness.build_plan(CHANGE, "fast", harness_root, validate_openspec=False)


def test_default_real_data_target_is_rejected(harness_root: Path) -> None:
    target = harness_root / "data" / "beanmind.db"
    target.parent.mkdir()
    target.write_text("never read", encoding="utf-8")
    definition = {
        "cwd": ".",
        "argument_root": ".",
    }

    with pytest.raises(harness.HarnessError, match="不安全"):
        harness._validate_dynamic_args(
            harness_root, "backend-targeted", definition, ["data/beanmind.db"]
        )


def test_runner_continues_after_failure_and_records_current_results(harness_root: Path) -> None:
    plan = [
        harness.PlannedCheck(
            "fails",
            (sys.executable, "-c", "raise SystemExit(7)"),
            harness_root,
            5,
        ),
        harness.PlannedCheck(
            "passes", (sys.executable, "-c", "print('ok')"), harness_root, 5
        ),
    ]

    report, report_path = harness.execute_plan(
        change=CHANGE,
        mode="fast",
        plan=plan,
        root=harness_root,
        manifest=_base_manifest(),
        manifest_path=_manifest_path(harness_root),
    )

    assert report["status"] == "FAIL"
    assert [item["status"] for item in report["checks"]] == ["FAIL", "PASS"]
    assert report_path.exists()
    assert harness._exit_for_status(report["status"]) == 1


def test_timeout_is_failed_and_redacted_log_is_persisted(harness_root: Path) -> None:
    plan = [
        harness.PlannedCheck(
            "timeout",
            (
                sys.executable,
                "-c",
                "import time; print('api_key=topsecret', flush=True); time.sleep(2)",
            ),
            harness_root,
            1,
        )
    ]

    report, report_path = harness.execute_plan(
        change=CHANGE,
        mode="fast",
        plan=plan,
        root=harness_root,
        manifest=_base_manifest(),
        manifest_path=_manifest_path(harness_root),
    )

    assert report["status"] == "FAIL"
    assert report["checks"][0]["exit_code"] == 124
    log = (report_path.parent / "timeout.log").read_text(encoding="utf-8")
    assert "topsecret" not in log
    assert "[REDACTED]" in log


def test_fast_pass_is_not_described_as_full_gate(harness_root: Path, capsys) -> None:
    plan, _, _, _ = harness.build_plan(
        CHANGE, "fast", harness_root, validate_openspec=False
    )
    harness._print_plan(plan, "fast")

    assert "不能替代 full" in capsys.readouterr().out


def test_required_manual_item_blocks_full_and_rerun_does_not_overwrite(
    harness_root: Path,
) -> None:
    manifest = _base_manifest()
    manifest["manual_acceptance"] = [
        {"id": "approval", "required": True, "status": "NOT_RUN"}
    ]
    _write_json(_manifest_path(harness_root), manifest)

    first, first_path = harness.execute_plan(
        change=CHANGE,
        mode="full",
        plan=[],
        root=harness_root,
        manifest=manifest,
        manifest_path=_manifest_path(harness_root),
        required_manual=["approval"],
    )
    second, second_path = harness.execute_plan(
        change=CHANGE,
        mode="full",
        plan=[],
        root=harness_root,
        manifest=manifest,
        manifest_path=_manifest_path(harness_root),
        required_manual=["approval"],
    )

    assert first["status"] == second["status"] == "BLOCKED"
    assert harness._exit_for_status("BLOCKED") == 2
    assert first_path != second_path
    assert first_path.exists() and second_path.exists()


def test_publish_only_writes_verification_summary(harness_root: Path) -> None:
    tasks_path = harness_root / "openspec" / "changes" / CHANGE / "tasks.md"
    business_path = harness_root / "scripts" / "change_harness.py"
    tasks_before = tasks_path.read_bytes()
    business_before = business_path.read_bytes()
    harness.execute_plan(
        change=CHANGE,
        mode="fast",
        plan=[],
        root=harness_root,
        manifest=_base_manifest(),
        manifest_path=_manifest_path(harness_root),
    )

    output = harness.publish_report(CHANGE, harness_root)

    assert output.name == "verification.md"
    assert "Harness 验证摘要" in output.read_text(encoding="utf-8")
    assert tasks_path.read_bytes() == tasks_before
    assert business_path.read_bytes() == business_before
    assert not list((harness_root / "openspec" / "changes").glob("archive/*"))


def test_baseline_plan_does_not_require_openspec(harness_root: Path) -> None:
    openspec_dir = harness_root / "openspec"
    for path in sorted(openspec_dir.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
        else:
            path.rmdir()
    openspec_dir.rmdir()

    backend = harness._baseline_plan("backend", harness_root)
    frontend = harness._baseline_plan("frontend", harness_root)

    assert [item.check_id for item in backend] == ["backend-full", "diff-check"]
    assert [item.check_id for item in frontend] == ["frontend-full", "frontend-build"]


def test_harness_reports_are_ignored_but_sources_are_not() -> None:
    root = Path(__file__).resolve().parents[2]
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", ".harness/runs/example/report.json"], cwd=root
    )
    catalog = subprocess.run(["git", "check-ignore", "-q", "harness/checks.json"], cwd=root)
    script = subprocess.run(
        ["git", "check-ignore", "-q", "scripts/change_harness.py"], cwd=root
    )

    assert ignored.returncode == 0
    assert catalog.returncode == 1
    assert script.returncode == 1


def test_redaction_handles_authorization_and_json_secrets() -> None:
    output = 'Authorization: Bearer abc123\n{"api_key": "secret-value"}\ntoken=xyz\n'

    redacted = harness.redact_output(output)

    assert "abc123" not in redacted
    assert "secret-value" not in redacted
    assert "xyz" not in redacted
    assert redacted.count("[REDACTED]") == 3
