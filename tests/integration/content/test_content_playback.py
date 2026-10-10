"""真实 PostgreSQL 播放准备、收费审计、来源 CAS 与业务版本隔离。"""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from threading import Event
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.artifact_metadata import PostgresArtifactMetadataGateway
from aima_ugc.adapters.persistence.postgres.collection import PostgresCollectionRepository
from aima_ugc.adapters.persistence.postgres.collection_run_execution import (
    PostgresCollectionRunExecutionGateway,
)
from aima_ugc.adapters.persistence.postgres.content_complete import (
    PostgresCompleteContentRepository,
)
from aima_ugc.adapters.persistence.postgres.content_playback import (
    PostgresContentPlaybackRepository,
)
from aima_ugc.adapters.persistence.postgres.content_queries import PostgresContentQueryRepository
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
from aima_ugc.adapters.providers.fake import FakeProviderTransport
from aima_ugc.adapters.providers.tikhub.operations.xiaohongshu import build_video_detail_request
from aima_ugc.adapters.providers.tikhub.runtime import TikHubOperationCall
from aima_ugc.adapters.storage.local import LocalArtifactStore
from aima_ugc.bootstrap.collection_scope import TikHubCollectionScopeExecutor
from aima_ugc.bootstrap.content_playback_service import PostgresContentPlaybackHttpService
from aima_ugc.bootstrap.worker import collection_job_terminal_callback
from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalMediaV1
from aima_ugc.contracts.content_playback import ContentMediaPlaybackPrepareRequest
from aima_ugc.modules.collection.collection_run_executor import CollectionRunExecutor
from aima_ugc.modules.collection.collection_run_job import (
    CollectionRunJobHandler,
    register_collection_run_job,
)
from aima_ugc.modules.collection.providers import ProviderTransportResponse
from aima_ugc.modules.collection.providers.transport import ProviderTransportFailure
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.content_cursor import InvalidContentCursor
from aima_ugc.modules.content.contribution_tables import content_source_contributions_table
from aima_ugc.modules.content.extended_tables import content_media_table
from aima_ugc.modules.content.http import ContentResourceNotFound
from aima_ugc.modules.content.media_playback import (
    ContentPlaybackSessionCodec,
    media_source_revision,
)
from aima_ugc.modules.content.media_playback_tables import (
    content_media_playback_states_table as states,
)
from aima_ugc.modules.content.tables import content_versions_table, contents_table
from aima_ugc.modules.identity import Principal
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.modules.system.tables import provider_configs_table
from aima_ugc.platform.jobs import JobExecutionFence, JobReaper, JobRegistry, JobWorker
from aima_ugc.platform.jobs.models import LeaseLostError
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.storage import ArtifactService
from aima_ugc.platform.storage.tables import artifacts_table
from aima_ugc.platform.time import beijing_now
from pydantic import SecretStr
from sqlalchemy import delete, func, select, update

from tests.integration.collection.test_collection_scope_runtime import (
    _Context,
    _fixture,
    _raw_service,
)
from tests.integration.content.test_content_audit_regressions import _source
from tests.integration.content.test_content_audit_regressions import (
    database_runtime as database_runtime,
)

VIEWER = Principal("viewer", "测试查看者", "administrator", "development")
NOTE_ID = "a00000000000000000000001"


def _seed(runtime, *, legacy=False, with_url=True, external_media_id=None):
    now = beijing_now() - timedelta(seconds=30)
    original = _source(runtime, observed_at=now, suffix="playback-original")
    observation = CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id=NOTE_ID,
        content_type="video",
        title="已入库正文",
        observed_at=now,
        source=original,
        observed_fields=["title", "content_type", "media"],
        media_collection_mode="partial",
        media=[
            CanonicalMediaV1(
                media_type="video",
                external_media_id=external_media_id,
                url="https://sns-v11.rednotecdn.com/original" if with_url else None,
                preview_url="https://sns-i11.rednotecdn.com/cover",
                duration_ms=17800,
                observed_fields=[
                    "media_type",
                    "external_media_id",
                    "url",
                    "preview_url",
                    "duration_ms",
                ],
            )
        ],
    )
    with runtime.new_session() as session, session.begin():
        content_id = (
            PostgresCompleteContentRepository(session).ingest_content(observation).target_id
        )
        if legacy:
            session.execute(update(content_media_table).values(observation_metadata={}))
        # 当前 fixture 保留配置表；冻结的 Provider 与直接准备 Raw 的测试必须是同一配置。
        session.execute(update(provider_configs_table).values(enabled=False))
        provider = PostgresProviderConfigRepository(session).create(
            ProviderConfig(
                id=uuid4(),
                provider="tikhub",
                display_name="播放测试",
                base_url="https://api.tikhub.io",
                secret_ref="fixture/media",
                enabled=True,
                max_retries=3,
            )
        )
        owner = PostgresContentPlaybackRepository(session)
        source = owner.get_source(content_id, 0, lock=True)
        assert source is not None
        if with_url:
            owner.record_stream_failure(source, code="cdn_forbidden", now=beijing_now())
    service = PostgresContentPlaybackHttpService(
        SimpleNamespace(database=runtime),
        session_codec=ContentPlaybackSessionCodec(secret=b"media-test-signing-secret-32-bytes"),
    )
    return SimpleNamespace(
        content_id=content_id,
        source=source,
        observation=observation,
        provider=provider,
        service=service,
    )


def _prepare(seed):
    return seed.service.prepare(
        seed.content_id,
        0,
        ContentMediaPlaybackPrepareRequest(failed_source_revision=seed.source.source_revision),
        principal=VIEWER,
        request_id="playback-test",
    )


def _claim(runtime, job_id):
    with runtime.new_session() as session, session.begin():
        session.execute(update(jobs_table).where(jobs_table.c.id == job_id).values(priority=50))
        job = PostgresJobRepository(session).claim_next(
            supported_job_types=("collection.run.v1",),
            worker_id="media-test",
            lease_seconds=120,
            minimum_priority=50,
        )
        assert job is not None and job.id == job_id and job.lease_token is not None
    return JobExecutionFence(job.id, job.lease_token)


def _executor(runtime, tmp_path, transport):
    store = LocalArtifactStore(tmp_path / "artifacts")
    return TikHubCollectionScopeExecutor(
        session_factory=runtime.new_session,
        raw_artifacts=_raw_service(runtime, tmp_path / "artifacts"),
        artifacts=ArtifactService(
            metadata=PostgresArtifactMetadataGateway(runtime.new_session), store=store
        ),
        artifact_store=store,
        transport_factory=lambda _: transport,
        secret_resolver=lambda _: SecretStr("fixture-secret"),
    )


def _start(runtime, fence):
    with runtime.new_session() as session, session.begin():
        repository = PostgresCollectionRepository(session)
        run = repository.get_run_by_job_id(fence.job_id)
        assert run is not None
        return repository.start_run(run.id), repository.start_scope(
            repository.list_scopes(run.id)[0].id
        )


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("normal_update", [None, "preview_url", "url", "media_type"])
def test_refresh_cas_preserves_normal_ingestion_and_business_version(
    database_runtime, tmp_path, legacy, normal_update
):
    seed = _seed(database_runtime, legacy=legacy)
    prepared = _prepare(seed)
    assert prepared.status == "preparing"
    fence = _claim(database_runtime, prepared.job_id)
    run, scope = _start(database_runtime, fence)
    transport = FakeProviderTransport(
        (
            ProviderTransportResponse(
                status_code=200, body=_fixture("video_detail_20261009.sanitized.json")
            ),
        )
    )
    executor = _executor(database_runtime, tmp_path, transport)
    request = build_video_detail_request(note_id=NOTE_ID)
    executed = executor._execute_call(
        run=run,
        scope=scope,
        call=TikHubOperationCall(
            "xiaohongshu",
            "content_detail",
            "get_video_note_detail",
            "GET",
            request.path,
            dict(request.params),
        ),
        provider_config=seed.provider,
        context=_Context(fence),
    )
    if normal_update is not None:
        later = _source(database_runtime, observed_at=beijing_now(), suffix="playback-later")
        values = {
            normal_update: "image"
            if normal_update == "media_type"
            else "https://sns-v27.rednotecdn.com/new"
            if normal_update == "url"
            else "https://sns-i11.rednotecdn.com/new-cover"
        }
        if normal_update != "media_type":
            values["media_type"] = "video"
        with database_runtime.new_session() as session, session.begin():
            PostgresCompleteContentRepository(session).ingest_content(
                seed.observation.model_copy(
                    update={
                        "source": later,
                        "observed_at": later.observed_at,
                        "media": [CanonicalMediaV1(observed_fields=[normal_update], **values)],
                    }
                )
            )
    with database_runtime.new_session() as session, session.begin():
        tables = (contents_table, content_versions_table, content_source_contributions_table)
        before = [
            tuple(dict(row) for row in session.execute(select(table)).mappings())
            for table in tables
        ]
        applied = PostgresContentPlaybackRepository(session).publish_refresh(
            fence=fence,
            content_id=seed.content_id,
            position=0,
            identity_token=seed.source.identity_token,
            expected_source_revision=seed.source.source_revision,
            generation=1,
            url="http://sns-v11.rednotecdn.com/refreshed",
            attempt_id=executed.attempt_id,
            raw_id=executed.raw_artifact_id,
            observed_at=executed.observed_at,
        )
        assert applied == (normal_update in {None, "preview_url"})
        assert [
            tuple(dict(row) for row in session.execute(select(table)).mappings())
            for table in tables
        ] == before
        media = session.execute(select(content_media_table)).mappings().one()
        if applied:
            assert media["url"] == "https://sns-v11.rednotecdn.com/refreshed"
            assert media["observation_metadata"]["identity_token"] == seed.source.identity_token
            assert media_source_revision(media) != seed.source.source_revision
            assert session.scalar(select(states.c.state)) == "ready"
        elif normal_update == "url":
            assert media["url"] == values["url"]


@pytest.mark.parametrize("status", [200, 403, 503, "unknown", "not_sent"])
def test_formal_refresh_scope_sends_once_and_restores_completed_raw(
    database_runtime, tmp_path, status
):
    seed = _seed(database_runtime, with_url=False)
    prepared = _prepare(seed)
    fence = _claim(database_runtime, prepared.job_id)
    run, scope = _start(database_runtime, fence)
    transport = FakeProviderTransport(
        (
            ProviderTransportFailure.unknown(code="network_unknown", safe_summary="fixture")
            if status == "unknown"
            else ProviderTransportFailure.not_sent(code="network_not_sent", safe_summary="fixture")
            if status == "not_sent"
            else ProviderTransportResponse(
                status_code=status,
                body=_fixture("video_detail_20261009.sanitized.json")
                if status == 200
                else {"code": status},
            ),
        )
    )
    executor = _executor(database_runtime, tmp_path, transport)
    with database_runtime.new_session() as session, session.begin():
        before = dict(session.execute(select(contents_table)).mappings().one())
    first = executor.execute(run=run, scope=scope, context=_Context(fence))
    assert first.status == ("succeeded" if status == 200 else "failed")
    assert first.requested_count == 1 and first.comment_count == first.content_count == 0
    second = executor.execute(run=run, scope=scope, context=_Context(fence))
    assert second.status == first.status
    assert transport.call_count == 1
    with database_runtime.new_session() as session, session.begin():
        assert (
            session.scalar(
                select(func.count())
                .select_from(provider_requests_table)
                .where(provider_requests_table.c.scope_id == scope.id)
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(provider_request_attempts_table)
                .join(
                    provider_requests_table,
                    provider_requests_table.c.id
                    == provider_request_attempts_table.c.provider_request_id,
                )
                .where(provider_requests_table.c.scope_id == scope.id)
            )
            == 1
        )
        assert dict(session.execute(select(contents_table)).mappings().one()) == before
        assert session.scalar(select(states.c.state)) == (
            "ready" if status == 200 else "unavailable"
        )
    assert _prepare(seed).status == ("ready" if status == 200 else "cooldown")


def test_concurrent_prepare_deduplicates_and_nonrefreshable_failure_never_bills(database_runtime):
    seed = _seed(database_runtime)
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: _prepare(seed), range(4)))
    assert {response.status for response in responses} == {"preparing"}
    assert len({response.job_id for response in responses}) == 1
    with database_runtime.new_session() as session, session.begin():
        assert (
            session.scalar(
                select(func.count())
                .select_from(collection_runs_table)
                .where(collection_runs_table.c.config_snapshot["mode"].astext == "media_refresh")
            )
            == 1
        )
        owner = PostgresContentPlaybackRepository(session)
        owner.settle_job(
            responses[0].job_id, code="failed", now=beijing_now() - timedelta(minutes=10)
        )
        owner.record_stream_failure(seed.source, code="unsupported_format", now=beijing_now())
    assert _prepare(seed).status == "ready"


def test_refresh_cannot_publish_another_known_video_identity(database_runtime, tmp_path):
    seed = _seed(database_runtime, with_url=False, external_media_id="original-video-id")
    prepared = _prepare(seed)
    fence = _claim(database_runtime, prepared.job_id)
    run, scope = _start(database_runtime, fence)
    transport = FakeProviderTransport(
        (
            ProviderTransportResponse(
                status_code=200, body=_fixture("video_detail_20261009.sanitized.json")
            ),
        )
    )
    result = _executor(database_runtime, tmp_path, transport).execute(
        run=run, scope=scope, context=_Context(fence)
    )
    assert result.status == "failed" and result.stop_reason == "source_changed"
    with database_runtime.new_session() as session, session.begin():
        row = session.execute(select(content_media_table)).mappings().one()
        assert row["url"] is None and row["external_media_id"] == "original-video-id"
    assert transport.call_count == 1


@pytest.mark.parametrize(
    "platform,kind,hidden",
    [
        ("xiaohongshu", "video", True),
        ("xiaohongshu", "image", False),
        ("douyin", "video", False),
        ("weibo", "video", False),
        ("bilibili", "video", False),
        ("kuaishou", "video", False),
    ],
)
def test_public_media_query_keeps_xiaohongshu_video_source_on_server(
    database_runtime, platform, kind, hidden
):
    seed = _seed(database_runtime)
    with database_runtime.new_session() as session, session.begin():
        session.execute(
            update(contents_table)
            .where(contents_table.c.id == seed.content_id)
            .values(platform=platform)
        )
        session.execute(update(content_media_table).values(media_type=kind))
        media = PostgresContentQueryRepository(session, analysis_identity=None).list_media(
            seed.content_id
        )[0]
        assert (media.url is None) == hidden
        assert media.position == 0 and media.preview_url is not None and media.duration_ms == 17800
        assert (
            session.scalar(select(content_media_table.c.url))
            == "https://sns-v11.rednotecdn.com/original"
        )


@pytest.mark.parametrize("terminal", ["cancelled", "failed"])
def test_terminal_callback_closes_queued_or_abnormal_refresh_without_sending(
    database_runtime, terminal
):
    seed = _seed(database_runtime, with_url=False)
    prepared = _prepare(seed)
    with database_runtime.new_session() as session, session.begin():
        jobs = PostgresJobRepository(session)
        if terminal == "cancelled":
            job = jobs.request_cancel(prepared.job_id)
        else:
            session.execute(
                update(jobs_table)
                .where(jobs_table.c.id == prepared.job_id)
                .values(status="failed", error_code="timeout", finished_at=beijing_now())
            )
            job = jobs.get(prepared.job_id)
        assert job is not None
        collection_job_terminal_callback(session, job)
        assert session.scalar(select(states.c.state)) == "unavailable"
        run = PostgresCollectionRepository(session).get_run_by_job_id(job.id)
        assert run is not None and run.status == terminal
        assert PostgresCollectionRepository(session).list_scopes(run.id)[0].status == terminal
    assert _prepare(seed).status == "cooldown"


def _registry(runtime, executor):
    """复用正式 Handler/Run 编排与终态回调，只替换外部 Transport。"""
    registry = JobRegistry()
    register_collection_run_job(
        registry,
        CollectionRunJobHandler(
            CollectionRunExecutor(
                gateway=PostgresCollectionRunExecutionGateway(runtime.new_session),
                scope_executor=executor,
            )
        ),
        terminal_callback=collection_job_terminal_callback,
    )
    return registry


def _playback_observation_snapshot(runtime):
    """只读观察前后比较持久事实，包含账单来源与播放状态。"""
    with runtime.new_session() as session, session.begin():
        return {
            table.name: tuple(dict(row) for row in session.execute(select(table)).mappings())
            for table in (
                jobs_table,
                collection_runs_table,
                provider_requests_table,
                provider_request_attempts_table,
                artifacts_table,
                states,
                contents_table,
                content_versions_table,
                content_source_contributions_table,
            )
        }


@pytest.mark.parametrize("status", ["queued", "running", "published"])
def test_readonly_prepare_observes_existing_active_job_without_mutation(
    database_runtime, tmp_path, status
):
    """并发观察现有排队或运行任务，不产生新状态、任务或收费事实。"""
    seed = _seed(database_runtime, with_url=False)
    prepared = _prepare(seed)
    if status != "queued":
        fence = _claim(database_runtime, prepared.job_id)
        if status == "published":
            run, scope = _start(database_runtime, fence)
            transport = FakeProviderTransport(
                (
                    ProviderTransportResponse(
                        status_code=200, body=_fixture("video_detail_20261009.sanitized.json")
                    ),
                )
            )
            assert (
                _executor(database_runtime, tmp_path, transport)
                .execute(run=run, scope=scope, context=_Context(fence))
                .status
                == "succeeded"
            )
    body = ContentMediaPlaybackPrepareRequest(observed_job_id=prepared.job_id)
    before = _playback_observation_snapshot(database_runtime)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(
                lambda _: seed.service.prepare(
                    seed.content_id, 0, body, principal=VIEWER, request_id="observe"
                ),
                range(4),
            )
        )
    assert {result.status for result in results} == {"preparing"}
    assert {result.job_id for result in results} == {prepared.job_id}
    assert _playback_observation_snapshot(database_runtime) == before


def test_readonly_prepare_and_normal_media_change_serialize_without_extra_jobs(
    database_runtime, monkeypatch
):
    """正常补采等待 Content 锁；一次观察看到完整旧事实，之后旧任务绑定安全失效。"""
    seed = _seed(database_runtime, with_url=False)
    prepared = _prepare(seed)
    later = _source(database_runtime, observed_at=beijing_now(), suffix="readonly-normal-update")
    body = ContentMediaPlaybackPrepareRequest(observed_job_id=prepared.job_id)
    locked, release, writer_started = Event(), Event(), Event()
    original = PostgresContentPlaybackRepository.get_source

    def hold_source(owner, content_id, position, *, lock=False):
        """只阻塞第一次观察的 Content 锁，正常 Writer 仍调用生产入库实现。"""
        source = original(owner, content_id, position, lock=lock)
        if lock and not locked.is_set():
            locked.set()
            assert release.wait(5)
        return source

    def update_media():
        """并发正常补采更新 URL，不能被只读观察改写或创建第二个媒体任务。"""
        with database_runtime.new_session() as session, session.begin():
            writer_started.set()
            PostgresCompleteContentRepository(session).ingest_content(
                seed.observation.model_copy(
                    update={
                        "source": later,
                        "observed_at": later.observed_at,
                        "observed_fields": ["media"],
                        "media": [
                            CanonicalMediaV1(
                                media_type="video",
                                url="https://sns-v27.rednotecdn.com/normal-concurrent",
                                observed_fields=["url"],
                            )
                        ],
                    }
                )
            )

    before = _playback_observation_snapshot(database_runtime)
    monkeypatch.setattr(PostgresContentPlaybackRepository, "get_source", hold_source)
    with ThreadPoolExecutor(max_workers=2) as pool:
        observer = pool.submit(
            seed.service.prepare,
            seed.content_id,
            0,
            body,
            principal=VIEWER,
            request_id="observe-concurrent",
        )
        try:
            assert locked.wait(5)
            writer = pool.submit(update_media)
            assert writer_started.wait(5) and not writer.done()
        finally:
            release.set()
        assert observer.result().status == "preparing"
        writer.result()
    assert (
        seed.service.prepare(
            seed.content_id, 0, body, principal=VIEWER, request_id="observe-after-change"
        ).status
        == "unavailable"
    )
    after = _playback_observation_snapshot(database_runtime)
    for name in (
        "jobs",
        "collection_runs",
        "provider_requests",
        "provider_request_attempts",
        "artifacts",
        "content_media_playback_states",
    ):
        assert after[name] == before[name]


def test_readonly_prepare_does_not_settle_abnormal_terminal_state(database_runtime):
    """终态回调尚未收敛也只返回观察结果，不借轮询写状态。"""
    seed = _seed(database_runtime, with_url=False)
    prepared = _prepare(seed)
    with database_runtime.new_session() as session, session.begin():
        session.execute(
            update(jobs_table)
            .where(jobs_table.c.id == prepared.job_id)
            .values(status="failed", error_code="timeout", finished_at=beijing_now())
        )
    before = _playback_observation_snapshot(database_runtime)
    observed = seed.service.prepare(
        seed.content_id,
        0,
        ContentMediaPlaybackPrepareRequest(observed_job_id=prepared.job_id),
        principal=VIEWER,
        request_id="observe-unsettled",
    )
    assert observed.status == "unavailable" and observed.failure_code == "timeout"
    assert _playback_observation_snapshot(database_runtime) == before


@pytest.mark.parametrize("terminal", ["succeeded", "failed", "cancelled"])
def test_readonly_prepare_observes_terminal_job_after_cooldown_without_reopening(
    database_runtime, tmp_path, monkeypatch, terminal
):
    """终态观察在冷却过期后仍只读；成功会话属于本次 Principal。"""
    seed = _seed(database_runtime, with_url=False)
    prepared = _prepare(seed)
    with database_runtime.new_session() as session, session.begin():
        session.execute(
            update(jobs_table).where(jobs_table.c.id == prepared.job_id).values(priority=50)
        )
        if terminal == "cancelled":
            job = PostgresJobRepository(session).request_cancel(prepared.job_id)
            collection_job_terminal_callback(session, job)
    transport = FakeProviderTransport(
        (
            ProviderTransportResponse(
                status_code=503 if terminal == "failed" else 200,
                body=_fixture("video_detail_20261009.sanitized.json"),
            ),
        )
    )
    if terminal != "cancelled":
        worker = JobWorker(
            session_factory=database_runtime.new_session,
            registry=_registry(database_runtime, _executor(database_runtime, tmp_path, transport)),
            worker_id="readonly-terminal",
            lease_seconds=120,
            retry_delay_seconds=0,
            minimum_priority=50,
        )
        assert worker.run_once()
    monkeypatch.setattr(
        "aima_ugc.bootstrap.content_playback_service.beijing_now",
        lambda: beijing_now() + timedelta(minutes=10),
    )
    before = _playback_observation_snapshot(database_runtime)
    other = Principal("other-observer", "其他查看者", "administrator", "development")
    body = ContentMediaPlaybackPrepareRequest(observed_job_id=prepared.job_id)
    observed = seed.service.prepare(
        seed.content_id, 0, body, principal=other, request_id="observe-terminal"
    )
    assert observed.status == ("ready" if terminal == "succeeded" else "unavailable")
    assert _playback_observation_snapshot(database_runtime) == before
    assert transport.call_count == (0 if terminal == "cancelled" else 1)
    if terminal == "succeeded":
        with database_runtime.new_session() as session, session.begin():
            source = PostgresContentPlaybackRepository(session).get_source(seed.content_id, 0)
        token = parse_qs(urlsplit(observed.stream_url).query)["session"][0]
        bindings = dict(
            content_id=seed.content_id,
            position=0,
            identity_token=source.identity_token,
            source_revision=source.source_revision,
        )
        seed.service._codec().verify(token, principal_id=other.principal_id, **bindings)
        with pytest.raises(InvalidContentCursor):
            seed.service._codec().verify(token, principal_id=VIEWER.principal_id, **bindings)


@pytest.mark.parametrize(
    "change",
    ["wrong_job", "wrong_content", "wrong_position", "url", "identity", "deleted", "invisible"],
)
def test_readonly_prepare_rejects_unbound_or_replaced_media_without_mutation(
    database_runtime, change
):
    """旧任务不能观察其他任务、已换来源/身份或不再可见的媒体。"""
    seed = _seed(database_runtime, with_url=False)
    prepared = _prepare(seed)
    with database_runtime.new_session() as session, session.begin():
        if change == "url":
            session.execute(
                update(content_media_table).values(url="https://sns-v27.rednotecdn.com/normal-new")
            )
        elif change == "identity":
            session.execute(update(content_media_table).values(media_type="image"))
        elif change == "deleted":
            session.execute(delete(content_media_table))
        elif change == "invisible":
            session.execute(update(contents_table).values(rule_filter_visible=False))
    before = _playback_observation_snapshot(database_runtime)
    result = seed.service.prepare(
        uuid4() if change == "wrong_content" else seed.content_id,
        1 if change == "wrong_position" else 0,
        ContentMediaPlaybackPrepareRequest(
            observed_job_id=uuid4() if change == "wrong_job" else prepared.job_id
        ),
        principal=VIEWER,
        request_id="observe-changed",
    )
    assert result.status == "unavailable" and result.stream_url is result.job_id is None
    assert _playback_observation_snapshot(database_runtime) == before


def test_real_playback_api_readonly_observation_is_not_import_job_lookup(database_runtime):
    """真实公开 prepare 接受只读观察并拒绝观察与付费恢复的混合意图。"""
    from aima_ugc.bootstrap.content_playback_http import install_content_playback_routes
    from aima_ugc.modules.identity import DevelopmentIdentityResolver
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    seed = _seed(database_runtime, with_url=False)
    prepared = _prepare(seed)
    app = FastAPI()
    install_content_playback_routes(
        app,
        identity_resolver=DevelopmentIdentityResolver(principal_id=VIEWER.principal_id),
        service=seed.service,
    )
    before = _playback_observation_snapshot(database_runtime)
    with TestClient(app) as client:
        path = f"/api/v1/contents/{seed.content_id}/media/0/playback/prepare"
        response = client.post(path, json={"observed_job_id": str(prepared.job_id)})
        assert response.status_code == 200
        assert response.json()["status"] == "preparing"
        assert response.headers["cache-control"] == "private, no-store"
        assert (
            client.post(
                path,
                json={
                    "observed_job_id": str(prepared.job_id),
                    "failed_source_revision": seed.source.source_revision,
                },
            ).status_code
            == 422
        )
        assert client.post(path, json={"observed_job_id": "invalid-uuid"}).status_code == 422
    assert _playback_observation_snapshot(database_runtime) == before


@pytest.mark.parametrize("detail_case", ["recommendations", "missing", "duplicate", "malformed"])
def test_real_worker_refresh_selects_unique_requested_note_from_detail_response(
    database_runtime, tmp_path, detail_case
):
    """真实 Job/Raw/Mapper 链只接受目标身份；推荐项不能使合法目标失败或代替目标。"""
    seed = _seed(database_runtime, with_url=False)
    prepared = _prepare(seed)
    body = deepcopy(_fixture("video_detail_20261009.sanitized.json"))
    target = body["data"]["data"][0]
    recommendations = [dict(target, id=f"a0000000000000000000000{number}") for number in (2, 3)]
    body["data"]["data"] = {
        "recommendations": [recommendations[0], target, recommendations[1]],
        "missing": recommendations,
        "duplicate": [target, deepcopy(target), recommendations[0]],
        "malformed": [{"unrecognized_provider_error": "temporarily_unavailable"}],
    }[detail_case]
    transport = FakeProviderTransport((ProviderTransportResponse(status_code=200, body=body),))
    with database_runtime.new_session() as session, session.begin():
        session.execute(
            update(jobs_table).where(jobs_table.c.id == prepared.job_id).values(priority=50)
        )
    worker = JobWorker(
        session_factory=database_runtime.new_session,
        registry=_registry(database_runtime, _executor(database_runtime, tmp_path, transport)),
        worker_id="media-target-detail",
        lease_seconds=120,
        retry_delay_seconds=0,
        minimum_priority=50,
    )
    assert worker.run_once()
    with database_runtime.new_session() as session, session.begin():
        job = PostgresJobRepository(session).get(prepared.job_id)
        expected = "succeeded" if detail_case == "recommendations" else "failed"
        assert job.status == expected
        run = PostgresCollectionRepository(session).get_run_by_job_id(job.id)
        assert run.status == expected and run.requested_count == 1
        assert run.content_count == run.comment_count == 0
        state = session.execute(select(states)).mappings().one()
        assert state["state"] == ("ready" if expected == "succeeded" else "unavailable")
        assert state["failure_code"] == (
            None if expected == "succeeded" else "detail_mapping_invalid"
        )
        media = session.execute(select(content_media_table)).mappings().one()
        assert (media["url"] is not None) == (expected == "succeeded")
        attempts = tuple(
            session.execute(
                select(provider_request_attempts_table)
                .join(provider_requests_table)
                .where(
                    provider_requests_table.c.scope_id.in_(
                        [
                            scope.id
                            for scope in PostgresCollectionRepository(session).list_scopes(run.id)
                        ]
                    )
                )
            ).mappings()
        )
        assert len(attempts) == 1 and attempts[0]["raw_artifact_id"] is not None
    assert transport.call_count == 1 and not worker.run_once()


@pytest.mark.parametrize("outcome", ["success", "cancelled", "failed"])
def test_real_worker_converges_media_refresh_with_one_dispatch(database_runtime, tmp_path, outcome):
    seed = _seed(database_runtime, with_url=False)
    prepared = _prepare(seed)

    class Transport(FakeProviderTransport):
        def send(self, request):
            response = super().send(request)
            if outcome == "cancelled":
                with database_runtime.new_session() as session, session.begin():
                    PostgresJobRepository(session).request_cancel(prepared.job_id)
            return response

    transport = Transport(
        (
            ProviderTransportResponse(
                status_code=503 if outcome == "failed" else 200,
                body=_fixture("video_detail_20261009.sanitized.json"),
            ),
        )
    )
    with database_runtime.new_session() as session, session.begin():
        session.execute(
            update(jobs_table).where(jobs_table.c.id == prepared.job_id).values(priority=50)
        )
    registry = _registry(database_runtime, _executor(database_runtime, tmp_path, transport))
    worker = JobWorker(
        session_factory=database_runtime.new_session,
        registry=registry,
        worker_id="media-worker",
        lease_seconds=120,
        retry_delay_seconds=0,
        minimum_priority=50,
    )
    assert worker.run_once()
    with database_runtime.new_session() as session, session.begin():
        job = PostgresJobRepository(session).get(prepared.job_id)
        assert job.status == ("succeeded" if outcome == "success" else outcome)
        run = PostgresCollectionRepository(session).get_run_by_job_id(job.id)
        assert run.status == job.status
        assert run.requested_count == 1 and run.content_count == run.comment_count == 0
        assert session.scalar(select(states.c.state)) == (
            "ready" if outcome == "success" else "unavailable"
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(provider_request_attempts_table)
                .where(provider_request_attempts_table.c.raw_artifact_id.is_not(None))
            )
            >= 1
        )
    assert transport.call_count == 1 and not worker.run_once()


@pytest.mark.parametrize("cancelled", [False, True])
def test_real_reaper_closes_refresh_timeout_or_running_cancel(
    database_runtime, tmp_path, cancelled
):
    seed = _seed(database_runtime, with_url=False)
    prepared = _prepare(seed)
    _claim(database_runtime, prepared.job_id)
    with database_runtime.new_session() as session, session.begin():
        if cancelled:
            PostgresJobRepository(session).request_cancel(prepared.job_id)
        expired = beijing_now() - timedelta(seconds=1)
        session.execute(
            update(jobs_table)
            .where(jobs_table.c.id == prepared.job_id)
            .values(
                lease_expires_at=expired,
                attempt_deadline_at=expired,
            )
        )
    registry = _registry(
        database_runtime, _executor(database_runtime, tmp_path, FakeProviderTransport(()))
    )
    assert JobReaper(
        session_factory=database_runtime.new_session, registry=registry, retry_delay_seconds=0
    ).run_once()
    with database_runtime.new_session() as session, session.begin():
        job = PostgresJobRepository(session).get(prepared.job_id)
        assert job.status == ("cancelled" if cancelled else "failed")
        assert session.scalar(select(states.c.state)) == "unavailable"
    assert _prepare(seed).status == "cooldown"


def test_lease_takeover_restores_completed_raw_without_second_attempt(
    database_runtime, tmp_path, caplog
):
    seed = _seed(database_runtime, with_url=False)
    prepared = _prepare(seed)
    old_fence = _claim(database_runtime, prepared.job_id)
    run, scope = _start(database_runtime, old_fence)
    transport = FakeProviderTransport(
        (
            ProviderTransportResponse(
                status_code=200, body=_fixture("video_detail_20261009.sanitized.json")
            ),
        )
    )
    executor = _executor(database_runtime, tmp_path, transport)
    request = build_video_detail_request(note_id=NOTE_ID)
    executor._execute_call(
        run=run,
        scope=scope,
        provider_config=seed.provider,
        context=_Context(old_fence),
        call=TikHubOperationCall(
            "xiaohongshu",
            "content_detail",
            "get_video_note_detail",
            "GET",
            request.path,
            dict(request.params),
        ),
    )
    with database_runtime.new_session() as session, session.begin():
        session.execute(
            update(jobs_table)
            .where(jobs_table.c.id == prepared.job_id)
            .values(lease_expires_at=func.clock_timestamp() - timedelta(seconds=1))
        )
    worker = JobWorker(
        session_factory=database_runtime.new_session,
        registry=_registry(database_runtime, executor),
        worker_id="media-takeover",
        lease_seconds=120,
        retry_delay_seconds=0,
        minimum_priority=50,
    )
    assert worker.run_once()
    with database_runtime.new_session() as session, session.begin():
        job = PostgresJobRepository(session).get(prepared.job_id)
        assert job.status == "succeeded" and job.attempt == 1 and job.lease_takeover_count == 1, (
            "\n".join(getattr(r, "exception", "") for r in caplog.records)
        )
        assert session.scalar(select(states.c.state)) == "ready"
        assert (
            session.scalar(
                select(func.count())
                .select_from(provider_request_attempts_table)
                .join(
                    provider_requests_table,
                    provider_requests_table.c.id
                    == provider_request_attempts_table.c.provider_request_id,
                )
                .where(provider_requests_table.c.scope_id == scope.id)
            )
            == 1
        )
        with pytest.raises(LeaseLostError):
            PostgresJobRepository(session).lock_current_execution(old_fence)
    assert transport.call_count == 1


def test_stream_session_rechecks_principal_current_source_and_visibility_without_billing(
    database_runtime,
):
    seed = _seed(database_runtime)
    seen = []
    seed.service._proxy = SimpleNamespace(
        open=lambda url, **kwargs: seen.append((url, kwargs)) or "handle"
    )
    ready = seed.service.prepare(
        seed.content_id,
        0,
        ContentMediaPlaybackPrepareRequest(),
        principal=VIEWER,
        request_id="stream-only",
    )
    token = parse_qs(urlsplit(ready.stream_url).query)["session"][0]
    arguments = dict(session=token, byte_range="bytes=0-2", principal=VIEWER)
    assert seed.service.stream(seed.content_id, 0, **arguments) == "handle"
    assert seen[0][0] == seed.source.url and seen[0][1]["byte_range"] == "bytes=0-2"
    other = Principal("other-viewer", "其他查看者", "administrator", "development")
    with pytest.raises(InvalidContentCursor):
        seed.service.stream(seed.content_id, 0, **{**arguments, "principal": other})
    with database_runtime.new_session() as session, session.begin():
        session.execute(
            update(content_media_table).values(url="https://sns-v27.rednotecdn.com/new")
        )
    with pytest.raises(InvalidContentCursor):
        seed.service.stream(seed.content_id, 0, **arguments)
    with database_runtime.new_session() as session, session.begin():
        session.execute(
            update(contents_table)
            .where(contents_table.c.id == seed.content_id)
            .values(rule_filter_visible=False)
        )
    with pytest.raises(ContentResourceNotFound):
        seed.service.stream(seed.content_id, 0, **arguments)
    with database_runtime.new_session() as session, session.begin():
        assert (
            session.scalar(
                select(func.count())
                .select_from(collection_runs_table)
                .where(collection_runs_table.c.config_snapshot["mode"].astext == "media_refresh")
            )
            == 0
        )
    assert len(seen) == 1
