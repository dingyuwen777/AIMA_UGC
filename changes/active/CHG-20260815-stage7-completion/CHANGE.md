---
schema: rvc-change/v1
id: CHG-20260815-stage7-completion
title: 完成 Stage 7 多平台采集与 Scheduler Runtime
level: L3
status: in_progress
owner: dingyuwen777
branch: feature/stage7-completion
created: 2026-08-15
updated: 2026-08-17
depends_on: [CHG-20260815-stage7-plan-occurrence-run-snapshot, CHG-20260815-stage7-provider-config-routing, CHG-20260815-stage7-decision-capability, CHG-20260815-stage7-douyin-operation, CHG-20260815-stage7-weibo-operation, CHG-20260815-stage7-bilibili-operation, CHG-20260815-stage7-kuaishou-operation]
affected_areas: [collection, provider, scheduler, database, testing, documentation, ci]
affected_paths: [backend/src/aima_ugc/modules/collection/, backend/src/aima_ugc/adapters/providers/tikhub/, backend/src/aima_ugc/adapters/persistence/postgres/, backend/src/aima_ugc/bootstrap/, backend/src/aima_ugc/entrypoints/, migrations/versions/, tests/unit/collection/, tests/integration/collection/, tests/fixtures/, scripts/, docs/blueprint/, docs/collection/, backend/src/aima_ugc/modules/collection/README.md, .github/workflows/]
contracts: [ProviderPlatformCapabilityV1, CanonicalContentV1, CanonicalCommentV1]
data_changes: [collection_plans, collection_schedule_occurrences, collection_runs]
---

# 背景与现状

Stage 7 已建立 Decision/Capability、Provider Config/Registry、Keyword Pack、Plan/Occurrence/Run Snapshot、五平台 TikHub Operation/真实脱敏 Fixture/Mapper/Capability 基础，以及批准的 Scheduler `latest_only` Runtime。当前正式 Stage 仍未闭环，剩余核心是 `collection.run.v1` live Worker 执行链、统一长期 Probe、文档/CI/Review/合并闭环。

2026-08-16 用户批准快手一级、二级评论正式使用 App Operation；Web 不自动 fallback，只作为显式备用证据保留。其他平台的同语义 API family 只有通过真实受限 A/B 后才能标记为已验证备用。

2026-08-17 用户进一步明确：**当前系统不需要“预算”功能。此前已经实现的请求/金额预算账户、Reservation、Run 预算分配、Plan `request_budget` 和发送前预算硬门禁全部撤回；代码中不保留 dormant 预算实现。Blueprint 只允许保留未来可扩展方向，若以后确有预算需求必须创建新的 L3 Change 重新设计和批准。**

Provider Request/Attempt 的 `provider_config_id`、Billing/成本快照、`potential_duplicate_charge` 等仍属于 Provider 执行与审计事实，不等于预算功能，继续保留。Job Fencing、一次 Attempt 最多一次真实发送、Raw 完整性和未知发送结果的保守恢复语义不受预算回撤影响。

# 目标

在不进入 Stage 8 的前提下完成 Stage 7：

1. 固化并验证 `latest_only + max_catch_up_runs=0` Scheduler Runtime；
2. 完成五平台真实 Raw → Mapper → Canonical → Ingestion 兼容证据；
3. 建立正式 `collection.run.v1` live Worker 执行链和可重复的 Operation / Business Pipeline Probe；
4. 快手评论主 Operation 使用 App，Web 仅保留显式备用，不建立自动 fallback；
5. 对其他平台同语义 API family 建立受限 A/B 证据；
6. 完整撤回当前预算功能实现，同时保持已发布 Migration 历史不可改写；
7. 通过相关 Unit/Contract/PostgreSQL/质量门禁、PR CI、Review、正常合并和合并后 main 新鲜 CI 证明 Stage 7 闭环。

# 成功标准

- [ ] Blueprint 07/08/09 与当前 Change 明确记录 `latest_only + max_catch_up_runs=0`。
- [ ] Plan 领域与数据库拒绝与首版 Scheduler 决策冲突的配置。
- [ ] Scheduler 对 due slot、并发、事务崩溃与重复 tick 保持 Occurrence/Job/Run/cursor 原子且幂等。
- [ ] 五平台当前主 Operation 有合法脱敏真实 Fixture、Mapper、Capability/Registry 与 Canonical/Ingestion 证据。
- [ ] 快手 `comments/sub_comments` 默认生产链使用 App；Web 备用不进入自动 fallback。
- [ ] 正式 `collection.run.v1` Worker Handler 可消费 Scheduler Job，并复用 Provider Routing、Dispatch、Raw、Mapper、Decision、Ingestion 链。
- [ ] 所有业务可见 Run/Scope/Provider 状态写入继续验证当前 Job Fencing Token。
- [ ] Provider 外部调用不包在数据库事务中；同一 Attempt 最多一次真实发送；未知发送结果不得重发同一 Attempt。
- [ ] 当前 Plan/Run/Dispatch 不包含预算配置、预算账户、Reservation、预算分配或超预算门禁。
- [ ] 当前 SQLAlchemy Schema 不再注册 `provider_budget_accounts/provider_budget_reservations`，`collection_plans` 不再包含 `request_budget`。
- [ ] Budget Runtime 模块、Repository、Run Preparer、专用测试和预算 CI 工作流被删除，而不是仅禁用。
- [ ] 历史 `20260815_0012` / `0013` 不改写；新增向前 Migration 从当前 head 删除预算表和 `request_budget`，并通过 downgrade/upgrade round-trip。
- [ ] Blueprint 明确：未来预算/成本 Guard 只是可扩展方向，不是当前 Contract/Schema/运行能力；重新实现需新的 L3 Change。
- [ ] 新增/修改行为遵循 Red → Green → Refactor；真实付费 Probe 是受控例外，不进入普通 CI。
- [ ] Ruff、mypy、Unit、Contract、PostgreSQL Integration、Architecture、Table Ownership、Secret Scan、Docs 与受影响 Stage 回归通过。
- [ ] PR 通过正常 CI 合入 main；合并后的 main 有新鲜成功证据后 Change 才标记 done 并归档。

# 范围

- Stage 7 Scheduler Runtime 与 `latest_only` 领域/数据库约束。
- 五平台 TikHub 主 Operation/Mapper/Capability/Registry 的真实兼容纵切。
- 快手 App 评论主链、Web 显式备用边界。
- 同平台 API family 候选与受限 A/B Probe。
- 正式 `collection.run.v1` Worker Handler 与 Operation / Business Pipeline Probe。
- 当前预算功能向前回撤及对应 Migration/测试/文档。
- Blueprint、Collection 开发说明和平台文档同步。

# 非目标

- 不实现 Stage 8 HTTP CRUD、正式业务页面、Secret 写 API 或认证授权。
- 不实现实时直播评论/WebSocket/ASR。
- 不建立自动 App/Web fallback。
- 不为未证明字段、分页、排序或评论关系编造 Mapper。
- **不重新设计预算配置、预算比例、金额上限、单内容预算或预算 UI。**
- 不增加微服务、Redis、Kafka、通用插件框架或第二套 Scheduler 存储。
- 不顺手升级依赖。

# 必须保持不变

- Provider → Raw → Mapper → Canonical → Ingestion；Provider 不写业务表，Mapper 不访问数据库/HTTP。
- PostgreSQL Job Runtime 是 scheduled Run 的正式任务事实；Scheduler 不自建进程内任务队列。
- 一个 `(plan_id, schedule_version, scheduled_for)` 只有一个 Occurrence；Occurrence/Run/Job/Plan 推进同事务。
- Provider Secret 只通过 `provider_config_id → secret_ref` 解析；不进入代码、日志、Raw、Fixture、Job Payload 或数据库明文。
- `manual/api/backfill` Run 既有合法行为保持兼容。
- Canonical V1、表 Owner、外部 ID 字符串、PostgreSQL `timestamptz` 规则不变。
- 所有业务可见写入继续受当前 Job Fencing Token 约束。
- Provider Transport 不隐藏网络重试；同一 Attempt 不重复发送。
- “已验证备用”只表示兼容证据和显式人工切换选项，不等于自动 fallback。

# 方案比较与用户批准决策

## Scheduler：latest-only（采用）

停机恢复后多个逻辑调度点已到期时，只把最新 slot 入队；更早 slot 写 `skipped / misfire_superseded`。首版 `max_catch_up_runs=0`，不额外补跑历史 Run。用户于 2026-08-15 明确批准。

## 快手评论：App 主链 + Web 显式备用（采用）

- 一级评论：`/api/v1/kuaishou/app/fetch_video_comment`；
- 二级回复：`/api/v1/kuaishou/app/fetch_video_sub_comments`；
- Web 只保留显式 builder / Probe / 兼容证据；
- 运行时不得因 App 失败自动调用 Web。

用户于 2026-08-16 明确批准。

## 预算功能回撤方案 A：改写历史 Migration（不采用）

`20260815_0012` 和 `0013` 已进入 main。改写或删除历史 Revision 会破坏现有数据库升级链、已部署环境和 CI 可追溯性，不符合 Migration 规则。

## 预算功能回撤方案 B：新增向前 Migration + 删除 Runtime（采用）

- 保留历史 `0012/0013` 不变；
- 新增 `20260817_0015`，从 `0014` 向前删除预算两表和 `collection_plans.request_budget`；
- 删除 Budget Service/Repository/Envelope/Run Preparer、预算专用测试与工作流；
- 删除 Dispatch 的预算检查/结算；
- 保留 `provider_requests.provider_config_id` 和 Provider Billing/费用事实；
- Blueprint 仅记录未来扩展方向。

这是用户于 2026-08-17 明确批准的当前方案。

## 预算功能回撤方案 C：代码保留但默认关闭（不采用）

会留下两套长期语义和 dormant 复杂度，也容易被后续 Agent 误判为当前能力，不符合用户“全部删除”的要求。

# Migration 与数据影响

历史 Revision 不修改：

```text
20260815_0012  建立 Provider Budget Ledger，并增加 provider_requests.provider_config_id
20260815_0013  建立 Plan/Occurrence/Run Snapshot，其中曾包含 request_budget
20260815_0014  latest-only Scheduler policy
20260817_0015  向前移除预算表与 request_budget
```

`0015 upgrade`：

```text
drop provider_budget_reservations
drop provider_budget_accounts
drop collection_plans.request_budget
```

`provider_requests.provider_config_id` 必须保留，因为它表达稳定 Provider Config 来源身份，而不是预算。

`0015 downgrade` 只负责恢复上一 Revision 的 Schema 形态；被 upgrade 删除的历史预算额度/Reservation 数据不会自动重建。因此上线 `0015` 前若任何环境已有需要保留的预算账本数据，应先按发布/备份流程留存数据库备份。当前业务系统不再读取这些数据。

# 当前预算扩展边界

当前代码**没有** Budget Port、Budget Repository、Budget Table 或预算配置字段。未来如果业务确实需要预算/限额能力，只允许作为新的 L3 Change 重新设计。候选扩展位置可以放在：

```text
已准备 Provider Attempt
→ 可选 Cost/Budget Guard（未来）
→ Dispatch CAS
→ Provider Transport
```

未来 Guard 可以读取 `provider_config_id / run / content / operation / Billing estimate` 等稳定事实，但当前不定义它的 Contract、Schema、配置字段、默认策略或 UI；不能为了“预留接口”在生产代码中保留空实现。

# 验证计划

[步骤 1：预算回撤 Red]
→ 范围：Plan 字段、Schema 表、Budget Runtime 模块存在性
→ 预期：回撤前测试按正确原因失败
→ 证据：Red 已观测 `3 failed, 208 passed`，失败分别为 `request_budget`、Budget 表、Budget 模块仍存在

[步骤 2：预算回撤 Green]
→ 范围：0015 Migration、Plan/Schema/Scheduler/Dispatch、预算模块/测试/CI 删除
→ 预期：当前运行时无预算功能，Provider Fencing/Dispatch/Raw 行为不变
→ 验证：Unit、Stage 5B/5D、Stage 6、Scheduler、Provider Config、Migration round-trip、Ruff/mypy

[步骤 3：文档同步]
→ 范围：AGENTS、Blueprint 03/07/08/README、Collection 文档、PR
→ 预期：不再把预算写成当前能力；未来扩展边界清楚但不预设计实现
→ 验证：Docs Check + Secret Scan + 人工一致性 Review

[步骤 4：live Worker]
→ 范围：`collection.run.v1` Scope Executor / Worker 装配
→ 预期：Scheduler Job 能进入 Provider → Raw → Mapper → Decision → Ingestion 正式链
→ 验证：Red/Green Unit + PostgreSQL Integration + Fake Transport；真实付费 Probe 继续只走受控 GitHub Runner

[步骤 5：最终 Stage 7 交付]
→ 范围：PR #55 全量 diff、CI、Review、Change 状态
→ 预期：只有当前 Stage 7 内容，无 Stage 8 漂移
→ 验证：完整 PR CI + Review + main 合并后新鲜 CI

# 回滚

- 代码回滚：回退本 Change 中预算回撤之后的提交时，必须同时考虑数据库是否已经执行 `0015`；不能只回代码不处理 Schema。
- Schema 开发回滚：可 downgrade `0015 → 0014` 恢复旧表结构，但已删除预算数据不会凭 downgrade 自动恢复。
- 生产数据恢复：若确需恢复 upgrade 前预算账本值，只能使用升级前协调备份，不把 downgrade 当数据恢复。
- 禁止修改或删除已经进入 main 的 `0012/0013/0014` Revision。

# 当前状态

- Scheduler latest-only：已实现，继续回归验证。
- 五平台 Operation/Mapper/真实脱敏证据：已建立大量机器事实，继续最终一致性复核。
- Kuaishou App comments/sub-comments：当前主链已切换，Web 仅显式备用。
- PostgreSQL Fenced Collection Run Gateway：已实现并通过 Stage 5B 既有验证。
- TikHub Runtime comments/sub-comments 统一入口：已实现，继续全局质量回归。
- 预算功能回撤：Red 已完成；Green 代码/Migration 正在验证，文档同步进行中。
- `collection.run.v1` live Worker：仍未闭环，是预算回撤完成后的当前核心开发工作。
- Stage 8：未开始，也不得在本 Change 中开始。
