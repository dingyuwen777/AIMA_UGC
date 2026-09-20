---
schema: coding-change/v1
id: CHG-20260920-110232-concurrency-lock-boundaries
title: 修复并发读取阻塞与历史导入租约丢失
level: L2
status: ready_for_review
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

## 背景

Requirement Source 为 Issue #545。用户要求按既定修复方案完成代码修改、验证并合并到 `main`。

## 当前现状

1. `active_analysis_configuration()` 每次都调用 `bootstrap_default()`；后者在检查 active Version 前取得事务级独占 advisory lock。
2. 多个 API 读取路径在同一请求事务中调用该函数，锁等待会占住已经 checkout 的数据库连接。
3. Historical Import Chunk 在长业务事务开始调用 `lock_current_execution()`，对 Job 行执行 `SELECT ... FOR UPDATE`。
4. Heartbeat 使用独立 Session 更新同一 Job 行；长事务持有行锁时，Heartbeat 会等待并可能错过 Lease。
5. 当前已有 `validate_current_execution()` 作为事务开始的无行锁校验，兼容 Import Worker 已采用“开始 validate、提交前 lock”的正常参照。

## 问题、根因或约束

- Analysis 读取路径把“读取已有 active Version”和“空库初始化”合并成同一条带写锁路径，造成不必要的读写互斥；并发请求在等待时继续占用连接，可能放大为连接池超时。
- Historical Import Chunk 把最终提交所需的 Job 行锁提前到长事务开始，Heartbeat 与业务事务发生自锁竞争，Lease 到期后最终 Fence 校验失败并回滚。

## 不修改的后果

- Scheme registry 有写事务时，原本只读的 Analysis 请求仍可能排队并占住连接，继续放大 API 超时风险。
- 处理时间接近或超过 Lease 的 Chunk 仍可能阻塞自身 Heartbeat，造成重复尝试、失败回滚和 Worker 退出风险。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 已有 active Version 时，`active_analysis_configuration()` 仍调用先取 advisory lock 的 `bootstrap_default()` | `backend/src/aima_ugc/bootstrap/analysis_identity.py`、Scheme Repository 当前实现 | 读取已有配置应先走无写锁快路径；仅空库进入 bootstrap |
| E2 | Chunk 长事务开始即对 Job 行执行 `SELECT ... FOR UPDATE`，Heartbeat 通过独立事务更新同一行 | `backend/src/aima_ugc/bootstrap/historical_import_worker.py`、`PostgresJobRepository` | 事务开始只能无锁校验 Fence，提交前才锁定校验 |
| E3 | 普通 Import Worker 已采用“开始 validate、提交前 lock”的边界 | `backend/src/aima_ugc/bootstrap/import_worker.py` | Historical Import 可复用同一既有不变量，无需新机制 |
| E4 | 项目规范要求 API 短事务及持久 Job 的 Lease、Heartbeat、Fencing | 根 `AGENTS.md` 与 Blueprint | 修复必须保留最终原子提交和 Fencing，不能以关闭安全机制止血 |
| E5 | Issue 已把修复边界固化为 AC1—AC4 | `#545` | Change、实现、测试和交付逐条绑定稳定 Acceptance |

## 推断与待确认

- 已确认上述两条机制能够造成连接等待和 Lease 丢失；事故发生时最初持锁事务的业务来源没有现场 `pg_locks` 快照，不能把某个具体请求断言为唯一首因。该未知项不阻塞切断已确认的放大路径。

# 目标、成功标准与非目标

## 目标

- 已初始化的 Analysis 配置读取不进入 registry 写锁路径，同时保留空库并发初始化的唯一 active 语义。
- Historical Import Chunk 处理期间 Heartbeat 可以续租，最终业务提交仍由当前 Fencing Token 保护。

## 成功标准

- [x] 已有 active Scheme 时直接读取，不进入带 registry 写锁的 bootstrap。
- [x] 空库 bootstrap 仍由 advisory lock 保护，并发初始化只形成一个 active Version。
- [x] Historical Import Chunk 长事务开始只校验当前 Fencing Token，不在处理期间锁住 Job 行。
- [x] 最终业务提交前仍锁定并校验当前 Fencing Token。
- [x] 两条失败机制都有 Red → Green 回归和真实 PostgreSQL 并发证据。
- [ ] PR current-head CI、独立 Review、guarded merge 与 main-fresh 收尾完成。

## 范围

- Analysis Scheme active identity 的读取/空库初始化分流。
- Historical Import Chunk 的事务开始与最终提交 Fence 边界。
- 对应真实 PostgreSQL 并发回归、质量门禁和交付证据。

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

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 仅修改 Analysis bootstrap 与 Historical Import Worker 两处 Owner 实现及回归 | E1—E5 | 不扩展到连接池容量、Worker 监督或日志改造 |
| 接口与契约 | 不改变公共 HTTP、Pydantic/OpenAPI、generated client 或 Job Payload | E1—E5 | 调用方无需适配 |
| 数据与迁移 | 不改变 Schema、Migration 或历史数据 | E1—E3 | 无迁移、回填和不可逆数据操作 |
| 错误与失败语义 | 保留 Lease、Deadline、取消、重试和 Fence 失败语义，只消除错误的锁边界 | E2—E4 | 过期执行仍不能提交，Heartbeat 获得正常续租窗口 |
| 兼容性 | 保持唯一 active Scheme、业务原子提交和所有合法输入输出 | E1—E4 | 修复只改变内部同步时机 |
| 部署与回滚 | 普通代码合并，无额外配置/迁移/发布动作；可整体 revert PR | E4 | 无独立部署或数据恢复步骤 |

# 修改方案与决策依据

## 最小充分方案

### Step 1：固定 Analysis 读取回归

- **Requirement**：#545 AC1/AC3。
- **Owner / 行为**：Analysis identity 读取已有 active Version 时不调用 bootstrap。
- **修改范围**：`tests/unit/` 或现有 Analysis PostgreSQL Integration 测试。
- **可观察结果**：旧实现因仍调用 bootstrap 而失败；修复后读取成功且空库初始化语义不变。
- **直接 Evidence**：目标 pytest Red/Green 输出；必要时 PostgreSQL 并发测试。

### Step 2：固定 Historical Chunk Heartbeat/Fencing 回归

- **Requirement**：#545 AC2/AC3。
- **Owner / 行为**：Chunk 处理期间 Job 行可被 Heartbeat 更新，最终提交仍需当前 Fence。
- **修改范围**：`tests/integration/ingestion/test_stage12_historical_campaign_worker.py` 及必要测试辅助。
- **可观察结果**：旧实现下 Heartbeat 被事务行锁阻塞或调用序列不符合不变量；修复后处理期可续租，失效 Token 不能提交。
- **直接 Evidence**：真实 PostgreSQL Integration Red/Green。

### Step 3：最小生产修复

- **Requirement**：#545 AC1/AC2。
- **Owner / 行为**：Analysis 读取/初始化分流；Historical Chunk 开始 validate、提交前 lock。
- **修改范围**：`analysis_identity.py`、`historical_import_worker.py`。
- **可观察结果**：两条回归转绿，公共 Contract 与数据语义不变。
- **直接 Evidence**：目标测试、相关模块回归、diff 审查。

### Step 4：完成审计与交付

- **Requirement**：#545 AC4。
- **Owner / 行为**：质量门禁、Review、CI、合并和 post-merge 收尾。
- **修改范围**：Change/PR/Issue 状态与仓库既有自动归档链。
- **可观察结果**：current-head 门禁通过，guarded merge 后 main-fresh 通过，Issue Acceptance 有直接 Evidence。
- **直接 Evidence**：命令输出、PR/CI/head/merge/archive/Issue 回读。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1：已有 active Version 先直接读取，未命中才 bootstrap | E1、E4 | 把普通读请求移出独占锁路径，同时 bootstrap 内部重检继续保证空库并发安全 |
| D2：Chunk 开始 validate，提交前 lock | E2、E3、E4 | Heartbeat 在长处理期可更新 Job 行，最终锁定校验仍阻止失效执行提交 |
| D3：不调整连接池容量或扩大 Worker 行为 | E1—E5 | 容量调整不能切断已确认锁竞争，且缺少独立容量测量和上游 Acceptance |

## 备选方案与取舍

- 只扩大数据库连接池：只能推迟连接耗尽，不能消除 Scheme 写锁导致的连接占用，未采用。
- 延长 Historical Import Lease：只能降低部分复现概率，Heartbeat 仍会被同一事务行锁阻塞，未采用。
- 拆分整个 Chunk 为多个事务：会改变导入原子性、checkpoint 和失败语义，超出本次已确认问题的最小充分边界，未采用。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 已有 active Scheme 的读取不进入带 registry 写锁的 bootstrap；空库并发初始化仍安全 | #545 / AC1 | satisfied | `test_analysis_identity_locking.py` 两项真实 PostgreSQL 回归；Red 命中 advisory lock，Green 2/2；实现只在 active 未命中时 bootstrap |
| R2 | Historical Import Chunk 处理期间不锁 Job 行，Heartbeat 可续租；最终提交仍受 Fence 保护 | #545 / AC2 | satisfied | Heartbeat Red 命中 `jobs` tuple lock，Green 通过；事务开始 `validate_current_execution`、提交前保留 `lock_current_execution`；Job Runtime 13/13 |
| R3 | 两条机制均有目标回归和真实 PostgreSQL Integration 证据 | #545 / AC3 | satisfied | 隔离 PostgreSQL 18 目标 3/3、database + ingestion 130/130、jobs 13/13 |
| R4 | 相关回归、质量门禁与 current-head CI 通过，公共边界保持不变 | #545 / AC4 | explicitly_deferred | 本地相关回归、Ruff 与独立 Review 已通过且 Contract/Schema/lock 无 diff；仓库 CI 设计要求 Change Ready 后执行，current-head Green 是 merge 前硬门禁 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| `backend/src/aima_ugc/bootstrap/analysis_identity.py` | active 读取快路径，空库才 bootstrap | 消除普通读取的不必要 registry 写锁 | R1 / E1 |
| `backend/src/aima_ugc/bootstrap/historical_import_worker.py` | 长事务开始无锁 validate，最终提交保留 lock | 解除 Heartbeat 与业务事务的 Job 行锁竞争 | R2 / E2、E3 |
| `tests/integration/database/test_analysis_identity_locking.py` | 新增真实 PostgreSQL advisory lock 与并发空库回归 | 直接证明读锁边界和唯一 active 语义 | R1、R3 |
| `tests/integration/ingestion/test_stage12_historical_campaign_worker.py` | 新增长事务期间 Heartbeat 回归 | 直接证明处理期可续租和最终完成 | R2、R3 |
| 当前 Change / PR / Issue | 同步追溯、证据、审计和交付状态 | 满足持久 L2 交付门禁 | R4 / E5 |

- [x] 调查当前实现和事实源
- [x] 建立任务路由和验证矩阵
- [x] 行为变化取得失败证据
- [x] 完成最小实现
- [x] 复核长期文档影响
- [x] 取得覆盖当前版本的验证证据
- [x] 完成需求追溯、完成审计和适用复核

# 验证矩阵

| 验证层 | 是否要求 | Scope / Evidence |
| --- | --- | --- |
| Behavior / Unit / Component | required | 目标 3/3、相关 unit/API 9/9；覆盖 active 读取、空库并发与 Historical Chunk Heartbeat |
| Contract / Consumer | not_applicable | 不改变 HTTP、Pydantic、OpenAPI、generated client 或 Job Payload |
| Integration / Persistence / Runtime Dependency | required | 隔离 PostgreSQL 18：database + ingestion 130/130、jobs 13/13；覆盖 advisory lock、行锁、Heartbeat/Lease/Fencing |
| User / Workflow Acceptance | not_applicable | 不改变用户入口或工作流语义；原始运行时故障由真实生产入口的 PostgreSQL Integration 直接覆盖 |
| Real Cross-component Golden Path | not_applicable | 不改变前端/API/Worker 接线，且当前独立失败边界可在后端真实数据库层直接证明 |
| External Dependency / Provider Probe | not_applicable | 不改变 TikHub/LLM 或任何外部 Provider 边界 |
| Build / Package / Runtime | required | 目标文件 Ruff 已通过；完整仓库检查与 PR current-head CI 在 Ready 后执行 |
| Docs / Governance / Other | required | Change 机器契约通过；独立 Review 无 Finding；PR current-head 治理/CI 在 Ready 后执行 |

## 验证计划

- 目标测试：Analysis identity 两项 PostgreSQL 并发测试；Historical Chunk Heartbeat 测试。
- 相关回归：Analysis、Job、Historical Campaign 相关测试及 CI 选定后端套件。
- 静态检查或构建：Ruff、类型/仓库质量门禁、Wheel/运行检查由正式 CI 覆盖。
- 专项真实边界：GitHub Runner 的隔离 PostgreSQL；本地数据库未证明隔离，不执行会 `TRUNCATE` 的集成夹具。
- 就绪检查：`uv run python scripts/quality/check_change_completion.py --root . --require-active-ready`。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 快路径可能削弱空库并发初始化；Fence 调整可能允许失效执行提交 | 用并发空库唯一 active 测试和最终提交锁定校验覆盖 |
| 兼容性 | 保持公共接口、数据和合法行为 | 只改变内部锁取得时机，不改 Contract/Schema/Payload |
| 数据 / Migration | 不适用 | 无 Schema、Migration、回填或数据格式变化 |
| 部署 / 运行 | 普通代码变更 | 不改变配置、进程拓扑、依赖或启动方式 |
| 回滚 / 恢复 | 可 revert 本 PR | 无迁移和不可逆数据变化；若回归可恢复原实现 |

# 文档、依赖、部署与发布影响

- **长期文档**：现有 Blueprint/模块文档已经要求 API 短事务、Heartbeat 不被外部/长工作阻塞、最终写入受 Fencing 保护；本次优先修实现与测试，完成前复核是否仍需 targeted 文档澄清。
- **依赖 / Runtime**：不新增、删除或升级依赖，不修改锁文件和 Runtime。
- **配置 / Secret**：不改变配置面、默认值或 Secret 处理。
- **部署 / Release**：不创建 Release、不部署；本次只合并到 `main`。
- **兼容 / 消费方通知**：不改变公共 Contract、Schema、Payload 或人工流程，无需消费方适配。

# 完成审计

- [x] upstream_re_read：已重新读取 #545、适用项目规则、Scheme/Job Repository、两条入口及当前 diff。
- [x] change_coverage：已从 #545 AC1—AC4 独立重建完成定义；R1—R3 已满足，R4 的 Runner/merge 生命周期按仓库工作流明确延期且保持硬门禁。
- [x] reverse_audit：已从 active Scheme consumers 反查读取/空库分流，并从 Chunk → Heartbeat → Lease takeover → 最终 Fence 反查事务边界与真实 PostgreSQL 证据。
- [x] unresolved_cleared：无 `not_satisfied`；不适用层均基于无公共 Contract、UI、跨组件或外部 Provider 变化；仅剩 Ready 后 current-head CI/merge 生命周期。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | `02e27512` / 本地 | `uv run ruff check ...` | 通过 | 新增回归测试满足静态规范 |
| V2 | `02e27512` / 本地 | 目标 pytest `--collect-only` | 收集 17 项 | 测试模块可导入，目标用例进入正式收集 |
| V3 | `02e27512` / GitHub Runner | PR run `35485986763` | 前置 Change 机器契约失败，PostgreSQL Integration 被跳过 | 该失败不是功能 Red，未冒充缺陷证据 |
| V4 | 修复前生产实现 / 本地隔离 PostgreSQL 18 | 目标 Analysis lock 测试 | `LockNotAvailable` at `pg_advisory_xact_lock`；空库并发对照通过 | active 读取确实错误进入独占 registry 锁；并发 bootstrap 测试基线有效 |
| V5 | 修复前生产实现 / 本地隔离 PostgreSQL 18 | Historical Chunk Heartbeat 目标测试 | `LockNotAvailable` while updating tuple in `jobs` | 长业务事务提前锁 Job 行会真实阻塞 Heartbeat |
| V6 | `17991db9` / 本地隔离 PostgreSQL 18 | 三条目标测试 | 3 passed | 两条 Red 已转 Green，空库唯一 active 保持 |
| V7 | `17991db9` / 本地隔离 PostgreSQL 18 | `pytest tests/integration/database tests/integration/ingestion -q` | 130 passed | Analysis 数据库行为与 Historical Import 相邻状态/持久化回归通过 |
| V8 | `17991db9` / 本地隔离 PostgreSQL 18 | `pytest tests/integration/jobs -q` | 13 passed | Heartbeat、Lease takeover、stale token 与通用 Fence 语义保持 |
| V9 | `17991db9` / 本地 | 相关 unit/API pytest；目标文件 Ruff | 9 passed；All checks passed | 相邻装配/API 与静态规范通过 |
| V10 | `17991db9` / 独立 Review | #545 → 调用链/diff → tests/evidence 复核 | `NO_FINDINGS_WITHIN_SCOPE` | 最终 Fence、空库 bootstrap、兼容与测试证据未发现阻塞问题 |
| V11 | final PR head / GitHub Runner | current-head required CI | 待 Change Ready 后执行 | merge 前硬门禁，不以前序失败或本地证据替代 |

## 未验证内容与剩余风险

- 事故现场没有 `pg_locks` 快照，无法确认唯一首个持锁请求；本次已切断两个代码级、可重复的锁放大机制。
- current-head GitHub CI、guarded merge、main-fresh、Change Archive、Issue Closure 与分支清理尚未发生；在实际完成前不宣称交付完成。

## 交付状态

- Issue：#545，OPEN。
- Branch：`fix/concurrency-lock-boundaries`。
- PR：#546，当前实现与本地证据已就绪，等待 final-head CI。
- CI：前序 run `35485986763` 的 Change 机器契约失败已修正；final-head CI 待本次 Ready 提交推送后执行。
- Merge：未执行。
- Release / Deploy：不适用。

## 备注

- 事故当时没有保存 `pg_locks` 快照，因此不声称已识别唯一首个持锁请求；当前修复针对代码中已确认且可复现的两条锁放大机制。
