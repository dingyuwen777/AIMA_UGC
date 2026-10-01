"""报告管理员边界：普通用户不能读取依据、下载文件或提交任务。"""

from uuid import uuid4

import pytest
from aima_ugc.bootstrap.api import create_app
from aima_ugc.modules.identity import DevelopmentIdentityResolver
from fastapi.testclient import TestClient


class _ForbiddenReportService:
    """权限拒绝必须发生在数据库、文件或外部服务调用之前。"""

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"非管理员调用了报告 Service：{name}")


@pytest.mark.parametrize(
    ("method", "suffix"),
    [
        ("post", "/preflight"),
        ("post", ""),
        ("get", ""),
        ("get", "/{report_id}"),
        ("post", "/{report_id}/retry"),
        ("post", "/{report_id}/publish"),
        ("post", "/{report_id}/cancel"),
        ("get", "/{report_id}/artifacts/{artifact_id}/download"),
    ],
)
def test_report_endpoints_reject_ordinary_user_before_service(method: str, suffix: str) -> None:
    app = create_app(
        report_runs_service=_ForbiddenReportService(),  # type: ignore[arg-type]
        identity_resolver=DevelopmentIdentityResolver(role="user"),
    )
    path = "/api/v1/reports" + suffix.format(report_id=uuid4(), artifact_id=uuid4())
    payload = (
        {"brand_id": str(uuid4()), "start_date": "2026-09-01", "end_date": "2026-09-02"}
        if method == "post" and suffix in {"", "/preflight"}
        else None
    )
    with TestClient(app) as client:
        response = client.request(method, path, json=payload)
    assert response.status_code == 403
    assert response.json()["errors"][0]["code"] == "administrator_required"
