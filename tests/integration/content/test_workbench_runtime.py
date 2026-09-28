"""工作台 active Scheme 过滤与布局 CAS 的真实 PostgreSQL 回归。"""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.workbench import (
    PostgresWorkbenchRepository,
    WorkbenchLayoutRevisionConflict,
)
from aima_ugc.adapters.persistence.postgres.workbench_snapshots import (
    PostgresWorkbenchSnapshotRepository,
)
from aima_ugc.bootstrap.workbench_http import _period
from aima_ugc.contracts.workbench import WorkbenchLayoutModule, WorkbenchQuery
from aima_ugc.modules.analysis.manual_override_tables import (
    analysis_content_manual_overrides_table,
)
from aima_ugc.modules.analysis.relevance_review_tables import (
    analysis_content_relevance_reviews_table,
)
from aima_ugc.modules.analysis.scheme_tables import (
    analysis_scheme_versions_table,
    analysis_schemes_table,
)
from aima_ugc.modules.analysis.tables import (
    analysis_content_label_pairs_table,
    analysis_content_results_table,
    analysis_content_runs_table,
)
from aima_ugc.modules.content.content_cursor import ContentCursorPosition
from aima_ugc.modules.content.read_model_tables import voice_plaza_content_projection_table
from aima_ugc.modules.content.tables import accounts_table, contents_table
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs.tables import jobs_table
from sqlalchemy import event


def test_workbench_mind_and_trend_each_execute_one_aggregate_statement() -> None:
    """慢模块必须各用一次数据库执行复用范围事实，不能重建 5/4 次完整关联。"""

    runtime = DatabaseRuntime(load_settings())
    session = runtime.new_session()
    statements: list[str] = []

    def capture_statement(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        """只记录本测试主动执行的聚合 SQL。"""

        statements.append(statement)

    event.listen(runtime.engine, "before_cursor_execute", capture_statement)
    try:
        repository = PostgresWorkbenchRepository(session)
        current_start = datetime(2026, 8, 30, tzinfo=UTC)
        current_end = datetime(2026, 9, 29, tzinfo=UTC)
        previous_start = datetime(2026, 7, 31, tzinfo=UTC)
        query = WorkbenchQuery()
        trend = repository.trend_snapshot(
            active_scheme_version_id=uuid4(),
            query=query,
            previous_start_at=previous_start,
            current_start_at=current_start,
            end_at=current_end,
        )
        mind = repository.mind_snapshot(
            active_scheme_version_id=uuid4(),
            query=query,
            previous_start_at=previous_start,
            current_start_at=current_start,
            end_at=current_end,
        )

        assert trend["current_summary"]["total_count"] == 0
        assert mind["current_summary"]["identified_user_count"] == 0
        aggregate_statements = [statement for statement in statements if "workbench:" in statement]
        assert len(aggregate_statements) == 2
        assert "workbench:trend-snapshot" in aggregate_statements[0]
        assert "workbench:mind-snapshot" in aggregate_statements[1]
    finally:
        event.remove(runtime.engine, "before_cursor_execute", capture_statement)
        session.close()
        runtime.dispose()


def _job_values(job_id: UUID, *, now: datetime, suffix: str) -> dict[str, object]:
    """生成满足正式 Job Runtime 数据库约束的已完成测试 Job。"""

    return {
        "id": job_id,
        "job_type": "workbench-integration-test",
        "payload_version": "1",
        "payload": {},
        "result": {},
        "status": "succeeded",
        "internal_idempotency_key": f"workbench-{suffix}-{job_id}",
        "priority": 0,
        "attempt": 1,
        "max_attempts": 1,
        "timeout_seconds": 60,
        "progress": 100,
        "available_at": now,
        "started_at": now,
        "finished_at": now,
        "created_at": now,
        "updated_at": now,
    }


def _run_values(
    run_id: UUID,
    *,
    job_id: UUID,
    scheme_version_id: UUID,
    taxonomy_hash: str,
    now: datetime,
    suffix: str,
) -> dict[str, object]:
    """生成一个冻结指定 Analysis Scheme Version 的已完成 Run。"""

    return {
        "id": run_id,
        "client_idempotency_key": f"workbench-run-{suffix}-{run_id}",
        "planner_job_id": job_id,
        "run_intent": "initial_analysis",
        "scope": "selected",
        "filter_snapshot": {},
        "status": "succeeded",
        "target_count": 1,
        "shard_count": 1,
        "shard_size": 1,
        "prompt_version": "content-labeling.v4",
        "analysis_scheme_version_id": scheme_version_id,
        "prompt_text_snapshot": "test prompt",
        "prompt_sha256": "1" * 64,
        "taxonomy_sha256": taxonomy_hash,
        "model_provider": "fake",
        "model": "fake-model",
        "generation_config": {},
        "generation_config_hash": "2" * 64,
        "runtime_config_snapshot": {},
        "created_at": now,
        "started_at": now,
        "finished_at": now,
    }


def _result_values(
    result_id: UUID,
    *,
    content_id: UUID,
    run_id: UUID,
    job_id: UUID,
    sentiment: str,
    taxonomy_hash: str,
    now: datetime,
) -> dict[str, object]:
    """生成一个 relevant Analysis Result，供 active/old Scheme 对照。"""

    return {
        "id": result_id,
        "content_id": content_id,
        "content_version": 1,
        "analysis_run_id": run_id,
        "job_id": job_id,
        "schema_version": "content-labeling.v4",
        "relevance": "relevant",
        "voice_type": "真实用户发声",
        "sentiment": sentiment,
        "prompt_version": "content-labeling.v4",
        "prompt_sha256": "1" * 64,
        "taxonomy_sha256": taxonomy_hash,
        "model_provider": "fake",
        "model": "fake-model",
        "input_hash": "3" * 64,
        "generation_config_hash": "2" * 64,
        "analyzed_at": now,
        "created_at": now,
    }


def test_workbench_uses_active_scheme_result_instead_of_projection_latest_result() -> None:
    """Projection 即使指向更新的旧 Scheme Result，工作台也只能统计指定 active Version。"""

    runtime = DatabaseRuntime(load_settings())
    session = runtime.new_session()
    transaction = session.begin()
    now = datetime(2026, 9, 27, 0, 0, tzinfo=UTC)
    try:
        scheme_id = uuid4()
        active_version_id = uuid4()
        old_version_id = uuid4()
        active_job_id = uuid4()
        old_job_id = uuid4()
        active_run_id = uuid4()
        old_run_id = uuid4()
        active_result_id = uuid4()
        old_result_id = uuid4()
        content_id = uuid4()
        account_id = uuid4()

        session.execute(
            analysis_schemes_table.insert().values(
                id=scheme_id,
                name=f"workbench-test-{scheme_id}",
                is_active=False,
                created_at=now,
                updated_at=now,
            )
        )
        for version_id, version, taxonomy_hash in (
            (active_version_id, 1, "a" * 64),
            (old_version_id, 2, "b" * 64),
        ):
            session.execute(
                analysis_scheme_versions_table.insert().values(
                    id=version_id,
                    scheme_id=scheme_id,
                    version=version,
                    status="retired",
                    description="test",
                    definition={"sentiments": ["正面", "负面", "无法判断"]},
                    compiled_prompt="test prompt",
                    prompt_sha256="1" * 64,
                    taxonomy_sha256=taxonomy_hash,
                    created_by="integration-test",
                    created_at=now,
                )
            )

        session.execute(
            jobs_table.insert(),
            [
                _job_values(active_job_id, now=now, suffix="active"),
                _job_values(old_job_id, now=now, suffix="old"),
            ],
        )
        session.execute(
            accounts_table.insert().values(
                id=account_id,
                platform="xiaohongshu",
                external_account_id=f"workbench-user-{account_id}",
                display_name="用户甲",
                first_seen_at=now,
                last_seen_at=now,
                updated_at=now,
            )
        )
        session.execute(
            contents_table.insert().values(
                id=content_id,
                platform="xiaohongshu",
                external_content_id=f"workbench-content-{content_id}",
                content_type="note",
                title="爱玛外观体验",
                text="配色很好看",
                author_account_id=account_id,
                published_at=now,
                first_seen_at=now,
                last_seen_at=now,
                current_version=1,
                updated_at=now,
            )
        )
        session.execute(
            analysis_content_runs_table.insert(),
            [
                _run_values(
                    active_run_id,
                    job_id=active_job_id,
                    scheme_version_id=active_version_id,
                    taxonomy_hash="a" * 64,
                    now=now,
                    suffix="active",
                ),
                _run_values(
                    old_run_id,
                    job_id=old_job_id,
                    scheme_version_id=old_version_id,
                    taxonomy_hash="b" * 64,
                    now=now + timedelta(seconds=1),
                    suffix="old",
                ),
            ],
        )
        session.execute(
            analysis_content_results_table.insert(),
            [
                _result_values(
                    active_result_id,
                    content_id=content_id,
                    run_id=active_run_id,
                    job_id=active_job_id,
                    sentiment="正面",
                    taxonomy_hash="a" * 64,
                    now=now,
                ),
                _result_values(
                    old_result_id,
                    content_id=content_id,
                    run_id=old_run_id,
                    job_id=old_job_id,
                    sentiment="负面",
                    taxonomy_hash="b" * 64,
                    now=now + timedelta(seconds=1),
                ),
            ],
        )
        session.execute(
            analysis_content_label_pairs_table.insert(),
            [
                {
                    "analysis_result_id": active_result_id,
                    "ordinal": 0,
                    "primary_label": "外观设计",
                    "secondary_label": "颜色与配色",
                },
                {
                    "analysis_result_id": old_result_id,
                    "ordinal": 0,
                    "primary_label": "售后服务",
                    "secondary_label": "维修体验",
                },
            ],
        )
        session.execute(
            voice_plaza_content_projection_table.update()
            .where(voice_plaza_content_projection_table.c.content_id == content_id)
            .values(
                content_version=1,
                platform="xiaohongshu",
                content_type="note",
                published_at=now,
                sort_at=now,
                is_visible=True,
                analysis_result_id=old_result_id,
                analysis_status="completed",
                effective_relevance="relevant",
                relevance_source="ai",
                effective_voice_type="真实用户发声",
                effective_sentiment="负面",
                labels=[{"primary_label": "售后服务", "secondary_label": "维修体验"}],
                brand_ids=[],
                vehicle_model_ids=[],
                competition_scope="none_detected",
                updated_at=now,
            )
        )

        repository = PostgresWorkbenchRepository(session)
        query = WorkbenchQuery()
        start_at = now - timedelta(days=1)
        end_at = now + timedelta(days=1)
        trend_snapshot = repository.trend_snapshot(
            active_scheme_version_id=active_version_id,
            query=query,
            previous_start_at=start_at - timedelta(days=2),
            current_start_at=start_at,
            end_at=end_at,
        )
        stream = repository.stream_rows(
            active_scheme_version_id=active_version_id,
            query=query,
            start_at=start_at,
            end_at=end_at,
        )
        mind_snapshot = repository.mind_snapshot(
            active_scheme_version_id=active_version_id,
            query=query,
            previous_start_at=start_at - timedelta(days=2),
            current_start_at=start_at,
            end_at=end_at,
        )

        summary = trend_snapshot["current_summary"]
        mind = mind_snapshot["current_primary"]
        assert int(summary["analyzed_count"]) == 1
        assert int(summary["positive_count"]) == 1
        assert stream[0]["effective_sentiment"] == "正面"
        assert stream[0]["effective_labels"] == [
            {"primary_label": "外观设计", "secondary_label": "颜色与配色"}
        ]
        assert [(row["primary_label"], int(row["user_count"])) for row in mind] == [("外观设计", 1)]

        snapshots = PostgresWorkbenchSnapshotRepository(session)
        revision_before = snapshots.current_data_revision()
        session.execute(
            voice_plaza_content_projection_table.update()
            .where(voice_plaza_content_projection_table.c.content_id == content_id)
            .values(updated_at=now + timedelta(seconds=1))
        )
        revision_after = snapshots.current_data_revision()
        assert revision_after > revision_before

        snapshot_hash = "c" * 64
        refresh = snapshots.request_refresh(
            module="trend",
            query_hash=snapshot_hash,
            query=query.model_dump(mode="json"),
            source_revision=revision_after,
            analysis_scheme_version_id=active_version_id,
        )
        assert refresh is not None
        assert (
            snapshots.request_refresh(
                module="trend",
                query_hash=snapshot_hash,
                query=query.model_dump(mode="json"),
                source_revision=revision_after,
                analysis_scheme_version_id=active_version_id,
            )
            is None
        )
        assert (
            snapshots.request_refresh(
                module="trend",
                query_hash=snapshot_hash,
                query=query.model_dump(mode="json"),
                source_revision=revision_after + 1,
                analysis_scheme_version_id=active_version_id,
            )
            is None
        )
        assert snapshots.record_success(
            refresh=refresh,
            taxonomy_sha256="a" * 64,
            response={"result": "latest-success"},
            computed_at=now,
        )
        retry_refresh = snapshots.request_refresh(
            module="trend",
            query_hash=snapshot_hash,
            query=query.model_dump(mode="json"),
            source_revision=revision_after + 1,
            analysis_scheme_version_id=active_version_id,
        )
        assert retry_refresh is not None
        assert snapshots.record_failure(refresh=retry_refresh, error_code="temporary_failure")
        failed_snapshot = snapshots.get(module="trend", query_hash=snapshot_hash)
        assert failed_snapshot is not None
        assert failed_snapshot["status"] == "failed"
        assert failed_snapshot["response"] == {"result": "latest-success"}

        # Projection 仍指向旧 Scheme 时，回退路径必须应用当前 Content Version 的人工事实。
        session.execute(
            analysis_content_manual_overrides_table.insert().values(
                content_id=content_id,
                content_version=1,
                voice_type="品牌官方发声",
                sentiment="负面",
                labels=[{"primary_label": "售后服务", "secondary_label": "维修体验"}],
                voice_type_locked=True,
                sentiment_locked=True,
                labels_locked=True,
                actor_ref="workbench-integration-test",
                updated_at=now + timedelta(seconds=2),
            )
        )
        session.execute(
            analysis_content_relevance_reviews_table.insert().values(
                id=uuid4(),
                content_id=content_id,
                content_version=1,
                analysis_result_id=active_result_id,
                review_no=1,
                decision="irrelevant",
                request_id=f"workbench-review-{content_id}-1",
                reviewed_at=now + timedelta(seconds=2),
            )
        )
        session.execute(
            voice_plaza_content_projection_table.update()
            .where(voice_plaza_content_projection_table.c.content_id == content_id)
            .values(
                is_visible=True,
                analysis_result_id=old_result_id,
                analysis_status="completed",
                updated_at=now + timedelta(seconds=2),
            )
        )
        irrelevant_snapshot = repository.trend_snapshot(
            active_scheme_version_id=active_version_id,
            query=query,
            previous_start_at=start_at - timedelta(days=2),
            current_start_at=start_at,
            end_at=end_at,
        )
        assert int(irrelevant_snapshot["current_summary"]["total_count"]) == 0
        session.execute(
            analysis_content_relevance_reviews_table.insert().values(
                id=uuid4(),
                content_id=content_id,
                content_version=1,
                analysis_result_id=active_result_id,
                review_no=2,
                decision="relevant",
                request_id=f"workbench-review-{content_id}-2",
                reviewed_at=now + timedelta(seconds=3),
            )
        )
        session.execute(
            voice_plaza_content_projection_table.update()
            .where(voice_plaza_content_projection_table.c.content_id == content_id)
            .values(
                is_visible=True,
                analysis_result_id=old_result_id,
                analysis_status="completed",
                updated_at=now + timedelta(seconds=3),
            )
        )
        manual_query = WorkbenchQuery(
            voice_types=("品牌官方发声",),
            sentiments=("负面",),
            primary_labels=("售后服务",),
            secondary_labels=("维修体验",),
        )
        manual_stream = repository.stream_rows(
            active_scheme_version_id=active_version_id,
            query=manual_query,
            start_at=start_at,
            end_at=end_at,
        )
        manual_mind = repository.mind_snapshot(
            active_scheme_version_id=active_version_id,
            query=manual_query,
            previous_start_at=start_at - timedelta(days=2),
            current_start_at=start_at,
            end_at=end_at,
        )
        assert manual_stream[0]["effective_voice_type"] == "品牌官方发声"
        assert manual_stream[0]["effective_sentiment"] == "负面"
        assert manual_stream[0]["effective_labels"] == [
            {"primary_label": "售后服务", "secondary_label": "维修体验"}
        ]
        assert [row["primary_label"] for row in manual_mind["current_primary"]] == ["售后服务"]

        # Projection 已同步到 active Scheme 后，应走派生读模型快路径且保持相同业务结果。
        session.execute(
            voice_plaza_content_projection_table.update()
            .where(voice_plaza_content_projection_table.c.content_id == content_id)
            .values(
                analysis_result_id=active_result_id,
                effective_relevance="relevant",
                relevance_source="manual_review",
                effective_voice_type="品牌官方发声",
                effective_sentiment="负面",
                labels=[{"primary_label": "售后服务", "secondary_label": "维修体验"}],
                updated_at=now + timedelta(seconds=4),
            )
        )
        fast_trend_snapshot = repository.trend_snapshot(
            active_scheme_version_id=active_version_id,
            query=query,
            previous_start_at=start_at - timedelta(days=2),
            current_start_at=start_at,
            end_at=end_at,
        )
        fast_mind_snapshot = repository.mind_snapshot(
            active_scheme_version_id=active_version_id,
            query=query,
            previous_start_at=start_at - timedelta(days=2),
            current_start_at=start_at,
            end_at=end_at,
        )
        assert int(fast_trend_snapshot["current_summary"]["relevant_count"]) == 1
        assert int(fast_trend_snapshot["current_summary"]["positive_count"]) == 0
        assert [row["sentiment"] for row in fast_trend_snapshot["sentiment_counts"]] == ["负面"]
        assert [
            (row["primary_label"], int(row["user_count"]))
            for row in fast_mind_snapshot["current_primary"]
        ] == [("售后服务", 1)]

        # 同一筛选源必须同时改变声音流、声量/情感聚合与心智聚合。
        excluded_queries = (
            WorkbenchQuery(platforms=("douyin",)),
            WorkbenchQuery(voice_types=("真实用户发声",)),
            WorkbenchQuery(sentiments=("正面",)),
            WorkbenchQuery(primary_labels=("外观设计",)),
            WorkbenchQuery(secondary_labels=("颜色与配色",)),
            WorkbenchQuery(brand_ids=(uuid4(),)),
            WorkbenchQuery(vehicle_model_ids=(uuid4(),)),
        )
        for excluded_query in excluded_queries:
            assert (
                repository.stream_rows(
                    active_scheme_version_id=active_version_id,
                    query=excluded_query,
                    start_at=start_at,
                    end_at=end_at,
                )
                == ()
            )
            assert (
                int(
                    repository.trend_snapshot(
                        active_scheme_version_id=active_version_id,
                        query=excluded_query,
                        previous_start_at=start_at - timedelta(days=2),
                        current_start_at=start_at,
                        end_at=end_at,
                    )["current_summary"]["total_count"]
                )
                == 0
            )
            assert (
                repository.mind_snapshot(
                    active_scheme_version_id=active_version_id,
                    query=excluded_query,
                    previous_start_at=start_at - timedelta(days=2),
                    current_start_at=start_at,
                    end_at=end_at,
                )["current_primary"]
                == []
            )

        earlier = WorkbenchQuery(date_from=date(2026, 9, 20), date_to=date(2026, 9, 21))
        _, _, earlier_start, earlier_end = _period(earlier)
        assert (
            repository.stream_rows(
                active_scheme_version_id=active_version_id,
                query=earlier,
                start_at=earlier_start,
                end_at=earlier_end,
            )
            == ()
        )
        assert (
            int(
                repository.trend_snapshot(
                    active_scheme_version_id=active_version_id,
                    query=earlier,
                    previous_start_at=earlier_start - timedelta(days=2),
                    current_start_at=earlier_start,
                    end_at=earlier_end,
                )["current_summary"]["total_count"]
            )
            == 0
        )
        assert (
            repository.mind_snapshot(
                active_scheme_version_id=active_version_id,
                query=earlier,
                previous_start_at=earlier_start - timedelta(days=2),
                current_start_at=earlier_start,
                end_at=earlier_end,
            )["current_primary"]
            == []
        )

        # 稳定 keyset Cursor 必须跨页覆盖全部匹配记录，不能重复最新一页。该样本放在
        # 单内容过滤语义断言之后，避免额外内容污染 relevance 与筛选回归。
        extra_content_ids = (uuid4(), uuid4())
        extra_result_ids = (uuid4(), uuid4())
        for index, (extra_content_id, extra_result_id) in enumerate(
            zip(extra_content_ids, extra_result_ids, strict=True),
            start=1,
        ):
            published_at = now - timedelta(minutes=index)
            session.execute(
                contents_table.insert().values(
                    id=extra_content_id,
                    platform="xiaohongshu",
                    external_content_id=f"workbench-cursor-{extra_content_id}",
                    content_type="note",
                    title=f"Cursor {index}",
                    text=f"分页声音 {index}",
                    author_account_id=account_id,
                    published_at=published_at,
                    first_seen_at=published_at,
                    last_seen_at=published_at,
                    current_version=1,
                    updated_at=published_at,
                )
            )
            result_values = _result_values(
                extra_result_id,
                content_id=extra_content_id,
                run_id=active_run_id,
                job_id=active_job_id,
                sentiment="正面",
                taxonomy_hash="a" * 64,
                now=published_at,
            )
            result_values["input_hash"] = str(index + 4) * 64
            session.execute(analysis_content_results_table.insert().values(**result_values))
            session.execute(
                analysis_content_label_pairs_table.insert().values(
                    analysis_result_id=extra_result_id,
                    ordinal=0,
                    primary_label="外观设计",
                    secondary_label="颜色与配色",
                )
            )
            session.execute(
                voice_plaza_content_projection_table.update()
                .where(voice_plaza_content_projection_table.c.content_id == extra_content_id)
                .values(
                    content_version=1,
                    platform="xiaohongshu",
                    content_type="note",
                    published_at=published_at,
                    sort_at=published_at,
                    is_visible=True,
                    analysis_result_id=extra_result_id,
                    analysis_status="completed",
                    effective_relevance="relevant",
                    relevance_source="ai",
                    effective_voice_type="真实用户发声",
                    effective_sentiment="正面",
                    labels=[{"primary_label": "外观设计", "secondary_label": "颜色与配色"}],
                    brand_ids=[],
                    vehicle_model_ids=[],
                    competition_scope="none_detected",
                    updated_at=published_at,
                )
            )

        first_page = repository.stream_rows(
            active_scheme_version_id=active_version_id,
            query=query,
            start_at=start_at,
            end_at=end_at,
            limit=2,
        )
        second_page = repository.stream_rows(
            active_scheme_version_id=active_version_id,
            query=query,
            start_at=start_at,
            end_at=end_at,
            limit=2,
            position=ContentCursorPosition(
                sort_at=first_page[-1]["published_at"],
                content_id=first_page[-1]["content_id"],
            ),
        )
        paged_ids = [row["content_id"] for row in (*first_page, *second_page)]
        assert paged_ids == [content_id, *extra_content_ids]
        assert len(paged_ids) == len(set(paged_ids))
    finally:
        transaction.rollback()
        session.close()
        runtime.dispose()


def test_workbench_layout_create_and_revision_conflict_are_persistent() -> None:
    """布局第一次保存 revision=1；旧 revision 再写必须冲突。"""

    runtime = DatabaseRuntime(load_settings())
    session = runtime.new_session()
    transaction = session.begin()
    # 开发身份尚无 identity_principals 行，首次布局保存仍须可用。
    principal_id = f"local-administrator-{uuid4().hex}"
    now = datetime(2026, 9, 27, 0, 0, tzinfo=UTC)
    modules = (
        WorkbenchLayoutModule(module_id="sound-stream", order=0, column_span=6, row_units=48),
        WorkbenchLayoutModule(module_id="brand-mind", order=1, column_span=6, row_units=48),
        WorkbenchLayoutModule(module_id="ugc-trend", order=2, column_span=6, row_units=48),
    )
    try:
        repository = PostgresWorkbenchRepository(session)
        first = repository.save_layout(
            principal_id=principal_id,
            expected_revision=0,
            modules=modules,
            now=now,
        )
        assert int(first["revision"]) == 1

        with pytest.raises(WorkbenchLayoutRevisionConflict):
            repository.save_layout(
                principal_id=principal_id,
                expected_revision=0,
                modules=modules,
                now=now,
            )
    finally:
        transaction.rollback()
        session.close()
        runtime.dispose()
