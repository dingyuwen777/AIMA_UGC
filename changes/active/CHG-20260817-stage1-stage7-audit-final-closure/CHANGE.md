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
affected_paths: [backend/src/aima_ugc/modules/content/, backend/src/aima_ugc/platform/jobs/, backend/src/aima_ugc/modules/collection/, backend/src/aima_ugc/adapters/providers/tikhub/pricing.toml, tests/unit/content/, tests/unit/collection/, tests/integration/jobs/, docs/blueprint/06-开发约束与分阶段实施.md, changes/archive/2026-08/CHG-20260815-stage7-completion/CHANGE.md]
contracts: []
data_changes: []
---

# 背景与现状

`main@3519fcd360b8e8201ed03ff1a7c0013c662ab528` 已完成前两轮 Stage 1—7 正确性整改及 Change 归档。交付前重新逐项反查 2026-08-17 全面审计原始 Findings 后确认仍有 5 个问题未真正清零，因此新建本 Change；已归档 Change 不重新激活。

本 Change 不进入 Stage 8，也不改变既有业务 Contract、Schema、Provider Operation、Scheduler 或 Budget 回撤决定。

# 目标

1. 让 `InMemoryContentRepository` 在其已支持的 Content 子集上与生产 PostgreSQL Repository 使用相同的字段级 sparse/out-of-order Current freshness 语义，避免 Unit Fake 维护第二套错误状态机。
2. 在正式 Job / Collection / Provider 主链补齐 Blueprint 已批准的稳定结构化生命周期事件，复用现有 `log_event` 与 Formatter，不增加第二套日志框架。
3. 修正 Blueprint 06 当前阶段无条件要求不存在 Compose，以及已撤回 Budget/Reservation 专项仍被写成当前强制测试的问题。
4. 修正 `pricing.toml` 已失效的硬预算/Reservation 注释，只保留当前 Pricing/Billing 事实。
5. 修正 Stage 7 Completion Change 最终 `data_changes` 仍包含已撤回 Budget 表的 metadata 冲突。

# 可观察成功标准

- [x] InMemory Content 回归在旧实现证明较旧 Observation 会错误回滚更晚已观察字段；修复后通过。
- [x] InMemory 支持“较旧 Observation 补充更晚未观察字段”和“更晚显式 null 阻止较旧非空回滚”，`first_seen_at` 可向前扩展且 `last_seen_at` 单调向前。
- [x] JobWorker 通过正式生产入口输出 `job.started`、`job.completed`、`job.retry_scheduled`、`job.failed`、`job.cancelled`；Lease/Heartbeat 异常继续使用稳定结构化 warning，日志不含 Lease Token/Payload/Secret。
- [x] CollectionRunExecutor 输出 `collection.run.started`、`collection.scope.completed`、`collection.run.completed`，只记录关联 ID、状态与安全聚合字段，不记录 Provider/用户原文。
- [x] ProviderDispatchService 输出 `provider.request.started`、`provider.request.completed` / `provider.request.failed`，只记录 lineage/status/duration/billing/artifact 等安全字段，不记录请求/响应正文、request_params 或 Secret。
- [x] 日志事件测试从正式 Worker/Executor/Dispatch 入口验证 `record.event` 和关联字段，不只测试 Mock Logger。
- [x] Blueprint 06 不再把当前不存在的 `compose.yaml` 作为所有任务无条件必读，也不再把已撤回 Budget/Reservation Ledger 写成当前强制 Integration 专项；未来 Budget 仍需新的 L3 Change。
- [x] `pricing.toml` 不再声称当前存在硬预算或 Reservation；Pricing endpoint/价格数据未改变。
- [x] `CHG-20260815-stage7-completion` 最终 `data_changes` 不再包含 `provider_budget_accounts/provider_budget_reservations`；历史正文过程保持不改写。
- [x] 未新增/升级依赖，未改变公共 Contract、Schema/Migration、五平台 Operation、Scheduler 策略、Budget 回撤或 Stage 8/Release 非目标。
- [x] 目标测试、相关 Unit/PostgreSQL Integration、Ruff、mypy、Architecture/Table Owner、Secret、Docs 与主/相关 Stage CI 已在候选 head 取得新鲜成功证据。
- [ ] PR 完成最终两阶段 Review、正常合并后，`main` 再取得新鲜成功 CI，并归档本 Change。

# Red → Green 证据

## InMemory / Collection / Provider Red

测试-only head `f0c6d3a97106843bbc60bd988e23b0d448c1686c`：

```text
Stage 6 Unit:
5 failed, 205 passed
```

其中：

- 较旧 Content title 把 `NEW` 错误回滚为 `OLD`；
- 更晚显式 `null` 被较旧 `OLD TEXT` 回滚；
- Collection/Provider 三个失败均为稳定 `record.event` 缺失。

同一 Red 的 Stage 5D：

```text
3 failed, 205 passed
```

三处失败均为 Collection / Provider 生命周期事件缺失。

## Job Red

取消测试先修正为真实 `request_cancel` 前置后，head `c2c5eaac8f3c3d49393a430bdf04a05c8622e2e7`：

```text
Stage 4 Job Runtime:
4 failed, 46 passed
```

`succeeded/retry/failed/cancelled` 四种结果均只因没有 `job.started + terminal event` 失败。

## Green

实现提交：

```text
93f8de24894de311ce156db3d8d3c83af1bf4402
闭环审计剩余运行语义与日志
```

首轮 Green 的功能/Contract 测试已通过；Stage 5A 当轮为：

```text
21 passed
```

唯一失败是 Ruff 报告新增文件机械格式差异。随后提交：

```text
2dd28dbb0aae1cd987116c89e12806779193a119
按 Ruff 整理审计整改格式
```

该 head 的 12/12 PR workflows 全部 success。

# 最终事实修正

由于 GitHub Contents API 不提供小范围 patch，且当前执行环境不能 DNS clone GitHub，本轮曾建立一次性分支 workflow 做两处精确字符串替换。该 workflow：

- 仅在本开发分支运行；
- 替换数量不等于 1 时 fail-close；
- 使用 `git diff --check`；
- 成功后已从分支删除；
- **最终 PR diff 不包含该临时 workflow。**

实际修正：

1. Blueprint 06 移除当前 Stage 1—7 无条件 `compose.yaml` 必读，明确只有进入 Release/Compose 且文件已建立时读取；
2. Blueprint 06 删除当前强制多级 Budget/Reservation Integration 专项，改为未来新 L3 Change 冻结 Contract/Schema/Migration 后再建立；
3. Stage 7 Completion `data_changes` 只保留最终实际 `collection_plans / collection_schedule_occurrences / collection_runs`；
4. Pricing 注释只保留 endpoint Pricing / Provider Attempt 成本审计事实。

最终候选 head：

```text
9b2996d84ef671583b7b8b956eb3761a2c94c85a
```

该 head 实际取得：

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

# 实现结果

## InMemory Content Fake

- 只为当前 Fake 已支持的 `content_type/title/text/metrics.like_count` 保存私有字段 freshness；
- 不扩张 `ContentCurrent` 公共测试结构；
- 较旧 Observation 只能补充未被更晚观察的字段；
- 显式 null 推进 freshness；
- 较旧指标仍可形成合法历史 Observation，但不能回滚更晚 Current；
- 保持 `A → B → A` 当前版本行为与既有 Metric History 边界。

## Job 生命周期日志

复用 `aima_ugc.platform.logging.log_event`：

```text
job.started
job.completed
job.retry_scheduled
job.failed
job.cancelled
job.lease_lost
job.heartbeat_failed
```

`job.started` 只在成功 Claim 后记录；终态/重试事件只在 Repository 状态转换提交后记录。Handler 未收敛异常不会伪装成已持久化 `job.failed`。

## Collection 生命周期日志

```text
collection.run.started
collection.scope.completed
collection.run.completed
```

只记录 Run/Job/Scope ID、平台、operation group、状态、停止原因和计数，不记录 `source_value`、Provider Raw 或用户原文。

## Provider 生命周期日志

```text
provider.request.started
provider.request.completed
provider.request.failed
```

开始事件位于 `start_dispatch` CAS 成功之后；终态事件位于 `finalize_dispatch` 成功之后。日志不记录 `request_params`、Transport Request/Response Body、Authorization、Raw 或 Fence Token。

# 兼容、部署与回滚

- 公共 API/Canonical/Provider Contract：不变化。
- 数据库/Migration：不变化。
- 依赖/锁文件：不变化。
- 五平台 Operation、快手 App 评论主链：不变化。
- Scheduler：继续 `latest_only + max_catch_up_runs=0`。
- Budget Runtime：继续删除状态。
- Worker/Reaper 常驻进程管理：继续属于 Release，不在本 Change 实现。
- 生产部署：仍 No-Go，本 Change 不改变 Release 门禁。
- 回滚本代码只会失去新增生命周期日志与 InMemory parity，不涉及数据迁移。

# Review 状态

需求符合性复核已逐项对照原审计剩余 5 项、当前 Change、Blueprint 与最终 diff；没有发现 Stage 8/Release/Budget 范围扩张。

代码质量 Review 正在以最终 Change 提交后的 head 完成最后核验；PR 合并和合并后 `main` CI 未执行前，本 Change 保持 `ready_for_review`，不提前标记 `done`。

# Git

- 基线 main：`3519fcd360b8e8201ed03ff1a7c0013c662ab528`
- 开发分支：`fix/stage1-stage7-audit-final-closure`
- PR：`#61 闭环 Stage 1-7 审计剩余问题`
- 当前候选实现 head：`9b2996d84ef671583b7b8b956eb3761a2c94c85a`
- 合并：尚未执行
- Change：`ready_for_review`
