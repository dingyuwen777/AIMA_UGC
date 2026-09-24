---
schema: coding-change/v1
id: CHG-20260924-152229-import-replay-reversal-throughput
title: 历史数据导入、重筛与精确撤回后端吞吐修复
level: L3
status: in_progress
owner: yuwen.ding
branch: perf/593-import-replay-reversal-throughput
created: 2026-09-24T15:22:29+08:00
updated: 2026-09-24T15:22:29+08:00
completion_gate: required
depends_on: []
affected_areas:
  - ingestion
  - content
  - vehicles
  - storage
  - jobs
affected_paths:
  - backend/src/aima_ugc/
  - tests/
  - scripts/performance/
  - docs/appendix/
  - docs/operations/
contracts:
  - canonical-content.v1
  - ingestion.canonical-replay.v1
  - ingestion.canonical-replay-reversal.v1
data_changes:
  - canonical_replay_content_changes 精确撤回账本
  - contents 与 Brand/Vehicle Evidence
---

# 背景、目标和边界

2026-09-24 真实演示中，本地和服务器历史文件的全量预检/转换各约 41–50 秒；100 Artifact 重筛发生 `ON CONFLICT DO UPDATE` 同批重复命中并持续重试；“取消并撤回”单 Job 耗时 99.752 秒。历史微基准改善不能证明这三个过程已经流畅。

目标是在相同输入、相同数据库语义下系统性降低预检、导入、重筛和撤回端到端耗时，修复确定性失败，并保留安全边界。范围限后端、测试、基准与技术文档；不改 UI 或等待体验，不访问付费 Provider、生产库或正式历史迁移。

# 硬约束与方案

保持 Source Artifact 不可变、首笔业务写入前全量预检、Canonical Contract、过滤与 Historical Fill-Only、Content Owner、逐行账本、Fencing、检查点、取消、精确撤回以及后续事实保护。优先基于真实文件和隔离 PostgreSQL 的分段 Profile，按热点在现有 Owner 内合批或减少重复解析；性能改动必须通过结果对账，不以关闭校验或单纯放大并发取代根因修复。

备选方案：①仅加 Worker 并发，可能放大数据库锁争用且不能解决确定性失败；②先消除重复计算和逐行 SQL 往返，再按测量决定并发，当前采用；③另建 ETL/写库链，破坏 Owner 与追溯边界，拒绝。

# Requirement Traceability

| ID | 要求 | Source | 状态 | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 本地手工与服务器历史文件预检、转换和入库显著提速且结果对账一致 | #593；user:20260924-导入性能 | not_satisfied | 待同输入前后实测与账本对账 |
| R2 | 历史重筛显著提速，多别名同车型批量 Evidence 不再永久重试 | #593；user:20260924-重筛性能 | not_satisfied | 待失败回归、真实 PostgreSQL 和基准 |
| R3 | “取消并撤回”显著提速，撤回精确性、恢复与后续事实保护不变 | #593；user:20260924-撤回性能 | not_satisfied | 待分段基线、集成回归与前后对照 |
| R4 | 仅改后端，不改 UI/等待过程，不改正式业务语义与生产数据 | user:20260924-范围；AGENTS.md；docs/blueprint/07_技术决策与实施门禁.md | not_satisfied | 待最终 diff、测试与数据库边界复核 |
| R5 | 当前 PR 的测试、文档、Review、CI 与完成审计闭环 | AGENTS.md；#593 | not_satisfied | 待当前 HEAD 证据 |

# Validation Matrix

| 验证层 | 是否要求 | 范围 / 计划证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Canonical 转换、别名去重、撤回规则与错误分类的失败和回归测试 |
| 接口 / 契约 | required | Canonical/Job/API 字段与错误、生成契约保持兼容 |
| 集成 / 持久化 / 运行依赖 | required | 隔离 PostgreSQL 下的导入、重筛、撤回、账本、Fencing/重试 |
| 用户 / 工作流验收 | required | 后端 API → Worker → 结果/撤回的可观察状态与对账 |
| 跨组件关键路径 | required | 真实文件 → Artifact → Job → Content → 撤回的代表路径 |
| 外部依赖探测 | not_applicable | 不改变 TikHub 或付费模型边界，本轮输入均为本地文件 |
| 构建 / 打包 / 运行 | required | 当前 Python 环境、正式 Worker 装配和包检查 |
| 文档 / 治理 / 其他 | required | 技术文档、Change Ready、架构/Owner/Secret 和 CI |

# 实施与验收步骤

1. 使用两份真实 XLSX 和隔离库建立阶段 Profile，记录输入、命中率、结果计数与基线；日志不输出正文或 Secret。
2. 先写重筛同车型多别名与永久错误的失败回归，再修生产路径；验证无重试且结果一致。
3. 对预检、转换、入库已证实的热点逐项实验，采用真正降低端到端耗时且不损坏数据语义的实现；做相同输入 A/B。
4. 测量撤回每批数据库阶段，在现有 Owner 内减少无谓往返；验证取消/重试/接管、贡献恢复和后续写保护，记录 A/B。
5. 同步当前技术文档，重新读取上游要求，做完成审计、两阶段 Review、项目检查与当前 PR CI。

# 兼容、数据、部署与回滚

默认保持 HTTP/Job/Canonical 格式、Schema、依赖与业务语义不变；若 Profile 证明必须改其中之一，先更新本 Change 和正式决策并补迁移方案。生产部署、Migration 和历史正式数据操作不在本次授权。代码回滚使用旧 Worker/应用，保留已经提交的业务和撤回账本；本轮实验只写隔离数据库。

# Completion Audit

- [ ] upstream_re_read：重读用户范围、#593 与长期技术约束，独立重建完成定义。
- [ ] change_coverage：逐项核对 R1–R5 和真实日志中的失败/慢段。
- [ ] reverse_audit：由输入、Artifact、Job、Content 和撤回结果反查所有关键消费者与恢复路径。
- [ ] unresolved_cleared：清零 not_satisfied，或以正式依据记录延期/不适用；证据覆盖当前 HEAD。

# 交付状态

Issue #593；分支 `perf/593-import-replay-reversal-throughput`。早期 PR、验证、Review 与 CI 状态将在实施过程中更新；未获合并授权，本 Change 在实现 PR 中保持 Active。
