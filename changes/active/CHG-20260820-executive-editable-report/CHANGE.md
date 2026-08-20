---
schema: rvc-change/v1
id: CHG-20260820-executive-editable-report
title: 管理层舆情报告与可编辑Word图表
level: L2
status: ready_for_review
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

1. 默认报告正文不再出现“模板、Excel、Sheet、Markdown、Word 转换器、Canonical、Exporter”等实现说明；统计口径只在必要的末尾说明中用业务语言表达。
2. 报告先给管理摘要和风险关注，再展示平台、情感、主题、关键词与趋势；已有完整统计不丢失。
3. 新增可直接用于管理判断的派生信息：声量峰值、主要平台、情感结构、平台×情感对比、负面平台/主题、主要一级/二级主题、热门关键词。
4. Markdown 仍是报告正文唯一维护来源；模板章节/文字修改继续自动进入 Word。
5. Word 中 pie/bar/line 图表使用 Office 原生 Chart，内嵌可编辑数据工作簿；用户可在支持 Office Chart 的 Word 中编辑图表数据，不再把这些图表作为 PNG 图片写入 DOCX。
6. `generate_excel_report()` 公共入口、报告输入 Workbook 最低字段要求、`imports_test` 接线和现有 Markdown Mermaid 子集保持兼容。
7. 不新增第三方依赖，不修改数据库、HTTP Contract、Migration 或前端。

# 已实现

## 管理层默认报告

默认 `report_template.md` 现在按以下顺序组织：

```text
管理摘要
→ 核心指标 / 每日声量
→ 舆情风险关注
→ 平台声量与情感结构
→ 整体情感表现
→ 核心议题分析
→ 热点关键词
→ 完整统计明细
→ 数据质量说明
```

管理摘要和风险摘要全部由既有结构化统计确定性计算，不调用 LLM，也不制造原数据中不存在的事实。

新增统计包括：

- 内容/评论声量、覆盖平台、声量峰值；
- 主要平台、首要一级/二级议题、热点关键词；
- 平台 × 情感交叉表与多系列图；
- 负面内容平台分布；
- 负面一级/二级议题分布；
- 原有平台、情感、一级/二级、标签对、关键词和每日非零明细全部保留。

## Word 可编辑图表

Markdown 继续使用本报告支持的 `pie` / `xychart` Mermaid 子集；xychart 通过受控 `%% series [...]` 注释携带业务系列名称，不影响 Markdown 展示。

Word 转换改为：

```text
ChartSpec
→ Office 原生 Chart XML
→ word/charts/chartN.xml
→ word/charts/_rels/chartN.xml.rels
→ word/embeddings/chartN.xlsx
```

每张图都有可打开的内嵌 XLSX 数据，DOCX 不再为这些报告图表生成 `word/media/chart-*.png`。Word 正文仍完全来自最终 `report.md`，没有第二套正文模板。

# 范围

- 重写 `platform/reporting/report_template.md` 的管理层展示结构和措辞；
- 扩展 `excel_report.py` 的管理摘要、平台情感交叉统计与负面风险统计；
- 增加 `chart_spec.py` 作为 Markdown/Word 图表的最小中间结构；
- 扩展 Markdown→DOCX 转换与 OOXML package，生成可编辑 Word Chart + 内嵌 XLSX；
- 更新 reporting README、Blueprint 13 和直接相关测试。

# 非目标

- 不使用 LLM 生成新的业务判断；
- 不改变标签 Taxonomy 或 Analysis Contract；
- 不新增正式数据库 Report Source/Report Job/API/Web 页面；
- 不修改 Excel Exporter 或 `imports_test` 默认内容列；
- 不做通用 Markdown/Office 图表引擎，只支持本报告现有 pie/bar/line 子集；
- 本轮未宣称 Microsoft Word 桌面版所有版本的像素级渲染一致；Office/LibreOffice 主题、字体和分页允许有轻微差异。

# 必须保持不变

- 报告只读输入，不修改源 Workbook；
- 完整平台、标签、关键词和每日明细继续保留；Top N 只限制图表，不裁剪完整数据表；
- 未支持 Mermaid 类型继续 fail closed；
- DOCX 生成后继续做 ZIP/XML/包结构校验；
- 不引入新的运行时外部服务。

# TDD 证据

## Red

先增加两个验收行为测试，再修改生产实现。有效 Red 实际观察为：

```text
2 failed, 39 passed
```

失败原因分别为：

1. 默认报告仍以 `# AIMA_UGC 舆情数据分析报告` 开头并包含技术口吻，未达到管理层可直接展示要求；
2. Mermaid xychart 解析器不支持 `%% series [...]` 系列元数据，Word 仍沿用静态 PNG 图表路径。

第一次尝试曾先被测试文件 Ruff 格式门禁拦截；该次不作为行为 Red，修正测试格式后才取得上述有效 Red。

## Green / 回归

在最终实现上，PR #94 的正式 CI head `a994ed1ae0096af761911b44a0e33f5cfabc666d` 已实际通过：

```text
CI                                   success
Stage 1-7 Audit Correctness          success
Stage 6 XHS Vertical Slice           success
Stage 7 Keyword Packs                success
Stage 7 Provider Config Routing      success
Stage 7 Plan Occurrence Run Snapshot success
Stage 7 Scheduler Runtime            success
```

CI 内部：

```text
Stage 1            success
Stage 2 Platform   success
Stage 3A Database  success
Windows bootstrap  success
```

Stage 1 的 `Backend and repository checks`、Wheel build、Frontend checks 均成功；Stage 2 的 Platform unit/PostgreSQL integration tests 与 readiness smoke 均成功。

直接回归测试证明：

- 默认生成报告以“爱玛品牌舆情分析报告”开头，包含管理摘要、风险、平台×情感、负面内容、声量峰值等业务内容，且不包含指定实现术语；
- 输入 XLSX Hash 在报告前后不变；
- 自定义 Markdown 文本仍同时进入 Markdown 和 Word；
- DOCX 包包含 `word/charts/chartN.xml`、Chart Relationship 与 `word/embeddings/chartN.xlsx`；
- 测试会重新用 openpyxl 打开内嵌 XLSX 并校验系列名称、分类与数值；
- Word 文档 XML 使用 `c:chart`，且不再出现旧 `word/media/chart-*` 报告图表；
- 未支持 Mermaid 类型继续关闭失败；
- 原有 `imports_test`/多 Excel/数据库来源/LLM 费用审计接线未改变。

# 文档同步

已同步：

- `backend/src/aima_ugc/platform/reporting/README.md`：管理层默认报告、统计范围、Markdown 唯一正文源、可编辑 Office Chart + 内嵌 XLSX；
- `docs/blueprint/13-统一数据Excel导出与调试复用.md`：默认管理层视图、确定性摘要、Word 原生可编辑图表、包结构与验证门禁。

# 兼容 / Migration / 部署 / 回滚

- 公共 API：无变化；
- 数据库/Migration：无变化；
- HTTP Contract/前端：无变化；
- 依赖：无新增或升级，内嵌图表数据复用现有 openpyxl；
- 部署：无独立部署步骤；
- 回滚：回退本 Change 的 reporting/template/test/docs 变更即可，数据库无回滚动作。

# Git / 交付

- 分支：`feature/executive-editable-report`
- PR：#94（Draft，待最终 Review 后转 Ready）
- Change：`ready_for_review`
- 合并：未执行
