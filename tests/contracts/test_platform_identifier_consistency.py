"""平台机器标识必须统一使用完整名称。"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LEGACY_PLATFORM = "x" + "hs"
_LEGACY_PATTERN = re.compile(rf"(?<![A-Za-z0-9_]){_LEGACY_PLATFORM}(?![A-Za-z0-9_])")
_SCAN_ROOTS = (
    "backend/src",
    "frontend/src",
    "frontend/tests",
    "frontend/e2e",
    "frontend/e2e-fullstack",
    "contracts",
    "docs",
    "scripts",
    "tests",
)
_TEXT_SUFFIXES = {".py", ".ts", ".vue", ".json", ".md", ".toml", ".yml", ".yaml"}
_EXCLUDED_PREFIXES = (
    "changes/",
    "migrations/versions/",
    "tests/fixtures/providers/tikhub/",
)


def test_current_platform_identifiers_do_not_use_legacy_xhs() -> None:
    """当前机器事实不得重新引入旧小红书缩写；历史证据与 Migration 除外。"""

    violations: list[str] = []
    for root_name in _SCAN_ROOTS:
        root = _REPO_ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in _TEXT_SUFFIXES:
                continue
            relative = path.relative_to(_REPO_ROOT).as_posix()
            if relative == "tests/contracts/test_platform_identifier_consistency.py":
                continue
            if relative.startswith(_EXCLUDED_PREFIXES):
                continue
            text = path.read_text(encoding="utf-8")
            for line_number, line in enumerate(text.splitlines(), start=1):
                if _LEGACY_PATTERN.search(line):
                    violations.append(f"{relative}:{line_number}: {line.strip()}")

    assert not violations, (
        "当前代码/Contract/generated/测试/正式文档仍包含旧平台机器值；"
        "统一使用 xiaohongshu。\n" + "\n".join(violations)
    )
