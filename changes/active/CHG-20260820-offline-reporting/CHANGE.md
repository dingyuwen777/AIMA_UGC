---
schema: rvc-change/v1
id: CHG-20260820-offline-reporting
title: 离线数据报告与 Markdown Word 导出
level: L2
status: in_progress
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
- [ ] 在最新 `main` 基线上重新取得完整门禁证据、PR/合并状态与合并后验证。

# 范围

- `backend/src/aima_ugc/platform/reporting/`：共享默认模板、Excel 统计、Markdown 渲染、Markdown→DOCX、图表 PNG、DOCX 校验；
- `imports_test/test.py`：独立 `generate_report()` 与 `run_all()` 接线，只消费共享 Report Renderer；
- 报告与 `run_all()` 回归测试；
- `imports_test` README、Report 模块 README、Blueprint 13；
- 最新 `main` 与本 Change 的兼容集成、PR/合并及合并后验证。

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

当前 `feature/offline-reporting` 的 merge-base 就是上述 `main`，此前比较为 `behind_by=0`。因此本 Change 不是把旧实现覆盖到新主分支，而是在同一最新机器基线上追加报告能力。

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
10. 用户已明确授权本轮完成后推送到 `main`；仍按仓库 Git/PR/CI 门禁执行，不绕过验证。

# 任务

- [x] 调查相关代码、Contract、Blueprint、README 和测试。
- [x] 建立 Red → Green 报告核心测试。
- [x] 实现报告统计、Markdown、Mermaid、Word 和 DOCX 校验。
- [x] 接入 `generate_report()` 与 `run_all()`。
- [x] 融合多 Excel、费用审计和恢复后的完整 `run_all()` 链路。
- [x] 同步相关 README/Blueprint。
- [x] 增加输入 Excel Hash、模板同步、未知 Mermaid、OOXML 换行和 `run_all()` 接线回归测试。
- [x] 更新既有 `run_all()` 隔离目录测试，使其覆盖最终 Excel 与报告仍使用同一个 run 目录。
- [x] 新增共享默认模板 Red 测试，并确认当前实现因缺少 `DEFAULT_REPORT_TEMPLATE_PATH` 正确失败：`1 failed`。
- [x] 把默认模板迁移到 `platform/reporting/report_template.md`，移除 `imports_test` 私有模板和模板常量。
- [x] 迁移后的相关 Ruff/Mypy 与目标测试通过：`19 passed`。
- [ ] 清理迁移专用临时 workflow/脚本/诊断文件。
- [ ] 基于最新 `main` 执行完整目标测试、全量 Unit、Ruff、Mypy、架构/Owner/文档/Secret、Wheel/模板打包和 DOCX 实际渲染验证。
- [ ] 创建 PR、确认 CI/Review、按授权合并到 `main`。
- [ ] 在合并后的 `main` 再次验证报告默认模板、既有 imports/LLM 功能和仓库门禁，完成后归档 Change。

# 验证

## 上一版报告能力完整证据

上一版默认模板仍位于 `imports_test` 时，业务源码状态 `5ef2f292922d8a8777c93a62f7715a2522b85bab` 已通过：

```text
目标测试：18 passed
全量 unit：410 passed
Ruff format/check：通过
Mypy：183 source files 无问题
Architecture / Table Owner / Docs / Secret：通过
DOCX：9 张图表，LibreOffice Writer 成功转 PDF
```

该证据只证明上一版实现，不替代模板迁移后的最终验证。

## 共享默认模板 Red → Green

Red 证据：

```text
测试：tests/unit/platform/test_reporting_default_template.py
结果：1 failed
原因：aima_ugc.platform.reporting 尚无 DEFAULT_REPORT_TEMPLATE_PATH
```

Green/迁移目标验证：

```text
Ruff：通过
Mypy：6 个直接相关源文件无问题
目标/回归测试：19 passed
旧 imports_test/report_template.md 引用扫描：无残留
imports_test.REPORT_TEMPLATE_FILE 扫描：无残留
```

该迁移验证由临时 runner 完成；迁移专用 runner 文件在最终集成前必须清理。

## 最终计划

最终 feature/PR 必须重新运行：

```bash
uv lock --check
uv sync --locked
uv run ruff format --check backend tests scripts
uv run ruff check backend tests scripts
uv run mypy backend/src
uv run pytest tests/unit -q
uv run python scripts/quality/check_architecture.py
uv run python scripts/quality/check_table_ownership.py
uv run python scripts/quality/check_docs.py
uv run python scripts/quality/scan_secrets.py
uv build --wheel
```

并额外验证：

```text
DEFAULT_REPORT_TEMPLATE_PATH 指向 platform/reporting/report_template.md
共享模板进入 Wheel/安装包
report.md / report.docx 生成
DOCX ZIP/XML/媒体校验
LibreOffice Writer 打开并转 PDF
最新 main 的多 Excel、LLM 费用审计、数据库来源和 run_all 阶段顺序未被裁剪
```

# 文档影响

- `imports_test/README.md`：报告目录、统计口径、独立生成，以及共享模板位置；
- `platform/reporting/README.md`：默认模板事实源、生产入口、输入输出、统计、测试和限制；
- Blueprint 13：统一 Excel 与 Provider-neutral Report Renderer 的长期边界和共享默认模板 Owner。

本次不修改 Contract/Migration/依赖版本。

# 交付

- 基线：当前 `main@3a6ffbe759f0dfde2c67d8d4d97d336fe2571702`。
- 分支：`feature/offline-reporting`。
- Change：模板迁移与主分支集成期间为 `in_progress`。
- PR：待最终 feature 验证后创建。
- 合并：用户已授权；仅在 PR/CI/验证满足仓库门禁后执行。
- 发布/部署：不在本次范围。
