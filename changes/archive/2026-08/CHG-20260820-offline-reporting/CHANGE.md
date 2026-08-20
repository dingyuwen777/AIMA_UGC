---
schema: rvc-change/v1
id: CHG-20260820-offline-reporting
title: 离线数据报告与 Markdown Word 导出
level: L2
status: done
owner: dingyuwen777
branch: feature/offline-reporting
created: 2026-08-20
updated: 2026-08-20
depends_on: []
affected_areas:
  - platform-reporting
  - imports-test
affected_paths:
  - backend/src/aima_ugc/platform/reporting/
  - backend/src/aima_ugc/adapters/providers/imports_test/
  - tests/unit/platform/
  - tests/unit/collection/test_p1g_imports_run_all.py
  - tests/unit/collection/test_imports_test_run_directory.py
  - docs/blueprint/13-统一数据Excel导出与调试复用.md
contracts: []
data_changes: []
---

# 目标

在不改变 Canonical、Analysis、UnifiedDataExcelV1、数据库或 Excel 数据语义的前提下，为处理完成的统一 Excel 增加 Provider-neutral 的只读报告能力：

```text
统一 Excel
→ 统计
→ Markdown + Mermaid
→ Word
```

默认 `run_all()` 在最终 `labeled_data.xlsx` 后生成报告；已有处理后 Excel 也可单独传给 `generate_report(excel_path=...)`，不必重跑前序流程。

默认 Markdown 模板归 `aima_ugc.platform.reporting` 所有，固定维护在：

```text
backend/src/aima_ugc/platform/reporting/report_template.md
```

`imports_test` 只复用共享默认模板，不维护第二份模板路径或模板内容。

# 最终结果

本 Change 已完成并通过 PR #90 以 Squash merge 合入 `main`：

```text
PR: #90 实现共享离线报告与 Markdown Word 导出
merge commit: 46a077c26bab5981767003121934a7d45e8d8bf0
```

合并后 `main` 同时保留原有完整人工 Excel/AI 链路和新增报告链路：

```text
单/多 Excel INPUT_XLSX_FILES
→ Canonical 合并
→ 全局关键词过滤
→ 全局稳定身份去重
→ 可选多源 PostgreSQL 入库
→ LLM 打标 + 请求审计/费用计算与复算
→ labeled_data.xlsx
→ 共享 Markdown/Mermaid 报告
→ Word 报告
```

没有通过报告功能覆盖、降级或删除主分支已有的多 Excel、数据库或 LLM 费用审计实现。

# 成功标准

- [x] `run_all()` 保留完整主链，并在 `export_labeled_excel` 后追加 `generate_report`。
- [x] `run_summary.json` 与 `P1RunSummary` 返回 `report_markdown` / `report_word` 路径。
- [x] 报告覆盖内容总量、评论总量、标签对总量、平台、情感、一级/二级标签、一级→二级标签对、关键词、日期范围、每日趋势与数据完整性。
- [x] Markdown 使用 Mermaid `pie` / `xychart`；完整统计保留表格，Top N 只限制图表可读性。
- [x] `generate_report(...)` 支持直接指定处理后的 Excel；`run_all(report_excel_path=...)` 也可显式覆盖报告输入。
- [x] Markdown 是唯一正文模板，Word 读取最终 Markdown，不维护第二套正文。
- [x] Word 支持本报告需要的标题、段落、列表、表格和 Mermaid 图；未知 Mermaid 类型明确失败。
- [x] 报告只读输入 Excel，不写数据库、不调用 LLM、不改变上游事实。
- [x] 默认模板由 `platform.reporting` 维护，`generate_excel_report()` 不传 `template_path` 时使用共享默认模板；显式 `template_path=` 仍兼容。
- [x] `imports_test` 已移除私有 `REPORT_TEMPLATE_FILE` 和私有 `report_template.md`。
- [x] 共享默认模板已进入 Wheel 安装包。
- [x] 未新增 Migration、公共 HTTP Contract、第三方运行时服务或 Python 依赖升级。
- [x] PR 正式 CI 全部成功。
- [x] 合并后的 `main` 已重新取得新鲜验证证据。

# 范围与非目标

本 Change 实现：

- `backend/src/aima_ugc/platform/reporting/` 的共享默认模板、统计、Markdown、DOCX 与图表能力；
- `imports_test` 独立 `generate_report()` 及 `run_all()` 报告接线；
- 报告相关 Unit/回归测试；
- `imports_test` README、reporting README 和 Blueprint 13 同步。

本 Change 没有实现：

- 正式网页报告中心、Report Job、Artifact 权限/API 或数据库 Report Schema；
- Canonical、Analysis、标签 Taxonomy 或统一 Excel Contract 变更；
- 新的模型分析结论；
- 通用 Markdown/Mermaid 全语法引擎；
- 依赖升级或数据库 Migration。

# 必须保持不变与最终兼容结果

合并前后均确认以下 `main` 能力保留：

- `INPUT_XLSX_FILES` 单/多 Excel；
- `ExcelBatchConversionSummary` 与 `convert_excel_files_to_canonical_jsonl`；
- 多文件 Canonical 合并后的全局关键词过滤与稳定身份去重；
- `ingest_excel_files_run_to_postgres` 多源正式入库；
- `LLMRequestAuditWriter`；
- `load_llm_pricing` 与 `recalculate_llm_request_costs`；
- `recalculate_cost()`；
- `label_sentiment → export_labeled_excel`；
- `p1-run-summary.v2`；
- `WRITE_TO_DATABASE=False` 默认行为；
- 现有 Canonical、Analysis、数据库 Schema/Migration、HTTP Contract 与前端行为。

报告能力只在最终 Excel 之后增加派生步骤。

# 关键决策

1. 报告业务输入固定为统一 Excel，不反向读取或重新定义 Provider/Canonical/数据库。
2. 完整统计进 Markdown 表格，图表可做 Top N 视觉裁剪，但不丢完整数据。
3. Markdown 是唯一正文模板；Word 从最终 Markdown 生成。
4. 默认模板由 `platform.reporting` Owner 维护；`imports_test` 不拥有第二份模板。
5. `generate_excel_report()` 默认使用共享模板，显式 `template_path=` 保持兼容。
6. 不引入 Pandoc、python-docx、Matplotlib、pandas 或在线 Mermaid 服务；复用标准库 OOXML/ZIP/PNG 与既有 openpyxl。
7. Mermaid 只支持当前报告实际需要的 `pie` / `xychart` 子集；未知类型 fail closed。
8. DOCX 生成后校验 ZIP CRC、关键 XML 与媒体数量，并使用 LibreOffice Writer 做实际打开/渲染验证。
9. feature 分支开发过程中产生较多 Contents API 机械提交，正式 PR 使用 Squash merge，避免污染 `main` 历史。

# TDD 与实现过程证据

共享默认模板迁移新增测试：

```text
tests/unit/platform/test_reporting_default_template.py
```

Red：

```text
1 failed
原因：迁移前 aima_ugc.platform.reporting 不存在 DEFAULT_REPORT_TEMPLATE_PATH
```

Green 后直接相关门禁：

```text
Ruff: 通过
Mypy: 直接相关 6 个源文件通过
目标/回归测试: 19 passed
旧 imports_test/report_template.md 引用: 无残留
imports_test.REPORT_TEMPLATE_FILE: 无残留
```

# Feature 集成验证

最终 PR 前被测源码状态：

```text
abd5b71f9ae0929e5c7aafa41a036d61aec39548
```

GitHub Actions `ubuntu-24.04` / Python 3.14.7 / 仓库锁定 uv 环境结果：

```text
目标/回归测试: 19 passed in 4.26s
全量 Unit: 411 passed in 6.08s
Ruff format: 349 files already formatted
Ruff check: All checks passed
Mypy: 183 source files 无问题
Architecture: 通过
Table Owner: 通过
Docs: 通过
Secret scan: 通过
uv build --wheel: 成功
Wheel 安装: 成功
```

安装后共享模板实际存在于：

```text
site-packages/aima_ugc/platform/reporting/report_template.md
```

兼容检查明确验证：

```text
INPUT_XLSX_FILES
ExcelBatchConversionSummary
convert_excel_files_to_canonical_jsonl
ingest_excel_files_run_to_postgres
LLMRequestAuditWriter
load_llm_pricing
recalculate_llm_request_costs
label_sentiment
export_labeled_excel
generate_report
```

全部同时存在。

DOCX 实际验证：

```text
共享默认模板生成 report.md + report.docx
图表: 9
LibreOffice Writer 成功打开并转 PDF
PDF: 190773 bytes
```

# PR 正式 CI

PR #90 head：

```text
124762947fa82f236fab73d9af6c448fc0310a74
```

正式 PR 工作流全部成功：

```text
CI
Stage 1-7 Audit Correctness
Stage 5A Provider Raw
Stage 5B Collection Execution
Stage 5C Provider Persistence
Stage 5D Provider Dispatch
Stage 6 XHS Vertical Slice
Stage 7 Keyword Packs
Stage 7 Provider Config Routing
Stage 7 Plan Occurrence Run Snapshot
Stage 7 Scheduler Runtime
```

CI 内部 Stage 1、Stage 2 Platform、Stage 3A Database、Windows bootstrap 等 Job 也均成功。

# 合并后 main 验证

最终被测 `main`：

```text
46a077c26bab5981767003121934a7d45e8d8bf0
```

为取得连接器可读取的新鲜 post-merge 证据，从该 main SHA 建立只读验证分支；验证分支在被测 main 之上只增加临时 workflow，Ancestry 门禁确认没有混入生产代码变化。

结果：

```text
main ancestry: success
locked environment: success
目标/回归测试: 19 passed in 4.32s
Ruff format/check: success
Mypy: 183 source files 无问题
Architecture / Table Owner / Docs / Secret: success
全量 Unit: 411 passed in 6.29s
Wheel build/install + shared template: success
合并后 imports/LLM/数据库/报告能力共存: success
LibreOffice DOCX render: success
```

Wheel 中模板：

```text
/tmp/aima-postmerge-wheel/lib/python3.14/site-packages/aima_ugc/platform/reporting/report_template.md
```

Word：

```text
图表: 9
LibreOffice Writer 转 PDF: success
PDF: 190894 bytes
```

验证没有使用 Microsoft Word 实机，因此剩余风险仅包括 Microsoft Word 与 LibreOffice 在字体/分页上的细微视觉差异；DOCX 包结构、XML、媒体、实际打开与 PDF 渲染均已验证。

# 文档同步

已同步：

- `backend/src/aima_ugc/adapters/providers/imports_test/README.md`；
- `backend/src/aima_ugc/platform/reporting/README.md`；
- `docs/blueprint/13-统一数据Excel导出与调试复用.md`。

长期事实固定为：

```text
统一 Excel 数据契约/Exporter
≠
Report Renderer
```

默认报告模板由 `platform.reporting` 维护，`imports_test` 只是一个人工调用入口。

# 兼容、依赖、Migration、部署与回滚

- 公共 HTTP Contract：无变化；
- 数据库 Schema/Migration：无变化；
- Python/Node 依赖及锁文件：无变化；
- 部署方式：无变化；
- 数据迁移：不需要；
- 回滚：代码层可回退 PR #90 的 Squash merge；没有数据库或持久化格式回滚步骤；已生成的 Markdown/Word 是派生文件，可直接删除并重新生成。

# Git / PR / 合并状态

- 开发分支：`feature/offline-reporting`；
- PR：#90；
- PR 状态：已合并；
- 合并方式：Squash merge；
- main 合并提交：`46a077c26bab5981767003121934a7d45e8d8bf0`；
- post-merge 验证：成功；
- 发布/部署：未执行，本 Change 不包含部署；
- Change：满足归档门禁，归档为 `done`。
