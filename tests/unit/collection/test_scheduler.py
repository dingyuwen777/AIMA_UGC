"""Stage 7 Scheduler 纯领域语义测试。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from aima_ugc.modules.collection.planning import CollectionPlanRecord
from aima_ugc.modules.collection.scheduler import (
    MISFIRE_SUPERSEDED,
    ScheduleExpressionError,
    next_schedule_time,
    resolve_scheduler_plan,
)


def _plan(*, next_run_at: datetime | None, enabled: bool = True) -> CollectionPlanRecord:
    now = datetime(2026, 8, 15, 0, 0, tzinfo=UTC)
    return CollectionPlanRecord(
        id=uuid4(),
        name="爱玛舆情默认计划",
        enabled=enabled,
        schedule_expr="0 */6 * * *",
        timezone="Asia/Shanghai",
        schedule_version=3,
        next_run_at=next_run_at,
        last_scheduled_at=None,
        misfire_policy="latest_only",
        max_catch_up_runs=0,
        detail_policy="on_change",
        comment_policy="adaptive",
        request_budget=100,
        created_by=None,
        created_at=now,
        updated_at=now,
        platforms=(),
        keyword_pack_ids=(),
    )


def test_first_release_cron_uses_plan_timezone_and_returns_utc() -> None:
    # 2026-08-15 17:00 Asia/Shanghai 后的下一个 6 小时点是本地 18:00，即 10:00 UTC。
    result = next_schedule_time(
        "0 */6 * * *",
        "Asia/Shanghai",
        datetime(2026, 8, 15, 9, 0, tzinfo=UTC),
    )

    assert result == datetime(2026, 8, 15, 10, 0, tzinfo=UTC)


def test_cron_rejects_non_five_field_or_named_values() -> None:
    with pytest.raises(ScheduleExpressionError):
        next_schedule_time("0 0 * * * *", "Asia/Shanghai", datetime.now(UTC))

    with pytest.raises(ScheduleExpressionError):
        next_schedule_time("0 0 * JAN *", "Asia/Shanghai", datetime.now(UTC))


def test_uninitialized_plan_only_sets_future_cursor_without_backfill() -> None:
    now = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)

    decision = resolve_scheduler_plan(_plan(next_run_at=None), now=now)

    assert decision.enqueue_for is None
    assert decision.skipped == ()
    assert decision.last_scheduled_at is None
    assert decision.next_run_at == datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
    assert decision.initialized is True


def test_latest_only_skips_older_due_slots_and_enqueues_newest() -> None:
    # next_run_at=06:00 本地；Scheduler 17:00 本地恢复，因此 06:00、12:00 已到期。
    plan = _plan(next_run_at=datetime(2026, 8, 14, 22, 0, tzinfo=UTC))
    now = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)

    decision = resolve_scheduler_plan(plan, now=now)

    assert [item.scheduled_for for item in decision.skipped] == [
        datetime(2026, 8, 14, 22, 0, tzinfo=UTC)
    ]
    assert {item.reason for item in decision.skipped} == {MISFIRE_SUPERSEDED}
    assert decision.enqueue_for == datetime(2026, 8, 15, 4, 0, tzinfo=UTC)
    assert decision.last_scheduled_at == datetime(2026, 8, 15, 4, 0, tzinfo=UTC)
    assert decision.next_run_at == datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
    assert decision.initialized is False


def test_future_or_disabled_plan_does_not_emit_occurrence() -> None:
    future = datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
    now = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)

    future_decision = resolve_scheduler_plan(_plan(next_run_at=future), now=now)
    disabled_decision = resolve_scheduler_plan(_plan(next_run_at=future, enabled=False), now=now)

    assert future_decision.enqueue_for is None
    assert future_decision.skipped == ()
    assert future_decision.next_run_at == future
    assert disabled_decision.enqueue_for is None
    assert disabled_decision.skipped == ()
    assert disabled_decision.next_run_at == future
