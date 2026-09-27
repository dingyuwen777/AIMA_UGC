"""工作台 active Scheme 过滤与布局 CAS 的真实 PostgreSQL 回归。"""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.workbench import (
    PostgresWorkbenchRepository,
    WorkbenchLayoutRevisionConflict,
)
from aima_ugc.bootstrap.workbench_http import _period
from aima_ugc.contracts.workbench import WorkbenchLayoutModule, WorkbenchQuery
from aima_ugc.modules.analysis.scheme_tables import (
    analysis_scheme_versions_table,
    analysis_schemes_table,
)
from aima_ugc.modules.analysis.tables import (
    analysis_content_label_pairs_table,
    analysis_content_results_table,
    analysis_content_runs_table,
)
from aima_ugc.modules.content.read_model_tables import voice_plaza_content_projection_table
from aima_ugc.modules.content.tables import accounts_table, contents_table
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs.tables import jobs_table


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
        summary = repository.period_summary(
            active_scheme_version_id=active_version_id,
            query=query,
            start_at=start_at,
            end_at=end_at,
        )
        stream = repository.stream_rows(
            active_scheme_version_id=active_version_id,
            query=query,
            start_at=start_at,
            end_at=end_at,
        )
        mind = repository.mind_counts(
            active_scheme_version_id=active_version_id,
            query=query,
            start_at=start_at,
            end_at=end_at,
        )

        assert int(summary["analyzed_count"]) == 1
        assert int(summary["positive_count"]) == 1
        assert stream[0]["effective_sentiment"] == "正面"
        assert stream[0]["effective_labels"] == [
            {"primary_label": "外观设计", "secondary_label": "颜色与配色"}
        ]
        assert [(row["primary_label"], int(row["user_count"])) for row in mind] == [("外观设计", 1)]

        # 同一筛选源必须同时改变声音流、声量/情感聚合与心智聚合。
        excluded_queries = (
            WorkbenchQuery(platforms=("douyin",)),
            WorkbenchQuery(voice_types=("品牌官方发声",)),
            WorkbenchQuery(sentiments=("负面",)),
            WorkbenchQuery(primary_labels=("售后服务",)),
            WorkbenchQuery(secondary_labels=("维修体验",)),
            WorkbenchQuery(brand_ids=(uuid4(),)),
            WorkbenchQuery(vehicle_model_ids=(uuid4(),)),
        )
        for excluded_query in excluded_queries:
            assert repository.stream_rows(
                active_scheme_version_id=active_version_id,
                query=excluded_query,
                start_at=start_at,
                end_at=end_at,
            ) == ()
            assert int(repository.period_summary(
                active_scheme_version_id=active_version_id,
                query=excluded_query,
                start_at=start_at,
                end_at=end_at,
            )["total_count"]) == 0
            assert repository.mind_counts(
                active_scheme_version_id=active_version_id,
                query=excluded_query,
                start_at=start_at,
                end_at=end_at,
            ) == ()

        earlier = WorkbenchQuery(date_from=date(2026, 9, 20), date_to=date(2026, 9, 21))
        _, _, earlier_start, earlier_end = _period(earlier)
        assert repository.stream_rows(
            active_scheme_version_id=active_version_id,
            query=earlier,
            start_at=earlier_start,
            end_at=earlier_end,
        ) == ()
        assert int(repository.period_summary(
            active_scheme_version_id=active_version_id,
            query=earlier,
            start_at=earlier_start,
            end_at=earlier_end,
        )["total_count"]) == 0
        assert repository.mind_counts(
            active_scheme_version_id=active_version_id,
            query=earlier,
            start_at=earlier_start,
            end_at=earlier_end,
        ) == ()
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
