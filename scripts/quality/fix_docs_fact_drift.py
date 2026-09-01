"""一次性修复已由当前仓库机器事实确认的文档漂移。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _replace_once(path: str, old: str, new: str) -> None:
    """只允许精确替换一次，防止在长文档中静默误改或漏改。"""
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one match, got {count}: {old!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def _replace_all_exact(path: str, old: str, new: str, expected: int) -> None:
    """仅在已知精确出现次数匹配时执行批量替换。"""
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise RuntimeError(
            f"{path}: expected {expected} matches, got {count}: {old!r}"
        )
    target.write_text(text.replace(old, new), encoding="utf-8")


def _fix_source_mode() -> None:
    _replace_once(
        "docs/guides/02_AIMA持续开发与内网上线通用提示词.md",
        "2. 按 `AGENTS.md` 读取 `.agents/skills/reliable-vibe-coding/SKILL.md`；\n"
        "3. 按 Skill 判断本轮任务等级和 Change 要求；",
        "2. 使用当前宿主实际可用的 GitHub/仓库读取能力读取 "
        "`dingyuwen777/Agent_Skills` 当前默认分支 canonical 源码：先读根 `AGENTS.md`，"
        "再按当前源码导航读取 ENTRY、Router、命中的 `SKILL.md` 与 required References；"
        "不得把 AIMA 本地 `.agents` 安装副本、Runtime、Release、缓存或历史聊天当作 canonical；\n"
        "3. 按当前 canonical Skill 判断本轮任务等级和 Change 要求，同时继续遵守 AIMA 自己的项目 Overlay；",
    )


def _fix_root_readme_navigation() -> None:
    old = """关键代码：

```text
backend/src/aima_ugc/bootstrap/import_http.py
backend/src/aima_ugc/bootstrap/import_worker.py
backend/src/aima_ugc/bootstrap/historical_import_http.py
backend/src/aima_ugc/bootstrap/historical_import_worker.py
backend/src/aima_ugc/bootstrap/manual_ingestion.py
backend/src/aima_ugc/modules/ingestion/
backend/src/aima_ugc/modules/content/ingestion.py
```
"""
    new = """关键代码：

- [`backend/src/aima_ugc/bootstrap/import_http.py`](backend/src/aima_ugc/bootstrap/import_http.py)
- [`backend/src/aima_ugc/bootstrap/import_worker.py`](backend/src/aima_ugc/bootstrap/import_worker.py)
- [`backend/src/aima_ugc/bootstrap/historical_import_http.py`](backend/src/aima_ugc/bootstrap/historical_import_http.py)
- [`backend/src/aima_ugc/bootstrap/historical_import_worker.py`](backend/src/aima_ugc/bootstrap/historical_import_worker.py)
- [`backend/src/aima_ugc/bootstrap/manual_ingestion.py`](backend/src/aima_ugc/bootstrap/manual_ingestion.py)
- [`backend/src/aima_ugc/modules/ingestion/`](backend/src/aima_ugc/modules/ingestion/)
- [`backend/src/aima_ugc/modules/content/ingestion.py`](backend/src/aima_ugc/modules/content/ingestion.py)
"""
    _replace_once("README.md", old, new)


def _fix_api_fact_sources() -> None:
    old = """精确机器事实始终以：

```text
backend/src/aima_ugc/contracts/http.py
backend/src/aima_ugc/contracts/runtime.py
backend/src/aima_ugc/contracts/relevance_review.py
backend/src/aima_ugc/bootstrap/api.py
backend/src/aima_ugc/bootstrap/analysis_capability_http.py
backend/src/aima_ugc/entrypoints/api_main.py
contracts/openapi/openapi.json
frontend/src/generated/api/
```

为准。
"""
    new = """精确机器事实始终以以下当前仓库 Owner 为准：

- [`backend/src/aima_ugc/contracts/http.py`](../backend/src/aima_ugc/contracts/http.py)
- [`backend/src/aima_ugc/contracts/runtime.py`](../backend/src/aima_ugc/contracts/runtime.py)
- [`backend/src/aima_ugc/contracts/relevance_review.py`](../backend/src/aima_ugc/contracts/relevance_review.py)
- [`backend/src/aima_ugc/bootstrap/api.py`](../backend/src/aima_ugc/bootstrap/api.py)
- [`backend/src/aima_ugc/bootstrap/analysis_capability_http.py`](../backend/src/aima_ugc/bootstrap/analysis_capability_http.py)
- [`backend/src/aima_ugc/entrypoints/api_main.py`](../backend/src/aima_ugc/entrypoints/api_main.py)
- [`contracts/openapi/openapi.json`](../contracts/openapi/openapi.json)
- [`frontend/src/generated/api/`](../frontend/src/generated/api/)
"""
    _replace_once("docs/03_API接口说明.md", old, new)


def _fix_stage12_fact_sources() -> None:
    old = """任何后续修改不得从本文旧施工措辞猜当前实现。先重新读取当前分支：

```text
AGENTS.md
.agents/skills/coding/SKILL.md
.agents/skills/review/SKILL.md
docs/blueprint/README.md
docs/blueprint/02_采集系统与数据标准化.md
docs/blueprint/03_数据库与文件存储.md
docs/blueprint/04_后端任务API与前端.md
docs/blueprint/05_日志安全部署与运维.md
docs/blueprint/06_开发约束与分阶段实施.md
docs/blueprint/07_技术决策与实施门禁.md
docs/roadmap/02_生产上线实施路线.md
本文
docs/appendix/07_AI舆情打标与分析实现.md
docs/appendix/08_数据入口与统一入库实现.md
docs/appendix/14_4000万历史迁移与Analysis Run运行手册.md
docs/01_代码结构与修改导航.md
docs/02_环境运行与部署.md
backend/src/aima_ugc/modules/ingestion/README.md
backend/src/aima_ugc/modules/content/README.md
backend/src/aima_ugc/modules/analysis/README.md
backend/src/aima_ugc/modules/ingestion/historical_*.py
backend/src/aima_ugc/bootstrap/historical_import_http.py
backend/src/aima_ugc/bootstrap/historical_import_worker.py
backend/src/aima_ugc/adapters/persistence/postgres/historical_import.py
backend/src/aima_ugc/adapters/persistence/postgres/historical_content.py
backend/src/aima_ugc/modules/analysis/content_analysis_job.py
backend/src/aima_ugc/adapters/persistence/postgres/analysis.py
backend/src/aima_ugc/bootstrap/analysis_worker.py
backend/src/aima_ugc/contracts/http.py
backend/src/aima_ugc/bootstrap/api.py
backend/src/aima_ugc/bootstrap/worker.py
compose.yaml
env.production.example
migrations/
tests/
frontend/src/features/import-batches/
frontend/src/features/voice-plaza/
frontend/e2e/
frontend/e2e-fullstack/
```
"""
    new = """任何后续修改不得从本文旧施工措辞猜当前实现。先重新读取当前分支的项目 Overlay 和真实事实源：

- [`AGENTS.md`](../../AGENTS.md)
- [`docs/blueprint/README.md`](../blueprint/README.md)
- [`docs/blueprint/02_采集系统与数据标准化.md`](../blueprint/02_采集系统与数据标准化.md)
- [`docs/blueprint/03_数据库与文件存储.md`](../blueprint/03_数据库与文件存储.md)
- [`docs/blueprint/04_后端任务API与前端.md`](../blueprint/04_后端任务API与前端.md)
- [`docs/blueprint/05_日志安全部署与运维.md`](../blueprint/05_日志安全部署与运维.md)
- [`docs/blueprint/06_开发约束与分阶段实施.md`](../blueprint/06_开发约束与分阶段实施.md)
- [`docs/blueprint/07_技术决策与实施门禁.md`](../blueprint/07_技术决策与实施门禁.md)
- [`docs/roadmap/02_生产上线实施路线.md`](02_生产上线实施路线.md)
- 本文（当前文件）
- [`docs/appendix/07_AI舆情打标与分析实现.md`](../appendix/07_AI舆情打标与分析实现.md)
- [`docs/appendix/08_数据入口与统一入库实现.md`](../appendix/08_数据入口与统一入库实现.md)
- [`docs/appendix/14_4000万历史迁移与Analysis Run运行手册.md`](../appendix/14_4000万历史迁移与Analysis%20Run运行手册.md)
- [`docs/01_代码结构与修改导航.md`](../01_代码结构与修改导航.md)
- [`docs/02_环境运行与部署.md`](../02_环境运行与部署.md)
- [`backend/src/aima_ugc/modules/ingestion/README.md`](../../backend/src/aima_ugc/modules/ingestion/README.md)
- [`backend/src/aima_ugc/modules/content/README.md`](../../backend/src/aima_ugc/modules/content/README.md)
- [`backend/src/aima_ugc/modules/analysis/README.md`](../../backend/src/aima_ugc/modules/analysis/README.md)
- `backend/src/aima_ugc/modules/ingestion/historical_*.py`（按本轮调用链读取实际命中文件）
- [`backend/src/aima_ugc/bootstrap/historical_import_http.py`](../../backend/src/aima_ugc/bootstrap/historical_import_http.py)
- [`backend/src/aima_ugc/bootstrap/historical_import_worker.py`](../../backend/src/aima_ugc/bootstrap/historical_import_worker.py)
- [`backend/src/aima_ugc/adapters/persistence/postgres/historical_import.py`](../../backend/src/aima_ugc/adapters/persistence/postgres/historical_import.py)
- [`backend/src/aima_ugc/adapters/persistence/postgres/historical_content.py`](../../backend/src/aima_ugc/adapters/persistence/postgres/historical_content.py)
- [`backend/src/aima_ugc/modules/analysis/content_analysis_job.py`](../../backend/src/aima_ugc/modules/analysis/content_analysis_job.py)
- [`backend/src/aima_ugc/adapters/persistence/postgres/analysis.py`](../../backend/src/aima_ugc/adapters/persistence/postgres/analysis.py)
- [`backend/src/aima_ugc/bootstrap/analysis_worker.py`](../../backend/src/aima_ugc/bootstrap/analysis_worker.py)
- [`backend/src/aima_ugc/contracts/http.py`](../../backend/src/aima_ugc/contracts/http.py)
- [`backend/src/aima_ugc/bootstrap/api.py`](../../backend/src/aima_ugc/bootstrap/api.py)
- [`backend/src/aima_ugc/bootstrap/worker.py`](../../backend/src/aima_ugc/bootstrap/worker.py)
- [`compose.yaml`](../../compose.yaml)
- [`env.production.example`](../../env.production.example)
- `migrations/`、`tests/`、`frontend/src/features/import-batches/`、`frontend/src/features/voice-plaza/`、`frontend/e2e/`、`frontend/e2e-fullstack/`：按本轮实际影响面读取，不把目录清单当成固定机器事实副本。

Agent_Skills 通用治理必须使用 Source Mode：通过当前宿主实际可用的 GitHub/仓库读取能力读取 `dingyuwen777/Agent_Skills` 当前默认分支 canonical 源码，先读其根 `AGENTS.md`，再按当前源码导航读取 ENTRY、Router、命中的 `SKILL.md` 与 required References。AIMA 本地 `.agents` 安装副本、Runtime、Release、缓存和历史聊天不得作为 canonical Skill 来源；但 AIMA 当前分支自己的 `AGENTS.md`、文档、代码、Contract、Schema、CI 和部署事实仍必须遵守。
"""
    _replace_once("docs/roadmap/03_4000万历史数据迁移实施方案.md", old, new)


def _fix_api_shorthands() -> None:
    replacements: dict[str, list[tuple[str, str, int]]] = {
        "backend/src/aima_ugc/modules/reporting/README.md": [
            (
                "→ GET /download",
                "→ GET /api/v1/data-exports/{export_id}/download",
                1,
            )
        ],
        "docs/03_API接口说明.md": [
            ("`/content-analysis-requests`", "`/api/v1/content-analysis-requests`", 1),
            ("`/import-batches`", "`/api/v1/import-batches`", 1),
        ],
        "docs/appendix/08_数据入口与统一入库实现.md": [
            ("`/relevance-config`", "`/api/v1/relevance-config`", 1),
            ("`/import-batches`", "`/api/v1/import-batches`", 1),
        ],
        "docs/appendix/09_Stage8F前后端能力矩阵与真实验收.md": [
            ("`GET /contents`", "`GET /api/v1/contents`", 1),
        ],
        "docs/blueprint/04_后端任务API与前端.md": [
            ("`GET /collection-capabilities`", "`GET /api/v1/collection-capabilities`", 1),
            ("`GET /content-analysis-capabilities`", "`GET /api/v1/content-analysis-capabilities`", 1),
            ("`POST /content-analysis-requests`", "`POST /api/v1/content-analysis-requests`", 1),
            ("`/analysis/content-runs/preview`", "`/api/v1/analysis/content-runs/preview`", 1),
            ("`POST /content-relevance-reviews`", "`POST /api/v1/content-relevance-reviews`", 1),
            ("`GET /contents`", "`GET /api/v1/contents`", 1),
            ("`/import-batches`", "`/api/v1/import-batches`", 1),
            ("`/content-analysis-jobs/{job_id}`", "`/api/v1/content-analysis-jobs/{job_id}`", 1),
        ],
        "docs/blueprint/07_技术决策与实施门禁.md": [
            ("`GET /contents`", "`GET /api/v1/contents`", 1),
        ],
        "docs/roadmap/01_内网V1上线实施计划.md": [
            ("`/import-batches`", "`/api/v1/import-batches`", 1),
        ],
    }
    for path, items in replacements.items():
        for old, new, expected in items:
            _replace_all_exact(path, old, new, expected)


def main() -> int:
    _fix_source_mode()
    _fix_root_readme_navigation()
    _fix_api_fact_sources()
    _fix_stage12_fact_sources()
    _fix_api_shorthands()
    print("已修复确认的文档事实漂移与导航清单。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
