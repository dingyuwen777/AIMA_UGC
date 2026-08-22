"""平台机器标识在 Contract、数据库与当前代码中必须保持唯一。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import get_args

import pytest

from aima_ugc.adapters.providers.imports.excel_profile import get_excel_import_profile
from aima_ugc.contracts.platform import (
    PLATFORM_NAMES,
    PLATFORM_SCOPES,
    PlatformName,
    PlatformScope,
)
from aima_ugc.modules.collection.tables import (
    collection_plan_platforms_table,
    collection_scopes_table,
)
from aima_ugc.modules.content.tables import accounts_table, contents_table
from aima_ugc.modules.system.tables import keyword_pack_items_table
from pydantic import TypeAdapter, ValidationError

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EXPECTED = ("xiaohongshu", "douyin", "weibo", "bilibili", "kuaishou")
_INVALID_MACHINE_VALUES = (
    "xhs",
    "red",
    "dy",
    "wb",
    "ks",
    "bili",
    "all",
    "twitter",
    "XIAOHONGSHU",
    "DOUYIN",
    "WEIBO",
    "BILIBILI",
    "KUAISHOU",
)
_FORBIDDEN_MACHINE_LITERALS = tuple(
    value for value in _INVALID_MACHINE_VALUES if value not in {"all", "twitter"}
)
_FORBIDDEN_LITERAL_PATTERNS = {
    value: re.compile(rf"[\"']{re.escape(value)}[\"']")
    for value in _FORBIDDEN_MACHINE_LITERALS
}
_ENCODED_LEGACY_PATTERNS = {
    "collection.xhs": re.compile(r"[\"']collection\.xhs\.[^\"']*[\"']"),
}
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
_EXCLUDED_FILES = {"tests/contracts/test_platform_identifier_consistency.py"}


def _check_sql(table: object, name: str) -> str:
    constraints = [
        str(item.sqltext)
        for item in table.constraints  # type: ignore[attr-defined]
        if getattr(item, "name", None) == name
    ]
    assert len(constraints) == 1
    return constraints[0]


def test_platform_name_contract_is_exactly_five_values() -> None:
    assert get_args(PlatformName) == _EXPECTED
    assert PLATFORM_NAMES == _EXPECTED
    assert get_args(PlatformScope) == ("all", *_EXPECTED)
    assert PLATFORM_SCOPES == ("all", *_EXPECTED)

    adapter = TypeAdapter(PlatformName)
    for platform in _EXPECTED:
        assert adapter.validate_python(platform) == platform
    for invalid in _INVALID_MACHINE_VALUES:
        with pytest.raises(ValidationError):
            adapter.validate_python(invalid)


def test_excel_profile_maps_source_labels_only_to_formal_platforms() -> None:
    profile = get_excel_import_profile("aima-monitoring-excel.v1")
    source_labels = {
        "小红书": "xiaohongshu",
        "xiaohongshu": "xiaohongshu",
        "抖音": "douyin",
        "douyin": "douyin",
        "微博": "weibo",
        "新浪微博": "weibo",
        "weibo": "weibo",
        "B站": "bilibili",
        "哔哩哔哩": "bilibili",
        "bilibili": "bilibili",
        "快手": "kuaishou",
        "kuaishou": "kuaishou",
    }
    for source, expected in source_labels.items():
        assert profile.resolve_platform(source) == expected
    for invalid in _INVALID_MACHINE_VALUES:
        with pytest.raises(ValueError):
            profile.resolve_platform(invalid)


def test_database_platform_identity_constraints_use_the_same_five_values() -> None:
    for table in (
        accounts_table,
        contents_table,
        collection_plan_platforms_table,
        collection_scopes_table,
    ):
        sql = _check_sql(table, "platform_allowed")
        for value in _EXPECTED:
            assert f"'{value}'" in sql
        assert "'all'" not in sql

    scope_sql = _check_sql(keyword_pack_items_table, "platform_scope_allowed")
    assert "'all'" in scope_sql
    for value in _EXPECTED:
        assert f"'{value}'" in scope_sql


def test_current_machine_facts_do_not_reintroduce_platform_alias_literals() -> None:
    violations: list[str] = []
    patterns = {**_FORBIDDEN_LITERAL_PATTERNS, **_ENCODED_LEGACY_PATTERNS}
    for root_name in _SCAN_ROOTS:
        root = _REPO_ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in _TEXT_SUFFIXES:
                continue
            relative = path.relative_to(_REPO_ROOT).as_posix()
            if relative in _EXCLUDED_FILES or relative.startswith(_EXCLUDED_PREFIXES):
                continue
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                for value, pattern in patterns.items():
                    if pattern.search(line):
                        violations.append(
                            f"{relative}:{line_number}: forbidden={value}: {line.strip()}"
                        )
    assert not violations, (
        "当前机器事实仍包含平台缩写/别名/大小写变体；平台身份只能使用五个正式值。\n"
        + "\n".join(violations)
    )
