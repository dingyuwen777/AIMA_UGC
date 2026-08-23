"""平台机器标识在 Contract、数据库与当前有效系统中必须保持唯一。"""

from __future__ import annotations

import re
from pathlib import Path
from uuid import UUID

import pytest
from aima_ugc.adapters.providers.imports.excel_profile import get_excel_import_profile
from aima_ugc.contracts.http import (
    CollectionPlanListQuery,
    CollectionPlanPlatformRequest,
    CollectionRunPlatformRequest,
    ContentFilterSnapshot,
)
from aima_ugc.contracts.platform import (
    PLATFORM_NAMES,
    PLATFORM_SCOPES,
    PlatformName,
    PlatformScope,
    normalize_platform_name,
)
from aima_ugc.modules.collection.tables import (
    collection_plan_platforms_table,
    collection_scopes_table,
)
from aima_ugc.modules.content.tables import accounts_table, contents_table
from aima_ugc.modules.system.tables import keyword_pack_items_table
from aima_ugc.platform.presentation import platform_display_name
from pydantic import TypeAdapter, ValidationError

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EXPECTED = ("xiaohongshu", "douyin", "weibo", "bilibili", "kuaishou")
_INVALID_MACHINE_VALUES = ("xhs", "red", "dy", "wb", "ks", "bili", "all", "twitter")
_FORBIDDEN_EXACT_LITERALS = ("dy", "wb", "ks", "bili")
_FORBIDDEN_LITERAL_PATTERNS = {
    value: re.compile(rf"[\"']{re.escape(value)}[\"']") for value in _FORBIDDEN_EXACT_LITERALS
}
_PLATFORM_CONTEXT_PATTERN = re.compile(
    r"(?:platform(?:s|_scope)?|Platform(?:Name|Scope)?)", re.IGNORECASE
)
_XIAOHONGSHU_ALIAS_PATTERN = re.compile(r"xhs", re.IGNORECASE)
_XIAOHONGSHU_EXTERNAL_LITERALS = ("xhslink.com", "xhslink.cn")
_RED_PLATFORM_ALIAS_PATTERN = re.compile(
    r"(?:platform|platform_scope)\s*(?:=|:)\s*[\"']red[\"']",
    re.IGNORECASE,
)
_SCAN_ROOTS = (
    ".github",
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
_EXCLUDED_FILES = {
    "tests/contracts/test_platform_identifier_consistency.py",
    "tests/integration/database/test_migration_data_lifecycle.py",
}


def _check_sql(table: object, name: str) -> str:
    table_name = getattr(table, "name", None)
    assert isinstance(table_name, str)
    expected_name = f"ck_{table_name}_{name}"
    constraints = [
        str(item.sqltext)
        for item in table.constraints  # type: ignore[attr-defined]
        if getattr(item, "name", None) == expected_name
    ]
    assert len(constraints) == 1
    return constraints[0]


def _is_excluded(relative: str) -> bool:
    return relative in _EXCLUDED_FILES or relative.startswith(_EXCLUDED_PREFIXES)


def _contains_xiaohongshu_machine_alias(line: str) -> bool:
    """外部官方域名可保真；移除域名后仍出现 ``xhs`` 才视为内部别名。"""

    machine_text = line
    for literal in _XIAOHONGSHU_EXTERNAL_LITERALS:
        machine_text = re.sub(re.escape(literal), "", machine_text, flags=re.IGNORECASE)
    return _XIAOHONGSHU_ALIAS_PATTERN.search(machine_text) is not None


def test_platform_name_contract_is_exactly_five_values() -> None:
    assert PLATFORM_NAMES == _EXPECTED
    assert PLATFORM_SCOPES == ("all", *_EXPECTED)

    name_adapter = TypeAdapter(PlatformName)
    scope_adapter = TypeAdapter(PlatformScope)
    for platform in _EXPECTED:
        assert name_adapter.validate_python(platform) == platform
        assert scope_adapter.validate_python(platform) == platform
    assert scope_adapter.validate_python("all") == "all"

    for invalid in _INVALID_MACHINE_VALUES:
        with pytest.raises(ValidationError):
            name_adapter.validate_python(invalid)
    for invalid in ("xhs", "red", "dy", "wb", "ks", "bili", "twitter"):
        with pytest.raises(ValidationError):
            scope_adapter.validate_python(invalid)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("XIAOHONGSHU", "xiaohongshu"),
        ("Douyin", "douyin"),
        ("WEIBO", "weibo"),
        ("BiliBili", "bilibili"),
        (" KUAISHOU ", "kuaishou"),
    ],
)
def test_formal_platform_input_is_case_insensitive(raw: str, expected: PlatformName) -> None:
    assert normalize_platform_name(raw) == expected


def test_platform_abbreviations_remain_invalid_external_inputs() -> None:
    for invalid in ("xhs", "red", "dy", "wb", "ks", "bili"):
        with pytest.raises(ValueError):
            normalize_platform_name(invalid)


def test_http_platform_inputs_normalize_formal_name_case_only() -> None:
    config_id = UUID("00000000-0000-0000-0000-000000000001")

    assert (
        CollectionRunPlatformRequest(
            platform="XIAOHONGSHU",
            provider_config_id=config_id,
        ).platform
        == "xiaohongshu"
    )
    assert (
        CollectionPlanPlatformRequest(
            platform="Douyin",
            provider_config_id=config_id,
        ).platform
        == "douyin"
    )
    assert CollectionPlanListQuery(platform="WEIBO").platform == "weibo"
    assert ContentFilterSnapshot(platforms=("BiliBili", " KUAISHOU ")).platforms == (
        "bilibili",
        "kuaishou",
    )

    for invalid in ("xhs", "red", "dy", "wb", "ks", "bili"):
        with pytest.raises(ValidationError):
            CollectionPlanListQuery(platform=invalid)
        with pytest.raises(ValidationError):
            ContentFilterSnapshot(platforms=(invalid,))


def test_excel_profile_maps_source_labels_only_to_formal_platforms() -> None:
    profile = get_excel_import_profile("aima-monitoring-excel.v1")
    source_labels = {
        "小红书": "xiaohongshu",
        "小红书 APP": "xiaohongshu",
        "xiaohongshu": "xiaohongshu",
        "XIAOHONGSHU": "xiaohongshu",
        "Xiaohongshu": "xiaohongshu",
        "抖音": "douyin",
        "抖音 APP": "douyin",
        "douyin": "douyin",
        "DOUYIN": "douyin",
        "微博": "weibo",
        "新浪微博": "weibo",
        "weibo": "weibo",
        "WEIBO": "weibo",
        "B站": "bilibili",
        "哔哩哔哩": "bilibili",
        "哔哩哔哩APP": "bilibili",
        "bilibili": "bilibili",
        "BILIBILI": "bilibili",
        "快手": "kuaishou",
        "kuaishou": "kuaishou",
        "KUAISHOU": "kuaishou",
    }
    for source, expected in source_labels.items():
        assert profile.resolve_platform(source) == expected
    for invalid in _INVALID_MACHINE_VALUES:
        with pytest.raises(ValueError):
            profile.resolve_platform(invalid)


def test_excel_platform_display_names_are_chinese() -> None:
    assert {platform: platform_display_name(platform) for platform in PLATFORM_NAMES} == {
        "xiaohongshu": "小红书",
        "douyin": "抖音",
        "weibo": "微博",
        "bilibili": "哔哩哔哩",
        "kuaishou": "快手",
    }


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


def test_current_paths_do_not_use_xiaohongshu_abbreviation() -> None:
    violations: list[str] = []
    for root_name in _SCAN_ROOTS:
        root = _REPO_ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            relative = path.relative_to(_REPO_ROOT).as_posix()
            if _is_excluded(relative):
                continue
            if _XIAOHONGSHU_ALIAS_PATTERN.search(relative):
                violations.append(relative)
    assert not violations, (
        "当前有效仓库路径仍包含小红书平台缩写；路径也必须使用 xiaohongshu。\n"
        + "\n".join(violations)
    )


def test_current_machine_facts_do_not_reintroduce_platform_aliases() -> None:
    violations: list[str] = []
    for root_name in _SCAN_ROOTS:
        root = _REPO_ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in _TEXT_SUFFIXES:
                continue
            relative = path.relative_to(_REPO_ROOT).as_posix()
            if _is_excluded(relative):
                continue
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if _contains_xiaohongshu_machine_alias(line):
                    detail = (
                        f"{relative}:{line_number}: "
                        f"forbidden=xiaohongshu abbreviation: {line.strip()}"
                    )
                    violations.append(detail)
                if _PLATFORM_CONTEXT_PATTERN.search(line):
                    for value, pattern in _FORBIDDEN_LITERAL_PATTERNS.items():
                        if pattern.search(line):
                            violations.append(
                                f"{relative}:{line_number}: forbidden={value}: {line.strip()}"
                            )
                if _RED_PLATFORM_ALIAS_PATTERN.search(line):
                    violations.append(
                        f"{relative}:{line_number}: forbidden=red platform alias: {line.strip()}"
                    )
    assert not violations, (
        "当前有效机器事实仍包含平台缩写/别名；平台身份只能使用五个正式值。\n"
        + "\n".join(violations)
    )
