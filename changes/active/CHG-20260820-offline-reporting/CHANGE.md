---
schema: rvc-change/v1
id: CHG-20260820-offline-reporting
title: 离线数据报告与 Markdown Word 导出
level: L2
status: ready_for_review
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

# 成功标准

- [x] `run_all()` 保留最新完整链路，并在 `export_labeled_excel` 后追加 `generate_report`。
- [x] `run_summary.json` 与 `P1RunSummary` 返回 `report_markdown` / `report_word` 路径。
- [x] 报告覆盖内容总量、评论总量、标签对总量、平台、情感、一级/二级标签、一级→二级标签对、关键词、日期范围、每日趋势与数据完整性。
- [x] Markdown 使用 Mermaid `pie` / `xychart`；完整统计保留表格，Top N 只限制图表可读性。
- [x] `generate_report(...)` 支持直接指定处理后的 Excel；`run_all(report_excel_path=...)` 也可显式覆盖报告输入。
- [x] Markdown 是唯一正文模板，Word 读取最终 Markdown，不维护第二套正文。
- [x] Word 支持本报告需要的标题、段落、列表、表格和 Mermaid 图；未知 Mermaid 类型明确失败。
- [x] 报告只读输入 Excel，不写数据库、不调用 LLM、不改变上游事实。
- [x] 默认模板由 `platform.reporting` 维护，`generate_excel_report()` 不传 `template_path` 时使用共享默认模板；显式 `template_path=` 仍兼容。
- [x] `imports_test` 已移除私有 `REPORT_TEMPLATE_FILE` 和私有 `report_template.md`。
- [x] 未新增 Migration、公共 HTTP Contract、第三方运行时服务或 Python 依赖升级。
- [x] 已在当前 `main` 基线之上的稳定 feature 源码取得完整门禁、Wheel/模板打包、既有 main 能力保留与 LibreOffice 渲染的新鲜证据。
- [ ] PR/正式 CI/Review、合并及合并后验证尚未完成。

# 范围

- `backend/src/aima_ugc/platform/reporting/`：共享默认模板、Excel 统计、Markdown 渲染、Markdown→DOCX、图表 PNG、DOCX 校验；
- `imports_test/test.py`：独立 `generate_report()` 与 `run_all()` 接线，只消费共享 Report Renderer；
- 报告与 `run_all()` 回归测试；
- `imports_test` README、Report 模块 README、Blueprint 13；
- 当前 `main` 与本 Change 的兼容集成、PR/合并及合并后验证。

# 非目标

- 不实现正式网页报告中心、Report Job、Artifact 权限/API 或数据库 Report Schema；
- 不改变统一 Excel、Canonical、Analysis 或标签 Taxonomy Contract；
- 不新增模型分析结论；
- 不实现通用 Markdown/Mermaid 全语法引擎；
- 不通过覆盖旧 feature 历史、强制推送或裁剪 `main` 已有能力来完成集成。

# 必须保持不变

- 当前 `main` 的 `INPUT_XLSX_FILES` 单/多 Excel、全局过滤/去重和多文件数据库来源语义；
- LLM 请求费用审计、价格目录、费用复算和 `p1-run-summary.v2`；
- `run_all()` 的 `label_sentiment()` 与 `export_labeled_excel()` 自动阶段；
- 共享 Excel Exporter 字段、Sheet、样式、安全与大文件行为；
- `WRITE_TO_DATABASE=False` 默认行为、当前锁定依赖与 Prompt Taxonomy 事实源；
- 现有 Canonical、Analysis、数据库 Schema/Migration、HTTP Contract 与前端均不因报告能力发生变化。

# 当前主分支事实

本轮重新读取 GitHub 后确认：

```text
main = 3a6ffbe759f0dfde2c67d8d4d97d336fe2571702
```

该 `main` 已包含此前并行开发形成的：

```text
单/多 Excel INPUT_XLSX_FILES
→ 合并 Canonical
→ 全局过滤/去重
→ 可选多源 PostgreSQL 入库
→ LLM 请求审计/费用计算与复算
→ label_sentiment
→ export_labeled_excel
```

`feature/offline-reporting` 的 merge-base 是上述 `main`，最新比较为 `behind_by=0`。因此本 Change 不是用旧实现覆盖主分支，而是在同一机器基线上追加报告能力。

# 关键决策

1. 报告唯一业务输入是实际存在的统一 Excel，避免重新解释 Provider/Canonical/数据库。
2. 完整数据进表格，图表可限制 Top N；不因视觉裁剪丢数据。
3. Markdown 是唯一正文模板；Word 由 `report.md` 转换。
4. 不引入 Pandoc、python-docx、Matplotlib、pandas 或在线 Mermaid 服务；使用标准库 OOXML/ZIP/PNG + 既有 openpyxl。
5. Mermaid 使用 `pie` / `xychart`，Word 转换只支持本模板使用的子集并 fail closed。
6. 多 Excel、LLM 费用审计、多文件数据库来源和恢复后的完整 `run_all()` 是主分支既有能力，报告集成不得回退这些行为。
7. DOCX `w:br` 固定放在 `w:r` 内；生成后校验 ZIP CRC、关键 OOXML/XML 和图表媒体数。
8. `xml.etree.ElementTree.tostring(..., encoding="utf-8")` 的标准库类型存根返回值通过 `typing.cast(bytes, ...)` 明确给 mypy；不改变运行时字节序列化行为。
9. 默认 Markdown 模板归 `platform.reporting` 所有；`generate_excel_report()` 默认读取模块内模板，调用方仍可显式传入 `template_path=` 覆盖，保持已有公共调用兼容。
10. 用户已明确授权本轮完成后合并到 `main`；仍按仓库 PR/CI/Review/合并后验证门禁执行，不绕过任何检查。

# 任务

- [x] 调查相关代码、Contract、Blueprint、README 和测试。
- [x] 建立 Red → Green 报告核心测试。
- [x] 实现报告统计、Markdown、Mermaid、Word 和 DOCX 校验。
- [x] 接入 `generate_report()` 与 `run_all()`。
- [x] 融合多 Excel、费用审计和恢复后的完整 `run_all()` 链路。
- [x] 同步相关 README/Blueprint。
- [x] 增加输入 Excel Hash、模板同步、未知 Mermaid、OOXML 换行和 `run_all()` 接线回归测试。
- [x] 更新既有 `run_all()` 隔离目录测试，使其覆盖最终 Excel 与报告仍使用同一个 run 目录。
- [x] 新增共享默认模板 Red 测试，并确认因缺少 `DEFAULT_REPORT_TEMPLATE_PATH` 正确失败：`1 failed`。
- [x] 把默认模板迁移到 `platform/reporting/report_template.md`，移除 `imports_test` 私有模板和模板常量。
- [x] 迁移后的相关 Ruff/Mypy 与目标测试通过：`19 passed`。
- [x] 清理模板迁移和最终验证专用临时 workflow/脚本/诊断文件。
- [x] 基于当前 `main` 基线执行完整目标测试、全量 Unit、Ruff、Mypy、架构/Owner/文档/Secret、Wheel/模板打包、最新 main 能力保留和 DOCX 实际渲染验证。
- [ ] 创建 PR、确认正式 CI/Review、按授权合并到 `main`。
- [ ] 在合并后的 `main` 再次核对报告默认模板、既有 imports/LLM 功能与正式 CI；成功后归档 Change。

# 验证

最终 feature 机器证据保存于：

```text
changes/active/CHG-20260820-offline-reporting/verification_evidence.json
```

被测源码状态：

```text
abd5b71f9ae0929e5c7aafa41a036d61aec39548
```

验证环境：GitHub Actions `ubuntu-24.04` / Python 3.14.7 / 仓库锁定 uv 环境。

## 共享默认模板 Red

```text
tests/unit/platform/test_reporting_default_template.py
1 failed
原因：迁移前 aima_ugc.platform.reporting 无 DEFAULT_REPORT_TEMPLATE_PATH
```

该失败由目标行为尚未实现导致，随后进入 Green。

## 最终 feature 验证

目标与回归测试：

```text
19 passed in 4.26s
```

全量 Unit：

```text
411 passed in 6.08s
```

静态与仓库门禁：

```text
349 files already formatted
Ruff: All checks passed
Mypy: 183 source files 无问题
Architecture: 通过
Table Owner: 通过
Docs: 通过
Secret scan: 通过
```

Wheel 与模板：

```text
uv build --wheel 成功
Wheel 安装成功
安装后的共享模板实际存在于：
site-packages/aima_ugc/platform/reporting/report_template.md
模板包含 OVERVIEW_TABLE / PLATFORM_PIE_CHART 等关键占位符
```

既有 `main` 能力保留检查：

```text
imports_test 中仍存在：
INPUT_XLSX_FILES
ExcelBatchConversionSummary / convert_excel_files_to_canonical_jsonl
多源 ingest_excel_files_run_to_postgres
LLMRequestAuditWriter / load_llm_pricing / recalculate_llm_request_costs
label_sentiment → export_labeled_excel
以及新增 generate_report
```

结果：`imports_test 最新 main 能力与报告接线并存检查通过`。

DOCX 实际渲染：

```text
共享默认模板生成 report.md + report.docx
Word 内嵌图表：9
LibreOffice Writer headless 成功打开并转 PDF
PDF：190773 bytes
```

LibreOffice 输出仍有 `javaldx` Java 警告，但 Writer 转换成功且生成非空 PDF；生产报告生成不依赖 Java。未使用 Microsoft Word 实机交叉验证，剩余风险是不同 Office 渲染器可能存在细微分页/字体差异。

测试 SHA 之后只有验证证据提交、临时验证 workflow 删除和本文状态更新；生产代码与测试逻辑未再变化。

# 文档影响

- `imports_test/README.md`：报告目录、统计口径、独立生成，以及共享模板位置；
- `platform/reporting/README.md`：默认模板事实源、生产入口、输入输出、统计、测试和限制；
- Blueprint 13：统一 Excel 与 Provider-neutral Report Renderer 的长期边界和共享默认模板 Owner。

本次不修改 Contract/Migration/依赖版本。

# 交付

- 基线：`main@3a6ffbe759f0dfde2c67d8d4d97d336fe2571702`。
- 分支：`feature/offline-reporting`。
- Change：`ready_for_review`。
- PR：待创建。
- 合并：用户已授权；仅在正式 PR CI/Review 满足仓库门禁后执行。
- 发布/部署：不在本次范围。
