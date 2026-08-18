"""全面整改新增 Schema 的 Owner 注册回归。"""

from aima_ugc.modules.collection.corrective_tables import (
    collection_content_actions_table,
)
from aima_ugc.modules.content.extended_tables import (
    comment_locations_table,
    comment_media_table,
    comment_mentions_table,
    comment_thread_coverage_observations_table,
    content_external_ids_table,
    content_locations_table,
    content_media_table,
    content_mentions_table,
    content_topics_table,
)


def test_comprehensive_corrective_schema_is_registered() -> None:
    assert collection_content_actions_table.info["owner"] == "collection"
    assert content_external_ids_table.info["owner"] == "content"
    assert content_media_table.info["owner"] == "content"
    assert content_topics_table.info["owner"] == "content"
    assert content_mentions_table.info["owner"] == "content"
    assert content_locations_table.info["owner"] == "content"
    assert comment_media_table.info["owner"] == "content"
    assert comment_mentions_table.info["owner"] == "content"
    assert comment_locations_table.info["owner"] == "content"
    assert comment_thread_coverage_observations_table.info["owner"] == "content"
