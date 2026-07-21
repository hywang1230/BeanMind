#!/usr/bin/env python3
"""OpenSpec change validation harness for BeanMind.

The harness intentionally executes only commands registered in
``harness/checks.json``. Change manifests may select checks and provide test
paths, but cannot provide arbitrary commands.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Any, Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
ALLOWED_STATUSES = {"PASS", "FAIL", "BLOCKED", "NOT_RUN"}
SHELL_META = re.compile(r"[;&|`$<>\n\r]")
SENSITIVE_TARGETS = {
    "data/ledger/main.beancount",
    "data/beanmind.db",
}


class HarnessError(ValueError):
    """Raised when a harness contract is invalid or unsafe."""


@dataclass(frozen=True)
class PlannedCheck:
    check_id: str
    argv: tuple[str, ...]
    cwd: Path
    timeout_seconds: int


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HarnessError(f"缺少配置文件：{path}") from exc
    except json.JSONDecodeError as exc:
        raise HarnessError(f"JSON 无法解析：{path}: {exc}") from exc
    if not isinstance(value, dict):
        raise HarnessError(f"JSON 顶层必须是对象：{path}")
    return value


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _safe_repo_path(root: Path, value: str, *, must_exist: bool = False) -> Path:
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts or SHELL_META.search(value):
        raise HarnessError(f"路径不安全或越界：{value}")
    resolved = (root / candidate).resolve()
    if not _inside(resolved, root.resolve()):
        raise HarnessError(f"路径越界：{value}")
    if must_exist and not resolved.exists():
        raise HarnessError(f"路径不存在：{value}")
    return resolved


def load_catalog(root: Path = REPO_ROOT) -> dict[str, dict[str, Any]]:
    payload = _load_json(root / "harness" / "checks.json")
    checks = payload.get("checks")
    if payload.get("version") != 1 or not isinstance(checks, dict) or not checks:
        raise HarnessError("checks.json 必须包含 version=1 和非空 checks")
    for check_id, definition in checks.items():
        if not isinstance(check_id, str) or not isinstance(definition, dict):
            raise HarnessError("检查 ID 和定义格式无效")
        argv = definition.get("argv")
        modes = definition.get("modes")
        timeout = definition.get("timeout_seconds")
        if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
            raise HarnessError(f"检查 {check_id} 的 argv 必须是非空字符串数组")
        if any(SHELL_META.search(item) for item in argv):
            raise HarnessError(f"检查 {check_id} 的 argv 含 shell 控制字符")
        for item in argv:
            placeholders = re.findall(r"\{[^{}]+\}", item)
            if any(placeholder != "{change}" for placeholder in placeholders):
                raise HarnessError(f"检查 {check_id} 使用未知占位符")
        if not isinstance(modes, list) or not modes or not set(modes) <= {
            "fast",
            "full",
            "baseline",
        }:
            raise HarnessError(f"检查 {check_id} 的 modes 无效")
        if not isinstance(timeout, int) or timeout <= 0:
            raise HarnessError(f"检查 {check_id} 的 timeout_seconds 无效")
        _safe_repo_path(root, str(definition.get("cwd", ".")), must_exist=True)
        argument_root = definition.get("argument_root")
        if argument_root is not None:
            if not isinstance(argument_root, str):
                raise HarnessError(f"检查 {check_id} 的 argument_root 无效")
            _safe_repo_path(root, argument_root, must_exist=True)
    return checks


def load_policy(root: Path = REPO_ROOT) -> dict[str, dict[str, Any]]:
    payload = _load_json(root / "harness" / "policy.json")
    policies = payload.get("risk_tags")
    if payload.get("version") != 1 or not isinstance(policies, dict) or not policies:
        raise HarnessError("policy.json 必须包含 version=1 和非空 risk_tags")
    catalog = load_catalog(root)
    for tag, policy in policies.items():
        if not isinstance(tag, str) or not isinstance(policy, dict):
            raise HarnessError("风险标签和策略格式无效")
        referenced: list[str] = []
        for group in policy.get("fast_any", []):
            if not isinstance(group, list) or not group:
                raise HarnessError(f"风险策略 {tag} 的 fast_any 无效")
            referenced.extend(group)
        referenced.extend(policy.get("full_all", []))
        unknown = sorted(set(referenced) - set(catalog))
        if unknown:
            raise HarnessError(f"风险策略 {tag} 引用未知检查：{', '.join(unknown)}")
        for field in ("required_scenarios", "required_manual"):
            values = policy.get(field, [])
            if not isinstance(values, list) or not all(isinstance(x, str) for x in values):
                raise HarnessError(f"风险策略 {tag} 的 {field} 无效")
    return policies


def _normalise_check_ref(value: Any) -> tuple[str, list[str]]:
    if isinstance(value, str):
        return value, []
    if not isinstance(value, dict) or set(value) - {"id", "args"}:
        raise HarnessError("检查引用只能是 ID 或包含 id/args 的对象")
    check_id = value.get("id")
    args = value.get("args", [])
    if not isinstance(check_id, str) or not isinstance(args, list) or not all(
        isinstance(arg, str) for arg in args
    ):
        raise HarnessError("检查引用的 id/args 格式无效")
    return check_id, args


def _validate_dynamic_args(
    root: Path, check_id: str, definition: dict[str, Any], args: Sequence[str]
) -> list[str]:
    argument_root = definition.get("argument_root")
    if args and not argument_root:
        raise HarnessError(f"检查 {check_id} 不允许附加参数")
    safe_args: list[str] = []
    cwd = _safe_repo_path(root, str(definition.get("cwd", ".")), must_exist=True)
    allowed_root = _safe_repo_path(root, argument_root, must_exist=True) if argument_root else None
    for arg in args:
        normalised = Path(arg).as_posix().lstrip("./")
        if (
            not arg
            or arg.startswith("-")
            or Path(arg).is_absolute()
            or ".." in Path(arg).parts
            or SHELL_META.search(arg)
            or normalised in SENSITIVE_TARGETS
        ):
            raise HarnessError(f"检查 {check_id} 的参数不安全：{arg}")
        resolved = (cwd / arg).resolve()
        if allowed_root is None or not _inside(resolved, allowed_root):
            raise HarnessError(f"检查 {check_id} 的参数越界：{arg}")
        if not resolved.exists():
            raise HarnessError(f"检查 {check_id} 的测试路径不存在：{arg}")
        safe_args.append(arg)
    return safe_args


def load_manifest(change: str, root: Path = REPO_ROOT) -> tuple[dict[str, Any], Path]:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", change):
        raise HarnessError(f"change 名不合法：{change}")
    path = root / "openspec" / "changes" / change / "verification.json"
    return _load_json(path), path


def _validate_openspec(change: str, root: Path) -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["openspec", "status", "--change", change, "--json"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HarnessError(f"无法读取 OpenSpec change：{exc}") from exc
    if result.returncode != 0:
        raise HarnessError(f"OpenSpec change 不可用：{result.stderr.strip() or result.stdout.strip()}")
    try:
        status = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise HarnessError("OpenSpec status 未返回有效 JSON") from exc
    if status.get("changeName") != change or not status.get("isComplete"):
        raise HarnessError("OpenSpec change 名不一致或 artifacts 尚未完成")
    return status


def build_plan(
    change: str,
    mode: str,
    root: Path = REPO_ROOT,
    *,
    validate_openspec: bool = True,
) -> tuple[list[PlannedCheck], dict[str, Any], Path, list[str]]:
    if mode not in {"fast", "full"}:
        raise HarnessError(f"不支持的模式：{mode}")
    catalog = load_catalog(root)
    policies = load_policy(root)
    manifest, manifest_path = load_manifest(change, root)
    if validate_openspec:
        _validate_openspec(change, root)
    if manifest.get("version") != 1 or manifest.get("change") != change:
        raise HarnessError("verification.json 的 version 或 change 不匹配")
    affected_paths = manifest.get("affected_paths")
    risk_tags = manifest.get("risk_tags")
    checks_by_mode = manifest.get("checks")
    scenario_links = manifest.get("scenario_links")
    manual_items = manifest.get("manual_acceptance")
    if not isinstance(affected_paths, list) or not affected_paths or not all(
        isinstance(x, str) for x in affected_paths
    ):
        raise HarnessError("affected_paths 必须是非空字符串数组")
    for path in affected_paths:
        _safe_repo_path(root, path)
    if not isinstance(risk_tags, list) or not risk_tags or not all(
        isinstance(x, str) for x in risk_tags
    ):
        raise HarnessError("risk_tags 必须是非空字符串数组")
    unknown_tags = sorted(set(risk_tags) - set(policies))
    if unknown_tags:
        raise HarnessError(f"未知风险标签：{', '.join(unknown_tags)}")
    if not isinstance(checks_by_mode, dict) or not all(
        isinstance(checks_by_mode.get(key), list) for key in ("fast", "full")
    ):
        raise HarnessError("checks 必须同时声明 fast 和 full 数组")
    if not isinstance(scenario_links, dict):
        raise HarnessError("scenario_links 必须是对象")
    if not isinstance(manual_items, list):
        raise HarnessError("manual_acceptance 必须是数组")

    manual_by_id: dict[str, dict[str, Any]] = {}
    for item in manual_items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise HarnessError("manual_acceptance 项格式无效")
        if item["id"] in manual_by_id:
            raise HarnessError(f"重复人工验收 ID：{item['id']}")
        if item.get("status", "NOT_RUN") not in ALLOWED_STATUSES:
            raise HarnessError(f"人工验收状态无效：{item['id']}")
        if not isinstance(item.get("required", False), bool):
            raise HarnessError(f"人工验收 required 无效：{item['id']}")
        manual_by_id[item["id"]] = item

    normalised_by_mode: dict[str, list[tuple[str, list[str]]]] = {}
    for check_mode in ("fast", "full"):
        refs = [_normalise_check_ref(value) for value in checks_by_mode[check_mode]]
        ids = [check_id for check_id, _ in refs]
        if len(ids) != len(set(ids)):
            raise HarnessError(f"{check_mode} 包含重复检查 ID")
        for check_id, args in refs:
            if check_id not in catalog:
                raise HarnessError(f"引用未知检查：{check_id}")
            if check_mode not in catalog[check_id]["modes"]:
                raise HarnessError(f"检查 {check_id} 不适用于 {check_mode}")
            _validate_dynamic_args(root, check_id, catalog[check_id], args)
        normalised_by_mode[check_mode] = refs

    fast_ids = {item[0] for item in normalised_by_mode["fast"]}
    full_ids = {item[0] for item in normalised_by_mode["full"]}
    for tag in risk_tags:
        policy = policies[tag]
        for choices in policy.get("fast_any", []):
            if not fast_ids.intersection(choices):
                raise HarnessError(f"风险标签 {tag} 缺少 fast 检查之一：{', '.join(choices)}")
        missing_full = sorted(set(policy.get("full_all", [])) - full_ids)
        if missing_full:
            raise HarnessError(f"风险标签 {tag} 缺少 full 检查：{', '.join(missing_full)}")
        missing_scenarios = sorted(set(policy.get("required_scenarios", [])) - set(scenario_links))
        if missing_scenarios:
            raise HarnessError(f"风险标签 {tag} 缺少场景：{', '.join(missing_scenarios)}")
        missing_manual = sorted(set(policy.get("required_manual", [])) - set(manual_by_id))
        if missing_manual:
            raise HarnessError(f"风险标签 {tag} 缺少人工验收：{', '.join(missing_manual)}")

    known_evidence = set(catalog) | set(manual_by_id)
    for scenario, evidence_ids in scenario_links.items():
        if not isinstance(scenario, str) or not isinstance(evidence_ids, list) or not evidence_ids:
            raise HarnessError("scenario_links 的键和值格式无效")
        unknown_evidence = sorted(set(evidence_ids) - known_evidence)
        if unknown_evidence:
            raise HarnessError(f"场景 {scenario} 引用未知证据：{', '.join(unknown_evidence)}")

    plan: list[PlannedCheck] = []
    for check_id, args in normalised_by_mode[mode]:
        definition = catalog[check_id]
        dynamic_args = _validate_dynamic_args(root, check_id, definition, args)
        argv = tuple(item.replace("{change}", change) for item in definition["argv"])
        plan.append(
            PlannedCheck(
                check_id=check_id,
                argv=argv + tuple(dynamic_args),
                cwd=_safe_repo_path(root, str(definition.get("cwd", ".")), must_exist=True),
                timeout_seconds=definition["timeout_seconds"],
            )
        )

    required_manual = sorted(
        {
            item_id
            for tag in risk_tags
            for item_id in policies[tag].get("required_manual", [])
        }
        | {item_id for item_id, item in manual_by_id.items() if item.get("required")}
    )
    return plan, manifest, manifest_path, required_manual


def redact_output(output: str) -> str:
    redacted = re.sub(
        r"(?i)(authorization\s*:\s*bearer\s+)[^\s]+",
        r"\1[REDACTED]",
        output,
    )
    redacted = re.sub(
        r"(?i)([\"']?(?:api[_-]?key|token|secret|password)[\"']?\s*[:=]\s*[\"']?)[^\s,\"']+",
        r"\1[REDACTED]",
        redacted,
    )
    return redacted


def _run_capture(argv: Sequence[str], cwd: Path, timeout: int) -> tuple[int, str, float]:
    started = monotonic()
    try:
        result = subprocess.run(
            list(argv),
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.returncode, redact_output(result.stdout or ""), monotonic() - started
    except subprocess.TimeoutExpired as exc:
        raw_output = exc.stdout or ""
        if isinstance(raw_output, bytes):
            raw_output = raw_output.decode("utf-8", errors="replace")
        message = f"{raw_output}\n检查超过 {timeout} 秒，已终止。"
        return 124, redact_output(message), monotonic() - started
    except OSError as exc:
        return 127, redact_output(f"无法启动检查：{exc}"), monotonic() - started


def _git_value(root: Path, argv: Sequence[str], fallback: str = "UNKNOWN") -> str:
    try:
        result = subprocess.run(
            list(argv), cwd=root, capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return fallback
    return result.stdout.strip() if result.returncode == 0 else fallback


def _workspace_hash(root: Path) -> str:
    digest = hashlib.sha256()
    try:
        diff = subprocess.run(
            ["git", "diff", "--binary", "HEAD"],
            cwd=root,
            capture_output=True,
            timeout=30,
            check=False,
        )
        digest.update(diff.stdout)
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"],
            cwd=root,
            capture_output=True,
            timeout=30,
            check=False,
        )
        for raw_name in sorted(filter(None, untracked.stdout.split(b"\0"))):
            digest.update(raw_name)
            path = root / raw_name.decode("utf-8", errors="surrogateescape")
            if path.is_file():
                with path.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
    except (OSError, subprocess.TimeoutExpired):
        digest.update(b"UNAVAILABLE")
    return digest.hexdigest()


def _manifest_hash(path: Path | None) -> str:
    if path is None:
        return hashlib.sha256(b"baseline-v1").hexdigest()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _new_run_dir(root: Path, change: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    run_dir = root / ".harness" / "runs" / change / f"{timestamp}-{uuid.uuid4().hex[:8]}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def execute_plan(
    *,
    change: str,
    mode: str,
    plan: Sequence[PlannedCheck],
    root: Path,
    manifest: dict[str, Any] | None,
    manifest_path: Path | None,
    required_manual: Iterable[str] = (),
) -> tuple[dict[str, Any], Path]:
    run_dir = _new_run_dir(root, change)
    started_at = datetime.now(timezone.utc)
    results: list[dict[str, Any]] = []
    for check in plan:
        exit_code, output, duration = _run_capture(
            check.argv, check.cwd, check.timeout_seconds
        )
        status = "PASS" if exit_code == 0 else "FAIL"
        log_path = run_dir / f"{check.check_id}.log"
        log_path.write_text(output, encoding="utf-8")
        results.append(
            {
                "id": check.check_id,
                "status": status,
                "argv": list(check.argv),
                "cwd": check.cwd.relative_to(root).as_posix() or ".",
                "duration_seconds": round(duration, 3),
                "exit_code": exit_code,
                "log": log_path.name,
            }
        )
        print(f"[{status}] {check.check_id} ({duration:.2f}s)")

    uncovered: list[str] = []
    if mode == "full" and manifest is not None:
        manual_by_id = {
            item["id"]: item for item in manifest.get("manual_acceptance", []) if isinstance(item, dict)
        }
        uncovered = [
            item_id
            for item_id in required_manual
            if manual_by_id.get(item_id, {}).get("status") != "PASS"
        ]
    if any(item["status"] == "FAIL" for item in results):
        overall = "FAIL"
    elif uncovered:
        overall = "BLOCKED"
    else:
        overall = "PASS"

    ended_at = datetime.now(timezone.utc)
    report = {
        "schema_version": 1,
        "change": change,
        "mode": mode,
        "status": overall,
        "git_head": _git_value(root, ["git", "rev-parse", "HEAD"]),
        "workspace_sha256": _workspace_hash(root),
        "manifest_sha256": _manifest_hash(manifest_path),
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "duration_seconds": round((ended_at - started_at).total_seconds(), 3),
        "checks": results,
        "uncovered": uncovered,
    }
    report_path = run_dir / "report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"[{overall}] 报告：{report_path.relative_to(root)}")
    return report, report_path


def _baseline_plan(component: str, root: Path) -> list[PlannedCheck]:
    catalog = load_catalog(root)
    load_policy(root)
    ids_by_component = {
        "backend": ["backend-full", "diff-check"],
        "frontend": ["frontend-full", "frontend-build"],
        "all": ["backend-full", "frontend-full", "frontend-build", "diff-check"],
    }
    plan: list[PlannedCheck] = []
    for check_id in ids_by_component[component]:
        definition = catalog[check_id]
        if "baseline" not in definition["modes"]:
            raise HarnessError(f"检查 {check_id} 不适用于 baseline")
        plan.append(
            PlannedCheck(
                check_id=check_id,
                argv=tuple(definition["argv"]),
                cwd=_safe_repo_path(root, str(definition.get("cwd", ".")), must_exist=True),
                timeout_seconds=definition["timeout_seconds"],
            )
        )
    return plan


def latest_report(change: str, root: Path = REPO_ROOT) -> tuple[dict[str, Any], Path]:
    runs_root = root / ".harness" / "runs" / change
    reports = sorted(runs_root.glob("*/report.json"), reverse=True) if runs_root.exists() else []
    if not reports:
        raise HarnessError(f"没有找到 {change} 的运行报告")
    return _load_json(reports[0]), reports[0]


def publish_report(change: str, root: Path = REPO_ROOT) -> Path:
    report, report_path = latest_report(change, root)
    change_dir = root / "openspec" / "changes" / change
    if not change_dir.is_dir():
        raise HarnessError(f"OpenSpec change 不存在：{change}")
    uncovered = report.get("uncovered") or []
    checks = report.get("checks") or []
    lines = [
        "## Harness 验证摘要",
        "",
        f"- 模式：`{report.get('mode', 'UNKNOWN')}`",
        f"- 总状态：`{report.get('status', 'UNKNOWN')}`",
        f"- Git HEAD：`{report.get('git_head', 'UNKNOWN')}`",
        f"- 工作区摘要：`{report.get('workspace_sha256', 'UNKNOWN')}`",
        f"- 验证清单摘要：`{report.get('manifest_sha256', 'UNKNOWN')}`",
        f"- 证据：`{report_path.relative_to(root)}`",
        "",
        "### 自动检查",
        "",
    ]
    for item in checks:
        lines.append(
            f"- `{item.get('id')}`：{item.get('status')}，{item.get('duration_seconds')} 秒"
        )
    lines.extend(["", "### 未覆盖项", ""])
    if uncovered:
        lines.extend(f"- `{item}`" for item in uncovered)
    else:
        lines.append("- 无。")
    lines.extend(
        [
            "",
            "> 该摘要仅记录 harness 证据，不自动修改 tasks、提交代码或归档 change。",
            "",
        ]
    )
    output = change_dir / "verification.md"
    output.write_text("\n".join(lines), encoding="utf-8")
    return output


def _print_plan(plan: Sequence[PlannedCheck], mode: str) -> None:
    print(f"预检通过，模式：{mode}")
    for item in plan:
        print(f"- {item.check_id}: {' '.join(item.argv)}")
    if mode == "fast":
        print("注意：fast PASS 不能替代 full 门禁。")


def _exit_for_status(status: str) -> int:
    return {"PASS": 0, "FAIL": 1, "BLOCKED": 2, "NOT_RUN": 3}.get(status, 1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check", help="校验 change 验证契约")
    check_parser.add_argument("--change", required=True)
    check_parser.add_argument("--mode", choices=("fast", "full"), default="fast")

    run_parser = subparsers.add_parser("run", help="执行 change 检查并生成报告")
    run_parser.add_argument("--change", required=True)
    run_parser.add_argument("--mode", choices=("fast", "full"), required=True)

    report_parser = subparsers.add_parser("report", help="读取或发布最新报告")
    report_parser.add_argument("--change", required=True)
    report_parser.add_argument("--publish", action="store_true")

    baseline_parser = subparsers.add_parser("baseline", help="执行不依赖 OpenSpec 的 CI 基线")
    baseline_parser.add_argument(
        "--component", choices=("backend", "frontend", "all"), default="all"
    )
    return parser


def main(argv: Sequence[str] | None = None, *, root: Path = REPO_ROOT) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "check":
            plan, _, _, _ = build_plan(args.change, args.mode, root)
            _print_plan(plan, args.mode)
            return 0
        if args.command == "run":
            plan, manifest, manifest_path, required_manual = build_plan(
                args.change, args.mode, root
            )
            _print_plan(plan, args.mode)
            report, _ = execute_plan(
                change=args.change,
                mode=args.mode,
                plan=plan,
                root=root,
                manifest=manifest,
                manifest_path=manifest_path,
                required_manual=required_manual,
            )
            return _exit_for_status(report["status"])
        if args.command == "report":
            if args.publish:
                output = publish_report(args.change, root)
                print(f"已发布：{output.relative_to(root)}")
            else:
                report, path = latest_report(args.change, root)
                print(json.dumps(report, ensure_ascii=False, indent=2))
                print(f"报告：{path.relative_to(root)}")
            return 0
        if args.command == "baseline":
            plan = _baseline_plan(args.component, root)
            report, _ = execute_plan(
                change=f"baseline-{args.component}",
                mode="baseline",
                plan=plan,
                root=root,
                manifest=None,
                manifest_path=None,
            )
            return _exit_for_status(report["status"])
    except HarnessError as exc:
        print(f"HARNESS ERROR: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
