"""U1—U5 Principal、管理员路由与 Principal Inbox API 回归。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from aima_ugc.bootstrap.api import create_app
from aima_ugc.contracts.product import (
    NotificationItemResponse,
    NotificationListResponse,
    NotificationMarkReadRequest,
    NotificationMarkReadResponse,
)
from aima_ugc.modules.identity import DevelopmentIdentityResolver, Principal
from fastapi.testclient import TestClient


class _UnexpectedAdministrationService:
    """普通用户命中 Router 守卫后不应调用管理员 Service。"""

    def list_analysis_schemes(self) -> object:
        raise AssertionError("普通用户不应进入管理员 Service")

    def list_audit_events(self, *, limit: int) -> object:
        del limit
        raise AssertionError("普通用户不应读取审计 Service")


class _RecordingProductService:
    def __init__(self) -> None:
        self.principal_ids: list[str] = []
        self.item_id = uuid4()

    def list_notifications(self, principal: Principal, *, limit: int) -> NotificationListResponse:
        assert limit == 50
        self.principal_ids.append(principal.principal_id)
        return NotificationListResponse(
            items=(
                NotificationItemResponse(
                    id=self.item_id,
                    event_type="data_export_succeeded",
                    title="导出完成",
                    message="导出文件已经可下载。",
                    resource_type="data_export",
                    resource_id="export-1",
                    is_read=False,
                    created_at=datetime(2026, 9, 2, tzinfo=UTC),
                ),
            ),
            unread_count=1,
        )

    def mark_notifications_read(
        self,
        principal: Principal,
        request: NotificationMarkReadRequest,
    ) -> NotificationMarkReadResponse:
        self.principal_ids.append(principal.principal_id)
        assert request.item_ids == (self.item_id,)
        return NotificationMarkReadResponse(requested_count=1, changed_count=1)


class _UnexpectedConfigurationMutationService:
    """普通用户必须在 Router 角色守卫处停止，不能进入配置 Service。"""

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"普通用户不应调用配置 Service：{name}")


def test_current_principal_exposes_only_the_two_role_model() -> None:
    """普通用户身份仍通过统一 Principal 投影，不引入第三种角色。"""

    client = TestClient(
        create_app(
            identity_resolver=DevelopmentIdentityResolver(
                principal_id="ordinary-user",
                display_name="普通用户",
                role="user",
            )
        )
    )

    response = client.get("/api/v1/principal")

    assert response.status_code == 200
    assert response.json() == {
        "principal_id": "ordinary-user",
        "display_name": "普通用户",
        "role": "user",
        "source": "development",
        "is_administrator": False,
    }


def test_ordinary_user_cannot_read_admin_scheme_or_audit_routes() -> None:
    """管理员页面的只读 Contract 也由后端角色守卫保护。"""

    client = TestClient(
        create_app(
            administration_service=_UnexpectedAdministrationService(),  # type: ignore[arg-type]
            identity_resolver=DevelopmentIdentityResolver(role="user"),
        ),
        raise_server_exceptions=False,
    )

    schemes = client.get("/api/v1/analysis-schemes")
    audits = client.get("/api/v1/audit-events")

    assert schemes.status_code == audits.status_code == 403
    assert schemes.json()["errors"][0]["code"] == "administrator_required"
    assert audits.json()["errors"][0]["code"] == "administrator_required"


def test_ordinary_user_cannot_mutate_keyword_relevance_or_plan_configuration() -> None:
    """词包、全局相关性和采集计划写操作都属于管理员配置边界。"""

    unexpected = _UnexpectedConfigurationMutationService()
    client = TestClient(
        create_app(
            import_service=unexpected,  # type: ignore[arg-type]
            strategy_service=unexpected,  # type: ignore[arg-type]
            identity_resolver=DevelopmentIdentityResolver(role="user"),
        ),
        raise_server_exceptions=False,
    )
    pack_id = uuid4()
    plan_id = uuid4()
    vehicle_id = uuid4()

    responses = (
        client.post("/api/v1/keyword-packs", json={"name": "普通用户词包"}),
        client.post(
            f"/api/v1/keyword-packs/{pack_id}/keywords",
            json={"text": "爱玛"},
        ),
        client.put(
            f"/api/v1/keyword-packs/{pack_id}/enabled",
            json={"enabled": False},
        ),
        client.put(
            "/api/v1/relevance-config",
            json={"keyword_pack_id": str(pack_id)},
        ),
        client.post(
            "/api/v1/collection-plans",
            json={
                "name": "普通用户计划",
                "schedule_expr": "0 8 * * *",
                "platforms": [
                    {
                        "platform": "douyin",
                        "provider_config_id": str(uuid4()),
                        "search_config": {},
                    }
                ],
                "vehicle_model_ids": [str(vehicle_id)],
            },
        ),
        client.put(
            f"/api/v1/collection-plans/{plan_id}/enabled",
            json={"enabled": False},
        ),
    )

    assert all(response.status_code == 403 for response in responses)
    assert all(
        response.json()["errors"][0]["code"] == "administrator_required" for response in responses
    )


def test_notification_inbox_is_resolved_for_the_current_principal() -> None:
    """通知查询和已读操作都携带同一个 Principal，不接受前端伪造用户 ID。"""

    product = _RecordingProductService()
    client = TestClient(
        create_app(
            product_service=product,  # type: ignore[arg-type]
            identity_resolver=DevelopmentIdentityResolver(
                principal_id="ordinary-user",
                display_name="普通用户",
                role="user",
            ),
        )
    )

    listing = client.get("/api/v1/notifications")
    marked = client.put(
        "/api/v1/notifications/read",
        json={"item_ids": [str(product.item_id)]},
    )

    assert listing.status_code == marked.status_code == 200
    assert listing.json()["unread_count"] == 1
    assert marked.json()["changed_count"] == 1
    assert product.principal_ids == ["ordinary-user", "ordinary-user"]
