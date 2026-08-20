---
schema: rvc-change/v1
id: CHG-20260820-executive-editable-report
title: 管理层舆情报告与可编辑Word图表
level: L2
status: done
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

把偏技术说明的离线舆情报告改成营销管理层可直接阅读和展示的报告，同时把 Word 中由 Mermaid 转换得到的静态 PNG 图表升级为可编辑 Office 原生图表。

# 已完成结果

## 管理层默认报告

默认 `report_template.md` 已改为：

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

最终业务正文不再展示 Excel/Sheet/Markdown/Word/模板/Canonical/Exporter 等实现说明。管理摘要和风险摘要全部由既有结构化统计确定性计算，不新增 LLM 请求。

新增并保留的主要分析视图：

- 内容/评论声量、覆盖平台、声量峰值；
- 主要平台、首要一级/二级议题、热点关键词；
- 平台 × 情感交叉表与多系列图；
- 负面内容平台分布；
- 负面一级/二级议题分布；
- 原有平台、情感、一级/二级、标签对、关键词和每日非零明细继续完整保留。

## Markdown 与 Word

Markdown 仍是报告正文唯一维护来源：

```text
report_template.md
→ 填充统计
→ report.md
→ report.docx
```

因此正文标题、章节和普通文字只修改 Markdown 模板即可，Word 不维护第二套正文。

## 可编辑 Word 图表

Word 报告图表已从静态 PNG 改为：

```text
ChartSpec
→ Office 原生 Chart XML
→ word/charts/chartN.xml
→ word/charts/_rels/chartN.xml.rels
→ word/embeddings/chartN.xlsx
```

Markdown 继续使用本报告支持的 Mermaid `pie` / `xychart` 子集；xychart 用受控注释保留系列名称。每张 Word 图表包含可打开的内嵌 XLSX 数据，支持 Office Chart 编辑的软件可通过“编辑数据”修改分类、系列和数值，并可继续调整标题、图例、样式和布局。

本轮没有新增 Word 正文模板，也没有为了 Word 再计算第二套统计。

# 兼容边界

保持不变：

- `generate_excel_report()` 公共入口；
- 报告输入 Workbook 最低字段要求；
- `imports_test` 接线和 `run_all()` 既有顺序；
- 报告只读输入，不修改源 Workbook；
- Top N 只限制图表，不裁剪完整数据表；
- 未支持 Mermaid 类型继续 fail closed；
- 数据库、Migration、HTTP Contract、前端均未变化；
- 未新增或升级第三方依赖，内嵌 XLSX 复用仓库已有 openpyxl。

# TDD 与验证证据

## Red

先增加验收测试，再修改生产实现。有效行为 Red：

```text
2 failed, 39 passed
```

失败原因：

1. 旧默认报告仍以技术口吻呈现，未达到管理层直接展示要求；
2. 旧 Mermaid/Word 路径不支持系列名称元数据，图表仍走静态 PNG 路径。

第一次尝试曾先被测试文件 Ruff 格式检查阻断，该次没有冒充行为 Red；修正测试格式后才取得上述有效 Red。

## Green / 正式 CI

PR #94 最终 head：

```text
6c9f4e3c127f7ba701470248708f118721c95ee7
```

以下工作流全部成功：

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

验证覆盖：

- 默认报告领导展示口吻与实现术语门禁；
- 管理摘要、风险、平台 × 情感等统计；
- 输入 XLSX Hash 前后不变；
- 自定义 Markdown 文本同时进入 Markdown/Word；
- DOCX ZIP/关键 OOXML/Office Chart/Relationship 校验；
- 每张图内嵌 XLSX 可被 openpyxl 重新打开并校验系列名称、分类和数值；
- `c:chart` 原生图表引用存在；
- 旧 `word/media/chart-*` 报告图表不再生成；
- 未支持 Mermaid 类型继续失败关闭；
- Wheel、Mypy、Ruff、文档、Secret、前端和既有 PostgreSQL 门禁通过。

Microsoft Word 桌面版的不同版本可能存在主题颜色、字体或分页差异；本 Change 不声明所有桌面端版本像素级完全一致。数据包、原生 Chart 结构和可编辑数据已经由自动化测试验证。

# 文档同步

已同步：

- `backend/src/aima_ugc/platform/reporting/README.md`
- `docs/blueprint/13-统一数据Excel导出与调试复用.md`

Blueprint 13 已把旧“Word 图表转换为 PNG”更新为当前“Office 原生 Chart + 内嵌 XLSX”的机器事实，并固定默认管理层报告的长期边界。

# Git / 集成

- 功能 PR：#94 `升级管理层舆情报告与可编辑 Word 图表`
- 功能 PR 状态：Merged
- 合并方式：Squash
- 功能合并提交：`74ef9bd032f32a5c3bf09b23419a8c76486dd9d2`
- 合并后 `main` 已确认指向该提交，并已读取 `report_template.md` 确认新管理层模板存在。
- 本归档只关闭 Change 生命周期，不修改 Blueprint 或生产实现。

# Migration / 部署 / 回滚

- Migration：无；
- 数据库数据迁移：无；
- 部署：无额外运行时部署步骤；
- 回滚：回退功能合并提交即可恢复旧报告行为，数据库不需要回滚。
