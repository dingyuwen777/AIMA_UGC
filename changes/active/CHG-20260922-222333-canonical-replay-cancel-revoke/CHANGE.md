---
schema: coding-change/v1
id: CHG-20260922-222333-canonical-replay-cancel-revoke
title: 历史数据重筛支持弹窗、取消与精确撤回
level: L3
status: ready_for_review
owner: codex
branch: feat/canonical-replay-cancel-revoke
created: 2026-09-22
updated: 2026-09-23
completion_gate: required
depends_on: []
affected_areas:
  - ingestion
  - content
  - vehicles
  - jobs
  - collection-runtime
  - contracts
  - frontend
  - documentation
  - governance
affected_paths:
  - backend/src/aima_ugc/modules/ingestion/
  - backend/src/aima_ugc/modules/content/
  - backend/src/aima_ugc/modules/vehicles/
  - backend/src/aima_ugc/adapters/persistence/postgres/
  - backend/src/aima_ugc/bootstrap/
  - backend/src/aima_ugc/contracts/http.py
  - backend/src/aima_ugc/modules/collection/
  - backend/src/aima_ugc/database_schema.py
  - migrations/versions/
  - frontend/src/features/import-batches/
  - tests/
  - frontend/e2e/
  - docs/product/
  - docs/blueprint/
  - docs/appendix/
  - .github/PULL_REQUEST_TEMPLATE.md
contracts:
  - CanonicalReplayAllRequest lifecycle
  - Canonical Replay all-request cancel and revoke API
  - CollectionRuntimeItemResponse
  - OpenAPI and generated frontend client
data_changes:
  - 新增 Replay 操作级可逆贡献账与撤回状态事实
  - 新增向前 Alembic Migration；旧 Replay 无账本时 fail closed
---

# 变更摘要

- **要解决的问题**：历史数据重筛详情仍是抽屉，现有取消只能停止后续批次，无法撤回已提交的 Content Current、业务可见性和自动品牌/车型 Evidence。
- **拟议修改**：详情改为与数据导入一致的弹窗；为每次全历史 Replay 持久记录精确可逆贡献，新增 all-request 取消并撤回、终态撤回和持久撤回 Job。
- **预期结果**：管理员可在同一运行记录中查看、取消并安全撤回一次重筛；只撤回仍可归因于本次操作的变化。

# 背景、现状与问题

Issue #570 固化了用户决定和 AC1—AC8。当前全历史 Replay 为
`canonical_replay_all_requests → canonical_replay_runs → jobs`，运行中心按父请求聚合；
但公开 API 只支持单 Run 取消。Worker 在批边界响应取消，已提交批次仍保留。
Content 来源贡献沿用原始导入/采集来源，自动 Evidence 也没有 Replay before/after 账，
因此不能从现有版本或结果行安全猜测撤回范围。

# 事实与证据

| 编号 | 已确认事实 | 来源 | 决策约束 |
| --- | --- | --- | --- |
| E1 | 一次全历史请求拆分为多个 Run/Job，运行中心只展示一条 | Migration 0058、Replay Repository、Runtime Query | all-request 是用户操作和计数单位 |
| E2 | 当前取消只停止后续批次，已提交写入不回滚 | Replay Worker、单 Run cancel API | 先停止子任务，再异步撤回 |
| E3 | 来源贡献与 Evidence 没有本次 Replay 的可逆身份 | Content/Evidence tables | 新建操作级账；旧请求 fail closed |
| E4 | Campaign 撤销使用 before/after、freshness 和生命周期 Version | 生命周期撤销实现与文档 | 复用安全不变量，不能整 Campaign 粗撤 |
| E5 | Replay 详情用 Drawer，数据导入用 Modal | 当前前端组件 | 改容器并保留轮询 |

## 推断与待确认

- 无。撤回范围、保留项、旧数据策略和过程状态已由 #570 及用户确认。

# 目标、成功标准与非目标

## 目标

- Replay 详情使用 Modal 并继续自动刷新。
- all-request 支持管理员“取消并撤回”和终态“撤回本次入库”。
- 用持久、幂等、可审计账本精确恢复仍属于本次 Replay 的 Current、可见性和自动 Evidence。
- 同一运行记录展示取消、撤回进度、统计、成功与失败。

## 成功标准

- [x] AC1—AC8 已有直接实现与新鲜分层证据；PR CI 与 main-fresh 由交付门禁继续收口。
- [x] 旧 Replay 无操作账本时拒绝撤回。
- [x] 取消、撤回重试和 Worker 接管保持幂等、Lease/Fencing 与审计语义。

## 范围

- Replay all-request 状态、操作账、取消/撤回服务、API、Job 与 Migration。
- Content Current、可见性、自动 Brand/Vehicle Evidence 的条件式恢复。
- Runtime 聚合、前端弹窗、生成物、测试和受影响长期文档。

## 非目标

- 不删除 Canonical/Raw、Content 历史 Version 或审计事实。
- 不撤回其它来源/后来写入，不覆盖人工锁定 Evidence。
- 不改变品牌/车型保存后仍需手动重筛的规则。
- 不执行生产 Migration、数据撤回、部署或 Provider/LLM 调用。

## 必须保持不变

- PostgreSQL 是唯一业务事实源；Content/Evidence 仍由各自 Owner 写入。
- Job Runtime 的 Lease、Fencing、Heartbeat、取消和重试不变量保持。
- 每 Run 最多 100 Artifact、每批最多 1000 行保持。
- Data Import Campaign 撤销与历史审计不回归。

# 约束与意图决策

| 维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 操作粒度 | all-request 是取消、撤回、进度和幂等单位 | #570 / AC2、AC3；E1 | 子 Run 只是执行分片 |
| 撤回时序 | 先取消全部活跃子任务，停止写入后再撤回 | #570 / AC2；E2 | 防止 Replay 与撤回竞态 |
| 可逆账本 | 原写事务内记录 before/after 与 freshness | #570 / AC4—AC6；E3—E4 | 只撤仍匹配 after 的变化 |
| 旧数据 | 无精确账本的旧 Replay 不可撤回 | #570 风险与迁移；E3 | fail closed |
| Contract | 新增 all-request cancel/revoke；扩展 lifecycle、进度和统计 | #570 / AC2、AC3、AC7 | 同步 OpenAPI 和生成 Client |
| Migration | 新增表/约束，不做历史猜测回填 | #570 / AC8 | 先迁移再部署新代码 |
| 回滚 | 代码可回退，新账本/撤回事实保留 | #570 风险与迁移 | DB downgrade 需独立确认 |

# 修改方案与决策依据

## 最小充分方案

1. 先用 Contract、PostgreSQL、Worker 和 Browser 失败测试固定目标行为。
2. 在 Replay 批事务中记录本次操作对 Content Current/可见性/自动 Evidence 的可逆事实。
3. 新增持久撤回 Job；先收敛子 Replay Job，再按 freshness 条件恢复 Owner 数据；有 Current Delta
   时追加生命周期 Version，纯 Evidence 幂等收敛时保留原 Version 和有效 Analysis。
4. 扩展 all-request API、管理员审计和运行中心聚合，保持幂等且一次请求只计一次。
5. 用 Modal 替换 Replay Drawer，提供确认、禁用、过程反馈和轮询。
6. 生成 Contract/Client，完成分层验证、Review、CI、合并和 main-fresh。

## 证据到决策

| 决策 | 证据 | 原因 |
| --- | --- | --- |
| D1：操作级账 + 持久撤回 Job | E2—E4 | 支持部分提交、重试、接管、后来写入和审计 |
| D2：撤回前收敛子 Job | E1—E2 | 消除继续入库与撤回的竞态 |
| D3：旧请求 fail closed | E3 | 缺少 before/after 时无法安全归因 |
| D4：同一运行记录承载生命周期 | E1、#570 / AC7 | 不建平行任务或重复 KPI |

## 备选方案与取舍

- **复用 Campaign 整体撤销**：不采用；全历史 Replay 跨多个来源/Campaign，会扩大撤销范围。
- **按 Content Version 或当前 Evidence 反推后删除**：不采用；无法区分共享、后来写入和人工锁定。
- **HTTP 内同步撤回**：不采用；数据量不受单请求时长约束，且会绕过持久 Job 保障。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | Replay 详情用 Modal 并保持自动刷新 | #570 / AC1 | satisfied | Modal 组件与 Mock Browser 18 项通过；运行记录轮询保持 |
| R2 | all-request 取消全部子任务并撤回，幂等且有管理员审计 | #570 / AC2 | satisfied | queued 子 Job 取消编排、运行中批边界取消、API 与审计集成回归通过 |
| R3 | 终态请求可显式撤回且不重复 | #570 / AC3 | satisfied | 唯一 reversal Job、重复请求和真实 API→Worker→Runtime→Browser 路径通过 |
| R4 | Current 只在 after/freshness 匹配时恢复；有 Delta 才追加 Version | #570 / AC4 | satisfied | PostgreSQL Worker 回归覆盖生命周期 Version、纯 Evidence 不使 Analysis 失效及后来普通导入保护 |
| R5 | Replay 独占内容退出业务视图，共享内容保留 | #570 / AC5 | satisfied | 可见性 Owner、独占隐藏与后来来源保留集成回归通过 |
| R6 | 自动 Evidence 精确恢复，人工锁定和后续 Evidence 保持 | #570 / AC6 | satisfied | before/after 快照、版本/Owner 防护及人工品牌锁继承回归通过 |
| R7 | 运行中心展示取消/撤回过程、进度和统计 | #570 / AC7 | satisfied | Runtime 聚合、Contract、Client、Modal 统计和无重复记录测试通过 |
| R8 | Migration、分层验证、文档、Review、CI、main-fresh 完整 | #570 / AC8 | satisfied | Migration/Contract/PostgreSQL/Worker/Browser/真实全栈/文档/本地 Review 证据完整；PR CI 与合并后 main-fresh 由交付门禁继续验证 |

# 计划改动

| 模块 | 计划修改 | 原因 | 对应要求 |
| --- | --- | --- | --- |
| Replay tables/domain/repository/HTTP | 状态、操作账、编排、幂等 | 建立精确持久事实和公开能力 | R2—R7 |
| Content/Vehicle/Brand Owner | 条件式应用/恢复和生命周期审计 | 不绕过表 Owner | R4—R6 |
| Job/Worker registry | 新增可恢复撤回 Job | 长任务统一运行 | R2—R7 |
| Migration/database schema | 表、约束和索引 | 支撑并发、幂等、审计 | R2—R8 |
| Runtime/Contract/Frontend | 生命周期、统计和 Modal | 完成用户工作流 | R1—R3、R7 |
| Tests/generated/docs | 回归、生成一致性、事实同步 | 防止语义漂移 | R1—R8 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 生命周期、幂等、条件恢复、进度和 Modal |
| 接口 / 契约 | required | API、Runtime、Job payload、OpenAPI/Schema/Client |
| 集成 / 持久化 / 运行依赖 | required | PostgreSQL、部分提交、后来写入、共享来源、Evidence、重试 |
| 用户 / 工作流验收 | required | 运行中取消并撤回、终态撤回、旧请求禁用、结果展示 |
| 跨组件关键路径 | required | Modal → API → Job → PostgreSQL → Runtime → Browser |
| 外部依赖 / 供应方探测 | not_applicable | 不改变或调用 TikHub、LLM 等外部依赖 |
| 构建 / 打包 / 运行 | required | 后端静态、Migration、前端检查/测试/构建、Worker 注册 |
| 文档 / 治理 / 其他 | required | targeted 文档、完成审计、Review、PR CI、main-fresh、归档 |

## 验证计划

- 目标测试：Replay API/Contract、PostgreSQL Worker/撤回、Runtime、Browser Modal。
- 相关回归：Content lifecycle/contribution、Campaign revocation、Evidence、Job Runtime。
- 静态/构建：Ruff、Mypy、生成兼容、ESLint、typecheck、Vitest、Vite build。
- 真实边界：PostgreSQL 和少量 API + Worker + Browser 全栈；Provider Probe 不适用。
- 就绪：`python scripts/quality/check_change_completion.py --root . --require-active-ready`。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 处理 |
| --- | --- | --- |
| 主要风险 | 误撤其它来源、撤回并发、重试重复副作用 | freshness、先停子 Job、唯一约束、fencing、集成测试 |
| 兼容性 | 保留既有 API；新增操作和响应字段 | 同步生成消费者；旧请求明确不可撤回 |
| 数据 / Migration | 向前 Migration，不做历史猜测回填 | 新请求开始形成精确账 |
| 部署 / 运行 | 先迁移再部署 API/Worker/Frontend | 本任务不执行生产动作 |
| 回滚 / 恢复 | 代码可回滚，新增事实保留 | downgrade 前需确认无人依赖 |

# 文档、依赖、部署与发布影响

- **长期文档**：targeted 同步产品、数据库、任务/API/前端、统一入库和生命周期撤销。
- **依赖 / Runtime**：不新增、删除或升级。
- **配置 / Secret**：不变。
- **部署 / Release**：需要向前 Migration 和同版本发布；本任务不执行生产部署。
- **兼容**：生成 Client 同步；旧 Replay 不可撤回需在 UI 明示。

# 完成审计

- [x] upstream_re_read：已于 2026-09-23 重读 #570、用户确认、文档、Contract、Schema/Migration 和实现。
- [x] change_coverage：R1—R8 已逐项重建，交付阶段仍按 PR CI 与 main-fresh 门禁执行。
- [x] reverse_audit：已完成 Modal→API→Job→账本/Owner 与后端 lifecycle→Runtime→Modal/统计双向审计。
- [x] unresolved_cleared：`not_satisfied` 已清零；外部依赖探测为不适用，生产动作明确不在授权范围。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | 当前任务工作树 / PostgreSQL 18 dev | `pytest`：Replay API、Repository、Migration、Worker、Runtime | 63 passed | all-request 编排、账本、撤回、可见性、Evidence、纯 Evidence 版本稳定与运行中心 |
| V2 | 当前任务工作树 / PostgreSQL 18 dev | Replay Worker 定向复验 | 14 passed | queued 取消排队撤回、管理员审计、精确撤回、后写保护及 Analysis 版本保持 |
| V3 | 当前任务工作树 | Ruff format/check 全 CI 范围 + Mypy `backend/src` | 758 files formatted；lint passed；365 source files typed | Python 格式、静态质量和完整后端类型边界 |
| V4 | 当前任务工作树 / Alembic | `alembic current` + `alembic check` | `20260922_0059 (head)`；无新差异 | 向前迁移及模型一致性 |
| V5 | 当前任务工作树 | Contract 生成检查、兼容检查、Contract/Docs/CI Scope 测试 | 148 passed；生成与文档事实一致 | OpenAPI、生成 Client、兼容性和文档同步 |
| V6 | 当前任务工作树 / Node 24 | ESLint、Typecheck、Vitest、Vite build | 32 files / 227 tests；build passed | 前端静态、组件与生产构建 |
| V7 | 当前任务工作树 / Playwright Mock | `collection-runtime.spec.ts` | 18 passed | Modal、确认、取消并撤回与运行中心回归 |
| V8 | 当前任务工作树 / 真实 API+Worker+PostgreSQL+Browser | `canonical-replay-reversal.spec.ts` | 1 passed | 终态 Replay 从 UI 到持久撤回再回显的跨组件关键路径 |
| V9 | 当前任务工作树 | 独立 diff/根因/并发/迁移/回滚审查 | 无阻断 Finding；修正文档唯一键、重复导出、类型豁免并补取消/审计回归 | Review-and-fix 完成 |

## 未验证内容与剩余风险

- 生产 Migration、生产数据撤回和生产部署不在授权范围。
- 生产 Migration、生产数据撤回和生产部署未执行，符合明确非目标。

## 交付状态

- Issue：#570（open）。
- 分支：`feat/canonical-replay-cancel-revoke`。
- PR：#571（早期 PR 已创建，当前逻辑待推送）。
- CI / 合并 / 归档：Change 已 ready_for_review；等待 PR CI、受保护合并与自动归档。
- 发布 / 部署：不适用；用户只授权合并源码到 `main`。

## 备注

- 原工作区同步中断后有未确认残留；本任务在最新 `origin/main` 的隔离工作树施工，不触碰原工作区。
- Issue #570 已按当前 Requirement Source Contract 补齐并恢复多行语义段；由后续 `synchronize` CI 读取 live Issue 复核。
- CI 复核暴露 PR 模板文案与既有 GOV014 精确机器 marker 漂移；已将“当前仓库真实路径”同步为“仓库内真实存在的路径”，不改变允许来源范围。
