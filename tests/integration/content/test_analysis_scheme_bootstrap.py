"""唯一内容打标 Prompt 的 PostgreSQL Scheme bootstrap 回归。"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.analysis_schemes import (
    PostgresAnalysisSchemeRepository,
)
from aima_ugc.bootstrap.worker import create_worker_runtime
from aima_ugc.modules.analysis import CONTENT_LABELING_PROMPT_PATH, PROMPT_VERSION
from aima_ugc.modules.analysis.schemes import prompt_taxonomy_from_version
from aima_ugc.modules.analysis.tables import analysis_content_runs_table
from aima_ugc.platform.config import load_settings
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


def test_git_prompt_change_refreshes_pure_git_scheme_after_existing_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """已有历史 Run 时，纯 Git-managed Scheme 仍追加新版本并自动应用 Git Prompt。"""

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
                assert first.version == 1

                now = beijing_now()
                planner_job_id = uuid4()
                session.execute(
                    insert(jobs_table).values(
                        id=planner_job_id,
                        job_type="test.analysis.plan",
                        payload_version="v1",
                        payload={},
                        result={},
                        status="succeeded",
                        internal_idempotency_key=f"bootstrap-refresh-{uuid4().hex}",
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
                        client_idempotency_key=f"bootstrap-run-{uuid4().hex}",
                        planner_job_id=planner_job_id,
                        run_intent="initial_analysis",
                        scope="query",
                        filter_snapshot={},
                        status="succeeded",
                        target_count=1,
                        shard_count=1,
                        shard_size=1,
                        prompt_version=PROMPT_VERSION,
                        analysis_scheme_version_id=first.id,
                        prompt_text_snapshot=first.compiled_prompt,
                        prompt_sha256=first.prompt_sha256,
                        taxonomy_sha256=first.taxonomy_sha256,
                        model_provider="fake",
                        model="fake",
                        generation_config={},
                        generation_config_hash="a" * 64,
                        runtime_config_snapshot={},
                        created_at=now,
                        finished_at=now,
                    )
                )

            edited_prompt = tmp_path / "content_labeling.md"
            original = CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8")
            edited = original.replace(
                "### 品牌评价\n\n- 口碑与信任\n",
                "### 品牌评价\n\n- Git自动刷新标签\n",
                1,
            )
            assert edited != original
            edited_prompt.write_text(edited, encoding="utf-8")
            monkeypatch.setattr(
                "aima_ugc.adapters.persistence.postgres.analysis_schemes."
                "CONTENT_LABELING_PROMPT_PATH",
                edited_prompt,
            )

            with session.begin():
                repository = PostgresAnalysisSchemeRepository(session)
                refreshed, changed = repository.bootstrap_default(
                    actor_ref="system:git-bootstrap"
                )
                assert changed is True
                assert refreshed.version == 2
                assert refreshed.status == "published"
                assert refreshed.definition.labels["品牌评价"][0] == "Git自动刷新标签"
                assert repository.get_active_version() == refreshed

                historical_version_id = session.scalar(
                    select(analysis_content_runs_table.c.analysis_scheme_version_id).where(
                        analysis_content_runs_table.c.id == run_id
                    )
                )
                assert historical_version_id == first.id
        finally:
            session.close()
    finally:
        runtime.close()
