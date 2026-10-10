"""用户播放的短事务准备与站内流；只复用现有 Collection Job/Raw 执行链。"""

from __future__ import annotations

from dataclasses import replace
from urllib.parse import urlencode
from uuid import UUID, uuid4

from aima_ugc.adapters.persistence.postgres.collection import PostgresCollectionRepository
from aima_ugc.adapters.persistence.postgres.content_playback import (
    PostgresContentPlaybackRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
from aima_ugc.adapters.providers.video_stream import (
    VideoStreamError,
    VideoStreamHandle,
    VideoStreamProxy,
    normalize_video_url,
)
from aima_ugc.contracts.content_playback import (
    ContentMediaPlaybackPrepareRequest,
    ContentMediaPlaybackResponse,
    ContentPlaybackStatus,
)
from aima_ugc.modules.collection.collection_run_job import (
    COLLECTION_RUN_JOB_TYPE,
    COLLECTION_RUN_PAYLOAD_VERSION,
    CollectionRunJobPayload,
)
from aima_ugc.modules.collection.execution import (
    CollectionExecutionService,
    CollectionScopeDefinition,
)
from aima_ugc.modules.collection.media_refresh import media_refresh_snapshot
from aima_ugc.modules.content.http import ContentResourceNotFound
from aima_ugc.modules.content.media_playback import (
    REFRESHABLE_STREAM_FAILURES,
    ContentPlaybackSessionCodec,
    ContentPlaybackSource,
)
from aima_ugc.modules.identity import Principal
from aima_ugc.platform.security import read_secret_file
from aima_ugc.platform.time import beijing_now

from .runtime import PlatformRuntime


class PostgresContentPlaybackHttpService:
    """同媒体的并发准备在 Content 锁内去重；网络传输始终在事务外。"""

    def __init__(
        self,
        runtime: PlatformRuntime,
        *,
        proxy: VideoStreamProxy | None = None,
        session_codec: ContentPlaybackSessionCodec | None = None,
    ) -> None:
        self._runtime = runtime
        self._proxy = proxy or VideoStreamProxy()
        self._session_codec = session_codec

    def _codec(self) -> ContentPlaybackSessionCodec:
        if self._session_codec is None:
            secret = (
                read_secret_file(
                    self._runtime.settings.content_cursor_signing_key_file,
                    root=self._runtime.settings.secret_dir,
                )
                .get_secret_value()
                .encode("utf-8")
            )
            self._session_codec = ContentPlaybackSessionCodec(secret=secret)
        return self._session_codec

    def _response(
        self,
        source: ContentPlaybackSource,
        status: ContentPlaybackStatus,
        *,
        principal: Principal,
        failure_code: str | None = None,
    ) -> ContentMediaPlaybackResponse:
        url = None
        if status == "ready":
            session = self._codec().issue(
                principal_id=principal.principal_id,
                content_id=source.content_id,
                position=source.position,
                identity_token=source.identity_token,
                source_revision=source.source_revision,
            )
            url = (
                f"/api/v1/contents/{source.content_id}/media/{source.position}/playback/stream?"
                + urlencode({"session": session})
            )
        return ContentMediaPlaybackResponse(
            content_id=source.content_id,
            position=source.position,
            status=status,
            generation=source.generation,
            source_revision=source.source_revision,
            stream_url=url,
            job_id=source.job_id if status == "preparing" else None,
            cooldown_until=source.cooldown_until if status == "cooldown" else None,
            failure_code=failure_code or source.failure_code,
        )

    def prepare(
        self,
        content_id: UUID,
        position: int,
        body: ContentMediaPlaybackPrepareRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> ContentMediaPlaybackResponse:
        with self._runtime.database.new_session() as session:
            with session.begin():
                owner = PostgresContentPlaybackRepository(session)
                source = owner.get_source(content_id, position, lock=True)
                if body.observed_job_id is not None:
                    # 只读观察必须先于 settle/enqueue；过期冷却和失败终态也不能重开收费任务。
                    if source is None:
                        return ContentMediaPlaybackResponse(
                            content_id=content_id,
                            position=position,
                            status="unavailable",
                            generation=0,
                            source_revision="",
                            failure_code="source_changed",
                        )
                    if source.job_id != body.observed_job_id:
                        return self._response(
                            source,
                            "unavailable",
                            principal=principal,
                            failure_code="source_changed",
                        )
                    job = PostgresJobRepository(session).get(body.observed_job_id)
                    if job is None or job.job_type != COLLECTION_RUN_JOB_TYPE:
                        return self._response(
                            source,
                            "unavailable",
                            principal=principal,
                            failure_code="source_changed",
                        )
                    if job.status in {"queued", "running"}:
                        return self._response(source, "preparing", principal=principal)
                    if (
                        job.status == "succeeded"
                        and source.state == "ready"
                        and source.url
                        and source.failure_code is None
                    ):
                        try:
                            normalize_video_url(source.url)
                        except VideoStreamError:
                            return self._response(
                                source,
                                "unavailable",
                                principal=principal,
                                failure_code="invalid_source",
                            )
                        return self._response(source, "ready", principal=principal)
                    return self._response(
                        source,
                        "unavailable",
                        principal=principal,
                        failure_code=source.failure_code or job.error_code or job.status,
                    )
                if source is None:
                    raise ContentResourceNotFound
                now = beijing_now()
                if source.state == "preparing" and source.job_id is not None:
                    # 不反向锁 Job：Worker 的固定锁序是 Job→Content→state。
                    job = PostgresJobRepository(session).get(source.job_id)
                    if job is not None and job.status in {"queued", "running", "retry_wait"}:
                        return self._response(source, "preparing", principal=principal)
                    owner.settle_job(
                        source.job_id, code=job.status if job is not None else "failed", now=now
                    )
                    source = owner.get_source(content_id, position)
                    assert source is not None
                valid_url = False
                if source.url:
                    try:
                        normalize_video_url(source.url)
                        valid_url = True
                    except VideoStreamError:
                        return self._response(
                            source,
                            "unavailable",
                            principal=principal,
                            failure_code="invalid_source",
                        )
                should_refresh = (
                    body.failed_source_revision == source.source_revision
                    and source.failure_source_revision == source.source_revision
                    and source.failure_code in REFRESHABLE_STREAM_FAILURES
                )
                if valid_url and not should_refresh:
                    return self._response(source, "ready", principal=principal)
                if source.cooldown_until is not None and source.cooldown_until > now:
                    return self._response(source, "cooldown", principal=principal)
                configs = [
                    config
                    for config in PostgresProviderConfigRepository(session).list_enabled()
                    if config.provider_kind == "collection" and config.provider == "tikhub"
                ]
                if not configs:
                    return self._response(
                        source,
                        "unavailable",
                        principal=principal,
                        failure_code="provider_unavailable",
                    )
                provider = sorted(configs, key=lambda config: str(config.id))[0]
                snapshot = media_refresh_snapshot(source, provider)
                # Content 锁和同事务 state 已承担并发去重；新意图 UUID 区分删除后恢复的生命周期。
                refresh_intent_id = uuid4()
                job = PostgresJobRepository(session).enqueue(
                    job_type=COLLECTION_RUN_JOB_TYPE,
                    payload_version=COLLECTION_RUN_PAYLOAD_VERSION,
                    payload=CollectionRunJobPayload().model_dump(mode="json"),
                    internal_idempotency_key=(
                        f"media:{content_id}:{position}:"
                        f"{source.identity_token}:{source.generation + 1}:{refresh_intent_id}"
                    ),
                    request_id=request_id,
                    priority=10,
                    max_attempts=1,
                    timeout_seconds=provider.timeout_seconds + 30,
                )
                execution = CollectionExecutionService(
                    PostgresCollectionRepository(session)
                ).create_run(
                    job_id=job.id,
                    trigger_type="api",
                    config_snapshot=snapshot,
                    scopes=(
                        CollectionScopeDefinition(
                            platform="xiaohongshu",
                            source_type="content",
                            source_value=str(content_id),
                            operation_group="media_refresh",
                        ),
                    ),
                )
                owner.begin_refresh(source, job_id=job.id, run_id=execution.run.id)
                return self._response(
                    replace(
                        source,
                        generation=source.generation + 1,
                        job_id=job.id,
                        run_id=execution.run.id,
                        state="preparing",
                        failure_code=None,
                    ),
                    "preparing",
                    principal=principal,
                )

    def stream(
        self,
        content_id: UUID,
        position: int,
        *,
        session: str,
        byte_range: str | None,
        principal: Principal,
    ) -> VideoStreamHandle:
        with self._runtime.database.new_session() as database_session:
            with database_session.begin():
                source = PostgresContentPlaybackRepository(database_session).get_source(
                    content_id, position
                )
                if source is None:
                    raise ContentResourceNotFound
                self._codec().verify(
                    session,
                    principal_id=principal.principal_id,
                    content_id=content_id,
                    position=position,
                    identity_token=source.identity_token,
                    source_revision=source.source_revision,
                )
                if source.url is None:
                    raise VideoStreamError("invalid_source")

        def failed(code: str) -> None:
            with self._runtime.database.new_session() as failure_session:
                with failure_session.begin():
                    PostgresContentPlaybackRepository(failure_session).record_stream_failure(
                        source, code=code, now=beijing_now()
                    )

        return self._proxy.open(
            source.url, principal_id=principal.principal_id, byte_range=byte_range, failure=failed
        )
