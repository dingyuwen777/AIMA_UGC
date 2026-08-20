---
schema: rvc-change/v1
id: CHG-20260820-analysis-persistence-report-source
title: Analysis持久化与报告数据源边界
level: L3
status: ready_for_review
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

把已经确认的长期架构决策固化到 Blueprint：

1. AI 打标成功且通过本地 Validator 后，正式数据库模式必须把 Analysis 作为独立派生业务事实写入 PostgreSQL；不能长期停留在“Excel 有标签、数据库只有 Content”。
2. Content 与 Analysis 继续由不同 Owner 管理：Content Owner 保存平台事实，Analysis Owner 保存模型派生结果与标签对。
3. 离线单批报告继续读取本次处理完成的统一 Excel；正式系统报告、跨批次趋势和 Dashboard 读取 PostgreSQL Report Read Model。
4. 报告数据源必须显式选择，禁止根据“数据库是否可用/是否启动”自动在 Excel 与 PostgreSQL 之间切换。
5. Excel 与 PostgreSQL 两种数据源最终复用同一个 Provider-neutral Report Dataset/Statistics/Renderer 和同一个 Markdown 模板。

# 当前机器事实

基线：

```text
main@a70ce7528ce983b72dde33e1a251cac658b28468
```

当前实现：

- `imports_test.run_all(write_to_database=True)` 在 AI 打标前先把去重后的 Content 通过正式 File Import/Content Ingestion 写入 PostgreSQL；
- AI 成功后回写 `deduplicated/contents.jsonl`，随后导出 `labeled_data.xlsx`；
- 当前离线 Report Renderer 固定读取统一 Excel；
- 当前尚无正式 Analysis PostgreSQL DDL/Migration/Repository/Job/HTTP Contract；
- Blueprint 15 原有未来 Analysis 父结果 + 标签对子事实方向，但此前没有把“正式 DB 模式必须持久化成功 Analysis”写成硬规则；
- Blueprint 03 与 15 此前对未来 Analysis 表名/结构描述不一致。

# 用户确认与方案比较

用户已确认：

```text
AI 打标完成的数据也必须进入数据库。

离线单批报告 → Excel
正式系统报告/跨批次趋势 → PostgreSQL Read Model

不能因为数据库启动了就让同一个离线命令静默换数据源。
```

## 方案 A：只把 Content 入库，Analysis 长期只留 JSONL/Excel

优点：实现最少。

缺点：PostgreSQL 无法成为完整业务事实源；正式页面/跨批次报告无法可靠使用 AI 标签；Excel 与数据库长期分叉。

**不采用。**

## 方案 B：Content 与 Analysis 分 Owner 持久化，报告源按场景显式选择

- Content 先通过 Content Owner 入库并取得稳定 `content_id`；
- AI 通过 Validator 后，同一份 Analysis 同时用于 JSONL/Excel 与 Analysis Owner PostgreSQL 持久化；
- 离线批次报告继续使用 Excel 快照；
- 正式系统报告使用 PostgreSQL Query/Read Model；
- 两种来源统一转成 Report Dataset，再复用同一 Statistics/Renderer/Markdown 模板。

**采用。**

## 方案 C：数据库可用就自动读数据库，不可用就读 Excel

优点：调用表面简单。

缺点：同一命令会因环境状态产生不同数据范围；数据库可能包含历史/TikHub/其他 Batch，无法自然代表本次 run；可复现性差。

**禁止采用。**

# 已固化设计

## Analysis 持久化

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

硬规则：

- AI 标签不进入 `contents` 表；
- PostgreSQL Analysis、JSONL、Excel 消费同一份 Validator 成功结构，不从 Excel 反向解析后再入库，也不因写库二次调用模型；
- Analysis 使用“结果父事实 + 标签对子事实”逻辑模型；具体表名/DDL 留给后续 Analysis Persistence L3 Change + Migration 冻结；
- 相同 `content_id + input_hash + prompt_sha256 + taxonomy_sha256 + provider/model` identity 必须幂等；输入/Prompt/Taxonomy/模型变化形成新的历史分析结果；
- Query 层提供确定性的 `current_analysis`，默认匹配当前 Content 输入版本/Hash 与当前选定 Analysis 配置的最新成功结果；
- Analysis Result 与 Label Pairs 同一短事务提交；外部 LLM HTTP 不放进数据库事务；
- AI 失败不写猜测结果；Content 成功而 Analysis 持久化失败时必须暴露 partial/failed Analysis 阶段并允许幂等补写。

## 报告数据源

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

硬规则：

- `imports_test` 的本次 run 报告即使 `write_to_database=True` 也继续读取本次 Excel 快照；
- 正式系统报告、跨 Batch、7/30/90 天趋势和 Dashboard 使用 PostgreSQL Read Model；
- 禁止按 PostgreSQL 是否启动/可达自动切换数据源；
- Report Renderer 不直接 SQL；数据库读取通过 Query Repository/Read Model；
- 两种来源复用同一个 Provider-neutral Report Dataset、统计实现、Renderer 和 `platform/reporting/report_template.md`；
- 正式数据库报告在 Analysis Persistence + current Analysis Query Read Model 落地前不得冒充已支持。

# 本轮范围

- [x] 更新 Blueprint 03：Analysis Owner/逻辑结果模型，明确当前未落机器 Schema，消除与 Blueprint 15 的表描述冲突。
- [x] 更新 Blueprint 13：离线 Excel 报告 vs PostgreSQL 正式报告、显式数据源、统一 Report Dataset/Renderer。
- [x] 更新 Blueprint 15：Analysis 成功结果正式持久化、幂等/历史/current Analysis、事务与报告关系。
- [x] 更新 Blueprint 17：Stage 8A 当前只写 Content 的机器限制、后续完整写入目标、数据库报告/AI 页面硬门禁。
- [x] 保持 Stage 8B—8F 既有编号，不在本轮重排阶段。

# 非目标

- 不实现 Analysis PostgreSQL Schema/Migration/Repository；
- 不修改 `imports_test.run_all()`；
- 不实现数据库版 Report Source；
- 不新增 Report Job/API/Web 页面；
- 不调整 Stage 8A 已闭环机器实现；
- 不修改代码、Contract、依赖或部署配置。

# 验证证据

本轮为纯设计文档变更，不伪造 TDD。文档更新通过临时 GitHub Actions 在锁定 Python/uv 环境中执行，只有下列检查成功后才提交四份 Blueprint：

```text
uv sync --locked
uv run python scripts/quality/check_docs.py
uv run python scripts/quality/scan_secrets.py
设计关键字/边界断言
```

临时 workflow 的提交步骤位于上述检查之后；四份 Blueprint 已实际提交，说明这些检查完成后没有失败阻断。

收尾后重新比较：

```text
base main = a70ce7528ce983b72dde33e1a251cac658b28468
head = docs/analysis-persistence-report-source
behind_by = 0
最终 diff 仅 5 个文件：
- 本 Change
- Blueprint 03
- Blueprint 13
- Blueprint 15
- Blueprint 17
```

没有代码、Migration、Contract、依赖、测试或运行配置变化。

# Migration / 部署 / 回滚

- Migration：本轮无；后续 Analysis Persistence L3 Change 才创建。
- 部署：无运行时变化。
- 兼容：当前 `imports_test`/数据库/报告运行行为不变；本轮只是把未来目标变成正式设计门禁。
- 回滚：只需回退文档提交，不影响数据库或线上数据。

# Git / 交付

- 分支：`docs/analysis-persistence-report-source`。
- Change：`ready_for_review`。
- PR：未创建。
- 合并：未执行。
- 发布/部署：未执行。
