---
schema: rvc-change/v1
id: CHG-20260820-analysis-persistence-report-source
title: Analysis持久化与报告数据源边界
level: L3
status: in_progress
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

当前 `main@a70ce7528ce983b72dde33e1a251cac658b28468`：

- `imports_test.run_all(write_to_database=True)` 在 AI 打标前先把去重后的 Content 通过正式 File Import/Content Ingestion 写入 PostgreSQL；
- AI 成功后回写 `deduplicated/contents.jsonl`，随后导出 `labeled_data.xlsx`；
- 当前离线 Report Renderer 固定读取统一 Excel；
- 当前尚无正式 Analysis PostgreSQL DDL/Migration/Repository/Job/HTTP Contract；
- Blueprint 15 已有未来 Analysis 父结果 + 标签对子事实方向，但还没有把“正式 DB 模式必须持久化成功 Analysis”写成硬规则；
- Blueprint 03 与 15 对未来 Analysis 表名/结构描述存在不一致，需要统一为逻辑模型并把正式 DDL 名称留给后续 Analysis 持久化 Change 冻结。

# 已确认决策

用户已确认：

```text
AI 打标完成的数据也必须进入数据库。

离线单批报告 → Excel
正式系统报告/跨批次趋势 → PostgreSQL Read Model

不能因为数据库启动了就让同一个离线命令静默换数据源。
```

## 方案比较

### 方案 A：只把 Content 入库，Analysis 长期只留 JSONL/Excel

优点：实现最少。

缺点：PostgreSQL 无法成为完整业务事实源；正式页面/跨批次报告无法可靠使用 AI 标签；Excel 与数据库长期分叉。

不采用。

### 方案 B：Content 与 Analysis 分 Owner 持久化，报告源按场景显式选择

- Content 先通过 Content Owner 入库并取得稳定 `content_id`；
- AI 通过 Validator 后，同一份 Analysis 同时用于 JSONL/Excel 与 Analysis Owner PostgreSQL 持久化；
- 离线批次报告继续使用 Excel 快照；
- 正式系统报告使用 PostgreSQL Query/Read Model；
- 两种来源统一转成 Report Dataset，再复用同一 Statistics/Renderer/Markdown 模板。

优点：职责清晰、可追溯、支持长期查询和历史、不会让报告层依赖某个输入来源。

采用。

### 方案 C：数据库可用就自动读数据库，不可用就读 Excel

优点：调用表面简单。

缺点：同一命令会因环境状态产生不同数据范围；数据库可能包含历史/TikHub/其他 Batch，无法自然代表本次 run；可复现性差。

禁止采用。

# 数据与兼容边界

- 当前不创建 Analysis 表、不写 Migration、不改变现有 `imports_test` 运行行为；本轮只冻结未来设计。
- 正式 Analysis 持久化实现必须作为后续独立 L3 Change 冻结具体表名、字段、唯一约束、Migration、Job/事务边界和 Query 语义。
- 不把 AI 标签塞进 `contents` 表，也不把多标签塞进逗号/换行字符串或 PostgreSQL ENUM。
- 已通过 Validator 的 Analysis 是 JSONL/Excel 与 PostgreSQL 的同一逻辑事实，不能从 Excel 反向解析后再写数据库。
- 相同 Analysis identity 必须幂等；输入、Prompt/Taxonomy 或模型身份变化时保留新的历史结果，不覆盖旧分析事实。
- AI 失败不得写猜测标签；成功项可以独立持久化，失败项保持可重试/可观察。

# 报告边界

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

Report Renderer 禁止直接 SQL；PostgreSQL 读取必须经过 Query Repository/Read Model。

# 本轮范围

- 同步 Blueprint 03/13/15/17；
- 消除 Analysis 未来表描述冲突；
- 固化 AI 成功结果必须进入正式 PostgreSQL 的长期目标；
- 固化 Excel/数据库报告源按场景显式选择的规则。

# 非目标

- 不实现 Analysis PostgreSQL Schema/Migration/Repository；
- 不修改 `imports_test.run_all()`；
- 不实现数据库版 Report Source；
- 不新增 Report Job/API/Web 页面；
- 不调整 Stage 8A 已闭环机器实现；
- 不重排已经确定的 Stage 8B—8F 编号，本轮只增加进入后续数据库报告/AI页面前的硬门禁。

# 任务

- [x] 读取当前 main、AGENTS、Skill 和相关 Blueprint。
- [x] 确认当前机器行为与目标行为的差异。
- [ ] 更新 Blueprint 15：Analysis 持久化硬规则、历史/幂等、JSONL/Excel 同源。
- [ ] 更新 Blueprint 17：Stage 8 当前机器事实、正式 DB 模式目标、后续实现门禁。
- [ ] 更新 Blueprint 13：离线 Excel 报告 vs PostgreSQL 正式报告、显式数据源、统一 Report Dataset/Renderer。
- [ ] 更新 Blueprint 03：Analysis 逻辑表/Owner 规划与“未落地”状态，消除与 Blueprint 15 的冲突。
- [ ] 检查四份文档互相引用和表述一致性。

# 验证

本轮为纯设计文档变更，不伪造 TDD。替代验证：

- `scripts/quality/check_docs.py`；
- `scripts/quality/scan_secrets.py`；
- 检查 Blueprint 03/13/15/17 不再存在互相冲突的 Analysis 持久化/报告源描述；
- 确认没有代码、Migration、Contract、依赖文件变化。

# Migration / 部署 / 回滚

- Migration：本轮无；后续 Analysis Persistence L3 Change 才创建。
- 部署：无运行时变化。
- 回滚：本轮只修改 Blueprint，可通过回退文档提交恢复；不会影响数据库或线上数据。

# Git / 交付

- 分支：`docs/analysis-persistence-report-source`。
- PR：未创建。
- 合并：未执行。
