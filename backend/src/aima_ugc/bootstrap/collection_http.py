"""Stage 8E Collection Run/Capability HTTP Application Service。"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.collection import PostgresCollectionRepository
from aima_ugc.adapters.persistence.postgres.collection_runtime_queries import (
    PostgresCollectionRuntimeQueryRepository,
)
from aima_ugc.adapters.persistence.postgres.collection_targets import (
    PostgresCollectionTargetReader,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.relevance import (
    GlobalRelevanceUnavailable,
    PostgresGlobalRelevanceRepository,
)
from aima_ugc.adapters.persistence.postgres.scheduled_keywords import (
    MissingScheduledKeywordPackError,
    PostgresScheduledKeywordSnapshotReader,
)
from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
from aima_ugc.adapters.providers.registry import build_default_provider_registry
from aima_ugc.adapters.providers.tikhub.transport import (
    DEFAULT_TIKHUB_REQUEST_TIMEOUT_SECONDS,
)
from aima_ugc.contracts.collection import (
    CollectionDecisionPolicyV1,
    ProviderPlatformCapabilityV1,
)
from aima_ugc.contracts.collection.models import BusinessOperation
from aima_ugc.contracts.http import (
    CollectionBatchSupplementEligibilityResponse,
    CollectionBatchSupplementTargetResponse,
    CollectionCapabilitiesResponse,
    CollectionCapabilityResponse,
    CollectionPlatform,
    CollectionProviderConfigResponse,
    CollectionRunCreatedResponse,
    CollectionRunCreateRequest,
    CollectionRunMode,
    CollectionRunResponse,
    CollectionRunStatsResponse,
    CollectionRuntimeItemResponse,
    CollectionRuntimeListQuery,
    CollectionRuntimeListResponse,
    CollectionRuntimeStatus,
    CollectionRuntimeSummaryResponse,
    CollectionScopeResponse,
    ImportStatsResponse,
)
from aima_ugc.modules.collection.collection_run_job import (
    COLLECTION_RUN_JOB_TYPE,
    COLLECTION_RUN_PAYLOAD_VERSION,
    CollectionRunJobPayload,
)
from aima_ugc.modules.collection.execution import (
    CollectionExecutionService,
    CollectionRunRecord,
    CollectionScopeDefinition,
    CollectionScopeRecord,
)
from aima_ugc.modules.collection.execution_limits import (
    DEADLINE_SAFETY_PERCENT,
    MAX_COMMENT_PAGES,
    MAX_SEARCH_PAGES,
    MAX_SUB_COMMENT_PAGES,
    provider_execution_window_floor_seconds,
)
from aima_ugc.modules.collection.http import (
    CollectionConflict,
    CollectionResourceNotFound,
    CollectionRuntimeCursorUnavailable,
)
from aima_ugc.modules.collection.http import (
    InvalidCollectionRuntimeCursor as InvalidCollectionRuntimeCursorError,
)
from aima_ugc.modules.collection.run_snapshot import provider_run_snapshot
from aima_ugc.modules.collection.runtime_cursor import (
    CollectionRuntimeCursorCodec,
    CollectionRuntimeCursorPosition,
    InvalidCollectionRuntimeCursor,
)
from aima_ugc.modules.collection.runtime_query import (
    CollectionRuntimeReadQuery,
    CollectionRuntimeReadRecord,
)
from aima_ugc.modules.collection.scheduled_scopes import build_scheduled_scope_snapshot
from aima_ugc.platform.security import SecretFileError, read_secret_file

from .analysis_identity import current_analysis_identity
from .runtime import PlatformRuntime

_COLLECTION_JOB_MAX_ATTEMPTS = 2
_SHANGHAI = ZoneInfo("Asia/Shanghai")
_ALL_COLLECTION_PLATFORMS: tuple[CollectionPlatform, ...] = (
    "xiaohongshu",
    "douyin",
    "weibo",
    "bilibili",
    "kuaishou",
)


class PostgresCollectionHttpService:
    """创建短事务 Run/Job/Scope，并提供 Provider-neutral 查询。"""

    def __init__(
        self,
        runtime: PlatformRuntime,
        *,
        cursor_signing_secret: bytes | None = None,
    ) -> None:
        self._runtime = runtime
        self._cursor_signing_secret = cursor_signing_secret

    def get_capabilities(self) -> CollectionCapabilitiesResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                configs = PostgresProviderConfigRepository(session).list_enabled()
                registry = build_default_provider_registry()
                public_configs: list[CollectionProviderConfigResponse] = []
                capabilities: dict[tuple[str, str], CollectionCapabilityResponse] = {}
                for config in configs:
                    config_has_route = False
                    for platform in ("xiaohongshu", "douyin", "weibo", "bilibili", "kuaishou"):
                        try:
                            route = registry.resolve(config=config, platform=platform)
                        except ValueError:
                            continue
                        config_has_route = True
                        capabilities[(route.provider, route.platform)] = (
                            CollectionCapabilityResponse(
                                provider=route.provider,
                                platform=_collection_platform(route.platform),
                                operations=tuple(
                                    operation.business_operation
                                    for operation in route.capability.operations
                                ),
                            )
                        )
                    if config_has_route:
                        public_configs.append(
                            CollectionProviderConfigResponse(
                                id=config.id,
                                provider=config.provider,
                                display_name=config.display_name,
                            )
                        )
                return CollectionCapabilitiesResponse(
                    provider_configs=tuple(public_configs),
                    capabilities=tuple(capabilities[key] for key in sorted(capabilities)),
                )
        finally:
            session.close()

    def get_batch_supplement_eligibility(
        self,
        batch_id: UUID,
    ) -> CollectionBatchSupplementEligibilityResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                reader = PostgresCollectionTargetReader(
                    session,
                    analysis_identity=current_analysis_identity(self._runtime.settings),
                )
                if not reader.batch_exists(batch_id):
                    raise CollectionResourceNotFound
                targets = reader.list_batch_targets(
                    batch_id=batch_id,
                    platforms=_ALL_COLLECTION_PLATFORMS,
                )
                counts: dict[CollectionPlatform, int] = {}
                for target in targets:
                    counts[target.platform] = counts.get(target.platform, 0) + 1
                return CollectionBatchSupplementEligibilityResponse(
                    batch_id=batch_id,
                    targets=tuple(
                        CollectionBatchSupplementTargetResponse(
                            platform=platform,
                            target_count=counts[platform],
                        )
                        for platform in _ALL_COLLECTION_PLATFORMS
                        if platform in counts
                    ),
                )
        finally:
            session.close()

    def create_run(
        self,
        request: CollectionRunCreateRequest,
        *,
        request_id: str,
    ) -> CollectionRunCreatedResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                provider_snapshots = self._resolve_provider_snapshots(session, request)
                try:
                    relevance_snapshot, _ = PostgresGlobalRelevanceRepository(session).snapshot()
                except GlobalRelevanceUnavailable as exc:
                    raise CollectionConflict from exc
                scopes, keyword_pack_snapshot = self._build_scopes(session, request)
                if not scopes:
                    raise CollectionConflict
                effective_keywords = tuple(
                    dict.fromkeys(
                        scope.source_value
                        for scope in scopes
                        if scope.source_type == "keyword_search"
                    )
                )
                timeout_seconds = provider_execution_window_floor_seconds(
                    scope_count=len(scopes),
                    request_timeout_seconds=DEFAULT_TIKHUB_REQUEST_TIMEOUT_SECONDS,
                )
                idempotency_nonce = uuid4()
                job = PostgresJobRepository(session).enqueue(
                    job_type=COLLECTION_RUN_JOB_TYPE,
                    payload_version=COLLECTION_RUN_PAYLOAD_VERSION,
                    payload=CollectionRunJobPayload().model_dump(mode="json"),
                    internal_idempotency_key=f"api:{idempotency_nonce}",
                    request_id=request_id,
                    priority=10,
                    max_attempts=_COLLECTION_JOB_MAX_ATTEMPTS,
                    timeout_seconds=timeout_seconds,
                )
                policy = CollectionDecisionPolicyV1(
                    comments_enabled=request.include_comments,
                )
                execution = CollectionExecutionService(
                    PostgresCollectionRepository(session)
                ).create_run(
                    job_id=job.id,
                    trigger_type="api",
                    config_snapshot={
                        "schema_version": "collection-run-config.v1",
                        "mode": request.mode,
                        "keyword_pack_ids": [str(item) for item in request.keyword_pack_ids],
                        "keyword_packs": list(keyword_pack_snapshot),
                        "keywords": list(effective_keywords),
                        "import_batch_id": (
                            str(request.import_batch_id)
                            if request.import_batch_id is not None
                            else None
                        ),
                        "include_comments": request.include_comments,
                        "include_sub_comments": request.include_sub_comments,
                        "manual_deep_collection": True,
                        "detail_policy": "on_change",
                        "comment_policy": "adaptive",
                        "decision_policy": policy.model_dump(mode="json"),
                        "job_timeout_seconds": timeout_seconds,
                        "execution_limits": {
                            "scope_count": len(scopes),
                            "max_search_pages": MAX_SEARCH_PAGES,
                            "max_comment_pages": MAX_COMMENT_PAGES,
                            "max_sub_comment_pages": MAX_SUB_COMMENT_PAGES,
                            "provider_request_timeout_seconds": (
                                DEFAULT_TIKHUB_REQUEST_TIMEOUT_SECONDS
                            ),
                            "deadline_safety_percent": DEADLINE_SAFETY_PERCENT,
                        },
                        "platforms": list(provider_snapshots),
                        "relevance": relevance_snapshot.model_dump(mode="json"),
                    },
                    scopes=scopes,
                    import_batch_id=request.import_batch_id,
                )
                return CollectionRunCreatedResponse(
                    run_id=execution.run.id,
                    job_id=job.id,
                    mode=request.mode,
                    import_batch_id=request.import_batch_id,
                )
        finally:
            session.close()

    def get_run(self, run_id: UUID) -> CollectionRunResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresCollectionRepository(session)
                run = repository.get_run(run_id)
                if run is None:
                    raise CollectionResourceNotFound
                job = PostgresJobRepository(session).get(run.job_id)
                if job is None:
                    raise CollectionResourceNotFound
                scopes = tuple(repository.list_scopes(run.id))
                snapshot = run.config_snapshot
                mode_value = snapshot.get("mode", "discovery")
                if mode_value not in {"discovery", "batch_supplement"}:
                    raise CollectionConflict
                mode: CollectionRunMode = (
                    "discovery" if mode_value == "discovery" else "batch_supplement"
                )
                return CollectionRunResponse(
                    run_id=run.id,
                    job_id=run.job_id,
                    mode=mode,
                    import_batch_id=run.import_batch_id,
                    status=_public_run_status(run, job.status),
                    stage=_run_stage(run),
                    progress=job.progress,
                    attempt=job.attempt,
                    max_attempts=job.max_attempts,
                    platforms=tuple(
                        sorted({_collection_platform(scope.platform) for scope in scopes})
                    ),
                    keywords=_snapshot_keywords(snapshot),
                    stats=_run_stats(run, scopes),
                    scopes=tuple(_scope_response(scope) for scope in scopes),
                    error_summary=run.error_summary,
                    error_code=job.error_code,
                    created_at=run.created_at,
                    started_at=run.started_at or job.started_at,
                    finished_at=run.finished_at or job.finished_at,
                )
        finally:
            session.close()

    def list_runtime_runs(
        self,
        query: CollectionRuntimeListQuery,
    ) -> CollectionRuntimeListResponse:
        codec = self._cursor_codec()
        query_hash = _runtime_query_hash(query)
        try:
            position = (
                codec.decode(query.cursor, query_hash=query_hash)
                if query.cursor is not None
                else None
            )
        except InvalidCollectionRuntimeCursor as exc:
            raise InvalidCollectionRuntimeCursorError from exc
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                rows = PostgresCollectionRuntimeQueryRepository(session).list_runs(
                    CollectionRuntimeReadQuery(
                        search=query.search,
                        record_types=query.record_types,
                        status=query.status,
                        stage=query.stage,
                        created_from=query.created_from,
                        created_to=query.created_to,
                        position=position,
                        limit=query.limit + 1,
                    )
                )
        finally:
            session.close()
        has_more = len(rows) > query.limit
        page = rows[: query.limit]
        next_cursor = None
        if has_more and page:
            last = page[-1]
            next_cursor = codec.encode(
                CollectionRuntimeCursorPosition(
                    created_at=last.created_at,
                    record_id=last.record_id,
                    record_type=last.record_type,
                ),
                query_hash=query_hash,
            )
        return CollectionRuntimeListResponse(
            items=tuple(_runtime_item_response(row) for row in page),
            next_cursor=next_cursor,
            has_more=has_more,
        )

    def get_runtime_summary(self) -> CollectionRuntimeSummaryResponse:
        as_of = datetime.now(UTC)
        local_now = as_of.astimezone(_SHANGHAI)
        today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_start = today_start + timedelta(days=1)
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                summary = PostgresCollectionRuntimeQueryRepository(session).summary(
                    today_start_utc=today_start.astimezone(UTC),
                    tomorrow_start_utc=tomorrow_start.astimezone(UTC),
                )
        finally:
            session.close()
        return CollectionRuntimeSummaryResponse(
            processing_count=summary.processing_count,
            completed_today_count=summary.completed_today_count,
            contents_ingested_today=summary.contents_ingested_today,
            as_of=as_of,
        )

    def _cursor_codec(self) -> CollectionRuntimeCursorCodec:
        secret = self._cursor_signing_secret
        if secret is None:
            try:
                secret = (
                    read_secret_file(
                        self._runtime.settings.collection_runtime_cursor_signing_key_file,
                        root=self._runtime.settings.secret_dir,
                    )
                    .get_secret_value()
                    .encode("utf-8")
                )
            except SecretFileError as exc:
                raise CollectionRuntimeCursorUnavailable from exc
        try:
            return CollectionRuntimeCursorCodec(secret=secret)
        except ValueError as exc:
            raise CollectionRuntimeCursorUnavailable from exc

    def _resolve_provider_snapshots(
        self,
        session: Session,
        request: CollectionRunCreateRequest,
    ) -> tuple[dict[str, object], ...]:
        repository = PostgresProviderConfigRepository(session)
        registry = build_default_provider_registry()
        snapshots: list[dict[str, object]] = []
        for selection in request.platforms:
            config = repository.get(selection.provider_config_id)
            if config is None:
                raise CollectionResourceNotFound
            try:
                route = registry.resolve(config=config, platform=selection.platform)
                _validate_requested_capabilities(route.capability, request)
            except ValueError as exc:
                raise CollectionConflict from exc
            snapshots.append(provider_run_snapshot(config, platform=selection.platform))
        return tuple(snapshots)

    def _build_scopes(
        self,
        session: Session,
        request: CollectionRunCreateRequest,
    ) -> tuple[tuple[CollectionScopeDefinition, ...], tuple[dict[str, object], ...]]:
        if request.mode == "discovery":
            try:
                catalog = PostgresScheduledKeywordSnapshotReader(session).read(
                    request.keyword_pack_ids
                )
            except (MissingScheduledKeywordPackError, ValueError) as exc:
                raise CollectionResourceNotFound from exc
            if any(not pack.enabled for pack in catalog.keyword_packs):
                raise CollectionConflict
            snapshot = build_scheduled_scope_snapshot(
                plan_platforms=tuple(item.platform for item in request.platforms),
                entries=catalog.entries,
                keyword_packs=catalog.keyword_packs,
            )
            return (
                snapshot.scopes,
                tuple(
                    {"id": str(pack.pack_id), "version": pack.version}
                    for pack in snapshot.keyword_packs
                ),
            )
        assert request.import_batch_id is not None
        reader = PostgresCollectionTargetReader(
            session,
            analysis_identity=current_analysis_identity(self._runtime.settings),
        )
        if not reader.batch_exists(request.import_batch_id):
            raise CollectionResourceNotFound
        selected_platforms = tuple(selection.platform for selection in request.platforms)
        targets = reader.list_batch_targets(
            batch_id=request.import_batch_id,
            platforms=selected_platforms,
        )
        actual_platforms = {target.platform for target in targets}
        if set(selected_platforms) != actual_platforms:
            raise CollectionConflict
        return (
            tuple(
                CollectionScopeDefinition(
                    platform=target.platform,
                    source_type="content",
                    source_value=str(target.content_id),
                    operation_group="content_enrichment",
                )
                for target in targets
            ),
            (),
        )


def _validate_requested_capabilities(
    capability: ProviderPlatformCapabilityV1,
    request: CollectionRunCreateRequest,
) -> None:
    required: list[BusinessOperation] = ["content_detail"]
    if request.mode == "discovery":
        required.append("keyword_search")
    if request.include_comments:
        required.append("comments")
    if request.include_sub_comments:
        required.append("sub_comments")
    missing = [name for name in required if capability.operation(name) is None]
    if missing:
        raise ValueError(f"Provider Capability 缺少: {', '.join(missing)}")


def _public_run_status(
    run: CollectionRunRecord,
    job_status: str,
) -> CollectionRuntimeStatus:
    if job_status in {"failed", "cancelled"}:
        return cast(CollectionRuntimeStatus, job_status)
    return run.status


def _run_stage(run: CollectionRunRecord) -> str:
    if run.status != "running":
        return run.status
    return (
        "content_enrichment"
        if run.config_snapshot.get("mode") == "batch_supplement"
        else "content_discovery"
    )


def _snapshot_keywords(snapshot: dict[str, object]) -> tuple[str, ...]:
    value = snapshot.get("keywords", [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return ()
    return tuple(cast(list[str], value))


def _scope_stats(scope: CollectionScopeRecord) -> CollectionRunStatsResponse:
    return CollectionRunStatsResponse(
        requested_count=_safe_count(scope.stats, "requested_count"),
        succeeded_count=_safe_count(scope.stats, "succeeded_count"),
        failed_count=_safe_count(scope.stats, "failed_count"),
        content_count=_safe_count(scope.stats, "content_count"),
        comment_count=_safe_count(scope.stats, "comment_count"),
        filtered_count=_safe_count(scope.stats, "filtered_content_count"),
    )


def _scope_response(scope: CollectionScopeRecord) -> CollectionScopeResponse:
    return CollectionScopeResponse(
        id=scope.id,
        platform=_collection_platform(scope.platform),
        source_type=scope.source_type,
        operation_group=scope.operation_group,
        status=_runtime_status(scope.status),
        progress=scope.progress,
        stats=_scope_stats(scope),
        stop_reason=scope.stop_reason,
        started_at=scope.started_at,
        finished_at=scope.finished_at,
    )


def _run_stats(
    run: CollectionRunRecord,
    scopes: tuple[CollectionScopeRecord, ...],
) -> CollectionRunStatsResponse:
    return CollectionRunStatsResponse(
        requested_count=run.requested_count,
        succeeded_count=run.succeeded_count,
        failed_count=run.failed_count,
        content_count=run.content_count,
        comment_count=run.comment_count,
        filtered_count=sum(_safe_count(scope.stats, "filtered_content_count") for scope in scopes),
    )


def _safe_count(payload: dict[str, object], key: str) -> int:
    value = payload.get(key, 0)
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _runtime_query_hash(query: CollectionRuntimeListQuery) -> str:
    payload = query.model_dump(
        mode="json",
        exclude={"cursor", "limit"},
        exclude_none=True,
    )
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _runtime_item_response(
    record: CollectionRuntimeReadRecord,
) -> CollectionRuntimeItemResponse:
    import_stats = (
        ImportStatsResponse(
            rows_seen=_safe_count(record.import_stats, "rows_seen"),
            rows_matched=_safe_count(record.import_stats, "rows_matched"),
            rows_filtered_out=_safe_count(record.import_stats, "rows_filtered_out"),
            duplicates_removed=_safe_count(record.import_stats, "duplicates_removed"),
            rows_ingested=_safe_count(record.import_stats, "rows_ingested"),
            rows_rejected=_safe_count(record.import_stats, "rows_rejected"),
        )
        if record.import_stats is not None
        else None
    )
    collection_stats = (
        CollectionRunStatsResponse(
            requested_count=record.requested_count,
            succeeded_count=record.succeeded_count,
            failed_count=record.failed_count,
            content_count=record.content_count,
            comment_count=record.comment_count,
            filtered_count=record.filtered_count,
        )
        if record.collection_run_id is not None
        else None
    )
    return CollectionRuntimeItemResponse(
        record_id=record.record_id,
        job_id=record.job_id,
        record_type=record.record_type,
        display_name=_runtime_display_name(record),
        status=_runtime_status(record.status),
        progress=record.progress,
        stage=record.stage,
        import_batch_id=record.import_batch_id,
        collection_run_id=record.collection_run_id,
        source_filename=record.source_filename,
        platforms=_runtime_platforms(record.config_snapshot),
        keywords=_snapshot_keywords(record.config_snapshot or {}),
        import_stats=import_stats,
        collection_stats=collection_stats,
        error_summary=record.error_summary,
        error_code=record.error_code,
        created_at=record.created_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
    )


def _runtime_display_name(record: CollectionRuntimeReadRecord) -> str:
    if record.record_type == "excel_import":
        return record.source_filename or "Excel 导入"
    if record.record_type == "tikhub_batch_supplement":
        suffix = f" · {record.source_filename}" if record.source_filename else ""
        return f"TikHub 批次补采{suffix}"
    keywords = _snapshot_keywords(record.config_snapshot or {})
    suffix = f" · {'、'.join(keywords[:2])}" if keywords else ""
    return f"TikHub 主动发现{suffix}"


def _runtime_platforms(
    snapshot: dict[str, object] | None,
) -> tuple[CollectionPlatform, ...]:
    if snapshot is None:
        return ()
    raw = snapshot.get("platforms")
    if not isinstance(raw, list):
        return ()
    platforms: list[CollectionPlatform] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        platform = item.get("platform")
        if (
            isinstance(platform, str)
            and platform
            in {
                "xiaohongshu",
                "douyin",
                "weibo",
                "bilibili",
                "kuaishou",
            }
            and platform not in platforms
        ):
            platforms.append(cast(CollectionPlatform, platform))
    return tuple(platforms)


def _collection_platform(value: str) -> CollectionPlatform:
    if value not in {"xiaohongshu", "douyin", "weibo", "bilibili", "kuaishou"}:
        raise CollectionConflict
    return cast(CollectionPlatform, value)


def _runtime_status(value: str) -> CollectionRuntimeStatus:
    if value not in {
        "queued",
        "running",
        "partial_success",
        "succeeded",
        "failed",
        "cancelled",
    }:
        raise CollectionConflict
    return cast(CollectionRuntimeStatus, value)


__all__ = ["PostgresCollectionHttpService"]
