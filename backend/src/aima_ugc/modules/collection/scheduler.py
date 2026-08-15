"""Collection Scheduler 的首版 Cron 与 latest-only 领域语义。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aima_ugc.modules.collection.planning import CollectionPlanRecord

MISFIRE_SUPERSEDED = "misfire_superseded"
_MAX_CALENDAR_SEARCH_DAYS = 366 * 5
_MAX_MISFIRE_SLOTS = 10_000


class ScheduleExpressionError(ValueError):
    """首版五字段 Cron 表达式无法安全解释。"""


class SchedulerBacklogLimitError(RuntimeError):
    """积压逻辑调度点异常过多，拒绝在一个事务中无限展开。"""


@dataclass(frozen=True, slots=True)
class SkippedScheduleSlot:
    """一个被 latest-only 明确覆盖的历史逻辑调度点。"""

    scheduled_for: datetime
    reason: str = MISFIRE_SUPERSEDED


@dataclass(frozen=True, slots=True)
class SchedulerPlanDecision:
    """锁定 Plan 后一次 Scheduler 事务需要提交的全部调度决定。"""

    skipped: tuple[SkippedScheduleSlot, ...]
    enqueue_for: datetime | None
    last_scheduled_at: datetime | None
    next_run_at: datetime | None
    initialized: bool = False


@dataclass(frozen=True, slots=True)
class _CronField:
    values: frozenset[int]
    wildcard: bool


@dataclass(frozen=True, slots=True)
class _CronExpression:
    minute: _CronField
    hour: _CronField
    day_of_month: _CronField
    month: _CronField
    day_of_week: _CronField


def next_schedule_time(schedule_expr: str, timezone: str, after: datetime) -> datetime:
    """返回 `after` 之后首个五字段 Cron 时刻，统一转换为 UTC。"""
    if after.utcoffset() is None:
        raise ValueError("after 必须包含时区")
    cron = _parse_cron(schedule_expr)
    try:
        zone = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ScheduleExpressionError(f"未知时区: {timezone}") from exc

    local_after = after.astimezone(zone)
    current_date = local_after.date()
    minutes = sorted(cron.minute.values)
    hours = sorted(cron.hour.values)

    for day_offset in range(_MAX_CALENDAR_SEARCH_DAYS + 1):
        candidate_date = current_date + timedelta(days=day_offset)
        if not _date_matches(cron, candidate_date):
            continue
        for hour in hours:
            for minute in minutes:
                candidate = datetime.combine(
                    candidate_date,
                    time(hour=hour, minute=minute),
                    tzinfo=zone,
                )
                if candidate > local_after:
                    return candidate.astimezone(UTC)

    raise ScheduleExpressionError("Cron 在首版五年搜索窗口内没有可执行时刻")


def resolve_scheduler_plan(plan: CollectionPlanRecord, *, now: datetime) -> SchedulerPlanDecision:
    """按已批准 `latest_only` 策略解析一个已加锁 Plan。"""
    if now.utcoffset() is None:
        raise ValueError("now 必须包含时区")

    if not plan.enabled or plan.schedule_expr is None:
        return SchedulerPlanDecision(
            skipped=(),
            enqueue_for=None,
            last_scheduled_at=plan.last_scheduled_at,
            next_run_at=plan.next_run_at,
        )
    if plan.misfire_policy != "latest_only":
        raise ValueError("Scheduler 首版只允许 latest_only misfire_policy")
    if plan.max_catch_up_runs != 0:
        raise ValueError("Scheduler 首版 max_catch_up_runs 必须为 0")

    now_utc = now.astimezone(UTC)
    if plan.next_run_at is None:
        return SchedulerPlanDecision(
            skipped=(),
            enqueue_for=None,
            last_scheduled_at=plan.last_scheduled_at,
            next_run_at=next_schedule_time(plan.schedule_expr, plan.timezone, now_utc),
            initialized=True,
        )

    next_run_at = plan.next_run_at.astimezone(UTC)
    if next_run_at > now_utc:
        return SchedulerPlanDecision(
            skipped=(),
            enqueue_for=None,
            last_scheduled_at=plan.last_scheduled_at,
            next_run_at=next_run_at,
        )

    due_slots: list[datetime] = []
    cursor = next_run_at
    while cursor <= now_utc:
        due_slots.append(cursor)
        if len(due_slots) > _MAX_MISFIRE_SLOTS:
            raise SchedulerBacklogLimitError(
                "Scheduler 积压超过单次事务安全上限，需人工确认后再恢复"
            )
        cursor = next_schedule_time(plan.schedule_expr, plan.timezone, cursor)

    newest_due = due_slots[-1]
    return SchedulerPlanDecision(
        skipped=tuple(SkippedScheduleSlot(scheduled_for=item) for item in due_slots[:-1]),
        enqueue_for=newest_due,
        last_scheduled_at=newest_due,
        next_run_at=cursor,
    )


def _parse_cron(value: str) -> _CronExpression:
    fields = value.split()
    if len(fields) != 5:
        raise ScheduleExpressionError("首版 schedule_expr 必须是五字段 Cron")
    return _CronExpression(
        minute=_parse_field(fields[0], minimum=0, maximum=59, name="minute"),
        hour=_parse_field(fields[1], minimum=0, maximum=23, name="hour"),
        day_of_month=_parse_field(fields[2], minimum=1, maximum=31, name="day_of_month"),
        month=_parse_field(fields[3], minimum=1, maximum=12, name="month"),
        day_of_week=_parse_field(
            fields[4], minimum=0, maximum=7, name="day_of_week", normalize_sunday=True
        ),
    )


def _parse_field(
    raw: str,
    *,
    minimum: int,
    maximum: int,
    name: str,
    normalize_sunday: bool = False,
) -> _CronField:
    wildcard = raw == "*"
    values: set[int] = set()
    if not raw:
        raise ScheduleExpressionError(f"Cron {name} 不能为空")

    for part in raw.split(","):
        if not part:
            raise ScheduleExpressionError(f"Cron {name} 包含空列表项")
        base, step = _split_step(part, name=name)
        if base == "*":
            start, end = minimum, maximum
        elif "-" in base:
            start_text, end_text = base.split("-", 1)
            start = _parse_int(start_text, name=name)
            end = _parse_int(end_text, name=name)
            if start > end:
                raise ScheduleExpressionError(f"Cron {name} 范围起点不能大于终点")
        else:
            start = _parse_int(base, name=name)
            end = start

        if start < minimum or end > maximum:
            raise ScheduleExpressionError(f"Cron {name} 必须位于 {minimum}..{maximum}")
        for item in range(start, end + 1, step):
            values.add(0 if normalize_sunday and item == 7 else item)

    if not values:
        raise ScheduleExpressionError(f"Cron {name} 没有有效取值")
    return _CronField(values=frozenset(values), wildcard=wildcard)


def _split_step(part: str, *, name: str) -> tuple[str, int]:
    if "/" not in part:
        return part, 1
    if part.count("/") != 1:
        raise ScheduleExpressionError(f"Cron {name} step 格式非法")
    base, step_text = part.split("/", 1)
    step = _parse_int(step_text, name=f"{name} step")
    if step <= 0:
        raise ScheduleExpressionError(f"Cron {name} step 必须大于 0")
    return base, step


def _parse_int(value: str, *, name: str) -> int:
    if not value.isascii() or not value.isdigit():
        raise ScheduleExpressionError(f"Cron {name} 首版只接受数字、*、范围、列表和步长")
    return int(value)


def _date_matches(cron: _CronExpression, candidate: date) -> bool:
    if candidate.month not in cron.month.values:
        return False
    dom_matches = candidate.day in cron.day_of_month.values
    cron_weekday = (candidate.weekday() + 1) % 7
    dow_matches = cron_weekday in cron.day_of_week.values

    if cron.day_of_month.wildcard or cron.day_of_week.wildcard:
        return dom_matches and dow_matches
    return dom_matches or dow_matches
