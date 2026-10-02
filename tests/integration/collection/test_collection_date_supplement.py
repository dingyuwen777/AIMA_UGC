from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.collection_targets import PostgresCollectionTargetReader
from aima_ugc.bootstrap.collection_http import PostgresCollectionHttpService
from aima_ugc.contracts.http import (
    CollectionDateSupplementQuery,
    CollectionRunCreateRequest,
    CollectionRuntimeListQuery,
)
from aima_ugc.modules.analysis.tables import analysis_content_results_table
from aima_ugc.modules.collection.http import CollectionConflict
from aima_ugc.modules.collection.tables import collection_runs_table, collection_scopes_table
from aima_ugc.modules.content.extended_tables import content_external_ids_table
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.platform.jobs.tables import jobs_table
from sqlalchemy import insert, select, text, update

from tests.integration.collection.test_collection_supplement_target_eligibility import (
    _insert_content,
    _seed_batch,
)
from tests.integration.collection.test_stage8e_collection_http_runtime import (
    _seed_config_and_search_pack,
)
from tests.integration.collection.test_stage8e_collection_http_runtime import (
    runtime as postgres_runtime,
)

runtime = postgres_runtime

FROM = datetime.fromisoformat("2026-09-01T00:00:00+08:00")
TO = datetime.fromisoformat("2026-09-01T23:59:59.999+08:00")
PLATFORMS = ("xiaohongshu", "douyin", "weibo", "bilibili", "kuaishou")


def test_date_eligibility_can_read_more_than_postgres_bind_limit(runtime) -> None:  # type: ignore[no-untyped-def]
    """日期没有人为条数上限，身份/相关性读取也不能被逐 ID 参数数限制。"""
    with runtime.database.engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO contents (id, platform, external_content_id, content_type, "
                "published_at, first_seen_at, last_seen_at, updated_at, current_version, "
                "field_observed_at) SELECT gen_random_uuid(), 'douyin', "
                "'large-date-' || n::text, 'video', :now, :now, :now, :now, 1, "
                "'{}'::jsonb FROM generate_series(1, 70000) n"
            ),
            {"now": FROM},
        )
    with runtime.database.new_session() as session:
        targets, sources, diagnostics = PostgresCollectionTargetReader(
            session
        ).list_date_range_selection(published_from=FROM, published_to=TO, platforms=("douyin",))
    assert targets == ()
    assert len(sources) == 70_000
    assert len(diagnostics) == 1 and diagnostics[0].blocked_count == 70_000


def test_date_range_uses_current_content_across_sources_and_closed_beijing_bounds(runtime) -> None:  # type: ignore[no-untyped-def]
    _, job_id, attempt_id, artifact_id = _seed_batch(runtime)
    expected = []
    for ordinal, (platform, id_type, native_id) in enumerate(
        (
            ("xiaohongshu", "note_id", "note-1"),
            ("douyin", "aweme_id", "123456789"),
            ("weibo", "status_id", "1234567890"),
            ("bilibili", "av_id", "123456"),
            ("kuaishou", "photo_id", "photo-1"),
        )
    ):
        content_id = _insert_content(
            runtime,
            attempt_id=attempt_id,
            artifact_id=artifact_id,
            external_content_id=native_id,
            lookup_id=True,
            job_id=job_id,
            irrelevant=False,
            platform=platform,
            lookup_id_type=id_type,
        )
        expected.append(content_id)
        with runtime.database.engine.begin() as connection:
            connection.execute(
                update(contents_table)
                .where(contents_table.c.id == content_id)
                .values(
                    published_at=FROM
                    if ordinal == 0
                    else TO
                    if ordinal == 1
                    else FROM + timedelta(hours=12)
                )
            )
    for ordinal, published_at in enumerate(
        (None, FROM - timedelta(microseconds=1), TO + timedelta(microseconds=1))
    ):
        with runtime.database.engine.begin() as connection:
            connection.execute(
                insert(contents_table).values(
                    id=uuid4(),
                    platform="douyin",
                    external_content_id=f"outside-{ordinal}",
                    content_type="video",
                    published_at=published_at,
                    first_seen_at=FROM,
                    last_seen_at=FROM,
                    updated_at=FROM,
                    current_version=1,
                    field_observed_at={},
                )
            )
    # 没有任何导入来源关联的内容也必须进入日期补采。
    standalone = uuid4()
    with runtime.database.engine.begin() as connection:
        connection.execute(
            insert(contents_table).values(
                id=standalone,
                platform="douyin",
                external_content_id="standalone-native-id",
                content_type="video",
                published_at=FROM,
                first_seen_at=FROM,
                last_seen_at=FROM,
                updated_at=FROM,
                current_version=1,
                field_observed_at={},
            )
        )
    candidate = _insert_content(
        runtime,
        attempt_id=attempt_id,
        artifact_id=artifact_id,
        external_content_id="url_sha256:date-candidate",
        lookup_id=False,
        job_id=job_id,
        irrelevant=False,
    )
    with runtime.database.engine.begin() as connection:
        connection.execute(
            update(contents_table).where(contents_table.c.id == candidate).values(published_at=FROM)
        )
        connection.execute(
            insert(content_external_ids_table).values(
                content_id=candidate,
                id_type="share_text",
                external_id="https://xhslink.com/o/example",
                provider_attempt_id=attempt_id,
                raw_artifact_id=artifact_id,
                observed_at=FROM,
            )
        )
    with runtime.database.new_session() as session:
        reader = PostgresCollectionTargetReader(session)
        targets, sources, diagnostics = reader.list_date_range_selection(
            published_from=FROM,
            published_to=TO,
            platforms=PLATFORMS,
        )
    assert {target.content_id for target in targets} == {*expected, candidate}
    assert {item.content_id for item in sources} == {*expected, standalone, candidate}
    assert len(sources) == 7
    assert len(diagnostics) == 5
    assert sum(item.direct_target_count for item in diagnostics) == 5
    assert sum(item.resolution_candidate_count for item in diagnostics) == 1
    assert sum(item.blocked_count for item in diagnostics) == 1


def test_date_selection_excludes_current_irrelevant_and_freezes_unavailable_siblings(
    runtime,
) -> None:  # type: ignore[no-untyped-def]
    config_id, _ = _seed_config_and_search_pack(runtime)
    _, job_id, attempt_id, artifact_id = _seed_batch(runtime)
    ids = []
    for external_id, typed, irrelevant in (
        ("native-note", True, True),
        ("irrelevant-note", True, True),
        ("url_sha256:blocked", False, False),
    ):
        # 每个 AI Run 的 Planner Job 有唯一约束，两个结果使用独立的测试父 Job。
        analysis_job_id = _seed_batch(runtime)[1] if irrelevant and ids else job_id
        ids.append(
            _insert_content(
                runtime,
                attempt_id=attempt_id,
                artifact_id=artifact_id,
                external_content_id=external_id,
                lookup_id=typed,
                job_id=analysis_job_id,
                irrelevant=irrelevant,
            )
        )
    with runtime.database.engine.begin() as connection:
        connection.execute(
            update(analysis_content_results_table)
            .where(analysis_content_results_table.c.content_id == ids[0])
            .values(relevance="relevant", sentiment="中性")
        )
        connection.execute(
            update(contents_table).where(contents_table.c.id.in_(ids)).values(published_at=FROM)
        )
    service = PostgresCollectionHttpService(runtime, cursor_signing_secret=b"r" * 32)
    query = CollectionDateSupplementQuery(published_from=FROM, published_to=TO)
    eligibility = service.get_date_supplement_eligibility(query)
    assert eligibility.targets[0].target_count == 1
    assert eligibility.diagnostics[0].blocked_count == 1
    request = CollectionRunCreateRequest(
        mode="date_supplement",
        published_from=FROM,
        published_to=TO,
        platforms=({"platform": "xiaohongshu", "provider_config_id": config_id},),
    )
    created = service.create_run(request, request_id="date-freeze")
    with runtime.database.engine.begin() as connection:
        run = (
            connection.execute(
                select(collection_runs_table).where(collection_runs_table.c.id == created.run_id)
            )
            .mappings()
            .one()
        )
        scope_ids = connection.scalars(
            select(collection_scopes_table.c.source_value).where(
                collection_scopes_table.c.run_id == created.run_id
            )
        ).all()
        assert (
            connection.scalar(select(jobs_table.c.id).where(jobs_table.c.id == created.job_id))
            == created.job_id
        )
        # 排队后日期和相关性均改变；执行读取仍须保留已经冻结的目标。
        connection.execute(
            update(contents_table)
            .where(contents_table.c.id == ids[0])
            .values(published_at=FROM - timedelta(days=1))
        )
        connection.execute(
            update(analysis_content_results_table)
            .where(analysis_content_results_table.c.content_id == ids[0])
            .values(relevance="irrelevant", sentiment=None)
        )
    assert set(scope_ids) == {str(ids[0]), str(ids[2])}
    assert run["import_batch_id"] is None and run["data_import_campaign_id"] is None
    assert run["config_snapshot"]["schema_version"] == "collection-run-config.v3"
    assert run["config_snapshot"]["supplement_selection"] == {
        "type": "published_date_range",
        "published_from": FROM.isoformat(),
        "published_to": TO.isoformat(),
    }
    with runtime.database.new_session() as session:
        reader = PostgresCollectionTargetReader(session)
        assert reader.get_content_target(content_id=ids[0]) is not None
        # 相关性只限制创建；执行期读取明确不相关内容也不重新筛选。
        assert reader.get_content_target(content_id=ids[1]) is not None
    detail = service.get_run(created.run_id)
    assert detail.mode == "date_supplement" and detail.published_from == FROM
    listing = service.list_runtime_runs(
        CollectionRuntimeListQuery(record_types=("tikhub_date_supplement",), limit=1)
    )
    assert listing.items[0].display_name == "TikHub 日期补采 · 2026-09-01 ~ 2026-09-01"
    assert listing.items[0].collection_run_id == created.run_id
    with pytest.raises(CollectionConflict):
        service.create_run(
            CollectionRunCreateRequest(
                mode="date_supplement",
                published_from=FROM,
                published_to=TO,
                platforms=({"platform": "douyin", "provider_config_id": config_id},),
            ),
            request_id="empty-platform",
        )
