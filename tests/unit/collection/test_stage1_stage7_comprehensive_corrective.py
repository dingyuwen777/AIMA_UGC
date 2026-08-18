"""Stage 1-7 全面整改的跨边界失败回归。"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from aima_ugc.contracts.canonical import CanonicalCommentV1, CanonicalSourceV1
from aima_ugc.modules.collection.collection_run_executor import CollectionRunExecutor
from aima_ugc.modules.collection.execution import CollectionExecution, CollectionRunRecord
from aima_ugc.modules.collection.planning import (
    CollectionPlanDefinition,
    PlanPlatformDefinition,
    UnsafePlanConfigError,
)
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.logging.formatter import AimaLogFormatter
from pydantic import ValidationError

_NOW = datetime(2026, 8, 18, 1, 0, tzinfo=UTC)


def _plan(**overrides: object) -> CollectionPlanDefinition:
    values: dict[str, object] = {
        "name": "爱玛舆情计划",
        "enabled": True,
        "schedule_expr": "0 */6 * * *",
        "timezone": "Asia/Shanghai",
        "schedule_version": 1,
        "misfire_policy": "latest_only",
        "max_catch_up_runs": 0,
        "detail_policy": "on_change",
        "comment_policy": "adaptive",
        "created_by": None,
        "platforms": (
            PlanPlatformDefinition(
                platform="xhs",
                provider_config_id=uuid4(),
                config={"sort_mode": "latest"},
            ),
        ),
        "keyword_pack_ids": (uuid4(),),
    }
    values.update(overrides)
    return CollectionPlanDefinition(**values)  # type: ignore[arg-type]


def test_plan_rejects_empty_execution_surface_and_secret_suffixes() -> None:
    with pytest.raises(ValueError, match="platform"):
        _plan(platforms=())
    with pytest.raises(ValueError, match="keyword"):
        _plan(keyword_pack_ids=())
    with pytest.raises(UnsafePlanConfigError, match="Secret"):
        PlanPlatformDefinition(
            platform="xhs",
            provider_config_id=uuid4(),
            config={"nested": {"refresh_token": "must-not-persist"}},
        )


def test_comment_observed_fields_reject_unknown_nested_leaf() -> None:
    source = CanonicalSourceV1(
        provider_name="file_import",
        operation="fixture",
        observed_at=_NOW,
    )
    with pytest.raises(ValidationError, match="observed_fields"):
        CanonicalCommentV1(
            platform="xhs",
            external_content_id="content-1",
            external_comment_id="comment-1",
            observed_at=_NOW,
            observed_fields=["metrics.not_a_real_metric"],
            source=source,
        )


def test_log_formatter_recursively_redacts_nested_sensitive_values() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="safe",
        args=(),
        exc_info=None,
    )
    record.event = "test.event"
    record.context = {
        "safe": "visible",
        "password": "nested-password-must-not-survive",
        "tokens": [{"refresh_token": "nested-token-must-not-survive"}],
    }

    rendered = AimaLogFormatter(service="worker").format(record)

    assert "nested-password-must-not-survive" not in rendered
    assert "nested-token-must-not-survive" not in rendered
    assert "visible" in rendered
    assert "***" in rendered


class _Context:
    def __init__(self, job_id) -> None:  # type: ignore[no-untyped-def]
        self._fence = JobExecutionFence(job_id=job_id, lease_token="lease")

    @property
    def fence(self) -> JobExecutionFence:
        return self._fence

    def heartbeat(self, *, progress: int) -> None:
        assert 0 <= progress <= 100

    def cancel_requested(self) -> bool:
        return False


class _Gateway:
    def __init__(self, execution: CollectionExecution) -> None:
        self.execution = execution
        self.finished_status: str | None = None

    def load(self, fence: JobExecutionFence) -> CollectionExecution | None:
        assert fence.job_id == self.execution.run.job_id
        return self.execution

    def start_run(self, run_id, *, fence):  # type: ignore[no-untyped-def]
        assert run_id == self.execution.run.id
        assert fence.job_id == self.execution.run.job_id
        return self.execution.run

    def start_scope(self, scope_id, *, fence):  # type: ignore[no-untyped-def]
        raise AssertionError("zero-scope run 不应启动 scope")

    def checkpoint_scope(self, scope_id, *, fence, pagination_state, progress, stats):  # type: ignore[no-untyped-def]
        raise AssertionError("zero-scope run 不应 checkpoint scope")

    def finish_scope(self, scope_id, *, fence, status, stop_reason, pagination_state, stats):  # type: ignore[no-untyped-def]
        raise AssertionError("zero-scope run 不应 finish scope")

    def finish_run(
        self,
        run_id,
        *,
        fence,
        status,
        requested_count,
        succeeded_count,
        failed_count,
        content_count,
        comment_count,
        error_summary,
    ):  # type: ignore[no-untyped-def]
        assert run_id == self.execution.run.id
        self.finished_status = status
        return self.execution.run


class _NeverScopeExecutor:
    def execute(self, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("zero-scope run 不应执行 Scope")


def test_zero_scope_collection_run_fails_closed() -> None:
    job_id = uuid4()
    run = CollectionRunRecord(
        id=uuid4(),
        job_id=job_id,
        manual_plan_id=None,
        occurrence_id=None,
        trigger_type="api",
        config_snapshot={},
        status="queued",
        started_at=None,
        finished_at=None,
        requested_count=0,
        succeeded_count=0,
        failed_count=0,
        content_count=0,
        comment_count=0,
        error_summary=None,
        created_at=_NOW,
    )
    execution = CollectionExecution(run=run, scopes=())
    gateway = _Gateway(execution)
    context = _Context(job_id)

    result = CollectionRunExecutor(
        gateway=gateway,
        scope_executor=_NeverScopeExecutor(),
    ).execute(fence=context.fence, context=context)

    assert result.outcome == "failed"
    assert gateway.finished_status == "failed"
