"""媒体 Migration 的 DDL 回退保留稳定事实，但明确移除新增元数据与播放状态。"""

from uuid import UUID, uuid4

from aima_ugc.modules.content.contribution_tables import content_source_contributions_table
from aima_ugc.modules.content.extended_tables import content_media_table
from aima_ugc.modules.content.media_playback_tables import content_media_playback_states_table
from aima_ugc.modules.content.tables import content_versions_table, contents_table
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from sqlalchemy import insert, inspect, select, text

from tests.integration.content.test_content_playback import _prepare, _seed
from tests.integration.database.test_migration_data_lifecycle import (
    _downgrade,
    _engine,
    _migration_target,
    _upgrade,
)
from tests.integration.database.test_migration_data_lifecycle import (
    migration_database as migration_database,
)


def test_0085_0086_data_roundtrip_preserves_stable_facts_and_immutable_delta(migration_database):
    _upgrade(migration_database, "20261009_0086")
    with _migration_target(migration_database):
        runtime = DatabaseRuntime(load_settings())
        try:
            seed = _seed(runtime, with_url=False)
            _prepare(seed)
            with runtime.new_session() as session, session.begin():
                source = seed.observation.source
                session.execute(
                    insert(content_source_contributions_table).values(
                        id=uuid4(),
                        source_item_key="a" * 64,
                        content_id=seed.content_id,
                        provider_attempt_id=UUID(source.provider_attempt_id),
                        raw_artifact_id=source.raw_artifact_id,
                        version_after=1,
                        delta={
                            "schema_version": "content-source-contribution.v1",
                            "legacy": {"value": 1},
                        },
                        observed_at=seed.observation.observed_at,
                        created_at=seed.observation.observed_at,
                    )
                )
                stable = dict(session.execute(select(content_media_table)).mappings().one())
                assert stable.pop("observation_metadata")
                before = [
                    tuple(dict(row) for row in session.execute(select(table)).mappings())
                    for table in (
                        contents_table,
                        content_versions_table,
                        content_source_contributions_table,
                    )
                ]
                assert (
                    session.execute(select(content_media_playback_states_table)).first() is not None
                )
        finally:
            runtime.dispose()
    _downgrade(migration_database, "20261009_0084")
    engine = _engine(migration_database)
    try:
        with engine.begin() as connection:
            assert "content_media_playback_states" not in inspect(connection).get_table_names()
            assert "observation_metadata" not in {
                column["name"] for column in inspect(connection).get_columns("content_media")
            }
            assert (
                dict(connection.execute(text("SELECT * FROM content_media")).mappings().one())
                == stable
            )
    finally:
        engine.dispose()
    _upgrade(migration_database, "20261009_0086")
    engine = _engine(migration_database)
    try:
        with engine.begin() as connection:
            restored = dict(connection.execute(select(content_media_table)).mappings().one())
            assert restored.pop("observation_metadata") == {}
            assert restored == stable
            assert connection.execute(select(content_media_playback_states_table)).first() is None
            assert [
                tuple(dict(row) for row in connection.execute(select(table)).mappings())
                for table in (
                    contents_table,
                    content_versions_table,
                    content_source_contributions_table,
                )
            ] == before
    finally:
        engine.dispose()
