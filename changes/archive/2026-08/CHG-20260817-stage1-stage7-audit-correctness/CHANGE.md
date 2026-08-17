---
schema: rvc-change/v1
id: CHG-20260817-stage1-stage7-audit-correctness
title: 修复 Stage 1-7 审计发现的正确性与恢复缺口
level: L3
status: done
owner: dingyuwen777
branch: fix/stage1-stage7-audit-correctness
created: 2026-08-17
updated: 2026-08-17
depends_on: [CHG-20260817-stage1-stage7-correctness]
affected_areas: [content, collection, platform, provider, database, migration, testing, ci, documentation]
affected_paths: [backend/src/aima_ugc/modules/content/, backend/src/aima_ugc/platform/storage/, backend/src/aima_ugc/adapters/storage/, backend/src/aima_ugc/adapters/persistence/postgres/, backend/src/aima_ugc/modules/collection/, backend/src/aima_ugc/entrypoints/, backend/src/aima_ugc/platform/jobs/, migrations/versions/, tests/, scripts/quality/, .github/workflows/, README.md, docs/, backend/src/aima_ugc/modules/system/README.md, backend/src/aima_ugc/modules/collection/README.md, backend/src/aima_ugc/adapters/providers/tikhub/pricing.toml]
contracts: []
data_changes: [accounts, account_external_ids, contents, comments, artifacts]
---

# 完成结论

本 Change 已于 2026-08-17 完成实现、两阶段 Review、PR 合并、合并后 `main` 新鲜 CI 和生命周期归档。它只闭环 Stage 1—7 审计发现的正确性、恢复、CI 与文档一致性问题；**未进入 Stage 8，也未提前实现 Release 能力**。

实现 PR：`#59 修复 Stage 1-7 审计发现的正确性与恢复缺口`

```text
开始 main:
fbe7abc28f66d038565993b0ea28c0cdc5ab31f1

最终实现 branch head:
698964ff915f043d36fb0511c6d6d46e39b03e5d

PR #59 merge commit / 合并后 main:
19080d6a5417c794a4baa4166c6a70bc60012942
```

PR #59 使用正常 Merge Commit 合并，并以 `expected_head_sha=698964ff915f043d36fb0511c6d6d46e39b03e5d` 防止 head 漂移；未强推、未绕过 Branch Protection、未跳过 CI。

# 背景与根因

`main@fbe7abc28f66d038565993b0ea28c0cdc5ab31f1` 的 Stage 1—7 功能面已经建立，Stage 8 尚未开始。2026-08-17 全面一致性与代码质量审计重新对照代码、Migration、Contract、测试、Blueprint、README 与归档 Change 后确认：上一轮 `CHG-20260817-stage1-stage7-correctness` 已修复一批恢复、并发、Coverage 与乱序缺陷，但仍存在以下组合边界和事实漂移：

1. `last_seen_at` 只能表达实体级最新观察时间，不能正确表达 sparse `observed_fields` 下每个 Current 字段各自的 freshness；
2. Raw 文件已经确定性落盘、但 Artifact metadata 仍为 `pending` 的崩溃窗口缺少安全恢复；
3. `account_external_ids` 作为稳定备用身份仍可能被冲突 Observation 静默覆盖；
4. 快手 Capability 声明 `supports_reply_count=true`，但 Mapper 未消费真实 `subCommentCount`；
5. Stage 5 Storage path filter、Secret Scan、Architecture/Table Owner Gate、恢复日志和部分长期文档存在漏检或事实漂移。

本 Change 采用最小增量修复，不推翻现有架构。

# 目标

1. 修复稀疏 `observed_fields` 与乱序 Observation 组合下的 Content/Comment/Account Current 字段 freshness；
2. 修复 Raw 文件已落盘但 Artifact Metadata 仍为 `pending` 时的崩溃恢复；
3. 明确并修复 `account_external_ids` 的稳定身份冲突语义；
4. 闭环 Worker/Reaper 当前阶段边界、快手 `reply_count`、关键日志、CI path/Secret/Architecture/Table Owner 门禁和正式文档状态；
5. 保持 Stage 8、Release、认证授权、Docker/Compose、协调 Backup/Restore 和已撤回 Budget Runtime 在本 Change 范围外。

# 可观察成功标准

- [x] PostgreSQL 回归覆盖 sparse + out-of-order 的 Content、Comment、Account Current 组合边界，并在修复后通过；
- [x] Current 具有字段级 freshness 机器事实；更晚 Observation 未观察的字段允许由较旧 Observation 补充，更晚已观察字段（包括允许的显式 null）不得被旧 Observation 回滚；
- [x] `account_external_ids` 不再被冲突 Observation 静默覆盖；同值幂等，不同值 fail-closed，原稳定值保持不变；
- [x] Raw 文件已写、metadata=`pending`、Attempt=`dispatching` 时 Recovery 可以复用有效 Raw，不再次发送同一 Attempt；损坏/缺失文件仍保守收敛；
- [x] Artifact pending reconciliation 在 `pending → stored` CAS 前完成 gzip、RawEnvelope、lineage 校验，并保持 SHA-256、byte_size、no-overwrite 安全边界；错误 lineage 不提升 Artifact 状态；
- [x] Worker/Reaper 当前边界与代码/文档一致：Stage 1—7 已有正式 runtime/装配和 `run_once()`，生产常驻服务管理继续留给后续 Release；
- [x] 快手 `supports_reply_count=true` 有真实脱敏响应证据，生产 Mapper 使用 `subCommentCount`，不把布尔 `displaySubCommentCount` 当计数；
- [x] Stage 5 Raw/Dispatch CI 在 Platform Storage / Storage Adapter 变化时能触发关键回归；
- [x] Secret Scan 覆盖 Provider Fixture、Change、docs 等高风险路径，并允许合法 `<redacted-…>` 脱敏占位；
- [x] Architecture/Table Owner Gate 自动检查当前 AGENTS 可低误报机械验证的硬边界；
- [x] README、Blueprint、模块 README、Kuaishou、部署/测试说明与最终机器事实一致；
- [x] 未新增/升级依赖，未改变 Canonical V1、Provider V1、五平台主 Operation、快手 App 评论主链、Scheduler `latest_only + max_catch_up_runs=0`、Budget 回撤和 Stage 8/Release 非目标；
- [x] PR 完成需求符合性与代码质量两阶段 Review；最终 PR head 和合并后 `main` 均取得新鲜成功 CI 证据。

# 范围

- Content Current/History 字段级 freshness 与账号稳定 ID；
- Artifact `pending` → 已存在文件的恢复对账；
- Provider Attempt Recovery 与 Raw replay 接线；
- 直接相关 PostgreSQL Migration、Repository、测试和 CI；
- Worker/Reaper 当前阶段边界核对；
- Kuaishou reply-count Capability/Mapper；
- Secret/Architecture/Table Owner/日志/文档一致性缺口。

# 非目标

- 不开始 Stage 8 HTTP CRUD、正式业务页面、认证授权或 API 幂等 actor；
- 不实现 Production Docker/Compose、离线 Release、SBOM/签名、协调 Backup/Restore、维护 epoch 或 advisory write barrier；
- 不恢复请求次数/金额 Budget、Budget Account、Reservation Ledger 或 dormant Budget 接口；
- 不改变 TikHub 五平台已批准主 Operation，不建立自动 App/Web/Provider fallback；
- 不新增 Redis/Celery/Kafka/工作流引擎或新基础设施；
- 不升级 Python/Node/PostgreSQL/依赖版本。

# 必须保持不变

- 模块化单体与 API/Worker/Scheduler/Migration 分进程基线；
- Provider → immutable Raw → Mapper → Canonical → Ingestion → Owner Repository → PostgreSQL；
- Canonical V1 / Provider V1 公共 Contract 与生成 OpenAPI/Client 兼容边界；
- 外部 HTTP 不进入数据库事务；同一 Attempt 不隐藏网络重试；
- 已校验 Raw 存在时禁止再次调用 Provider，真实重发必须新建 Attempt；
- Scheduler 固定 `latest_only + max_catch_up_runs=0`；
- 快手正式 comments/sub-comments 保持 App 主链，Web 仅显式 `verified_backup`，无自动 fallback；
- Secret 只通过 `secret_ref`，TikHub Bearer 只发往批准 Origin；
- Budget Runtime 保持删除状态；
- Stage 8/Release 边界不提前实现。

# 方案比较与最终决策

## A. Current 字段 freshness

### A1：继续使用整行 `last_seen_at` + 特殊判断

无法区分“更晚 Observation 未观察该字段”和“更晚已经观察该字段”，不能正确处理稀疏事实，不采用。

### A2：每个 Current 字段增加独立 `*_observed_at` 列

语义明确，但会为 Content/Comment/Account 的大量稀疏字段增加伴生列和 Migration 噪音，不采用。

### A3：Current 行增加内部字段级 freshness JSONB

最终采用。`accounts/contents/comments` 增加 Content Owner 内部维护的 `field_observed_at` JSONB，key 为已批准稳定字段路径，value 为 UTC ISO-8601 时间；在现有行锁边界内按字段比较 Observation 时间。

它只表达 Current provenance，不替代稳定业务列，也不成为第二套指标历史。

## B. 备用稳定账号 ID

最终采用 fail-closed：同一 `account_id + id_type` 已存在且值不同则抛出稳定身份冲突，不覆盖；相同值幂等。若未来证明某类 alternate ID 实际可变，必须新建 Change 重新设计身份语义。

## C. Raw pending crash recovery

最终采用最小 reconcile：保留现有三阶段 Artifact 生命周期，不把文件 I/O 放进 DB 事务。Recovery 对确定性 `pending` Raw 先读取实体并完成 gzip / RawEnvelope / **当前 Request/Attempt lineage** 校验，再重算 hash/size 并 CAS `pending → stored`；之后才进入 terminal/link 流程。损坏、缺失或错误 lineage 都不提升状态，并保守收敛 Provider Attempt。

普通 `stored/linked` replay 继续先校验 SHA-256/byte_size，再解析 gzip/Contract，保持既有错误语义。

# 实现结果

## 1. Content / Comment / Account Current

- Migration `20260817_0017` 为 `accounts/contents/comments` 增加 `field_observed_at` JSONB；
- 历史非空 Current 字段使用当前 `last_seen_at` 作为保守回填基线；当前为 null 且无法证明历史观察过的字段不伪造 freshness；
- Repository 在锁内逐字段决定是否允许更新；
- 更晚显式 null 建立 freshness 后，较旧非空值不能回滚该字段；
- `first_seen_at` 仍允许更早事实向前扩展，`last_seen_at` 单调保持实体级最新观察时间。

## 2. `account_external_ids`

- 已持久化稳定 ID 后，相同值保持幂等；
- 不同值关闭失败，不覆盖原值；
- PostgreSQL 回归在冲突失败后重新读取，确认原稳定值仍存在。

## 3. Provider Raw / Recovery

- `RawArtifactService.reconcile_pending(...)` 只处理 `pending` Raw；
- 在状态提升前验证实体、Contract 和当前 Request/Attempt lineage；
- 错误 lineage 回归明确要求 Artifact 仍保持 `pending`，hash/size/stored_at 不被伪造；
- Recovery 拒绝 Raw 时写安全 warning `provider_raw_recovery_rejected`，只包含 Attempt ID、Artifact ID 和安全失败摘要，不记录 Raw、请求参数或 Secret；
- 正常 replay 兼容既有 SHA/size → gzip/Contract 校验顺序。

## 4. Kuaishou

2026-08-16 的合法脱敏真实证据确认：

```text
displaySubCommentCount = boolean 显示开关
subCommentCount = 实际回复数量
```

Mapper 只把 `subCommentCount` 映射到 `CanonicalMetricsV1.reply_count`；Capability 与 Mapper 再次一致。无需为本 Change 额外产生 TikHub 付费请求。

## 5. CI / Secret / Architecture / Table Owner

- Stage 5A / 5D path filter 覆盖整个 Platform Storage 与 Storage Adapter 关键变化；
- Secret Scan 增加 Provider Fixture、Change、docs 等路径；
- Architecture Gate 机械检查领域模块反向依赖 Adapter/Entrypoint、Provider 直连持久化/业务表、Mapper 引入 HTTP/DB、Entrypoint 直接 SQL 等当前 AGENTS 已明确边界；
- Table Owner Gate 不再只验证“owner 是合法字符串”，同时按当前稳定表分组核对期望 Owner；
- 专项 workflow 使用长期名称 `Stage 1-7 Audit Correctness / Audit PostgreSQL Regression`，不把永久回归门禁继续命名为 Red 阶段。

## 6. 文档

已按最终机器事实同步：

- `README.md`；
- `docs/blueprint/03-数据库与文件存储.md`；
- `docs/blueprint/10-TikHub真实响应结构附录.md`；
- `docs/collection/kuaishou.md`；
- `docs/环境运行与部署.md`；
- `backend/src/aima_ugc/modules/content/README.md`；
- `backend/src/aima_ugc/modules/system/README.md`；
- 相关 Collection/质量门禁说明。

部署文档明确区分：Stage 1—7 Job Runtime/Scheduler/五平台采集已存在；当前公网生产 No-Go 来自 Stage 8 和 Release 尚未闭环的能力，不能再把 Job Runtime/正式 Scheduler 写成“尚未实现”。

# 兼容、Migration、部署与回滚

- 公共 HTTP/Pydantic Contract：无变化；Canonical V1 / Provider V1 无破坏性变化；
- 数据库：新增向前 Revision `20260817_0017`，历史 Revision 未改写；
- downgrade `0017` 只删除内部 `field_observed_at` provenance 列，不删除已有业务 Current 值；
- Raw pending reconciliation 无新 Schema；
- 未新增或升级依赖；
- 本 Change 不建立生产部署流程；当前生产仍 No-Go；
- 正式生产回滚、协调 Backup/Restore 和生产镜像仍属于后续 Release。

# TDD 与 Review 证据

## 需求符合性 Review

逐项核对目标、范围、非目标、公共 Contract、五平台 Operation、Scheduler 策略、Budget 回撤、Stage 8/Release 边界和正式文档。未发现范围漂移。

## 代码质量 Review

最终 Review 额外发现并闭环两个重要问题：

1. **显式 null 测试覆盖缺口**：实现已有字段级 freshness，但成功标准明确要求“更晚显式 null 不得被较旧非空值回滚”，原新增测试未直接证明。新增 PostgreSQL 回归后，最终候选 CI 通过；
2. **pending Raw lineage-before-CAS 顺序缺陷**：最初实现会在验证当前 Request/Attempt lineage 前先把合法 gzip/RawEnvelope 从 `pending` 提升为 `stored`。新增错误-lineage 回归后取得正确 Red：专项 PostgreSQL 为 `1 failed / 6 passed`，失败值明确为 `stored != pending`；随后把 lineage 校验移动到 CAS 前并保留后续防御性校验，最终回归转绿。

此前快手 reply-count 也通过目标 Red/Green 证明：旧 Mapper 对真实 `subCommentCount` 返回 `reply_count=None`，修复后映射为真实计数；Raw Recovery warning 通过“降级 unknown 但无 warning”的失败用例建立回归。

严重/重要 Review 问题均在合并前处理，没有以“后续优化”延期当前 blocker。

# 最终验证

## PR 最终 head

```text
698964ff915f043d36fb0511c6d6d46e39b03e5d
```

该 head 的 Pull Request workflow 最终：

```text
12 / 12 success
```

包括：

- CI；
- Stage 1-7 Audit Correctness；
- Stage 4 Job Runtime；
- Stage 5A Provider Raw；
- Stage 5B Collection Execution；
- Stage 5C Provider Persistence；
- Stage 5D Provider Dispatch；
- Stage 6 XHS Vertical Slice；
- Stage 7 Scheduler Runtime；
- Stage 7 Keyword Packs；
- Stage 7 Provider Config Routing；
- Stage 7 Plan Occurrence Run Snapshot。

PR 合并前无 Review submission blocker、无未解决 inline review thread。

## 合并后 `main`

PR #59 合并后：

```text
main = 19080d6a5417c794a4baa4166c6a70bc60012942
```

该 merge commit 实际触发 11 条 `push` workflow。最终 GitHub Actions 查询结果：

```text
completed = 11
success = 11
failure = 0
queued = 0
in_progress = 0
cancelled = 0
```

因此本 Change 的完成结论使用的是**合并后 `main` 的新鲜证据**，不是复用 PR 旧绿灯。

# TikHub Probe 状态

本 Change 没有新增付费 TikHub Real Probe。快手 `subCommentCount`、App/Web family 和 Capability 已有 2026-08-16 合法脱敏真实 Fixture/台账证据，当前修复可以由生产 Mapper + Fixture + PostgreSQL/CI 回归证明。未用付费 HTTP 替代可重复测试，也未写入或输出 TikHub Secret。

# Git

- 基线 main：`fbe7abc28f66d038565993b0ea28c0cdc5ab31f1`；
- 实现分支：`fix/stage1-stage7-audit-correctness`；
- 最终实现 head：`698964ff915f043d36fb0511c6d6d46e39b03e5d`；
- 实现 PR：`#59 修复 Stage 1-7 审计发现的正确性与恢复缺口`；
- merge commit / 合并后 main：`19080d6a5417c794a4baa4166c6a70bc60012942`；
- PR 最终 head CI：12/12 success；
- 合并后 main push CI：11/11 success；
- 生命周期归档分支：`docs/archive-stage1-stage7-audit-correctness`；
- Change：`done`，归档到 `changes/archive/2026-08/CHG-20260817-stage1-stage7-audit-correctness/CHANGE.md`。

# 最终验收

- [x] sparse + out-of-order Current 字段 freshness 闭环；
- [x] 显式 null freshness 回归闭环；
- [x] alternate stable ID 冲突 fail-closed 且原值保持；
- [x] pending Raw 有效文件恢复闭环；
- [x] 错误 lineage 在 `pending → stored` 前被拒绝；
- [x] Raw replay 兼容既有完整性错误语义；
- [x] 快手 reply_count Capability 与 Mapper 一致；
- [x] Recovery 关键降级有安全结构化日志；
- [x] Stage 5 Storage path、Secret、Architecture、Table Owner 门禁补强；
- [x] 正式文档与最终机器事实同步；
- [x] 未恢复 Budget Runtime；
- [x] 未改变五平台主 Operation、快手 App 评论主链或 Scheduler latest_only；
- [x] 需求符合性 Review 完成；
- [x] 代码质量、安全、兼容性 Review 完成；
- [x] PR #59 最终 head 12/12 workflow success；
- [x] PR #59 正常合入 `main`；
- [x] 合并后 `main` 11/11 push workflow 新鲜全绿；
- [x] Change 更新为 `done`；
- [x] Change 按仓库规则归档到 `changes/archive/2026-08/`；
- [x] Stage 8 未开始。

本归档只处理 Change 生命周期记录，不新增业务实现，也不开始 Stage 8。
