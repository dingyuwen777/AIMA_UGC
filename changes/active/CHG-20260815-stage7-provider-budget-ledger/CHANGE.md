---
schema: rvc-change/v1
id: CHG-20260815-stage7-provider-budget-ledger
title: 建立 Stage 7 Provider 多级预算账本
level: L3
status: active
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

- [ ] `provider_requests` 通过附加 Migration 增加可追溯的 `provider_config_id` 外键；历史 Revision `20260813_0001`—`20260815_0011` 不改写。
- [ ] 新建 Collection Owner 的 `provider_budget_accounts/provider_budget_reservations`，账户支持 `global/run/run_comments/content_comments` 四层、`request_count/monetary_cost` 两种维度，并绑定稳定 `provider_config_id`。
- [ ] 同 Provider Config、Scope、维度、单位的预算周期不能重叠；账户范围、时间、金额、单位和关系由 PostgreSQL 约束保护。
- [ ] 一次 billable Attempt 的普通 Operation 原子预留 `global + run`；评论/回复在提供内部 `content_id` 时原子预留 `global + run + run_comments + content_comments`；每层同时保留请求次数和货币预算。
- [ ] 任一必需账户缺失、超额、Provider Config/Run 不匹配或 Reservation 不完整时 fail closed；`ProviderDispatchService` 不得调用 Transport。
- [ ] 同一 Attempt 的预留事务重放幂等，不重复扣减；新 Attempt 必须独立预留。
- [ ] `completed` 把请求次数和实际费用结算到 `settled_amount`；实际费用高于预留仍如实记录并使后续请求受超额状态阻断。
- [ ] `not_sent` 全量释放；`unknown` 把原预留转入 `unknown_amount` 并继续占预算，禁止把未知计费当未发送释放。
- [ ] 预算账户提供从 Reservation 重算余额的审计入口，数据库累计值与账本不一致时明确报 drift。
- [ ] Stage 5C/5D/Stage 6 既有不计费 Fake、Dispatch、Recovery、Raw/Candidate/Ingestion 回归保持通过。
- [ ] `20260815_0011 → head`、`base → head`、downgrade/upgrade round trip 和 `alembic check` 均有 PostgreSQL 18.4 新鲜证据。
- [ ] Ruff、mypy、Architecture、Table Ownership、Secret Scan、Docs、Contract 生成/兼容门禁通过。
- [ ] 合并后 main 对本单元相关 CI 重新验证；长期文档与机器事实同步后才允许 Change done/archive。

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
3. Blueprint 03 已冻结并发 reserve/settle/release/unknown 基础算法：账户行锁、同事务全有或全无、同 Attempt Reservation 唯一、未知费用继续占用、实际费用超预留仍如实结算。
4. 预算直接父事实 `collection_runs`、`contents`、`provider_requests/provider_request_attempts` 与 `provider_configs` 已进入 main；预算表不依赖尚未批准的 Scheduler misfire 值，因此 Scheduler 门禁不阻塞本单元。

# 方案比较

## 方案 A：最终 PostgreSQL Ledger + Dispatch 门禁（采用）

按已批准四层模型一次建立最终 Account/Reservation，并让 billable Attempt 在 `reserved → dispatching` CAS 前检查完整 Reservation，终态与 Provider Attempt 在同一短事务结算。优点是并发正确、可审计、无临时弱约束表，且直接满足 Stage 7 预算成功标准。

## 方案 B：只建预算表，暂不接 Dispatch（拒绝）

DDL 可以先完成，但无法证明“无预算绝不发真实请求”，会留下可绕过的生产路径，不构成闭环。

## 方案 C：内存计数器或配置文件额度（拒绝）

不能跨 Worker 原子约束、无法处理崩溃后的 unknown 计费，也不具备数据库审计链，违反当前 Blueprint。

# 实施任务

1. Red：先加入预算 Requirement、PostgreSQL reserve/并发/终态/审计、Dispatch fail-closed 测试与独立 CI；实际观察因生产预算模块/Migration 缺失而失败。
2. Green：最小增加 Budget 模型/Service、Collection Owner Tables、PostgreSQL Repository 和 `20260815_0012`。
3. Dispatch：在现有 Provider Persistence 中增加稳定 Config 关联与 billable Attempt；发送前验证 Reservation，终态同事务 settle/release/unknown；不改一次发送边界。
4. Refactor：只消除本 Change 新代码的重复和质量问题，不整理无关模块。
5. 文档：同步 Collection README、Blueprint 03 与 Blueprint README；不得把本单元完成写成整个 Stage 7 完成。
6. Review/集成：需求符合性 → 代码质量 → PR CI → merge → main CI → Change done/archive → 删除本任务分支。

# 验证计划

## Red

- `uv run pytest tests/unit/collection/test_provider_budget.py -q`
- `uv run pytest tests/integration/collection/test_provider_budget.py -q`
- GitHub Actions `Stage 7 Provider Budget Ledger` 的 Unit/PostgreSQL Job。

## Green / Regression

- `uv lock --check`
- `uv sync --locked`
- `uv run pytest tests/unit/collection tests/unit/content tests/contracts/test_provider_v1.py -q`
- `uv run pytest tests/integration/collection tests/integration/content tests/integration/database/test_provider_config_repository.py -q`
- `uv run alembic upgrade head && uv run alembic current && uv run alembic check`
- `uv run alembic downgrade 20260815_0011 && uv run alembic upgrade head && uv run alembic check`
- `uv run alembic downgrade base && uv run alembic upgrade head && uv run alembic check`
- `uv run ruff format --check backend tests scripts migrations/versions`
- `uv run ruff check backend tests scripts migrations/versions`
- `uv run mypy backend/src`
- `uv run python scripts/contracts/generate.py --check`
- `uv run python scripts/contracts/check_compatibility.py`
- `uv run python scripts/quality/check_architecture.py`
- `uv run python scripts/quality/check_table_ownership.py`
- `uv run python scripts/quality/scan_secrets.py`
- `uv run python scripts/quality/check_docs.py`

# 兼容、Migration、部署与回滚

- 兼容：新增表与 `provider_requests.provider_config_id` 可空列；历史不计费 Request/Attempt 保持可读可回归。新 billable 路径必须显式绑定 Provider Config。
- Migration：新增 `20260815_0012`，父 Revision 固定 `20260815_0011`；不改写历史 Revision。
- 部署：使用 billable Provider Dispatch 前必须先升级到 `0012` 并配置覆盖当前时刻的账户；账户缺失时按设计关闭失败，不降级成无预算发送。
- 回滚：结构可 downgrade 到 `0011`；若新表已有业务账本，downgrade 会删除 Budget 数据且移除 Request Config 关联，执行前必须备份/导出，不能宣称无损回滚。

# 安全、性能与运维风险

- Budget 仅保存 UUID、范围、周期、额度和费用数字，不保存 Credential；Secret Scan 必须继续通过。
- reserve 通过稳定顺序锁账户，避免并发超扣和交叉死锁；测试必须覆盖同额度下两个并发 Attempt 只有一个成功。
- 实际费用超过估算时必须保留真实 settled 数字并阻断后续额度，不允许截断到上限制造假账。
- `unknown_amount` 是保守容量占用，需要未来独立账单/人工对账能力才能释放；本 Change 不伪造自动 reconciliation。

# Git

- 基线 main：`d44397ae076b5502de310f6f617c85457131d7be`
- 分支：`feature/stage7-provider-budget-ledger`
- 用户本地工作区：当前宿主不可见，不能确认 modified/staged/untracked/未推送提交
- Red Commit：待生成
- PR：待创建
- CI：待 Red/Green 新鲜执行
- 合并：未合并
- Change：active；未满足完成条件，不得归档
