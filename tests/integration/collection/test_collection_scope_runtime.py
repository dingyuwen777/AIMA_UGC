"""Stage 7 concrete Collection Scope Runtime 的 PostgreSQL/Fake Transport 纵切。"""

from __future__ import annotations

import json
from collections.abc import Iterator
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataGateway,
    PostgresArtifactMetadataRepository,
)
from aima_ugc.adapters.persistence.postgres.collection import PostgresCollectionRepository
from aima_ugc.adapters.persistence.postgres.collection_run_execution import (
    PostgresCollectionRunExecutionGateway,
)
from aima_ugc.adapters.persistence.postgres.content_complete import (
    PostgresCompleteContentRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
from aima_ugc.adapters.providers.fake import FakeProviderTransport
from aima_ugc.adapters.storage.local import LocalArtifactStore
from aima_ugc.bootstrap.collection_scope import TikHubCollectionScopeExecutor
from aima_ugc.contracts.canonical import CanonicalContentV1
from aima_ugc.modules.collection.collection_run_executor import CollectionRunExecutor
from aima_ugc.modules.collection.execution import (
    CollectionExecutionService,
    CollectionScopeDefinition,
)
from aima_ugc.modules.collection.providers import ProviderTransportResponse, RawArtifactService
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.extended_tables import content_media_table
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.modules.vehicles.tables import content_brand_evidence_table
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.storage import (
    ArtifactService,
    CanonicalArtifactParent,
    CanonicalArtifactReader,
)
from aima_ugc.platform.storage.tables import artifacts_table, canonical_artifact_links_table
from pydantic import SecretStr
from sqlalchemy import func, select

from tests.integration.content.test_content_audit_regressions import _source
from tests.integration.stage3_brand_support import stage4_collection_config_snapshot

_FIXTURES = Path("tests/fixtures/providers/tikhub/xiaohongshu")
_OBSERVED_AT = datetime(2026, 8, 17, 4, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("entrypoint", "failure_status", "legacy_chunk"),
    [
        (entry, status, False)
        for entry in ("prefetch", "late_detail", "enrichment")
        for status in (403, 503)
    ]
    + [("prefetch", 503, True), ("filtered", 403, False)]
    + [(entry, 200, False) for entry in ("prefetch", "late_detail", "enrichment")],
)
def test_optional_video_failure_preserves_successful_primary_and_real_failure_audit(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
    entrypoint: str,
    failure_status: int,
    legacy_chunk: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """三个正式消费者先保存封面；503恢复复用成功Raw，只重试失败视频请求。"""
    note_id = "a00000000000000000000001"
    search = _search_response()
    search_note = search["data"]["data"]["items"][0]["note"]
    search_note.update(id=note_id, type="future_note")
    search["data"]["data"]["items"] = [search["data"]["data"]["items"][0]]
    primary = _fixture("video_cover_detail_20261009.sanitized.json")
    primary["data"]["data"][0].update(title="爱玛脱敏成功详情", desc="已成功正文", comments_count=0)
    secondary = _fixture("video_detail_20261009.sanitized.json")
    for key in ("title", "desc", "comments_count"):
        secondary["data"]["data"][0].pop(key, None)
    snapshot = stage4_collection_config_snapshot(
        database_runtime,
        alias="独立品牌"
        if entrypoint == "filtered"
        else "爱玛"
        if entrypoint == "prefetch"
        else "脱敏",
    )
    if entrypoint == "enrichment":
        snapshot["brand_vehicle_filter"]["search_semantics"] = "not_applicable"
    target_id = None
    if entrypoint == "enrichment":
        source = _source(database_runtime, observed_at=_OBSERVED_AT, suffix="legacy-note-seed")
        with database_runtime.new_session() as session, session.begin():
            target_id = (
                PostgresCompleteContentRepository(session)
                .ingest_content(
                    CanonicalContentV1(
                        platform="xiaohongshu",
                        external_content_id=note_id,
                        content_type="note",
                        title="脱敏旧正文",
                        source=source,
                        observed_at=_OBSERVED_AT,
                        observed_fields=["content_type", "title"],
                    )
                )
                .target_id
            )
    with database_runtime.new_session() as session, session.begin():
        provider = PostgresProviderConfigRepository(session).create(
            ProviderConfig(
                id=uuid4(),
                provider="tikhub",
                display_name="媒体失败恢复",
                base_url="https://api.tikhub.io",
                secret_ref="fixture/media",
                enabled=True,
            )
        )
        job = PostgresJobRepository(session).enqueue(
            job_type="collection.run.v1",
            payload_version="collection.run.v1",
            payload={"schema_version": "collection.run.v1"},
            internal_idempotency_key=f"media-failure:{uuid4()}",
            request_id=None,
            priority=50,
            max_attempts=2,
            timeout_seconds=300,
        )
        execution = CollectionExecutionService(PostgresCollectionRepository(session)).create_run(
            job_id=job.id,
            trigger_type="api",
            config_snapshot={
                **snapshot,
                "mode": "content_supplement" if target_id else "discovery",
                "include_comments": False,
                "decision_policy": {"comments_enabled": False, "comment_mode": "adaptive"},
                "platforms": [
                    {
                        "platform": "xiaohongshu",
                        "provider_config_id": str(provider.id),
                        "config": {
                            "sort_mode": "latest",
                            "published_within": "1d",
                            "content_type": "all",
                        },
                    }
                ],
            },
            scopes=(
                CollectionScopeDefinition(
                    platform="xiaohongshu",
                    source_type="content" if target_id else "keyword_search",
                    source_value=str(target_id) if target_id else "爱玛",
                    operation_group="content_enrichment" if target_id else "content_discovery",
                ),
            ),
        )
    with database_runtime.new_session() as session, session.begin():
        claimed = PostgresJobRepository(session).claim_next(
            supported_job_types=("collection.run.v1",),
            worker_id="media-failure-worker",
            lease_seconds=120,
        )
    assert claimed is not None and claimed.id == job.id and claimed.lease_token is not None
    fence = JobExecutionFence(job_id=job.id, lease_token=claimed.lease_token)
    transport = FakeProviderTransport(
        (
            *(() if target_id else (ProviderTransportResponse(status_code=200, body=search),)),
            ProviderTransportResponse(status_code=200, body=primary),
            ProviderTransportResponse(
                status_code=failure_status,
                body={"data": {"data": []}} if failure_status == 200 else {"code": failure_status},
            ),
        )
    )
    store = LocalArtifactStore(tmp_path / "artifacts")
    artifacts = ArtifactService(
        metadata=PostgresArtifactMetadataGateway(database_runtime.new_session), store=store
    )
    errors = []
    historical_artifact = []
    monkeypatch.setattr(
        "aima_ugc.bootstrap.collection_scope._log_scope_execution_failed",
        lambda **kwargs: errors.append(kwargs["error"]),
    )

    def run(fake):
        executor = TikHubCollectionScopeExecutor(
            session_factory=database_runtime.new_session,
            raw_artifacts=_raw_service(database_runtime, tmp_path / "artifacts"),
            artifacts=artifacts,
            artifact_store=store,
            transport_factory=lambda _: fake,
            secret_resolver=lambda _: SecretStr("fixture-secret"),
        )
        if legacy_chunk:
            validate = executor._persistent_filter_inputs

            def legacy_search_chunk(**kwargs):
                if (
                    kwargs.get("legacy_alternatives")
                    and executor._canonical_for_attempt(kwargs["provider_attempt_id"]) is None
                ):
                    # 旧 Writer 的真实形状：Search父事实下保存primary Detail，追加一次后永不改写。
                    import gzip
                    from io import BytesIO

                    rows = tuple(
                        executor._legacy_canonical_by_source[
                            alternatives[1].source.model_dump_json()
                        ]
                        for alternatives in kwargs["legacy_alternatives"]
                    )
                    wires = []
                    for row in rows:
                        wire = row.model_dump(mode="json")
                        wire.pop("media_collection_mode")
                        for media_item in wire["media"]:
                            media_item.pop("observed_fields")
                        wires.append(json.dumps(wire, ensure_ascii=False) + "\n")
                    artifact = artifacts.store_stream(
                        kind="canonical-content.v1",
                        content_type="application/x-ndjson",
                        retention_class="canonical",
                        source=BytesIO(gzip.compress("".join(wires).encode(), mtime=0)),
                        max_bytes=1024 * 1024,
                        filename_suffix=".jsonl.gz",
                        encoding="gzip",
                    )
                    historical_artifact.append(
                        artifacts.link_canonical(
                            artifact.id,
                            parent=CanonicalArtifactParent(
                                provider_attempt_id=kwargs["provider_attempt_id"]
                            ),
                        )
                    )
                return validate(**kwargs)

            executor._persistent_filter_inputs = legacy_search_chunk
        return CollectionRunExecutor(
            gateway=PostgresCollectionRunExecutionGateway(database_runtime.new_session),
            scope_executor=executor,
        ).execute(fence=fence, context=_Context(fence))

    result = run(transport)
    assert not errors
    assert result.outcome == (
        "succeeded" if entrypoint == "filtered" else "retry" if failure_status == 503 else "failed"
    )
    if entrypoint == "filtered":
        with database_runtime.new_session() as session, session.begin():
            assert session.scalar(select(func.count()).select_from(contents_table)) == 0
            scope = (
                session.execute(
                    select(collection_scopes_table).where(
                        collection_scopes_table.c.id == execution.scopes[0].id
                    )
                )
                .mappings()
                .one()
            )
            assert scope["status"] == "partial_success" and scope["stats"]["failed_count"] == 1
            assert scope["stats"]["filtered_content_count"] == 1
            assert (
                session.scalar(
                    select(collection_runs_table.c.status).where(
                        collection_runs_table.c.id == execution.run.id
                    )
                )
                == "partial_success"
            )
        return
    with database_runtime.new_session() as session, session.begin():
        current = (
            session.execute(
                select(contents_table).where(contents_table.c.external_content_id == note_id)
            )
            .mappings()
            .one()
        )
        media = (
            session.execute(
                select(content_media_table).where(content_media_table.c.content_id == current["id"])
            )
            .mappings()
            .one()
        )
        assert current["content_type"] == "video"
        assert current["title"] == "爱玛脱敏成功详情"
        assert media["preview_url"].endswith("fixture-26.webp") and media["url"] is None
        failed = (
            session.execute(
                select(provider_request_attempts_table)
                .join(
                    provider_requests_table,
                    provider_requests_table.c.id
                    == provider_request_attempts_table.c.provider_request_id,
                )
                .where(
                    provider_requests_table.c.scope_id == execution.scopes[0].id,
                    provider_requests_table.c.operation == "get_video_note_detail",
                )
            )
            .mappings()
            .one()
        )
        assert failed["dispatch_status"] == "completed" and failed["http_status"] == failure_status
        assert failed["raw_artifact_id"] is not None
        scope = (
            session.execute(
                select(collection_scopes_table).where(
                    collection_scopes_table.c.id == execution.scopes[0].id
                )
            )
            .mappings()
            .one()
        )
        assert scope["stats"]["content_count"] == 1
        assert scope["stats"]["failed_count"] == (0 if failure_status == 200 else 1)
        if failure_status == 200:
            assert scope["stats"]["technical_partial_results"] == 1
            assert scope["stop_reason"] == "detail_response_empty"
        assert scope["status"] == ("running" if failure_status == 503 else "failed")
        assert (
            session.scalar(
                select(collection_runs_table.c.status).where(
                    collection_runs_table.c.id == execution.run.id
                )
            )
            != "succeeded"
        )
    if failure_status == 503:
        resumed = FakeProviderTransport(
            (ProviderTransportResponse(status_code=200, body=secondary),)
        )
        assert run(resumed).outcome == "succeeded"
        assert resumed.call_count == 1
        assert resumed.seen_requests[0].path.endswith("get_video_note_detail")
        with database_runtime.new_session() as session, session.begin():
            media = (
                session.execute(
                    select(content_media_table).where(
                        content_media_table.c.content_id == current["id"]
                    )
                )
                .mappings()
                .one()
            )
            assert media["preview_url"] is not None and media["url"].endswith("fixture-13.mp4")
            row = (
                session.execute(select(contents_table).where(contents_table.c.id == current["id"]))
                .mappings()
                .one()
            )
            assert row["title"] == current["title"] and row["text"] == current["text"]
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(content_brand_evidence_table)
                    .where(
                        content_brand_evidence_table.c.content_id == current["id"],
                        content_brand_evidence_table.c.content_version == row["current_version"],
                        content_brand_evidence_table.c.is_active.is_(True),
                    )
                )
                > 0
            )
        if legacy_chunk:
            assert len(historical_artifact) == 1
            frozen_rows = tuple(CanonicalArtifactReader(store=store).read(historical_artifact[0]))
            assert frozen_rows[0].title == "爱玛脱敏成功详情"
            assert frozen_rows[0].media[0].media_type == "image"
            assert str(frozen_rows[0].media[0].url).endswith("fixture-26.webp")


@dataclass
class _Context:
    fence: JobExecutionFence

    def heartbeat(self, *, progress: int) -> None:
        assert 0 <= progress <= 100

    def cancel_requested(self) -> bool:
        return False


@pytest.fixture
def database_runtime() -> Iterator[DatabaseRuntime]:
    runtime = DatabaseRuntime(load_settings())
    with runtime.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE jobs, artifacts, accounts, vehicle_brands RESTART IDENTITY CASCADE"
        )
    try:
        yield runtime
    finally:
        with runtime.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE jobs, artifacts, accounts, vehicle_brands RESTART IDENTITY CASCADE"
            )
        runtime.dispose()


def _fixture(name: str) -> dict[str, object]:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _search_response() -> dict[str, object]:
    body = _fixture("search_notes_page1.sanitized.json")
    provider = body["data"]
    assert isinstance(provider, dict)
    page = provider["data"]
    assert isinstance(page, dict)
    items = page["items"]
    assert isinstance(items, list) and items
    first = items[0]
    assert isinstance(first, dict)
    note = first["note"]
    assert isinstance(note, dict)
    note["comments_count"] = 0
    page["items"] = [first, deepcopy(first)]
    page["has_more"] = False
    return body


def _detail_response() -> dict[str, object]:
    body = _fixture("image_detail.sanitized.json")
    outer = body["data"]
    assert isinstance(outer, dict)
    rows = outer["data"]
    assert isinstance(rows, list) and rows
    wrapper = rows[0]
    assert isinstance(wrapper, dict)
    notes = wrapper["note_list"]
    assert isinstance(notes, list) and notes
    note = notes[0]
    assert isinstance(note, dict)
    note["id"] = "note-fixture-1"
    note["comments_count"] = 0
    return body


def _raw_service(runtime: DatabaseRuntime, root: Path) -> RawArtifactService:
    store = LocalArtifactStore(root)
    return RawArtifactService(
        artifacts=ArtifactService(
            metadata=PostgresArtifactMetadataGateway(runtime.new_session),
            store=store,
        ),
        store=store,
    )


@pytest.mark.parametrize("filter_alias", ("脱敏", "图文"))
def test_scope_runtime_persists_each_raw_canonical_before_filter(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
    filter_alias: str,
) -> None:
    session = database_runtime.new_session()
    try:
        with session.begin():
            provider_config = PostgresProviderConfigRepository(session).create(
                ProviderConfig(
                    id=uuid4(),
                    provider="tikhub",
                    display_name="TikHub Scope Runtime",
                    base_url="https://api.tikhub.io",
                    secret_ref="providers/tikhub/test/scope-runtime",
                    enabled=True,
                )
            )
            job = PostgresJobRepository(session).enqueue(
                job_type="collection.run.v1",
                payload_version="collection.run.v1",
                payload={"schema_version": "collection.run.v1"},
                internal_idempotency_key=f"scope-runtime:{uuid4()}",
                request_id=None,
                priority=10,
                max_attempts=2,
                timeout_seconds=300,
            )
            CollectionExecutionService(PostgresCollectionRepository(session)).create_run(
                job_id=job.id,
                trigger_type="api",
                config_snapshot={
                    "schema_version": "collection-run-config.v4",
                    "plan_type": "tikhub",
                    "decision_policy": {"comment_mode": "adaptive"},
                    **stage4_collection_config_snapshot(database_runtime, alias=filter_alias),
                    "detail_policy": "on_change",
                    "comment_policy": "adaptive",
                    "platforms": [
                        {
                            "platform": "xiaohongshu",
                            "provider_config_id": str(provider_config.id),
                            "config": {
                                "sort_mode": "latest",
                                "published_within": "1d",
                                "content_type": "all",
                            },
                        }
                    ],
                },
                scopes=(
                    CollectionScopeDefinition(
                        platform="xiaohongshu",
                        source_type="keyword_search",
                        source_value="爱玛",
                        operation_group="content_discovery",
                    ),
                ),
            )
        with session.begin():
            claimed = PostgresJobRepository(session).claim_next(
                supported_job_types=("collection.run.v1",),
                worker_id="scope-runtime-worker",
                lease_seconds=120,
            )
        assert claimed is not None and claimed.lease_token is not None
    finally:
        session.close()

    transport = FakeProviderTransport(
        (
            ProviderTransportResponse(status_code=200, body=_search_response()),
            ProviderTransportResponse(status_code=200, body=_detail_response()),
        )
    )
    fence = JobExecutionFence(job_id=job.id, lease_token=claimed.lease_token)
    scope_executor = TikHubCollectionScopeExecutor(
        session_factory=database_runtime.new_session,
        raw_artifacts=_raw_service(database_runtime, tmp_path / "artifacts"),
        artifacts=ArtifactService(
            metadata=PostgresArtifactMetadataGateway(database_runtime.new_session),
            store=LocalArtifactStore(tmp_path / "artifacts"),
        ),
        artifact_store=LocalArtifactStore(tmp_path / "artifacts"),
        transport_factory=lambda _config: transport,
        secret_resolver=lambda secret_ref: (
            SecretStr("fixture-secret")
            if secret_ref == provider_config.secret_ref
            else (_ for _ in ()).throw(AssertionError("unexpected secret_ref"))
        ),
        observed_at=lambda: _OBSERVED_AT,
    )
    result = CollectionRunExecutor(
        gateway=PostgresCollectionRunExecutionGateway(database_runtime.new_session),
        scope_executor=scope_executor,
    ).execute(fence=fence, context=_Context(fence))

    assert result.outcome == "succeeded"
    assert transport.call_count == 2
    assert [request.path for request in transport.seen_requests] == [
        "/api/v1/xiaohongshu/app_v2/search_notes",
        "/api/v1/xiaohongshu/app_v2/get_image_note_detail",
    ]
    assert all(request.credential is None for request in transport.seen_requests)

    session = database_runtime.new_session()
    try:
        with session.begin():
            assert session.scalar(select(func.count()).select_from(provider_requests_table)) == 2
            assert (
                session.scalar(select(func.count()).select_from(provider_request_attempts_table))
                == 2
            )
            assert session.scalar(select(func.count()).select_from(artifacts_table)) == 4
            assert (
                session.scalar(select(func.count()).select_from(canonical_artifact_links_table))
                == 2
            )
            search_attempt_id = session.scalar(
                select(provider_request_attempts_table.c.id)
                .join(
                    provider_requests_table,
                    provider_requests_table.c.id
                    == provider_request_attempts_table.c.provider_request_id,
                )
                .where(provider_requests_table.c.operation == "search_notes")
            )
            assert search_attempt_id is not None
            canonical_artifact = PostgresArtifactMetadataRepository(
                session
            ).get_canonical_for_parent(
                CanonicalArtifactParent(provider_attempt_id=search_attempt_id)
            )
            assert canonical_artifact is not None
            content = session.execute(select(contents_table)).mappings().one()
        canonical_rows = tuple(
            CanonicalArtifactReader(store=LocalArtifactStore(tmp_path / "artifacts")).read(
                canonical_artifact
            )
        )
        assert len(canonical_rows) == 2
        assert all(row.external_content_id == "note-fixture-1" for row in canonical_rows)
        assert all(row.title == "脱敏标题 A" for row in canonical_rows)
        assert all(
            row.source.provider_attempt_id == str(search_attempt_id) for row in canonical_rows
        )
        with session.begin():
            detail_attempt_id = session.scalar(
                select(provider_request_attempts_table.c.id)
                .join(
                    provider_requests_table,
                    provider_requests_table.c.id
                    == provider_request_attempts_table.c.provider_request_id,
                )
                .where(provider_requests_table.c.operation == "get_image_note_detail")
            )
            detail_artifact = PostgresArtifactMetadataRepository(session).get_canonical_for_parent(
                CanonicalArtifactParent(provider_attempt_id=detail_attempt_id)
            )
        assert detail_artifact is not None
        detail_rows = tuple(
            CanonicalArtifactReader(store=LocalArtifactStore(tmp_path / "artifacts")).read(
                detail_artifact
            )
        )
        assert len(detail_rows) == 1 and detail_rows[0].title == "脱敏图文标题"
        assert detail_rows[0].source.provider_attempt_id == str(detail_attempt_id)
        assert content["platform"] == "xiaohongshu"
        assert content["external_content_id"] == "note-fixture-1"
        assert content["title"] == "脱敏图文标题"
        assert content["current_comment_count"] == 0
    finally:
        session.close()
