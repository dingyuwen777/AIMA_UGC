from __future__ import annotations

import runpy
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CHECKER = runpy.run_path(str(ROOT / "scripts" / "quality" / "check_docs_facts.py"))
CHECK_REPOSITORY = CHECKER["check_repository"]
CURRENT_JOB_TYPES = CHECKER["_current_job_types"]
WORKER_JOB_SOURCE_FILES = CHECKER["_worker_job_source_files"]
REQUIRE_EXACT_BLOCK = CHECKER["_require_exact_block"]
CHECK_ROADMAP_LIFECYCLE = CHECKER["_check_roadmap_lifecycle"]
CHECK_RETIRED_LIVE_DOCS = CHECKER["_check_retired_live_docs"]
RETIRED_LIVE_DOCS = CHECKER["RETIRED_LIVE_DOCS"]


def _write(path: Path, content: str) -> None:
    """写入文档事实检查的最小测试夹具。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _with_root(
    function: Callable[..., Any],
    root: Path,
    *args: object,
    **kwargs: object,
) -> Any:
    """临时把 checker 的 ROOT 指向隔离夹具并恢复原值。"""
    original = function.__globals__["ROOT"]
    function.__globals__["ROOT"] = root
    try:
        return function(*args, **kwargs)
    finally:
        function.__globals__["ROOT"] = original


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


def test_exact_fact_block_rejects_missing_and_stale_values(tmp_path: Path) -> None:
    """受控小型事实块必须同时拒绝漏写当前值和残留旧值。"""
    _write(
        tmp_path / "docs/facts.md",
        """# Facts

<!-- docs-facts:example:start -->
```text
alpha
legacy
```
<!-- docs-facts:example:end -->
""",
    )
    errors: list[str] = []

    _with_root(
        REQUIRE_EXACT_BLOCK,
        tmp_path,
        errors,
        code="TEST",
        owner_doc="docs/facts.md",
        key="example",
        values={"alpha", "beta"},
        label="示例",
    )

    assert any("缺少当前示例事实 beta" in error for error in errors)
    assert any("存在已失效示例事实 legacy" in error for error in errors)


def test_exact_fact_block_accepts_markdown_link_values(tmp_path: Path) -> None:
    """导航型事实可以写成可点击 Markdown 链接，同时仍按链接标题做 exact-set。"""
    _write(
        tmp_path / "docs/facts.md",
        """# Facts

<!-- docs-facts:example:start -->
- [`alpha.yml`](../.github/workflows/alpha.yml)
- [`beta.yml`](../.github/workflows/beta.yml)
<!-- docs-facts:example:end -->
""",
    )
    errors: list[str] = []

    _with_root(
        REQUIRE_EXACT_BLOCK,
        tmp_path,
        errors,
        code="TEST",
        owner_doc="docs/facts.md",
        key="example",
        values={"alpha.yml", "beta.yml"},
        label="示例",
    )

    assert errors == []


def test_exact_fact_block_rejects_duplicate_values(tmp_path: Path) -> None:
    """受控事实块中的重复值不能被 set 比较静默吞掉。"""
    _write(
        tmp_path / "docs/facts.md",
        """# Facts

<!-- docs-facts:example:start -->
```text
alpha
alpha
```
<!-- docs-facts:example:end -->
""",
    )
    errors: list[str] = []

    _with_root(
        REQUIRE_EXACT_BLOCK,
        tmp_path,
        errors,
        code="TEST",
        owner_doc="docs/facts.md",
        key="example",
        values={"alpha"},
        label="示例",
    )

    assert any("重复示例事实 alpha" in error for error in errors)


def test_roadmap_lifecycle_requires_active_status(tmp_path: Path) -> None:
    """live Roadmap 必须显式 Active，完成文档不能长期留在当前路线。"""
    _write(
        tmp_path / "docs/roadmap/01_active.md",
        "# Active\n\n- 状态：Active\n",
    )
    _write(
        tmp_path / "docs/roadmap/02_completed.md",
        "# Completed\n\n> Status: Completed\n",
    )
    errors: list[str] = []

    _with_root(CHECK_ROADMAP_LIFECYCLE, tmp_path, errors)

    assert not any("01_active.md" in error for error in errors)
    assert any(error.startswith("DOCF015 docs/roadmap/02_completed.md") for error in errors)


def test_retired_live_doc_cannot_be_reintroduced(tmp_path: Path) -> None:
    """已经迁移/完成的旧路径重新出现时必须被机器门禁拒绝。"""
    retired = sorted(RETIRED_LIVE_DOCS)[0]
    _write(tmp_path / retired, "# retired\n")
    errors: list[str] = []

    _with_root(CHECK_RETIRED_LIVE_DOCS, tmp_path, errors)

    assert errors == [f"DOCF014 {retired}: 已退役文档不得重新进入 live docs"]


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
