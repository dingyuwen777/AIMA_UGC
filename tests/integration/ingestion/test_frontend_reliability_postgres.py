"""CHG-314 的 PostgreSQL 事务、分页与聚合事实集成测试。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from aima_ugc.adapters.persistence.postgres.collection_runtime_queries import (
    PostgresCollectionRuntimeQueryRepository,
)
from aima_ugc.adapters.persistence.postgres.historical_import import (
    PostgresHistoricalImportRepository,
)
from aima_ugc.adapters.persistence.postgres.keywords import PostgresKeywordCatalogRepository
from aima_ugc.adapters.persistence.postgres.system import PostgresAuditRepository
from aima_ugc.bootstrap.administration_http import PostgresAdministrationHttpService
from aima_ugc.bootstrap.api import create_app
from aima_ugc.bootstrap.historical_import_http import PostgresHistoricalImportHttpService
from aima_ugc.bootstrap.import_http import PostgresImportHttpService
from aima_ugc.bootstrap.worker import create_worker_runtime
from aima_ugc.modules.collection.runtime_query import CollectionRuntimeReadQuery
from aima_ugc.modules.ingestion.historical_tables import (
    historical_import_campaign_items_table,
    historical_import_campaigns_table,
)
from aima_ugc.modules.system.models import AuditEvent
from aima_ugc.modules.system.tables import (
    audit_events_table,
    keyword_pack_items_table,
    keyword_packs_table,
)
from aima_ugc.platform.config import load_settings
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, insert, select, update


def _runtime(tmp_path):
    settings = load_settings().model_copy(
        update={"data_dir": tmp_path / "data", "log_dir": tmp_path / "logs"}
    )
    return create_worker_runtime(settings=settings)


def test_keyword_pack_initial_keywords_commit_atomically_and_roll_back_together(
    tmp_path,
    monkeypatch,
) -> None:
    runtime = _runtime(tmp_path)
    try:
        client = TestClient(
            create_app(import_service=PostgresImportHttpService(runtime)),
            raise_server_exceptions=False,
        )
        suffix = uuid4().hex
        success_name = f"atomic-pack-{suffix}"
        created = client.post(
            "/api/v1/keyword-packs",
            json={
                "name": success_name,
                "description": "single transaction",
                "keywords": [
                    {"text": f"爱玛-{suffix}", "priority": 100, "enabled": True},
                    {"text": f"电动车-{suffix}", "priority": 80, "enabled": True},
                ],
            },
        )
        assert created.status_code == 201
        assert [item["text"] for item in created.json()["keywords"]] == [
            f"电动车-{suffix}",
            f"爱玛-{suffix}",
        ]
        pack_id = UUID(created.json()["id"])
        with runtime.database.engine.begin() as connection:
            assert (
                connection.scalar(
                    select(func.count())
                    .select_from(keyword_pack_items_table)
                    .where(keyword_pack_items_table.c.pack_id == pack_id)
                )
                == 2
            )

        original_add = PostgresKeywordCatalogRepository.add_item_if_missing
        calls = 0

        def fail_on_second_item(self, item):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("forced second-item failure")
            return original_add(self, item)

        monkeypatch.setattr(
            PostgresKeywordCatalogRepository,
            "add_item_if_missing",
            fail_on_second_item,
        )
        rollback_name = f"rollback-pack-{suffix}"
        failed = client.post(
            "/api/v1/keyword-packs",
            json={
                "name": rollback_name,
                "keywords": [
                    {"text": f"rollback-a-{suffix}", "priority": 100, "enabled": True},
                    {"text": f"rollback-b-{suffix}", "priority": 100, "enabled": True},
                ],
            },
        )
        assert failed.status_code == 500
        with runtime.database.engine.begin() as connection:
            assert (
                connection.scalar(
                    select(func.count())
                    .select_from(keyword_packs_table)
                    .where(keyword_packs_table.c.name == rollback_name)
                )
                == 0
            )
    finally:
        runtime.close()


def test_audit_repository_and_service_page_complete_history(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    event_ids = [uuid4(), uuid4(), uuid4()]
    try:
        with runtime.database.new_session() as session:
            with session.begin():
                repository = PostgresAuditRepository(session)
                baseline = repository.count()
                base_time = datetime(2099, 1, 1, tzinfo=UTC)
                for index, event_id in enumerate(event_ids):
                    repository.append(
                        AuditEvent(
                            id=event_id,
                            actor_kind="principal",
                            actor_ref="local-administrator",
                            event_type=f"reliability_audit_{index}",
                            object_type="test",
                            object_id=str(index),
                            request_id=f"request-{index}",
                            safe_detail={"index": index},
                            created_at=base_time + timedelta(seconds=index),
                        )
                    )

        response = PostgresAdministrationHttpService(runtime).list_audit_events(
            offset=1,
            limit=2,
        )

        assert response.total == baseline + 3
        assert response.offset == 1
        assert response.limit == 2
        assert [item.id for item in response.items] == [event_ids[1], event_ids[0]]
    finally:
        with runtime.database.engine.begin() as connection:
            connection.execute(
                delete(audit_events_table).where(audit_events_table.c.id.in_(event_ids))
            )
        runtime.close()


def test_historical_campaign_failed_chunk_count_ignores_bounded_detail_shape(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    campaign_id = uuid4()
    source_id = uuid4()
    failed_chunk_id = uuid4()
    succeeded_chunk_id = uuid4()
    created_at = datetime(2026, 9, 3, tzinfo=UTC)
    try:
        with runtime.database.engine.begin() as connection:
            connection.execute(
                insert(historical_import_campaigns_table).values(
                    id=campaign_id,
                    client_idempotency_key=f"reliability-{campaign_id}",
                    source_kind="server_path",
                    ingestion_policy="historical_fill_only",
                    declared_file_count=1,
                    root_relative_path="history.xlsx",
                    recursive=False,
                    profile_snapshot={},
                    keyword_pack_snapshot={},
                    status="partial_failed",
                    discovered_file_count=1,
                    ready_item_count=1,
                    total_rows=20,
                    stats={},
                    created_at=created_at,
                )
            )
            connection.execute(
                insert(historical_import_campaign_items_table).values(
                    id=source_id,
                    campaign_id=campaign_id,
                    item_kind="source_file",
                    relative_path="history.xlsx",
                    manifest_identity="a" * 64,
                    row_count=0,
                    status="failed",
                    attempt_count=1,
                    stats={},
                    created_at=created_at,
                )
            )
            connection.execute(
                insert(historical_import_campaign_items_table),
                [
                    {
                        "id": failed_chunk_id,
                        "campaign_id": campaign_id,
                        "parent_item_id": source_id,
                        "item_kind": "chunk",
                        "relative_path": "history.xlsx",
                        "manifest_identity": "a" * 64,
                        "ordinal": 0,
                        "row_start": 1,
                        "row_end": 10,
                        "row_count": 10,
                        "status": "failed",
                        "attempt_count": 1,
                        "stats": {},
                        "error_code": "forced_failure",
                        "created_at": created_at,
                    },
                    {
                        "id": succeeded_chunk_id,
                        "campaign_id": campaign_id,
                        "parent_item_id": source_id,
                        "item_kind": "chunk",
                        "relative_path": "history.xlsx",
                        "manifest_identity": "a" * 64,
                        "ordinal": 1,
                        "row_start": 11,
                        "row_end": 20,
                        "row_count": 10,
                        "status": "succeeded",
                        "attempt_count": 1,
                        "stats": {},
                        "error_code": None,
                        "created_at": created_at,
                    },
                ],
            )

        with runtime.database.new_session() as session:
            with session.begin():
                progress = PostgresHistoricalImportRepository(session).campaign_progresses(
                    (campaign_id,)
                )[campaign_id]
        assert progress.failed_chunk_count == 1

        response = PostgresHistoricalImportHttpService(runtime).get_campaign(campaign_id)
        assert response.failed_chunk_count == 1
    finally:
        with runtime.database.engine.begin() as connection:
            connection.execute(
                delete(historical_import_campaigns_table).where(
                    historical_import_campaigns_table.c.id == campaign_id
                )
            )
        runtime.close()


def test_historical_progress_tracks_chunk_terminal_changes_and_runtime_view(tmp_path) -> None:
    """新增、失败重试、批量取消和删除都按 Source 净变化反映进度。"""

    runtime = _runtime(tmp_path)
    campaign_id, source_id = uuid4(), uuid4()
    succeeded_id, failed_id, ready_id = uuid4(), uuid4(), uuid4()
    created_at = datetime(2026, 9, 26, tzinfo=UTC)
    try:
        with runtime.database.engine.begin() as connection:
            connection.execute(
                insert(historical_import_campaigns_table).values(
                    id=campaign_id,
                    client_idempotency_key=f"progress-{campaign_id}",
                    root_relative_path="progress.xlsx",
                    profile_snapshot={},
                    status="running",
                    discovered_file_count=1,
                    ready_item_count=1,
                    total_rows=60,
                    created_at=created_at,
                )
            )
            connection.execute(
                insert(historical_import_campaign_items_table).values(
                    id=source_id,
                    campaign_id=campaign_id,
                    item_kind="source_file",
                    relative_path="progress.xlsx",
                    manifest_identity="a" * 64,
                    row_count=60,
                    status="running",
                    created_at=created_at,
                )
            )
            connection.execute(
                insert(historical_import_campaign_items_table),
                [
                    {
                        "id": chunk_id,
                        "campaign_id": campaign_id,
                        "parent_item_id": source_id,
                        "item_kind": "chunk",
                        "relative_path": "progress.xlsx",
                        "manifest_identity": "a" * 64,
                        "ordinal": ordinal,
                        "row_start": ordinal * 20 + 1,
                        "row_end": (ordinal + 1) * 20,
                        "row_count": 20,
                        "status": status,
                        "created_at": created_at,
                    }
                    for ordinal, (chunk_id, status) in enumerate(
                        ((succeeded_id, "succeeded"), (failed_id, "failed"), (ready_id, "ready"))
                    )
                ],
            )

        def progress() -> tuple[int, int, int]:
            with runtime.database.new_session() as session, session.begin():
                source = session.execute(
                    select(
                        historical_import_campaign_items_table.c.completed_row_count,
                        historical_import_campaign_items_table.c.failed_chunk_count,
                    ).where(historical_import_campaign_items_table.c.id == source_id)
                ).one()
                campaign = PostgresHistoricalImportRepository(session).campaign_progresses(
                    (campaign_id,)
                )[campaign_id]
                runtime_rows = PostgresCollectionRuntimeQueryRepository(session).list_runs(
                    CollectionRuntimeReadQuery(
                        search=str(campaign_id),
                        record_types=("data_import_campaign",),
                        status=None,
                        stage=None,
                        created_from=None,
                        created_to=None,
                        position=None,
                        limit=10,
                    )
                )
                assert len(runtime_rows) == 1
                assert campaign.migration_completed_row_count == int(source[0])
                assert campaign.failed_chunk_count == int(source[1])
                return int(source[0]), int(source[1]), runtime_rows[0].progress

        assert progress() == (40, 1, 67)
        with runtime.database.engine.begin() as connection:
            connection.execute(
                update(historical_import_campaign_items_table)
                .where(historical_import_campaign_items_table.c.id == failed_id)
                .values(status="ready")
            )
        assert progress() == (20, 0, 33)
        with runtime.database.engine.begin() as connection:
            connection.execute(
                update(historical_import_campaign_items_table)
                .where(historical_import_campaign_items_table.c.id.in_((failed_id, ready_id)))
                .values(status="cancelled")
            )
        assert progress() == (60, 0, 100)
        with runtime.database.engine.begin() as connection:
            connection.execute(
                update(historical_import_campaign_items_table)
                .where(historical_import_campaign_items_table.c.id == failed_id)
                .values(status="failed")
            )
        assert progress() == (60, 1, 100)
        with runtime.database.engine.begin() as connection:
            connection.execute(
                delete(historical_import_campaign_items_table).where(
                    historical_import_campaign_items_table.c.id == failed_id
                )
            )
        assert progress() == (40, 0, 67)
    finally:
        with runtime.database.engine.begin() as connection:
            connection.execute(
                delete(historical_import_campaigns_table).where(
                    historical_import_campaigns_table.c.id == campaign_id
                )
            )
        runtime.close()
