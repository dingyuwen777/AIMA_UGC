"""把 Content Owner 的 Provider Attempt/Raw 来源绑定为同一事实对。"""

from sqlalchemy import ForeignKeyConstraint, UniqueConstraint

from aima_ugc.modules.collection.tables import provider_request_attempts_table
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
from aima_ugc.modules.content.tables import (
    comment_coverage_observations_table,
    comment_metric_observations_table,
    comment_versions_table,
    content_metric_observations_table,
    content_versions_table,
)

_SOURCE_TABLES = (
    content_versions_table,
    content_metric_observations_table,
    comment_versions_table,
    comment_metric_observations_table,
    comment_coverage_observations_table,
    content_external_ids_table,
    content_media_table,
    content_topics_table,
    content_mentions_table,
    content_locations_table,
    comment_media_table,
    comment_mentions_table,
    comment_locations_table,
    comment_thread_coverage_observations_table,
)


def register_content_source_constraints() -> None:
    """幂等注册复合来源约束，供运行 Schema 与 Alembic drift 检查共用。"""
    parent_name = "uq_provider_request_attempts_id_raw_artifact"
    if not any(constraint.name == parent_name for constraint in provider_request_attempts_table.constraints):
        provider_request_attempts_table.append_constraint(
            UniqueConstraint(
                provider_request_attempts_table.c.id,
                provider_request_attempts_table.c.raw_artifact_id,
                name=parent_name,
            )
        )

    for table in _SOURCE_TABLES:
        constraint_name = f"fk_{table.name}_attempt_raw_source"
        if any(constraint.name == constraint_name for constraint in table.constraints):
            continue
        table.append_constraint(
            ForeignKeyConstraint(
                [table.c.provider_attempt_id, table.c.raw_artifact_id],
                [
                    provider_request_attempts_table.c.id,
                    provider_request_attempts_table.c.raw_artifact_id,
                ],
                name=constraint_name,
            )
        )


__all__ = ["register_content_source_constraints"]
