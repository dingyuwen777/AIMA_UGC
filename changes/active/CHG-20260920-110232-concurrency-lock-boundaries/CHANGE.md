---
schema: coding-change/v1
id: CHG-20260920-110232-concurrency-lock-boundaries
title: 修复并发读取阻塞与历史导入租约丢失
level: L2
status: in_progress
owner: dingyuwen777
branch: fix/concurrency-lock-boundaries
created: 2026-09-20
updated: 2026-09-20
completion_gate: required
depends_on: []
affected_areas:
  - backend
  - analysis
  - ingestion
  - jobs
  - testing
affected_paths:
  - backend/src/aima_ugc/bootstrap/analysis_identity.py
  - backend/src/aima_ugc/bootstrap/historical_import_worker.py
  - tests/unit/
  - tests/integration/
contracts:
  - Analysis Scheme active identity
  - PostgreSQL Durable Job Fencing
data_changes: []
---

# 变更摘要

- **要解决的问题**：并发读取 Analysis 配置时，已有 active Scheme 的请求仍进入带独占 advisory lock 的 bootstrap；历史导入 Chunk 又在长业务事务开始就锁定 Job 行，导致 Heartbeat 无法续租。
- **拟议修改**：把 Analysis 已初始化读取与空库 bootstrap 分流；Historical Import Chunk 在事务开始只校验 Fencing Token，最终提交前再锁定校验。
- **预期结果**：普通 Analysis 读请求不再被 Scheme registry 写锁串行化；长 Chunk 处理期间 Heartbeat 可以更新 Lease，最终业务提交仍受 Fencing 保护。

# 背景、现状与问题

Requirement Source 为 Issue #545。用户要求按既定修复方案完成代码修改、验证并合并到 `main`。

## 已确认事实

1. `active_analysis_configuration()` 每次都调用 `bootstrap_default()`；后者在检查 active Version 前取得事务级独占 advisory lock。
2. 多个 API 读取路径在同一请求事务中调用该函数，锁等待会占住已经 checkout 的数据库连接。
3. Historical Import Chunk 在长业务事务开始调用 `lock_current_execution()`，对 Job 行执行 `SELECT ... FOR UPDATE`。
4. Heartbeat 使用独立 Session 更新同一 Job 行；长事务持有行锁时，Heartbeat 会等待并可能错过 Lease。
5. 当前已有 `validate_current_execution()` 作为事务开始的无行锁校验，兼容 Import Worker 已采用“开始 validate、提交前 lock”的正常参照。

# 目标、成功标准与非目标

## 目标

- [ ] 已有 active Scheme 时直接读取，不进入带 registry 写锁的 bootstrap。
- [ ] 空库 bootstrap 仍由 advisory lock 保护，并发初始化只形成一个 active Version。
- [ ] Historical Import Chunk 长事务开始只校验当前 Fencing Token，不在处理期间锁住 Job 行。
- [ ] 最终业务提交前仍锁定并校验当前 Fencing Token。
- [ ] 两条失败机制都有 Red → Green 回归和真实 PostgreSQL 并发证据。
- [ ] PR current-head CI、独立 Review、guarded merge 与 main-fresh 收尾完成。

## 非目标

- 不在没有容量测量时调整连接池 `pool_size`、`max_overflow` 或 `pool_timeout`。
- 不改变公共 HTTP Contract、Pydantic/OpenAPI/generated client。
- 不改变数据库 Schema/Migration、Job Payload、Retry/Deadline 或 Worker 监督策略。
- 不升级依赖、Runtime 或构建工具。
- 不把调查中发现的相邻日志增强、进程监督或容量规划扩进本次修复。

## 必须保持不变

- 数据库唯一 active Analysis Scheme 与空库 bootstrap 的并发安全语义。
- Worker Lease、Heartbeat、Attempt Deadline、Fencing、取消和 Reaper 公共语义。
- Historical Import 的 Content/Evidence/账本/checkpoint 原子提交。
- 公共 API、Schema、依赖锁、启动、部署与 Release 方式。

# 修改方案与计划

## Step 1：固定 Analysis 读取回归

- **Requirement**：#545 AC1/AC3。
- **Owner / 行为**：Analysis identity 读取已有 active Version 时不调用 bootstrap。
- **修改范围**：`tests/unit/` 或现有 Analysis PostgreSQL Integration 测试。
- **可观察结果**：旧实现因仍调用 bootstrap 而失败；修复后读取成功且空库初始化语义不变。
- **直接 Evidence**：目标 pytest Red/Green 输出；必要时 PostgreSQL 并发测试。

## Step 2：固定 Historical Chunk Heartbeat/Fencing 回归

- **Requirement**：#545 AC2/AC3。
- **Owner / 行为**：Chunk 处理期间 Job 行可被 Heartbeat 更新，最终提交仍需当前 Fence。
- **修改范围**：`tests/integration/ingestion/test_stage12_historical_campaign_worker.py` 及必要测试辅助。
- **可观察结果**：旧实现下 Heartbeat 被事务行锁阻塞或调用序列不符合不变量；修复后处理期可续租，失效 Token 不能提交。
- **直接 Evidence**：真实 PostgreSQL Integration Red/Green。

## Step 3：最小生产修复

- **Requirement**：#545 AC1/AC2。
- **Owner / 行为**：Analysis 读取/初始化分流；Historical Chunk 开始 validate、提交前 lock。
- **修改范围**：`analysis_identity.py`、`historical_import_worker.py`。
- **可观察结果**：两条回归转绿，公共 Contract 与数据语义不变。
- **直接 Evidence**：目标测试、相关模块回归、diff 审查。

## Step 4：完成审计与交付

- **Requirement**：#545 AC4。
- **Owner / 行为**：质量门禁、Review、CI、合并和 post-merge 收尾。
- **修改范围**：Change/PR/Issue 状态与仓库既有自动归档链。
- **可观察结果**：current-head 门禁通过，guarded merge 后 main-fresh 通过，Issue Acceptance 有直接 Evidence。
- **直接 Evidence**：命令输出、PR/CI/head/merge/archive/Issue 回读。

# Requirement Traceability

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 已有 active Scheme 的读取不进入带 registry 写锁的 bootstrap；空库并发初始化仍安全 | #545 / AC1 | not_satisfied | 待 Red/Green 与 PostgreSQL 回归 |
| R2 | Historical Import Chunk 处理期间不锁 Job 行，Heartbeat 可续租；最终提交仍受 Fence 保护 | #545 / AC2 | not_satisfied | 待 Red/Green 与 PostgreSQL 回归 |
| R3 | 两条机制均有目标回归和真实 PostgreSQL Integration 证据 | #545 / AC3 | not_satisfied | 待目标测试与集成测试 |
| R4 | 相关回归、质量门禁与 current-head CI 通过，公共边界保持不变 | #545 / AC4 | not_satisfied | 待质量门禁、Review 与 CI |

# Validation Matrix

| 验证层 | 是否要求 | Scope / Evidence |
| --- | --- | --- |
| Behavior / Unit / Component | required | Analysis 已有 active Version 读取分支及 Historical Chunk 的开始/提交 Fence 不变量 |
| Contract / Consumer | not_applicable | 不改变 HTTP、Pydantic、OpenAPI、generated client 或 Job Payload |
| Integration / Persistence / Runtime Dependency | required | PostgreSQL advisory lock、Job 行锁、Heartbeat/Lease/Fencing 并发语义 |
| User / Workflow Acceptance | not_applicable | 不改变用户入口或工作流语义；原始运行时故障由真实生产入口的 PostgreSQL Integration 直接覆盖 |
| Real Cross-component Golden Path | not_applicable | 不改变前端/API/Worker 接线，且当前独立失败边界可在后端真实数据库层直接证明 |
| External Dependency / Provider Probe | not_applicable | 不改变 TikHub/LLM 或任何外部 Provider 边界 |
| Build / Package / Runtime | required | 仓库正式 Python 检查与 PR current-head CI |
| Docs / Governance / Other | required | Change Completion、架构/Owner/Secret/docs checks、两阶段 Review、PR/Issue 追溯 |

# 文档、兼容性、迁移与回滚

- **长期文档**：现有 Blueprint/模块文档已经要求 API 短事务、Heartbeat 不被外部/长工作阻塞、最终写入受 Fencing 保护；本次优先修实现与测试，完成前复核是否仍需 targeted 文档澄清。
- **Contract / Schema / Migration**：无变化。
- **依赖 / Runtime / lock**：无变化。
- **部署 / Release**：不创建 Release、不部署；合并后由既有发布流程消费。
- **回滚**：可 revert 本次 PR；无不可逆数据变化或迁移。

# Completion Audit

- [ ] upstream_re_read：Ready 前重新读取 #545、适用项目规则与当前实现事实。
- [ ] change_coverage：逐条比较 #545 AC1—AC4 与本 Change，确认没有遗漏或静默缩限。
- [ ] reverse_audit：从 active Scheme consumers 与 Historical Chunk/Heartbeat/Fence 两向反查实现和证据层。
- [ ] unresolved_cleared：`not_satisfied` 清零；所有 N/A 都有当前事实依据。

# 完成证据与交付状态

- Issue：#545，OPEN。
- Branch：`fix/concurrency-lock-boundaries`。
- PR：待首个失败回归/治理提交后创建早期 PR。
- Merge：未执行。
- Release / Deploy：不适用。
