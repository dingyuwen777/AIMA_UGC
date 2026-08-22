"""一次性收口平台强类型边界；最终合并前删除。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _replace(path: str, old: str, new: str, *, expected: int = 1) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    actual = text.count(old)
    if actual != expected:
        raise RuntimeError(f"{path}: expected {expected} matches, got {actual}: {old!r}")
    target.write_text(text.replace(old, new), encoding="utf-8")


def main() -> int:
    _replace(
        "backend/src/aima_ugc/modules/collection/scheduled_scopes.py",
        "from aima_ugc.contracts.platform import PlatformName, PlatformScope",
        "from aima_ugc.contracts.platform import PlatformName, PlatformScope, require_platform_name",
    )
    _replace(
        "backend/src/aima_ugc/modules/collection/scheduled_scopes.py",
        "    normalized_platforms = tuple(\n"
        "        platform.strip() for platform in plan_platforms if platform.strip()\n"
        "    )",
        "    normalized_platforms = tuple(plan_platforms)",
    )
    _replace(
        "backend/src/aima_ugc/modules/collection/scheduled_scopes.py",
        "        if entry.item_platform_scope == \"all\":\n"
        "            target_platforms = normalized_platforms\n"
        "        elif entry.item_platform_scope in platform_set:\n"
        "            target_platforms = (entry.item_platform_scope,)\n"
        "        else:\n"
        "            target_platforms = ()",
        "        if entry.item_platform_scope == \"all\":\n"
        "            target_platforms = normalized_platforms\n"
        "        else:\n"
        "            scoped_platform = require_platform_name(entry.item_platform_scope)\n"
        "            target_platforms = (scoped_platform,) if scoped_platform in platform_set else ()",
    )

    _replace(
        "backend/src/aima_ugc/contracts/provider/models.py",
        "from pydantic import AwareDatetime, Field, model_validator\n",
        "from pydantic import AwareDatetime, Field, model_validator\n\n"
        "from aima_ugc.contracts.platform import require_platform_name\n",
    )
    _replace(
        "backend/src/aima_ugc/contracts/provider/models.py",
        "            platform=platform,",
        "            platform=require_platform_name(platform),",
        expected=2,
    )

    _replace(
        "backend/src/aima_ugc/platform/logging/setup.py",
        "gzip.open(destination, \"weibo\")",
        "gzip.open(destination, \"wb\")",
    )

    for path in (
        "backend/src/aima_ugc/adapters/persistence/postgres/collection.py",
        "backend/src/aima_ugc/adapters/persistence/postgres/collection_planning.py",
        "backend/src/aima_ugc/adapters/persistence/postgres/xiaohongshu_replay.py",
        "backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py",
        "backend/src/aima_ugc/adapters/persistence/postgres/reporting.py",
        "backend/src/aima_ugc/adapters/persistence/postgres/analysis.py",
    ):
        _replace(
            path,
            "from sqlalchemy.orm import Session\n",
            "from sqlalchemy.orm import Session\n\n"
            "from aima_ugc.contracts.platform import require_platform_name\n",
        )

    _replace(
        "backend/src/aima_ugc/adapters/persistence/postgres/collection.py",
        '        platform=cast(str, row["platform"]),',
        '        platform=require_platform_name(cast(str, row["platform"])),',
    )
    _replace(
        "backend/src/aima_ugc/adapters/persistence/postgres/collection_planning.py",
        '        platform=cast(str, row["platform"]),',
        '        platform=require_platform_name(cast(str, row["platform"])),',
    )
    _replace(
        "backend/src/aima_ugc/adapters/persistence/postgres/xiaohongshu_replay.py",
        '                platform=cast(str, row["platform"]),',
        '                platform=require_platform_name(cast(str, row["platform"])),',
    )
    _replace(
        "backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py",
        '                    platform=cast(str, row["platform"]),',
        '                    platform=require_platform_name(cast(str, row["platform"])),',
    )
    _replace(
        "backend/src/aima_ugc/adapters/persistence/postgres/reporting.py",
        '                    platform=cast(str, row["platform"]),',
        '                    platform=require_platform_name(cast(str, row["platform"])),',
    )
    _replace(
        "backend/src/aima_ugc/adapters/persistence/postgres/reporting.py",
        '        platform=cast(str, row["platform"]),',
        '        platform=require_platform_name(cast(str, row["platform"])),',
    )
    _replace(
        "backend/src/aima_ugc/adapters/persistence/postgres/analysis.py",
        '        platform=cast(str, row["platform"]),',
        '        platform=require_platform_name(cast(str, row["platform"])),',
    )

    _replace(
        "backend/src/aima_ugc/adapters/persistence/postgres/collection_targets.py",
        "from sqlalchemy.orm import Session\n",
        "from sqlalchemy.orm import Session\n\n"
        "from aima_ugc.contracts.platform import PlatformName, require_platform_name\n",
    )
    _replace(
        "backend/src/aima_ugc/adapters/persistence/postgres/collection_targets.py",
        "    platform: str\n",
        "    platform: PlatformName\n",
    )
    _replace(
        "backend/src/aima_ugc/adapters/persistence/postgres/collection_targets.py",
        "        platforms: tuple[str, ...],",
        "        platforms: tuple[PlatformName, ...],",
    )
    _replace(
        "backend/src/aima_ugc/adapters/persistence/postgres/collection_targets.py",
        '        platform=cast(str, row["platform"]),',
        '        platform=require_platform_name(cast(str, row["platform"])),',
    )

    _replace(
        "backend/src/aima_ugc/bootstrap/collection_strategy_http.py",
        "    CollectionPlatform,\n",
        "",
    )
    _replace(
        "backend/src/aima_ugc/bootstrap/collection_strategy_http.py",
        "                platform=cast(CollectionPlatform, item.platform),",
        "                platform=item.platform,",
    )

    _replace(
        "backend/src/aima_ugc/platform/reporting/excel_report.py",
        "from openpyxl import load_workbook\n\nfrom aima_ugc.platform.presentation import platform_display_name",
        "from openpyxl import load_workbook\n\n"
        "from aima_ugc.contracts.platform import normalize_platform_name\n"
        "from aima_ugc.platform.presentation import platform_display_name",
    )
    _replace(
        "backend/src/aima_ugc/platform/reporting/excel_report.py",
        "_NEGATIVE_CHART_LIMIT = 8\n",
        "_NEGATIVE_CHART_LIMIT = 8\n\n\n"
        "def _report_platform_label(value: str) -> str:\n"
        "    \"\"\"兼容正式机器值大小写和已导出的中文展示文案。\"\"\"\n"
        "    try:\n"
        "        return platform_display_name(normalize_platform_name(value))\n"
        "    except ValueError:\n"
        "        return value\n",
    )
    _replace(
        "backend/src/aima_ugc/platform/reporting/excel_report.py",
        "platform = platform_display_name(platform)",
        "platform = _report_platform_label(platform)",
        expected=2,
    )
    _replace(
        "backend/src/aima_ugc/platform/reporting/excel_report.py",
        'platform = "（未填写）" if platform is None else platform_display_name(platform)',
        'platform = "（未填写）" if platform is None else _report_platform_label(platform)',
    )

    _replace(
        "backend/src/aima_ugc/contracts/http.py",
        "from aima_ugc.contracts.platform import PlatformName, PlatformScope",
        "from aima_ugc.contracts.platform import PlatformName, PlatformScope, normalize_platform_name",
    )
    _replace(
        "backend/src/aima_ugc/contracts/http.py",
        "type CollectionPlatform = PlatformName\n",
        "type CollectionPlatform = PlatformName\n\n\n"
        "def _normalize_platform_input(value: object) -> object:\n"
        "    if isinstance(value, str):\n"
        "        return normalize_platform_name(value)\n"
        "    return value\n\n\n"
        "def _normalize_platform_inputs(value: object) -> object:\n"
        "    if isinstance(value, (list, tuple)):\n"
        "        return tuple(_normalize_platform_input(item) for item in value)\n"
        "    return value\n",
    )
    _replace(
        "backend/src/aima_ugc/contracts/http.py",
        "    platform: CollectionPlatform\n    provider_config_id: UUID\n\n\nclass CollectionRunCreateRequest",
        "    platform: CollectionPlatform\n    provider_config_id: UUID\n\n"
        "    @field_validator(\"platform\", mode=\"before\")\n"
        "    @classmethod\n"
        "    def normalize_platform(cls, value: object) -> object:\n"
        "        return _normalize_platform_input(value)\n\n\nclass CollectionRunCreateRequest",
    )
    _replace(
        "backend/src/aima_ugc/contracts/http.py",
        "    platform: CollectionPlatform\n    provider_config_id: UUID\n\n\nclass CollectionPlanCreateRequest",
        "    platform: CollectionPlatform\n    provider_config_id: UUID\n\n"
        "    @field_validator(\"platform\", mode=\"before\")\n"
        "    @classmethod\n"
        "    def normalize_platform(cls, value: object) -> object:\n"
        "        return _normalize_platform_input(value)\n\n\nclass CollectionPlanCreateRequest",
    )
    _replace(
        "backend/src/aima_ugc/contracts/http.py",
        "    platform: CollectionPlatform | None = None\n    offset: int = Field(default=0, ge=0)",
        "    platform: CollectionPlatform | None = None\n    offset: int = Field(default=0, ge=0)\n\n"
        "    @field_validator(\"platform\", mode=\"before\")\n"
        "    @classmethod\n"
        "    def normalize_platform(cls, value: object) -> object:\n"
        "        return _normalize_platform_input(value)",
    )
    _replace(
        "backend/src/aima_ugc/contracts/http.py",
        "    source_identifier: UUID | None = None\n\n    @field_validator(\"published_from\", \"published_to\")",
        "    source_identifier: UUID | None = None\n\n"
        "    @field_validator(\"platforms\", mode=\"before\")\n"
        "    @classmethod\n"
        "    def normalize_platforms(cls, value: object) -> object:\n"
        "        return _normalize_platform_inputs(value)\n\n"
        "    @field_validator(\"published_from\", \"published_to\")",
    )

    _replace(
        "tests/contracts/test_platform_identifier_consistency.py",
        "    PlatformScope,\n)",
        "    PlatformScope,\n    normalize_platform_name,\n)",
    )
    _replace(
        "tests/contracts/test_platform_identifier_consistency.py",
        "_FORBIDDEN_LITERAL_PATTERNS = {\n"
        "    value: re.compile(rf\"[\\\"']{re.escape(value)}[\\\"']\") for value in _FORBIDDEN_EXACT_LITERALS\n"
        "}\n",
        "_FORBIDDEN_LITERAL_PATTERNS = {\n"
        "    value: re.compile(rf\"[\\\"']{re.escape(value)}[\\\"']\") for value in _FORBIDDEN_EXACT_LITERALS\n"
        "}\n"
        "_PLATFORM_CONTEXT_PATTERN = re.compile(\n"
        "    r\"(?:platform(?:s|_scope)?|Platform(?:Name|Scope)?)\", re.IGNORECASE\n"
        ")\n",
    )
    _replace(
        "tests/contracts/test_platform_identifier_consistency.py",
        "    for invalid in _INVALID_MACHINE_VALUES:\n"
        "        with pytest.raises(ValidationError):\n"
        "            adapter.validate_python(invalid)\n\n\ndef test_excel_profile_maps_source_labels_only_to_formal_platforms",
        "    for invalid in _INVALID_MACHINE_VALUES:\n"
        "        with pytest.raises(ValidationError):\n"
        "            adapter.validate_python(invalid)\n\n\n"
        "@pytest.mark.parametrize(\n"
        "    (\"raw\", \"expected\"),\n"
        "    [\n"
        "        (\"XIAOHONGSHU\", \"xiaohongshu\"),\n"
        "        (\"Douyin\", \"douyin\"),\n"
        "        (\"WEIBO\", \"weibo\"),\n"
        "        (\"BiliBili\", \"bilibili\"),\n"
        "        (\" KUAISHOU \", \"kuaishou\"),\n"
        "    ],\n"
        ")\n"
        "def test_formal_platform_input_is_case_insensitive(raw: str, expected: PlatformName) -> None:\n"
        "    assert normalize_platform_name(raw) == expected\n\n\n"
        "def test_platform_abbreviations_remain_invalid_external_inputs() -> None:\n"
        "    for invalid in (\"xhs\", \"red\", \"dy\", \"wb\", \"ks\", \"bili\"):\n"
        "        with pytest.raises(ValueError):\n"
        "            normalize_platform_name(invalid)\n\n\n"
        "def test_excel_profile_maps_source_labels_only_to_formal_platforms",
    )
    _replace(
        "tests/contracts/test_platform_identifier_consistency.py",
        "                for value, pattern in _FORBIDDEN_LITERAL_PATTERNS.items():\n"
        "                    if pattern.search(line):\n"
        "                        violations.append(\n"
        "                            f\"{relative}:{line_number}: forbidden={value}: {line.strip()}\"\n"
        "                        )",
        "                if _PLATFORM_CONTEXT_PATTERN.search(line):\n"
        "                    for value, pattern in _FORBIDDEN_LITERAL_PATTERNS.items():\n"
        "                        if pattern.search(line):\n"
        "                            violations.append(\n"
        "                                f\"{relative}:{line_number}: forbidden={value}: {line.strip()}\"\n"
        "                            )",
    )

    _replace(
        "tests/unit/platform/test_platform_presentation.py",
        "import pytest\nfrom aima_ugc.platform.presentation import platform_display_name\n",
        "import pytest\nfrom aima_ugc.contracts.platform import PlatformName\nfrom aima_ugc.platform.presentation import platform_display_name\n",
    )
    _replace(
        "tests/unit/platform/test_platform_presentation.py",
        "        (\"kuaishou\", \"快手\"),\n"
        "        (\"B站\", \"哔哩哔哩\"),\n"
        "        (\"抖音\", \"抖音\"),\n"
        "        (\"future_platform\", \"future_platform\"),",
        "        (\"kuaishou\", \"快手\"),",
    )
    _replace(
        "tests/unit/platform/test_platform_presentation.py",
        "    platform: str,",
        "    platform: PlatformName,",
    )
    _replace(
        "tests/unit/platform/test_platform_presentation.py",
        "def test_platform_display_name_translates_known_values_and_preserves_unknown(",
        "def test_platform_display_name_translates_formal_machine_values(",
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
