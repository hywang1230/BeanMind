"""Check maintained engineering Markdown, including local ignored documents.

Uses only the standard library. Historical assets and business designs are not
rewritten or scanned. Links in fenced examples are intentionally ignored.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
FILES = [ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "docs/README.md",
         ROOT / "docs/templates/design.md", *sorted((ROOT / "harness").rglob("*.md"))]
errors = []
for path in FILES:
    if not path.exists():  # AGENTS and docs are intentionally local/ignored.
        if path.name == "AGENTS.md" or ROOT / "docs" in path.parents:
            continue
        errors.append(f"missing: {path.relative_to(ROOT)}")
        continue
    fenced = False
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        location = f"{path.relative_to(ROOT)}:{number}"
        if line.rstrip() != line:
            errors.append(f"{location}: trailing whitespace")
        if line.lstrip().startswith("```"):
            fenced = not fenced
        if fenced:
            continue
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", line):
            if re.match(r"[a-zA-Z][\w+.-]*:|#", target):
                continue
            target_path = target.split("#", 1)[0]
            if target_path and not (path.parent / target_path).exists():
                errors.append(f"{location}: missing link {target}")
if errors:
    print("\n".join(errors), file=sys.stderr)
    raise SystemExit(1)
print("Engineering Markdown: links and whitespace OK")
