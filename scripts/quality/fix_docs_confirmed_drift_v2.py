"""一次性修复第二批已由当前仓库机器事实确认的文档漂移。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, got {count}: {old!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def fix_reporting_export_contract() -> None:
    old = """```text
backend/src/aima_ugc/contracts/export.py
backend/src/aima_ugc/platform/export/excel.py
```"""
    new = """- [`backend/src/aima_ugc/contracts/export/models.py`](../../../contracts/export/models.py)
- [`backend/src/aima_ugc/platform/export/excel.py`](../export/excel.py)"""
    target = ROOT / "backend/src/aima_ugc/platform/reporting/README.md"
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 2:
        raise RuntimeError(f"reporting README: expected two old export blocks, got {count}")
    target.write_text(text.replace(old, new), encoding="utf-8")


def fix_canonical_paths() -> None:
    replace_once(
        "docs/01_代码结构与修改导航.md",
        """目标 Contract：

```text
backend/src/aima_ugc/contracts/canonical.py
contracts/canonical/
```""",
        """目标 Contract：

- [`backend/src/aima_ugc/contracts/canonical/__init__.py`](../backend/src/aima_ugc/contracts/canonical/__init__.py)：Canonical Python package 的公开导出边界；
- [`contracts/canonical/`](../contracts/canonical/)：生成的 JSON Schema。""",
    )
    replace_once(
        "docs/appendix/02_TikHub五平台真实响应与字段映射.md",
        """精确 Contract：

```text
backend/src/aima_ugc/contracts/canonical.py
```""",
        """精确评论 Contract：[`backend/src/aima_ugc/contracts/canonical/comment.py`](../../backend/src/aima_ugc/contracts/canonical/comment.py)。""",
    )
    replace_once(
        "docs/appendix/02_TikHub五平台真实响应与字段映射.md",
        """### 第四步：看 Contract

```text
backend/src/aima_ugc/contracts/canonical.py
```

确认系统允许保存哪些公共字段。""",
        """### 第四步：看 Contract

查看 [`backend/src/aima_ugc/contracts/canonical/comment.py`](../../backend/src/aima_ugc/contracts/canonical/comment.py)，确认系统允许保存哪些公共字段。""",
    )
    replace_once(
        "docs/appendix/08_数据入口与统一入库实现.md",
        """精确定义：

```text
backend/src/aima_ugc/contracts/canonical.py
contracts/canonical/
```""",
        """精确定义：

- [`backend/src/aima_ugc/contracts/canonical/__init__.py`](../../backend/src/aima_ugc/contracts/canonical/__init__.py)：Canonical Python package 的公开导出边界；
- [`contracts/canonical/`](../../contracts/canonical/)：生成的 JSON Schema。""",
    )
    replace_once(
        "docs/blueprint/01_总体架构与技术选型.md",
        """精确 Canonical：

```text
backend/src/aima_ugc/contracts/canonical.py
contracts/canonical/
```""",
        """精确 Canonical：

- [`backend/src/aima_ugc/contracts/canonical/__init__.py`](../../backend/src/aima_ugc/contracts/canonical/__init__.py)：Canonical Python package 的公开导出边界；
- [`contracts/canonical/`](../../contracts/canonical/)：生成的 JSON Schema。""",
    )
    replace_once(
        "docs/blueprint/02_采集系统与数据标准化.md",
        """机器事实：

```text
backend/src/aima_ugc/contracts/canonical.py
contracts/canonical/
```""",
        """机器事实：

- [`backend/src/aima_ugc/contracts/canonical/__init__.py`](../../backend/src/aima_ugc/contracts/canonical/__init__.py)：Canonical Python package 的公开导出边界；
- [`contracts/canonical/`](../../contracts/canonical/)：生成的 JSON Schema。""",
    )
    replace_once(
        "docs/blueprint/07_技术决策与实施门禁.md",
        """机器事实：

```text
backend/src/aima_ugc/contracts/canonical.py
backend/src/aima_ugc/adapters/providers/tikhub/
backend/src/aima_ugc/modules/content/ingestion.py
backend/src/aima_ugc/modules/ingestion/
```""",
        """机器事实：

- [`backend/src/aima_ugc/contracts/canonical/__init__.py`](../../backend/src/aima_ugc/contracts/canonical/__init__.py)
- [`backend/src/aima_ugc/adapters/providers/tikhub/`](../../backend/src/aima_ugc/adapters/providers/tikhub/)
- [`backend/src/aima_ugc/modules/content/ingestion.py`](../../backend/src/aima_ugc/modules/content/ingestion.py)
- [`backend/src/aima_ugc/modules/ingestion/`](../../backend/src/aima_ugc/modules/ingestion/)""",
    )


def fix_runtime_and_fullstack_entries() -> None:
    replace_once(
        "docs/appendix/05_Scheduler调度执行与停机恢复.md",
        """主要测试按当前仓库实际分布在：

```text
tests/unit/collection/
tests/integration/
.github/workflows/stage7-scheduler-runtime.yml
```""",
        """主要测试按当前仓库实际分布在：

- [`tests/unit/collection/`](../../tests/unit/collection/)
- [`tests/integration/`](../../tests/integration/)
- [`.github/workflows/runtime.yml`](../../.github/workflows/runtime.yml)：当前 Runtime Acceptance；Scheduler 进程/Compose 运行边界由这一永久 Workflow 与相关测试共同覆盖，不再存在独立 `stage7-scheduler-runtime.yml`。""",
    )
    replace_once(
        "docs/appendix/11_生产部署与离线Release方案.md",
        """Windows 本地兼容相关时额外读：

```text
compose.windows.yaml
docs/guides/03_Windows Docker Desktop Compose运行.md
.github/workflows/compose-windows-desktop.yml
```""",
        """Windows 本地兼容相关时额外读：

- [`compose.windows.yaml`](../../compose.windows.yaml)
- [`docs/guides/03_Windows Docker Desktop Compose运行.md`](../guides/03_Windows%20Docker%20Desktop%20Compose运行.md)
- [`.github/workflows/runtime.yml`](../../.github/workflows/runtime.yml)：Windows Compose overlay 已并入当前 Runtime Acceptance，不再存在独立 `compose-windows-desktop.yml`。""",
    )
    replace_once(
        "docs/appendix/09_Stage8F前后端能力矩阵与真实验收.md",
        """永久测试入口：

```text
.github/workflows/fullstack.yml
frontend/playwright.fullstack.config.ts
frontend/e2e-fullstack/excel-import.spec.ts
frontend/e2e-fullstack/collection-plan-search-config.spec.ts
tests/fullstack/create_stage8f_excel_fixture.py
tests/fullstack/seed_collection_plan_provider.py
tests/fullstack/run_stage8f_worker.py
```

真实验收不 Mock `/api/v1/**`，固定覆盖 Excel 成功、Excel 失败和 Collection Plan 配置持久化三条链。""",
        """永久测试入口：

- [`.github/workflows/fullstack.yml`](../../.github/workflows/fullstack.yml)
- [`frontend/playwright.fullstack.config.ts`](../../frontend/playwright.fullstack.config.ts)
- [`frontend/e2e-fullstack/excel-import.spec.ts`](../../frontend/e2e-fullstack/excel-import.spec.ts)
- [`frontend/e2e-fullstack/collection-plan-search-config.spec.ts`](../../frontend/e2e-fullstack/collection-plan-search-config.spec.ts)
- [`frontend/e2e-fullstack/manual-relevance-review.spec.ts`](../../frontend/e2e-fullstack/manual-relevance-review.spec.ts)
- [`frontend/e2e-fullstack/stage12-historical-analysis.spec.ts`](../../frontend/e2e-fullstack/stage12-historical-analysis.spec.ts)
- [`tests/fullstack/create_stage8f_excel_fixture.py`](../../tests/fullstack/create_stage8f_excel_fixture.py)
- [`tests/fullstack/create_stage12_historical_fixture.py`](../../tests/fullstack/create_stage12_historical_fixture.py)
- [`tests/fullstack/seed_collection_plan_provider.py`](../../tests/fullstack/seed_collection_plan_provider.py)
- [`tests/fullstack/seed_stage8f_manual_relevance_review.py`](../../tests/fullstack/seed_stage8f_manual_relevance_review.py)
- [`tests/fullstack/fake_openai_llm.py`](../../tests/fullstack/fake_openai_llm.py)

当前 Workflow 直接用 `python -m aima_ugc.entrypoints.worker_main` 启动真实 Worker，不再存在 `tests/fullstack/run_stage8f_worker.py`。真实验收不 Mock `/api/v1/**`，当前 Full-stack 套件覆盖 Excel 成功/失败、Collection Plan 配置持久化、声音广场人工相关性复核，以及 Stage 12 历史导入与 Analysis Run 链路。""",
    )
    replace_once(
        "docs/roadmap/README.md",
        """Stage 8F 的永久业务闭环证据入口：

```text
docs/appendix/09_Stage8F前后端能力矩阵与真实验收.md
.github/workflows/stage8f-fullstack.yml
frontend/e2e-fullstack/excel-import.spec.ts
```""",
        """Stage 8F 及其后续持续扩展后的永久业务闭环证据入口：

- [`docs/appendix/09_Stage8F前后端能力矩阵与真实验收.md`](../appendix/09_Stage8F前后端能力矩阵与真实验收.md)
- [`.github/workflows/fullstack.yml`](../../.github/workflows/fullstack.yml)
- [`frontend/e2e-fullstack/excel-import.spec.ts`](../../frontend/e2e-fullstack/excel-import.spec.ts)

`fullstack.yml` 是当前唯一永久 Full-stack Acceptance Workflow；Stage 8F 后新增的人工相关性与 Stage 12 场景也在同一套 Full-stack 入口继续扩展，不再维护独立 `stage8f-fullstack.yml`。""",
    )


def fix_frontend_feature_fact() -> None:
    replace_once(
        "docs/blueprint/01_总体架构与技术选型.md",
        """当前正式 Feature：

```text
frontend/src/features/voice-plaza/
frontend/src/features/import-batches/
frontend/src/features/collection-strategy/
frontend/src/features/collection-runtime/
```""",
        """当前实际 Feature 目录：

- [`frontend/src/features/voice-plaza/`](../../frontend/src/features/voice-plaza/)
- [`frontend/src/features/import-batches/`](../../frontend/src/features/import-batches/)
- [`frontend/src/features/collection-strategy/`](../../frontend/src/features/collection-strategy/)

`/collection-runtime` 是当前正式 Route，但它由 `import-batches/pages/CollectionRuntimePage` 实现；仓库不存在独立 `frontend/src/features/collection-runtime/` Feature。""",
    )


def fix_api_coverage() -> None:
    old = """旧 `/api/v1/historical-import-*` Route 也继续作为 Stage 12 兼容边界存在，但当前页面不依赖它建立平行工作流。

---"""
    new = """## 6.3 `GET /api/v1/import-batches/{batch_id}/supplement-eligibility`

这是采集补采前的只读资格投影。后端按当前 Analysis Identity 读取该 Import Batch 对应的现有 Content Target，并按五个平台返回真实 `target_count`；接口本身不创建 Collection Run，也不把声音广场列表查询结果当资格依据。真正创建补采 Run 时，服务端仍会重新冻结/校验同一目标事实，因此该接口是前端展示与预检入口，不是最终写入守卫。

## 6.4 Historical Import 兼容 API

Stage 12 当前页面主流程使用 `data-import-campaigns`，但下列 Historical Import HTTP Contract 仍存在于当前 generated OpenAPI，且 HTTP 层没有标记 `deprecated`；它们属于兼容业务入口，不能描述成“已删除”，也不能再当成当前页面的第二套主工作流：

```text
GET  /api/v1/historical-import/directories
GET  /api/v1/historical-import-campaigns
POST /api/v1/historical-import-campaigns
GET  /api/v1/historical-import-campaigns/{campaign_id}
GET  /api/v1/historical-import-campaigns/{campaign_id}/items
GET  /api/v1/historical-import-campaigns/{campaign_id}/conflicts
POST /api/v1/historical-import-campaigns/{campaign_id}/start
POST /api/v1/historical-import-campaigns/{campaign_id}/cancel
POST /api/v1/historical-import-campaigns/{campaign_id}/retry-failed
```

精确 Method、Schema、operationId 和当前是否存在始终以 [`contracts/openapi/openapi.json`](../contracts/openapi/openapi.json) 为准。

---"""
    replace_once("docs/03_API接口说明.md", old, new)


def main() -> int:
    fix_reporting_export_contract()
    fix_canonical_paths()
    fix_runtime_and_fullstack_entries()
    fix_frontend_feature_fact()
    fix_api_coverage()
    print("第二批确认文档漂移已修复。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
