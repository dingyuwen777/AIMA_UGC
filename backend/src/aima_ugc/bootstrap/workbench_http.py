"""工作台 PostgreSQL Application Service。"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import date, datetime, time, timedelta
from typing import Any, cast
from uuid import UUID

from aima_ugc.adapters.persistence.postgres.workbench import (
    PostgresWorkbenchRepository,
    WorkbenchLayoutRevisionConflict,
)
from aima_ugc.bootstrap.analysis_identity import active_analysis_configuration
from aima_ugc.contracts.workbench import (
    WorkbenchDailyPointResponse,
    WorkbenchLabelResponse,
    WorkbenchLayoutModule,
    WorkbenchLayoutResponse,
    WorkbenchLayoutUpdateRequest,
    WorkbenchMindDimensionResponse,
    WorkbenchMindResponse,
    WorkbenchMindSecondaryResponse,
    WorkbenchQuery,
    WorkbenchSentimentStatResponse,
    WorkbenchStreamItemResponse,
    WorkbenchStreamResponse,
    WorkbenchTrendResponse,
)
from aima_ugc.modules.workbench.http import WorkbenchAnalysisUnavailable, WorkbenchLayoutConflict
from aima_ugc.platform.time import BEIJING_TIMEZONE, beijing_now, beijing_today

from .runtime import PlatformRuntime


_DEFAULT_LAYOUT = (
    WorkbenchLayoutModule(
        module_id="sound-stream", visible=True, order=0, column_span=6, row_units=48
    ),
    WorkbenchLayoutModule(
        module_id="brand-mind", visible=True, order=1, column_span=6, row_units=48
    ),
    WorkbenchLayoutModule(
        module_id="ugc-trend", visible=True, order=2, column_span=6, row_units=48
    ),
)


class PostgresWorkbenchHttpService:
    """工作台聚合只读；布局按 Principal 版本化保存。"""

    def __init__(self, runtime: PlatformRuntime) -> None:
        self._runtime = runtime

    def get_stream(self, query: WorkbenchQuery) -> WorkbenchStreamResponse:
        session = self._runtime.database.new_session()
        try:
            configuration = active_analysis_configuration(session, self._runtime.settings)
            self._require_positive(configuration.taxonomy.sentiments)
            _, _, start_at, end_at = _period(query)
            rows = PostgresWorkbenchRepository(session).stream_rows(
                active_scheme_version_id=configuration.scheme.id,
                query=query,
                start_at=start_at,
                end_at=end_at,
            )
            return WorkbenchStreamResponse(
                analysis_scheme_version_id=configuration.scheme.id,
                taxonomy_sha256=configuration.taxonomy.taxonomy_sha256,
                as_of=beijing_now(),
                items=tuple(_stream_item(row) for row in rows),
            )
        finally:
            session.close()

    def get_trend(self, query: WorkbenchQuery) -> WorkbenchTrendResponse:
        session = self._runtime.database.new_session()
        try:
            configuration = active_analysis_configuration(session, self._runtime.settings)
            self._require_positive(configuration.taxonomy.sentiments)
            date_from, date_to, start_at, end_at = _period(query)
            previous_from, previous_to, previous_start, previous_end = _previous_period(
                date_from, date_to
            )
            repository = PostgresWorkbenchRepository(session)
            current = repository.period_summary(
                active_scheme_version_id=configuration.scheme.id,
                query=query,
                start_at=start_at,
                end_at=end_at,
            )
            previous = repository.period_summary(
                active_scheme_version_id=configuration.scheme.id,
                query=query,
                start_at=previous_start,
                end_at=previous_end,
            )
            daily_rows = repository.daily_counts(
                active_scheme_version_id=configuration.scheme.id,
                query=query,
                start_at=start_at,
                end_at=end_at,
            )
            sentiment_rows = repository.sentiment_counts(
                active_scheme_version_id=configuration.scheme.id,
                query=query,
                start_at=start_at,
                end_at=end_at,
            )
            day_counts = {cast(date, row["day"]): int(row["count"]) for row in daily_rows}
            daily = tuple(
                WorkbenchDailyPointResponse(day=day, count=day_counts.get(day, 0))
                for day in _days(date_from, date_to)
            )
            peak = max(daily, key=lambda item: item.count, default=None)
            total = int(current["total_count"])
            relevant = int(current["relevant_count"])
            positive = int(current["positive_count"])
            previous_relevant = int(previous["relevant_count"])
            previous_positive = int(previous["positive_count"])
            positive_rate = _ratio(positive, relevant)
            previous_positive_rate = _ratio(previous_positive, previous_relevant)
            sentiment_total = sum(int(row["count"]) for row in sentiment_rows)
            sentiments = tuple(
                WorkbenchSentimentStatResponse(
                    sentiment=cast(str, row["sentiment"]),
                    count=int(row["count"]),
                    share=_ratio(int(row["count"]), sentiment_total) or 0.0,
                )
                for row in sentiment_rows
            )
            return WorkbenchTrendResponse(
                analysis_scheme_version_id=configuration.scheme.id,
                taxonomy_sha256=configuration.taxonomy.taxonomy_sha256,
                as_of=beijing_now(),
                date_from=date_from,
                date_to=date_to,
                previous_date_from=previous_from,
                previous_date_to=previous_to,
                total_count=total,
                daily_average=round(total / max(1, len(daily)), 2),
                peak_day=None if peak is None else peak.day,
                peak_count=0 if peak is None else peak.count,
                period_change_rate=_change_rate(total, int(previous["total_count"])),
                positive_rate=positive_rate,
                positive_rate_change_pp=_change_pp(positive_rate, previous_positive_rate),
                analyzed_count=int(current["analyzed_count"]),
                analysis_coverage_rate=_ratio(int(current["analyzed_count"]), total) or 0.0,
                daily=daily,
                sentiments=sentiments,
                summary=_trend_summary(peak, total, int(previous["total_count"])),
            )
        finally:
            session.close()

    def get_mind(self, query: WorkbenchQuery) -> WorkbenchMindResponse:
        session = self._runtime.database.new_session()
        try:
            configuration = active_analysis_configuration(session, self._runtime.settings)
            self._require_positive(configuration.taxonomy.sentiments)
            date_from, date_to, start_at, end_at = _period(query)
            previous_from, previous_to, previous_start, previous_end = _previous_period(
                date_from, date_to
            )
            repository = PostgresWorkbenchRepository(session)
            current_summary = repository.period_summary(
                active_scheme_version_id=configuration.scheme.id,
                query=query,
                start_at=start_at,
                end_at=end_at,
            )
            previous_summary = repository.period_summary(
                active_scheme_version_id=configuration.scheme.id,
                query=query,
                start_at=previous_start,
                end_at=previous_end,
            )
            current = {
                cast(str, row["primary_label"]): row
                for row in repository.mind_counts(
                    active_scheme_version_id=configuration.scheme.id,
                    query=query,
                    start_at=start_at,
                    end_at=end_at,
                )
            }
            previous = {
                cast(str, row["primary_label"]): row
                for row in repository.mind_counts(
                    active_scheme_version_id=configuration.scheme.id,
                    query=query,
                    start_at=previous_start,
                    end_at=previous_end,
                )
            }
            secondary: dict[str, list[WorkbenchMindSecondaryResponse]] = defaultdict(list)
            for row in repository.secondary_mind_counts(
                active_scheme_version_id=configuration.scheme.id,
                query=query,
                start_at=start_at,
                end_at=end_at,
            ):
                secondary[cast(str, row["primary_label"])].append(
                    WorkbenchMindSecondaryResponse(
                        secondary_label=cast(str, row["secondary_label"]),
                        user_count=int(row["user_count"]),
                    )
                )

            current_users = int(current_summary["identified_user_count"])
            previous_users = int(previous_summary["identified_user_count"])
            dimensions = []
            for primary in configuration.taxonomy.primary_labels:
                if primary == "无法分类":
                    continue
                row = current.get(primary)
                user_count = 0 if row is None else int(row["user_count"])
                content_count = 0 if row is None else int(row["content_count"])
                positive_count = 0 if row is None else int(row["positive_content_count"])
                user_share = _ratio(user_count, current_users) or 0.0
                previous_row = previous.get(primary)
                previous_count = 0 if previous_row is None else int(previous_row["user_count"])
                previous_share = _ratio(previous_count, previous_users) or 0.0
                secondary_items = tuple(secondary.get(primary, ()))
                change_pp = round((user_share - previous_share) * 100, 2)
                dimensions.append(
                    WorkbenchMindDimensionResponse(
                        primary_label=primary,
                        user_count=user_count,
                        user_share=user_share,
                        positive_rate=_ratio(positive_count, content_count),
                        user_share_change_pp=change_pp,
                        secondary_labels=secondary_items,
                        change_summary=_mind_summary(
                            primary=primary,
                            change_pp=change_pp,
                            secondary=secondary_items,
                        ),
                    )
                )
            dimensions.sort(key=lambda item: (-item.user_share, item.primary_label))
            total = int(current_summary["total_count"])
            return WorkbenchMindResponse(
                analysis_scheme_version_id=configuration.scheme.id,
                taxonomy_sha256=configuration.taxonomy.taxonomy_sha256,
                as_of=beijing_now(),
                date_from=date_from,
                date_to=date_to,
                previous_date_from=previous_from,
                previous_date_to=previous_to,
                identified_user_count=current_users,
                unidentified_content_count=int(current_summary["unidentified_content_count"]),
                analyzed_count=int(current_summary["analyzed_count"]),
                analysis_coverage_rate=_ratio(int(current_summary["analyzed_count"]), total) or 0.0,
                dimensions=tuple(dimensions),
            )
        finally:
            session.close()

    def get_layout(self, *, principal_id: str) -> WorkbenchLayoutResponse:
        session = self._runtime.database.new_session()
        try:
            return _layout_response(PostgresWorkbenchRepository(session).get_layout(principal_id))
        finally:
            session.close()

    def update_layout(
        self,
        body: WorkbenchLayoutUpdateRequest,
        *,
        principal_id: str,
    ) -> WorkbenchLayoutResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                try:
                    row = PostgresWorkbenchRepository(session).save_layout(
                        principal_id=principal_id,
                        expected_revision=body.revision,
                        modules=body.modules,
                        now=beijing_now(),
                    )
                except WorkbenchLayoutRevisionConflict as exc:
                    raise WorkbenchLayoutConflict from exc
            return _layout_response(row)
        finally:
            session.close()

    @staticmethod
    def _require_positive(sentiments: tuple[str, ...]) -> None:
        if "正面" not in sentiments:
            raise WorkbenchAnalysisUnavailable("当前 active Taxonomy 缺少“正面”情感")


def _period(query: WorkbenchQuery) -> tuple[date, date, datetime, datetime]:
    end_day = query.date_to or beijing_today()
    start_day = query.date_from or end_day - timedelta(days=29)
    start_at = datetime.combine(start_day, time.min, tzinfo=BEIJING_TIMEZONE)
    end_at = datetime.combine(end_day + timedelta(days=1), time.min, tzinfo=BEIJING_TIMEZONE)
    return start_day, end_day, start_at, end_at


def _previous_period(
    current_from: date,
    current_to: date,
) -> tuple[date, date, datetime, datetime]:
    length = (current_to - current_from).days + 1
    previous_to = current_from - timedelta(days=1)
    previous_from = previous_to - timedelta(days=length - 1)
    return (
        previous_from,
        previous_to,
        datetime.combine(previous_from, time.min, tzinfo=BEIJING_TIMEZONE),
        datetime.combine(previous_to + timedelta(days=1), time.min, tzinfo=BEIJING_TIMEZONE),
    )


def _days(start: date, end: date) -> tuple[date, ...]:
    return tuple(start + timedelta(days=index) for index in range((end - start).days + 1))


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 6)


def _change_rate(current: int, previous: int) -> float | None:
    if previous <= 0:
        return None
    return round((current - previous) / previous, 6)


def _change_pp(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    return round((current - previous) * 100, 2)


def _trend_summary(
    peak: WorkbenchDailyPointResponse | None,
    current: int,
    previous: int,
) -> str:
    if peak is None or current == 0:
        return "当前时间范围暂无可展示的 UGC 声量。"
    if previous <= 0:
        return f"{peak.day:%m/%d} 为当前周期声量峰值，共 {peak.count} 条。"
    direction = "上升" if current >= previous else "下降"
    return (
        f"{peak.day:%m/%d} 为当前周期声量峰值，共 {peak.count} 条；"
        f"当前周期总声量较紧邻等长上期{direction}。"
    )


def _mind_summary(
    *,
    primary: str,
    change_pp: float,
    secondary: tuple[WorkbenchMindSecondaryResponse, ...],
) -> str:
    direction = "上升" if change_pp > 0 else "下降" if change_pp < 0 else "持平"
    detail = f"；当前讨论集中在“{secondary[0].secondary_label}”" if secondary else ""
    return f"{primary}用户占比较紧邻等长上期{direction} {abs(change_pp):.2f}pp{detail}。"


def _stream_item(row: Mapping[str, Any]) -> WorkbenchStreamItemResponse:
    labels = row["effective_labels"] or ()
    return WorkbenchStreamItemResponse(
        content_id=cast(UUID, row["content_id"]),
        platform=cast(Any, row["platform"]),
        author_display_name=cast(str | None, row["author_display_name"]),
        published_at=cast(datetime | None, row["published_at"]),
        title=cast(str | None, row["title"]),
        text=cast(str | None, row["body_text"]),
        sentiment=cast(str | None, row["effective_sentiment"]),
        voice_type=cast(str | None, row["effective_voice_type"]),
        labels=tuple(
            WorkbenchLabelResponse(
                primary_label=cast(str, item["primary_label"]),
                secondary_label=cast(str, item["secondary_label"]),
            )
            for item in labels
            if isinstance(item, Mapping)
            and isinstance(item.get("primary_label"), str)
            and isinstance(item.get("secondary_label"), str)
        ),
        analysis_current=row["result_id"] is not None,
        vehicle_names=tuple(cast(Sequence[str], row["vehicle_names"] or ())),
    )


def _layout_response(row: Mapping[str, Any] | None) -> WorkbenchLayoutResponse:
    if row is None:
        return WorkbenchLayoutResponse(
            schema_version=1,
            revision=0,
            modules=_DEFAULT_LAYOUT,
            updated_at=None,
        )
    return WorkbenchLayoutResponse(
        schema_version=1,
        revision=int(row["revision"]),
        modules=tuple(WorkbenchLayoutModule.model_validate(item) for item in row["layout"]),
        updated_at=cast(datetime, row["updated_at"]),
    )


__all__ = ["PostgresWorkbenchHttpService"]
