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

在不改变 Canonical、Analysis、UnifiedDataExcelV1、数据库或 Excel 数据语义的前提下，为处理完成的统一 Excel 增加只读报告能力：

```text
统一 Excel
→ 统计
→ Markdown + Mermaid
→ Word
```

默认 `run_all()` 在最终 `labeled_data.xlsx` 后生成报告；已有处理后 Excel 也可单独传给 `generate_report(excel_path=...)`，不必重跑前序流程。

# 成功标准

- [x] `run_all()` 保留最新完整链路，并在 `export_labeled_excel` 后追加 `generate_report`。
- [x] `run_summary.json` 与 `P1RunSummary` 返回 `report_markdown` / `report_word` 路径。
- [x] 报告覆盖内容总量、评论总量、标签对总量、平台、情感、一级/二级标签、一级→二级标签对、关键词、日期范围、每日趋势与数据完整性。
- [x] Markdown 使用 Mermaid `pie` / `xychart`；完整统计保留表格，Top N 只限制图表可读性。
- [x] `generate_report(...)` 支持直接指定处理后的 Excel；`run_all(report_excel_path=...)` 也可显式覆盖报告输入。
- [x] Markdown 是唯一正文模板，Word 读取最终 Markdown，不维护第二套正文。
- [x] Word 支持本报告需要的标题、段落、列表、表格和 Mermaid 图；未知 Mermaid 类型明确失败。
- [x] 报告只读输入 Excel，不写数据库、不调用 LLM、不改变上游事实。
- [x] 未新增 Migration、公共 HTTP Contract、第三方运行时服务或 Python 依赖升级。
- [x] 已在最终稳定业务源码上取得目标测试、Ruff、Mypy、架构/Owner/文档/Secret、全量 unit 和 LibreOffice 渲染的新鲜证据。

# 范围

- `backend/src/aima_ugc/platform/reporting/`：Excel 统计、Markdown 渲染、Markdown→DOCX、图表 PNG、DOCX 校验；
- `imports_test/report_template.md`：当前人工入口唯一报告正文模板；
- `imports_test/test.py`：独立 `generate_report()` 与 `run_all()` 接线；
- 报告与 `run_all()` 回归测试；
- `imports_test` README、Report 模块 README、Blueprint 13。

# 非目标

- 不实现正式网页报告中心、Report Job、Artifact 权限/API 或数据库 Report Schema；
- 不改变统一 Excel、Canonical、Analysis 或标签 Taxonomy Contract；
- 不新增模型分析结论；
- 不实现通用 Markdown/Mermaid 全语法引擎；
- 不合并到 `main`。

# 必须保持不变

- 最新 `main` 的 `INPUT_XLSX_FILES` 单/多 Excel、全局过滤/去重和多文件数据库来源语义；
- LLM 请求费用审计、价格目录、复算能力和 `p1-run-summary.v2`；
- **`main@3a6ffbe759f0dfde2c67d8d4d97d336fe2571702` 已恢复 `run_all()` 的 `label_sentiment()` 与 `export_labeled_excel()` 自动阶段；**
- 共享 Excel Exporter 字段、Sheet、样式、安全与大文件行为；
- `WRITE_TO_DATABASE=False` 默认行为、当前锁定依赖与 Prompt Taxonomy 事实源。

# 关键决策

1. 报告唯一输入是实际存在的统一 Excel，避免重新解释 Provider/Canonical/数据库。
2. 完整数据进表格，图表可限制 Top N；不因视觉裁剪丢数据。
3. Markdown 是唯一正文模板；Word 由 `report.md` 转换。
4. 不引入 Pandoc、python-docx、Matplotlib、pandas 或在线 Mermaid 服务；使用标准库 OOXML/ZIP/PNG + 既有 openpyxl。
5. Mermaid 使用 `pie` / `xychart`，Word 转换只支持本模板使用的子集并 fail closed。
6. Change 期间 `main` 多次并发变化：先加入多 Excel/LLM 费用审计，再临时注释 AI/Excel，随后 `3a6ffbe...` 明确恢复完整打标流程；本 Change 每次都以最新机器事实为准，最终按 `3a6ffbe...` 保留完整链路并追加报告。
7. DOCX `w:br` 固定放在 `w:r` 内；生成后校验 ZIP CRC、关键 OOXML/XML 和图表媒体数。
8. `xml.etree.ElementTree.tostring(..., encoding="utf-8")` 的标准库类型存根返回值通过 `typing.cast(bytes, ...)` 明确给 mypy；不改变运行时字节序列化行为。

# 任务

- [x] 调查相关代码、Contract、Blueprint、README 和测试。
- [x] 建立 Red → Green 报告核心测试。
- [x] 实现报告统计、Markdown 模板、Mermaid、Word 和 DOCX 校验。
- [x] 接入 `generate_report()` 与 `run_all()`。
- [x] 融合多 Excel、费用审计和最新恢复的完整 `run_all()` 链路。
- [x] 同步相关 README/Blueprint。
- [x] 增加输入 Excel Hash、模板同步、未知 Mermaid、OOXML 换行和 `run_all()` 接线回归测试。
- [x] 更新既有 `run_all()` 隔离目录测试，使其覆盖最终 Excel 与报告仍使用同一个 run 目录。
- [x] `compare_commits(main, feature/offline-reporting)` 最终确认 merge-base 为 `3a6ffbe759f0dfde2c67d8d4d97d336fe2571702`，`behind_by=0`。
- [x] 执行最终验证门禁并记录机器证据。

# 验证

最终机器证据保存于：

```text
changes/active/CHG-20260820-offline-reporting/verification_evidence.json
```

被测业务源码状态：

```text
5ef2f292922d8a8777c93a62f7715a2522b85bab
```

验证环境：GitHub Actions `ubuntu-24.04` / Python 3.14.7 / 仓库锁定 uv 环境。

目标测试：

```bash
uv run pytest \
  tests/unit/platform/test_offline_reporting.py \
  tests/unit/platform/test_imports_test_reporting.py \
  tests/unit/platform/test_docx_package_structure.py \
  tests/unit/collection/test_p1g_imports_run_all.py \
  tests/unit/collection/test_imports_test_run_directory.py -q
```

结果：

```text
18 passed in 3.82s
```

静态与仓库门禁：

```bash
uv run ruff format --check backend tests scripts
uv run ruff check backend tests scripts
uv run mypy backend/src
uv run python scripts/quality/check_architecture.py
uv run python scripts/quality/check_table_ownership.py
uv run python scripts/quality/check_docs.py
uv run python scripts/quality/scan_secrets.py
```

结果：

```text
348 files already formatted
All checks passed!
Success: no issues found in 183 source files
Stage 1–7 架构骨架与硬边界检查通过
TABLE_OWNER_OK
文档入口与本地链接检查通过
源码、Provider 证据、Change 与文档 Secret 扫描通过
```

全量 unit：

```bash
uv run pytest tests/unit -q
```

结果：

```text
410 passed in 5.51s
```

DOCX 格式与渲染验证：

```text
报告生成器生成 report.md + report.docx
DOCX 内部校验 ZIP CRC、关键 OOXML/XML、图表媒体数量
样例 Word 包含 9 张图表
LibreOffice Writer headless 成功打开 DOCX 并转为 PDF
PDF 大小：191091 bytes
```

LibreOffice 输出存在 `javaldx` Java 警告，但 Writer 转换成功且生成了非空 PDF；本功能不依赖 Java。未使用 Microsoft Word 实机交叉验证，因此剩余风险仅是不同 Office 渲染器的细微版式差异，不影响 DOCX 包结构和已验证内容完整性。

# 文档影响

- `imports_test/README.md`：报告目录、统计口径、独立生成、模板与 Word 使用；
- `platform/reporting/README.md`：生产入口、输入输出、统计、测试和限制；
- Blueprint 13：数据明细 Excel 与只读 Report Renderer 的长期边界。

本次不修改 Contract/Migration/依赖版本。

# 交付

- 最新融合基线：`main@3a6ffbe759f0dfde2c67d8d4d97d336fe2571702`；最终比较确认 `behind_by=0`。
- 分支：`feature/offline-reporting`。
- Change：`ready_for_review`，继续保留在 `changes/active/`，未归档。
- PR：未创建。
- 合并：未执行；用户明确要求本轮不要合并 `main`。
- 发布/部署：未执行。
