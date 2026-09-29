"""唯一内容打标 Prompt 的 PostgreSQL Scheme bootstrap 回归。"""

from __future__ import annotations

from pathlib import Path

from aima_ugc.adapters.persistence.postgres.analysis_schemes import (
    PostgresAnalysisSchemeRepository,
)
from aima_ugc.bootstrap.worker import create_worker_runtime
from aima_ugc.modules.analysis import CONTENT_LABELING_PROMPT_PATH, PROMPT_VERSION
from aima_ugc.modules.analysis.schemes import prompt_taxonomy_from_version
from aima_ugc.platform.config import load_settings


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
