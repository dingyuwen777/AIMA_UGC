"""Collection live runtime 的 Fenced Provider Request/Attempt 准备与 Scope 执行事实读取。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from aima_ugc.contracts.provider import ProviderBillingV1, ProviderRequestV1
from aima_ugc.modules.collection.candidate_tables import (
    collection_candidate_ingestions_table,
    collection_candidates_table,
)
from aima_ugc.modules.collection.provider_persistence import (
    PreparedProviderAttempt,
    ProviderAttemptRecord,
    ProviderPersistenceConflictError,
    ProviderPersistenceService,
)
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.tables import comments_table
from aima_ugc.platform.jobs import JobExecutionFence, LeaseLostError

from .jobs import PostgresJobRepository
from .provider import PostgresProviderRepository


@dataclass(frozen=True, slots=True)
class CollectionScopeExecutionCounts:
    """由 Provider Attempt/Candidate Ingestion durable 事实聚合的 Scope 计数。"""

    requested_count: int
    succeeded_count: int
    failed_count: int
    content_count: int
    comment_count: int
    root_comment_count: int
    reply_count: int


def read_collection_scope_execution_counts(
    session: Session, *, scope_id: UUID
) -> CollectionScopeExecutionCounts:
    """聚合已提交的执行事实；调用方负责持有当前 Job 或终态结算事务锁。"""
    attempts = session.execute(
        select(
            provider_request_attempts_table.c.dispatch_status,
            provider_request_attempts_table.c.error_code,
        )
        .select_from(
            provider_request_attempts_table.join(
                provider_requests_table,
                provider_request_attempts_table.c.provider_request_id
                == provider_requests_table.c.id,
            )
        )
        .where(provider_requests_table.c.scope_id == scope_id)
    ).all()
    requested_count = sum(status != "reserved" for status, _ in attempts)
    succeeded_count = sum(
        status == "completed" and error_code is None for status, error_code in attempts
    )
    failed_count = sum(
        status in {"not_sent", "unknown"} or (status == "completed" and error_code is not None)
        for status, error_code in attempts
    )

    def target_count(kind: str, *, reply: bool | None = None) -> int:
        target_column = (
            collection_candidate_ingestions_table.c.content_id
            if kind == "content"
            else collection_candidate_ingestions_table.c.comment_id
        )
        source = (
            collection_candidate_ingestions_table.join(
                collection_candidates_table,
                collection_candidate_ingestions_table.c.candidate_id
                == collection_candidates_table.c.id,
            )
            .join(
                provider_request_attempts_table,
                collection_candidates_table.c.provider_request_attempt_id
                == provider_request_attempts_table.c.id,
            )
            .join(
                provider_requests_table,
                provider_request_attempts_table.c.provider_request_id
                == provider_requests_table.c.id,
            )
        )
        if reply is not None:
            source = source.join(
                comments_table,
                collection_candidate_ingestions_table.c.comment_id == comments_table.c.id,
            )
        query = (
            select(func.count(func.distinct(target_column)))
            .select_from(source)
            .where(
                provider_requests_table.c.scope_id == scope_id,
                collection_candidates_table.c.item_kind == kind,
                collection_candidate_ingestions_table.c.result.in_(("ingested", "duplicate")),
                target_column.is_not(None),
            )
        )
        if reply is not None:
            is_reply = or_(
                comments_table.c.parent_comment_id.is_not(None),
                and_(
                    comments_table.c.root_comment_id.is_not(None),
                    comments_table.c.root_comment_id != comments_table.c.external_comment_id,
                ),
            )
            query = query.where(
                is_reply
                if reply
                else and_(
                    comments_table.c.parent_comment_id.is_(None),
                    or_(
                        comments_table.c.root_comment_id.is_(None),
                        comments_table.c.root_comment_id == comments_table.c.external_comment_id,
                    ),
                )
            )
        value = session.scalar(query)
        return int(value or 0)

    return CollectionScopeExecutionCounts(
        requested_count=requested_count,
        succeeded_count=succeeded_count,
        failed_count=failed_count,
        content_count=target_count("content"),
        comment_count=target_count("comment"),
        root_comment_count=target_count("comment", reply=False),
        reply_count=target_count("comment", reply=True),
    )


class PostgresFencedProviderAttemptPreparer:
    """在任何 Provider Request/Attempt 写入前验证当前 Job Fence 与 Scope 归属。"""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def has_scope_request(
        self,
        *,
        scope_id: UUID,
        request_fingerprint: str,
        fence: JobExecutionFence,
    ) -> bool:
        """只在当前 Job 持有 Scope 时查询已有逻辑请求。"""
        session = self._session_factory()
        try:
            with session.begin():
                PostgresJobRepository(session).lock_current_execution(fence)
                owner_job_id = session.scalar(
                    select(collection_runs_table.c.job_id)
                    .select_from(
                        collection_scopes_table.join(
                            collection_runs_table,
                            collection_scopes_table.c.run_id == collection_runs_table.c.id,
                        )
                    )
                    .where(collection_scopes_table.c.id == scope_id)
                )
                if owner_job_id != fence.job_id:
                    raise LeaseLostError("Collection Scope 不属于当前 Job Fence")
                return (
                    session.scalar(
                        select(provider_requests_table.c.id).where(
                            provider_requests_table.c.scope_id == scope_id,
                            provider_requests_table.c.request_fingerprint == request_fingerprint,
                        )
                    )
                    is not None
                )
        finally:
            session.close()

    def prepare_billable_attempt(
        self,
        *,
        request: ProviderRequestV1,
        provider_config_id: UUID,
        attempt_id: UUID,
        billing: ProviderBillingV1,
        fence: JobExecutionFence,
    ) -> PreparedProviderAttempt:
        session = self._session_factory()
        try:
            with session.begin():
                PostgresJobRepository(session).lock_current_execution(fence)
                media_refresh = self._require_request_scope(session, request=request, fence=fence)
                repository = PostgresProviderRepository(session)
                service = ProviderPersistenceService(repository)
                if media_refresh:
                    persisted = service.ensure_request(
                        request, provider_config_id=provider_config_id
                    )
                    attempts = repository.list_attempts(persisted.id)
                    if attempts:
                        return PreparedProviderAttempt(
                            request=persisted,
                            attempt=max(attempts, key=lambda item: item.attempt_no),
                        )
                return service.prepare_billable_attempt(
                    request=request,
                    provider_config_id=provider_config_id,
                    attempt_id=attempt_id,
                    billing=billing,
                )
        finally:
            session.close()

    def resolve_or_prepare_billable_attempt(
        self,
        *,
        request: ProviderRequestV1,
        provider_config_id: UUID,
        attempt_id: UUID,
        billing: ProviderBillingV1,
        fence: JobExecutionFence,
    ) -> PreparedProviderAttempt:
        """恢复时复用同一逻辑 Request 的成功 Raw 或尚未发送的 reserved Attempt。"""
        session = self._session_factory()
        try:
            with session.begin():
                PostgresJobRepository(session).lock_current_execution(fence)
                media_refresh = self._require_request_scope(session, request=request, fence=fence)

                repository = PostgresProviderRepository(session)
                service = ProviderPersistenceService(repository)
                persisted_request = service.ensure_request(
                    request,
                    provider_config_id=provider_config_id,
                )
                attempts = repository.list_attempts(persisted_request.id)
                dispatching_attempts = [
                    attempt for attempt in attempts if attempt.dispatch_status == "dispatching"
                ]
                if dispatching_attempts:
                    raise ProviderPersistenceConflictError(
                        "同一 Provider Request 存在未收敛的 dispatching Attempt，"
                        "必须先执行 Recovery"
                    )

                successful_attempts = [
                    attempt
                    for attempt in attempts
                    if attempt.dispatch_status == "completed"
                    and attempt.error_code is None
                    and attempt.raw_artifact_id is not None
                ]
                if successful_attempts:
                    successful = max(successful_attempts, key=lambda item: item.attempt_no)
                    if any(item.attempt_no > successful.attempt_no for item in attempts):
                        raise ProviderPersistenceConflictError(
                            "成功 Provider Attempt 之后存在额外执行事实，无法静默选择重发"
                        )
                    return PreparedProviderAttempt(
                        request=persisted_request,
                        attempt=successful,
                    )

                # v6 一次发送预算覆盖 Provider 重试；unknown/失败不能隐式第二次收费。
                if media_refresh and attempts:
                    return PreparedProviderAttempt(
                        request=persisted_request,
                        attempt=max(attempts, key=lambda item: item.attempt_no),
                    )

                if attempts:
                    latest_attempt = max(attempts, key=lambda item: item.attempt_no)
                    state = (
                        session.scalar(
                            select(collection_scopes_table.c.pagination_state).where(
                                collection_scopes_table.c.id == request.scope_id
                            )
                        )
                        or {}
                    )
                    manual_after = state.get("_account_manual_retry_after")
                    manual_retry = isinstance(
                        manual_after, str
                    ) and latest_attempt.created_at < datetime.fromisoformat(manual_after)
                    if (
                        latest_attempt.dispatch_status != "reserved"
                        and not _attempt_allows_retry(latest_attempt)
                        and not manual_retry
                    ):
                        return PreparedProviderAttempt(
                            request=persisted_request,
                            attempt=latest_attempt,
                        )

                reserved_attempts = [
                    attempt for attempt in attempts if attempt.dispatch_status == "reserved"
                ]
                if len(reserved_attempts) > 1:
                    raise ProviderPersistenceConflictError(
                        "同一 Provider Request 存在多个 reserved Attempt，无法安全恢复"
                    )

                resolved_attempt_id = reserved_attempts[0].id if reserved_attempts else attempt_id
                return service.prepare_billable_attempt(
                    request=request,
                    provider_config_id=provider_config_id,
                    attempt_id=resolved_attempt_id,
                    billing=billing,
                )
        finally:
            session.close()

    def read_scope_counts(
        self,
        *,
        scope_id: UUID,
        fence: JobExecutionFence,
    ) -> CollectionScopeExecutionCounts:
        """从数据库执行事实聚合计数，避免进程崩溃造成内存统计丢失。"""
        session = self._session_factory()
        try:
            with session.begin():
                PostgresJobRepository(session).lock_current_execution(fence)
                ownership = session.execute(
                    select(collection_runs_table.c.job_id)
                    .select_from(
                        collection_scopes_table.join(
                            collection_runs_table,
                            collection_scopes_table.c.run_id == collection_runs_table.c.id,
                        )
                    )
                    .where(collection_scopes_table.c.id == scope_id)
                ).scalar_one_or_none()
                if ownership != fence.job_id:
                    raise LeaseLostError("Collection Scope 不属于当前 Job Fence")

                return read_collection_scope_execution_counts(session, scope_id=scope_id)
        finally:
            session.close()

    @staticmethod
    def _require_request_scope(
        session: Session,
        *,
        request: ProviderRequestV1,
        fence: JobExecutionFence,
    ) -> bool:
        ownership = session.execute(
            select(
                collection_scopes_table.c.run_id,
                collection_scopes_table.c.platform,
                collection_runs_table.c.job_id,
                collection_runs_table.c.config_snapshot,
                collection_scopes_table.c.source_type,
                collection_scopes_table.c.source_value,
                collection_scopes_table.c.operation_group,
            )
            .select_from(
                collection_scopes_table.join(
                    collection_runs_table,
                    collection_scopes_table.c.run_id == collection_runs_table.c.id,
                )
            )
            .where(collection_scopes_table.c.id == request.scope_id)
            .with_for_update(of=collection_scopes_table)
        ).one_or_none()
        if ownership is None:
            raise LeaseLostError("Provider Request Scope 不属于当前 Job Fence")
        if (
            ownership.run_id != request.run_id
            or ownership.platform != request.platform
            or ownership.job_id != fence.job_id
        ):
            raise LeaseLostError("Provider Request Scope 不属于当前 Job Fence")
        snapshot = ownership.config_snapshot
        if (
            snapshot.get("mode") != "media_refresh"
            and snapshot.get("schema_version") != "collection-run-config.v6"
        ):
            return False
        from aima_ugc.adapters.providers.tikhub.operations.xiaohongshu import (
            build_video_detail_request,
        )
        from aima_ugc.modules.collection.media_refresh import validate_media_refresh_snapshot

        target = validate_media_refresh_snapshot(snapshot)
        operation = build_video_detail_request(note_id=target.note_id)
        if (
            request.platform != "xiaohongshu"
            or request.provider != "tikhub"
            or request.operation != "get_video_note_detail"
            or ownership.source_type != "content"
            or ownership.source_value != str(target.content_id)
            or ownership.operation_group != "media_refresh"
            or request.request_params
            != {"method": "GET", "path": operation.path, "params": dict(operation.params)}
            or request.pagination_input != {}
        ):
            raise ProviderPersistenceConflictError(
                "media_refresh Request 不符合冻结的唯一视频详情调用"
            )
        others = session.scalar(
            select(provider_requests_table.c.id)
            .where(
                provider_requests_table.c.scope_id == request.scope_id,
                provider_requests_table.c.request_fingerprint != request.request_fingerprint,
            )
            .limit(1)
        )
        if others is not None:
            raise ProviderPersistenceConflictError(
                "media_refresh Scope 只允许一个逻辑 Provider Request"
            )
        return True


_RETRYABLE_HTTP_STATUSES = {408, 425, 429}


def _attempt_allows_retry(attempt: ProviderAttemptRecord) -> bool:
    if attempt.dispatch_status in {"not_sent", "unknown"}:
        return True
    if attempt.dispatch_status != "completed" or attempt.http_status is None:
        return False
    return attempt.http_status in _RETRYABLE_HTTP_STATUSES or attempt.http_status >= 500


__all__ = [
    "CollectionScopeExecutionCounts",
    "PostgresFencedProviderAttemptPreparer",
]
