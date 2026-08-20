---
schema: rvc-change/v1
id: CHG-20260820-analysis-persistence-report-source
title: Analysis持久化与报告数据源边界
level: L3
status: done
owner: dingyuwen777
branch: docs/analysis-persistence-report-source
created: 2026-08-20
updated: 2026-08-20
depends_on: []
affected_areas:
  - analysis
  - reporting
  - ingestion
affected_paths:
  - docs/blueprint/03-数据库与文件存储.md
  - docs/blueprint/13-统一数据Excel导出与调试复用.md
  - docs/blueprint/15-舆情AI打标与统一分析契约.md
  - docs/blueprint/17-Stage8数据入口统一入库与业务前端实施.md
contracts: []
data_changes:
  - planned-analysis-persistence
---

# 目标

把已经确认的长期架构决策固化到 Blueprint，并作为后续正式实现的设计门禁：

1. AI 打标成功且通过本地 Validator 后，正式数据库模式必须把 Analysis 作为独立派生业务事实写入 PostgreSQL；不能长期停留在“Excel 有标签、数据库只有 Content”。
2. Content 与 Analysis 分 Owner：Content Owner 保存平台/外部可观察事实，Analysis Owner 保存模型派生结果与标签对。
3. 离线单批报告继续读取本次处理完成的统一 Excel；正式系统报告、跨批次趋势和 Dashboard 读取 PostgreSQL Report Read Model。
4. 报告数据源必须显式选择，禁止根据 PostgreSQL 是否启动/可达自动切换 Excel 与数据库。
5. Excel/PostgreSQL 两种 Source 最终适配为同一个 Provider-neutral Report Dataset/Context，复用同一 Statistics/Renderer 和 `platform/reporting/report_template.md`。

# 用户确认与方案

用户确认：

```text
AI 打标完成的数据也必须进入数据库。

离线单批报告 → Excel
正式系统报告/跨批次趋势 → PostgreSQL Read Model

不能因为数据库启动了就让同一个离线命令静默换数据源。
```

## 方案 A：Content 入库，Analysis 长期只留 JSONL/Excel

不采用。它会造成数据库与 Excel 长期分叉，无法支撑正式页面、跨批次查询和系统级报告。

## 方案 B：Content/Analysis 分 Owner 持久化，报告源按场景显式选择

采用：

```text
ContentIngestionService
→ Content Owner PostgreSQL
→ stable content_id

Analysis Service
→ LLM
→ Runtime Taxonomy Validator
→ 合法 ContentLabelAnalysisV2
   ├→ JSONL / Excel
   └→ Analysis Owner PostgreSQL
```

离线批次报告使用 Excel 快照；正式系统报告使用 PostgreSQL Query Repository/Report Read Model；两种来源统一转换为 Report Dataset 后复用同一 Renderer。

## 方案 C：数据库可用就读数据库，否则读 Excel

禁止采用。同一命令会因环境状态产生不同数据范围，且数据库可能包含历史、TikHub 和其他 Batch，无法自然代表本次 run。

# 已固化设计

## Analysis 持久化硬规则

- AI 标签不进入 `contents` 表；
- PostgreSQL Analysis、JSONL、Excel 消费同一份 Validator 成功结构，不从 Excel 反向解析后再入库，也不因写库二次调用模型；
- Analysis 使用“结果父事实 + 标签对子事实”逻辑模型；正式表名、DDL、索引与 Migration 由后续独立 Analysis Persistence L3 Change 冻结；
- 相同 `content_id + input_hash + prompt_sha256 + taxonomy_sha256 + provider/model` identity 必须幂等；输入、Prompt/Taxonomy 或模型变化时形成新历史分析结果；
- Query 层提供确定性的 `current_analysis`；
- Analysis Result 与 Label Pairs 在同一短事务提交，外部 LLM HTTP 不放数据库事务；
- AI 失败不写猜测结果；Content 成功而 Analysis 持久化失败时必须暴露 partial/failed Analysis 阶段并允许幂等补写。

## 报告数据源硬规则

```text
离线/人工单批：
labeled_data.xlsx
→ Excel Report Source
→ Report Dataset
→ Statistics / Renderer
→ report.md / report.docx

正式系统：
PostgreSQL
→ Query Repository / Report Read Model
→ Report Dataset
→ Statistics / Renderer
→ report.md / report.docx / Web
```

- `imports_test` 本次 run 即使 `write_to_database=True`，离线报告仍读取本次 Excel 快照；
- 正式系统报告、跨 Batch、7/30/90 天趋势和 Dashboard 使用 PostgreSQL Read Model；
- Report Renderer 不直接 SQL；
- 两种来源复用同一 Provider-neutral Report Dataset、统计实现、Renderer 和共享 Markdown 模板；
- Analysis Persistence + `current_analysis` Query Read Model 落地前，正式数据库报告不得冒充已支持。

# 当前机器事实边界

本 Change 只更新设计文档，没有提前修改运行时实现。

在设计合并时的机器事实仍为：

- Stage 8A 显式数据库模式只持久化 Content；
- AI 成功结果当前回写 `deduplicated/contents.jsonl` 并导出 `labeled_data.xlsx`；
- 当前离线 Report Renderer 只有 Excel Source；
- 正式 Analysis PostgreSQL DDL/Migration/Repository/Job/HTTP Contract 尚未落地。

因此本 Change 固化的是后续实现目标，不把未来设计写成已经存在的机器能力。

# 修改范围

已同步：

- Blueprint 03：Analysis Owner/逻辑结果模型与“当前未落机器 Schema”边界，消除与 Blueprint 15 的未来表描述冲突；
- Blueprint 13：离线 Excel 报告 vs PostgreSQL 正式报告、显式数据源、统一 Report Dataset/Renderer；
- Blueprint 15：Analysis 成功结果正式持久化、幂等/历史/`current_analysis`、事务与报告关系；
- Blueprint 17：Stage 8A 当前只写 Content 的机器限制、后续完整写入目标、数据库报告/AI 页面硬门禁；
- 保持 Stage 8B—8F 既有编号，不在本 Change 重排正式阶段。

# 非目标

- 不实现 Analysis PostgreSQL Schema/Migration/Repository；
- 不修改 `imports_test.run_all()`；
- 不实现数据库版 Report Source；
- 不新增 Report Job/API/Web 页面；
- 不调整 Stage 8A 已闭环机器实现；
- 不修改代码、Contract、依赖或部署配置。

# 验证证据

文档分支完成时已执行：

```text
uv sync --locked
uv run python scripts/quality/check_docs.py
uv run python scripts/quality/scan_secrets.py
设计关键字/边界断言
```

最终 PR #92 只包含本 Change + Blueprint 03/13/15/17，没有代码、Migration、Contract、依赖、测试或运行配置变化。

PR #92 正式工作流：

```text
CI                                  success
Stage 6 XHS Vertical Slice          success
Stage 7 Keyword Packs               success
Stage 7 Provider Config Routing     success
Stage 7 Plan Occurrence Run Snapshot success
Stage 7 Scheduler Runtime           success
```

# Git / 集成

```text
设计基线 main：
a70ce7528ce983b72dde33e1a251cac658b28468

PR：#92
方式：Squash merge

合并后 main 提交：
78f2c1d48aec5c7c0db88e3f5a75080496779bf7
```

合并后已重新读取 `main`，确认四份 Blueprint 均存在于新主分支，Active Change 可进入归档。

# Migration / 部署 / 回滚

- Migration：本轮无；后续 Analysis Persistence L3 Change 才创建；
- 部署：无运行时变化；
- 兼容：现有 `imports_test`、数据库与报告运行行为不变；
- 回滚：仅需回退 Blueprint 文档提交，不影响数据库或线上数据。
