"""Prompt V4.6 首次正式打标前的 PostgreSQL Scheme bootstrap 回归。"""

from __future__ import annotations

from pathlib import Path

from aima_ugc.adapters.persistence.postgres import analysis_schemes as scheme_module
from aima_ugc.adapters.persistence.postgres.analysis_schemes import (
    PostgresAnalysisSchemeRepository,
)
from aima_ugc.bootstrap.worker import create_worker_runtime
from aima_ugc.modules.analysis import CONTENT_LABELING_PROMPT_PATH
from aima_ugc.modules.analysis.schemes import prompt_taxonomy_from_version
from aima_ugc.platform.config import load_settings


def test_unused_system_git_bootstrap_refreshes_to_v46_before_first_analysis_run(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """纯系统旧基线且没有 Analysis Run 时可追加刷新，旧 Version 继续保留审计历史。"""

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

        legacy_v4 = CONTENT_LABELING_PROMPT_PATH.with_name("content_labeling_v4.md")
        monkeypatch.setattr(scheme_module, "CONTENT_LABELING_PROMPT_PATH", legacy_v4)
        session = runtime.database.new_session()
        try:
            with session.begin():
                first, created = PostgresAnalysisSchemeRepository(session).bootstrap_default(
                    actor_ref="system:git-bootstrap"
                )
                assert created is True
                assert first.version == 1
                assert prompt_taxonomy_from_version(first).output_protocol_version == (
                    "content-labeling.v4"
                )
        finally:
            session.close()

        monkeypatch.setattr(
            scheme_module,
            "CONTENT_LABELING_PROMPT_PATH",
            CONTENT_LABELING_PROMPT_PATH,
        )
        session = runtime.database.new_session()
        try:
            with session.begin():
                refreshed, changed = PostgresAnalysisSchemeRepository(session).bootstrap_default(
                    actor_ref="system:git-bootstrap"
                )
                assert changed is True
                assert refreshed.version == 2
                assert refreshed.prompt_sha256 != first.prompt_sha256
                assert prompt_taxonomy_from_version(refreshed).output_protocol_version == (
                    "content-labeling.v4.6"
                )
                versions = PostgresAnalysisSchemeRepository(session).list_schemes()[0][1]
                assert [(item.version, item.status) for item in versions] == [
                    (2, "published"),
                    (1, "retired"),
                ]
        finally:
            session.close()

        # 一旦已经形成额外 Version，就不再自动按后续 Git 指针回切。
        monkeypatch.setattr(scheme_module, "CONTENT_LABELING_PROMPT_PATH", legacy_v4)
        session = runtime.database.new_session()
        try:
            with session.begin():
                unchanged, changed = PostgresAnalysisSchemeRepository(session).bootstrap_default(
                    actor_ref="system:git-bootstrap"
                )
                assert changed is False
                assert unchanged.id == refreshed.id
        finally:
            session.close()
    finally:
        runtime.close()
