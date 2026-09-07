"""Data Import Campaign 撤销的 PostgreSQL 来源安全集成测试。"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

from aima_ugc.adapters.persistence.postgres.content_queries import (
    PostgresContentQueryRepository,
)
from aima_ugc.adapters.persistence.postgres.historical_revocation import (
    PostgresImportCampaignRevocationRepository,
)
from aima_ugc.bootstrap.api import create_app
from aima_ugc.bootstrap.historical_import_http import PostgresHistoricalImportHttpService
from aima_ugc.bootstrap.import_http import PostgresImportHttpService
from aima_ugc.bootstrap.worker import (
    create_collection_job_registry,
    create_job_worker,
    create_worker_runtime,
)
from aima_ugc.contracts.http import ContentFilterSnapshot
from aima_ugc.modules.content.query import ContentReadQuery
from aima_ugc.modules.ingestion.revocation import ImportCampaignRevocationService
from aima_ugc.modules.ingestion.revocation_tables import (
    historical_import_campaign_revocations_table,
)
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.time import beijing_now
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import func, select


def _xlsx(rows: tuple[tuple[str, str], ...]) -> bytes:
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
    for title, content_key in rows:
        sheet.append(
            [
                "小红书",
                title,
                f"{title} 正文",
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


def test_revocation_hides_exclusive_content_and_retains_shared_content(tmp_path: Path) -> None:
    """撤销 Campaign 只移除其独占贡献，共享 Content 仍可查询、分析和导出。"""

    historical_root = tmp_path / "approved-history"
    historical_root.mkdir()
    shared_key = f"revocation-shared-{uuid4()}"
    exclusive_key = f"revocation-exclusive-{uuid4()}"
    (historical_root / "campaign.xlsx").write_bytes(
        _xlsx(
            (
                ("爱玛共享来源", shared_key),
                ("爱玛独占来源", exclusive_key),
            )
        )
    )
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
    try:
        client = TestClient(
            create_app(
                historical_import_service=PostgresHistoricalImportHttpService(runtime),
                import_service=PostgresImportHttpService(runtime),
            )
        )
        pack_id = _keyword_pack(client)
        baseline = client.post(
            "/api/v1/import-batches",
            files=[
                (
                    "file",
                    (
                        "baseline.xlsx",
                        _xlsx((("爱玛共享来源", shared_key),)),
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
        assert client.post(
            f"/api/v1/historical-import-campaigns/{campaign_id}/start"
        ).status_code == 200
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

        revoke_session = runtime.database.new_session()
        try:
            with revoke_session.begin():
                service = ImportCampaignRevocationService(
                    PostgresImportCampaignRevocationRepository(revoke_session)
                )
                preview = service.preview(campaign_id)
                assert preview.eligible is True
                assert preview.already_revoked is False
                assert preview.impact.affected_content_count == 2
                assert preview.impact.hidden_content_count == 1
                assert preview.impact.retained_shared_content_count == 1

                first, created_now = service.revoke(
                    campaign_id,
                    actor_ref="integration-admin",
                    request_id="revocation-request-1",
                    reason="集成测试撤销",
                    revoked_at=beijing_now(),
                )
                second, created_again = service.revoke(
                    campaign_id,
                    actor_ref="integration-admin",
                    request_id="revocation-request-2",
                    reason="重复点击",
                    revoked_at=beijing_now(),
                )
                assert created_now is True
                assert created_again is False
                assert second == first
        finally:
            revoke_session.close()

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
                selected = after_repository.freeze_targets(
                    content_ids=(shared_id, exclusive_id)
                )
                assert [target.content_id for target in selected] == [shared_id]
                assert (
                    after_session.scalar(
                        select(func.count()).select_from(
                            historical_import_campaign_revocations_table
                        )
                    )
                    == 1
                )
        finally:
            after_session.close()
    finally:
        with runtime.database.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE jobs, artifacts, keyword_packs, accounts RESTART IDENTITY CASCADE"
            )
        runtime.close()
