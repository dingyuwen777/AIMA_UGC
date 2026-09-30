"""唯一内容打标 Prompt 的 PostgreSQL Scheme bootstrap 回归。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.analysis_schemes import (
    PostgresAnalysisSchemeRepository,
)
from aima_ugc.bootstrap.analysis_identity import promote_git_analysis_scheme
from aima_ugc.bootstrap.worker import create_worker_runtime
from aima_ugc.modules.analysis import CONTENT_LABELING_PROMPT_PATH, PROMPT_VERSION
from aima_ugc.modules.analysis.schemes import prompt_taxonomy_from_version
from aima_ugc.modules.analysis.tables import analysis_content_runs_table
from aima_ugc.platform.config import load_settings
from aima_ugc.modules.system.tables import audit_events_table
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.time import beijing_now
from sqlalchemy import insert, select


def test_empty_database_bootstraps_the_unique_current_prompt(tmp_path: Path) -> None:
    """空库只从 content_labeling.md 建立当前 v3.0 active Version。"""

    settings = load_settings().model_copy(
        update={
            "data_dir": tmp_path / "data",
            "log_dir": tmp_path / "logs",
        }
    )
    runtime = create_worker_runtime(settings=settings)
    try:
        with runtime.database.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE analysis_schemes, analysis_scheme_versions, jobs "
                "RESTART IDENTITY CASCADE"
            )

        session = runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresAnalysisSchemeRepository(session)
                version, created = repository.bootstrap_default(actor_ref="system:git-bootstrap")

                assert created is True
                assert version.version == 1
                assert version.status == "published"
                assert version.compiled_prompt == CONTENT_LABELING_PROMPT_PATH.read_text(
                    encoding="utf-8"
                )
                assert (
                    prompt_taxonomy_from_version(version).output_protocol_version
                    == PROMPT_VERSION
                    == "content-labeling.v3.0"
                )
                assert repository.get_active_version() == version

                unchanged, changed = repository.bootstrap_default(actor_ref="system:git-bootstrap")
                assert changed is False
                assert unchanged == version
        finally:
            session.close()
    finally:
        runtime.close()


def _edited_prompt(tmp_path: Path) -> Path:
    """生成只改 Markdown 标签区、未手工同步机器 JSON 的 Git Prompt 副本。"""

    original = CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8")
    edited = original.replace(
        "### 品牌评价\n\n- 口碑与信任\n",
        "### 品牌评价\n\n- Git部署自动发布标签\n",
        1,
    )
    assert edited != original
    path = tmp_path / "content_labeling.md"
    path.write_text(edited, encoding="utf-8")
    return path


def _insert_historical_run(session, version) -> UUID:  # type: ignore[no-untyped-def]
    """插入绑定旧 Scheme Version 的最小历史 Run，验证 promotion 不改写快照。"""

    now = beijing_now()
    job_id = uuid4()
    session.execute(
        insert(jobs_table).values(
            id=job_id,
            job_type="test.analysis.plan",
            payload_version="v1",
            payload={},
            result={},
            status="succeeded",
            internal_idempotency_key=f"git-promotion-job-{uuid4().hex}",
            request_id=None,
            priority=0,
            attempt=1,
            max_attempts=1,
            timeout_seconds=60,
            progress=100,
            available_at=now,
            finished_at=now,
            created_at=now,
            updated_at=now,
        )
    )
    run_id = uuid4()
    session.execute(
        insert(analysis_content_runs_table).values(
            id=run_id,
            client_idempotency_key=f"git-promotion-run-{uuid4().hex}",
            planner_job_id=job_id,
            run_intent="initial_analysis",
            scope="query",
            filter_snapshot={},
            status="succeeded",
            target_count=1,
            shard_count=1,
            shard_size=1,
            prompt_version=PROMPT_VERSION,
            analysis_scheme_version_id=version.id,
            prompt_text_snapshot=version.compiled_prompt,
            prompt_sha256=version.prompt_sha256,
            taxonomy_sha256=version.taxonomy_sha256,
            model_provider="fake",
            model="fake",
            generation_config={},
            generation_config_hash="a" * 64,
            runtime_config_snapshot={},
            created_at=now,
            finished_at=now,
        )
    )
    return run_id


def test_deployment_promotion_applies_git_prompt_after_historical_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """历史 Run 不阻塞部署期 promotion，且旧 Run 继续引用旧 Version。"""

    settings = load_settings().model_copy(
        update={
            "data_dir": tmp_path / "data",
            "log_dir": tmp_path / "logs",
        }
    )
    runtime = create_worker_runtime(settings=settings)
    try:
        with runtime.database.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE analysis_schemes, analysis_scheme_versions, jobs "
                "RESTART IDENTITY CASCADE"
            )

        session = runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresAnalysisSchemeRepository(session)
                first, created = repository.bootstrap_default(actor_ref="system:git-bootstrap")
                assert created is True
                run_id = _insert_historical_run(session, first)

            edited_prompt = _edited_prompt(tmp_path)
            monkeypatch.setattr(
                "aima_ugc.adapters.persistence.postgres.analysis_schemes."
                "CONTENT_LABELING_PROMPT_PATH",
                edited_prompt,
            )

            with session.begin():
                promotion = promote_git_analysis_scheme(session)
                promoted = promotion.scheme
                assert promotion.action == "promoted"
                assert promoted.version == 2
                assert promoted.definition.labels["品牌评价"][0] == "Git部署自动发布标签"
                repository = PostgresAnalysisSchemeRepository(session)
                assert repository.get_active_version() == promoted

                historical_version_id = session.scalar(
                    select(analysis_content_runs_table.c.analysis_scheme_version_id).where(
                        analysis_content_runs_table.c.id == run_id
                    )
                )
                assert historical_version_id == first.id

                audit = (
                    session.execute(
                        select(
                            audit_events_table.c.event_type,
                            audit_events_table.c.safe_detail,
                        ).where(
                            audit_events_table.c.object_id == str(promoted.id),
                            audit_events_table.c.event_type == "analysis_scheme_git_promoted",
                        )
                    )
                    .mappings()
                    .one()
                )
                assert audit["safe_detail"]["action"] == "promoted"
                assert audit["safe_detail"]["version"] == 2
                assert "prompt_text" not in audit["safe_detail"]

                second = promote_git_analysis_scheme(session)
                assert second.action == "unchanged"
                assert second.scheme == promoted
        finally:
            session.close()
    finally:
        runtime.close()


def test_deployment_promotion_rejects_manual_scheme_lineage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """人工 Version 存在时，部署不得用 Git Prompt 静默覆盖管理员配置。"""

    settings = load_settings().model_copy(
        update={
            "data_dir": tmp_path / "data",
            "log_dir": tmp_path / "logs",
        }
    )
    runtime = create_worker_runtime(settings=settings)
    try:
        with runtime.database.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE analysis_schemes, analysis_scheme_versions, jobs "
                "RESTART IDENTITY CASCADE"
            )

        session = runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresAnalysisSchemeRepository(session)
                first, created = repository.bootstrap_default(actor_ref="system:git-bootstrap")
                assert created is True
                manual = repository.create_draft(
                    name="默认内容舆情分析方案",
                    description="人工配置",
                    definition=first.definition,
                    actor_ref="user:test-admin",
                )
                published = repository.activate_version(
                    manual.id,
                    expected_version=manual.version,
                )
                assert published.created_by == "user:test-admin"

            with pytest.raises(RuntimeError, match="人工 Version"):
                with session.begin():
                    PostgresAnalysisSchemeRepository(session).promote_git_prompt()

            edited_prompt = _edited_prompt(tmp_path)
            monkeypatch.setattr(
                "aima_ugc.adapters.persistence.postgres.analysis_schemes."
                "CONTENT_LABELING_PROMPT_PATH",
                edited_prompt,
            )

            with pytest.raises(RuntimeError, match="人工 Version"):
                with session.begin():
                    PostgresAnalysisSchemeRepository(session).promote_git_prompt()

            with session.begin():
                current = PostgresAnalysisSchemeRepository(session).get_active_version()
                assert current is not None
                assert current.id == published.id
        finally:
            session.close()
    finally:
        runtime.close()


def test_deployment_promotion_serializes_concurrent_git_refresh(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """并发 configure 只允许一个 promotion，第二个事务观察新 active 后幂等返回。"""

    settings = load_settings().model_copy(
        update={
            "data_dir": tmp_path / "data",
            "log_dir": tmp_path / "logs",
        }
    )
    runtime = create_worker_runtime(settings=settings)
    try:
        with runtime.database.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE analysis_schemes, analysis_scheme_versions, jobs "
                "RESTART IDENTITY CASCADE"
            )

        seed_session = runtime.database.new_session()
        try:
            with seed_session.begin():
                first, created = PostgresAnalysisSchemeRepository(
                    seed_session
                ).bootstrap_default(actor_ref="system:git-bootstrap")
                assert created is True
                assert first.version == 1
        finally:
            seed_session.close()

        edited_prompt = _edited_prompt(tmp_path)
        monkeypatch.setattr(
            "aima_ugc.adapters.persistence.postgres.analysis_schemes."
            "CONTENT_LABELING_PROMPT_PATH",
            edited_prompt,
        )
        barrier = Barrier(2)

        def promote_once() -> tuple[str, UUID, int]:
            """在独立事务中模拟一个并发 configure promotion。"""

            session = runtime.database.new_session()
            try:
                barrier.wait(timeout=10)
                with session.begin():
                    version, action = PostgresAnalysisSchemeRepository(
                        session
                    ).promote_git_prompt()
                    return action, version.id, version.version
            finally:
                session.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = tuple(executor.map(lambda _index: promote_once(), range(2)))

        assert sorted(action for action, _id, _version in results) == [
            "promoted",
            "unchanged",
        ]
        assert {version for _action, _id, version in results} == {2}
        assert len({version_id for _action, version_id, _version in results}) == 1
    finally:
        runtime.close()
