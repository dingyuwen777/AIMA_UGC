"""一次性维护脚本：把当前运行时平台机器标识统一为五个平台完整名称。

该脚本只在 feature branch 的临时维护 Workflow 中运行，完成后与 Workflow 一起删除。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
XHS_TOKEN = re.compile(r"(?<![A-Za-z0-9_-])xhs(?![A-Za-z0-9_-])")
TEXT_SUFFIXES = {".py", ".ts", ".vue", ".json", ".md", ".toml", ".yml", ".yaml"}
SCAN_ROOTS = (
    "backend/src",
    "frontend/src",
    "frontend/tests",
    "frontend/e2e",
    "frontend/e2e-fullstack",
    "tests",
    "scripts/dev",
    "docs",
)
EXCLUDED_PREFIXES = (
    "tests/fixtures/providers/tikhub/",
    "changes/",
    "migrations/versions/",
)
EXCLUDED_FILES = {
    "tests/contracts/test_platform_identifier_consistency.py",
    "scripts/dev/_unify_platform_identifiers_once.py",
}


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def replace_required(path: str, old: str, new: str) -> None:
    text = read(path)
    if old not in text:
        raise RuntimeError(f"{path}: 未找到预期片段: {old[:80]!r}")
    write(path, text.replace(old, new))


def replace_current_xhs_tokens() -> None:
    for root_name in SCAN_ROOTS:
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
                continue
            relative = path.relative_to(ROOT).as_posix()
            if relative in EXCLUDED_FILES or relative.startswith(EXCLUDED_PREFIXES):
                continue
            text = path.read_text(encoding="utf-8")
            updated = XHS_TOKEN.sub("xiaohongshu", text)
            if updated != text:
                path.write_text(updated, encoding="utf-8")

    # 旧测试中曾用 dy 冒充平台值；这里显式改为正式值，不做全仓无差别缩写替换。
    path = ROOT / "tests/integration/collection/test_collection_repository.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace('"dy"', '"douyin"').replace("'dy'", "'douyin'")
    path.write_text(text, encoding="utf-8")


def rename_xiaohongshu_fixture_directory() -> None:
    source = ROOT / "tests/fixtures/providers/tikhub/xhs"
    target = ROOT / "tests/fixtures/providers/tikhub/xiaohongshu"
    if target.exists():
        return
    if not source.exists():
        raise RuntimeError("缺少预期小红书 Fixture 目录")
    source.rename(target)


def write_platform_contract() -> None:
    write(
        "backend/src/aima_ugc/contracts/platform.py",
        '''"""AIMA_UGC 唯一平台机器身份 Contract。"""\n\nfrom typing import Literal\n\ntype PlatformName = Literal[\n    "xiaohongshu",\n    "douyin",\n    "weibo",\n    "bilibili",\n    "kuaishou",\n]\ntype PlatformScope = Literal[\n    "all",\n    "xiaohongshu",\n    "douyin",\n    "weibo",\n    "bilibili",\n    "kuaishou",\n]\n\nPLATFORM_NAMES: tuple[PlatformName, ...] = (\n    "xiaohongshu",\n    "douyin",\n    "weibo",\n    "bilibili",\n    "kuaishou",\n)\nPLATFORM_SCOPES: tuple[PlatformScope, ...] = ("all", *PLATFORM_NAMES)\n\n__all__ = ["PLATFORM_NAMES", "PLATFORM_SCOPES", "PlatformName", "PlatformScope"]\n''',
    )


def patch_contract_types() -> None:
    path = "backend/src/aima_ugc/contracts/canonical/base.py"
    text = read(path)
    if "from aima_ugc.contracts.platform import PlatformName" not in text:
        text = text.replace(
            "from pydantic import BaseModel, ConfigDict, Field, field_validator\n",
            "from pydantic import BaseModel, ConfigDict, Field, field_validator\n\n"
            "from aima_ugc.contracts.platform import PlatformName\n",
        )
    text = re.sub(
        r"\nPlatformName = Annotated\[\n    str,\n    Field\(min_length=1, max_length=64, pattern=r\"\^\[a-z0-9\]\[a-z0-9_-\]\*\$\"\),\n\]\n",
        "\n",
        text,
        count=1,
    )
    write(path, text)

    path = "backend/src/aima_ugc/contracts/provider/base.py"
    text = read(path)
    if "from aima_ugc.contracts.platform import PlatformName" not in text:
        text = text.replace(
            "from pydantic import BaseModel, ConfigDict, Field, JsonValue, SecretStr\n",
            "from pydantic import BaseModel, ConfigDict, Field, JsonValue, SecretStr\n\n"
            "from aima_ugc.contracts.platform import PlatformName\n",
        )
    text = re.sub(
        r"\nPlatformName = Annotated\[\n    str,\n    Field\(min_length=1, max_length=64, pattern=r\"\^\[a-z0-9\]\[a-z0-9_-\]\*\$\"\),\n\]\n",
        "\n",
        text,
        count=1,
    )
    write(path, text)

    path = "backend/src/aima_ugc/contracts/http.py"
    text = read(path)
    if "from aima_ugc.contracts.platform import PlatformName, PlatformScope" not in text:
        marker = "from aima_ugc.contracts.collection.models import BusinessOperation\n"
        text = text.replace(
            marker,
            marker + "from aima_ugc.contracts.platform import PlatformName, PlatformScope\n",
        )
    text = text.replace(
        'type CollectionPlatform = Literal["xiaohongshu", "douyin", "weibo", "bilibili", "kuaishou"]',
        "type CollectionPlatform = PlatformName",
    )
    text = text.replace('    platform: str = "all"\n', '    platform_scope: PlatformScope = "all"\n')
    text = text.replace("    platform: str\n", "    platform: PlatformName\n")
    text = text.replace(
        "    platforms: tuple[str, ...] = Field(default=(), max_length=20)\n",
        "    platforms: tuple[PlatformName, ...] = Field(default=(), max_length=5)\n",
    )
    write(path, text)


def patch_excel_profile() -> None:
    write(
        "backend/src/aima_ugc/adapters/providers/imports/excel_profile.py",
        '''"""Excel 导入 Profile 与平台值归一化规则。"""\n\nfrom __future__ import annotations\n\nfrom dataclasses import dataclass\n\nfrom aima_ugc.contracts.platform import PlatformName\n\nfrom .models import ExcelImportRowError\n\nAIMA_MONITORING_EXCEL_V1 = "aima-monitoring-excel.v1"\n\n_REQUIRED_HEADERS = (\n    "媒体名称（中文）",\n    "标题",\n    "内文",\n    "作者",\n    "出版日期",\n    "原文链接",\n)\n\n_PLATFORM_LABELS: dict[str, PlatformName] = {\n    "小红书": "xiaohongshu",\n    "xiaohongshu": "xiaohongshu",\n    "抖音": "douyin",\n    "douyin": "douyin",\n    "微博": "weibo",\n    "新浪微博": "weibo",\n    "weibo": "weibo",\n    "b站": "bilibili",\n    "哔哩哔哩": "bilibili",\n    "bilibili": "bilibili",\n    "快手": "kuaishou",\n    "kuaishou": "kuaishou",\n}\n\n\n@dataclass(frozen=True, slots=True)\nclass ExcelImportProfile:\n    """描述一个受版本控制的源 Excel 结构。"""\n\n    name: str\n    default_sheet_name: str\n    required_headers: tuple[str, ...]\n\n    def resolve_platform(self, value: object) -> PlatformName:\n        text = _non_empty_text(value)\n        if text is None:\n            raise ExcelImportRowError("platform_missing", "媒体名称（中文）不能为空")\n        platform = _PLATFORM_LABELS.get(text)\n        if platform is not None:\n            return platform\n        raise ExcelImportRowError(\n            "platform_unmapped",\n            "媒体名称（中文）只能映射到系统五个平台机器标识",\n        )\n\n\n_PROFILE = ExcelImportProfile(\n    name=AIMA_MONITORING_EXCEL_V1,\n    default_sheet_name="文章",\n    required_headers=_REQUIRED_HEADERS,\n)\n\n\ndef get_excel_import_profile(name: str) -> ExcelImportProfile:\n    """按显式版本名取得 Excel Profile；未知版本 fail closed。"""\n\n    if name != _PROFILE.name:\n        raise ValueError(f"不支持的 Excel Profile: {name}")\n    return _PROFILE\n\n\ndef _non_empty_text(value: object) -> str | None:\n    if value is None:\n        return None\n    text = str(value).strip()\n    return text or None\n''',
    )


def patch_tikhub_runtime_type() -> None:
    path = "backend/src/aima_ugc/adapters/providers/tikhub/runtime.py"
    text = read(path)
    if "from aima_ugc.contracts.platform import PlatformName" not in text:
        text = text.replace(
            "from aima_ugc.contracts.canonical import CanonicalCommentV1, CanonicalContentV1\n",
            "from aima_ugc.contracts.canonical import CanonicalCommentV1, CanonicalContentV1\n"
            "from aima_ugc.contracts.platform import PlatformName\n",
        )
    text = text.replace(
        'TikHubPlatform = Literal["xiaohongshu", "douyin", "weibo", "bilibili", "kuaishou"]',
        "TikHubPlatform = PlatformName",
    )
    write(path, text)


def patch_collection_targets() -> None:
    path = "backend/src/aima_ugc/adapters/persistence/postgres/collection_targets.py"
    text = read(path)
    text = re.sub(
        r"\n# Collection 公共 Contract.*?_CONTENT_TO_COLLECTION_PLATFORM = \{.*?\n\}\n",
        "\n",
        text,
        flags=re.S,
        count=1,
    )
    text = text.replace("        stored_platforms = _stored_platforms(platforms)\n", "")
    text = text.replace("content.c.platform.in_(stored_platforms)", "content.c.platform.in_(platforms)")
    text = re.sub(
        r"\n\ndef _stored_platforms\(platforms: tuple\[str, \.\.\.\]\) -> tuple\[str, \.\.\.\]:.*?\n\ndef _target",
        "\n\ndef _target",
        text,
        flags=re.S,
        count=1,
    )
    text = re.sub(
        r"def _target\(row: RowMapping\) -> CollectionEnrichmentTarget:\n    stored_platform = cast\(str, row\[\"platform\"\]\)\n    return CollectionEnrichmentTarget\(\n        content_id=cast\(UUID, row\[\"id\"\]\),\n        platform=_CONTENT_TO_COLLECTION_PLATFORM.get\(stored_platform, stored_platform\),",
        'def _target(row: RowMapping) -> CollectionEnrichmentTarget:\n    return CollectionEnrichmentTarget(\n        content_id=cast(UUID, row["id"]),\n        platform=cast(str, row["platform"]),',
        text,
        count=1,
    )
    write(path, text)


def patch_frontend_batch_probe() -> None:
    path = "frontend/src/features/import-batches/api.ts"
    text = read(path)
    text = re.sub(
        r"\nconst contentPlatformByCollection: Record<CollectionPlatform, string> = \{.*?\n\}\n",
        "\n",
        text,
        flags=re.S,
        count=1,
    )
    text = text.replace(
        "    platforms: [contentPlatformByCollection[platform]],\n",
        "    platforms: [platform],\n",
    )
    write(path, text)


def patch_keyword_scope() -> None:
    path = "backend/src/aima_ugc/modules/system/models.py"
    text = read(path)
    if "from aima_ugc.contracts.platform import PlatformScope" not in text:
        text = text.replace(
            "from uuid import UUID\n",
            "from uuid import UUID\n\nfrom aima_ugc.contracts.platform import PlatformScope\n",
        )
    text = re.sub(
        r"(class KeywordPackItem:.*?\n)(    platform: str\n)",
        r"\1    platform_scope: PlatformScope\n",
        text,
        flags=re.S,
        count=1,
    )
    write(path, text)

    path = "backend/src/aima_ugc/modules/system/tables.py"
    text = read(path)
    if "from aima_ugc.contracts.platform import PLATFORM_SCOPES" not in text:
        text = text.replace(
            "from aima_ugc.platform.database.metadata import metadata\n",
            "from aima_ugc.contracts.platform import PLATFORM_SCOPES\n"
            "from aima_ugc.platform.database.metadata import metadata\n\n"
            "_PLATFORM_SCOPE_CHECK = \"platform_scope in (\" + \",\".join(\n"
            "    f\"'{value}'\" for value in PLATFORM_SCOPES\n"
            ") + \")\"\n",
        )
    text = text.replace('    Column("platform", Text(), primary_key=True),\n', '    Column("platform_scope", Text(), primary_key=True),\n')
    text = text.replace(
        '    CheckConstraint("char_length(platform) > 0", name="platform_nonempty"),\n',
        '    CheckConstraint(_PLATFORM_SCOPE_CHECK, name="platform_scope_allowed"),\n',
    )
    write(path, text)

    path = "backend/src/aima_ugc/adapters/persistence/postgres/keywords.py"
    text = read(path)
    text = text.replace('platform=row["platform"]', 'platform_scope=row["platform_scope"]')
    text = text.replace("keyword_pack_items_table.c.platform", "keyword_pack_items_table.c.platform_scope")
    text = text.replace("item.platform", "item.platform_scope")
    text = text.replace("platform=item.platform_scope", "platform_scope=item.platform_scope")
    write(path, text)

    path = "backend/src/aima_ugc/bootstrap/import_http.py"
    text = read(path)
    text = text.replace('                        platform="all",\n', '                        platform_scope="all",\n')
    text = text.replace("                platform=item.platform,\n", "                platform_scope=item.platform_scope,\n")
    write(path, text)

    path = "backend/src/aima_ugc/adapters/persistence/postgres/relevance.py"
    text = read(path).replace("keyword_pack_items_table.c.platform,", "keyword_pack_items_table.c.platform_scope,")
    write(path, text)

    path = "backend/src/aima_ugc/modules/collection/scheduled_scopes.py"
    text = read(path)
    if "from aima_ugc.contracts.platform import PlatformName, PlatformScope" not in text:
        text = text.replace(
            "from uuid import UUID\n",
            "from uuid import UUID\n\nfrom aima_ugc.contracts.platform import PlatformName, PlatformScope\n",
        )
    text = text.replace("item_platform", "item_platform_scope")
    text = text.replace("    item_platform_scope: str\n", "    item_platform_scope: PlatformScope\n")
    text = text.replace("    plan_platforms: tuple[str, ...],\n", "    plan_platforms: tuple[PlatformName, ...],\n")
    text = text.replace("`platform=all`", "`platform_scope=all`")
    write(path, text)

    path = "backend/src/aima_ugc/adapters/persistence/postgres/scheduled_keywords.py"
    text = read(path)
    text = text.replace("keyword_pack_items_table.c.platform.label(\"item_platform\")", "keyword_pack_items_table.c.platform_scope.label(\"item_platform_scope\")")
    text = text.replace("keyword_pack_items_table.c.platform,", "keyword_pack_items_table.c.platform_scope,")
    text = text.replace("item_platform=row[\"item_platform\"]", "item_platform_scope=row[\"item_platform_scope\"]")
    write(path, text)

    # KeywordPackItem 构造器的字段名是本次 Schema 语义修改的一部分。
    for root_name in ("tests", "backend/src"):
        root = ROOT / root_name
        for file_path in root.rglob("*.py"):
            relative = file_path.relative_to(ROOT).as_posix()
            if relative.startswith("migrations/") or relative == "scripts/dev/_unify_platform_identifiers_once.py":
                continue
            source = file_path.read_text(encoding="utf-8")
            updated = re.sub(
                r"(KeywordPackItem\((?:(?!\n\s*\)).)*?)\bplatform=",
                r"\1platform_scope=",
                source,
                flags=re.S,
            )
            if updated != source:
                file_path.write_text(updated, encoding="utf-8")

    path = "tests/integration/database/test_keyword_repository.py"
    text = read(path)
    text = text.replace('"platform",\n', '"platform_scope",\n')
    text = text.replace('"platform",\n        )', '"platform_scope",\n        )')
    text = text.replace('("pack_id", "keyword_id", "platform")', '("pack_id", "keyword_id", "platform_scope")')
    write(path, text)


def patch_platform_typed_domains() -> None:
    patches = {
        "backend/src/aima_ugc/modules/collection/planning.py": (
            "from aima_ugc.contracts.collection import CollectionDecisionPolicyV1\n",
            "from aima_ugc.contracts.collection import CollectionDecisionPolicyV1\nfrom aima_ugc.contracts.platform import PlatformName\n",
            [("    platform: str\n", "    platform: PlatformName\n")],
        ),
        "backend/src/aima_ugc/modules/collection/execution.py": (
            "from uuid import UUID\n",
            "from uuid import UUID\n\nfrom aima_ugc.contracts.platform import PlatformName\n",
            [("    platform: str\n", "    platform: PlatformName\n")],
        ),
        "backend/src/aima_ugc/modules/collection/provider_routing.py": (
            "from aima_ugc.contracts.collection import ProviderPlatformCapabilityV1, ProviderPlatformRouteV1\n",
            "from aima_ugc.contracts.collection import ProviderPlatformCapabilityV1, ProviderPlatformRouteV1\nfrom aima_ugc.contracts.platform import PlatformName\n",
            [("platform: str", "platform: PlatformName")],
        ),
        "backend/src/aima_ugc/modules/collection/run_snapshot.py": (
            "from aima_ugc.modules.system.models import ProviderConfig\n",
            "from aima_ugc.contracts.platform import PlatformName\nfrom aima_ugc.modules.system.models import ProviderConfig\n",
            [("    platform: str,\n", "    platform: PlatformName,\n")],
        ),
        "backend/src/aima_ugc/modules/collection/xhs_replay.py": (
            "from aima_ugc.contracts.provider import RawEnvelopeV1\n",
            "from aima_ugc.contracts.platform import PlatformName\nfrom aima_ugc.contracts.provider import RawEnvelopeV1\n",
            [("    platform: str\n", "    platform: PlatformName\n")],
        ),
        "backend/src/aima_ugc/modules/content/query.py": (
            "from aima_ugc.contracts.http import ContentFilterSnapshot\n",
            "from aima_ugc.contracts.http import ContentFilterSnapshot\nfrom aima_ugc.contracts.platform import PlatformName\n",
            [("    platform: str\n", "    platform: PlatformName\n")],
        ),
    }
    for path, (marker, replacement, substitutions) in patches.items():
        text = read(path)
        if replacement not in text:
            text = text.replace(marker, replacement)
        for old, new in substitutions:
            text = text.replace(old, new)
        write(path, text)


def patch_database_platform_checks() -> None:
    path = "backend/src/aima_ugc/modules/content/tables.py"
    text = read(path)
    if "from aima_ugc.contracts.platform import PLATFORM_NAMES" not in text:
        text = text.replace(
            "from aima_ugc.platform.database.metadata import metadata\n",
            "from aima_ugc.contracts.platform import PLATFORM_NAMES\n"
            "from aima_ugc.platform.database.metadata import metadata\n\n"
            "_PLATFORM_CHECK = \"platform in (\" + \",\".join(\n"
            "    f\"'{value}'\" for value in PLATFORM_NAMES\n"
            ") + \")\"\n",
        )
    account_marker = '    UniqueConstraint("platform", "external_account_id"),\n'
    if 'name="platform_allowed"' not in text.split("contents_table", 1)[0]:
        text = text.replace(account_marker, account_marker + '    CheckConstraint(_PLATFORM_CHECK, name="platform_allowed"),\n', 1)
    content_marker = '    UniqueConstraint("platform", "external_content_id"),\n'
    text = text.replace(content_marker, content_marker + '    CheckConstraint(_PLATFORM_CHECK, name="platform_allowed"),\n', 1)
    write(path, text)

    path = "backend/src/aima_ugc/modules/collection/tables.py"
    text = read(path)
    if "from aima_ugc.contracts.platform import PLATFORM_NAMES" not in text:
        text = text.replace(
            "from aima_ugc.platform.database.metadata import metadata\n",
            "from aima_ugc.contracts.platform import PLATFORM_NAMES\n"
            "from aima_ugc.platform.database.metadata import metadata\n\n"
            "_PLATFORM_CHECK = \"platform in (\" + \",\".join(\n"
            "    f\"'{value}'\" for value in PLATFORM_NAMES\n"
            ") + \")\"\n",
        )
    text = text.replace(
        '    CheckConstraint("char_length(platform) > 0", name="platform_nonempty"),\n',
        '    CheckConstraint(_PLATFORM_CHECK, name="platform_allowed"),\n',
        1,
    )
    scope_marker = '    UniqueConstraint("run_id", "platform", "source_type", "source_value", "operation_group"),\n'
    text = text.replace(scope_marker, scope_marker + '    CheckConstraint(_PLATFORM_CHECK, name="platform_allowed"),\n', 1)
    write(path, text)


def write_migration() -> None:
    write(
        "migrations/versions/20260822_0024_unify_platform_identifiers.py",
        '''"""统一五个平台机器标识并移除小红书双值语义。\n\nRevision ID: 20260822_0024\nRevises: 20260821_0023\n"""\n\nfrom collections.abc import Sequence\n\nimport sqlalchemy as sa\nfrom alembic import op\n\nrevision: str = "20260822_0024"\ndown_revision: str | Sequence[str] | None = "20260821_0023"\nbranch_labels: str | Sequence[str] | None = None\ndepends_on: str | Sequence[str] | None = None\n\n_ALLOWED = "('xiaohongshu','douyin','weibo','bilibili','kuaishou')"\n_SCOPE_ALLOWED = "('all','xiaohongshu','douyin','weibo','bilibili','kuaishou')"\n_OLD_REPLAY = "collection.xhs.raw-replay.v1"\n_NEW_REPLAY = "collection.xiaohongshu.raw-replay.v1"\n\n\ndef _exists(connection: sa.Connection, sql: str) -> bool:\n    return bool(connection.scalar(sa.text(f"SELECT EXISTS ({sql})")))\n\n\ndef _assert_no_identity_conflicts(connection: sa.Connection) -> None:\n    checks = {\n        "accounts": """\n            SELECT 1 FROM accounts old\n            JOIN accounts new ON new.external_account_id = old.external_account_id\n            WHERE old.platform = 'xhs' AND new.platform = 'xiaohongshu'\n        """,\n        "contents": """\n            SELECT 1 FROM contents old\n            JOIN contents new ON new.external_content_id = old.external_content_id\n            WHERE old.platform = 'xhs' AND new.platform = 'xiaohongshu'\n        """,\n        "collection_plan_platforms": """\n            SELECT 1 FROM collection_plan_platforms old\n            JOIN collection_plan_platforms new ON new.plan_id = old.plan_id\n            WHERE old.platform = 'xhs' AND new.platform = 'xiaohongshu'\n        """,\n        "collection_scopes": """\n            SELECT 1 FROM collection_scopes old\n            JOIN collection_scopes new\n              ON new.run_id = old.run_id\n             AND new.source_type = old.source_type\n             AND new.source_value = old.source_value\n             AND new.operation_group = old.operation_group\n            WHERE old.platform = 'xhs' AND new.platform = 'xiaohongshu'\n        """,\n        "keyword_pack_items": """\n            SELECT 1 FROM keyword_pack_items old\n            JOIN keyword_pack_items new\n              ON new.pack_id = old.pack_id AND new.keyword_id = old.keyword_id\n            WHERE old.platform = 'xhs' AND new.platform = 'xiaohongshu'\n        """,\n        "jobs": f"""\n            SELECT 1 FROM jobs old\n            JOIN jobs new ON new.internal_idempotency_key = old.internal_idempotency_key\n            WHERE old.job_type = '{_OLD_REPLAY}' AND new.job_type = '{_NEW_REPLAY}'\n        """,\n    }\n    conflicts = [name for name, sql in checks.items() if _exists(connection, sql)]\n    if conflicts:\n        raise RuntimeError(\n            "平台标识迁移冲突：同一业务身份同时存在旧值和正式值："\n            + ", ".join(conflicts)\n        )\n\n\ndef _rewrite_run_platforms(old: str, new: str) -> None:\n    op.execute(\n        sa.text(\n            """\n            UPDATE collection_runs\n            SET config_snapshot = jsonb_set(\n                config_snapshot,\n                '{platforms}',\n                (\n                    SELECT jsonb_agg(\n                        CASE\n                            WHEN jsonb_typeof(item) = 'object' AND item->>'platform' = :old\n                                THEN jsonb_set(item, '{platform}', to_jsonb(CAST(:new AS text)))\n                            WHEN item = to_jsonb(CAST(:old AS text))\n                                THEN to_jsonb(CAST(:new AS text))\n                            ELSE item\n                        END\n                        ORDER BY ord\n                    )\n                    FROM jsonb_array_elements(config_snapshot->'platforms')\n                         WITH ORDINALITY AS elements(item, ord)\n                )\n            )\n            WHERE jsonb_typeof(config_snapshot->'platforms') = 'array'\n              AND EXISTS (\n                  SELECT 1\n                  FROM jsonb_array_elements(config_snapshot->'platforms') AS elements(item)\n                  WHERE (jsonb_typeof(item) = 'object' AND item->>'platform' = :old)\n                     OR item = to_jsonb(CAST(:old AS text))\n              )\n            """\n        ).bindparams(old=old, new=new)\n    )\n\n\ndef upgrade() -> None:\n    connection = op.get_bind()\n    _assert_no_identity_conflicts(connection)\n\n    for table in ("accounts", "contents", "collection_plan_platforms", "collection_scopes"):\n        op.execute(f"UPDATE {table} SET platform = 'xiaohongshu' WHERE platform = 'xhs'")\n\n    op.execute("UPDATE keyword_pack_items SET platform = 'xiaohongshu' WHERE platform = 'xhs'")\n    op.execute(\n        "UPDATE collection_candidate_ingestions "\n        "SET canonical_identity = 'xiaohongshu:' || substring(canonical_identity from 5) "\n        "WHERE canonical_identity LIKE 'xhs:%'"\n    )\n    _rewrite_run_platforms("xhs", "xiaohongshu")\n\n    op.execute(\n        sa.text(\n            """\n            UPDATE jobs\n            SET job_type = CASE WHEN job_type = :old THEN :new ELSE job_type END,\n                payload_version = CASE WHEN payload_version = :old THEN :new ELSE payload_version END,\n                payload = CASE\n                    WHEN payload->>'schema_version' = :old\n                    THEN jsonb_set(payload, '{schema_version}', to_jsonb(CAST(:new AS text)))\n                    ELSE payload\n                END\n            WHERE job_type = :old OR payload_version = :old OR payload->>'schema_version' = :old\n            """\n        ).bindparams(old=_OLD_REPLAY, new=_NEW_REPLAY)\n    )\n\n    op.alter_column(\n        "keyword_pack_items",\n        "platform",\n        new_column_name="platform_scope",\n        existing_type=sa.Text(),\n        existing_nullable=False,\n    )\n\n    op.create_check_constraint(op.f("ck_accounts_platform_allowed"), "accounts", f"platform in {_ALLOWED}")\n    op.create_check_constraint(op.f("ck_contents_platform_allowed"), "contents", f"platform in {_ALLOWED}")\n    op.create_check_constraint(\n        op.f("ck_collection_plan_platforms_platform_allowed"),\n        "collection_plan_platforms",\n        f"platform in {_ALLOWED}",\n    )\n    op.create_check_constraint(\n        op.f("ck_collection_scopes_platform_allowed"),\n        "collection_scopes",\n        f"platform in {_ALLOWED}",\n    )\n    op.create_check_constraint(\n        op.f("ck_keyword_pack_items_platform_scope_allowed"),\n        "keyword_pack_items",\n        f"platform_scope in {_SCOPE_ALLOWED}",\n    )\n\n\ndef downgrade() -> None:\n    # 平台身份合并是不可逆数据归一化：旧库可能原本同时存在 Excel=xiaohongshu\n    # 与 TikHub=xhs，升级后无法仅凭当前行可靠恢复来源。Downgrade 因此只回退\n    # Schema/字段名；真正的数据回滚必须恢复升级前数据库备份。\n    op.drop_constraint(\n        op.f("ck_keyword_pack_items_platform_scope_allowed"),\n        "keyword_pack_items",\n        type_="check",\n    )\n    op.drop_constraint(\n        op.f("ck_collection_scopes_platform_allowed"),\n        "collection_scopes",\n        type_="check",\n    )\n    op.drop_constraint(\n        op.f("ck_collection_plan_platforms_platform_allowed"),\n        "collection_plan_platforms",\n        type_="check",\n    )\n    op.drop_constraint(op.f("ck_contents_platform_allowed"), "contents", type_="check")\n    op.drop_constraint(op.f("ck_accounts_platform_allowed"), "accounts", type_="check")\n    op.alter_column(\n        "keyword_pack_items",\n        "platform_scope",\n        new_column_name="platform",\n        existing_type=sa.Text(),\n        existing_nullable=False,\n    )\n''',
    )


def append_migration_tests() -> None:
    path = "tests/integration/database/test_migration_data_lifecycle.py"
    text = read(path)
    marker = "def test_0023_to_0024_unifies_platform_machine_values"
    if marker in text:
        return
    text += r'''


def test_0023_to_0024_unifies_platform_machine_values(migration_database: str) -> None:
    _upgrade(migration_database, "20260821_0023")
    account_id = uuid4()
    content_id = uuid4()
    pack_id = uuid4()
    keyword_id = uuid4()
    engine = _engine(migration_database)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO accounts(
                      id, platform, external_account_id, first_seen_at, last_seen_at,
                      field_observed_at, updated_at
                    ) VALUES (
                      :id, 'xhs', 'platform-migration-account', :seen, :seen, '{}'::jsonb, :seen
                    )
                    """
                ),
                {"id": account_id, "seen": _NOW},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO contents(
                      id, platform, external_content_id, content_type, author_account_id,
                      first_seen_at, last_seen_at, current_version, field_observed_at, updated_at
                    ) VALUES (
                      :id, 'xhs', 'platform-migration-content', 'image', :author_id,
                      :seen, :seen, 1, '{}'::jsonb, :seen
                    )
                    """
                ),
                {"id": content_id, "author_id": account_id, "seen": _NOW},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO keyword_packs(id, name, description, enabled, version, created_at, updated_at)
                    VALUES (:id, :name, '', TRUE, 1, :seen, :seen)
                    """
                ),
                {"id": pack_id, "name": f"platform-migration-{pack_id}", "seen": _NOW},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO keywords(id, text, normalized_text, enabled, created_at, updated_at)
                    VALUES (:id, '爱玛', :normalized, TRUE, :seen, :seen)
                    """
                ),
                {"id": keyword_id, "normalized": f"platform-migration-{keyword_id}", "seen": _NOW},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO keyword_pack_items(pack_id, keyword_id, platform, priority, enabled, note)
                    VALUES (:pack_id, :keyword_id, 'all', 10, TRUE, '')
                    """
                ),
                {"pack_id": pack_id, "keyword_id": keyword_id},
            )
    finally:
        engine.dispose()

    _upgrade(migration_database, "20260822_0024")

    engine = _engine(migration_database)
    try:
        inspector = inspect(engine)
        assert "platform_scope" in {item["name"] for item in inspector.get_columns("keyword_pack_items")}
        assert "platform" not in {item["name"] for item in inspector.get_columns("keyword_pack_items")}
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT platform FROM accounts WHERE id = :id"), {"id": account_id}) == "xiaohongshu"
            assert connection.scalar(text("SELECT platform FROM contents WHERE id = :id"), {"id": content_id}) == "xiaohongshu"
            assert connection.scalar(
                text(
                    "SELECT platform_scope FROM keyword_pack_items "
                    "WHERE pack_id = :pack_id AND keyword_id = :keyword_id"
                ),
                {"pack_id": pack_id, "keyword_id": keyword_id},
            ) == "all"
            with pytest.raises(Exception):
                connection.execute(
                    text(
                        "UPDATE contents SET platform = 'invalid-platform' WHERE id = :id"
                    ),
                    {"id": content_id},
                )
    finally:
        engine.dispose()


def test_0023_to_0024_blocks_duplicate_content_identity(migration_database: str) -> None:
    _upgrade(migration_database, "20260821_0023")
    engine = _engine(migration_database)
    try:
        with engine.begin() as connection:
            for platform in ("xhs", "xiaohongshu"):
                connection.execute(
                    text(
                        """
                        INSERT INTO contents(
                          id, platform, external_content_id, content_type,
                          first_seen_at, last_seen_at, current_version,
                          field_observed_at, updated_at
                        ) VALUES (
                          :id, :platform, 'platform-conflict', 'image',
                          :seen, :seen, 1, '{}'::jsonb, :seen
                        )
                        """
                    ),
                    {"id": uuid4(), "platform": platform, "seen": _NOW},
                )
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError, match="平台标识迁移冲突.*contents"):
        _upgrade(migration_database, "20260822_0024")

    engine = _engine(migration_database)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20260821_0023"
            platforms = connection.execute(
                text(
                    "SELECT platform FROM contents WHERE external_content_id = 'platform-conflict' "
                    "ORDER BY platform"
                )
            ).scalars().all()
            assert platforms == ["xhs", "xiaohongshu"]
    finally:
        engine.dispose()
'''
    write(path, text)


def write_platform_consistency_test() -> None:
    write(
        "tests/contracts/test_platform_identifier_consistency.py",
        '''"""平台机器标识在 Contract、数据库与当前代码中必须保持唯一。"""\n\nfrom __future__ import annotations\n\nimport re\nfrom pathlib import Path\nfrom typing import get_args\n\nimport pytest\nfrom pydantic import TypeAdapter, ValidationError\n\nfrom aima_ugc.adapters.providers.imports.excel_profile import get_excel_import_profile\nfrom aima_ugc.contracts.platform import PLATFORM_NAMES, PLATFORM_SCOPES, PlatformName, PlatformScope\nfrom aima_ugc.modules.collection.tables import (\n    collection_plan_platforms_table,\n    collection_scopes_table,\n)\nfrom aima_ugc.modules.content.tables import accounts_table, contents_table\nfrom aima_ugc.modules.system.tables import keyword_pack_items_table\n\n_REPO_ROOT = Path(__file__).resolve().parents[2]\n_LEGACY_TOKEN = "x" + "hs"\n_LEGACY_PATTERN = re.compile(rf"(?<![A-Za-z0-9_-]){_LEGACY_TOKEN}(?![A-Za-z0-9_-])")\n_SCAN_ROOTS = (\n    "backend/src",\n    "frontend/src",\n    "frontend/tests",\n    "frontend/e2e",\n    "frontend/e2e-fullstack",\n    "contracts",\n    "docs",\n    "scripts",\n    "tests",\n)\n_TEXT_SUFFIXES = {".py", ".ts", ".vue", ".json", ".md", ".toml", ".yml", ".yaml"}\n_EXCLUDED_PREFIXES = (\n    "changes/",\n    "migrations/versions/",\n    "tests/fixtures/providers/tikhub/",\n)\n_EXCLUDED_FILES = {\n    "tests/contracts/test_platform_identifier_consistency.py",\n    "scripts/dev/_unify_platform_identifiers_once.py",\n}\n_EXPECTED = ("xiaohongshu", "douyin", "weibo", "bilibili", "kuaishou")\n\n\ndef _check_sql(table, name: str) -> str:  # type: ignore[no-untyped-def]\n    constraints = [\n        str(item.sqltext)\n        for item in table.constraints\n        if getattr(item, "name", None) == name\n    ]\n    assert len(constraints) == 1\n    return constraints[0]\n\n\ndef test_platform_name_contract_is_exactly_five_values() -> None:\n    assert get_args(PlatformName) == _EXPECTED\n    assert PLATFORM_NAMES == _EXPECTED\n    assert get_args(PlatformScope) == ("all", *_EXPECTED)\n    assert PLATFORM_SCOPES == ("all", *_EXPECTED)\n\n    adapter = TypeAdapter(PlatformName)\n    for platform in _EXPECTED:\n        assert adapter.validate_python(platform) == platform\n    for invalid in ("xhs", "red", "dy", "wb", "ks", "bili", "all", "twitter", "XIAOHONGSHU"):\n        with pytest.raises(ValidationError):\n            adapter.validate_python(invalid)\n\n\ndef test_excel_profile_maps_source_labels_only_to_formal_platforms() -> None:\n    profile = get_excel_import_profile("aima-monitoring-excel.v1")\n    source_labels = {\n        "小红书": "xiaohongshu",\n        "xiaohongshu": "xiaohongshu",\n        "抖音": "douyin",\n        "douyin": "douyin",\n        "微博": "weibo",\n        "新浪微博": "weibo",\n        "weibo": "weibo",\n        "B站": "bilibili",\n        "哔哩哔哩": "bilibili",\n        "bilibili": "bilibili",\n        "快手": "kuaishou",\n        "kuaishou": "kuaishou",\n    }\n    for source, expected in source_labels.items():\n        assert profile.resolve_platform(source) == expected\n    for invalid in ("xhs", "red", "dy", "wb", "ks", "bili", "twitter", "XIAOHONGSHU"):\n        with pytest.raises(ValueError):\n            profile.resolve_platform(invalid)\n\n\ndef test_database_platform_identity_constraints_use_the_same_five_values() -> None:\n    for table in (accounts_table, contents_table, collection_plan_platforms_table, collection_scopes_table):\n        sql = _check_sql(table, "platform_allowed")\n        for value in _EXPECTED:\n            assert f"'{value}'" in sql\n        assert "'all'" not in sql\n\n    scope_sql = _check_sql(keyword_pack_items_table, "platform_scope_allowed")\n    assert "'all'" in scope_sql\n    for value in _EXPECTED:\n        assert f"'{value}'" in scope_sql\n\n\ndef test_current_machine_facts_do_not_reintroduce_legacy_xhs_token() -> None:\n    violations: list[str] = []\n    for root_name in _SCAN_ROOTS:\n        root = _REPO_ROOT / root_name\n        if not root.exists():\n            continue\n        for path in root.rglob("*"):\n            if not path.is_file() or path.suffix not in _TEXT_SUFFIXES:\n                continue\n            relative = path.relative_to(_REPO_ROOT).as_posix()\n            if relative in _EXCLUDED_FILES or relative.startswith(_EXCLUDED_PREFIXES):\n                continue\n            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):\n                if _LEGACY_PATTERN.search(line):\n                    violations.append(f"{relative}:{line_number}: {line.strip()}")\n    assert not violations, (\n        "当前机器事实仍包含旧小红书平台缩写；平台身份只能使用五个正式值。\\n"\n        + "\\n".join(violations)\n    )\n''',
    )


def patch_docs_and_change() -> None:
    path = "docs/appendix/Stage8F前后端能力矩阵与真实验收.md"
    text = read(path)
    text = text.replace("`xiaohongshu` / `xiaohongshu`", "`xiaohongshu`")
    text = text.replace("stored platform = xiaohongshu 或 xiaohongshu", "stored platform = xiaohongshu")
    text = text.replace("这条兼容链", "这条统一链")
    text = text.replace("兼容映射", "统一平台身份")
    write(path, text)

    path = "docs/roadmap/README.md"
    text = read(path)
    text = text.replace(
        "Excel Batch 小红书补采的 xiaohongshu/xiaohongshu 边界已有正式兼容和集成回归",
        "Excel 与 TikHub 的小红书平台身份统一为 xiaohongshu，并有集成回归",
    )
    text = text.replace("xiaohongshu/xiaohongshu", "xiaohongshu")
    write(path, text)

    path = "docs/blueprint/07-技术决策与实施门禁.md"
    text = read(path)
    if "平台机器身份只允许五个完整名称" not in text:
        text += '''\n\n# 平台机器身份：只允许五个完整名称\n\n系统内部平台身份固定为：\n\n```text\nxiaohongshu\ndouyin\nweibo\nbilibili\nkuaishou\n```\n\n这五个值贯穿 Provider Capability、Canonical、Collection Plan/Run/Scope、Content、HTTP Contract、generated Client、Frontend 与 PostgreSQL。\n\n禁止把平台缩写、品牌别名、大小写变体或 `all` 通配符写入平台身份字段。外部 Excel 的中文媒体名称只在入口 Profile 映射一次；“词包适用于全部平台”使用 `platform_scope=all`，不再冒充平台身份。PostgreSQL 平台身份列必须有五值 CHECK 作为最终完整性门禁。\n'''
    write(path, text)

    path = "changes/active/CHG-20260822-unify-platform-identifiers/CHANGE.md"
    text = read(path)
    text = text.replace(
        "关键词“全平台”会作为 scope 语义单独处理，不再冒充平台身份。" if "关键词“全平台”会作为 scope 语义单独处理，不再冒充平台身份。" in text else "外部输入中的中文“`小红书`”仍作为源数据映射到 `xiaohongshu`；不再接受 `xhs` / `red` 作为 Excel 机器别名。历史 Change 与旧 Migration 保留当时事实，不改写历史。",
        "外部输入中的中文平台名称只在入口映射到正式五值；不接受平台缩写/别名作为内部机器值。关键词全平台适用语义改为 `platform_scope=all`，不再占用平台身份字段。历史 Change 与旧 Migration 保留当时事实，不改写历史。",
    )
    text = text.replace(
        "## 回滚\n\nDowngrade 仅作为版本回滚机制，把本 Migration 统一后的正式小红书平台值恢复为旧 `xhs` 语义；它不代表运行时继续兼容旧值。",
        "## 回滚\n\n平台数据归一化不可从最终值推断旧来源，因此 Alembic downgrade 只回退 Schema/字段名；生产级数据回滚必须恢复升级前 PostgreSQL 备份。当前项目尚未生产部署，合并前通过隔离数据库完整验证该路径。",
    )
    write(path, text)


def main() -> int:
    rename_xiaohongshu_fixture_directory()
    replace_current_xhs_tokens()
    write_platform_contract()
    patch_contract_types()
    patch_excel_profile()
    patch_tikhub_runtime_type()
    patch_collection_targets()
    patch_frontend_batch_probe()
    patch_keyword_scope()
    patch_platform_typed_domains()
    patch_database_platform_checks()
    write_migration()
    append_migration_tests()
    write_platform_consistency_test()
    patch_docs_and_change()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
