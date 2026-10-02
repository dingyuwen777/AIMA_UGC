"""统一补采的显式选择、预览并发确认与全部来源状态验证。"""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.content_queries import PostgresContentQueryRepository
from aima_ugc.bootstrap.analysis_identity import active_analysis_configuration
from aima_ugc.bootstrap.collection_http import PostgresCollectionHttpService
from aima_ugc.contracts.http import CollectionRunCreateRequest, CollectionSupplementPreviewRequest
from aima_ugc.modules.collection.http import (
    CollectionConflict,
    CollectionResourceNotFound,
    CollectionSupplementTargetsChanged,
)
from aima_ugc.modules.collection.tables import collection_runs_table, collection_scopes_table
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.platform.jobs.tables import jobs_table
from sqlalchemy import func, select, update

from tests.integration.collection.test_collection_date_supplement import FROM, TO
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


def seed(runtime):  # type: ignore[no-untyped-def]
    """正式来源分别覆盖有原生 ID、不相关、身份缺口和未选择对照。"""
    config_id, _ = _seed_config_and_search_pack(runtime)
    _, job_id, attempt_id, artifact_id = _seed_batch(runtime)
    ids = []
    for i, (lookup, irrelevant) in enumerate(
        ((True, False), (True, True), (False, False), (True, False))
    ):
        ids.append(
            _insert_content(
                runtime,
                attempt_id=attempt_id,
                artifact_id=artifact_id,
                external_content_id=f"selected-{i}" if lookup else "url_sha256:selected-blocked",
                lookup_id=lookup,
                job_id=job_id,
                irrelevant=irrelevant,
            )
        )
    with runtime.database.engine.begin() as connection:
        connection.execute(
            update(contents_table).where(contents_table.c.id.in_(ids)).values(published_at=FROM)
        )
    return config_id, ids, PostgresCollectionHttpService(runtime, cursor_signing_secret=b"r" * 32)


def counts(runtime):  # type: ignore[no-untyped-def]
    with runtime.database.engine.begin() as connection:
        return tuple(
            connection.scalar(select(func.count()).select_from(table))
            for table in (
                jobs_table,
                collection_runs_table,
                collection_scopes_table,
            )
        )


def test_selected_preserves_irrelevant_and_blocked_without_unselected_scopes(runtime):  # type: ignore[no-untyped-def]
    config, ids, service = seed(runtime)
    targets = {"kind": "selected", "content_ids": [ids[2], ids[0], ids[1], ids[0]]}
    preview = service.preview_supplement(CollectionSupplementPreviewRequest(targets=targets))
    reordered = service.preview_supplement(
        CollectionSupplementPreviewRequest(
            targets={"kind": "selected", "content_ids": [ids[1], ids[0], ids[2]]},
        )
    )
    assert preview.target_count == 3 and preview.target_fingerprint == reordered.target_fingerprint
    assert preview.platforms[0].content_count == 3
    assert preview.platforms[0].direct_target_count == 2
    assert preview.platforms[0].blocked_count == 1
    created = service.create_run(
        CollectionRunCreateRequest(
            mode="content_supplement",
            supplement_targets=targets,
            expected_target_count=3,
            expected_target_fingerprint=preview.target_fingerprint,
            platforms=({"platform": "xiaohongshu", "provider_config_id": config},),
        ),
        request_id="selected-explicit",
    )
    with runtime.database.new_session() as session:
        scopes = (
            session.execute(
                select(collection_scopes_table).where(
                    collection_scopes_table.c.run_id == created.run_id
                )
            )
            .mappings()
            .all()
        )
        assert {scope["source_value"] for scope in scopes} == {str(value) for value in ids[:3]}
        assert all(
            scope["source_type"] == "content" and scope["operation_group"] == "content_enrichment"
            for scope in scopes
        )
        run = (
            session.execute(
                select(collection_runs_table).where(collection_runs_table.c.id == created.run_id)
            )
            .mappings()
            .one()
        )
        snapshot = run["config_snapshot"]["supplement_selection"]
        assert snapshot["kind"] == "selected" and snapshot["target_count"] == 3
        assert "content_ids" not in snapshot and run["import_batch_id"] is None
        reader = PostgresContentQueryRepository(
            session,
            analysis_identity=active_analysis_configuration(session, runtime.settings).identity,
        )
        assert reader.latest_supplement_status(ids[0]).run_id == created.run_id
        assert reader.latest_supplement_status(ids[3]) is None
    assert service.get_run(created.run_id).supplement_selection.kind == "selected"


def test_missing_selected_and_omitted_platforms_cannot_silently_skip(runtime):  # type: ignore[no-untyped-def]
    config, ids, service = seed(runtime)
    before = counts(runtime)
    with pytest.raises(CollectionResourceNotFound):
        service.preview_supplement(
            CollectionSupplementPreviewRequest(
                targets={"kind": "selected", "content_ids": [ids[0], uuid4()]}
            )
        )
    with runtime.database.engine.begin() as connection:
        connection.execute(
            update(contents_table).where(contents_table.c.id == ids[1]).values(platform="douyin")
        )
    targets = {"kind": "selected", "content_ids": ids[:2]}
    preview = service.preview_supplement(CollectionSupplementPreviewRequest(targets=targets))
    with pytest.raises(CollectionConflict):
        service.create_run(
            CollectionRunCreateRequest(
                mode="content_supplement",
                supplement_targets=targets,
                expected_target_count=2,
                expected_target_fingerprint=preview.target_fingerprint,
                platforms=({"platform": "xiaohongshu", "provider_config_id": config},),
            ),
            request_id="omitted-platform",
        )
    assert counts(runtime) == before


def test_same_count_date_membership_change_and_options_change_reject_atomically(runtime):  # type: ignore[no-untyped-def]
    config, ids, service = seed(runtime)
    targets = {"kind": "published_date_range", "published_from": FROM, "published_to": TO}
    with runtime.database.engine.begin() as connection:
        connection.execute(
            update(contents_table)
            .where(contents_table.c.id == ids[3])
            .values(published_at=FROM - timedelta(days=1))
        )
    preview = service.preview_supplement(
        CollectionSupplementPreviewRequest(targets=targets, platforms=("xiaohongshu",))
    )
    before = counts(runtime)
    request = CollectionRunCreateRequest(
        mode="content_supplement",
        supplement_targets=targets,
        expected_target_count=preview.target_count,
        expected_target_fingerprint=preview.target_fingerprint,
        platforms=({"platform": "xiaohongshu", "provider_config_id": config},),
    )
    with pytest.raises(CollectionSupplementTargetsChanged):
        service.create_run(
            request.model_copy(update={"include_sub_comments": True}), request_id="changed-options"
        )
    with runtime.database.engine.begin() as connection:
        connection.execute(
            update(contents_table)
            .where(contents_table.c.id == ids[0])
            .values(published_at=FROM - timedelta(days=1))
        )
        connection.execute(
            update(contents_table).where(contents_table.c.id == ids[3]).values(published_at=FROM)
        )
    current = service.preview_supplement(
        CollectionSupplementPreviewRequest(targets=targets, platforms=("xiaohongshu",))
    )
    assert current.target_count == preview.target_count
    assert current.target_fingerprint != preview.target_fingerprint
    with pytest.raises(CollectionSupplementTargetsChanged):
        service.create_run(request, request_id="same-count-changed-members")
    assert counts(runtime) == before
