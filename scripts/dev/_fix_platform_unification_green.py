"""一次性收口五个平台完整名称迁移的机械修改。"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_TEXT_SUFFIXES = {".py", ".ts", ".vue", ".json", ".md", ".toml", ".yml", ".yaml"}
_EXCLUDED_PREFIXES = (
    "changes/archive/",
    "migrations/versions/",
    "tests/fixtures/providers/tikhub/",
)
_EXCLUDED_FILES = {
    "tests/contracts/test_platform_identifier_consistency.py",
    "tests/integration/database/test_migration_data_lifecycle.py",
}
_LEGACY_XIAOHONGSHU = "".join(("x", "h", "s"))


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _excluded(path: Path) -> bool:
    relative = _relative(path)
    return relative in _EXCLUDED_FILES or relative.startswith(_EXCLUDED_PREFIXES)


def _replace_if_present(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old in text:
        target.write_text(text.replace(old, new), encoding="utf-8")


def _replace_platform_aliases_in_active_text() -> None:
    legacy_lower = _LEGACY_XIAOHONGSHU
    legacy_camel = legacy_lower.capitalize()
    legacy_upper = legacy_lower.upper()
    exact_aliases = {
        "dy": "douyin",
        "wb": "weibo",
        "ks": "kuaishou",
        "bili": "bilibili",
    }

    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in _TEXT_SUFFIXES or _excluded(path):
            continue
        text = path.read_text(encoding="utf-8")
        updated = text.replace(legacy_upper, "XIAOHONGSHU")
        updated = updated.replace(legacy_camel, "Xiaohongshu")
        updated = updated.replace(legacy_lower, "xiaohongshu")
        updated = re.sub(
            r"(?<![A-Za-z0-9_])XIAOHONGSHU(?![A-Za-z0-9_])",
            "xiaohongshu",
            updated,
        )
        for alias, formal in exact_aliases.items():
            updated = re.sub(
                rf"([\"']){re.escape(alias)}\1",
                lambda match, replacement=formal: (
                    f"{match.group(1)}{replacement}{match.group(1)}"
                ),
                updated,
            )
        if updated != text:
            path.write_text(updated, encoding="utf-8")


def _rename_active_paths() -> None:
    legacy = _LEGACY_XIAOHONGSHU
    paths = sorted(
        ROOT.rglob("*"),
        key=lambda path: len(path.relative_to(ROOT).parts),
        reverse=True,
    )
    for path in paths:
        if not path.exists() or _excluded(path):
            continue
        name = path.name
        updated_name = re.sub(re.escape(legacy), "xiaohongshu", name, flags=re.IGNORECASE)
        if updated_name == name:
            continue
        target = path.with_name(updated_name)
        if target.exists():
            raise FileExistsError(f"rename target already exists: {target}")
        path.rename(target)


def _fix_semantic_regressions() -> None:
    _replace_if_present(
        "tests/unit/collection/test_scheduled_scope_snapshot.py",
        "item_platform",
        "item_platform_scope",
    )
    _replace_if_present(
        "backend/src/aima_ugc/platform/export/excel.py",
        "from aima_ugc.platform.presentation import platform_display_name\n",
        "",
    )
    _replace_if_present(
        "backend/src/aima_ugc/platform/export/excel.py",
        "platform_display_name(content.platform)",
        "content.platform",
    )
    _replace_if_present(
        "backend/src/aima_ugc/platform/export/excel.py",
        "platform_display_name(comment.platform)",
        "comment.platform",
    )


def main() -> int:
    _fix_semantic_regressions()
    _replace_platform_aliases_in_active_text()
    _rename_active_paths()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
