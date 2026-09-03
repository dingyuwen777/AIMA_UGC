"""Stage 8D 声音广场 HTTP Application Service。"""

from __future__ import annotations

import hashlib
import json
from math import ceil
from typing import Any, Literal, cast
from uuid import UUID, uuid4, uuid5

from sqlalchemy import select
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.analysis import (
    AnalysisRequestNotFound,
    AnalysisRunStateConflict,
    PostgresAnalysisRepository,
)
from aima_ugc.adapters.persistence.postgres.analysis_manual_reviews import (
    PostgresAnalysisManualReviewRepository,
)
from aima_ugc.adapters.persistence.postgres.content_queries import (
    PostgresContentQueryRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.relevance_reviews import (
    PostgresContentRelevanceReviewRepository,
)
from aima_ugc.adapters.persistence.postgres.system import PostgresAuditRepository
from aima_ugc.adapters.persistence.postgres.vehicles import PostgresVehicleCatalogRepository
from aima_ugc.contracts.analysis import ContentRelevance
from aima_ugc.contracts.http import (
    AnalysisContentRunCreatedResponse,
    AnalysisContentRunCreateRequest,
    AnalysisContentRunListResponse,
    AnalysisContentRunPreviewRequest,
    AnalysisContentRunPreviewResponse,
    AnalysisContentRunResponse,
    AnalysisContentRunShardResponse,
    AnalysisContentRunStatsResponse,
    AnalysisRunIntent,
    AnalysisRunStatus,
    AnalysisRunTargetSelection,
    ContentAnalysisCreatedResponse,
    ContentAnalysisJobResultResponse,
    ContentAnalysisResponse,
    ContentAnalysisStatus,
    ContentAnalysisSubmitRequest,
    ContentAnalysisTaxonomyResponse,
    ContentDetailResponse,
    ContentFilterSnapshot,
    ContentLabelPairResponse,
    ContentListItemResponse,
    ContentListQuery,
    ContentListResponse,
    ContentMetricsResponse,
    ContentRelevanceSource,
    ContentSourceResponse,
    ContentTargetSelection,
    ContentVehicleEvidenceResponse,
    ContentVehicleResponse,
    JobStatusResponse,
)
from aima_ugc.contracts.product import (
    AnalysisManualLabelRequest,
    ContentAnalysisManualReviewRequest,
    ContentAnalysisManualReviewResponse,
    ContentAvailabilityResponse,
    ContentVehicleReviewRequest,
    ContentVehicleReviewResponse,
)
from aima_ugc.contracts.relevance_review import (
    ContentRelevanceReviewRequest,
    ContentRelevanceReviewResponse,
)
from aima_ugc.modules.analysis.content_analysis_job import (
    CONTENT_ANALYSIS_JOB_MAX_ATTEMPTS,
    CONTENT_ANALYSIS_JOB_PAYLOAD_VERSION,
    CONTENT_ANALYSIS_JOB_TIMEOUT_SECONDS,
    CONTENT_ANALYSIS_JOB_TYPE,
    CONTENT_ANALYSIS_PLAN_JOB_MAX_ATTEMPTS,
    CONTENT_ANALYSIS_PLAN_JOB_PAYLOAD_VERSION,
    CONTENT_ANALYSIS_PLAN_JOB_TIMEOUT_SECONDS,
    CONTENT_ANALYSIS_PLAN_JOB_TYPE,
    ContentAnalysisJobPayload,
    ContentAnalysisPlanJobPayload,
    analysis_all_scope_filter_snapshot,
    is_analysis_all_scope_filter_snapshot,
)
from aima_ugc.modules.content.content_cursor import ContentCursorCodec, ContentCursorPosition
from aima_ugc.modules.content.http import (
    ContentAnalysisRunConflict,
    ContentAnalysisTargetChanged,
    ContentAnalysisUnavailable,
    ContentCursorUnavailable,
    ContentResourceNotFound,
    ContentSelectionEmpty,
)
from aima_ugc.modules.content.query import ContentReadQuery, ContentReadRecord
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.modules.system.models import AuditEvent
from aima_ugc.platform.jobs import JobRecord
from aima_ugc.platform.security import SecretFileError, read_secret_file
from aima_ugc.platform.time import beijing_now

from .analysis_identity import (
    ActiveAnalysisConfiguration,
    active_analysis_configuration,
    current_analysis_generation_config,
)
from .analysis_taxonomy_http import content_analysis_taxonomy_projection
from .runtime import PlatformRuntime

_ANALYSIS_RUN_ID_NAMESPACE = UUID("d9c7fe38-1a46-4ef9-b9d3-bb87dd7d8301")
_AnalysisTargetSelection = ContentTargetSelection | AnalysisRunTargetSelection


class PostgresContentHttpService:
    def __init__(
        self,
        runtime: PlatformRuntime,
        *,
        cursor_signing_secret: bytes | None = None,
    ) -> None:
        self._runtime = runtime
        self._cursor_signing_secret = cursor_signing_secret

    def list_contents(self, query: ContentListQuery) -> ContentListResponse:
        codec = self._cursor_codec()
        filters = _filters(query)
        query_hash = _query_hash(filters)
        position = codec.decode(query.cursor, query_hash=query_hash) if query.cursor else None
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                configuration = active_analysis_configuration(session, self._runtime.settings)
                rows = PostgresContentQueryRepository(
                    session,
                    analysis_identity=configuration.identity,
                ).list_contents(
                    query=ContentReadQuery(
                        filters=filters,
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
                ContentCursorPosition(sort_at=last.sort_at, content_id=last.id),
                query_hash=query_hash,
            )
        return ContentListResponse(
            items=tuple(_item_response(item) for item in page),
            next_cursor=next_cursor,
            has_more=has_more,
        )

    def get_analysis_taxonomy(self) -> ContentAnalysisTaxonomyResponse:
        """返回数据库 active Scheme 的安全 Taxonomy 投影。"""

        configuration = self._load_active_analysis_configuration()
        return content_analysis_taxonomy_projection(configuration.taxonomy)

    def get_content(self, content_id: UUID) -> ContentDetailResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                configuration = active_analysis_configuration(session, self._runtime.settings)
                repository = PostgresContentQueryRepository(
                    session,
                    analysis_identity=configuration.identity,
                )
                record = repository.get_content(content_id)
                if record is None:
                    raise ContentResourceNotFound
                item = _item_response(record)
                return ContentDetailResponse(
                    **item.model_dump(),
                    media=repository.list_media(content_id),
                    comments=repository.list_comments(content_id),
                    comment_coverage=repository.latest_comment_coverage(content_id),
                    supplement_status=repository.latest_supplement_status(content_id),
                    source_records=repository.list_source_records(content_id),
                )
        finally:
            session.close()

    def review_vehicles(
        self,
        content_id: UUID,
        request: ContentVehicleReviewRequest,
        *,
        request_id: str,
        actor_ref: str,
    ) -> ContentVehicleReviewResponse:
        """人工确认当前内容版本车型，并写入同事务审计。"""

        session = self._runtime.database.new_session()
        try:
            with session.begin():
                current_version = session.scalar(
                    select(contents_table.c.current_version)
                    .where(contents_table.c.id == content_id)
                    .with_for_update()
                )
                if current_version is None:
                    raise ContentResourceNotFound
                if int(current_version) != request.content_version:
                    raise ContentAnalysisTargetChanged
                try:
                    PostgresVehicleCatalogRepository(session).replace_manual_evidence(
                        content_id=content_id,
                        content_version=request.content_version,
                        model_ids=request.vehicle_model_ids,
                        unlock_existing=request.unlock_existing,
                        actor_ref=actor_ref,
                    )
                except LookupError as exc:
                    raise ContentResourceNotFound from exc
                except RuntimeError as exc:
                    raise ContentAnalysisRunConflict from exc
                PostgresAuditRepository(session).append(
                    AuditEvent(
                        id=uuid4(),
                        actor_kind="principal",
                        actor_ref=actor_ref,
                        event_type="content_vehicle_reviewed",
                        object_type="content",
                        object_id=str(content_id),
                        request_id=request_id,
                        safe_detail={
                            "content_version": request.content_version,
                            "vehicle_model_ids": [str(item) for item in request.vehicle_model_ids],
                            "unlocked_existing": request.unlock_existing,
                        },
                        created_at=beijing_now(),
                    )
                )
                return ContentVehicleReviewResponse(
                    content_id=content_id,
                    content_version=request.content_version,
                    vehicle_model_ids=request.vehicle_model_ids,
                    manual_locked=not (request.unlock_existing and not request.vehicle_model_ids),
                )
        finally:
            session.close()

    def review_analysis(
        self,
        content_id: UUID,
        request: ContentAnalysisManualReviewRequest,
        *,
        request_id: str,
        actor_ref: str,
    ) -> ContentAnalysisManualReviewResponse:
        """人工纠正分析维度并保持原始 AI Result 不变。"""

        session = self._runtime.database.new_session()
        try:
            with session.begin():
                current_version = session.scalar(
                    select(contents_table.c.current_version)
                    .where(contents_table.c.id == content_id)
                    .with_for_update()
                )
                if current_version is None:
                    raise ContentResourceNotFound
                if int(current_version) != request.content_version:
                    raise ContentAnalysisTargetChanged
                configuration = active_analysis_configuration(session, self._runtime.settings)
                record = PostgresContentQueryRepository(
                    session,
                    analysis_identity=configuration.identity,
                ).get_content(content_id)
                if record is None:
                    raise ContentAnalysisRunConflict
                if record.analysis.status != "completed":
                    raise ContentAnalysisRunConflict
                taxonomy = configuration.taxonomy
                if (
                    request.voice_type is not None
                    and request.voice_type not in taxonomy.voice_types
                ):
                    raise ContentAnalysisRunConflict
                if request.sentiment is not None and request.sentiment not in taxonomy.sentiments:
                    raise ContentAnalysisRunConflict
                label_pairs = (
                    tuple((item.primary_label, item.secondary_label) for item in request.labels)
                    if request.labels is not None
                    else None
                )
                if label_pairs is not None and any(
                    primary not in taxonomy.labels or secondary not in taxonomy.labels[primary]
                    for primary, secondary in label_pairs
                ):
                    raise ContentAnalysisRunConflict
                try:
                    row = PostgresAnalysisManualReviewRepository(session).review(
                        content_id=content_id,
                        content_version=request.content_version,
                        voice_type=request.voice_type,
                        sentiment=request.sentiment,
                        labels=label_pairs,
                        unlock_dimensions=tuple(request.unlock_dimensions),
                        actor_ref=actor_ref,
                    )
                except RuntimeError as exc:
                    raise ContentAnalysisRunConflict from exc
                locked_dimensions = tuple(
                    dimension
                    for dimension in ("voice_type", "sentiment", "labels")
                    if bool(row[f"{dimension}_locked"])
                )
                _manual_labels = tuple(
                    AnalysisManualLabelRequest.model_validate(item)
                    for item in cast(list[dict[str, str]], row["labels"])
                )
                PostgresAuditRepository(session).append(
                    AuditEvent(
                        id=uuid4(),
                        actor_kind="principal",
                        actor_ref=actor_ref,
                        event_type="content_analysis_manually_reviewed",
                        object_type="content",
                        object_id=str(content_id),
                        request_id=request_id,
                        safe_detail=cast(
                            Any,
                            {
                                "content_version": request.content_version,
                                "locked_dimensions": list(locked_dimensions),
                                "unlocked_dimensions": list(request.unlock_dimensions),
                            },
                        ),
                        created_at=beijing_now(),
                    )
                )
                return ContentAnalysisManualReviewResponse(
                    content_id=content_id,
                    content_version=request.content_version,
                    voice_type=cast(str | None, row["voice_type"]),
                    sentiment=cast(str | None, row["sentiment"]),
                    labels=_manual_labels,
                    locked_dimensions=cast(Any, locked_dimensions),
                )
        finally:
            session.close()

    def create_analysis(
        self,
        request: ContentAnalysisSubmitRequest,
        *,
        request_id: str,
    ) -> ContentAnalysisCreatedResponse:
        preview = self._preview_analysis_targets(request.targets)
        created, first_request_id, first_job_id = self._create_analysis_run(
            client_idempotency_key=f"legacy-analysis:{uuid4()}",
            targets=request.targets,
            expected_target_count=preview.target_count,
            expected_configuration_hash=preview.configuration_hash,
            run_intent="manual_reanalysis",
            request_id=request_id,
            freeze_in_http=True,
        )
        if first_request_id is None or first_job_id is None:
            raise ContentAnalysisRunConflict
        return ContentAnalysisCreatedResponse(
            request_id=first_request_id,
            job_id=first_job_id,
            target_count=created.target_count,
            run_id=created.run_id,
            shard_count=created.shard_count,
        )

    def preview_analysis_run(
        self,
        request: AnalysisContentRunPreviewRequest,
    ) -> AnalysisContentRunPreviewResponse:
        return self._preview_analysis_targets(request.targets)

    def _preview_analysis_targets(
        self,
        targets: _AnalysisTargetSelection,
    ) -> AnalysisContentRunPreviewResponse:
        generation_config, generation_hash = current_analysis_generation_config()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                configuration = active_analysis_configuration(session, self._runtime.settings)
                identity = configuration.identity
                if identity is None:
                    raise ContentAnalysisUnavailable
                if isinstance(targets, AnalysisRunTargetSelection) and targets.scope == "all":
                    target_count = PostgresContentQueryRepository(
                        session,
                        analysis_identity=None,
                    ).count_all_analysis_targets()
                else:
                    target_statement = self._analysis_target_statement(
                        session,
                        targets,
                        analysis_identity=identity,
                    )
                    target_count = PostgresAnalysisRepository(session).count_targets(
                        target_statement
                    )
                if target_count == 0:
                    raise ContentSelectionEmpty
        finally:
            session.close()
        shard_size = self._runtime.settings.analysis_run_shard_size
        return AnalysisContentRunPreviewResponse(
            target_count=target_count,
            shard_count=ceil(target_count / shard_size),
            shard_size=shard_size,
            analysis_scheme_version_id=configuration.scheme.id,
            prompt_version=identity.prompt_version,
            prompt_sha256=identity.prompt_sha256,
            taxonomy_sha256=identity.taxonomy_sha256,
            model_provider=identity.model_provider,
            model=identity.model,
            generation_config=generation_config,
            generation_config_hash=generation_hash,
            configuration_hash=_analysis_configuration_hash(
                prompt_version=identity.prompt_version,
                prompt_sha256=identity.prompt_sha256,
                taxonomy_sha256=identity.taxonomy_sha256,
                model_provider=identity.model_provider,
                model=identity.model,
                generation_config_hash=generation_hash,
            ),
            cost_estimate_available=False,
            cost_estimate_note=(
                "当前适配器没有与模型匹配的逐内容 tokenizer，不能伪造总费用；"
                "页面展示冻结目标数、模型和实际生成参数，运行后以真实 token/cost 审计为准。"
            ),
        )

    def create_analysis_run(
        self,
        request: AnalysisContentRunCreateRequest,
        *,
        request_id: str,
    ) -> AnalysisContentRunCreatedResponse:
        created, _, _ = self._create_analysis_run(
            client_idempotency_key=request.client_idempotency_key,
            targets=request.targets,
            expected_target_count=request.expected_target_count,
            expected_configuration_hash=request.expected_configuration_hash,
            run_intent=request.run_intent,
            request_id=request_id,
            freeze_in_http=False,
        )
        return created

    def list_analysis_runs(self) -> AnalysisContentRunListResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresAnalysisRepository(session)
                return AnalysisContentRunListResponse(
                    items=tuple(
                        _analysis_run_response(repository, row, include_shards=False)
                        for row in repository.list_runs()
                    )
                )
        finally:
            session.close()

    def get_analysis_run(self, run_id: UUID) -> AnalysisContentRunResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresAnalysisRepository(session)
                run = repository.get_run(run_id)
                if run is None:
                    raise ContentResourceNotFound
                return _analysis_run_response(repository, run, include_shards=True)
        finally:
            session.close()

    def cancel_analysis_run(
        self,
        run_id: UUID,
        *,
        request_id: str,
    ) -> AnalysisContentRunResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresAnalysisRepository(session)
                try:
                    repository.request_run_cancel(run_id)
                except AnalysisRequestNotFound as exc:
                    raise ContentResourceNotFound from exc
                except AnalysisRunStateConflict as exc:
                    raise ContentAnalysisRunConflict from exc
                self._audit_analysis_run(
                    session,
                    event_type="analysis_run_cancel_requested",
                    run_id=run_id,
                    request_id=request_id,
                    detail={},
                )
                run = repository.get_run(run_id)
                if run is None:
                    raise ContentResourceNotFound
                return _analysis_run_response(repository, run, include_shards=True)
        finally:
            session.close()

    def _create_analysis_run(
        self,
        *,
        client_idempotency_key: str,
        targets: _AnalysisTargetSelection,
        expected_target_count: int,
        expected_configuration_hash: str,
        run_intent: str,
        request_id: str,
        freeze_in_http: bool,
    ) -> tuple[AnalysisContentRunCreatedResponse, UUID | None, UUID | None]:
        configuration = self._load_active_analysis_configuration()
        identity = configuration.identity
        llm_provider = configuration.llm_provider
        if identity is None or llm_provider is None:
            raise ContentAnalysisUnavailable
        generation_config, generation_hash = current_analysis_generation_config()
        configuration_hash = _analysis_configuration_hash(
            prompt_version=identity.prompt_version,
            prompt_sha256=identity.prompt_sha256,
            taxonomy_sha256=identity.taxonomy_sha256,
            model_provider=identity.model_provider,
            model=identity.model,
            generation_config_hash=generation_hash,
        )
        if configuration_hash != expected_configuration_hash:
            raise ContentAnalysisRunConflict
        shard_size = self._runtime.settings.analysis_run_shard_size
        filter_snapshot = _analysis_filter_snapshot(targets)
        storage_scope = _analysis_storage_scope(targets)
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresAnalysisRepository(session)
                existing = repository.get_run_by_client_key(client_idempotency_key)
                if existing is not None:
                    _assert_same_analysis_run_request(
                        existing,
                        expected_target_count=expected_target_count,
                        expected_configuration_hash=expected_configuration_hash,
                        run_intent=run_intent,
                        scope=storage_scope,
                        filter_snapshot=filter_snapshot,
                    )
                    existing_shards = repository.list_run_shards(cast(UUID, existing["id"]))
                    if freeze_in_http and not existing_shards:
                        raise ContentAnalysisRunConflict
                    first_shard = existing_shards[0] if existing_shards else None
                    return (
                        AnalysisContentRunCreatedResponse(
                            run_id=cast(UUID, existing["id"]),
                            planner_job_id=cast(UUID, existing["planner_job_id"]),
                            target_count=cast(int, existing["target_count"]),
                            shard_count=cast(int, existing["shard_count"]),
                        ),
                        cast(UUID, first_shard["request_id"]) if first_shard else None,
                        cast(UUID, first_shard["job_id"]) if first_shard else None,
                    )
                shard_count = ceil(expected_target_count / shard_size)
                run_id = uuid5(_ANALYSIS_RUN_ID_NAMESPACE, client_idempotency_key)
                planner_job = PostgresJobRepository(session).enqueue(
                    job_type=CONTENT_ANALYSIS_PLAN_JOB_TYPE,
                    payload_version=CONTENT_ANALYSIS_PLAN_JOB_PAYLOAD_VERSION,
                    payload=ContentAnalysisPlanJobPayload(run_id=run_id).model_dump(mode="json"),
                    internal_idempotency_key=f"content-analysis-run:{run_id}:planner",
                    request_id=request_id,
                    priority=0,
                    max_attempts=CONTENT_ANALYSIS_PLAN_JOB_MAX_ATTEMPTS,
                    timeout_seconds=CONTENT_ANALYSIS_PLAN_JOB_TIMEOUT_SECONDS,
                )
                run = repository.create_run_header(
                    run_id=run_id,
                    client_idempotency_key=client_idempotency_key,
                    planner_job_id=planner_job.id,
                    run_intent=run_intent,
                    scope=storage_scope,
                    filter_snapshot=filter_snapshot,
                    target_count=expected_target_count,
                    shard_count=shard_count,
                    shard_size=shard_size,
                    identity=identity,
                    analysis_scheme_version_id=configuration.scheme.id,
                    prompt_text_snapshot=configuration.taxonomy.prompt_text,
                    generation_config=generation_config,
                    generation_config_hash=generation_hash,
                    runtime_config_snapshot=cast(
                        dict[str, object],
                        llm_provider.safe_runtime_snapshot(),
                    ),
                )
                if run is None:
                    existing = repository.get_run_by_client_key(client_idempotency_key)
                    if existing is None:
                        raise ContentAnalysisRunConflict
                    _assert_same_analysis_run_request(
                        existing,
                        expected_target_count=expected_target_count,
                        expected_configuration_hash=expected_configuration_hash,
                        run_intent=run_intent,
                        scope=storage_scope,
                        filter_snapshot=filter_snapshot,
                    )
                    existing_shards = repository.list_run_shards(cast(UUID, existing["id"]))
                    if freeze_in_http and not existing_shards:
                        raise ContentAnalysisRunConflict
                    first_shard = existing_shards[0] if existing_shards else None
                    return (
                        AnalysisContentRunCreatedResponse(
                            run_id=cast(UUID, existing["id"]),
                            planner_job_id=cast(UUID, existing["planner_job_id"]),
                            target_count=cast(int, existing["target_count"]),
                            shard_count=cast(int, existing["shard_count"]),
                        ),
                        cast(UUID, first_shard["request_id"]) if first_shard else None,
                        cast(UUID, first_shard["job_id"]) if first_shard else None,
                    )
                if not freeze_in_http:
                    self._audit_analysis_run(
                        session,
                        event_type="analysis_run_created",
                        run_id=run_id,
                        request_id=request_id,
                        detail={
                            "target_count": expected_target_count,
                            "shard_count": shard_count,
                        },
                    )
                    return (
                        AnalysisContentRunCreatedResponse(
                            run_id=run_id,
                            planner_job_id=planner_job.id,
                            target_count=expected_target_count,
                            shard_count=shard_count,
                        ),
                        None,
                        None,
                    )
                target_statement = self._analysis_target_statement(
                    session,
                    targets,
                    analysis_identity=identity,
                )
                frozen_count = repository.freeze_run_targets(
                    run_id=run_id,
                    target_statement=target_statement,
                )
                if frozen_count == 0:
                    raise ContentSelectionEmpty
                if frozen_count != expected_target_count:
                    raise ContentAnalysisTargetChanged
                first_request_id = uuid4()
                first_job = PostgresJobRepository(session).enqueue(
                    job_type=CONTENT_ANALYSIS_JOB_TYPE,
                    payload_version=CONTENT_ANALYSIS_JOB_PAYLOAD_VERSION,
                    payload=ContentAnalysisJobPayload(
                        request_id=first_request_id,
                        run_id=run_id,
                        shard_no=0,
                    ).model_dump(mode="json"),
                    internal_idempotency_key=f"content-analysis-run:{run_id}:shard:0",
                    request_id=request_id,
                    priority=0,
                    max_attempts=CONTENT_ANALYSIS_JOB_MAX_ATTEMPTS,
                    timeout_seconds=CONTENT_ANALYSIS_JOB_TIMEOUT_SECONDS,
                )
                repository.create_run_shard(
                    run_id=run_id,
                    request_id=first_request_id,
                    job_id=first_job.id,
                    shard_no=0,
                )
                self._audit_analysis_run(
                    session,
                    event_type="analysis_run_created",
                    run_id=run_id,
                    request_id=request_id,
                    detail={
                        "target_count": frozen_count,
                        "shard_count": shard_count,
                    },
                )
                return (
                    AnalysisContentRunCreatedResponse(
                        run_id=run_id,
                        planner_job_id=planner_job.id,
                        target_count=frozen_count,
                        shard_count=shard_count,
                    ),
                    first_request_id,
                    first_job.id,
                )
        finally:
            session.close()

    @staticmethod
    def _audit_analysis_run(
        session: Session,
        *,
        event_type: str,
        run_id: UUID,
        request_id: str,
        detail: dict[str, object],
    ) -> None:
        """记录 Analysis Run 高价值管理动作，不保存目标正文或模型输出。"""

        PostgresAuditRepository(session).append(
            AuditEvent(
                id=uuid4(),
                actor_kind="system",
                actor_ref=None,
                event_type=event_type,
                object_type="analysis_content_run",
                object_id=str(run_id),
                request_id=request_id,
                safe_detail=cast(Any, detail),
                created_at=beijing_now(),
            )
        )

    def _analysis_target_statement(
        self,
        session: Session,
        targets: _AnalysisTargetSelection,
        *,
        analysis_identity: Any,
    ) -> Any:
        repository = PostgresContentQueryRepository(session, analysis_identity=analysis_identity)
        if isinstance(targets, AnalysisRunTargetSelection) and targets.scope == "all":
            raise ValueError("all Scope 只能由 Planner 有界冻结")
        if isinstance(targets, ContentTargetSelection) and targets.scope == "query":
            return repository.freeze_target_statement(
                filters=targets.filters or ContentFilterSnapshot()
            )
        return repository.freeze_target_statement(content_ids=targets.content_ids)

    def review_relevance(
        self,
        request: ContentRelevanceReviewRequest,
        *,
        request_id: str,
    ) -> ContentRelevanceReviewResponse:
        """保存双向人工相关性覆盖或撤销事件，保留 AI 原始结果。"""

        session = self._runtime.database.new_session()
        try:
            with session.begin():
                configuration = active_analysis_configuration(session, self._runtime.settings)
                summary = PostgresContentRelevanceReviewRepository(session).review_relevance(
                    content_ids=request.content_ids,
                    decision=request.decision,
                    analysis_identity=configuration.identity,
                    request_id=request_id,
                )
                return ContentRelevanceReviewResponse(
                    requested_count=summary.requested_count,
                    changed_count=summary.changed_count,
                    unchanged_count=summary.unchanged_count,
                )
        finally:
            session.close()

    def _load_active_analysis_configuration(self) -> ActiveAnalysisConfiguration:
        """在短事务中读取并验证当前 Scheme，首次 bootstrap 会连同审计提交。"""

        session = self._runtime.database.new_session()
        try:
            with session.begin():
                return active_analysis_configuration(session, self._runtime.settings)
        finally:
            session.close()

    def get_analysis_job(self, job_id: UUID) -> JobStatusResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                job = PostgresJobRepository(session).get(job_id)
                if job is None or job.job_type not in {
                    CONTENT_ANALYSIS_JOB_TYPE,
                    CONTENT_ANALYSIS_PLAN_JOB_TYPE,
                }:
                    raise ContentResourceNotFound
                return _analysis_job_response(
                    job,
                    parse_analysis_result=job.job_type == CONTENT_ANALYSIS_JOB_TYPE,
                )
        finally:
            session.close()

    def _cursor_codec(self) -> ContentCursorCodec:
        secret = self._cursor_signing_secret
        if secret is None:
            try:
                secret = (
                    read_secret_file(
                        self._runtime.settings.content_cursor_signing_key_file,
                        root=self._runtime.settings.secret_dir,
                    )
                    .get_secret_value()
                    .encode("utf-8")
                )
            except SecretFileError as exc:
                raise ContentCursorUnavailable from exc
        try:
            return ContentCursorCodec(secret=secret)
        except ValueError as exc:
            raise ContentCursorUnavailable from exc


def _filters(query: ContentListQuery) -> ContentFilterSnapshot:
    return ContentFilterSnapshot.model_validate(query.model_dump(exclude={"cursor", "limit"}))


def _analysis_filter_snapshot(targets: _AnalysisTargetSelection) -> dict[str, object]:
    if isinstance(targets, AnalysisRunTargetSelection) and targets.scope == "all":
        return analysis_all_scope_filter_snapshot()
    if isinstance(targets, ContentTargetSelection) and targets.scope == "query":
        return (targets.filters or ContentFilterSnapshot()).model_dump(mode="json")
    return {"content_ids": [str(item) for item in targets.content_ids]}


def _analysis_storage_scope(targets: _AnalysisTargetSelection) -> Literal["query", "selected"]:
    """公开 all 复用数据库既有 query Scope；内部快照负责区分语义。"""

    if isinstance(targets, AnalysisRunTargetSelection) and targets.scope == "all":
        return "query"
    return cast(Literal["query", "selected"], targets.scope)


def _analysis_response_scope(row: RowMapping) -> Literal["all", "query", "selected"]:
    """只有新 all 专用内部标记投影为 all；历史空 query 保持 query。"""

    stored_scope = cast(Literal["query", "selected"], row["scope"])
    if stored_scope == "query" and is_analysis_all_scope_filter_snapshot(row["filter_snapshot"]):
        return "all"
    return stored_scope


def _analysis_configuration_hash(
    *,
    prompt_version: str,
    prompt_sha256: str,
    taxonomy_sha256: str,
    model_provider: str,
    model: str,
    generation_config_hash: str,
) -> str:
    payload = {
        "generation_config_hash": generation_config_hash,
        "model": model,
        "model_provider": model_provider,
        "prompt_sha256": prompt_sha256,
        "prompt_version": prompt_version,
        "taxonomy_sha256": taxonomy_sha256,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _assert_same_analysis_run_request(
    row: RowMapping,
    *,
    expected_target_count: int,
    expected_configuration_hash: str,
    run_intent: str,
    scope: str,
    filter_snapshot: dict[str, object],
) -> None:
    actual_configuration_hash = _analysis_configuration_hash(
        prompt_version=cast(str, row["prompt_version"]),
        prompt_sha256=cast(str, row["prompt_sha256"]),
        taxonomy_sha256=cast(str, row["taxonomy_sha256"]),
        model_provider=cast(str, row["model_provider"]),
        model=cast(str, row["model"]),
        generation_config_hash=cast(str, row["generation_config_hash"]),
    )
    if (
        row["target_count"] != expected_target_count
        or row["run_intent"] != run_intent
        or row["scope"] != scope
        or row["filter_snapshot"] != filter_snapshot
        or actual_configuration_hash != expected_configuration_hash
    ):
        raise ContentAnalysisRunConflict


def _analysis_run_response(
    repository: PostgresAnalysisRepository,
    row: RowMapping,
    *,
    include_shards: bool,
) -> AnalysisContentRunResponse:
    shards = repository.list_run_shards(cast(UUID, row["id"])) if include_shards else ()
    return AnalysisContentRunResponse(
        id=cast(UUID, row["id"]),
        planner_job_id=cast(UUID, row["planner_job_id"]),
        sequence_no=cast(int, row["sequence_no"]),
        status=cast(AnalysisRunStatus, row["status"]),
        run_intent=cast(AnalysisRunIntent, row["run_intent"]),
        scope=_analysis_response_scope(row),
        target_count=cast(int, row["target_count"]),
        shard_count=cast(int, row["shard_count"]),
        shard_size=cast(int, row["shard_size"]),
        analysis_scheme_version_id=cast(UUID | None, row["analysis_scheme_version_id"]),
        prompt_version=cast(str, row["prompt_version"]),
        prompt_sha256=cast(str, row["prompt_sha256"]),
        taxonomy_sha256=cast(str, row["taxonomy_sha256"]),
        model_provider=cast(str, row["model_provider"]),
        model=cast(str, row["model"]),
        generation_config=cast(dict[str, object], row["generation_config"]),
        generation_config_hash=cast(str, row["generation_config_hash"]),
        error_code=cast(str | None, row["error_code"]),
        stats=AnalysisContentRunStatsResponse.model_validate(
            repository.run_stats(cast(UUID, row["id"]))
        ),
        shards=tuple(
            AnalysisContentRunShardResponse(
                request_id=cast(UUID, shard["request_id"]),
                job_id=cast(UUID, shard["job_id"]),
                shard_no=cast(int, shard["shard_no"]),
                target_count=cast(int, shard["target_count"]),
                status=cast(str, shard["status"]),
                progress=cast(int, shard["progress"]),
                error_code=cast(str | None, shard["error_code"]),
            )
            for shard in shards
        ),
        created_at=row["created_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
    )


def _query_hash(filters: ContentFilterSnapshot) -> str:
    payload = filters.model_dump(mode="json", exclude_none=True)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _item_response(record: ContentReadRecord) -> ContentListItemResponse:
    return ContentListItemResponse(
        id=record.id,
        content_version=record.current_version,
        platform=record.platform,
        external_content_id=record.external_content_id,
        content_type=record.content_type,
        title=record.title,
        text=record.text,
        author_display_name=record.author_display_name,
        published_at=record.published_at,
        last_seen_at=record.last_seen_at,
        content_url=record.canonical_url or record.share_url,
        metrics=ContentMetricsResponse.model_validate(record.metrics),
        analysis=ContentAnalysisResponse(
            status=cast(ContentAnalysisStatus, record.analysis.status),
            relevance=cast(ContentRelevance | None, record.analysis.relevance),
            voice_type=record.analysis.voice_type,
            sentiment=record.analysis.sentiment,
            labels=tuple(
                ContentLabelPairResponse(primary_label=primary, secondary_label=secondary)
                for primary, secondary in record.analysis.labels
            ),
            analyzed_at=record.analysis.analyzed_at,
            model_provider=record.analysis.model_provider,
            model=record.analysis.model,
            latest_run_id=record.analysis.latest_run_id,
            latest_run_status=record.analysis.latest_run_status,
            manual_locked_dimensions=cast(Any, record.analysis.manual_locked_dimensions),
        ),
        effective_relevance=cast(ContentRelevance | None, record.effective_relevance),
        relevance_source=cast(ContentRelevanceSource | None, record.relevance_source),
        source=ContentSourceResponse(
            provider_name=record.source.provider_name,
            provider_attempt_id=record.source.provider_attempt_id,
            raw_artifact_id=record.source.raw_artifact_id,
            import_batch_id=record.source.import_batch_id,
            collection_run_id=record.source.collection_run_id,
        ),
        vehicles=tuple(
            ContentVehicleResponse(
                vehicle_model_id=vehicle.vehicle_model_id,
                code=vehicle.code,
                display_name=vehicle.display_name,
                evidences=tuple(
                    ContentVehicleEvidenceResponse(
                        source=cast(Any, evidence.source),
                        matched_text=evidence.matched_text,
                        source_field=evidence.source_field,
                        catalog_version=evidence.catalog_version,
                        confidence=evidence.confidence,
                        is_manual_locked=evidence.is_manual_locked,
                    )
                    for evidence in vehicle.evidences
                ),
            )
            for vehicle in record.vehicles
        ),
        availability=(
            ContentAvailabilityResponse(
                status=cast(Any, record.availability.status),
                reason_code=record.availability.reason_code,
                evidence_kind=record.availability.evidence_kind,
                observed_at=record.availability.observed_at,
            )
            if record.availability is not None
            else None
        ),
    )


def _analysis_job_response(
    job: JobRecord,
    *,
    parse_analysis_result: bool = True,
) -> JobStatusResponse:
    result = (
        ContentAnalysisJobResultResponse.model_validate(job.result)
        if parse_analysis_result and isinstance(job.result, dict)
        else None
    )
    return JobStatusResponse(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        attempt=job.attempt,
        max_attempts=job.max_attempts,
        progress=job.progress,
        error_code=job.error_code,
        result=result,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


__all__ = ["PostgresContentHttpService"]
