"""声音广场增量读模型与固定成本查询形态回归。"""

from aima_ugc.adapters.persistence.postgres.content_queries import (
    PostgresContentQueryRepository,
)
from aima_ugc.contracts.http import ContentFilterOptionsResponse, ContentFilterSnapshot
from aima_ugc.database_schema import metadata
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session


def _postgres_sql(statement: object) -> str:
    """用生产 PostgreSQL 方言编译语句，避免 SQLite 隐藏查询形态差异。"""

    return str(
        statement.compile(  # type: ignore[attr-defined]
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).lower()


def test_voice_plaza_projection_schema_exposes_indexed_current_state() -> None:
    projection = metadata.tables["voice_plaza_content_projection"]
    state = metadata.tables["voice_plaza_projection_state"]

    assert {
        "content_id",
        "content_version",
        "sort_at",
        "platform",
        "analysis_status",
        "effective_relevance",
        "labels",
        "brand_ids",
        "vehicle_model_ids",
        "competition_scope",
        "updated_at",
    } <= set(projection.c.keys())
    assert {"singleton", "status", "last_content_id", "projected_count"} <= set(state.c.keys())
    assert {
        "ix_voice_plaza_projection_latest",
        "ix_voice_plaza_projection_published_latest",
        "ix_voice_plaza_projection_platform_latest",
        "ix_voice_plaza_projection_labels_gin",
        "ix_voice_plaza_projection_brand_ids_gin",
        "ix_voice_plaza_projection_vehicle_ids_gin",
    } <= {index.name for index in projection.indexes}
    published_latest = next(
        index
        for index in projection.indexes
        if index.name == "ix_voice_plaza_projection_published_latest"
    )
    predicate = str(published_latest.dialect_options["postgresql"]["where"])
    assert "is_visible IS TRUE" in predicate


def test_voice_plaza_source_ledgers_expose_content_lookup_indexes() -> None:
    """来源可见性按 Content 反查时必须命中部分索引，不能重复扫描历史账本。"""

    expected = {
        "processing_import_batch_items": "ix_processing_import_batch_items_content_id",
        "collection_candidate_ingestions": "ix_collection_candidate_ingestions_content_id",
    }

    for table_name, index_name in expected.items():
        table = metadata.tables[table_name]
        index = next(index for index in table.indexes if index.name == index_name)
        predicate = str(index.dialect_options["postgresql"]["where"])
        assert "content_id IS NOT NULL" in predicate


def test_voice_plaza_list_statement_has_no_global_window_projection() -> None:
    repository = PostgresContentQueryRepository(Session(), analysis_identity=None)
    statement, _ = repository._base_statement(ContentFilterSnapshot())  # noqa: SLF001

    sql = _postgres_sql(statement)

    assert "voice_plaza_content_projection" in sql
    assert "row_number() over" not in sql


def test_voice_plaza_count_statement_uses_projection_and_current_filters() -> None:
    """筛选总数必须复用窄投影，不能重新扫描旧 Current 窗口或加载全部 ID。"""

    repository = PostgresContentQueryRepository(Session(), analysis_identity=None)
    statement = repository._projection_count_statement(  # noqa: SLF001
        ContentFilterSnapshot(platforms=("xiaohongshu",), search="爱玛")
    )

    sql = _postgres_sql(statement)

    assert "count(*)" in sql
    assert "voice_plaza_content_projection" in sql
    assert "voice_plaza_content_projection.platform in ('xiaohongshu')" in sql
    assert "contents.title ilike" in sql
    assert "row_number() over" not in sql


def test_comment_reply_counts_are_grouped_once_per_content() -> None:
    repository = PostgresContentQueryRepository(Session(), analysis_identity=None)

    sql = _postgres_sql(repository._comment_statement(None))  # type: ignore[arg-type]  # noqa: SLF001

    assert "group by thread_reply_comment.content_id, thread_reply_comment.root_comment_id" in sql


def test_filter_options_contract_reports_projection_catalog_status() -> None:
    schema = ContentFilterOptionsResponse.model_json_schema()

    assert schema["properties"]["catalog_status"]["enum"] == ["building", "ready"]
