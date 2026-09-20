"""声音广场高频查询所需的数据库索引。"""

from aima_ugc.database_schema import metadata


def test_voice_plaza_query_indexes_are_registered_in_metadata() -> None:
    expected = {
        "contents": {"ix_contents_published_at_id_desc"},
        "comments": {
            "ix_comments_content_roots_published_desc",
            "ix_comments_content_thread_published",
        },
        "analysis_content_results": {"ix_analysis_results_content_version_run"},
        "analysis_content_run_targets": {"ix_analysis_targets_content_version_run"},
    }

    for table_name, index_names in expected.items():
        actual = {index.name for index in metadata.tables[table_name].indexes}
        assert index_names <= actual

    sort_index = next(
        index
        for index in metadata.tables["contents"].indexes
        if index.name == "ix_contents_published_at_id_desc"
    )
    assert "contents.published_at DESC NULLS LAST" in str(sort_index.expressions[0])
