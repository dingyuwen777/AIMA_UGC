"""下载管理操作的 Principal 守卫与未知提交回执恢复。"""

from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.providers.wisersone.export import WisersOneExporter
from aima_ugc.bootstrap import api as api_module
from aima_ugc.bootstrap.feishu_auth_http import (
    FeishuAuthRoutes,
    FeishuAuthSettings,
    FeishuLoginRequiredResolver,
    install_feishu_auth_routes,
)
from aima_ugc.contracts.http import HttpErrorResponse
from aima_ugc.modules.identity import DevelopmentIdentityResolver
from aima_ugc.modules.ingestion.historical_tables import historical_import_campaigns_table
from aima_ugc.modules.ingestion.wisersone_tables import wisersone_downloads_table
from aima_ugc.platform.jobs.tables import jobs_table
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from tests.integration.ingestion.test_wisersone_workflow import _create
from tests.integration.ingestion.test_wisersone_workflow import workflow as workflow


@pytest.mark.parametrize("authenticated", [False, True], ids=["no-session", "ordinary-user"])
def test_download_write_guards_reject_without_jobs_or_sends_and_keep_read_gate(
    workflow, authenticated: bool
) -> None:  # type: ignore[no-untyped-def]
    runtime, website, administrator_client, brand, _, _ = workflow
    created = _create(administrator_client, brand)
    download_id = created["id"]
    if authenticated:
        application = api_module.create_app(
            identity_resolver=DevelopmentIdentityResolver(role="user")
        )
        write_status, write_code = 403, "administrator_required"
    else:
        # 复用正式飞书会话解析和 401 翻译，不用测试自行伪造匿名 Principal。
        auth = FeishuAuthRoutes(
            auth_settings=FeishuAuthSettings(
                app_id="wisersone-permission-test",
                admin_group_id="administrator-test",
                user_group_id="user-test",
                redirect_uri="http://testserver/api/v1/auth/feishu/callback",
                cookie_secure=False,
            ),
            session_factory=runtime.database.new_session,
        )
        application = api_module.create_app(identity_resolver=FeishuLoginRequiredResolver(auth))
        install_feishu_auth_routes(application, auth_routes=auth)
        write_status, write_code = 401, "authentication_required"
    client = TestClient(application)
    try:
        rejected = [
            client.post(
                "/api/v1/wisersone-downloads",
                json={"client_idempotency_key": str(uuid4()), "brand_ids": [brand]},
            ),
            client.post(f"/api/v1/wisersone-downloads/{download_id}/cancel"),
            client.post(f"/api/v1/wisersone-downloads/{download_id}/retry"),
        ]
        for response in rejected:
            assert response.status_code == write_status, response.text
            error = HttpErrorResponse.model_validate(response.json())
            assert error.status == write_status and error.request_id
            assert error.errors[0].code == write_code

        for path in (
            "/api/v1/wisersone-downloads",
            f"/api/v1/wisersone-downloads/{download_id}",
        ):
            # 下载运行记录属于管理员管理数据，读取同样在业务入口前拒绝。
            response = client.get(path)
            assert response.status_code == write_status, response.text
            error = HttpErrorResponse.model_validate(response.json())
            assert error.status == write_status and error.request_id
            assert error.errors[0].code == write_code
        unchanged = administrator_client.get(f"/api/v1/wisersone-downloads/{download_id}").json()
        assert unchanged["status"] == "queued" and unchanged["send_state"] == "not_sent"
        assert unchanged["cancel_requested_at"] is None
        assert website.submissions == 0
        with runtime.database.engine.connect() as connection:
            assert connection.scalar(select(func.count()).select_from(jobs_table)) == 1
            assert (
                connection.scalar(select(func.count()).select_from(wisersone_downloads_table)) == 1
            )
            assert connection.scalar(select(jobs_table.c.status)) == "queued"
    finally:
        client.close()


def test_unknown_submission_with_host_receipt_resumes_same_task_without_resending(workflow) -> None:  # type: ignore[no-untyped-def]
    runtime, website, client, brand, new_worker, tick = workflow
    website.unknown = True
    website.receipt_before_failure = True
    created = _create(client, brand)
    download_id = UUID(created["id"])
    tick(new_worker())
    uncertain = client.get(f"/api/v1/wisersone-downloads/{download_id}").json()
    assert uncertain["status"] == "attention" and uncertain["send_state"] == "unknown"
    assert uncertain["website_task_id"] is None
    assert runtime.settings.wisersone_auth_dir is not None
    # 新 Exporter 从真实宿主目录读取 JSON，不能依赖旧 Worker 的内存。
    saved = WisersOneExporter(auth_dir=runtime.settings.wisersone_auth_dir).saved_task(download_id)
    assert saved is not None and saved.task_id == f"website-{download_id}"
    restored = client.post(f"/api/v1/wisersone-downloads/{download_id}/retry")
    assert restored.status_code == 200, restored.text
    assert restored.json()["id"] == str(download_id)
    assert restored.json()["send_state"] == "confirmed"
    assert restored.json()["website_task_id"] == saved.task_id
    assert client.post(f"/api/v1/wisersone-downloads/{download_id}/retry").status_code == 409

    worker = new_worker()
    result = {}
    for _ in range(25):
        tick(worker)
        result = client.get(f"/api/v1/wisersone-downloads/{download_id}").json()
        if result["status"] in {"succeeded", "failed", "partial_failed"}:
            break
    assert result["status"] == "succeeded", result
    assert result["website_task_id"] == saved.task_id and result["campaign_id"]
    assert website.submissions == 1
    assert website.polled_tasks and {task.task_id for task in website.polled_tasks} == {
        saved.task_id
    }
    with runtime.database.engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(wisersone_downloads_table)) == 1
        assert (
            connection.scalar(
                select(func.count())
                .select_from(historical_import_campaigns_table)
                .where(
                    historical_import_campaigns_table.c.client_idempotency_key
                    == f"wisersone:{download_id}"
                )
            )
            == 1
        )
        payloads = (
            connection.execute(
                select(jobs_table.c.payload).where(
                    jobs_table.c.job_type == "ingestion.wisersone-download.v1"
                )
            )
            .scalars()
            .all()
        )
        assert payloads and {payload["download_id"] for payload in payloads} == {str(download_id)}
