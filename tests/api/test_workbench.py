"""工作台 HTTP Contract 路由。"""

from datetime import date, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from aima_ugc.bootstrap.api import create_app
from aima_ugc.contracts.workbench import (
    WorkbenchDailyPointResponse,
    WorkbenchLayoutModule,
    WorkbenchLayoutResponse,
    WorkbenchLayoutUpdateRequest,
    WorkbenchMindResponse,
    WorkbenchQuery,
    WorkbenchStreamResponse,
    WorkbenchTrendResponse,
)
from aima_ugc.modules.identity import DevelopmentIdentityResolver
from aima_ugc.modules.workbench.http import WorkbenchLayoutConflict
from aima_ugc.platform.health import ReadinessReport
from fastapi.testclient import TestClient

_BEIJING = ZoneInfo("Asia/Shanghai")


class FakeWorkbenchService:
    """API 测试只记录真实 Contract 输入，不复制 PostgreSQL 实现。"""

    def __init__(self) -> None:
        self.scheme_version_id = uuid4()
        self.last_query: WorkbenchQuery | None = None
        self.last_principal_id: str | None = None
        self.conflict = False

    def get_stream(self, query: WorkbenchQuery) -> WorkbenchStreamResponse:
        """返回空声音流并记录解析后的查询。"""

        self.last_query = query
        return WorkbenchStreamResponse(
            analysis_scheme_version_id=self.scheme_version_id,
            taxonomy_sha256="a" * 64,
            as_of=datetime(2026, 9, 27, 8, 0, tzinfo=_BEIJING),
            items=(),
        )

    def get_trend(self, query: WorkbenchQuery) -> WorkbenchTrendResponse:
        """返回最小趋势快照。"""

        self.last_query = query
        return WorkbenchTrendResponse(
            analysis_scheme_version_id=self.scheme_version_id,
            taxonomy_sha256="a" * 64,
            as_of=datetime(2026, 9, 27, 8, 0, tzinfo=_BEIJING),
            date_from=date(2026, 9, 21),
            date_to=date(2026, 9, 27),
            previous_date_from=date(2026, 9, 14),
            previous_date_to=date(2026, 9, 20),
            total_count=10,
            daily_average=1.43,
            peak_day=date(2026, 9, 25),
            peak_count=3,
            period_change_rate=0.1,
            positive_rate=0.6,
            positive_rate_change_pp=2.0,
            analyzed_count=8,
            analysis_coverage_rate=0.8,
            daily=(WorkbenchDailyPointResponse(day=date(2026, 9, 21), count=1),),
            sentiments=(),
            summary="趋势摘要",
        )

    def get_mind(self, query: WorkbenchQuery) -> WorkbenchMindResponse:
        """返回空心智列表；真实维度由 active Taxonomy 后端实现负责。"""

        self.last_query = query
        return WorkbenchMindResponse(
            analysis_scheme_version_id=self.scheme_version_id,
            taxonomy_sha256="a" * 64,
            as_of=datetime(2026, 9, 27, 8, 0, tzinfo=_BEIJING),
            date_from=date(2026, 9, 21),
            date_to=date(2026, 9, 27),
            previous_date_from=date(2026, 9, 14),
            previous_date_to=date(2026, 9, 20),
            identified_user_count=0,
            unidentified_content_count=0,
            analyzed_count=0,
            analysis_coverage_rate=0,
            dimensions=(),
        )

    def get_layout(self, *, principal_id: str) -> WorkbenchLayoutResponse:
        """返回默认未持久化布局并记录 Principal。"""

        self.last_principal_id = principal_id
        return _layout_response()

    def update_layout(
        self,
        body: WorkbenchLayoutUpdateRequest,
        *,
        principal_id: str,
    ) -> WorkbenchLayoutResponse:
        """模拟 CAS 成功或冲突。"""

        self.last_principal_id = principal_id
        if self.conflict:
            raise WorkbenchLayoutConflict
        return WorkbenchLayoutResponse(
            schema_version=1,
            revision=body.revision + 1,
            modules=body.modules,
            updated_at=datetime(2026, 9, 27, 8, 0, tzinfo=_BEIJING),
        )


def _layout_response() -> WorkbenchLayoutResponse:
    """构造 API 测试复用的三个正式模块默认布局。"""

    return WorkbenchLayoutResponse(
        revision=0,
        modules=(
            WorkbenchLayoutModule(
                module_id="sound-stream", order=0, column_span=6, row_units=48
            ),
            WorkbenchLayoutModule(
                module_id="brand-mind", order=1, column_span=6, row_units=48
            ),
            WorkbenchLayoutModule(
                module_id="ugc-trend", order=2, column_span=6, row_units=48
            ),
        ),
    )


def _client(service: FakeWorkbenchService) -> TestClient:
    """用显式开发身份与健康依赖创建不触碰本机 Runtime 的 API Client。"""

    return TestClient(
        create_app(
            readiness_check=lambda: ReadinessReport(
                database="ok",
                artifact_store="ok",
                log_directory="ok",
            ),
            workbench_service=service,
            identity_resolver=DevelopmentIdentityResolver(),
        )
    )


def test_workbench_query_arrays_and_beijing_dates_reach_service() -> None:
    """GET Query 必须把数组与日期按正式 Workbench Contract 传给 Service。"""

    service = FakeWorkbenchService()
    client = _client(service)

    response = client.get(
        "/api/v1/workbench/stream",
        params=[
            ("date_from", "2026-09-21"),
            ("date_to", "2026-09-27"),
            ("platforms", "xiaohongshu"),
            ("platforms", "douyin"),
            ("sentiments", "正面"),
            ("primary_labels", "外观设计"),
        ],
    )

    assert response.status_code == 200
    assert response.json()["analysis_scheme_version_id"] == str(service.scheme_version_id)
    assert service.last_query is not None
    assert service.last_query.platforms == ("xiaohongshu", "douyin")
    assert service.last_query.sentiments == ("正面",)
    assert service.last_query.primary_labels == ("外观设计",)


def test_workbench_layout_uses_current_principal_and_returns_409_on_revision_conflict() -> None:
    """布局读写绑定当前 Principal，CAS 冲突不得被静默覆盖。"""

    service = FakeWorkbenchService()
    client = _client(service)
    initial = client.get("/api/v1/workbench/layout")

    assert initial.status_code == 200
    assert initial.json()["revision"] == 0
    assert service.last_principal_id

    service.conflict = True
    response = client.put(
        "/api/v1/workbench/layout",
        json={
            "revision": 0,
            "modules": initial.json()["modules"],
        },
    )

    assert response.status_code == 409
    assert response.json()["errors"][0]["code"] == "workbench_layout_conflict"
