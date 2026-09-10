"""Excel 与 Data Import 共用的确定性非计费 Provider lineage。"""

from __future__ import annotations

from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from aima_ugc.contracts.provider import ProviderAttemptV1, ProviderBillingV1, ProviderRequestV1
from aima_ugc.modules.collection.provider_persistence import ProviderPersistenceService
from aima_ugc.modules.collection.tables import (
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.platform.storage import ArtifactRecord
from aima_ugc.platform.time import beijing_now

from .provider import PostgresProviderRepository


def ensure_single_import_lineage(
    *,
    session: Session,
    batch_id: UUID,
    platform: str,
    input_artifact: ArtifactRecord,
    profile: str,
) -> tuple[UUID, UUID]:
    """建立或复用单文件 Import 当前确定性 Request/Attempt。"""

    if input_artifact.sha256 is None:
        raise ValueError("Excel Input Artifact 缺少 SHA-256")
    return _ensure_import_lineage(
        session=session,
        request=ProviderRequestV1.create_for_import(
            request_id=uuid5(batch_id, f"provider-request:{platform}"),
            import_batch_id=batch_id,
            provider="imports",
            platform=platform,
            operation="excel_import",
            request_params={
                "input_artifact_sha256": input_artifact.sha256,
                "profile": profile,
            },
            pagination_input={},
        ),
        attempt_id=uuid5(batch_id, f"provider-attempt:{platform}"),
        raw_artifact=input_artifact,
    )


def ensure_campaign_import_lineage(
    *,
    session: Session,
    batch_id: UUID,
    platform: str,
    canonical_artifact: ArtifactRecord,
    operation: str,
) -> tuple[UUID, UUID]:
    """建立或复用 Data Import Canonical Chunk 当前确定性 Request/Attempt。"""

    if canonical_artifact.sha256 is None:
        raise ValueError("Data Import Canonical Artifact 缺少 SHA-256")
    lineage_key = f"{platform}:{canonical_artifact.id}:{canonical_artifact.sha256}"
    return _ensure_import_lineage(
        session=session,
        request=ProviderRequestV1.create_for_import(
            request_id=uuid5(
                batch_id,
                f"campaign-provider-request:{operation}:{lineage_key}",
            ),
            import_batch_id=batch_id,
            provider="imports",
            platform=platform,
            operation=operation,
            request_params={"chunk_artifact_sha256": canonical_artifact.sha256},
            pagination_input={},
        ),
        attempt_id=uuid5(
            batch_id,
            f"campaign-provider-attempt:{operation}:{lineage_key}",
        ),
        raw_artifact=canonical_artifact,
    )


def _ensure_import_lineage(
    *,
    session: Session,
    request: ProviderRequestV1,
    attempt_id: UUID,
    raw_artifact: ArtifactRecord,
) -> tuple[UUID, UUID]:
    """允许正式写入与后续 Replay 幂等复用同一已完成非计费来源。"""

    existing = (
        session.execute(
            select(
                provider_requests_table.c.id.label("request_id"),
                provider_requests_table.c.import_batch_id,
                provider_requests_table.c.scope_id,
                provider_requests_table.c.provider,
                provider_requests_table.c.platform,
                provider_requests_table.c.operation,
                provider_requests_table.c.request_fingerprint,
                provider_requests_table.c.request_params,
                provider_requests_table.c.pagination_input,
                provider_request_attempts_table.c.dispatch_status,
                provider_request_attempts_table.c.raw_artifact_id,
                provider_request_attempts_table.c.billing_status,
                provider_request_attempts_table.c.potential_duplicate_charge,
            )
            .join(
                provider_request_attempts_table,
                provider_request_attempts_table.c.provider_request_id
                == provider_requests_table.c.id,
            )
            .where(provider_request_attempts_table.c.id == attempt_id)
        )
        .mappings()
        .one_or_none()
    )
    if existing is not None:
        if not (
            existing["request_id"] == request.request_id
            and existing["import_batch_id"] == request.import_batch_id
            and existing["scope_id"] is None
            and existing["provider"] == request.provider
            and existing["platform"] == request.platform
            and existing["operation"] == request.operation
            and existing["request_fingerprint"] == request.request_fingerprint
            and existing["request_params"] == request.request_params
            and existing["pagination_input"] == request.pagination_input
            and existing["dispatch_status"] == "completed"
            and existing["raw_artifact_id"] == raw_artifact.id
            and existing["billing_status"] == "not_billable"
            and existing["potential_duplicate_charge"] is False
        ):
            raise ValueError("Import Provider lineage 与当前确定性来源不一致")
        return request.request_id, attempt_id

    repository = PostgresProviderRepository(session)
    prepared = ProviderPersistenceService(repository).prepare_non_billable_attempt(
        request=request,
        attempt_id=attempt_id,
    )
    dispatching = repository.mark_dispatching(prepared.attempt.id)
    if dispatching.dispatch_started_at is None:
        raise RuntimeError("Import Attempt 未进入 dispatching")
    repository.finalize_dispatch(
        attempt=ProviderAttemptV1(
            attempt_id=dispatching.id,
            provider_request_id=prepared.request.id,
            attempt_no=dispatching.attempt_no,
            dispatch_status="completed",
            dispatch_started_at=dispatching.dispatch_started_at,
            completed_at=beijing_now(),
            raw_artifact_id=raw_artifact.id,
            billing=ProviderBillingV1(status="not_billable"),
            created_at=dispatching.created_at,
        ),
        raw_artifact_id=raw_artifact.id,
    )
    return prepared.request.id, dispatching.id


__all__ = ["ensure_campaign_import_lineage", "ensure_single_import_lineage"]
