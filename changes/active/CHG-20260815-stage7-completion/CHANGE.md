---
schema: rvc-change/v1
id: CHG-20260815-stage7-completion
title: 完成 Stage 7 多平台采集与 Scheduler Runtime
level: L3
status: in_progress
owner: dingyuwen777
branch: feature/stage7-completion
created: 2026-08-15
updated: 2026-08-15
depends_on: [CHG-20260815-stage7-plan-occurrence-run-snapshot, CHG-20260815-stage7-provider-budget-ledger, CHG-20260815-stage7-provider-config-routing, CHG-20260815-stage7-decision-capability, CHG-20260815-stage7-douyin-operation, CHG-20260815-stage7-weibo-operation, CHG-20260815-stage7-bilibili-operation, CHG-20260815-stage7-kuaishou-operation]
affected_areas: [collection, provider, scheduler, database, contracts, testing, documentation, ci]
affected_paths: [backend/src/aima_ugc/modules/collection/, backend/src/aima_ugc/adapters/providers/tikhub/, backend/src/aima_ugc/adapters/persistence/postgres/, backend/src/aima_ugc/entrypoints/, migrations/versions/, tests/unit/collection/, tests/contracts/, tests/integration/collection/, tests/fixtures/, scripts/, docs/blueprint/README.md, docs/blueprint/07-技术决策与实施门禁.md, docs/blueprint/08-采集策略与平台能力.md, docs/collection/, backend/src/aima_ugc/modules/collection/README.md, .github/workflows/]
contracts: [ProviderPlatformCapabilityV1, CanonicalContentV1, CanonicalCommentV1]
data_changes: [collection_plans, collection_schedule_occurrences, collection_runs]
---

# 背景与现状

Stage 7 已建立 Decision/Capability、Provider Config/Registry、Keyword Pack、Provider Budget Ledger、Plan/Occurrence/Run Snapshot，以及五个平台的 TikHub Operation 基础；小红书已经具备 Mapper 纵切。当前机器事实仍缺抖音、微博、B站、快手四个平台的合法脱敏非空真实 Fixture、Mapper/Capability/Registry 完整接线、统一 Probe，以及 Scheduler Runtime。

`collection_plans` 已有 `misfire_policy`、`max_catch_up_runs`、`next_run_at`、`last_scheduled_at`，但此前只是父事实，不允许 Scheduler 自行解释。2026-08-15 用户已明确批准方案 A：`latest_only`。

# 目标

在不进入 Stage 8 的前提下完成 Stage 7：

1. 把 Scheduler 停机恢复语义固化为 `latest_only`，并建立可并发、可恢复、可测试的 Scheduler Runtime；
2. 用合法取得并脱敏的真实 TikHub 非空响应闭环抖音、微博、B站、快手 Search Mapper 与 Capability/Registry；
3. 建立复用生产 Operation/Mapper/Decision Service 的 Operation Probe / Business Pipeline Probe 最小闭环；
4. 通过目标测试、PostgreSQL 集成、质量门禁、PR CI 和合并后 main 新鲜 CI 证明 Stage 7 完成。

# 成功标准

- [ ] Blueprint 07/08、Collection 文档和当前 Change 明确记录 `latest_only`：停机恢复时若累计多个已到期调度点，只入队最新一个；更早的已到期调度点记录 `skipped`，`skip_reason=misfire_superseded`；首版 `max_catch_up_runs=0`，不额外补跑历史 Run。
- [ ] 首版 Plan 创建/持久化不能写入与已批准策略冲突的 `misfire_policy/max_catch_up_runs`。
- [ ] Scheduler 解析当前正式 schedule expression、计算 due slots、在一个事务中创建唯一 Occurrence + Job + scheduled Run 并推进 `last_scheduled_at/next_run_at`。
- [ ] 多 Scheduler 并发时同一 `(plan_id, schedule_version, scheduled_for)` 只产生一个有效 Occurrence/Run/Job；预扫后 Plan 被禁用或改版本时不会误执行旧版本。
- [ ] Scheduler 停机多个周期恢复时只执行最新 due slot，更早 due slots 明确 skipped；恢复后 `next_run_at` 指向未来下一次。
- [ ] Scheduler 在提交边界重复执行/崩溃恢复时依靠数据库唯一约束和事务语义保持幂等，不绕过 Job Runtime。
- [ ] 抖音、微博、B站、快手各至少一份合法取得、脱敏、非空 Search Fixture；Fixture 不含 Secret，作者/账号等直接标识按测试需要做稳定替换。
- [ ] 四个平台 Search Mapper 输出 Provider/平台无关 Canonical，稳定外部内容 ID 仍为字符串，Mapper 不访问数据库、不发 HTTP。
- [ ] 四个平台 Capability 只暴露当前 Operation/Fixture 已证明的业务能力，并加入默认 TikHub Registry；不猜未证明字段/分页/评论增量能力。
- [ ] Operation Probe 使用生产 Registry/Capability/Operation/Mapper；真实 billable Probe 在 Pricing 未 verified 时发送前 fail closed，并具有请求数/费用上限。
- [ ] Business Pipeline Probe 复用生产 `CollectionDecisionService`，能输出机器可读 decisions JSONL；人工导出只作为 Probe 输出，不成为业务事实源。
- [ ] 新增/修改行为遵循 Red → Green → Refactor；真实付费 Probe 作为 TDD 例外，使用小请求上限并单独记录证据，不进入普通 CI。
- [ ] 相关 Migration 从 `0013 → head`、`base → head`、downgrade/upgrade、`alembic check` 通过；如最终无需 Migration，则在验证中记录依据。
- [ ] Ruff、mypy、Unit、Contract、PostgreSQL Integration、Architecture、Table Ownership、Secret Scan、Docs 以及受影响 Stage 回归通过。
- [ ] PR 通过正常 CI 合入 main；合并后的 main 再取得新鲜成功证据后，Change 才标记 done 并归档。

# 范围

- Stage 7 Scheduler Runtime 与 `latest_only` 领域/数据库约束。
- 抖音、微博、B站、快手 Search Raw → Mapper → Canonical 的最小真实纵切。
- 四个平台 Capability/Registry 接线。
- Operation Probe / Business Pipeline Probe 最小生产复用入口。
- 目标 Unit/Contract/PostgreSQL/质量测试与 Stage 7 CI。
- Blueprint、Collection 开发说明和平台文档同步。

# 非目标

- 不实现 Stage 8 HTTP CRUD、正式业务页面、Secret 写 API 或认证授权。
- 不实现实时直播评论/WebSocket/ASR。
- 不修改已批准的五平台主 Operation Matrix，除非官方事实证明当前代码错误；发生这种情况先更新本 Change 并按门禁处理。
- 不为未证明的详情/评论字段编造 Mapper；本 Stage 完成所需真实兼容以各平台至少非空 Search Fixture + Search Mapper/Capability 为最小门槛，详情/评论 Operation 继续保留请求/分页事实并由后续真实 Probe 扩充观察字段。
- 不增加微服务、Redis、Kafka、通用插件框架或第二套 Scheduler 存储。
- 不进入 Stage 8，不顺手升级现有依赖。

# 必须保持不变

- Provider → Raw → Mapper → Canonical → Ingestion；Provider 不写业务表，Mapper 不访问数据库/HTTP。
- PostgreSQL Job Runtime 是 scheduled Run 的正式任务事实；Scheduler 不自建进程内任务队列。
- 一个 `(plan_id, schedule_version, scheduled_for)` 只有一个 Occurrence；Occurrence/Run/Job/Plan 推进同事务。
- Provider Secret 只通过 `provider_config_id → secret_ref` 解析；不进入代码、日志、Raw、Fixture、Job Payload 或数据库明文。
- 真实 HTTP Attempt 继续受 Provider Pricing/Budget Ledger 保护；Pricing 未核验 fail closed。
- `manual/api/backfill` Run 既有行为保持兼容。
- Canonical V1、表 Owner、外部 ID 字符串、PostgreSQL `timestamptz` 规则不变。

# 方案比较与用户批准决策

## Scheduler 方案 A：latest-only（采用）

停机恢复后若多个逻辑调度点已经到期：

- 最新一个 due slot 入队；
- 更早 due slots 写 `skipped / misfire_superseded`；
- `max_catch_up_runs=0` 表示不额外执行历史 Run；
- 正常未来周期继续按 schedule 运行。

优点：恢复后立即取得最新舆情，避免 TikHub 集中补跑造成请求/费用风暴；重叠搜索窗口与 backfill 负责补漏。缺点：不逐个重放停机期间每个历史时点。

**用户于 2026-08-15 明确批准方案 A。**

## Scheduler 方案 B：bounded catch-up（不采用）

执行最新 due slot 并额外补最近 N 个历史 slot。历史连续性更好，但恢复成本、并发与重复请求显著增加。

## Scheduler 方案 C：strict skip（不采用）

全部错过 slot 都跳过，等待下一未来周期。成本最低，但恢复后可能继续产生一个完整调度间隔的舆情空窗。

# 公共接口与数据兼容

- 不新增 Stage 8 公开 HTTP API；现有 OpenAPI/Generated Client 应保持零漂移。
- `ProviderPlatformCapabilityV1` 只扩充已有 Provider+Platform 实例数据，不改变 Contract 字段结构。
- Canonical V1 字段结构不改变；新增 Mapper 只产生既有 Canonical Observation。
- 如增加 Migration，仅追加新 Revision，不改写 `0001`—`0013`；回滚必须明确数据影响。

# 安全、费用、性能与运维风险

- 真实 TikHub 调用只用于最小兼容验证，使用“爱玛”关键词、单页/小请求上限；API Key 不写入仓库、日志、Fixture 或输出。
- 未经官方 Pricing 核验的 billable endpoint 不发送；不得用全局默认单价绕过 fail-closed。
- Scheduler 恢复只执行最新 due slot，从语义上限制停机恢复请求风暴；常规 Provider 调用仍由 Budget Ledger 二次硬限制。
- 多 Scheduler 依赖 PostgreSQL 行锁/唯一键/事务协调，不引入分布式锁服务。

# 任务

[步骤 1]
→ 修改范围：Blueprint 07/08、Collection 文档、Plan 领域约束、当前 Change
→ 预期结果：`latest_only + max_catch_up_runs=0` 成为长期事实并可由代码拒绝冲突配置
→ 验证方式：目标 Unit/DB 约束测试、Docs/Secret/Architecture 门禁

[步骤 2]
→ 修改范围：Scheduler 领域服务、PostgreSQL Repository、Scheduler entrypoint、必要 Migration/测试
→ 预期结果：due slot 计算、latest-only misfire、唯一 Occurrence/Run/Job、Plan 推进和并发恢复闭环
→ 验证方式：先观察缺失行为 Red，再运行 Unit + PostgreSQL 并发/恢复专项

[步骤 3]
→ 修改范围：TikHub 四平台真实 Search Fixture、Mapper、Capability/Registry、Contract/Unit 测试
→ 预期结果：四平台能把合法非空真实 Search Raw 映射为 Canonical 并作为可运行 Capability 登记
→ 验证方式：Fixture Contract/Mapper Unit、Secret Scan、Canonical Contract、目标 CI

[步骤 4]
→ 修改范围：Operation Probe / Business Pipeline Probe 入口与测试
→ 预期结果：调试复用生产 Operation/Mapper/Decision Service，不复制业务规则；真实 billable 发送前受 Pricing/Budget 上限保护
→ 验证方式：Fake/Fixture Unit；获授权时执行小请求真实 Probe 并单独记录结果

[步骤 5]
→ 修改范围：长期文档、Stage 7 CI、Change
→ 预期结果：文档与机器事实一致，Stage 7 有独立质量门禁和完整 Git 证据
→ 验证方式：相关 workflows + PR CI + 合并后 main CI

# 验证

## 计划

- Red：Scheduler latest-only/并发/推进、四平台 Mapper/Capability、Probe 行为测试先于实现并确认因目标能力缺失失败。
- 目标测试：`tests/unit/collection/`、四平台 TikHub Mapper/Capability 测试、Scheduler PostgreSQL integration。
- 相关回归：Stage 4 Job Runtime、Stage 5 Collection/Dispatch、Stage 6 XHS、Stage 7 Provider Config/Keyword/Budget/Plan。
- 静态检查/构建：Ruff format/check、mypy、Contract generate/compatibility、Architecture、Table Ownership、Secret Scan、Docs。
- Migration：如新增 Revision，执行 `0013→head`、`base→head`、downgrade/upgrade、`alembic check`。
- 真实 Probe：仅显式执行、请求数和费用封顶，不进入普通 CI。

## 新鲜证据

- 尚未执行实现分支验证。

# 文档影响

必须同步：

- `docs/blueprint/07-技术决策与实施门禁.md`
- `docs/blueprint/08-采集策略与平台能力.md`
- `docs/blueprint/README.md`
- `docs/collection/README.md`
- `docs/collection/douyin.md`
- `docs/collection/weibo.md`
- `docs/collection/bilibili.md`
- `docs/collection/kuaishou.md`
- `backend/src/aima_ugc/modules/collection/README.md`

# 部署与回滚

- 当前任务只合并代码/文档，不自动部署生产服务器。
- 若新增 Migration，部署顺序为先备份/维护窗口准备 → Migration → Scheduler/Worker 新镜像；应用回滚前必须确认新 Migration 数据兼容。
- Scheduler 可通过不启动 Scheduler 进程停止自动调度；数据库 Occurrence/Run/Job 事实保留，不通过删除历史记录回滚。
- Mapper/Capability 可通过代码回滚移除新平台可运行登记，Raw/Canonical 历史事实不重写。

# 交付

- 基线 main：`2acc4b9e767c3cff06a0522f36242763ea9e44ee`
- Commit：进行中
- PR：进行中
- 发布：本任务不部署生产
