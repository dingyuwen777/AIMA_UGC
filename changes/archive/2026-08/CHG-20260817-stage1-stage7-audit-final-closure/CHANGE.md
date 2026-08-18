---
schema: rvc-change/v1
id: CHG-20260817-stage1-stage7-audit-final-closure
title: 闭环 Stage 1-7 审计剩余问题
level: L2
status: done
owner: dingyuwen777
branch: fix/stage1-stage7-audit-final-closure
created: 2026-08-17
updated: 2026-08-17
depends_on: [CHG-20260817-stage1-stage7-audit-correctness]
affected_areas: [content, collection, operations, provider, testing, documentation]
affected_paths: [backend/src/aima_ugc/modules/content/, backend/src/aima_ugc/operations/jobs/, backend/src/aima_ugc/modules/collection/, backend/src/aima_ugc/adapters/providers/tikhub/pricing.toml, tests/unit/content/, tests/unit/collection/, tests/integration/jobs/, tests/integration/collection/, docs/blueprint/05-日志安全部署与运维.md, docs/blueprint/06-开发约束与分阶段实施.md, changes/archive/2026-08/CHG-20260815-stage7-completion/CHANGE.md, .github/workflows/stage5a-provider-raw.yml]
contracts: []
data_changes: []
---

# 完成结论

本 Change 已完成实现、Red→Green、两阶段 Review、PR 合并、合并后 `main` 新鲜 CI 与生命周期归档。它只闭环 2026-08-17 全面审计在前两轮整改后仍未清零的 Stage 1—7 问题，**未进入 Stage 8，也未提前实现 Release 能力**。

实现 PR：`#61 闭环 Stage 1-7 审计剩余问题`

```text
开始 main:
3519fcd360b8e8201ed03ff1a7c0013c662ab528

最终 PR head:
0b06d2beec4b859329cf04507f34a638b060c934

PR #61 merge commit / 合并后 main:
0e35a7c6a22a2a0c4a210a2087a4e7b9ec4282ce
```

PR #61 正常合并，未强推、未绕过 Branch Protection、未跳过 CI。最终 PR head 实际取得 `12/12` PR workflows success；合并后的 `main@0e35a7c6a22a2a0c4a210a2087a4e7b9ec4282ce` 实际触发 11 条 push workflow，最终 `11/11 success`、`failure=0`、`in_progress=0`。

# 最终闭环的问题

1. `InMemoryContentRepository` 在已支持字段子集上对齐 PostgreSQL 字段级 sparse/out-of-order freshness，较旧 Observation 不再回滚更晚 Current；较旧未观察字段仍可补充，显式 `null` 会推进 freshness。
2. Job / Collection / Provider / Raw 主链补齐稳定结构化生命周期事件，并保持日志不记录 Payload、Raw、request_params、请求/响应正文、Authorization、Secret 或 Lease/Fencing Token。
3. Collection 日志诊断读取使用安全值，不再因损坏 stats 破坏 Scope 原有异常隔离；真正 durable stats 的严格校验没有放宽。
4. Blueprint 06 不再把当前不存在的 `compose.yaml` 作为 Stage 1—7 无条件必读，也不再把已撤回 Budget/Reservation Ledger 写成当前强制 Integration 专项。
5. TikHub `pricing.toml` 只保留 endpoint Pricing / Provider Attempt 成本审计事实，不再描述当前存在硬预算或 Reservation。
6. Stage 7 Completion Change 的最终 `data_changes` 不再包含已经撤回并删除的 Budget 表；历史正文过程保留。
7. Stage 5A 专项 CI 固定覆盖 Raw Artifact 生命周期日志回归。

# 稳定日志事件契约

最终事件名以当前 Blueprint 05 为准：

```text
job.started
job.retry_scheduled
job.completed
job.failed
job.cancelled
job.lease_lost
job.heartbeat_failed

collection.run.started
collection.run.completed
collection.scope.completed

provider.request.started
provider.request.completed
provider.request.failed

raw.artifact.stored
raw.artifact.write_failed
```

失败 Run 使用 `collection.run.completed + status=failed`；Provider unknown 使用 `provider.request.failed + status=unknown`。未建立平行的 `collection.run.failed` 或 `provider.request.unknown`。

# Red → Green 证据

## InMemory / Collection / Provider Red

测试-only head `f0c6d3a97106843bbc60bd988e23b0d448c1686c`：

```text
Stage 6 Unit: 5 failed, 205 passed
Stage 5D:     3 failed, 205 passed
```

失败直接证明较旧 Content 回滚更晚字段、显式 `null` 被较旧值回滚，以及 Collection/Provider 稳定事件缺失。

## Job Red

修正取消场景为真实 `request_cancel` 前置后，head `c2c5eaac8f3c3d49393a430bdf04a05c8622e2e7`：

```text
Stage 4 Job Runtime: 4 failed, 46 passed
```

四类 Job 结果均只因缺少 `job.started + terminal event` 失败。

## 初始 Green

```text
93f8de24894de311ce156db3d8d3c83af1bf4402  闭环审计剩余运行语义与日志
2dd28dbb0aae1cd987116c89e12806779193a119  按 Ruff 整理审计整改格式
```

第二个提交后的 12/12 PR workflows 全部 success。

## Review 期间新增回归

- Scope 日志故障隔离回归曾得到 `1 failed / 208 passed` 的有效 Red；修复后日志诊断字段安全读取，严格 durable stats 校验保留。
- Raw Artifact 生命周期回归证明 `raw.artifact.stored` / `raw.artifact.write_failed` 缺失；最终在成功存储/恢复确认后记录 stored，写失败只记录异常类型和 lineage 并原样抛出。
- Review 曾测试额外 `collection.run.failed` / `provider.request.unknown`，重新对照 Blueprint 05 后确认它们未获批准，最终测试与生产实现均收敛到稳定事件名 + `status` 表达状态。

# 最终验证

PR #61 最终 head：

```text
0b06d2beec4b859329cf04507f34a638b060c934
```

实际：

```text
12 / 12 PR workflows success
```

包括主 CI、Stage 1-7 Audit Correctness、Stage 4、Stage 5A/5B/5C/5D、Stage 6、Keyword Packs、Provider Config Routing、Plan Occurrence Run Snapshot、Scheduler Runtime。

合并后：

```text
main = 0e35a7c6a22a2a0c4a210a2087a4e7b9ec4282ce
11 / 11 push workflows success
failure = 0
in_progress = 0
```

这不是复用 PR 旧结果，而是合并后 `main` 的新鲜验证。

# 两阶段 Review

需求符合性 Review 已逐项对照原审计剩余问题、当前 Blueprint、最终 diff 和非目标；代码质量 Review 已检查正确性、异常传播、日志安全、Scope 故障隔离、兼容性、无关改动和测试有效性。PR 合并前没有未解决 inline review thread，也没有剩余 P0/P1/P2 blocker。

# 兼容、部署与回滚

- 公共 API / Canonical / Provider / OpenAPI Contract：不变化。
- 数据库 / Migration：不变化。
- 依赖 / Lock：不变化。
- 五平台 Operation / 快手 App 评论主链：不变化。
- Scheduler：继续 `latest_only + max_catch_up_runs=0`。
- Budget Runtime / Budget Account / Reservation Ledger：继续删除状态。
- Worker/Reaper 常驻进程管理：继续属于后续 Release，本 Change 未实现 supervisor loop。
- 生产部署：仍 No-Go，本 Change 未改变 Docker/离线 Release/协调 Backup-Restore 门禁。
- 回滚本 Change 只会失去新增生命周期日志和 InMemory Fake parity，不涉及数据迁移。

# 最终验收

- [x] 5 类剩余审计问题全部闭环；
- [x] Red→Green 证据成立；
- [x] 正式文档与机器事实同步；
- [x] 无依赖升级、无公共 Contract/Schema/Migration 变化；
- [x] Stage 8 / Release / Budget 非目标保持；
- [x] 两阶段 Review 完成；
- [x] PR #61 最终 head 12/12 全绿；
- [x] PR #61 正常合入 `main`；
- [x] 合并后 `main` 11/11 push workflow 新鲜全绿；
- [x] Change 更新为 `done` 并归档；
- [x] Stage 8 尚未开始。
