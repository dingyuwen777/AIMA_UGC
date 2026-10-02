---
schema: coding-change/v1
id: CHG-20261002-100000-date-supplement
title: 按发布时间补采与辅助补采弹窗
level: L3
status: in_progress
owner: Codex
branch: feature/date-supplement
created: 2026-10-02
updated: 2026-10-02
completion_gate: required
depends_on: []
affected_areas: [collection, frontend]
affected_paths: [backend/src/aima_ugc, frontend/src/features/collection-runtime, tests, contracts, docs]
contracts: [http, generated-client]
data_changes: []
---

# 变更摘要

Requirement-Source: #690

当前辅助补采依赖导入来源，用户已批准改为按已入库内容发布时间选取目标，并要求新建入口采用与导入数据一致的居中弹窗。

# 背景、现状与问题

Target Reader 已统一处理直接身份、可解析链接和当前明确不相关结果；创建 Run 已把每个 Content ID 固定为 Scope。Worker 当前只从 Batch/Campaign 恢复目标，必须增加按冻结 Content ID 读取的执行路径。

# 事实与证据

| 编号 | 事实 | 来源 | 约束 |
| --- | --- | --- | --- |
| E1 | 日期模式和日期字段不受现有 Contract 支持 | tests/contracts/test_collection_date_supplement.py 本轮 1 failed / 10 passed | 先增加契约 |
| E2 | 补采共享身份校验及 Scope Runtime | backend/src/aima_ugc/adapters/persistence/postgres/collection_targets.py；backend/src/aima_ugc/bootstrap/collection_scope.py | 复用现有链路 |
| E3 | 日期语义和居中弹窗已有共享组件 | frontend/src/shared/time/beijingTime.ts；AimaDateRange；AimaModalContainer | 不复制日历和弹窗机制 |

# 目标、成功标准与非目标

目标与验收以 #690 AC1–AC6 和用户批准的《按日期补采方案》为上游；非目标是依赖升级、新 Provider family、预算、生产操作及无依据的天数/条数限制。保持旧模式和历史任务兼容。

# 约束与意图决策

新增模式及资格接口；采用带时区的北京时间闭区间。已有 Content、Scope、Job 和 JSON 快照可以承载新行为，不新增 Schema/Migration。新任务部署需要 API、Worker、Frontend 同版本，回滚前暂停并结清日期任务，旧 Worker 不能处理新模式。

# 修改方案与决策依据

1. Contract、日期读取、资格 API → 北京时间范围和统一资格 → Contract/API/PostgreSQL 测试。
2. Run 冻结、Worker 内容恢复、运行类型 → 执行不重筛日期/相关性 → 持久化和评论/回复回归。
3. 同款居中弹窗、日期状态、详情/列表 → 用户能选择并观察结果 → 组件及全栈路径。
4. 生成、文档、容量、Review、CI → 契约和交付证据闭环。

## 备选方案与取舍

只改表单不能让现有 Worker 执行无导入来源的 Run；运行时再次日期查询会让目标漂移。采用创建时 Content Scope 冻结、执行时按 ID 恢复。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 日期资格与共享身份规则 | #690 / AC1 | not_satisfied | 待实现 |
| R2 | 原子冻结和兼容契约 | #690 / AC2 | not_satisfied | 待实现 |
| R3 | 冻结执行、详情评论回复 | #690 / AC3 | not_satisfied | 待实现 |
| R4 | 居中弹窗、状态与竞态 | #690 / AC4 | not_satisfied | 待实现 |
| R5 | 运行展示和生成客户端 | #690 / AC5 | not_satisfied | 待实现 |
| R6 | 分层验证、容量与文档 | #690 / AC6 | not_satisfied | 待验证 |

# 计划改动

Collection Contract/HTTP/Target Reader/Scope/Runtime Query；collection-runtime UI/Store/API/详情；generated client；相关测试；Blueprint §25 与当前产品说明。

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 输入与资格竞态、空/错误/重开、评论层级 |
| 接口 / 契约 | required | 日期合法性、旧模式、生成检查 |
| 集成 / 持久化 / 运行依赖 | required | PostgreSQL 日期边界、身份诊断、冻结、Worker |
| 用户 / 工作流验收 | required | 新建弹窗、运行中心及详情 |
| 跨组件关键路径 | required | 页面→API→PostgreSQL→Worker→结果 |
| 外部依赖 / 供应方探测 | not_applicable | Provider endpoint/mapper 不变；使用现有 Fake，无需付费 Probe |
| 构建 / 打包 / 运行 | required | 前端构建、后端静态检查、changed preflight |
| 文档 / 治理 / 其他 | required | 当前文档、Change、Completion、Review、CI |

# 风险、兼容性、迁移与回滚

主要风险是日期边界、执行漂移、身份缺口和请求竞态。测试只使用隔离数据库。无依赖、配置、Secret 或 Migration 变更；旧运行快照 v2 保留，新日期任务 v3。发布和回滚须 API/Worker/Frontend 协调。

# 文档、依赖、部署与发布影响

Docs Impact: targeted。只同步补采行为的正式说明；不改受管治理资产。发布部署未授权，本次交付止于可审查 PR。

# 完成审计

- [ ] upstream_re_read：重新读取用户方案和 live Issue。
- [ ] change_coverage：上游要求完整覆盖。
- [ ] reverse_audit：后端能力、前端入口、异步结果双向审计。
- [ ] unresolved_cleared：未满足要求清零。

# 完成证据与状态

Red：工作目录 .venv/Scripts/python.exe -m pytest tests/contracts/test_collection_date_supplement.py -q，1 failed / 10 passed，失败原因是现有契约拒绝日期模式和字段。

实现、Review、CI 尚未完成；未 merge、归档、关闭 Issue 或部署。
