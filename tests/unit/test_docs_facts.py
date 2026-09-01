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


def test_long_term_collection_docs_do_not_regress_to_historical_stage_claims() -> None:
    """当前文档必须描述现行采集链，不能重新长出已失效的阶段性结论。"""
    collection_readme = (ROOT / "backend/src/aima_ugc/modules/collection/README.md").read_text(
        encoding="utf-8"
    )
    blueprint_02 = (ROOT / "docs/blueprint/02_采集系统与数据标准化.md").read_text(encoding="utf-8")
    blueprint_08 = (ROOT / "docs/blueprint/08_采集策略与平台能力.md").read_text(encoding="utf-8")
    scheduler_appendix = (ROOT / "docs/appendix/05_Scheduler调度执行与停机恢复.md").read_text(
        encoding="utf-8"
    )

    assert "当前机器 Registry 只接线已经有实现事实的 `tikhub + xiaohongshu`" not in blueprint_02
    assert "当前 main 实际只有小红书 Operation/Mapper" not in blueprint_02
    assert "Stage 7 仍未闭环的核心是正式 `collection.run.v1` live Worker" not in blueprint_02
    assert "当前 L3 Corrective Change" not in collection_readme
    assert "collection_content_actions" in collection_readme
    assert "Candidate 在 Mapper 前" in blueprint_02
    assert "durable content action" in blueprint_08
    assert "计算 Job Deadline" in scheduler_appendix
    assert "latest_only" in scheduler_appendix
