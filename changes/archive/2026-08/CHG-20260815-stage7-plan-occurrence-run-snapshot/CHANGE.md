---
schema: rvc-change/v1
id: CHG-20260815-stage7-plan-occurrence-run-snapshot
title: 建立 Stage 7 Plan、Occurrence 与 Run Snapshot 父事实
level: L3
status: done
owner: dingyuwen777
branch: feature/stage7-plan-occurrence-run-snapshot
created: 2026-08-15
updated: 2026-08-15
depends_on: [CHG-20260815-stage7-provider-config-routing, CHG-20260815-stage7-keyword-packs]
affected_areas: [collection, system, database, jobs, testing, documentation]
affected_paths: [backend/src/aima_ugc/modules/collection/, backend/src/aima_ugc/adapters/persistence/postgres/, backend/src/aima_ugc/database_schema.py, migrations/versions/, tests/unit/collection/, tests/integration/collection/, docs/blueprint/README.md, docs/collection/README.md, backend/src/aima_ugc/modules/collection/README.md, .github/workflows/]
contracts: []
data_changes: [collection_plans, collection_plan_platforms, collection_plan_keyword_packs, collection_schedule_occurrences, collection_runs.manual_plan_id, collection_runs.occurrence_id]
---

# 背景与现状

Stage 5B 已建立 `collection_runs/collection_scopes`，Stage 7 已建立 Provider Config 与 Keyword Pack，但基线 Run 只支持 `manual/api/backfill`，没有 Plan、Plan→Platform/Keyword Pack 关系、Schedule Occurrence 或 Scheduled Run 的数据库父事实。Blueprint 03 已冻结这些目标关系，同时 Blueprint 07 明确 Scheduler 的 misfire/catch-up 行为仍未批准。

# 目标

建立未来 Scheduler 和 Stage 8 Plan API 共用的最小数据库父事实：Plan、平台配置、词包关联、Occurrence，以及 Run 对 Plan/Occurrence 的不可歧义关联。当前 Change 只建立可约束数据模型和显式创建入口，不实现 Scheduler 行为。

# 成功标准

- `collection_plans`、`collection_plan_platforms`、`collection_plan_keyword_packs`、`collection_schedule_occurrences` 由 Collection Owner 管理并通过新 Alembic Revision 建立。
- Plan 首版时区只接受 `Asia/Shanghai`；`schedule_version >= 1`、`request_budget >= 0`、`max_catch_up_runs >= 0` 等稳定结构约束由数据库和 Domain 同时保护。
- Plan 平台关系必须引用稳定 `provider_config_id`，同一 Plan/Platform 唯一；平台配置使用 JSONB 保存业务配置快照，不保存 Secret 或 Provider 私有分页状态。
- Plan→Keyword Pack 使用关联表，不把关系塞进 Plan JSON。
- Occurrence 唯一身份为 `(plan_id, schedule_version, scheduled_for)`；只允许 `enqueued/skipped` 可提交终态，并约束 `job_id/skip_reason` 一致性。
- `collection_runs` 新增可空 `manual_plan_id/occurrence_id`；`scheduled` Run 必须引用 Occurrence 且不得写 `manual_plan_id`；现有 `manual/api/backfill` 保持兼容并不得引用 Occurrence。
- Deferred 数据库约束在事务提交前验证：`enqueued` Occurrence 恰有一个反向 scheduled Run 且 Run/Occurrence `job_id` 一致；`skipped` Occurrence 没有 Run。
- Domain/Repository 能创建显式 Plan，以及原子创建 scheduled Job+Occurrence+Run/Scopes 所需父事实；不解析 Cron、不计算 misfire/catch-up。
- `0012 → head`、`base → head`、downgrade/upgrade、`alembic check` 和表 Owner/架构/Secret/Docs 门禁通过。
- PR 合并后 main 再次获得新鲜 CI 证据后才允许归档 Change。

# 范围

- Collection Plan/Platform/Keyword Pack/Occurrence/Run Snapshot 的 Domain、Table、Migration、Repository。
- Scheduled Run 数据一致性和现有 Run 创建兼容。
- Unit/PostgreSQL/Quality 测试与长期文档同步。

# 非目标

- 不实现 Scheduler 主循环、Cron 解析、`next_run_at/last_scheduled_at` 推进算法。
- 不批准或执行 `misfire_policy`、`max_catch_up_runs` 的具体运行语义；当前仅持久化调用方显式值，Scheduler 仍 No-Go。
- 不新增 Stage 8 HTTP API、前端页面或认证/授权能力。
- 不修改 TikHub Pricing、真实 Provider Probe、四平台 Mapper/Fixture。
- 不改写历史 Migration `0001`—`0012`。

# 必须保持不变

- PostgreSQL Job Runtime 是正式任务事实；一个 Run 继续只绑定一个 Job。
- Provider Config 只保存 `secret_ref`，Plan/Run Snapshot 不保存 API Key、Token、Cookie 等 Secret。
- 平台 Provider 选择使用稳定 `provider_config_id`；Provider 私有 cursor/page/search_id 等运行状态不进入 Plan 普通业务配置。
- Raw → Mapper → Canonical → Ingestion、表 Owner 与现有 Provider Budget 边界不改变。
- 当前 `manual/api/backfill` Run 调用保持兼容。

# 方案比较与已确认取舍

## 方案 A：全部平台配置拆成固定关系列

为每个平台和每一种采集参数都建立独立列/子表。

- 优点：数据库字段强类型、查询直接。
- 缺点：当前五个平台参数差异仍在持续冻结，提前建列会产生大量平台专有可空字段和频繁 Migration；把 Stage 8 尚未冻结的 API 形状过早固化到数据库。
- 结论：不采用。

## 方案 B：Plan 全量 JSONB

把平台、Provider Config、关键词包和业务参数全部存入一个 Plan JSONB。

- 优点：实现最少、变更灵活。
- 缺点：`provider_config_id`、Keyword Pack 等稳定身份失去 FK/唯一约束；无法满足 Blueprint 03 已批准的真实关系和 Owner/完整性要求。
- 结论：不采用。

## 方案 C：关系身份规范化 + 平台业务配置 JSONB（采用）

Plan/Platform、Plan/Keyword Pack 使用真实 FK 关联；平台变化较大的业务参数放在 `collection_plan_platforms.config` JSONB，并强制为 object。

- 优点：稳定身份、唯一性、引用完整性由数据库约束；未冻结的平台业务参数不被过早拆列；后续 Stage 8 可以在 Pydantic/Capability 层版本化校验后再演进数据库。
- 风险：JSONB 内部业务字段不是本 Change 的数据库级强类型事实，因此后续公开 Plan API 必须通过版本化 Contract/Capability 校验，不能直接把任意 JSON 写入 Repository。
- 结论：采用。JSONB 不得代替关系身份，也不得保存 Secret 或 Provider 私有分页状态。

# 公共接口与兼容策略

- 本 Change 不新增公开 HTTP API、OpenAPI 或前端 Client，因此 `contracts: []`；Contract 生成与兼容检查零漂移。
- `CollectionExecutionService.create_run` 仅增加可选 `manual_plan_id/occurrence_id`，原有 `manual/api/backfill` 调用保持兼容。
- 数据库通过追加 `0013` 演进；不修改历史 Revision。
- `scheduled` 是新增合法 trigger，只能在 `occurrence_id` 存在时提交；旧 trigger 语义不变。

# 安全、性能与运维风险

- 安全：Plan 平台配置入口递归拒绝常见 Secret 形态字段；真正凭据仍只通过 Provider Config `secret_ref` 引用；仓库 Secret Scan 通过。
- 并发/一致性：Occurrence 唯一键、Job/Occurrence 唯一关系与 deferred constraint 在事务提交点防止孤儿、Job 不一致和 skipped→Run 反向关系。
- 性能：本 Change 只建立父事实；关键关系由 PK/Unique/FK 覆盖当前按 Plan/Job/Occurrence 的写入与定位。Scheduler 扫描/抢占模式尚未批准，因此不提前为未知查询模式增加索引。
- 运维：新增 PL/pgSQL constraint function/trigger，Migration 与回滚已在 PostgreSQL 18.4 真实执行；回滚会删除本 Change 新增 Plan/Occurrence 数据，生产使用后不能无数据处置直接 downgrade。

# Red → Green → Refactor 证据

## Red

GitHub Actions run `31887206516`：

- Stage 7 Plan Unit 在锁定环境安装成功后，因 `aima_ugc.modules.collection.planning` 尚不存在而以 `1 error / exit code 2` 失败。
- PostgreSQL Job 先成功升级到当时 head `20260815_0012` 且 `alembic check` 无漂移，再因 Planning Repository 尚不存在失败。
- Red 由目标生产能力缺失触发，不是环境或旧 Migration 故障。

## 最终分支 Green / Refactor

GitHub Actions run `31888242072`，branch head `ae81c222fd309ddeb26b052f06f689b03812f09f`：

- `Stage 7 Plan Unit`：`17 passed in 1.30s`，0 failed，0 skipped。
- `Stage 7 Plan PostgreSQL`：`20260815_0013 (head)`，`alembic check` 无新操作；专项与既有 Collection Repository 合计 `11 passed in 0.72s`；随后 `0012 → head` 与 `base → head` downgrade/upgrade 均再次 `alembic check` 无 drift。
- `Stage 7 Plan Quality`：Ruff format/check 通过；mypy `Success: no issues found in 109 source files`；Contract generate/compatibility、Architecture（112 files）、Table Ownership（28 mapped tables）、Secret Scan（180 files）、Docs（33 Markdown files）全部通过。

## PR 与 main 集成

- PR：`#53`，head `638b8ee468f37ce82f21180d909dc47c3c4d52cc`。
- PR 级实际触发 workflow：11/11 success，包括主 CI、Stage 4、Stage 5A—5D、Stage 6、Stage 7 Provider Config/Keyword Packs/Budget 与本 Change 专项。
- 合并 commit：`34544ca732e6652ce9847a49bddb799e7d98b4e0`。
- 合并后 main push 对该 merge commit 再次触发 11 个 workflow，全部进入完成状态且未出现 failure/cancelled/timed_out/action_required/skipped/neutral 等非成功结论。
- main `Stage 7 Plan Occurrence Run Snapshot` run `31888469521`：Unit、PostgreSQL、Quality 三个 Job 均 `success`；`0013` Migration 已在 main 可读。
- main Stage 5D run `31888469788`、Stage 4 run `31888469282`、Stage 7 Provider Budget run `31888468995`、Stage 7 Keyword Packs run `31888469185` 等相关回归均 `success`。

# 两阶段 Review

## 需求符合性

- 范围内 Plan/Platform/Keyword Pack/Occurrence/Run 关系与成功标准均有生产实现和真实 PostgreSQL 证据。
- 未实现 Scheduler/Cron/misfire/catch-up、Stage 8 API/前端、四平台 Mapper/Fixture、TikHub Probe 等非目标。
- 未改写 `0001`—`0012`；未引入无关依赖；Contract 生成物零漂移。
- Blueprint 03 已批准的真实关系与本实现一致，因此不改写其设计；更新的是当前状态导航与 Collection 使用说明。

## 代码质量

- 正确性：deferred constraint 真实验证 orphan enqueued、Occurrence/Run Job mismatch、skipped Occurrence 反向 Run 三类非法提交。
- 兼容：原 `manual/api/backfill` Unit 与既有 PostgreSQL Collection Repository 回归通过。
- 安全：Plan 配置递归敏感键测试和仓库 Secret Scan 通过，未保存真实 TikHub Secret。
- Migration：`0012→0013`、`base→head`、downgrade/upgrade、drift 均通过。
- 并发：关系身份由数据库 Unique/FK/constraint 保护；本 Change 不实现未批准 Scheduler 并发策略。
- 资源生命周期：Repository 不自行提交，事务由调用方持有；集成测试显式关闭 Session/Runtime。
- 未发现严重或重要问题需要阻止合并。

# 文档影响

已同步：

- `backend/src/aima_ugc/modules/collection/README.md`：新增 Plan/Occurrence/Run Snapshot、Secret、Repository 与 Scheduler 非目标边界。
- `docs/collection/README.md`：同步当前采集父事实和 Stage 7 剩余能力。
- `docs/blueprint/README.md`：把本实现单元加入当前机器事实并从 Stage 7 剩余单元移除，同时保持 Stage 7 整体仍进行中。

未修改 `docs/blueprint/03-数据库与文件存储.md`：实际实现符合其已批准结构，无设计变化；不为制造变更痕迹改写长期设计。

# Git 结果

- 基线 main：`e453a3467ccfed61a81981acbc9cfae489e3afae`。
- 实现分支：`feature/stage7-plan-occurrence-run-snapshot`。
- 实现 PR：`#53`，已通过正常 merge commit 合入 main。
- 集成 main：`34544ca732e6652ce9847a49bddb799e7d98b4e0`，合并后相关 CI 已重新验证成功。
- Change 仅在上述集成证据成立后才切换为 `done` 并移入本归档路径。

# 回滚与部署

- Migration 为追加式 `0013`；不改写历史 Revision。
- 回滚通过 `alembic downgrade 20260815_0012` 删除本 Change 新增父事实/列；生产若已有 Plan/Occurrence 数据，回滚前必须确认数据处置，不能静默丢数据。
- 本轮未部署生产环境；数据库角色继续使用现有 Migration 权限。
