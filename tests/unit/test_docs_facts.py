from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKER = runpy.run_path(str(ROOT / "scripts" / "quality" / "check_docs_facts.py"))
CHECK_REPOSITORY = CHECKER["check_repository"]
CURRENT_JOB_TYPES = CHECKER["_current_job_types"]
WORKER_JOB_SOURCE_FILES = CHECKER["_worker_job_source_files"]


def test_current_document_facts_match_machine_sources() -> None:
    """当前权威文档应与机器事实源保持一致。"""
    assert CHECK_REPOSITORY() == []


def test_worker_job_sources_follow_production_registry_imports() -> None:
    """Worker Job 事实源应能跟随生产 register_* 导入及 package re-export。"""
    sources = WORKER_JOB_SOURCE_FILES()

    assert sources
    assert Path("backend/src/aima_ugc/modules/ingestion/import_job.py") in sources
    assert all((ROOT / source).is_file() for source in sources)


def test_worker_job_fact_source_excludes_unregistered_job_constants() -> None:
    """Worker 文档门禁只使用生产 Registry 装配的 Job，不扫描未注册备用常量。"""
    assert "collection.xiaohongshu.raw-replay.v1" not in CURRENT_JOB_TYPES()
