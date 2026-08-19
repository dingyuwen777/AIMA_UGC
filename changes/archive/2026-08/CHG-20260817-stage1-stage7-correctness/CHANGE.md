---
schema: rvc-change/v1
id: CHG-20260817-stage1-stage7-correctness
title: 修复 Stage 1-7 未闭环正确性与恢复缺陷
level: L3
status: done
owner: dingyuwen777
branch: fix/stage1-stage7-correctness
created: 2026-08-17
updated: 2026-08-17
depends_on: [CHG-20260815-stage7-completion]
affected_areas: [platform, jobs, collection, content, provider, database, migration, testing, ci, documentation]
affected_paths: [backend/src/aima_ugc/platform/jobs/, backend/src/aima_ugc/modules/collection/, backend/src/aima_ugc/modules/content/, backend/src/aima_ugc/adapters/persistence/postgres/, backend/src/aima_ugc/bootstrap/, migrations/versions/, tests/unit/, tests/integration/, .github/workflows/, README.md, docs/]
contracts: []
data_changes: [comment_coverage_observations]
---

# 完成结论

Stage 1—7 正确性与恢复整改已于 2026-08-17 完成实现、Red→Green、两阶段 Review、PR 合并、合并后 `main` 新鲜 CI 与 Change 生命周期归档。

本 Change 只修复既有 Stage 1—7 已批准语义，没有进入 Stage 8，也没有提前实现 Release 阶段的正式 Docker/离线发布/协调 Backup-Restore/维护写屏障。

实现 PR：`#57 修复 Stage 1-7 正确性与恢复缺陷`

```text
开始 main:
7e923680bf4931657597d8756c378480d9fe95b6

最终实现 PR head:
baf331cd7049b5cc67e4f43730bbe304388de541

PR #57 merge commit / 合并后 main:
cfedc01777e1999d2b4140c9eb0f42271445eaa0
```

PR #57 由 Draft 正常转为 Ready，并使用 `expected_head_sha=baf331cd7049b5cc67e4f43730bbe304388de541` 正常 merge；未强推、未重写历史、未绕过 CI 或仓库质量门禁。

# 最终范围与非目标

本轮完成：

- Provider `dispatching` Attempt 正式 Worker takeover / Reconciler 接线；
- Collection Run/Scope terminal skip、running checkpoint、durable 统计与 retry；
- Provider Request/Attempt 逻辑 Request 复用、可重试失败新 Attempt、不可重试 4xx takeover 不重发；
- 评论/二级回复软目标整页保留、Detail 后评论重决策；
- Account/Content/Comment 首次并发收敛；
- 旧 Observation 不回滚较新 Current；
- 稀疏指标历史；
- Comment Coverage 可观测持久化；
- CI、长期文档和一次性 Stage 7 Workflow 清理；
- `20260817_0016` 向前 Migration 与回退验证。

明确未做：

- Stage 8 HTTP CRUD、业务页面、认证授权和 Provider Secret 写 API；
- Release Docker Compose、离线 Release、协调 Backup/Restore、维护写屏障和生产恢复演练；
- Redis、Celery、Kafka、工作流引擎或新的基础设施；
- 五平台已批准主 Operation 变更、自动 Provider/App/Web fallback；
- Budget Account、Reservation Ledger、发送预算门禁；
- 依赖新增、升级或降级；
- Canonical V1、Provider V1、OpenAPI 或生成 Client 的公共 Contract 变化。

# 最终实现结果

## Provider 崩溃恢复与重试

正式 Scope 在执行前调用 `ProviderAttemptReconciler` 收敛遗留 `dispatching` Attempt。

```text
遗留 dispatching
→ 检查确定性 Raw
→ Raw 完整且校验通过：恢复 terminal + replay
→ 不再次发送 Provider

Raw 不存在/不可确认发送结果：
→ 保守 unknown
→ 后续真实重发必须建立新 Attempt
→ 保留 potential_duplicate_charge / Billing 审计事实
```

逻辑 Provider Request 由稳定 fingerprint 复用；任何真实重发都建立新 Provider Attempt。

当前自动 retry 边界保持：

```text
HTTP 408 / 425 / 429 / 5xx
Transport not_sent / unknown
```

非上述已完成 HTTP 4xx 不自动重试。Review 阶段新增了崩溃窗口回归：HTTP 400 已持久化且 Worker 在 Scope 失败终态提交前崩溃时，takeover 复用原失败 Attempt 并终止，Transport 不再被调用。

## Collection Run / Scope 恢复

- 已终态 Scope 在 Job retry / Lease takeover 后直接跳过；
- running Scope 的 `pagination_state / progress / stats` 通过 Fenced `checkpoint_scope()` 持久化；
- Scope 计数从 PostgreSQL Attempt/Candidate durable 事实恢复，不依赖进程内计数；
- retryable Provider 错误先保存 Scope checkpoint，再返回 Job retry；
- 普通不可重试 Scope 失败保持当前 Scope 隔离；
- Job progress 与 Scope 页进度不混用。

## 评论策略与 Coverage

评论和二级回复的 `target` 是“是否继续请求下一页”的软目标：当前 Provider 已经返回并付费的响应页全部 Mapper/Ingestion 后，才决定是否再请求下一页。

Search 阶段评论数未知并产生 `defer_until_detail` 时，Detail 完成后使用最新 Canonical 重新计算评论动作；不再次发送 Detail。

`comment_coverage_observations` 当前记录：

```text
coverage
reported_total
collected_count
sample_mode
sort_mode
target_count
stop_reason
observed_at
provider_attempt_id
raw_artifact_id
```

覆盖值保持：

```text
complete
partial
not_requested
unavailable
```

同一 `content_id + provider_attempt_id + raw_artifact_id` 来源幂等。XHS `0` 评论总数按明确零处理，不与缺失值混淆。

## Content Current / History 并发与乱序

Account、Content、Comment 首次建立身份使用 PostgreSQL UNIQUE + `ON CONFLICT DO NOTHING` 收敛并发赢家，不再依赖“先查后插”。

较旧 `observed_at` Observation：

- 可以向前扩展 `first_seen_at`；
- 可以保留合法 History/Metric/Raw 来源事实；
- 不覆盖较新的 Current 业务字段；
- 不回滚 Current 指标；
- 不回滚 `updated_at` / `current_version`。

指标历史按 `observed_fields` 稀疏保存；本次未观察到的指标保持 `NULL`，不从 Current 静默复制旧值伪造历史。

# Schema 与 Migration

新增向前 Revision：

```text
20260817_0016_comment_coverage_observability.py
```

它只为 `comment_coverage_observations` 增加：

```text
sample_mode
sort_mode
target_count
stop_reason
```

以及：

- `target_count >= 0` CHECK；
- `(content_id, provider_attempt_id, raw_artifact_id)` 来源唯一约束。

`0016` 之前可能已经存在的历史 Coverage 行不被伪造补值；新写入路径由 Content Owner 强制提供可观测字段。

历史 `20260813_0001`—`20260817_0015` 未改写。`0016` 已验证 downgrade/upgrade、`base → head`、Stage 5C → head 和 `alembic check`。

# Red → Green 证据

## Content 并发 / 乱序

`tests/integration/content/test_content_current_concurrency.py`

覆盖：

- Content first insert 并发；
- Comment first insert 并发；
- Account first insert 并发；
- 旧 Observation 不回滚较新 Current；
- 稀疏指标历史不伪造未观察值。

并发测试使用 PostgreSQL 测试 Trigger 放大真实竞争窗口；生产 Schema 不保留该 Trigger。

## Coverage / Detail 后重决策

`tests/integration/collection/test_collection_comment_coverage_runtime.py`

覆盖：

- Search 评论数未知 → Detail 后重决策；
- 评论软目标整页保留；
- partial / complete Coverage；
- `reported_total=0`；
- Provider 空页 `stop_reason`；
- sample/sort/target/source 事实。

## Raw takeover 不重发

`tests/integration/collection/test_collection_scope_recovery_runtime.py`

构造：

```text
Provider 2xx
→ Raw 已完整落盘
→ Attempt 仍 dispatching
→ Worker Lease 失效
→ 新 Worker takeover
```

正式 Scope Reconciler 恢复 Search Attempt 并 replay Raw；新 Worker 的 Transport 只执行后续合法调用，不再次发送 Search。

## Provider retry

`tests/integration/collection/test_collection_worker_retry_runtime.py`

验证：

```text
HTTP 500
→ 第一次 Provider Attempt + Raw/错误事实保留
→ Job retry
→ 同一逻辑 Request
→ 新 Provider Attempt
→ 200 成功
```

## 非重试 4xx takeover

`tests/integration/collection/test_collection_nonretryable_4xx_recovery.py`

修复前真实 PostgreSQL Red：

```text
resumed_transport.call_count == 1
```

修复后 Green：

```text
resumed_transport.call_count == 0
Provider Attempt 总数仍为 1
原 HTTP 400 / Raw / error_code 保留
Scope failed / http_400
```

## Run / Scope

`tests/unit/collection/test_collection_run_recovery.py`

验证 terminal Scope 跳过、running checkpoint、retryable Scope 结果、durable stats 与 Job retry 映射。

# Review 结果

最终实现完成两阶段 Review：

1. 需求符合性 Review：通过；所有实现均可追溯到本 Change 成功标准，未进入 Stage 8/Release，未恢复 Budget，未更换五平台主 Operation；
2. 代码质量 / 安全 / 并发 / 兼容性 Review：通过。

Review 阶段发现并修复：

- Stage 5D 回退检查脚本语法问题；
- 已完成不可重试 HTTP 4xx 在 crash/takeover 窗口可能被再次发送的问题；
- 已删除一次性 Normalization Workflow 的文档死引用。

最终不存在未解决的严重/重要 Review 问题，PR #57 没有未解决 Review thread。

# 最终 PR Head CI

最终实现 PR head：

```text
baf331cd7049b5cc67e4f43730bbe304388de541
```

实际取得：

```text
11 / 11 正式 PR workflows success
```

对应运行：

```text
CI                                      32016971380
Stage 4 Job Runtime                     32016971160
Stage 5A Provider Raw                   32016971328
Stage 5B Collection Execution           32016971355
Stage 5C Provider Persistence           32016971251
Stage 5D Provider Dispatch              32016971330
Stage 6 XHS Vertical Slice              32016971150
Stage 7 Keyword Packs                   32016971363
Stage 7 Provider Config Routing         32016971191
Stage 7 Plan Occurrence Run Snapshot    32016971262
Stage 7 Scheduler Runtime               32016971149
```

Stage 5D 最终明确通过：

```text
Unit / Provider Contract
HTTP 400 nonretryable takeover
Coverage / Detail re-decision
Raw takeover replay
完整 Collection PostgreSQL / Artifact Integration
Ruff format
Ruff lint
mypy
Architecture
Table Ownership
Secret / Docs
Contract
base → head
Stage 5C → head
```

# 合并后 main 新鲜 CI

PR #57 正常 merge 后：

```text
main:
cfedc01777e1999d2b4140c9eb0f42271445eaa0
```

已确认 `main` 实际指向该 merge commit，而不是仅依据 PR 状态推断。

该 merge commit 实际触发 11 条 `push` workflow；最终查询结果：

```text
success = 11
failure = 0
```

因此归档使用的是合并后 `main` 的新鲜 CI，不复用 PR 旧结果。

# 文档与 CI 收尾

已同步：

- `AGENTS.md`；
- 根 `README.md`；
- `backend/src/aima_ugc/modules/collection/README.md`；
- `backend/src/aima_ugc/modules/content/README.md`；
- `docs/blueprint/03-数据库与文件存储.md`；
- `docs/环境运行与部署.md`；
- `docs/测试与调试说明.md`。

已删除只绑定结束分支或明确标记一次性的旧 Stage 7 Workflow；正式 Scheduler CI 继续保留 `main` / PR 门禁，`Stage 7 TikHub Real Shape` 保留人工 `workflow_dispatch`，避免真实 Provider Probe 被普通 push 自动触发。

Probe 脚本、合法脱敏 Fixture 和 `docs/blueprint/10`—`12` 的真实响应/endpoint 台账证据继续保留。

# TikHub Probe 状态

本 Change 没有新增真实付费 TikHub Probe。当前缺陷均可由既有生产 Operation、脱敏 Fixture、Fake Transport、Raw Artifact 和真实 PostgreSQL 明确证明；因此没有用在线请求替代可重复回归，也没有为了“验证一下”产生无必要 Provider 费用。

若未来真实字段或 endpoint 仍有不确定性，继续按仓库规则：先查官方资料和既有 Fixture/台账；仍不足时，在用户明确授权下用有请求上限的 GitHub Runner 最小 Probe，并只保存合法脱敏证据。

# 部署、兼容与回滚

本 Change 未执行生产部署。

兼容性：

- 无新增依赖或版本升级；
- Canonical V1 / Provider V1 / OpenAPI / 生成 Client 未变化；
- 现有五平台主 Operation、Secret 边界、Job/Scheduler 基线保持；
- 新 Migration 为向前增量且已验证 downgrade。

未来 Release 若包含 `0016`，应按 Release 设计完成受控备份/迁移/启动；需要回滚 `0016` 时先停写并评估兼容，再受控 downgrade，不得改写历史 Revision。

# 最终验收

- [x] Provider Raw takeover 有完整 Raw 时不重发；
- [x] retryable Provider 失败使用同一逻辑 Request + 新 Attempt；
- [x] 不可重试 HTTP 4xx crash/takeover 不重发；
- [x] Run/Scope checkpoint、terminal skip 与 durable stats 完成；
- [x] 评论整页软目标与 Detail 后重决策完成；
- [x] Comment Coverage 可审计持久化完成；
- [x] Account/Content/Comment first-insert 并发收敛；
- [x] 旧 Observation 不回滚较新 Current；
- [x] 稀疏指标历史保持真实观察语义；
- [x] `20260817_0016` Migration 与 round-trip 验证完成；
- [x] 长期文档与 CI 清理完成；
- [x] 两阶段 Review 完成，无未解决严重/重要问题；
- [x] PR #57 最终 head 11/11 正式 CI 全绿；
- [x] PR #57 正常合入 `main`；
- [x] 合并后 `main@cfedc017...` 11/11 push workflow 新鲜全绿；
- [x] Change 更新为 `done`；
- [x] Change 归档到 `changes/archive/2026-08/`；
- [x] Stage 8 未开始；
- [x] 当前仍保持生产部署 No-Go，Release 未被提前实现。

本归档 PR 只处理 Change 生命周期，不新增业务实现，不改变 Contract/Schema，不开始 Stage 8。
