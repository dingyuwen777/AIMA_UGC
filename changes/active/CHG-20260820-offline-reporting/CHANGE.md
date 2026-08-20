---
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
  - docs/blueprint/13-统一数据Excel导出与调试复用.md
contracts: []
data_changes: []
---

# 离线数据报告与 Markdown Word 导出

## 目标

在不改变既有 Canonical、Analysis、UnifiedDataExcelV1、数据库或 Excel 数据处理结果的前提下，为处理完成的统一 Excel 增加可独立调用的报告生成能力：

```text
处理完成的 labeled_data.xlsx
→ 只读统计
→ Markdown 报告
→ Mermaid 图表
→ Word 文档
```

`imports_test.run_all()` 在最终 Excel 成功导出后调用同一报告实现；人工也可以直接指定任意符合当前统一 Excel 结构的 `.xlsx` 生成报告。

## 可观察成功标准

1. 每次 `imports_test.run_all()` 成功完成最终 Excel 后，同时生成 `reports/report.md` 与 `reports/report.docx`，并把路径写入运行摘要。
2. 报告至少完整展示内容总量、评论总量、标签对总量、各平台内容量/占比、情感分布、一级标签、二级标签、一级→二级标签对、关键词、日期范围与数据完整性。
3. 报告提供 Mermaid 图表：平台分布、情感分布、每日平台趋势、每日一级标签趋势、每日二级标签趋势及适合展示的 Top 标签/关键词图；完整数据仍以 Markdown 表格保留，不因图表 Top N 裁剪而丢失。
4. `generate_report(...)` 能绕过 `run_all()`，显式指定已处理 Excel 路径和输出目录独立运行。
5. Markdown 正文由可维护模板文件控制；修改模板普通文本后，下一次生成的 Markdown 与随后生成的 Word 都同步变化，不维护第二套 Word 正文模板。
6. Word 转换至少保留标题、段落、列表、表格以及本报告模板使用的 Mermaid `pie` / `xychart-beta` 图；不支持的 Mermaid 类型明确失败，不能静默丢图。
7. 报告生成只读输入 Excel；测试校验输入文件 Hash 在报告前后不变。
8. 不新增数据库 Migration、公共 HTTP Contract 或外部运行时服务，不升级现有依赖。

## 范围

- 新增 Provider-neutral 的 Excel 报告统计/Markdown 渲染能力；
- 新增 Markdown → DOCX 转换能力，并把本报告 Mermaid 图表转换为 Word 内嵌图；
- 新增 `imports_test` 报告模板、独立函数与 `run_all()` 接线；
- 补充对应单元测试、模块说明和 Blueprint 13 的 Report 边界说明；
- 校验生成 Markdown/DOCX 结构和 DOCX 可打开/可渲染性。

## 非目标

- 不实现 Stage 8B+ 正式网页报告中心、报告 Job、Artifact 权限/API 或数据库 Report Schema；
- 不改变现有统一 Excel 三 Sheet Contract、默认列、Canonical/Analysis Contract 或标签 Taxonomy；
- 不从模型生成管理层结论，不增加新的 LLM 调用；
- 不实现通用 Mermaid 全语法渲染器，仅支持本报告模板实际使用的图表子集；
- 不合并到 `main`。

## 必须保持不变

- `imports_test` 现有 convert → filter → deduplicate → 可选数据库 → label → Excel 的数据处理语义；
- `UnifiedDataExcelV1` 和共享 `platform/export/excel.py` 的当前字段、Sheet、样式、安全及导出行为；
- `WRITE_TO_DATABASE=False` 默认 file-only 行为；
- 现有 Python/uv 依赖版本与锁文件；
- Prompt Markdown 是具体标签体系唯一事实源，报告只消费已经写入 Excel 的分析结果。

## 已确认关键决策

1. **报告以最终统一 Excel 为唯一输入。** 这是只读派生层，避免再次解释 Provider JSON、Canonical 或数据库，并天然支持用户指定处理后的 Excel 路径。
2. **完整统计与图表分层。** Markdown 表格保存全部平台/标签/每日非零明细；折线/柱状图只选择 Top N 序列控制可读性，并明确图表口径。
3. **模板只维护 Markdown。** Python 只填充数据占位符；Word 转换读取生成后的 Markdown，不复制报告正文。
4. **不新增外部文档依赖。** 当前锁定依赖没有 Pandoc/python-docx/Matplotlib；本次使用标准库 OOXML/ZIP/PNG 实现所需 Word 子集，避免为离线报告引入新的系统安装或依赖升级。
5. **Mermaid 支持 fail closed。** Word 转换支持模板中的 `pie` 和 `xychart-beta`；模板若引入其他 Mermaid 类型，转换明确报错，避免 Word 悄悄缺少图表。

## 实施任务

### 1. 报告统计与 Markdown 渲染

→ 修改范围：`backend/src/aima_ugc/platform/reporting/`、`tests/unit/platform/`
→ 预期结果：只读统一 Excel，形成完整统计并按 Markdown 模板输出表格和 Mermaid 图表。
→ 验证方式：目标单元测试；输入 Excel SHA-256 前后相同；Markdown 关键统计、完整明细和 Mermaid 块断言。

### 2. Markdown 转 Word

→ 修改范围：`backend/src/aima_ugc/platform/reporting/`、`tests/unit/platform/`
→ 预期结果：生成有效 DOCX ZIP/OOXML，标题、表格和图表均存在；模板文字同步进入 Word。
→ 验证方式：单元测试重新打开 ZIP/XML；生成样例 DOCX 后使用仓库外可用的 LibreOffice/render_docx 做可打开性与视觉检查。

### 3. `imports_test` 接线与人工入口

→ 修改范围：`backend/src/aima_ugc/adapters/providers/imports_test/test.py`、`report_template.md`
→ 预期结果：`generate_report(...)` 支持指定 Excel；`run_all()` 最终 Excel 后调用并在 summary 中返回/记录 Markdown 和 Word 路径。
→ 验证方式：针对 helper 与 run_all hook 的单元测试；不触发真实 LLM/数据库。

### 4. 文档同步与复核

→ 修改范围：`backend/src/aima_ugc/adapters/providers/imports_test/README.md`、`docs/blueprint/13-统一数据Excel导出与调试复用.md`、必要测试说明
→ 预期结果：目录结构、调用方式、统计口径、模板维护、Mermaid/Word 支持范围和非目标与代码一致。
→ 验证方式：文档入口检查、两阶段 Review、相关质量门禁。

## 验证计划与本轮新鲜证据

待实施后记录实际命令、退出码、通过/失败数量和生成文件检查结果。未经实际运行不提前填写“通过”。

## 文档影响

- `imports_test/README.md`：增加报告目录、独立生成、模板与 Word 使用说明；
- Blueprint 13：在既有“Excel 与 Report Renderer 独立”边界下补充当前离线 Report Renderer 的实际输入输出和复用边界；
- 其他 Blueprint、Contract、Migration 如未改变不制造无关差异。

## Git / PR / 发布状态

- 分支：`feature/offline-reporting`
- Commit：进行中；提交信息使用中文。
- PR：未创建；用户只要求修改且明确暂不合并到 `main`。
- 合并：未执行，且本 Change 不允许在本轮自动合并。
- 发布/部署：不适用。
