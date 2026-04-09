"""生产代码中的 AI 个人术语防回归测试。"""

from pathlib import Path


PRODUCTION_PATHS = [
    Path("backend/infrastructure/intelligence"),
    Path("backend/application/services"),
]

BANNED_TERMS = [
    "经典白",
    "招行",
    "工行",
    "建行",
    "广发",
    "农行",
    "活期存款",
    "白金卡",
]


def test_ai_production_code_does_not_hardcode_personalized_terms():
    """AI 生产代码不应继续硬编码个人账本术语。"""
    violations = []

    for root in PRODUCTION_PATHS:
        for path in root.rglob("*.py"):
            content = path.read_text(encoding="utf-8")
            for term in BANNED_TERMS:
                if term in content:
                    violations.append(f"{path}: {term}")

    assert violations == []
