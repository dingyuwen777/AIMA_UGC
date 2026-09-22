---
schema: coding-change/v1
id: CHG-20260922-184135-canonical-replay-runtime-records
title: 重筛入库纳入采集运行记录与进度详情
level: L2
status: ready_for_review
owner: codex
branch: feat/canonical-replay-runtime-records
created: 2026-09-22
updated: 2026-09-22
completion_gate: required
depends_on: []
affected_areas:
  - ingestion
  - collection-runtime
  - contracts
  - frontend
  - documentation
affected_paths:
  - backend/src/aima_ugc/contracts/http.py
  - backend/src/aima_ugc/modules/collection/runtime_cursor.py
  - backend/src/aima_ugc/modules/collection/runtime_query.py
  - backend/src/aima_ugc/adapters/persistence/postgres/collection_runtime_queries.py
  - backend/src/aima_ugc/bootstrap/collection_http.py
  - frontend/src/features/import-batches/
  - frontend/src/features/admin-configuration/pages/AdminConfigurationPage/components/CatalogConfigurationPanel.vue
  - tests/contracts/test_stage8e_http.py
  - tests/unit/collection/test_collection_runtime_cursor.py
  - tests/integration/collection/test_stage8e_collection_http_runtime.py
  - frontend/e2e/collection-runtime.spec.ts
  - docs/product/02_当前产品能力与用户流程.md
  - docs/blueprint/04_后端任务API与前端.md
contracts:
  - CollectionRuntimeRecordType
  - CollectionRuntimeItemResponse
data_changes: []
---

# 变更摘要

- **要解决的问题**：管理员手动触发的全历史 Canonical Replay 已持久化为请求和多个子 Job，但采集运行中心不可见，用户无法跟踪进度和结果。
- **拟议修改**：把一次 `canonical_replay_all_requests` 聚合成一条统一运行记录，汇总关联子 Run/Job 的状态、加权进度、时间与处理统计，并提供前端详情。
- **预期结果**：一次点击对应一条“历史数据重筛”记录，可在采集运行中心持续查看进度、结果、问题和技术身份。

# 背景、现状与问题

Issue #566 固化了用户当前决定与七条验收标准。Canonical Replay 已存在 `all request → child run → persistent job` 的真实关系；当前统一运行只读模型只联合 Excel、统一数据导入和 TikHub 采集/补采，因此 Replay 被遗漏。把子 Job 逐条展示会把一次用户操作放大成多条记录，也会让 KPI 重复计数。

# 事实与证据

| 编号 | 已确认事实 | 来源 | 约束 |
| --- | --- | --- | --- |
| E1 | 一次全历史请求写入 `canonical_replay_all_requests`，子 Run 通过 `all_request_id` 关联 | Canonical Replay Schema/Repository | 必须按 all-request 聚合，不伪造 Collection Run |
| E2 | 子 Job 维护持久状态与 0—100 进度，子 Run 维护可对账行统计 | Job Runtime、Replay Worker/Run 表 | 运行记录必须复用真实状态和统计 |
| E3 | 当前统一运行 Contract 只有四种记录类型，SQL UNION 不含 Replay | HTTP Contract、Runtime Cursor/Query | Contract、Cursor、SQL、前端穷举需同步扩展 |
| E4 | 全历史请求可能为 0 个 Artifact，且此时不会创建子 Job | Replay enqueue_all | 空输入必须作为一次已完成、无处理数据的请求解释 |

# 目标、成功标准与非目标

## 目标

- 一次手动全历史重筛只展示一条统一运行记录。
- 聚合真实状态、按 Artifact 权重计算进度，并汇总子任务和行级处理结果。
- 记录进入类型筛选、自动轮询、KPI 与详情抽屉。

## 成功标准

- [x] 一次全历史请求在列表中只出现一次，多个子 Job 不泄漏成多条业务记录。
- [x] 排队、运行、成功、部分成功、失败、取消和空输入状态有稳定聚合语义。
- [x] 列表和详情展示 Artifact、子任务与行级处理统计。
- [x] KPI 按一次请求计数并汇总实际入库结果。
- [x] Contract、集成、Browser、生成、静态、构建、文档与本地 Review 已完成；PR PostgreSQL/全量 CI 作为 Ready 后远程硬门禁继续执行。

## 非目标

- 不改变 Replay 输入选择、分片、批次、幂等、Worker 或入库逻辑。
- 不新增 Schema/Migration，不自动触发重筛，不调用 TikHub 或 AI。
- 不执行生产部署、生产 Migration 或生产数据操作。

## 必须保持不变

- PostgreSQL 和现有 Replay 表继续是唯一事实源；统一运行只读聚合不写跨 Owner 表。
- 现有导入、采集、补采的列表、详情、筛选和 KPI 语义不回归。
- 技术 ID 只在详情中展示；生成 Client 不手工修改。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 用户记录粒度 | 一个 all-request 对应一条记录 | #566 / AC1、E1 | 子 Job 只作为统计与进度来源 |
| 进度 | 按各子 Run 的 Artifact 数量加权 Job 进度 | #566 / AC2、E2 | 最后一个不足 100 Artifact 的分片不会被等权放大 |
| 状态 | 活跃优先；全部终态后区分成功、部分成功、失败、取消；空输入直接成功 | #566 / AC2、E4 | 状态可解释且不会伪造 Job |
| Contract | 新增 `canonical_replay` 枚举和专用统计结构 | #566 / AC3、E3 | OpenAPI 与生成 Client 需要同步 |
| 数据与迁移 | 只读查询复用现有表 | E1—E4 | 无 Migration、回填或生产数据变更 |

# 修改方案与决策依据

## 最小充分方案

1. 先用 Contract、Cursor、PostgreSQL 集成与 Browser 失败测试固定目标行为。
2. 扩展统一运行读模型，按 all-request 聚合子 Run/Job，计算状态、加权进度、时间、错误与统计。
3. 扩展公共响应和前端穷举，新增“历史数据重筛”列表表现与详情抽屉；Store 轮询同步打开的详情。
4. 将 Replay 纳入 KPI，并更新管理员成功提示、产品与架构文档。
5. 重新生成 OpenAPI/JSON Schema/前端 Client，执行分层验证、Review、CI 和交付门禁。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1：聚合 all-request | E1、#566 / AC1 | 与一次点击的用户心智一致，避免重复记录和 KPI |
| D2：复用 Job/Run 事实 | E2、#566 / AC2—AC4 | 不复制进度状态机，也不创建平行任务事实 |
| D3：无 Migration | E1—E4 | 现有关系和统计已足够支撑只读投影 |

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 一次重筛只产生一条运行记录 | #566 / AC1 | satisfied | all-request 聚合 SQL；PostgreSQL 集成测试；Browser 列表回归 |
| R2 | 聚合状态与加权进度覆盖完整生命周期 | #566 / AC2 | satisfied | 状态优先级、Artifact 加权进度、空请求投影与集成测试 |
| R3 | 展示 Artifact、子任务与行级处理结果 | #566 / AC3 | satisfied | 专用 Runtime Stats Contract、列表和详情抽屉 Browser 回归 |
| R4 | 纳入三项运行 KPI且按请求计数 | #566 / AC4 | satisfied | all-request 摘要查询与集成断言 |
| R5 | 支持类型筛选和详情轮询同步 | #566 / AC5 | satisfied | Cursor/Contract、Store 同步和 Browser 筛选回归 |
| R6 | 管理员提示运行中心可查看且不自动重筛 | #566 / AC6 | satisfied | 管理员配置 Browser 全量回归；保存路径未新增 Replay 调用 |
| R7 | 完成分层验证、文档和交付门禁 | #566 / AC7 | explicitly_deferred | 本地分层验证、文档和两轮 Review 已完成；PR PostgreSQL/全量 CI、merge、archive 与 main-fresh 只能在 Ready 后执行 |

# 计划改动

| 文件 / 模块 | 计划修改 | 原因 | 对应要求 |
| --- | --- | --- | --- |
| Runtime Contract/Cursor/Read Model | 新增 Replay 类型、身份和统计 | 建立稳定公共投影 | R1—R5 |
| PostgreSQL Runtime Query | 聚合 all-request 与子 Job，并扩展 KPI | 使用真实持久事实 | R1—R4 |
| Collection HTTP Mapping | 生成用户可读名称、状态和专用统计 | 保持 Router/Service/Repository 边界 | R2—R3 |
| Runtime Store/Table/Drawer | 类型筛选、列表结果、详情和轮询同步 | 提供完整用户流程 | R3、R5 |
| 管理员配置反馈 | 指向采集运行中心 | 建立触发后的可发现性 | R6 |
| 测试、生成物、文档 | 回归与事实同步 | 防止契约和文档漂移 | R7 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Cursor 新类型、状态/进度映射、前端穷举 |
| 接口 / 契约 | required | Runtime RecordType、Item 统计与生成 Client |
| 集成 / 持久化 | required | 多子 Job、空输入、部分失败、筛选、Cursor、KPI |
| 用户 / 工作流验收 | required | 运行中心列表、详情、轮询与管理员提示 |
| 跨组件关键路径 | required | Replay 表 → Runtime SQL → HTTP → Browser |
| 外部依赖 / Provider | not_applicable | 不调用 TikHub、LLM 或其他外部服务 |
| 构建 / 运行 | required | 后端静态、前端 lint/typecheck/test/build |
| 文档 / 治理 | required | targeted 文档、Completion Audit、Review、Ready Gate |

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 处理 |
| --- | --- | --- |
| 主要风险 | 聚合状态或进度误导、一次请求被重复计数 | 以 all-request 为主键，覆盖多状态与不等长分片测试 |
| Contract 兼容 | 新增枚举值和可选专用统计 | 同步仓库内唯一生成 Client 与穷举映射 |
| 数据 / Migration | 不适用 | 只读复用现有表，不写历史数据 |
| 部署 | 普通后端/前端发布 | 无配置、Secret、Schema 或 Worker 注册变化 |
| 回滚 | Git 回滚 | 无数据恢复动作 |

# 文档、依赖、部署与发布影响

- **长期文档**：targeted 同步当前产品流程和后端任务/API/前端边界。
- **依赖 / Runtime**：不新增、删除或升级依赖和 Runtime。
- **配置 / Secret**：不变。
- **Schema / Migration / 数据**：不变，不需要 Alembic 或历史回填。
- **部署 / Release**：只交付源码，不执行生产发布或生产 Replay。

# 完成审计

- [x] upstream_re_read：Ready 前重新读取 #566、用户决定、Replay Schema/Repository/Worker、Runtime Contract/Query、前端消费者与产品文档，验收语义无漂移。
- [x] change_coverage：R1—R6 均映射到实现、Contract/Integration/Browser 测试和文档；R7 只延期 Ready 后才能发生的远程生命周期动作。
- [x] reverse_audit：从“重筛入库”按钮反查 all-request/child Run/Job，再到统一 Query、列表、详情、轮询与任务中心；从每个前端动作反查真实 Contract/持久事实，未新增取消或逐 Run 管理假能力。
- [x] unresolved_cleared：`not_satisfied` 已清零；本机缺少 PostgreSQL Secret 的执行缺口由 Ready 后 PR PostgreSQL Integration 硬门禁承接。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | Red / Windows 本地 Contract + Cursor | `pytest ... -k canonical_replay` | 2 failed：缺少 `CanonicalReplayRuntimeStatsResponse`；Cursor 拒绝 `canonical_replay` | 公共 Contract 与分页 Cursor 当前未纳入重筛 |
| V2 | Red / Playwright Browser Mock | `npm run test:e2e -- collection-runtime.spec.ts admin-configuration-figma.spec.ts --grep "canonical replay as one\|queues every historical"` | 2 failed：缺少重筛列表/详情表现与目标成功提示 | 用户流程当前未满足 #566 |
| V3 | Windows 本地 PostgreSQL 集成前置 | `pytest ... -k aggregates_all_canonical_replay_children_once` | setup error：本机缺少 `.runtime/secrets/postgres_password` | 本地无法形成数据库 Red/Green；干净 PR CI 必须执行该集成回归 |
| V4 | Green / Windows Contract、Cursor、Replay API | 相关 Pytest + 生成/兼容检查 | 20 passed；Contract 生成和兼容通过 | 公共枚举、专用统计、Cursor 与既有 Replay API 兼容 |
| V5 | Windows SQLAlchemy / PostgreSQL Dialect | 编译 `_canonical_replay_select` 与统一 UNION | 成功生成 9,701 / 20,565 字符 SQL | 新聚合查询可由 PostgreSQL Dialect 编译 |
| V6 | Windows Backend 静态 | Ruff changed scope；Mypy `backend/src/aima_ugc` | 全部通过；364 source files 无类型问题 | 后端格式、类型和调用边界成立 |
| V7 | Windows Frontend | ESLint；typecheck；Vitest；Vite build | 通过；32 files / 227 tests；生产构建成功 | 前端穷举、Store、组件和构建无回归 |
| V8 | Windows Playwright Browser Mock | `collection-runtime.spec.ts admin-configuration-figma.spec.ts` | 45 passed | 重筛列表、筛选、详情、提示及既有导入/补采/目录流程成立 |
| V9 | Windows 文档与仓库门禁 | docs/docs-facts、architecture、table ownership、Secret scan | 全部通过 | 文档事实、只读跨 Owner 聚合与 Secret 边界成立 |
| V10 | Windows Playwright 轮询同步 | `collection-runtime.spec.ts --grep "canonical replay as one"` | 1 passed；运行中详情在 5 秒轮询后更新为已完成 2 / 2 | 打开详情复用统一列表轮询并同步最新聚合状态 |
| V11 | base `1a9ecf2e` → head `382cc464` 两轮独立审查 | Issue #566、Schema、聚合 SQL、Contract、前端消费者、测试与文档双向审计 | 首轮发现数据库状态矩阵证据不足并补参数化集成回归；修复后 re-review 为 `NO_FINDINGS_WITHIN_SCOPE`，测试执行待 PR PostgreSQL CI | 防止用 Browser Mock 冒充持久状态映射证据，并复核修复没有扩大生产范围 |

## 未验证内容与剩余风险

- 本地 PostgreSQL 集成环境缺少 Secret，数据库回归只能由有正式测试服务的 PR CI 运行。
- 本地实现、非数据库分层验证与两轮 Review 已完成；PR PostgreSQL CI、合并、归档和 main-fresh 尚未完成。

## 交付状态

- Issue：#566。
- 分支：`feat/canonical-replay-runtime-records`。
- PR：#567（Draft），当前 HEAD `382cc464`；Change 已进入 `ready_for_review`，待远程 CI。
- Schema / Migration / 依赖 / 配置：均不变。
