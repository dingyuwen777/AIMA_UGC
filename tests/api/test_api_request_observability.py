from __future__ import annotations

import logging

from aima_ugc.bootstrap import api
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient


def _client(*, status_code: int = 200) -> TestClient:
    application = FastAPI()

    @application.get("/voice-plaza-probe")
    async def voice_plaza_probe() -> JSONResponse:
        return JSONResponse({"ok": status_code < 500}, status_code=status_code)

    application.add_middleware(api._RequestContextMiddleware)  # noqa: SLF001
    return TestClient(application)


def test_slow_request_logs_duration_without_query_values(
    caplog,
    monkeypatch,
) -> None:
    ticks = iter((10.0, 11.25))
    monkeypatch.setattr(api, "perf_counter", lambda: next(ticks), raising=False)

    with caplog.at_level(logging.WARNING, logger="aima_ugc"):
        response = _client().get("/voice-plaza-probe?keyword=不应进入日志")

    assert response.status_code == 200
    record = next(item for item in caplog.records if item.event == "api.request_slow")
    assert record.method == "GET"
    assert record.path == "/voice-plaza-probe"
    assert record.status_code == 200
    assert record.duration_ms == 1250
    assert "keyword" not in record.getMessage()
    assert "不应进入日志" not in record.getMessage()


def test_failed_response_is_logged_even_when_fast(caplog, monkeypatch) -> None:
    ticks = iter((20.0, 20.01))
    monkeypatch.setattr(api, "perf_counter", lambda: next(ticks), raising=False)

    with caplog.at_level(logging.WARNING, logger="aima_ugc"):
        response = _client(status_code=503).get("/voice-plaza-probe")

    assert response.status_code == 503
    record = next(item for item in caplog.records if item.event == "api.response_failed")
    assert record.status_code == 503
    assert record.duration_ms == 10
