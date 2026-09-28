"""工作台 Schema 与查询索引机器约束。"""

from aima_ugc.database_schema import metadata


def test_workbench_layout_table_has_dashboard_owner_and_revision_constraints() -> None:
    """用户布局必须是 Dashboard/Workbench 唯一写事实，并具备版本与 JSON 结构约束。"""

    table = metadata.tables["workbench_layouts"]
    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in table.constraints
        if hasattr(constraint, "sqltext")
    }

    assert table.info["owner"] == "dashboard"
    assert "ck_workbench_layouts_revision_positive" in checks
    assert "ck_workbench_layouts_principal_id_nonempty" in checks
    assert "ck_workbench_layouts_layout_array" in checks


def test_workbench_snapshot_table_is_rebuildable_and_revision_fenced() -> None:
    """聚合快照必须保存筛选、来源修订和刷新代次，且明确标记为派生数据。"""

    table = metadata.tables["workbench_snapshots"]
    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in table.constraints
        if hasattr(constraint, "sqltext")
    }

    assert table.info == {"owner": "dashboard", "derived": True}
    assert tuple(table.primary_key.columns.keys()) == ("module", "query_hash")
    assert {
        "query",
        "analysis_scheme_version_id",
        "target_analysis_scheme_version_id",
        "source_revision",
        "target_revision",
        "refresh_generation",
        "response",
        "computed_at",
    }.issubset(table.columns.keys())
    assert "ck_workbench_snapshots_status_allowed" in checks
    assert "ck_workbench_snapshots_response_computed_consistent" in checks


def test_analysis_runs_register_active_scheme_lookup_index() -> None:
    """Migration 新增的 active Scheme 查询索引必须同步进入 SQLAlchemy MetaData。"""

    indexes = {
        index.name: tuple(column.name for column in index.columns)
        for index in metadata.tables["analysis_content_runs"].indexes
    }

    assert indexes["ix_analysis_runs_scheme_sequence"] == (
        "analysis_scheme_version_id",
        "sequence_no",
        "id",
    )
