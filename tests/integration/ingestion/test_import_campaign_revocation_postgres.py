"""Data Import Campaign 撤销的 PostgreSQL 来源安全集成测试。"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

from aima_ugc.adapters.persistence.postgres.content_queries import (
    PostgresContentQueryRepository,
)
from aima_ugc.bootstrap.api import create_app
from aima_ugc.bootstrap.historical_import_http import PostgresHistoricalImportHttpService
from aima_ugc.bootstrap.import_http import PostgresImportHttpService
from aima_ugc.bootstrap.import_revocation_http import PostgresImportRevocationHttpService
from aima_ugc.bootstrap.worker import (
    create_collection_job_registry,
    create_job_worker,
    create_worker_runtime,
)
from aima_ugc.contracts.http import ContentFilterSnapshot
from aima_ugc.contracts.lifecycle import DataImportRevokeRequest
from aima_ugc.modules.collection.tables import (
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.query import ContentReadQuery
from aima_ugc.modules.content.tables import content_versions_table, contents_table
from aima_ugc.modules.ingestion.revocation_tables import (
    historical_import_campaign_revocations_table,
    historical_import_revocation_content_versions_table,
)
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.storage.tables import artifacts_table
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import and_, func, select


def _xlsx(rows: tuple[tuple[str, str, str | None], ...]) -> bytes:
    """生成最小 AIMA Excel；每行使用独立小红书 URL 作为稳定身份。"""

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "文章"
    sheet.append(
        [
            "媒体名称（中文）",
            "标题",
            "内文",
            "作者",
            "出版日期",
            "原文链接",
        ]
    )
    for title, content_key, text in rows:
        sheet.append(
            [
                "小红书",
                title,
                text,
                "官方账号",
                "2025-01-02 10:00:00",
                f"https://www.xiaohongshu.com/explore/{content_key}",
            ]
        )
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _keyword_pack(client: TestClient) -> str:
    """创建本测试专用词包并返回稳定 API ID。"""

    created = client.post(
        "/api/v1/keyword-packs",
        json={"name": f"撤销集成测试 {uuid4()}"},
    )
    assert created.status_code == 201
    pack_id = created.json()["id"]
    added = client.post(
        f"/api/v1/keyword-packs/{pack_id}/keywords",
        json={"text": "爱玛", "priority": 10},
    )
    assert added.status_code == 201
    return pack_id


def _drain(worker, *, maximum: int = 20) -> int:
    """同步执行当前测试已经入队的有限 Job，避免依赖后台调度时间。"""

    executed = 0
    for _ in range(maximum):
        if not worker.run_once():
            break
        executed += 1
    return executed


def _runtime(tmp_path: Path, historical_root: Path):
    """建立隔离 Runtime，并使用单 Chunk 便于精确断言生命周期结果。"""

    settings = load_settings().model_copy(
        update={
            "data_dir": tmp_path / "data",
            "log_dir": tmp_path / "logs",
            "historical_import_root": historical_root,
            "historical_chunk_rows": 100,
            "historical_max_in_flight_jobs": 1,
        }
    )
    runtime = create_worker_runtime(settings=settings)
    with runtime.database.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE jobs, artifacts, keyword_packs, accounts RESTART IDENTITY CASCADE"
        )
    return runtime


def _client(runtime) -> TestClient:
    """复用正式导入 Service 建立 API Client；撤销执行另走真实 Application Service。"""

    return TestClient(
        create_app(
            historical_import_service=PostgresHistoricalImportHttpService(runtime),
            import_service=PostgresImportHttpService(runtime),
        )
    )


def _cleanup(runtime) -> None:
    """清空当前 Integration 数据并释放 Runtime。"""

    with runtime.database.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE jobs, artifacts, keyword_packs, accounts RESTART IDENTITY CASCADE"
        )
    runtime.close()


def test_revocation_hides_exclusive_content_and_retains_shared_content(tmp_path: Path) -> None:
    """撤销 Campaign 会重组 Current；共享 Content 保留，独占 Content 退出后续业务目标。"""

    historical_root = tmp_path / "approved-history"
    historical_root.mkdir()
    shared_key = f"revocation-shared-{uuid4()}"
    exclusive_key = f"revocation-exclusive-{uuid4()}"
    (historical_root / "campaign.xlsx").write_bytes(
        _xlsx(
            (
                ("爱玛共享来源", shared_key, "共享正文"),
                ("爱玛独占来源", exclusive_key, "独占正文"),
            )
        )
    )
    runtime = _runtime(tmp_path, historical_root)
    try:
        client = _client(runtime)
        pack_id = _keyword_pack(client)
        baseline = client.post(
            "/api/v1/import-batches",
            files=[
                (
                    "file",
                    (
                        "baseline.xlsx",
                        _xlsx((("爱玛共享来源", shared_key, "共享正文"),)),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ),
                ),
                ("keyword_pack_ids", (None, pack_id)),
            ],
        )
        assert baseline.status_code == 202

        worker = create_job_worker(
            runtime=runtime,
            registry=create_collection_job_registry(runtime=runtime),
            worker_id="revocation-integration-worker",
            lease_seconds=120,
            retry_delay_seconds=0,
        )
        assert _drain(worker) == 1

        created = client.post(
            "/api/v1/historical-import-campaigns",
            json={
                "client_idempotency_key": f"revocation-{uuid4()}",
                "relative_paths": ["campaign.xlsx"],
                "recursive": False,
                "keyword_pack_ids": [pack_id],
            },
        )
        assert created.status_code == 202
        campaign_id = UUID(created.json()["campaign_id"])
        assert _drain(worker) == 2
        assert (
            client.post(f"/api/v1/historical-import-campaigns/{campaign_id}/start").status_code
            == 200
        )
        assert _drain(worker) == 1
        completed = client.get(f"/api/v1/historical-import-campaigns/{campaign_id}").json()
        assert completed["status"] == "succeeded"

        before_session = runtime.database.new_session()
        try:
            with before_session.begin():
                before_repository = PostgresContentQueryRepository(
                    before_session,
                    analysis_identity=None,
                )
                before = before_repository.list_contents(
                    ContentReadQuery(
                        filters=ContentFilterSnapshot(),
                        position=None,
                        limit=20,
                    )
                )
                assert len(before) == 2
                by_title = {record.title: record for record in before}
                shared_id = by_title["爱玛共享来源"].id
                exclusive_id = by_title["爱玛独占来源"].id
                assert before_repository.count_all_analysis_targets() == 2
        finally:
            before_session.close()

        service = PostgresImportRevocationHttpService(
            runtime.database.new_session,
            runtime.artifact_store,
        )
        preview = service.preview(campaign_id)
        assert preview.eligible is True
        assert preview.already_revoked is False
        assert preview.ineligible_reason is None
        assert preview.impact.affected_content_count == 2
        assert preview.impact.hidden_content_count == 1
        assert preview.impact.retained_shared_content_count == 1
        assert preview.impact.unreversible_content_count == 0

        first = service.revoke(
            campaign_id,
            DataImportRevokeRequest(reason="集成测试撤销"),
            actor_ref="integration-admin",
            request_id="revocation-request-1",
        )
        second = service.revoke(
            campaign_id,
            DataImportRevokeRequest(reason="重复点击"),
            actor_ref="integration-admin",
            request_id="revocation-request-2",
        )
        assert first.already_revoked is False
        assert second.already_revoked is True
        assert second.revoked_at == first.revoked_at
        assert second.impact == first.impact

        after_session = runtime.database.new_session()
        try:
            with after_session.begin():
                after_repository = PostgresContentQueryRepository(
                    after_session,
                    analysis_identity=None,
                )
                after = after_repository.list_contents(
                    ContentReadQuery(
                        filters=ContentFilterSnapshot(),
                        position=None,
                        limit=20,
                    )
                )
                assert [record.id for record in after] == [shared_id]
                assert after_repository.get_content(shared_id) is not None
                assert after_repository.get_content(exclusive_id) is None
                assert after_repository.count_all_analysis_targets() == 1
                selected = after_repository.freeze_targets(content_ids=(shared_id, exclusive_id))
                assert [target.content_id for target in selected] == [shared_id]
                assert (
                    after_session.scalar(
                        select(func.count()).select_from(
                            historical_import_campaign_revocations_table
                        )
                    )
                    == 1
                )
                assert (
                    after_session.scalar(
                        select(func.count()).select_from(
                            historical_import_revocation_content_versions_table
                        )
                    )
                    == 2
                )
                lifecycle_rows = tuple(
                    after_session.execute(
                        select(
                            contents_table.c.id,
                            provider_requests_table.c.provider,
                            provider_requests_table.c.operation,
                            artifacts_table.c.kind,
                            artifacts_table.c.storage_status,
                        )
                        .select_from(
                            contents_table.join(
                                content_versions_table,
                                and_(
                                    content_versions_table.c.content_id == contents_table.c.id,
                                    content_versions_table.c.version_no
                                    == contents_table.c.current_version,
                                ),
                            )
                            .join(
                                provider_request_attempts_table,
                                provider_request_attempts_table.c.id
                                == content_versions_table.c.provider_attempt_id,
                            )
                            .join(
                                provider_requests_table,
                                provider_requests_table.c.id
                                == provider_request_attempts_table.c.provider_request_id,
                            )
                            .join(
                                artifacts_table,
                                artifacts_table.c.id == content_versions_table.c.raw_artifact_id,
                            )
                        )
                        .where(contents_table.c.id.in_((shared_id, exclusive_id)))
                    ).mappings()
                )
                assert len(lifecycle_rows) == 2
                assert {row["provider"] for row in lifecycle_rows} == {"imports"}
                assert {row["operation"] for row in lifecycle_rows} == {"data_import_revoke"}
                assert {row["kind"] for row in lifecycle_rows} == {"provider-raw"}
                assert {row["storage_status"] for row in lifecycle_rows} == {"linked"}
        finally:
            after_session.close()
    finally:
        _cleanup(runtime)


def test_revocation_restores_field_filled_by_historical_fill_only(tmp_path: Path) -> None:
    """历史补空贡献被撤销后，共享 Content 恢复为导入前的空字段而不是删除 Content。"""

    historical_root = tmp_path / "approved-history"
    historical_root.mkdir()
    shared_key = f"revocation-fill-{uuid4()}"
    (historical_root / "fill.xlsx").write_bytes(
        _xlsx((("爱玛补空内容", shared_key, "历史补空正文"),))
    )
    runtime = _runtime(tmp_path, historical_root)
    try:
        client = _client(runtime)
        pack_id = _keyword_pack(client)
        baseline = client.post(
            "/api/v1/import-batches",
            files=[
                (
                    "file",
                    (
                        "baseline-empty.xlsx",
                        _xlsx((("爱玛补空内容", shared_key, None),)),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ),
                ),
                ("keyword_pack_ids", (None, pack_id)),
            ],
        )
        assert baseline.status_code == 202
        worker = create_job_worker(
            runtime=runtime,
            registry=create_collection_job_registry(runtime=runtime),
            worker_id="revocation-fill-worker",
            lease_seconds=120,
            retry_delay_seconds=0,
        )
        assert _drain(worker) == 1

        created = client.post(
            "/api/v1/historical-import-campaigns",
            json={
                "client_idempotency_key": f"revocation-fill-{uuid4()}",
                "relative_paths": ["fill.xlsx"],
                "recursive": False,
                "keyword_pack_ids": [pack_id],
            },
        )
        campaign_id = UUID(created.json()["campaign_id"])
        assert _drain(worker) == 2
        assert (
            client.post(f"/api/v1/historical-import-campaigns/{campaign_id}/start").status_code
            == 200
        )
        assert _drain(worker) == 1

        session = runtime.database.new_session()
        try:
            with session.begin():
                before = PostgresContentQueryRepository(
                    session,
                    analysis_identity=None,
                ).list_contents(
                    ContentReadQuery(
                        filters=ContentFilterSnapshot(),
                        position=None,
                        limit=20,
                    )
                )
                assert len(before) == 1
                content_id = before[0].id
                assert before[0].text == "历史补空正文"
                version_before_revoke = session.scalar(
                    select(contents_table.c.current_version).where(
                        contents_table.c.id == content_id
                    )
                )
        finally:
            session.close()

        service = PostgresImportRevocationHttpService(
            runtime.database.new_session,
            runtime.artifact_store,
        )
        preview = service.preview(campaign_id)
        assert preview.eligible is True
        assert preview.impact.unreversible_content_count == 0
        result = service.revoke(
            campaign_id,
            DataImportRevokeRequest(reason="撤销历史补空"),
            actor_ref="integration-admin",
            request_id="revocation-fill-request",
        )
        assert result.already_revoked is False
        assert result.impact.retained_shared_content_count == 1

        session = runtime.database.new_session()
        try:
            with session.begin():
                after_repository = PostgresContentQueryRepository(
                    session,
                    analysis_identity=None,
                )
                after = after_repository.list_contents(
                    ContentReadQuery(
                        filters=ContentFilterSnapshot(),
                        position=None,
                        limit=20,
                    )
                )
                assert len(after) == 1
                assert after[0].id == content_id
                assert after[0].text is None
                version_after_revoke = session.scalar(
                    select(contents_table.c.current_version).where(
                        contents_table.c.id == content_id
                    )
                )
                assert version_after_revoke == version_before_revoke + 1
                assert (
                    session.scalar(
                        select(func.count())
                        .select_from(historical_import_revocation_content_versions_table)
                        .where(
                            historical_import_revocation_content_versions_table.c.campaign_id
                            == campaign_id
                        )
                    )
                    == 1
                )
        finally:
            session.close()
    finally:
        _cleanup(runtime)
