"""声音广场投影回填的批次超时与可观测性回归。"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import cast

import pytest
from aima_ugc.adapters.persistence.postgres.voice_plaza_projection import (
    VoicePlazaProjectionState,
)
from aima_ugc.bootstrap import voice_plaza_projection_worker as worker_module
from aima_ugc.bootstrap.runtime import PlatformRuntime
from aima_ugc.modules.content.read_model_job import (
    VOICE_PLAZA_PROJECTION_JOB_TIMEOUT_SECONDS,
    VoicePlazaProjectionJobPayload,
)
from aima_ugc.platform.jobs import JobExecutionFence
from sqlalchemy.exc import OperationalError


class _Transaction:
    """为执行器提供最小事务上下文。"""

    def __enter__(self):  # type: ignore[no-untyped-def]
        return self

    def __exit__(self, exc_type, exc, traceback):  # type: ignore[no-untyped-def]
        return False


class _Session:
    """记录执行器在进入 Repository 前设置的数据库会话参数。"""

    def __init__(self) -> None:
        self.executed: list[tuple[str, object | None]] = []

    def begin(self) -> _Transaction:
        """返回可用于 `with` 的轻量事务。"""

        return _Transaction()

    def execute(self, statement, parameters=None):  # type: ignore[no-untyped-def]
        """保存 SQL 及绑定值，供测试验证 statement timeout。"""

        self.executed.append((str(statement), parameters))
        return SimpleNamespace()

    def close(self) -> None:
        """Fake Session 无外部资源需要释放。"""


class _Database:
    """每次返回同一个 Fake Session，便于检查执行轨迹。"""

    def __init__(self, session: _Session) -> None:
        self.session = session

    def new_session(self) -> _Session:
        """返回测试 Session。"""

        return self.session


class _Context:
    """提供执行器依赖的 Fence、Heartbeat 与取消接口。"""

    fence = JobExecutionFence(job_id=SimpleNamespace(), lease_token="test")  # type: ignore[arg-type]

    def heartbeat(self, *, progress: int) -> None:
        """记录进度不是本测试目标。"""

        del progress

    def cancel_requested(self) -> bool:
        """当前测试不请求取消。"""

        return False


class _ReadyRepository:
    """模拟一个批次完成后投影直接进入 ready。"""

    def __init__(self, session) -> None:  # type: ignore[no-untyped-def]
        del session

    def project_next_batch(self, **kwargs):  # type: ignore[no-untyped-def]
        """返回完成状态，避免测试依赖真实 PostgreSQL。"""

        del kwargs
        return (
            VoicePlazaProjectionState(
                status="ready",
                generation=1,
                last_content_id=None,
                projected_count=500,
                total_content_count=500,
            ),
            500,
        )


class _FailingRepository:
    """模拟数据库语句被 PostgreSQL 取消。"""

    def __init__(self, session) -> None:  # type: ignore[no-untyped-def]
        del session

    def project_next_batch(self, **kwargs):  # type: ignore[no-untyped-def]
        """抛出 SQLAlchemy 数据库异常，验证安全 Retry 日志。"""

        del kwargs
        raise OperationalError("statement", {}, Exception("timeout"))


def _runtime(session: _Session, logger: logging.Logger) -> PlatformRuntime:
    """构造只包含执行器真实依赖的 Runtime。"""

    return cast(
        PlatformRuntime,
        SimpleNamespace(database=_Database(session), logger=logger),
    )


def test_projection_batch_sets_statement_timeout_and_logs_progress(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """每批次必须在 Job Deadline 内有界完成并输出安全进度日志。"""

    session = _Session()
    logger = logging.getLogger("test.voice_plaza_projection_worker.success")
    monkeypatch.setattr(
        worker_module,
        "PostgresVoicePlazaProjectionRepository",
        _ReadyRepository,
    )

    with caplog.at_level(logging.INFO, logger=logger.name):
        result = worker_module.PostgresVoicePlazaProjectionJobExecutor(
            _runtime(session, logger)
        ).execute(
            payload=VoicePlazaProjectionJobPayload(generation=1),
            fence=_Context.fence,
            context=_Context(),  # type: ignore[arg-type]
        )

    assert result.outcome == "succeeded"
    timeout_calls = [entry for entry in session.executed if "set_config" in entry[0]]
    assert timeout_calls == [
        (
            "SELECT set_config('statement_timeout', :timeout, true)",
            {"timeout": "180s"},
        ),
        (
            "SELECT set_config('transaction_timeout', :timeout, true)",
            {"timeout": "240s"},
        ),
    ]
    events = {getattr(record, "event", None): record for record in caplog.records}
    assert events["voice_plaza_projection.batch_started"].batch_number == 1
    completed = events["voice_plaza_projection.batch_completed"]
    assert completed.processed_count == 500
    assert completed.projected_count == 500
    assert completed.total_content_count == 500
    assert completed.duration_ms >= 0
    assert (
        worker_module._BATCHES_PER_JOB  # noqa: SLF001
        * worker_module._BATCH_TRANSACTION_TIMEOUT_SECONDS  # noqa: SLF001
        < VOICE_PLAZA_PROJECTION_JOB_TIMEOUT_SECONDS
    )


def test_projection_batch_database_error_logs_safe_retry(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """数据库失败只记录安全分类并回到统一 Job Retry。"""

    session = _Session()
    logger = logging.getLogger("test.voice_plaza_projection_worker.failure")
    monkeypatch.setattr(
        worker_module,
        "PostgresVoicePlazaProjectionRepository",
        _FailingRepository,
    )

    with caplog.at_level(logging.WARNING, logger=logger.name):
        result = worker_module.PostgresVoicePlazaProjectionJobExecutor(
            _runtime(session, logger)
        ).execute(
            payload=VoicePlazaProjectionJobPayload(generation=1),
            fence=_Context.fence,
            context=_Context(),  # type: ignore[arg-type]
        )

    assert result.outcome == "retry"
    failed = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "voice_plaza_projection.batch_failed"
    )
    assert failed.batch_number == 1
    assert failed.error_type == "OperationalError"
    assert not hasattr(failed, "content_ids")
    assert not hasattr(failed, "statement")
