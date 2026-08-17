---
schema: rvc-change/v1
id: CHG-20260817-stage1-stage7-audit-final-closure
title: 闭环 Stage 1-7 审计剩余问题
level: L2
status: ready_for_review
owner: dingyuwen777
branch: fix/stage1-stage7-audit-final-closure
created: 2026-08-17
updated: 2026-08-17
depends_on: [CHG-20260817-stage1-stage7-audit-correctness]
affected_areas: [content, collection, platform, provider, testing, documentation]
affected_paths: [backend/src/aima_ugc/modules/content/, backend/src/aima_ugc/platform/jobs/, backend/src/aima_ugc/modules/collection/, backend/src/aima_ugc/adapters/providers/tikhub/pricing.toml, tests/unit/content/, tests/unit/collection/, tests/integration/jobs/, tests/integration/collection/, docs/blueprint/05-日志安全部署与运维.md, docs/blueprint/06-开发约束与分阶段实施.md, changes/archive/2026-08/CHG-20260815-stage7-completion/CHANGE.md, .github/workflows/stage5a-provider-raw.yml]
contracts: []
data_changes: []
---

# 背景与现状

`main@3519fcd360b8e8201ed03ff1a7c0013c662ab528` 已完成前两轮 Stage 1—7 正确性整改及 Change 归档。交付前再次逐项反查 2026-08-17 全面审计原始 Findings 后，确认仍有 5 个问题没有真正清零：InMemory Fake 与 PostgreSQL Current 时序语义漂移、关键生命周期日志不足、Blueprint 06 的 Compose/Budget 旧规则、Pricing 旧预算注释、Stage 7 Completion Change 最终 metadata 残留已删除 Budget 表。

本 Change 只闭环这些剩余事实，不进入 Stage 8，也不改变公共 Contract、数据库 Schema/Migration、Provider Operation、Scheduler 或 Budget 回撤决定。

# 目标与成功标准

- [x] InMemory Content Fake 在其已支持字段子集上使用字段级 sparse/out-of-order freshness，不再让较旧 Observation 回滚更晚 Current。
- [x] 较旧 Observation 可补充更晚未观察字段；更晚显式 `null` 可以阻止较旧非空值回滚；`first_seen_at` 可向前扩展，`last_seen_at` 单调向前。
- [x] JobWorker 从正式入口记录 `job.started`、`job.completed`、`job.retry_scheduled`、`job.failed`、`job.cancelled`，Lease/Heartbeat 异常使用 `job.lease_lost` / `job.heartbeat_failed`；日志不记录 Payload、Lease Token 或 Secret。
- [x] CollectionRunExecutor 记录 `collection.run.started`、`collection.scope.completed`、`collection.run.completed`；Run 失败仍使用稳定 `collection.run.completed`，由 `status=failed` 区分，不扩张 Blueprint 事件名。
- [x] Collection 日志读取损坏的诊断 stats 时不会再次抛异常破坏 Scope 故障隔离；真正 durable stats 的 `_stat_int()` 严格校验保持不变。
- [x] ProviderDispatchService 记录 `provider.request.started`、`provider.request.completed`、`provider.request.failed`；`unknown` 使用 `provider.request.failed + status=unknown` 区分，不扩张 Blueprint 事件名。
- [x] Raw Artifact 正常 capture / pending recovery 在成功确认后记录 `raw.artifact.stored`；写入失败记录 `raw.artifact.write_failed` 后原样抛出。
- [x] Job / Collection / Provider / Raw 日志测试均从正式生产入口验证事件、关联 ID 与敏感字段排除，不只验证 Mock Logger。
- [x] Blueprint 06 不再无条件要求当前不存在的 `compose.yaml`，也不再把已撤回 Budget/Reservation Ledger 写成当前强制 Integration 专项；未来 Budget 仍需新的 L3 Change。
- [x] `pricing.toml` 不再声称当前存在硬预算或 Reservation；endpoint 路径、价格与核验状态均未改变。
- [x] `CHG-20260815-stage7-completion` 最终 `data_changes` 不再包含 `provider_budget_accounts/provider_budget_reservations`，历史正文过程不重写。
- [x] 未新增/升级依赖，未改变 Canonical/Provider/OpenAPI Contract、Schema/Migration、五平台主 Operation、快手 App 评论主链、Scheduler `latest_only + max_catch_up_runs=0`、Budget 回撤或 Stage 8/Release 非目标。
- [x] 当前候选 head 的主 CI、相关 PostgreSQL Integration、Ruff、mypy、Architecture/Table Owner、Secret、Docs 与全部相关 Stage workflow 已取得新鲜成功证据。
- [ ] PR #61 正常合并后，合并后的 `main` 再取得新鲜成功 CI；随后把本 Change 更新为 `done` 并归档。

# Red → Green 证据

## InMemory / Collection / Provider Red

测试-only head `f0c6d3a97106843bbc60bd988e23b0d448c1686c`：

```text
Stage 6 Unit: 5 failed, 205 passed
Stage 5D:     3 failed, 205 passed
```

失败分别证明：较旧 Content 会回滚更晚字段、显式 `null` 会被较旧值回滚，以及 Collection/Provider 稳定事件缺失。

## Job Red

修正取消测试的真实 `request_cancel` 前置后，head `c2c5eaac8f3c3d49393a430bdf04a05c8622e2e7`：

```text
Stage 4 Job Runtime: 4 failed, 46 passed
```

`succeeded / retry / failed / cancelled` 四类结果均只因缺少 `job.started + terminal event` 失败。

## 初始 Green

实现提交：

```text
93f8de24894de311ce156db3d8d3c83af1bf4402  闭环审计剩余运行语义与日志
2dd28dbb0aae1cd987116c89e12806779193a119  按 Ruff 整理审计整改格式
```

第二个提交后的 12/12 PR workflows 全部 success。

## Review 发现的日志故障隔离

新增回归证明 Scope 本身的异常已被 Executor 隔离，但日志路径曾使用严格 `_stat_int()` 读取损坏 stats，导致日志再次抛错。有效 Red：

```text
Stage 5D: 1 failed, 208 passed
```

修复后日志只用 `_log_stat_int()` 安全读取诊断计数；真正恢复/聚合仍使用严格 `_stat_int()`，没有降低数据校验标准。

## Raw 生命周期事件

新增 Raw 日志回归后，已有 Raw/Provider 行为测试保持通过；有效行为 Red 证明 `raw.artifact.stored` / `raw.artifact.write_failed` 缺失。最终实现：

- `raw.artifact.stored` 在 Artifact 已经成功 `stored` 后记录；
- pending Raw recovery 也只在完整性/lineage 校验和 metadata 确认后记录；
- `raw.artifact.write_failed` 只记录异常类型与 lineage，不记录异常正文、Raw、请求或响应正文，并重新抛出原异常。

Stage 5A 已把 `tests/integration/collection/test_raw_artifact_logging.py` 纳入专用门禁。

## 事件契约收敛

Review 期间曾为 `unknown` Provider Attempt 和失败 Run 引入额外事件名的测试。重新读取当前 Blueprint 05 后确认正式稳定事件契约是：

```text
collection.run.started
collection.run.completed
collection.scope.completed

provider.request.started
provider.request.completed
provider.request.failed

raw.artifact.stored
raw.artifact.write_failed
```

因此最终实现不额外建立 `collection.run.failed` / `provider.request.unknown`：失败 Run 通过 `collection.run.completed + status=failed` 表达；Provider unknown 通过 `provider.request.failed + status=unknown` 表达。测试已同步到这一长期设计，不以测试反向修改 Blueprint。

# 文档与历史事实修正

- Blueprint 05 同步当前实际稳定 Job/Collection/Provider/Raw 事件，包括 `job.heartbeat_failed` 与 `raw.artifact.write_failed`。
- Blueprint 06 移除 Stage 1—7 无条件 `compose.yaml` 必读；只有进入 Release/Compose 且文件已建立时才读取。
- Blueprint 06 移除当前强制多级 Budget/Reservation Integration 专项，改为未来新的 L3 Change 冻结 Contract/Schema/Migration 后再建立。
- `pricing.toml` 只修注释，不改 endpoint Pricing 数据。
- Stage 7 Completion Change 的最终 `data_changes` 只保留实际 `collection_plans / collection_schedule_occurrences / collection_runs`；历史 Budget 回撤过程正文保留。

本轮为避免 GitHub Contents API 整篇重写大型文档，曾使用仅限开发分支的一次性精确 patch workflow；每个替换都要求匹配次数为 1 并运行 `git diff --check`，成功后立即删除。**最终 PR diff 不包含任何临时 patch workflow。**

# 当前实现边界

## InMemory Content Fake

只为 Fake 原本已经支持的 `content_type/title/text/metrics.like_count` 保存私有 freshness，不扩张 `ContentCurrent`，也不复制 PostgreSQL Repository 的完整实现。

## 日志安全

新增事件只保存稳定关联字段、状态、计数、费用快照和 Artifact ID。没有记录：

```text
request_params
Provider request/response body
Raw body
Authorization
Secret
Job Payload
Lease/Fencing Token
source_value / 用户原文
```

日志事件均放在既有状态边界之后；日志本身不改变 Provider 发送、Raw-first、Job Fencing、Collection 故障隔离或事务语义。

# 兼容、部署与回滚

- 公共 API / Canonical / Provider Contract：不变化。
- 数据库 / Migration：不变化。
- 依赖 / Lock：不变化。
- 五平台 Operation 与快手 App 评论主链：不变化。
- Scheduler：继续 `latest_only + max_catch_up_runs=0`。
- Budget Runtime：继续删除状态。
- Worker/Reaper 常驻进程管理：继续属于 Release，本 Change 不实现 supervisor loop。
- 生产部署：仍 No-Go，本 Change 不改变 Release 门禁。
- 回滚本 Change 只会失去新增生命周期日志和 InMemory Fake parity，不涉及数据迁移。

# 最终候选与验证

当前候选 head：

```text
acef89d5fe9afad9ce6e8ee407de10d2c9be2178
```

该 head 已实际取得：

```text
12 / 12 PR workflows success
```

包括：

- CI
- Stage 1-7 Audit Correctness
- Stage 4 Job Runtime
- Stage 5A Provider Raw
- Stage 5B Collection Execution
- Stage 5C Provider Persistence
- Stage 5D Provider Dispatch
- Stage 6 XHS Vertical Slice
- Stage 7 Keyword Packs
- Stage 7 Provider Config Routing
- Stage 7 Plan Occurrence Run Snapshot
- Stage 7 Scheduler Runtime

需求符合性 Review 已逐项对照原审计剩余问题、当前 Blueprint、最终 diff 与非目标；代码质量 Review 已检查正确性、异常传播、日志安全、故障隔离、兼容、无关改动和测试有效性，当前没有未解决 P0/P1/P2 blocker。

# Git

- 基线 main：`3519fcd360b8e8201ed03ff1a7c0013c662ab528`
- 开发分支：`fix/stage1-stage7-audit-final-closure`
- PR：`#61 闭环 Stage 1-7 审计剩余问题`
- 当前候选 head：`acef89d5fe9afad9ce6e8ee407de10d2c9be2178`
- PR：尚未合并
- 合并后 main 验证：尚未执行
- Change：`ready_for_review`
