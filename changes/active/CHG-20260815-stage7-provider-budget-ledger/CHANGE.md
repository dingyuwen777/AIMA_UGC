---
schema: rvc-change/v1
id: CHG-20260815-stage7-provider-budget-ledger
title: 建立 Stage 7 Provider 多级预算账本
level: L3
status: ready_for_review
owner: dingyuwen777
branch: feature/stage7-provider-budget-ledger
created: 2026-08-15
updated: 2026-08-15
depends_on: []
affected_areas: [collection, system, database, provider, testing, documentation]
affected_paths: [backend/src/aima_ugc/modules/collection/, backend/src/aima_ugc/adapters/persistence/postgres/, backend/src/aima_ugc/database_schema.py, migrations/versions/20260815_0012_stage7_provider_budget_ledger.py, tests/unit/collection/, tests/integration/collection/, docs/blueprint/03-数据库与文件存储.md, docs/blueprint/README.md, backend/src/aima_ugc/modules/collection/README.md, .github/workflows/stage7-provider-budget-ledger.yml]
contracts: []
data_changes: [provider_requests.provider_config_id, provider_budget_accounts, provider_budget_reservations]
---

# 目标

建立 Stage 7 已批准的最终 Provider 多级预算 Ledger，使真实计费 Attempt 在进入 Provider 发送边界前必须取得数据库硬预算预留，并在 completed/not_sent/unknown 终态分别结算、释放或保守占用；同时把 Provider Request 与稳定 `provider_config_id` 建立持久化关联，避免不同 Provider 配置实例混用额度。

# 成功标准

- [x] `provider_requests` 通过附加 Migration 增加可追溯的 `provider_config_id` 外键；历史 Revision `20260813_0001`—`20260815_0011` 未改写。
- [x] 新建 Collection Owner 的 `provider_budget_accounts/provider_budget_reservations`，账户支持 `global/run/run_comments/content_comments` 四层、`request_count/monetary_cost` 两种维度，并绑定稳定 `provider_config_id`。
- [x] 同 Provider Config、Scope、维度、单位的预算周期不能重叠；账户范围、时间、金额、单位和关系由 PostgreSQL CHECK/FK/Exclusion/Unique 约束保护。
- [x] 一次 billable Attempt 的普通 Operation 原子预留 `global + run`；评论/回复在提供内部 `content_id` 时原子预留 `global + run + run_comments + content_comments`；每层同时保留请求次数和货币预算。
- [x] 任一必需账户缺失、超额、Provider Config/Run 不匹配或 Reservation 不完整时 fail closed；`ProviderDispatchService` 不得调用 Transport。
- [x] 同一 Attempt 的预留事务重放幂等，不重复扣减；新 Attempt 独立预留，并发额度竞争由账户行锁串行裁决。
- [x] `completed` 把请求次数和实际费用结算到 `settled_amount`；实际费用高于预留仍如实记录，账户进入超额状态后后续 reserve 会被同一 `used + 本次预留 <= limit` 规则阻断。
- [x] `not_sent` 全量释放；`unknown` 把原预留转入 `unknown_amount` 并继续占预算，禁止把未知计费当未发送释放。
- [x] 预算账户提供从 Reservation 重算余额的审计入口，数据库累计值与账本不一致时明确报 drift。
- [x] Stage 5C/5D/Stage 6 既有不计费 Fake、Dispatch、Recovery、Raw/Candidate/Ingestion 兼容边界未被本实现改写；PR 广域回归仍作为合并门禁。
- [x] `20260815_0011 → head`、`base → head`、downgrade/upgrade round trip 和 `alembic check` 已在 PostgreSQL 18.4 Stage 7 Budget CI 获得新鲜 Green 证据。
- [x] Ruff、mypy、Architecture、Table Ownership、Secret Scan、Docs、Contract 生成/兼容门禁已在分支 CI Green。
- [ ] PR 广域 CI、合并后 main CI 和 main 机器事实重新验证完成；满足前不得归档 Change。

# 范围

- Provider Request 稳定 `provider_config_id` 持久化关联。
- Provider Budget Account / Reservation 数据模型、Table、Migration、Repository/Service。
- 普通 Attempt 两层预算和评论 Attempt 四层预算的原子 reserve。
- Dispatch 发送前 fail-closed 预算门禁。
- Dispatch/Recovery 终态 settle/release/unknown。
- Reservation 幂等、并发竞争、超额和账本 drift 审计。
- 本单元独立 Unit/PostgreSQL CI 与受影响长期文档。

# 非目标

- 不建立 `collection_plans`、Plan Platform、Occurrence 或 Run Snapshot。
- 不实现 Scheduler，不决定 `misfire_policy`、`max_catch_up_runs` 或停机 catch-up 行为。
- 不实现 Provider 价格发现、TikHub 价格硬编码、自动充值、账单拉取或财务对账 API。
- 不新增 HTTP API、OpenAPI、前端预算页面或 Stage 8 业务页面。
- 不调用真实付费 Provider；本 Change 使用 Fake Transport 和 PostgreSQL 验证发送门禁。
- 不修改四个平台 Mapper/Fixture/Capability/Registry 状态。
- 不实现 Retention、生产容量、SLO、RPO/RTO 或部署生产环境。

# 必须保持不变

- 已发布 Revision `20260813_0001`—`20260815_0011` 不改写，只新增 `0012`。
- Provider Client 继续一次 Attempt 最多一次 Transport send；真正重发必须创建新 Attempt。
- Raw 仍由 ArtifactService/RawArtifactService 管理，Provider/Mapper/Repository Owner 边界不改变。
- `not_billable` Fake/文件型 Attempt 不强行要求货币预算，既有 Stage 5D 测试语义保持兼容。
- Secret/API Key/Token 不进入 Budget 表、Request 参数、日志、Change、Fixture 或测试输出。
- Provider Config 由 System Owner 管理；Budget 表与 Provider Request/Attempt 仍由 Collection Owner 管理。
- `provider_config_id` 表达稳定配置实例身份；同 Provider 类型的不同配置实例预算严格隔离。

# 已确认设计依据

1. Blueprint 02 已冻结：Stage 5C 暂保留 `provider` 字段兼容，稳定 `provider_config_id` 的 Request 持久化关联由后续 Plan/Run/Budget Stage 7 Migration 增加。
2. Blueprint 07/08 已冻结：最终预算账户为 `global/run/run_comments/content_comments`；所有真实 HTTP Attempt 至少预留 global+run，评论/二级评论同时预留四层；预算账户绑定稳定 Provider Config。
3. Blueprint 03 已同步到当前 Stage 7 机器事实：账户行锁、同事务全有或全无、同 Attempt Reservation 唯一、未知费用继续占用、实际费用超预留仍如实结算，并明确四层两维和稳定 Provider Config。
4. 预算直接父事实 `collection_runs`、`contents`、`provider_requests/provider_request_attempts` 与 `provider_configs` 已进入 main；预算表不依赖尚未批准的 Scheduler misfire 值，因此 Scheduler 门禁不阻塞本单元。

# 方案比较

## 方案 A：最终 PostgreSQL Ledger + Dispatch 门禁（采用）

按已批准四层模型一次建立最终 Account/Reservation，并让 billable Attempt 在 `reserved → dispatching` CAS 前检查完整 Reservation，终态与 Provider Attempt 在同一短事务结算。优点是并发正确、可审计、无临时弱约束表，且直接满足 Stage 7 预算成功标准。

## 方案 B：只建预算表，暂不接 Dispatch（拒绝）

DDL 可以先完成，但无法证明“无预算绝不发真实请求”，会留下可绕过的生产路径，不构成闭环。

## 方案 C：内存计数器或配置文件额度（拒绝）

不能跨 Worker 原子约束、无法处理崩溃后的 unknown 计费，也不具备数据库审计链，违反当前 Blueprint。

# 实施结果

1. Red：提交 L3 Change、预算 Requirement、PostgreSQL reserve/并发/终态/审计、Dispatch fail-closed 测试与独立 CI；Run `31872227188` Unit Job 因 `aima_ugc.modules.collection.provider_budget` 尚不存在而退出 2，依赖安装/锁检查先成功，确认是正确功能 Red。
2. Green：新增 Budget 模型/Service、Collection Owner Tables、PostgreSQL Repository 和 `20260815_0012`；为 Provider Request 增加兼容可空的稳定 Config 关联，并新增 billable `estimated` Attempt 创建路径。
3. Dispatch/Recovery：正常发送和遗留 `dispatching` 恢复共享预算终态持久化 helper；发送前必须通过 Job Fence + 完整 Reservation 检查，未通过时不调用 Transport。
4. Refactor/兼容：保持旧 `not_billable` Repository 调用兼容；修正 Reservation replay 返回顺序、Ruff 格式/导入和 mypy Literal/参数类型，不降低测试或静态门禁。
5. 文档：同步 Collection README、Blueprint 03 与 Blueprint README；只描述预算单元已建立，不宣称整个 Stage 7 完成。
6. 分支验证：Run `31873153498` 的 Unit/PostgreSQL/Quality 三个 Job 全部成功；Quality 实际执行 Ruff、mypy、Contract、Architecture、Table Ownership、Secret Scan 和 Docs。文档最终提交后的 PR/merge CI 仍待完成。

# Review

## 阶段一：需求符合性

- 当前差异只覆盖稳定 Provider Config、预算 Ledger、Dispatch/Recovery 接线、对应测试/Migration/CI/文档；没有实现 Plan、Occurrence、Scheduler、前端或真实 Provider Transport。
- 历史 Revision 未改写；新 Revision 父节点固定 `20260815_0011`。
- Blueprint 03 原有三层预算摘要与较新的 Blueprint 08 冲突，已按当前批准四层模型和机器事实同步；没有把未批准 Scheduler 值补进 Schema。
- Provider Secret、API Key、Token、真实价格均未进入代码、测试数据或 Change。

## 阶段二：代码质量

- Reserve 使用 PostgreSQL 行锁和单事务全有或全无；同 Provider Config 的当前 enabled 账户按稳定 ID 顺序加锁，正确性优先，代价是同 Config 下不相关 Scope 的 reserve 可能被额外串行化，属于后续测量后再优化的性能风险，不影响当前正确性。
- `not_sent/released`、`unknown/unknown_amount`、`completed/settled actual` 与 Provider Attempt 终态同事务提交；Recovery 复用同一 helper，避免崩溃后预算悬挂。
- 历史/测试 `not_billable` Attempt 不强制预算；新的 billable Attempt 必须显式绑定 Provider Config 和 estimated Billing。
- Exclusion Constraint 依赖 PostgreSQL `btree_gist`；Migration 只创建缺失 Extension，downgrade 不删除可能被共享使用的 Extension。
- 账户聚合 drift 有显式审计错误，不自动篡改账本掩盖问题。
- PR 广域回归、合并后 main 复验仍是未完成门禁，因此当前 Change 仅为 `ready_for_review`。

# 验证证据

## Red

- `uv run pytest tests/unit/collection/test_provider_budget.py -q`：CI 收集阶段因生产预算模块不存在失败，退出码 2；Run `31872227188`。

## 已通过的 Green / Regression

- `uv lock --check`
- `uv sync --locked`
- Stage 7 Budget Unit：预算 Unit + Stage 5C/5D Provider Persistence/Dispatch Unit。
- Stage 7 Budget PostgreSQL：`upgrade head`、`alembic current/check`、预算/Provider Repository/Dispatch Integration、`0011 → head`、`base → head` 往返。
- Stage 7 Budget Quality：Ruff format/check、mypy、Contract generate/compatibility、Architecture、Table Ownership、Secret Scan、Docs。
- 已确认 Green Run：`31873153498`。

## 待合并门禁

- PR 实际触发的所有相关 Workflow/Job 全绿；
- 合并后 main HEAD 包含本单元；
- main 上相关 CI 新鲜全绿；
- Change 再更新 `done` 并移入 archive；
- 本任务分支在 archive 合并后清理。

# 兼容、Migration、部署与回滚

- 兼容：新增 `provider_requests.provider_config_id` 可空列；历史/不计费 Request/Attempt 保持可读可回归。新 billable 路径必须显式绑定 Provider Config。
- Migration：新增 `20260815_0012`，父 Revision 固定 `20260815_0011`；不改写历史 Revision。
- 部署：使用 billable Provider Dispatch 前必须先升级到 `0012` 并配置覆盖调用时刻的账户；账户缺失时按设计关闭失败，不降级成无预算发送。
- 回滚：结构可 downgrade 到 `0011`；若新表已有业务账本，downgrade 会删除 Budget 数据且移除 Request Config 关联，执行前必须备份/导出，不能宣称无损回滚。

# 安全、性能与运维风险

- Budget 仅保存 UUID、范围、周期、额度和费用数字，不保存 Credential；Secret Scan 继续作为 CI 门禁。
- reserve 为保证稳定锁序当前会锁同 Provider Config 在调用时刻 enabled 的账户，再筛选必需键；这可能增加高并发串行化，后续只有在真实负载证明必要时再收窄锁查询，不能以牺牲并发正确性换优化。
- 实际费用超过估算时保留真实 settled 数字并阻断后续额度，不允许截断到上限制造假账。
- `unknown_amount` 是保守容量占用，需要未来独立账单/人工对账能力才能释放；本 Change 不伪造自动 reconciliation。
- `btree_gist` 需要 Migration 账号具备首次创建 Extension 的权限；生产部署前应在目标 PostgreSQL 权限基线中确认。

# Git

- 基线 main：`d44397ae076b5502de310f6f617c85457131d7be`
- 分支：`feature/stage7-provider-budget-ledger`
- 用户本地工作区：当前宿主不可见，不能确认 modified/staged/untracked/未推送提交
- Red Commit：`ebc8f220ce73bd454f45102fca154d7979dd7665`
- 核心 Green Commit：`3b40b308a893a6cf9db7d938906047d296ac26ba`
- 后续兼容/质量/文档提交：均在同一任务分支，未重写历史
- PR：待创建
- CI：分支实现 Run `31873153498` 已 Green；PR/合并后 CI 待执行
- 合并：未合并
- Change：`ready_for_review`；未满足 main 集成条件，不得归档
