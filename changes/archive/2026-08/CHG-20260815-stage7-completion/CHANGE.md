---
schema: rvc-change/v1
id: CHG-20260815-stage7-completion
title: 完成 Stage 7 多平台采集与 Scheduler Runtime
level: L3
status: done
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

# 完成结论

Stage 7 已于 2026-08-17 完成实现、Review、PR 合并、合并后 `main` 新鲜 CI 与 Change 生命周期归档。下一正式阶段是 Stage 8；本 Change 未实现或提前开始 Stage 8。

实现 PR：`#55 完成 Stage 7 多平台采集与 Scheduler Runtime`

```text
开始 main:
2acc4b9e767c3cff06a0522f36242763ea9e44ee

最终实现 branch head:
056e8f5684b19f6b40c4e7c4755593aee3336a7a

PR #55 merge commit / 合并后 main:
737151a179a4b941c8bdc553cc77c4286bcb6d27
```

PR #55 已由 Draft 正常转为 Ready，并使用 `expected_head_sha=056e8f5684b19f6b40c4e7c4755593aee3336a7a` 正常 merge；未强推、未绕过 Branch Protection、未跳过 CI。

# 已批准且最终保持的业务决定

## Scheduler

```text
misfire_policy = latest_only
max_catch_up_runs = 0
```

停机恢复多个到期 slot 时：

- 只执行最新 slot；
- 更早 slot 写 `skipped / misfire_superseded`；
- 不额外补跑历史 Run。

## 快手评论

正式主链保持：

```text
/api/v1/kuaishou/app/fetch_video_comment
/api/v1/kuaishou/app/fetch_video_sub_comments
```

Web comments/sub-comments 只保留显式 `verified_backup`；不存在 App/Web 自动 fallback。

## Provider Config / Secret

- 同一 Provider 类型允许多个 Config；
- Config 不绑定平台；
- Platform/Plan 选择 `provider_config_id`；
- Secret 只通过 `secret_ref` 解析；
- Secret 不进入数据库明文、Job Payload、Raw、Fixture 或日志。

## Budget 回撤

当前系统不实现：

```text
请求次数预算
金额预算
Budget Account
Reservation Ledger
Run Budget
评论 Budget
collection_plans.request_budget
发送前 Budget Gate
Budget Service / Repository / Envelope / Preparer
dormant Budget 接口
```

历史 Migration `20260815_0012/0013/0014` 未改写；`20260817_0015` 作为向前 Migration 删除预算表和 `collection_plans.request_budget`。

继续保留：

- `provider_requests.provider_config_id`；
- Provider Request/Attempt Billing；
- endpoint Pricing；
- 成本快照；
- `potential_duplicate_charge`。

这些是 Provider 执行/审计事实，不属于 Budget Runtime。未来若重新需要 Budget / Cost Guard，必须创建新的 L3 Change。

# 正式实现结果

## live Worker

已正式闭环：

```text
Scheduler
→ Occurrence
→ collection.run.v1 Job
→ scheduled Run / Scope
→ Production JobRegistry
→ JobWorker.run_once()
→ CollectionRunJobHandler
→ CollectionRunExecutor
→ TikHubCollectionScopeExecutor
→ Provider Request / Attempt
→ Raw Artifact
→ Mapper
→ Canonical Content / Comment
→ fenced Ingestion
→ Job / Run / Scope succeeded
```

`create_collection_job_registry(...)` 复用既有：

- `JobRegistry` / `register_collection_run_job`；
- `CollectionRunJobHandler` / `CollectionRunExecutor`；
- `PostgresCollectionRunExecutionGateway`；
- `TikHubCollectionScopeExecutor`；
- `ArtifactService` / `RawArtifactService`；
- `PostgresArtifactMetadataGateway`；
- `TikHubHttpTransport`；
- 正式 Secret Reader；
- PostgreSQL Job Runtime。

未建立第二套 Worker、Provider Client、Raw Service、Mapper、Repository 或 Scheduler。

现有 `create_job_worker(...)` keyword-only 公共 API 保持不变。

## Transport 生命周期与出站安全

默认 Worker TikHub Transport 每次发送后关闭其自持 `httpx.Client`，未留下无人管理的 Client 生命周期。

代码质量/安全 Review 发现一个重要问题：原 TikHub Transport 只检查 HTTPS，理论上可把 Bearer Secret 发送到任意 HTTPS Base URL。先建立安全 Red：

```text
1 failed, 198 passed
原因：TikHubHttpTransport(base_url="https://example.com") 未抛 ValueError
```

随后在 TikHub Adapter 的出站边界限制到批准的：

```text
https://api.tikhub.io
```

并同时校验注入的 `httpx.Client.base_url`；禁止非 TikHub host、非标准 HTTPS Origin、嵌入凭据、query、fragment 或 path prefix 接收 TikHub Bearer Secret。

Green 后：

```text
Collection Unit / Provider Contract: 199 passed
PostgreSQL Collection Integration: 52 passed
```

## 五平台与快手主链

五个平台：

```text
xhs
douyin
weibo
bilibili
kuaishou
```

均通过同一 `TikHubCollectionScopeExecutor → TikHub runtime → 对应 Operation / Mapper` 边界；现有真实脱敏 Fixture、Operation/Mapper/Capability 测试和 PostgreSQL 纵切满足本 Stage 验收，不重复创建五套大型纵切。

快手正式评论 Operation 最终保持 App；Web 备用未进入 Runtime 自动 fallback。

# Red → Green → Refactor 证据

## Worker Red

初始正式 Red：

```text
ImportError:
cannot import name 'create_collection_job_registry'
from 'aima_ugc.bootstrap.worker'

exit code: 2
```

随后最小实现 Registry，并进一步先把测试切换到正式 `entrypoints/worker_main` 形成入口 Red，再由正式 entrypoint 导出同一装配实现转 Green。

## 质量门禁根因修复

过程中按新鲜 CI 根因依次修复：

- `collection_scope.py` 3 处 Ruff format 漂移；
- 3 个 Collection Integration 测试的 Ruff I001 导入顺序；
- `ProviderRequestV1.create()` 的 `request_params` 从宽泛 `dict[str, object]` 收紧为既有 `JsonObject` Contract 类型；
- TikHub Transport 出站 Origin 安全边界。

未删除失败测试、未降低 Ruff/mypy/Architecture/Table Ownership/Secret/Docs/Contract 门禁。

# Migration / Contract / Schema 影响

## Migration

Migration head 保持：

```text
20260817_0015 (head)
```

最终验证：

```text
alembic check:
No new upgrade operations detected.
```

同时完成：

- base → head downgrade/upgrade round-trip；
- previous revision → head downgrade/upgrade round-trip。

历史 `0012/0013/0014` 未改写。

## Contract

- 未新增 Budget Contract；
- 未改写 Canonical V1；
- `ReplyDecisionRequestV1` / `ReplyDecisionV1` 保持当前真实字段和动作；
- Provider Request JSON 参数类型只与现有 `JsonObject` Contract 对齐，没有放宽公共 Contract。

## Schema

当前 Schema 不再注册：

```text
provider_budget_accounts
provider_budget_reservations
collection_plans.request_budget
```

Provider Billing/Pricing/成本审计字段继续保留。

# Review 结果

PR #55 最终 head `056e8f5684b19f6b40c4e7c4755593aee3336a7a` 完成两阶段 Review：

1. 需求符合性 Review：通过；
2. 代码质量 / 安全 / 兼容性 Review：通过。

安全 Review 发现的 TikHub 任意 HTTPS Base URL 问题已通过 Red → Green 修复。最终不存在未解决的严重/重要 Review 问题，也不存在 Review Thread。

# 最终 PR Head CI

最终实现 head：

```text
056e8f5684b19f6b40c4e7c4755593aee3336a7a
```

该 head 实际触发并取得：

```text
11 / 11 PR workflows success
```

关键新鲜证据：

```text
Collection Unit / Provider Contract: 199 passed
PostgreSQL Collection Integration: 52 passed
Alembic: 20260817_0015 (head)
alembic check: No new upgrade operations detected.
Ruff: success
mypy: success
Architecture: success
Table Ownership: success
Secret Scan: success
Docs / Contract: success
Migration round-trip: success
```

# 合并后 main 新鲜 CI

PR #55 正常 merge 后：

```text
main:
737151a179a4b941c8bdc553cc77c4286bcb6d27
```

该 merge commit 实际触发 11 条 `push` workflow，最终：

```text
11 / 11 success
in_progress = 0
```

因此不是复用 PR 旧结果，而是取得了合并后 `main` 的新鲜成功证据。

# TikHub Probe 状态

本轮没有新增付费 TikHub Real Probe。原因：Stage 7 当前已有五平台合法脱敏真实 Fixture、既有受限 Real Probe/API-family A/B 与生产 Mapper/Canonical/PostgreSQL 证据，Worker/安全收尾只需要 `FakeProviderTransport` 和本地 Contract/DB/CI 即可证明。本轮未用付费 HTTP 代替可重复回归，也未泄露 API Key。

# 最终验收

- [x] live Worker 正式链闭环；
- [x] 当前 Change 成功标准完成；
- [x] 当前实现没有重新引入预算功能；
- [x] 快手 App comments/sub-comments 主链保持；
- [x] 无自动 Provider/App/Web fallback；
- [x] 需求符合性 Review 完成；
- [x] 代码质量、安全、兼容性 Review 完成；
- [x] Review 严重/重要问题全部处理；
- [x] PR #55 最终 head 新鲜 CI 11/11 全绿；
- [x] PR #55 从 Draft 正常转 Ready；
- [x] PR #55 正常合入 `main`；
- [x] 合并后 `main` 11/11 push workflow 新鲜全绿；
- [x] Change 更新为 `done`；
- [x] Change 按仓库规则归档到 `changes/archive/2026-08/`；
- [x] Stage 8 未开始。

本归档 PR 只处理 Change 生命周期与必要的当前阶段导航同步，不新增 Stage 7 业务实现，也不开始 Stage 8。
