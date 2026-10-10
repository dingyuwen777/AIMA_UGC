"""工作台 PostgreSQL Application Service。"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import date, datetime, time, timedelta
from typing import Any, Literal, cast
from uuid import UUID

from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.workbench import (
    PostgresWorkbenchRepository,
    WorkbenchLayoutRevisionConflict,
)
from aima_ugc.adapters.persistence.postgres.workbench_snapshots import (
    PostgresWorkbenchSnapshotRepository,
    WorkbenchSnapshotModule,
    WorkbenchSnapshotRefresh,
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
    WorkbenchStreamQuery,
    WorkbenchStreamResponse,
    WorkbenchTrendResponse,
)
from aima_ugc.modules.content.content_cursor import ContentCursorCodec, ContentCursorPosition
from aima_ugc.modules.content.http import ContentCursorUnavailable
from aima_ugc.modules.workbench.http import WorkbenchAnalysisUnavailable, WorkbenchLayoutConflict
from aima_ugc.modules.workbench.jobs import (
    WORKBENCH_SNAPSHOT_JOB_MAX_ATTEMPTS,
    WORKBENCH_SNAPSHOT_JOB_PAYLOAD_VERSION,
    WORKBENCH_SNAPSHOT_JOB_PRIORITY,
    WORKBENCH_SNAPSHOT_JOB_TIMEOUT_SECONDS,
    WORKBENCH_SNAPSHOT_JOB_TYPE,
    WorkbenchSnapshotJobPayload,
)
from aima_ugc.platform.jobs import JobRecord
from aima_ugc.platform.security import SecretFileError, read_secret_file
from aima_ugc.platform.time import BEIJING_TIMEZONE, beijing_now, beijing_today

from .runtime import PlatformRuntime

_DEFAULT_LAYOUT = (
    WorkbenchLayoutModule(
        module_id="sound-stream", visible=True, order=0, column_span=12, row_units=48
    ),
    WorkbenchLayoutModule(
        module_id="brand-mind", visible=True, order=1, column_span=6, row_units=48
    ),
    WorkbenchLayoutModule(
        module_id="ugc-trend", visible=True, order=2, column_span=6, row_units=48
    ),
)

_SNAPSHOT_FAILURE_RETRY_DELAY = timedelta(seconds=60)


class PostgresWorkbenchHttpService:
    """工作台聚合只读；布局按 Principal 版本化保存。"""

    def __init__(
        self,
        runtime: PlatformRuntime,
        *,
        cursor_signing_secret: bytes | None = None,
        use_snapshot_cache: bool = True,
    ) -> None:
        self._runtime = runtime
        self._cursor_signing_secret = cursor_signing_secret
        self._use_snapshot_cache = use_snapshot_cache

    def get_stream(self, query: WorkbenchStreamQuery) -> WorkbenchStreamResponse:
        session = self._runtime.database.new_session()
        try:
            codec = self._cursor_codec()
            query_hash = _stream_query_hash(query)
            position = codec.decode(query.cursor, query_hash=query_hash) if query.cursor else None
            configuration = active_analysis_configuration(session, self._runtime.settings)
            self._require_positive(configuration.taxonomy.sentiments)
            _, _, start_at, end_at = _period(query)
            rows = PostgresWorkbenchRepository(session).stream_rows(
                active_scheme_version_id=configuration.scheme.id,
                query=query,
                start_at=start_at,
                end_at=end_at,
                limit=query.limit + 1,
                position=position,
            )
            page_rows = rows[: query.limit]
            has_more = len(rows) > query.limit
            next_cursor = None
            if has_more and page_rows:
                last = page_rows[-1]
                next_cursor = codec.encode(
                    ContentCursorPosition(
                        sort_at=cast(datetime, last["published_at"]),
                        content_id=cast(UUID, last["content_id"]),
                    ),
                    query_hash=query_hash,
                )
            response = WorkbenchStreamResponse(
                analysis_scheme_version_id=configuration.scheme.id,
                taxonomy_sha256=configuration.taxonomy.taxonomy_sha256,
                as_of=beijing_now(),
                items=tuple(_stream_item(row) for row in page_rows),
                next_cursor=next_cursor,
                has_more=has_more,
            )
            session.commit()
            return response
        finally:
            session.close()

    def _cursor_codec(self) -> ContentCursorCodec:
        secret = self._cursor_signing_secret
        if secret is None:
            try:
                secret = (
                    read_secret_file(
                        self._runtime.settings.content_cursor_signing_key_file,
                        root=self._runtime.settings.secret_dir,
                    )
                    .get_secret_value()
                    .encode("utf-8")
                )
            except SecretFileError as exc:
                raise ContentCursorUnavailable from exc
        try:
            return ContentCursorCodec(secret=secret)
        except ValueError as exc:
            raise ContentCursorUnavailable from exc

    def get_trend(self, query: WorkbenchQuery) -> WorkbenchTrendResponse:
        if self._use_snapshot_cache:
            return cast(WorkbenchTrendResponse, self._get_snapshot_response("trend", query))
        return self._compute_trend(query)

    def _compute_trend(self, query: WorkbenchQuery) -> WorkbenchTrendResponse:
        session = self._runtime.database.new_session()
        try:
            configuration = active_analysis_configuration(session, self._runtime.settings)
            self._require_positive(configuration.taxonomy.sentiments)
            date_from, date_to, start_at, end_at = _period(query)
            previous_from, previous_to, previous_start, _previous_end = _previous_period(
                date_from, date_to
            )
            repository = PostgresWorkbenchRepository(session)
            snapshot = repository.trend_snapshot(
                active_scheme_version_id=configuration.scheme.id,
                query=query,
                previous_start_at=previous_start,
                current_start_at=start_at,
                end_at=end_at,
            )
            current = cast(Mapping[str, Any], snapshot["current_summary"])
            previous = cast(Mapping[str, Any], snapshot["previous_summary"])
            daily_rows = cast(Sequence[Mapping[str, Any]], snapshot["daily_counts"])
            sentiment_rows = cast(Sequence[Mapping[str, Any]], snapshot["sentiment_counts"])
            day_counts = {_json_date(row["day"]): int(row["count"]) for row in daily_rows}
            daily = tuple(
                WorkbenchDailyPointResponse(day=day, count=day_counts.get(day, 0))
                for day in _days(date_from, date_to)
            )
            total = int(current["total_count"])
            peak = max(daily, key=lambda item: item.count, default=None) if total else None
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
            response = WorkbenchTrendResponse(
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
            session.commit()
            return response
        finally:
            session.close()

    def get_mind(self, query: WorkbenchQuery) -> WorkbenchMindResponse:
        if self._use_snapshot_cache:
            return cast(WorkbenchMindResponse, self._get_snapshot_response("mind", query))
        return self._compute_mind(query)

    def _compute_mind(self, query: WorkbenchQuery) -> WorkbenchMindResponse:
        session = self._runtime.database.new_session()
        try:
            configuration = active_analysis_configuration(session, self._runtime.settings)
            self._require_positive(configuration.taxonomy.sentiments)
            date_from, date_to, start_at, end_at = _period(query)
            previous_from, previous_to, previous_start, _previous_end = _previous_period(
                date_from, date_to
            )
            repository = PostgresWorkbenchRepository(session)
            snapshot = repository.mind_snapshot(
                active_scheme_version_id=configuration.scheme.id,
                query=query,
                previous_start_at=previous_start,
                current_start_at=start_at,
                end_at=end_at,
            )
            current_summary = cast(Mapping[str, Any], snapshot["current_summary"])
            previous_summary = cast(Mapping[str, Any], snapshot["previous_summary"])
            current = {
                cast(str, row["primary_label"]): row
                for row in cast(Sequence[Mapping[str, Any]], snapshot["current_primary"])
            }
            previous = {
                cast(str, row["primary_label"]): row
                for row in cast(Sequence[Mapping[str, Any]], snapshot["previous_primary"])
            }
            secondary: dict[str, list[WorkbenchMindSecondaryResponse]] = defaultdict(list)
            for row in cast(Sequence[Mapping[str, Any]], snapshot["current_secondary"]):
                secondary[cast(str, row["primary_label"])].append(
                    WorkbenchMindSecondaryResponse(
                        secondary_label=cast(str, row["secondary_label"]),
                        content_count=int(row["content_count"]),
                    )
                )

            current_contents = int(current_summary["relevant_content_count"])
            previous_contents = int(previous_summary["relevant_content_count"])
            dimensions = []
            for primary in configuration.taxonomy.primary_labels:
                if primary == "无法分类":
                    continue
                current_row = current.get(primary)
                content_count = 0 if current_row is None else int(current_row["content_count"])
                positive_count = (
                    0 if current_row is None else int(current_row["positive_content_count"])
                )
                content_share = _ratio(content_count, current_contents) or 0.0
                previous_row = previous.get(primary)
                previous_count = 0 if previous_row is None else int(previous_row["content_count"])
                previous_share = _ratio(previous_count, previous_contents) or 0.0
                secondary_items = tuple(secondary.get(primary, ()))
                change_pp = round((content_share - previous_share) * 100, 2)
                dimensions.append(
                    WorkbenchMindDimensionResponse(
                        primary_label=primary,
                        content_count=content_count,
                        content_share=content_share,
                        positive_rate=_ratio(positive_count, content_count),
                        content_share_change_pp=change_pp,
                        secondary_labels=secondary_items,
                        change_summary=_mind_summary(
                            primary=primary,
                            change_pp=change_pp,
                            secondary=secondary_items,
                        ),
                    )
                )
            dimensions.sort(key=lambda item: (-item.content_share, item.primary_label))
            total = int(current_summary["total_count"])
            response = WorkbenchMindResponse(
                analysis_scheme_version_id=configuration.scheme.id,
                taxonomy_sha256=configuration.taxonomy.taxonomy_sha256,
                as_of=beijing_now(),
                date_from=date_from,
                date_to=date_to,
                previous_date_from=previous_from,
                previous_date_to=previous_to,
                relevant_content_count=current_contents,
                unidentified_content_count=int(current_summary["unidentified_content_count"]),
                analyzed_count=int(current_summary["analyzed_count"]),
                analysis_coverage_rate=_ratio(int(current_summary["analyzed_count"]), total) or 0.0,
                dimensions=tuple(dimensions),
            )
            session.commit()
            return response
        finally:
            session.close()

    def _get_snapshot_response(
        self,
        module: WorkbenchSnapshotModule,
        query: WorkbenchQuery,
    ) -> WorkbenchMindResponse | WorkbenchTrendResponse:
        """热路径读取持久最近成功结果；陈旧结果立即返回并幂等安排后台刷新。"""

        resolved_query = _resolved_snapshot_query(query)
        query_hash = _snapshot_query_hash(module, resolved_query)
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                configuration = active_analysis_configuration(session, self._runtime.settings)
                self._require_positive(configuration.taxonomy.sentiments)
                snapshots = PostgresWorkbenchSnapshotRepository(session)
                revision = snapshots.current_data_revision()
                row = snapshots.get(module=module, query_hash=query_hash)
                compatible_response = bool(
                    row is not None
                    and row["response"] is not None
                    and row["analysis_scheme_version_id"] == configuration.scheme.id
                    and row["taxonomy_sha256"] == configuration.taxonomy.taxonomy_sha256
                )
                if row is not None and compatible_response:
                    fresh = row["status"] == "ready" and int(row["source_revision"]) == revision
                    if fresh:
                        return _stored_snapshot_response(module, row, status="fresh")
                    if _snapshot_failure_backoff_active(
                        row,
                        source_revision=revision,
                        analysis_scheme_version_id=configuration.scheme.id,
                    ):
                        return _stored_snapshot_response(module, row, status="failed")
                    refresh = snapshots.request_refresh(
                        module=module,
                        query_hash=query_hash,
                        query=resolved_query.model_dump(mode="json"),
                        source_revision=revision,
                        analysis_scheme_version_id=configuration.scheme.id,
                    )
                    if refresh is not None:
                        _enqueue_snapshot_job(session, refresh=refresh, query=resolved_query)
                    return _stored_snapshot_response(module, row, status="refreshing")

                # 旧 Scheme/Taxonomy 的 response 不能作为当前筛选的最近成功结果；
                # 它只用于保留可审计历史，当前响应返回同一身份的 preparing 状态。
                if row is not None and _snapshot_failure_backoff_active(
                    row,
                    source_revision=revision,
                    analysis_scheme_version_id=configuration.scheme.id,
                ):
                    return _pending_snapshot_response(
                        module,
                        resolved_query,
                        configuration.scheme.id,
                        configuration.taxonomy.taxonomy_sha256,
                        status="failed",
                    )
                refresh = snapshots.request_refresh(
                    module=module,
                    query_hash=query_hash,
                    query=resolved_query.model_dump(mode="json"),
                    source_revision=revision,
                    analysis_scheme_version_id=configuration.scheme.id,
                )
                if refresh is not None:
                    _enqueue_snapshot_job(session, refresh=refresh, query=resolved_query)
                return _pending_snapshot_response(
                    module,
                    resolved_query,
                    configuration.scheme.id,
                    configuration.taxonomy.taxonomy_sha256,
                    status="preparing",
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


def _stream_query_hash(query: WorkbenchStreamQuery) -> str:
    payload = query.model_dump(mode="json", exclude={"cursor"})
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _resolved_snapshot_query(query: WorkbenchQuery) -> WorkbenchQuery:
    """把动态默认日期冻结为快照身份，避免跨北京时间自然日复用旧结果。"""

    date_from, date_to, _start_at, _end_at = _period(query)
    return query.model_copy(update={"date_from": date_from, "date_to": date_to})


def _snapshot_query_hash(module: WorkbenchSnapshotModule, query: WorkbenchQuery) -> str:
    payload = query.model_dump(mode="json")
    for key, value in payload.items():
        if isinstance(value, list):
            payload[key] = sorted(value)
    encoded = json.dumps(
        # 聚合口径和响应结构升级后重算，禁止将旧作者口径 JSONB 解释成内容口径。
        {"version": "content-mind.v2", "module": module, "query": payload},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _stored_snapshot_response(
    module: WorkbenchSnapshotModule,
    row: RowMapping,
    *,
    status: Literal["fresh", "refreshing", "failed"],
) -> WorkbenchMindResponse | WorkbenchTrendResponse:
    model = WorkbenchMindResponse if module == "mind" else WorkbenchTrendResponse
    response = model.model_validate(row["response"])
    return response.model_copy(
        update={
            "snapshot_status": status,
            "computed_at": cast(datetime | None, row["computed_at"]),
            "source_revision": cast(int | None, row["source_revision"]),
        }
    )


def _pending_snapshot_response(
    module: WorkbenchSnapshotModule,
    query: WorkbenchQuery,
    analysis_scheme_version_id: UUID,
    taxonomy_sha256: str,
    *,
    status: Literal["preparing", "failed"],
) -> WorkbenchMindResponse | WorkbenchTrendResponse:
    """冷筛选只返回真实准备状态，不把尚未聚合的数据伪装成零结果。"""

    date_from, date_to, _start_at, _end_at = _period(query)
    previous_from, previous_to, _previous_start, _previous_end = _previous_period(
        date_from, date_to
    )
    as_of = beijing_now()
    if module == "mind":
        return WorkbenchMindResponse(
            analysis_scheme_version_id=analysis_scheme_version_id,
            taxonomy_sha256=taxonomy_sha256,
            as_of=as_of,
            snapshot_status=status,
            computed_at=None,
            source_revision=None,
            date_from=date_from,
            date_to=date_to,
            previous_date_from=previous_from,
            previous_date_to=previous_to,
            relevant_content_count=0,
            unidentified_content_count=0,
            analyzed_count=0,
            analysis_coverage_rate=0,
            dimensions=(),
        )
    return WorkbenchTrendResponse(
        analysis_scheme_version_id=analysis_scheme_version_id,
        taxonomy_sha256=taxonomy_sha256,
        as_of=as_of,
        snapshot_status=status,
        computed_at=None,
        source_revision=None,
        date_from=date_from,
        date_to=date_to,
        previous_date_from=previous_from,
        previous_date_to=previous_to,
        total_count=0,
        daily_average=0,
        peak_day=None,
        peak_count=0,
        period_change_rate=None,
        positive_rate=None,
        positive_rate_change_pp=None,
        analyzed_count=0,
        analysis_coverage_rate=0,
        daily=(),
        sentiments=(),
        summary="后台正在准备当前筛选的聚合结果。",
    )


def _snapshot_failure_backoff_active(
    row: RowMapping,
    *,
    source_revision: int,
    analysis_scheme_version_id: UUID,
) -> bool:
    """同一失败目标短暂退避，避免页面轮询持续创建昂贵聚合任务。"""

    updated_at = cast(datetime | None, row["updated_at"])
    return bool(
        row["status"] == "failed"
        and int(row["target_revision"]) == source_revision
        and row["target_analysis_scheme_version_id"] == analysis_scheme_version_id
        and updated_at is not None
        and updated_at > beijing_now() - _SNAPSHOT_FAILURE_RETRY_DELAY
    )


def _enqueue_snapshot_job(
    session: Session,
    *,
    refresh: WorkbenchSnapshotRefresh,
    query: WorkbenchQuery,
) -> JobRecord:
    payload = WorkbenchSnapshotJobPayload(
        module=refresh.module,
        query_hash=refresh.query_hash,
        query=query,
        source_revision=refresh.source_revision,
        refresh_generation=refresh.refresh_generation,
        analysis_scheme_version_id=refresh.analysis_scheme_version_id,
    )
    return PostgresJobRepository(session).enqueue(
        job_type=WORKBENCH_SNAPSHOT_JOB_TYPE,
        payload_version=WORKBENCH_SNAPSHOT_JOB_PAYLOAD_VERSION,
        payload=payload.model_dump(mode="json"),
        internal_idempotency_key=(
            f"workbench-snapshot:{refresh.module}:{refresh.query_hash}:"
            f"{refresh.source_revision}:{refresh.analysis_scheme_version_id}:"
            f"{refresh.refresh_generation}"
        ),
        request_id=None,
        priority=WORKBENCH_SNAPSHOT_JOB_PRIORITY,
        max_attempts=WORKBENCH_SNAPSHOT_JOB_MAX_ATTEMPTS,
        timeout_seconds=WORKBENCH_SNAPSHOT_JOB_TIMEOUT_SECONDS,
    )


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


def _json_date(value: object) -> date:
    """把 PostgreSQL JSON 聚合中的日期恢复为业务自然日。"""

    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


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
    return f"{primary}帖子占比较紧邻等长上期{direction} {abs(change_pp):.2f}pp{detail}。"


def _stream_item(row: RowMapping) -> WorkbenchStreamItemResponse:
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


def _layout_response(row: RowMapping | None) -> WorkbenchLayoutResponse:
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
        modules=tuple(
            WorkbenchLayoutModule.model_validate(
                {
                    **item,
                    "column_span": max(6, item["column_span"]),
                    "visible": True if item["module_id"] == "sound-stream" else item["visible"],
                }
            )
            for item in row["layout"]
        ),
        updated_at=cast(datetime, row["updated_at"]),
    )


__all__ = ["PostgresWorkbenchHttpService"]
