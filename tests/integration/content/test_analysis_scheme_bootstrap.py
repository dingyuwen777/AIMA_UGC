"""唯一内容打标 Prompt 的 PostgreSQL Scheme bootstrap 回归。"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, insert, select

import aima_ugc.adapters.persistence.postgres.analysis_schemes as analysis_schemes_module
from aima_ugc.adapters.persistence.postgres.analysis_schemes import (
    PostgresAnalysisSchemeRepository,
)
from aima_ugc.bootstrap.worker import create_worker_runtime
from aima_ugc.modules.analysis import CONTENT_LABELING_PROMPT_PATH, PROMPT_VERSION
from aima_ugc.modules.analysis.scheme_tables import analysis_scheme_versions_table
from aima_ugc.modules.analysis.schemes import prompt_taxonomy_from_version
from aima_ugc.modules.analysis.tables import analysis_content_runs_table
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.time import beijing_now


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


def _changed_git_prompt(tmp_path: Path, *, label: str = "Git自动刷新测试") -> Path:
    """只修改人类可读标签区，模拟后续直接提交 Git Markdown。"""

    prompt = CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8")
    changed = prompt.replace(
        "### 品牌评价\n\n- 口碑与信任\n",
        f"### 品牌评价\n\n- {label}\n",
        1,
    )
    assert changed != prompt
    path = tmp_path / "content_labeling_changed.md"
    path.write_text(changed, encoding="utf-8")
    return path


def _insert_historical_run(session, *, version) -> None:  # type: ignore[no-untyped-def]
    """写入最小历史 Run，证明旧 Version 引用不会阻止 Git lineage 前进。"""

    now = beijing_now()
    job_id = uuid4()
    session.execute(
        insert(jobs_table).values(
            id=job_id,
            job_type="test.analysis-plan",
            payload_version="v1",
            payload={},
            result={},
            status="succeeded",
            internal_idempotency_key=f"git-prompt-refresh-{job_id}",
            request_id=None,
            priority=0,
            attempt=1,
            max_attempts=1,
            timeout_seconds=60,
            progress=100,
            available_at=now,
            started_at=now,
            finished_at=now,
            created_at=now,
            updated_at=now,
        )
    )
    session.execute(
        insert(analysis_content_runs_table).values(
            id=uuid4(),
            client_idempotency_key=f"git-prompt-refresh-run-{job_id}",
            planner_job_id=job_id,
            run_intent="manual_reanalysis",
            scope="selected",
            filter_snapshot={},
            status="succeeded",
            target_count=1,
            shard_count=1,
            shard_size=20,
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
            started_at=now,
            finished_at=now,
        )
    )


def test_git_managed_scheme_refreshes_after_historical_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """已有历史 Run 时，纯 Git-managed 默认 Scheme 仍自动追加新 active Version。"""

    settings = load_settings().model_copy(
        update={"data_dir": tmp_path / "data", "log_dir": tmp_path / "logs"}
    )
    runtime = create_worker_runtime(settings=settings)
    try:
        with runtime.database.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE analysis_schemes, analysis_scheme_versions, jobs "
                "RESTART IDENTITY CASCADE"
            )

        with runtime.database.new_session() as session, session.begin():
            repository = PostgresAnalysisSchemeRepository(session)
            original, created = repository.bootstrap_default(actor_ref="system:git-bootstrap")
            assert created is True
            _insert_historical_run(session, version=original)

        monkeypatch.setattr(
            analysis_schemes_module,
            "CONTENT_LABELING_PROMPT_PATH",
            _changed_git_prompt(tmp_path),
        )

        with runtime.database.new_session() as session, session.begin():
            repository = PostgresAnalysisSchemeRepository(session)
            refreshed, changed = repository.bootstrap_default(actor_ref="system:git-bootstrap")

            assert changed is True
            assert refreshed.version == 2
            assert refreshed.id != original.id
            assert refreshed.description == "由 Git Prompt 自动刷新生产 Scheme"
            assert refreshed.definition.labels["品牌评价"][0] == "Git自动刷新测试"
            assert repository.get_active_version() == refreshed

            retired = repository.get_version(original.id)
            assert retired is not None
            assert retired.status == "retired"
            historical_version_id = session.scalar(
                select(analysis_content_runs_table.c.analysis_scheme_version_id)
            )
            assert historical_version_id == original.id
    finally:
        runtime.close()


def test_git_refresh_is_blocked_by_manual_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """默认 Scheme 只要出现人工 Version，Git 变更就不能静默覆盖人工配置。"""

    settings = load_settings().model_copy(
        update={"data_dir": tmp_path / "data", "log_dir": tmp_path / "logs"}
    )
    runtime = create_worker_runtime(settings=settings)
    try:
        with runtime.database.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE analysis_schemes, analysis_scheme_versions, jobs "
                "RESTART IDENTITY CASCADE"
            )

        with runtime.database.new_session() as session, session.begin():
            repository = PostgresAnalysisSchemeRepository(session)
            original, created = repository.bootstrap_default(actor_ref="system:git-bootstrap")
            assert created is True
            repository.create_draft(
                name="默认内容舆情分析方案",
                description="人工草稿",
                definition=original.definition,
                actor_ref="user:administrator",
            )

        monkeypatch.setattr(
            analysis_schemes_module,
            "CONTENT_LABELING_PROMPT_PATH",
            _changed_git_prompt(tmp_path),
        )

        with runtime.database.new_session() as session, session.begin():
            repository = PostgresAnalysisSchemeRepository(session)
            active, changed = repository.bootstrap_default(actor_ref="system:git-bootstrap")

            assert changed is False
            assert active.id == original.id
            assert active.version == 1
            assert (
                session.scalar(select(func.count()).select_from(analysis_scheme_versions_table))
                == 2
            )
    finally:
        runtime.close()


def test_git_refresh_is_blocked_by_another_live_scheme(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """存在另一套未删除人工 Scheme 时，不自动推进默认 Git Scheme。"""

    settings = load_settings().model_copy(
        update={"data_dir": tmp_path / "data", "log_dir": tmp_path / "logs"}
    )
    runtime = create_worker_runtime(settings=settings)
    try:
        with runtime.database.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE analysis_schemes, analysis_scheme_versions, jobs "
                "RESTART IDENTITY CASCADE"
            )

        with runtime.database.new_session() as session, session.begin():
            repository = PostgresAnalysisSchemeRepository(session)
            original, created = repository.bootstrap_default(actor_ref="system:git-bootstrap")
            assert created is True
            repository.create_draft(
                name="人工分析方案",
                description="人工草稿",
                definition=original.definition,
                actor_ref="user:administrator",
            )

        monkeypatch.setattr(
            analysis_schemes_module,
            "CONTENT_LABELING_PROMPT_PATH",
            _changed_git_prompt(tmp_path),
        )

        with runtime.database.new_session() as session, session.begin():
            repository = PostgresAnalysisSchemeRepository(session)
            active, changed = repository.bootstrap_default(actor_ref="system:git-bootstrap")

            assert changed is False
            assert active.id == original.id
            assert active.version == 1
    finally:
        runtime.close()



def test_git_refresh_respects_manual_rollback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """管理员回滚到旧 Git Version 后，自动刷新不得覆盖该显式选择。"""

    settings = load_settings().model_copy(
        update={"data_dir": tmp_path / "data", "log_dir": tmp_path / "logs"}
    )
    runtime = create_worker_runtime(settings=settings)
    try:
        with runtime.database.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE analysis_schemes, analysis_scheme_versions, jobs "
                "RESTART IDENTITY CASCADE"
            )

        with runtime.database.new_session() as session, session.begin():
            repository = PostgresAnalysisSchemeRepository(session)
            original, created = repository.bootstrap_default(actor_ref="system:git-bootstrap")
            assert created is True

        changed_path = _changed_git_prompt(tmp_path, label="Git自动刷新版本2")
        monkeypatch.setattr(
            analysis_schemes_module,
            "CONTENT_LABELING_PROMPT_PATH",
            changed_path,
        )
        with runtime.database.new_session() as session, session.begin():
            repository = PostgresAnalysisSchemeRepository(session)
            version2, changed = repository.bootstrap_default(actor_ref="system:git-bootstrap")
            assert changed is True
            assert version2.version == 2
            rolled_back = repository.activate_version(original.id, expected_version=1)
            assert rolled_back.id == original.id
            assert rolled_back.status == "published"

        changed_path = _changed_git_prompt(tmp_path, label="Git自动刷新版本3")
        monkeypatch.setattr(
            analysis_schemes_module,
            "CONTENT_LABELING_PROMPT_PATH",
            changed_path,
        )
        with runtime.database.new_session() as session, session.begin():
            repository = PostgresAnalysisSchemeRepository(session)
            active, changed = repository.bootstrap_default(actor_ref="system:git-bootstrap")

            assert changed is False
            assert active.id == original.id
            assert active.version == 1
            assert (
                session.scalar(select(func.count()).select_from(analysis_scheme_versions_table))
                == 2
            )
    finally:
        runtime.close()
