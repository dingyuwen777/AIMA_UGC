"""正式 Scope 的一次视频详情执行；Raw/Attempt 复用既有收费审计链。"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from aima_ugc.adapters.persistence.postgres.content_playback import (
    PostgresContentPlaybackRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.providers.tikhub.operations.xiaohongshu import build_video_detail_request
from aima_ugc.adapters.providers.tikhub.runtime import (
    TikHubOperationCall,
    extract_detail_items,
    map_content,
    mapping_context,
)
from aima_ugc.adapters.providers.video_stream import VideoStreamError
from aima_ugc.contracts.provider import JsonObject
from aima_ugc.modules.collection.collection_run_executor import CollectionScopeExecutionResult
from aima_ugc.modules.collection.execution import CollectionRunRecord, CollectionScopeRecord
from aima_ugc.modules.collection.media_refresh import validate_media_refresh_snapshot
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol
from aima_ugc.platform.time import beijing_now

if TYPE_CHECKING:
    from .collection_scope import TikHubCollectionScopeExecutor


def execute_media_refresh(
    executor: TikHubCollectionScopeExecutor,
    *,
    run: CollectionRunRecord,
    scope: CollectionScopeRecord,
    provider_config: ProviderConfig,
    context: JobExecutionContextProtocol,
) -> CollectionScopeExecutionResult:
    """不创建 Candidate 或执行普通 Content ingest；仅发布有真实 Raw 证明的 URL。"""
    from .collection_scope import _ProviderCallFailed

    target = validate_media_refresh_snapshot(run.config_snapshot)
    if (
        scope.platform != "xiaohongshu"
        or scope.source_type != "content"
        or scope.source_value != str(target.content_id)
        or scope.operation_group != "media_refresh"
    ):
        raise ValueError("media_refresh Scope 与冻结目标不一致")

    def finish(
        code: str | None, *, cancelled: bool = False, cover_only: bool = False
    ) -> CollectionScopeExecutionResult:
        if code is not None:
            with executor._session_factory() as session, session.begin():
                PostgresJobRepository(session).lock_current_execution(context.fence)
                PostgresContentPlaybackRepository(session).settle_job(
                    context.fence.job_id, code=code, now=beijing_now()
                )
        counts = executor._attempt_preparer.read_scope_counts(
            scope_id=scope.id, fence=context.fence
        )
        stats = {
            "requested_count": counts.requested_count,
            "succeeded_count": counts.succeeded_count,
            "failed_count": counts.failed_count,
            "content_count": 0,
            "comment_count": 0,
            "detail_requests": counts.requested_count,
            "stage": "media_refresh",
            "technical_partial_results": int(code is not None and not cancelled),
        }
        return CollectionScopeExecutionResult(
            status="cancelled"
            if cancelled
            else "failed"
            if code and not cover_only
            else "succeeded",
            stop_reason=code or "media_refreshed",
            pagination_state={},
            stats=stats,
            requested_count=counts.requested_count,
            succeeded_count=counts.succeeded_count,
            failed_count=counts.failed_count,
            content_count=0,
            comment_count=0,
        )

    if context.cancel_requested():
        return finish("cancelled", cancelled=True)
    request = build_video_detail_request(note_id=target.note_id)
    call = TikHubOperationCall(
        "xiaohongshu",
        "content_detail",
        "get_video_note_detail",
        "GET",
        request.path,
        cast(JsonObject, dict(request.params)),
    )
    try:
        executed = executor._execute_call(
            run=run, scope=scope, call=call, provider_config=provider_config, context=context
        )
    except _ProviderCallFailed as exc:
        return finish(exc.error_code)
    if context.cancel_requested():
        return finish("cancelled", cancelled=True)
    try:
        items = extract_detail_items(
            "xiaohongshu", executed.body, external_content_id=target.note_id
        )
        if len(items) != 1:
            raise ValueError("media_refresh 详情必须返回唯一身份")
        observation = map_content(
            platform="xiaohongshu",
            raw=items[0],
            context=mapping_context(
                provider_request_id=str(executed.request_id),
                provider_attempt_id=str(executed.attempt_id),
                raw_artifact_id=executed.raw_artifact_id,
                operation=call.operation,
                source_type=scope.source_type,
                source_value=scope.source_value,
                observed_at=executed.observed_at,
            ),
            item_locator=f"media:{target.position}",
        )
        if observation.external_content_id != target.note_id:
            raise ValueError("media_refresh 详情身份不一致")
    except ValueError:
        return finish("detail_mapping_invalid")
    media = next(
        (
            item
            for item in observation.media
            if item.position == target.position and item.media_type == "video"
        ),
        None,
    )
    if media is None or media.url is None:
        return finish("cover_only", cover_only=True)
    try:
        with executor._session_factory() as session, session.begin():
            applied = PostgresContentPlaybackRepository(session).publish_refresh(
                fence=context.fence,
                content_id=target.content_id,
                position=target.position,
                identity_token=target.identity_token,
                expected_source_revision=target.expected_source_revision,
                generation=target.generation,
                url=str(media.url),
                attempt_id=executed.attempt_id,
                raw_id=executed.raw_artifact_id,
                observed_at=executed.observed_at,
                observed_external_media_id=media.external_media_id,
            )
    except VideoStreamError:
        return finish("invalid_source")
    return finish(None if applied else "source_changed")
