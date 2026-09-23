"""车型保存诊断日志的无数据库回归。"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import aima_ugc.bootstrap.administration_http as administration_http
import pytest
from aima_ugc.contracts.administration import VehicleModelUpdateRequest
from aima_ugc.modules.administration import AdministrationConflict
from aima_ugc.modules.identity import Principal
from aima_ugc.platform.logging.timing import StageTimings


class _Session:
    def __init__(self, *, fail_commit: bool = False) -> None:
        self.committed = False
        self.closed = False
        self.fail_commit = fail_commit

    @contextmanager
    def begin(self):  # type: ignore[no-untyped-def]
        yield
        if self.fail_commit:
            raise RuntimeError("不应进入日志的提交失败内容")
        self.committed = True

    def connection(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True


def test_stage_timings_retains_failed_stage() -> None:
    timings = StageTimings()
    with pytest.raises(ValueError), timings.measure("failed_stage"):
        raise ValueError("不应进入日志的业务内容")
    assert timings.stage_ms["failed_stage"] >= 0
    assert timings.total_ms >= 0


def test_vehicle_update_logs_only_slow_outcomes_with_safe_fields(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    model_id = uuid4()
    brand_id = uuid4()
    model = SimpleNamespace(id=model_id, brand_id=brand_id, version=1, catalog_version=2)
    sessions: list[_Session] = []
    fail_next_commit = False

    def new_session() -> _Session:
        nonlocal fail_next_commit
        session = _Session(fail_commit=fail_next_commit)
        fail_next_commit = False
        sessions.append(session)
        return session

    class Repository:
        def __init__(self, _session: _Session) -> None:
            pass

        def get_model(self, _model_id, *, for_update):  # type: ignore[no-untyped-def]
            return model

        def update_model(self, _model_id, **kwargs):  # type: ignore[no-untyped-def]
            timings = kwargs["timings"]
            with timings.measure("brand_check"):
                if kwargs["classification"].get("brand_id") != brand_id:
                    raise RuntimeError("不应进入日志的失败业务内容")
            with timings.measure("catalog_version"):
                pass
            with timings.measure("model_update"):
                pass
            return model

    monkeypatch.setattr(administration_http, "PostgresVehicleCatalogRepository", Repository)
    monkeypatch.setattr(administration_http, "_audit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(administration_http, "_vehicle_response", lambda *_args: model)
    logger = logging.getLogger("test.vehicle_update_timing")
    logger.setLevel(logging.WARNING)
    runtime = SimpleNamespace(database=SimpleNamespace(new_session=new_session), logger=logger)
    service = administration_http.PostgresAdministrationHttpService(runtime)
    principal = Principal(
        principal_id="vehicle-test-admin",
        display_name="管理员",
        role="administrator",
        source="development",
    )
    with caplog.at_level(logging.WARNING, logger=logger.name):
        monkeypatch.setattr(administration_http, "SLOW_VEHICLE_UPDATE_MS", 10**9)
        service.update_vehicle_model(
            model_id,
            VehicleModelUpdateRequest(display_name="快速敏感车型名", brand_id=brand_id),
            principal=principal,
            request_id="fast-request",
        )
        assert not caplog.records

        monkeypatch.setattr(administration_http, "SLOW_VEHICLE_UPDATE_MS", 0)
        service.update_vehicle_model(
            model_id,
            VehicleModelUpdateRequest(display_name="慢速敏感车型名", brand_id=brand_id),
            principal=principal,
            request_id="slow-request",
        )
        with pytest.raises(AdministrationConflict):
            service.update_vehicle_model(
                model_id,
                VehicleModelUpdateRequest(display_name="失败敏感车型名", brand_id=uuid4()),
                principal=principal,
                request_id="failed-request",
            )
        fail_next_commit = True
        with pytest.raises(RuntimeError, match="提交失败"):
            service.update_vehicle_model(
                model_id,
                VehicleModelUpdateRequest(display_name="提交失败敏感车型名", brand_id=brand_id),
                principal=principal,
                request_id="commit-failed-request",
            )

    assert [(record.request_id, record.outcome) for record in caplog.records] == [
        ("slow-request", "success"),
        ("failed-request", "failed"),
        ("commit-failed-request", "failed"),
    ]
    assert caplog.records[0].vehicle_model_id == str(model_id)
    assert caplog.records[0].changed_fields == ["brand_id", "display_name"]
    assert {"db_checkout", "vehicle_lock", "commit"} <= set(caplog.records[0].stage_ms)
    assert set(caplog.records[1].stage_ms) == {
        "session_create",
        "db_checkout",
        "vehicle_lock",
        "brand_check",
    }
    assert "commit" in caplog.records[2].stage_ms
    assert "敏感" not in caplog.text
    assert [session.committed for session in sessions] == [True, True, False, False]
    assert all(session.closed for session in sessions)
