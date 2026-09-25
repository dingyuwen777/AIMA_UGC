---
schema: coding-change/v1
id: CHG-20260925-095824-replay-revocation-impact
title: 修复历史重筛统计与数据导入撤销影响漏算
level: L3
status: in_progress
owner: yuwen.ding
branch: fix/603-replay-revocation-impact
created: 2026-09-25T09:58:24+08:00
updated: 2026-09-25
completion_gate: required
depends_on: []
affected_areas:
  - ingestion
  - collection
  - frontend
affected_paths:
  - backend/src/aima_ugc/adapters/persistence/postgres/historical_revocation.py
  - backend/src/aima_ugc/adapters/persistence/postgres/content_lifecycle.py
  - backend/src/aima_ugc/bootstrap/canonical_replay_worker.py
  - frontend/src/features/import-batches/pages/CollectionRuntimePage/components/CollectionRuntimeTable.vue
  - frontend/src/features/task-center/store.ts
  - tests/integration/ingestion/test_import_campaign_revocation_postgres.py
  - frontend/tests/collection-runtime.spec.ts
  - frontend/tests/task-center.spec.ts
  - docs/appendix/08_数据入口与统一入库实现.md
contracts: []
data_changes: []
---

# 背景与目标

本机 2026-09-25 的第二次全历史重筛新增入库为 0，但三个子任务分别收敛 16,469、22,780、1,055 条既有内容。采集运行与任务中心只显示“入库 0”，导致用户误以为没有处理。第四次本地导入 66,139 行全部过滤，但同 Campaign 后续重筛形成 6,757 条来源贡献、涉及 5,747 个 Content；撤销预览按原导入逐行账本显示影响 0，实际 Worker 重组 5,747 个 Content。

目标是让预览与真实贡献账本、执行进度一致，让重筛列表展示两种不同结果，并根据日志拆分慢阶段后验证可行优化。保持不可变历史审计事实、公共 API、Schema、依赖和用户现有数据不变。生产部署与改写既有审计不在范围内。

# 已确认事实与机制

- `historical_revocation._affected_content_ids` 只合并原导入行账本与在线补采账本，漏掉重筛沿原 Campaign 来源写入的 `content_source_contributions`。
- 撤销 Worker 的 `content_lifecycle._campaign_contributions_query` 已按 Campaign 关联读取上述贡献，故实际撤销数量大于预览。
- 第二次重筛的 `rows_ingested` 确为 0，`existing_convergence` 合计 40,304；当前两个前端概览只展示前者。
- 最大子任务的 `fallback_ms` 为 95,544 毫秒，但该阶段包含快照、Content 更新、证据、贡献账本，不能直接判定具体 SQL 瓶颈。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 验证 |
| --- | --- | --- | --- | --- |
| R1 | 过滤行后经重筛产生贡献时，撤销预览与实际撤销数量及进度口径一致 | #603 / AC1；用户截图 | not_satisfied | PostgreSQL 集成场景与本机只读对账 |
| R2 | 第二次重筛新增 0 时显示已有内容收敛，不误称无处理 | #603 / AC2；用户问题 | not_satisfied | 前端列表和任务中心测试 |
| R3 | 分析全链路日志和贡献归属，拆分关键慢阶段并以实验决定优化 | #603 / AC3；用户要求 | not_satisfied | 阶段指标、隔离数据库实验、耗时对照 |
| R4 | 回归、文档、Review、CI 保持数据正确性 | #603 / AC4；项目规则 | not_satisfied | 分层测试与 CI |

# 计划与验证

| 步骤 | 修改范围 | 可观察结果与验证 |
| --- | --- | --- |
| 来源对齐 | 撤销影响查询、贡献查询、PostgreSQL 集成测试 | 预览受影响数量等于实际处理的独立 Content 数，普通/补采场景不回退 |
| 口径修正 | 采集运行列表、任务中心及其测试 | 新增 0、已有内容收敛大于 0 的任务明确展示两项 |
| 性能取证 | 重筛 Worker 聚合阶段日志、隔离数据库实验 | 找到慢阶段和有证据的优化点，验证同数据结果不变 |
| 完成检查 | 文档、测试、Review、CI | 需求与结果逐项对齐，不改写旧审计事实 |

# 验证矩阵

| 层 | 要求 | 证据 |
| --- | --- | --- |
| PostgreSQL / Worker | required | 待执行 |
| 前端行为 | required | 待执行 |
| 静态检查与生成一致性 | required | 待执行 |
| 当前日志与隔离性能实验 | required | 待执行 |
| 外部 Provider | not_applicable | 当前链路不发送外部请求 |

# 完成审计

待重新读取 #603、Contract、当前 diff 和测试后填写。

# 两阶段 Review

待实施后执行。

# 交付与风险

无 Schema/Migration/依赖/公共 Contract 变动。历史已落地的错误撤销审计字段是不可变事实，本轮不追溯改写；将在结果中说明旧记录与新预览的边界。
