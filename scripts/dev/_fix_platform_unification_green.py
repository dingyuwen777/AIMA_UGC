"""一次性修复平台标识统一首轮 Green 暴露的机械问题。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def patch(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"{path}: expected snippet not found: {old[:80]!r}")
    target.write_text(text.replace(old, new), encoding="utf-8")


def main() -> int:
    patch(
        "migrations/versions/20260822_0024_unify_platform_identifiers.py",
        "    _assert_no_identity_conflicts(connection)\n\n"
        "    for table in (\"accounts\", \"contents\", \"collection_plan_platforms\", \"collection_scopes\"):\n",
        "    _assert_no_identity_conflicts(connection)\n\n"
        "    op.drop_constraint(\n"
        "        op.f(\"ck_collection_plan_platforms_platform_nonempty\"),\n"
        "        \"collection_plan_platforms\",\n"
        "        type_=\"check\",\n"
        "    )\n"
        "    op.drop_constraint(\n"
        "        op.f(\"ck_keyword_pack_items_platform_nonempty\"),\n"
        "        \"keyword_pack_items\",\n"
        "        type_=\"check\",\n"
        "    )\n\n"
        "    for table in (\"accounts\", \"contents\", \"collection_plan_platforms\", \"collection_scopes\"):\n",
    )
    patch(
        "migrations/versions/20260822_0024_unify_platform_identifiers.py",
        "    op.alter_column(\n"
        "        \"keyword_pack_items\",\n"
        "        \"platform_scope\",\n"
        "        new_column_name=\"platform\",\n"
        "        existing_type=sa.Text(),\n"
        "        existing_nullable=False,\n"
        "    )\n",
        "    op.alter_column(\n"
        "        \"keyword_pack_items\",\n"
        "        \"platform_scope\",\n"
        "        new_column_name=\"platform\",\n"
        "        existing_type=sa.Text(),\n"
        "        existing_nullable=False,\n"
        "    )\n"
        "    op.create_check_constraint(\n"
        "        op.f(\"ck_keyword_pack_items_platform_nonempty\"),\n"
        "        \"keyword_pack_items\",\n"
        "        \"char_length(platform) > 0\",\n"
        "    )\n"
        "    op.create_check_constraint(\n"
        "        op.f(\"ck_collection_plan_platforms_platform_nonempty\"),\n"
        "        \"collection_plan_platforms\",\n"
        "        \"char_length(platform) > 0\",\n"
        "    )\n",
    )
    patch(
        "tests/integration/database/test_migration_data_lifecycle.py",
        "from sqlalchemy.engine import Engine\n",
        "from sqlalchemy.engine import Engine\nfrom sqlalchemy.exc import IntegrityError\n",
    )
    patch(
        "tests/integration/database/test_migration_data_lifecycle.py",
        "with pytest.raises(Exception):",
        "with pytest.raises(IntegrityError):",
    )
    patch(
        "backend/src/aima_ugc/adapters/providers/imports/excel_profile.py",
        '    "b站": "bilibili",\n',
        '    "B站": "bilibili",\n',
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
