"""U1—U5 人工锁、Scheme、可用状态与 Principal Inbox PostgreSQL 集成回归。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.analysis_manual_reviews import (
    PostgresAnalysisManualReviewRepository,
)
from aima_ugc.adapters.persistence.postgres.notifications import PostgresNotificationRepository
from aima_ugc.adapters.persistence.postgres.system import PostgresAuditRepository
from aima_ugc.adapters.persistence.postgres.vehicles import PostgresVehicleCatalogRepository
from aima_ugc.bootstrap.administration_http import PostgresAdministrationHttpService
from aima_ugc.bootstrap.content_http import PostgresContentHttpService
from aima_ugc.bootstrap.worker import create_worker_runtime
from aima_ugc.contracts.administration import (
    AnalysisSchemeCreateDraftRequest,
    AnalysisSchemePublishRequest,
    AnalysisSchemeUpdateDraftRequest,
)
from aima_ugc.contracts.product import ContentAnalysisManualReviewRequest
from aima_ugc.modules.content.availability_tables import (
    content_availability_observations_table,
)
from aima_ugc.modules.content.http import ContentAnalysisRunConflict
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.modules.identity import Principal
from aima_ugc.modules.vehicles.models import ContentVehicleEvidence
from aima_ugc.platform.config import load_settings
from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def runtime():  # type: ignore[no-untyped-def]
    value = create_worker_runtime(settings=load_settings())

    def cleanup() -> None:
        with value.database.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE audit_events, notification_events, analysis_schemes, "
                "contents, vehicle_models RESTART IDENTITY CASCADE"
            )

    cleanup()
    try:
        yield value
    finally:
        cleanup()
        value.close()


def _seed_content(runtime) -> UUID:  # type: ignore[no-untyped-def]
    content_id = uuid4()
    now = datetime.now(UTC)
    with runtime.database.engine.begin() as connection:
        connection.execute(
            insert(contents_table).values(
                id=content_id,
                platform="xiaohongshu",
                external_content_id=f"u1-u5-{uuid4()}",
                content_type="note",
                title="爱玛 Q7 使用体验",
                text="续航稳定",
                first_seen_at=now,
                last_seen_at=now,
                current_version=1,
                field_observed_at={},
                updated_at=now,
            )
        )
    return content_id


def test_manual_vehicle_and_analysis_locks_require_explicit_unlock(runtime) -> None:  # type: ignore[no-untyped-def]
    """人工车型/分析结论锁住当前版本，自动证据和二次人工修改都不能静默覆盖。"""

    content_id = _seed_content(runtime)
    session = runtime.database.new_session()
    try:
        with session.begin():
            vehicles = PostgresVehicleCatalogRepository(session)
            model = vehicles.create_model(
                code="Q7",
                display_name="爱玛 Q7",
                aliases=("Q7", "爱玛Q7"),
                actor_ref="admin-1",
            )
            assert vehicles.append_evidence(
                ContentVehicleEvidence(
                    id=uuid4(),
                    content_id=content_id,
                    content_version=1,
                    vehicle_model_id=model.id,
                    source="alias_match",
                    matched_text="Q7",
                    source_field="title",
                    catalog_version=model.catalog_version,
                    confidence=1.0,
                    is_manual_locked=False,
                    is_active=True,
                    created_at=datetime.now(UTC),
                )
            )
            vehicles.replace_manual_evidence(
                content_id=content_id,
                content_version=1,
                model_ids=(model.id,),
                unlock_existing=False,
                actor_ref="admin-1",
            )
            assert not vehicles.append_evidence(
                ContentVehicleEvidence(
                    id=uuid4(),
                    content_id=content_id,
                    content_version=1,
                    vehicle_model_id=model.id,
                    source="ai_candidate",
                    matched_text="Q7",
                    source_field="text",
                    catalog_version=model.catalog_version,
                    confidence=0.8,
                    is_manual_locked=False,
                    is_active=True,
                    created_at=datetime.now(UTC),
                )
            )

            reviews = PostgresAnalysisManualReviewRepository(session)
            row = reviews.review(
                content_id=content_id,
                content_version=1,
                voice_type="真实用户发声",
                sentiment="正面",
                labels=(("产品体验", "续航表现"),),
                unlock_dimensions=(),
                actor_ref="admin-1",
            )
            assert row["voice_type_locked"] is True
            with pytest.raises(RuntimeError, match="voice_type 已人工锁定"):
                reviews.review(
                    content_id=content_id,
                    content_version=1,
                    voice_type="品牌官方发声",
                    sentiment=None,
                    labels=None,
                    unlock_dimensions=(),
                    actor_ref="admin-1",
                )
            unlocked = reviews.review(
                content_id=content_id,
                content_version=1,
                voice_type=None,
                sentiment=None,
                labels=None,
                unlock_dimensions=("voice_type",),
                actor_ref="admin-1",
            )
            assert unlocked["voice_type"] is None
            assert unlocked["voice_type_locked"] is False
    finally:
        session.close()


def test_manual_analysis_review_requires_current_completed_ai_result(runtime) -> None:  # type: ignore[no-untyped-def]
    """人工分析是对当前 AI 结果的纠正，不能在尚无结果时创建平行结论。"""

    content_id = _seed_content(runtime)
    service = PostgresContentHttpService(runtime, cursor_signing_secret=b"u1-u5-test")

    with pytest.raises(ContentAnalysisRunConflict):
        service.review_analysis(
            content_id,
            ContentAnalysisManualReviewRequest(
                content_version=1,
                voice_type="真实用户发声",
            ),
            request_id="manual-review-without-ai",
            actor_ref="admin-1",
        )


def test_analysis_scheme_publish_and_rollback_are_atomic_and_audited(runtime) -> None:  # type: ignore[no-untyped-def]
    service = PostgresAdministrationHttpService(runtime)
    principal = Principal(
        principal_id="admin-1",
        display_name="管理员",
        role="administrator",
        source="development",
    )
    initial = service.list_analysis_schemes().items[0]
    initial_version = initial.versions[0]
    created = service.create_analysis_scheme_draft(
        AnalysisSchemeCreateDraftRequest(
            name=initial.name,
            description="U4 草稿",
            definition=initial_version.definition,
        ),
        principal=principal,
        request_id="req-draft",
    )
    draft = next(item for item in created.versions if item.status == "draft")

    updated = service.update_analysis_scheme_draft(
        draft.id,
        AnalysisSchemeUpdateDraftRequest(
            description="U4 修订草稿",
            definition=draft.definition,
            expected_version=draft.version,
        ),
        principal=principal,
        request_id="req-update-draft",
    )
    revised_draft = next(item for item in updated.versions if item.status == "draft")
    assert revised_draft.id != draft.id
    assert revised_draft.version == draft.version + 1
    assert next(item for item in updated.versions if item.id == draft.id).status == "retired"

    published = service.publish_analysis_scheme(
        revised_draft.id,
        AnalysisSchemePublishRequest(expected_version=revised_draft.version),
        principal=principal,
        request_id="req-publish",
    )
    assert published.active_version_id == revised_draft.id
    assert sum(item.status == "published" for item in published.versions) == 1

    rolled_back = service.rollback_analysis_scheme(
        initial_version.id,
        AnalysisSchemePublishRequest(expected_version=initial_version.version),
        principal=principal,
        request_id="req-rollback",
    )
    assert rolled_back.active_version_id == initial_version.id
    assert sum(item.status == "published" for item in rolled_back.versions) == 1

    session = runtime.database.new_session()
    try:
        with session.begin():
            events = PostgresAuditRepository(session).list_recent(limit=20)
    finally:
        session.close()
    assert {event.event_type for event in events} >= {
        "analysis_scheme_bootstrapped",
        "analysis_scheme_draft_created",
        "analysis_scheme_draft_updated",
        "analysis_scheme_published",
        "analysis_scheme_rolled_back",
    }
    assert {event.request_id for event in events if event.actor_kind == "principal"} >= {
        "req-draft",
        "req-update-draft",
        "req-publish",
        "req-rollback",
    }


def test_availability_history_and_notification_inbox_preserve_evidence_and_principal(
    runtime,  # type: ignore[no-untyped-def]
) -> None:
    content_id = _seed_content(runtime)
    session = runtime.database.new_session()
    try:
        with session.begin():
            now = datetime.now(UTC)
            session.execute(
                insert(content_availability_observations_table),
                [
                    {
                        "id": uuid4(),
                        "content_id": content_id,
                        "content_version": 1,
                        "status": "unknown",
                        "reason_code": "provider_timeout",
                        "evidence_kind": "technical_failure",
                        "safe_summary": "provider request timed out",
                        "observed_at": now,
                    },
                    {
                        "id": uuid4(),
                        "content_id": content_id,
                        "content_version": 1,
                        "status": "available",
                        "reason_code": "manual_verified",
                        "evidence_kind": "manual_review",
                        "safe_summary": "manual review found content available",
                        "observed_at": datetime.now(UTC),
                    },
                ],
            )
            assert (
                session.scalar(
                    select(func.count()).select_from(content_availability_observations_table)
                )
                == 2
            )

            notifications = PostgresNotificationRepository(session)
            event_id = notifications.publish_to_principal(
                deduplication_key="export:1:succeeded",
                principal_id="user-a",
                event_type="data_export_succeeded",
                title="导出完成",
                message="文件已就绪",
            )
            notifications.publish_to_principal(
                deduplication_key="export:1:succeeded",
                principal_id="user-b",
                event_type="data_export_succeeded",
                title="导出完成",
                message="文件已就绪",
            )
            rows_a, unread_a = notifications.list_for_principal("user-a", limit=20)
            rows_b, unread_b = notifications.list_for_principal("user-b", limit=20)
            assert rows_a[0]["event_id"] == rows_b[0]["event_id"] == event_id
            assert unread_a == unread_b == 1
            assert notifications.mark_read("user-a", (rows_b[0]["id"],)) == 0
            assert notifications.mark_read("user-a", (rows_a[0]["id"],)) == 1
            assert notifications.list_for_principal("user-a", limit=20)[1] == 0
            assert notifications.list_for_principal("user-b", limit=20)[1] == 1
    finally:
        session.close()

    invalid_session = runtime.database.new_session()
    try:
        with pytest.raises(IntegrityError):
            with invalid_session.begin():
                invalid_session.execute(
                    insert(content_availability_observations_table).values(
                        id=uuid4(),
                        content_id=content_id,
                        content_version=1,
                        status="unavailable_confirmed",
                        reason_code="timeout",
                        evidence_kind="technical_failure",
                        safe_summary="",
                        observed_at=datetime.now(UTC),
                    )
                )
    finally:
        invalid_session.close()

    manual_confirmed_session = runtime.database.new_session()
    try:
        with pytest.raises(IntegrityError):
            with manual_confirmed_session.begin():
                manual_confirmed_session.execute(
                    insert(content_availability_observations_table).values(
                        id=uuid4(),
                        content_id=content_id,
                        content_version=1,
                        status="unavailable_confirmed",
                        reason_code="manual_claim",
                        evidence_kind="manual_review",
                        safe_summary="",
                        observed_at=datetime.now(UTC),
                    )
                )
    finally:
        manual_confirmed_session.close()

    unsupported_provider_session = runtime.database.new_session()
    try:
        with pytest.raises(IntegrityError):
            with unsupported_provider_session.begin():
                unsupported_provider_session.execute(
                    insert(content_availability_observations_table).values(
                        id=uuid4(),
                        content_id=content_id,
                        content_version=1,
                        status="unavailable_confirmed",
                        reason_code="provider_claim_without_evidence",
                        evidence_kind="provider_explicit",
                        safe_summary="",
                        observed_at=datetime.now(UTC),
                    )
                )
    finally:
        unsupported_provider_session.close()
