---
schema: rvc-change/v1
id: CHG-20260820-executive-editable-report
title: 管理层舆情报告与可编辑Word图表
level: L2
status: in_progress
owner: dingyuwen777
branch: feature/executive-editable-report
created: 2026-08-20
updated: 2026-08-20
depends_on: []
affected_areas:
  - reporting
affected_paths:
  - backend/src/aima_ugc/platform/reporting
  - tests/unit/platform
  - docs/blueprint/13-统一数据Excel导出与调试复用.md
contracts: []
data_changes: []
---

# 目标

把当前偏技术说明的离线舆情报告改成营销管理层可直接阅读和展示的报告，同时把 Word 中由 Mermaid 转换得到的静态 PNG 图表升级为可编辑 Office 原生图表。

# 成功标准

1. 默认报告正文不再出现“模板、Excel、Sheet、Markdown、Word 转换器、Canonical、Exporter”等实现说明；技术统计口径只在必要的附录中用业务语言说明。
2. 报告先给管理摘要，再展示平台、情感、主题、风险、关键词与趋势；已有完整统计不丢失。
3. 新增可直接用于管理判断的派生信息：声量峰值、主要平台、情感结构、平台×情感对比、负面平台/主题、主要一级/二级主题、热门关键词。
4. Markdown 仍是报告正文唯一维护来源；模板章节/文字修改继续自动进入 Word。
5. Word 中 pie/bar/line 图表使用 Office 原生 Chart，内嵌可编辑数据工作簿；用户可在 Office 中编辑图表数据，不再把这些图表作为 PNG 图片写入 DOCX。
6. `generate_excel_report()` 公共入口、报告输入 Workbook 最低字段要求、`imports_test` 接线和现有 Markdown Mermaid 子集保持兼容。
7. 不新增第三方依赖，不修改数据库、HTTP Contract、Migration 或前端。

# 范围

- 重写 `platform/reporting/report_template.md` 的管理层展示结构和措辞；
- 扩展 `excel_report.py` 的管理摘要、平台情感交叉统计与负面风险统计；
- 在 Mermaid 中携带不影响 Markdown 展示的系列名称元数据；
- 扩展 Markdown→DOCX 转换与 OOXML package，生成可编辑 Word Chart + 内嵌 XLSX；
- 更新 reporting README、Blueprint 13 和直接相关测试。

# 非目标

- 不使用 LLM 生成新的业务判断；所有摘要均由现有结构化统计确定性生成；
- 不改变标签 Taxonomy 或 Analysis Contract；
- 不新增正式数据库 Report Source/Report Job/API/Web 页面；
- 不修改 Excel Exporter 或 `imports_test` 默认内容列；
- 不做通用 Markdown/Office 图表引擎，只支持本报告现有 pie/bar/line 子集。

# 必须保持不变

- 报告只读输入，不修改源 Workbook；
- 完整平台、标签、关键词和每日明细继续保留；Top N 只限制图表，不裁剪完整数据表；
- 未支持 Mermaid 类型继续 fail closed；
- DOCX 生成后继续做 ZIP/XML/包结构校验；
- 不引入新的运行时外部服务。

# 实施步骤

1. Red：增加“管理层默认模板不得暴露实现术语”和“DOCX 图表必须为可编辑 Office Chart + embedded XLSX”的失败测试。
2. Green：补管理摘要/风险/平台情感交叉统计并重写默认模板。
3. Green：把 `ChartSpec`/DOCX Builder 改为原生 OOXML Chart，并用现有 openpyxl 生成内嵌数据工作簿。
4. Refactor：同步 README/Blueprint 13，清理仅为旧 PNG 图表路径保留的直接耦合。
5. 验证：目标测试、全部 reporting/imports 相关回归、Ruff、Mypy、Docs、Secret、Wheel；必要时用 LibreOffice/Office 兼容渲染验证 DOCX 可打开。

# 验证计划

- `uv run pytest tests/unit/platform/test_offline_reporting.py tests/unit/platform/test_docx_package_structure.py tests/unit/platform/test_reporting_default_template.py tests/unit/platform/test_imports_test_reporting.py tests/unit/collection/test_p1g_imports_run_all.py -q`
- `uv run ruff format --check backend/src/aima_ugc/platform/reporting tests/unit/platform`
- `uv run ruff check backend/src/aima_ugc/platform/reporting tests/unit/platform`
- `uv run mypy backend/src/aima_ugc/platform/reporting`
- `uv run python scripts/quality/check_docs.py`
- `uv run python scripts/quality/scan_secrets.py`
- `uv build --wheel`

# 文档影响

- `backend/src/aima_ugc/platform/reporting/README.md`：更新默认报告定位与可编辑图表说明。
- `docs/blueprint/13-统一数据Excel导出与调试复用.md`：把 Word 图表从 PNG 的当前事实更新为原生可编辑 Chart；保持 Markdown 唯一正文来源边界。

# Git / 交付

- 分支：`feature/executive-editable-report`
- PR：未创建
- 合并：未执行
