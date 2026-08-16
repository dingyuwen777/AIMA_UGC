---
schema: rvc-change/v1
id: CHG-20260815-stage7-completion
title: 完成 Stage 7 多平台采集与 Scheduler Runtime
level: L3
status: in_progress
owner: dingyuwen777
branch: feature/stage7-completion
created: 2026-08-15
updated: 2026-08-16
depends_on: [CHG-20260815-stage7-plan-occurrence-run-snapshot, CHG-20260815-stage7-provider-budget-ledger, CHG-20260815-stage7-provider-config-routing, CHG-20260815-stage7-decision-capability, CHG-20260815-stage7-douyin-operation, CHG-20260815-stage7-weibo-operation, CHG-20260815-stage7-bilibili-operation, CHG-20260815-stage7-kuaishou-operation]
affected_areas: [collection, provider, scheduler, database, contracts, testing, documentation, ci]
affected_paths: [backend/src/aima_ugc/modules/collection/, backend/src/aima_ugc/adapters/providers/tikhub/, backend/src/aima_ugc/adapters/persistence/postgres/, backend/src/aima_ugc/entrypoints/, migrations/versions/, tests/unit/collection/, tests/contracts/, tests/integration/collection/, tests/fixtures/, scripts/, docs/blueprint/README.md, docs/blueprint/07-技术决策与实施门禁.md, docs/blueprint/08-采集策略与平台能力.md, docs/collection/, backend/src/aima_ugc/modules/collection/README.md, .github/workflows/]
contracts: [ProviderPlatformCapabilityV1, CanonicalContentV1, CanonicalCommentV1]
data_changes: [collection_plans, collection_schedule_occurrences, collection_runs]
---

# 背景与现状

Stage 7 已建立 Decision/Capability、Provider Config/Registry、Keyword Pack、Provider Budget Ledger、Plan/Occurrence/Run Snapshot、五平台 TikHub Operation/真实脱敏 Fixture/Mapper/Capability 基础以及 Scheduler Runtime。Scheduler 已按批准的 `latest_only` 语义创建持久化调度事实；当前仍需完成正式 `collection.run.v1` live Worker Handler、统一长期 Probe、最终文档/CI/Review/合并闭环。

2026-08-16 已取得快手同一真实作品、同一有回复根评论的 Web/App A/B 证据：两套一级和二级评论接口均 HTTP 200 且非空；当次 endpoint-info 显示 App 一级/二级均为 0.001 USD，请求成本低于对应 Web 接口。用户随后明确批准：**快手一级、二级评论正式切换 App；Web 不自动 fallback，只作为已验证备用方案记录。**

同日用户追加要求：检查五个平台是否还存在同业务语义的不同 TikHub API family；有候选时用同关键词或同内容做受限真实 A/B，并记录结果数量、稳定内容 ID 重合和结构兼容。只有真实 A/B 通过的候选才能标为“已验证备用方案”；官方文档存在但未实测的接口只能标为“候选待验证”。

# 目标

在不进入 Stage 8 的前提下完成 Stage 7：

1. 固化并验证 `latest_only + max_catch_up_runs=0` Scheduler Runtime；
2. 完成五平台真实 Raw → Mapper → Canonical → Ingestion 兼容证据；
3. 建立正式 `collection.run.v1` live Worker 执行链和可重复的 Operation / Business Pipeline Probe；
4. 将快手评论主 Operation 切到 App，同时保留 Web 为显式、人工选择的已验证备用，不建立自动 fallback；
5. 对其他平台的同语义 API family 建立受限 A/B 验证与长期证据记录；未完成真实验证时不得把候选写成已验证备用；
6. 通过相关 Unit/Contract/PostgreSQL/质量门禁、PR CI、Review、正常合并与合并后 main 新鲜 CI 证明 Stage 7 闭环。

# 成功标准

- [ ] Blueprint 07/08、Collection 文档和当前 Change 明确记录 `latest_only` 停机恢复语义。
- [ ] Plan 领域与数据库拒绝与 `latest_only + max_catch_up_runs=0` 冲突的配置。
- [ ] Scheduler 对 due slot、并发、事务崩溃与重复 tick 保持 Occurrence/Job/Run/cursor 原子且幂等。
- [ ] 五平台当前主 Operation 有合法脱敏真实 Fixture、Mapper、Capability/Registry 与 Canonical/Ingestion 证据。
- [ ] 快手 `comments/sub_comments` 默认 Capability 和生产 Operation 使用 App：`fetch_video_comment` / `fetch_video_sub_comments`。
- [ ] 快手 Web `fetch_one_video_comment` / `fetch_one_video_sub_comment` 只保留为显式已验证备用；主 builder、Capability、Runtime 均不得静默调用 Web。
- [ ] 快手 App 一级/二级评论主 endpoint 均有 endpoint-level verified Pricing；Web 备用价格可保留用于人工 Probe/切换评估。
- [ ] API family 对照记录至少包含：相同关键词/内容输入、执行时间、主/候选 endpoint、过滤条件、单页结果数、稳定 ID 交集/并集、Jaccard、仅主/仅候选数量、分页/排序差异、结构兼容与价格快照。
- [ ] 当前官方没有同语义候选时明确记录“不存在可比候选”，不得为了凑 A/B 使用热榜、用户搜索或其他不同业务语义接口。
- [ ] 只有真实受限 A/B 成功、稳定 ID/结构可以归一化且价格已核验的候选才标为“已验证备用”；候选接口不自动进入默认 Capability 或 fallback 路径。
- [ ] Operation Probe 使用生产 Operation/Mapper；真实 billable Probe 在 Pricing 未 verified 时发送前 fail closed，并有请求数/费用硬上限。
- [ ] Business Pipeline Probe 复用生产 `CollectionDecisionService`；调试代码不复制正式分页/映射/写库逻辑。
- [ ] 正式 `collection.run.v1` Worker Handler 可消费 Scheduler Job 并复用 Provider Routing、Pricing/Budget、Dispatch、Raw、Mapper、Decision、Ingestion 链。
- [ ] 新增/修改行为遵循 Red → Green → Refactor；真实付费 Probe 是受控例外，不进入普通 CI。
- [ ] Ruff、mypy、Unit、Contract、PostgreSQL Integration、Architecture、Table Ownership、Secret Scan、Docs 与受影响 Stage 回归通过。
- [ ] PR 通过正常 CI 合入 main；合并后的 main 有新鲜成功证据后 Change 才标记 done 并归档。

# 范围

- Stage 7 Scheduler Runtime 与 `latest_only` 领域/数据库约束。
- 五平台 TikHub 主 Operation/Mapper/Capability/Registry 的真实兼容纵切。
- 快手 App 评论主链、Web 已验证备用边界与 endpoint-level Pricing。
- 同平台 API family 候选 builder、受限 A/B Probe、机器可读比较指标和长期文档。
- 正式 `collection.run.v1` Worker Handler 与 Operation / Business Pipeline Probe。
- 目标 Unit/Contract/PostgreSQL/质量测试与 Stage 7 CI。
- Blueprint、Collection 开发说明和平台文档同步。

# 非目标

- 不实现 Stage 8 HTTP CRUD、正式业务页面、Secret 写 API 或认证授权。
- 不实现实时直播评论/WebSocket/ASR。
- 除用户已批准的快手评论 Web→App 切换外，不因“存在另一 API family”自动修改其他平台正式主 Operation。
- 不建立按 HTTP 错误自动切换 App/Web 的 fallback、重试矩阵或双写抓取。
- 不把不同业务语义的接口包装成等价备用；例如综合搜索包含额外对象类型时只能作为候选实验，不能直接替代视频搜索。
- 不为未证明字段、分页、排序或评论关系编造 Mapper。
- 不增加微服务、Redis、Kafka、通用插件框架或第二套 Scheduler 存储。
- 不进入 Stage 8，不顺手升级现有依赖。

# 必须保持不变

- Provider → Raw → Mapper → Canonical → Ingestion；Provider 不写业务表，Mapper 不访问数据库/HTTP。
- PostgreSQL Job Runtime 是 scheduled Run 的正式任务事实；Scheduler 不自建进程内任务队列。
- 一个 `(plan_id, schedule_version, scheduled_for)` 只有一个 Occurrence；Occurrence/Run/Job/Plan 推进同事务。
- Provider Secret 只通过 `provider_config_id → secret_ref` 解析；不进入代码、日志、Raw、Fixture、Job Payload 或数据库明文。
- 真实 HTTP Attempt 受 Provider Pricing/Budget Ledger 保护；Pricing 未核验 fail closed。
- `manual/api/backfill` Run 既有行为保持兼容。
- Canonical V1、表 Owner、外部 ID 字符串、PostgreSQL `timestamptz` 规则不变。
- “已验证备用”只是兼容证据和显式人工切换选项，不等于运行时自动 fallback。

# 方案比较与用户批准决策

## Scheduler 方案 A：latest-only（采用）

停机恢复后若多个逻辑调度点已到期：最新一个入队，更早 slot 写 `skipped / misfire_superseded`，`max_catch_up_runs=0` 不额外补跑历史 Run。用户于 2026-08-15 明确批准。

## 快手评论方案 A：App 主链 + Web 显式备用（采用）

- 正式一级评论：`/api/v1/kuaishou/app/fetch_video_comment`；
- 正式二级评论：`/api/v1/kuaishou/app/fetch_video_sub_comments`；
- Web 一级/二级保留显式 builder 和 A/B 证据；
- 运行时不得因 App 失败自动调用 Web；
- 真正需要切回 Web 时必须形成新的显式决策/变更，而不是隐式容灾。

该方案基于同样本真实非空证据、当前更低 endpoint-level 单价与 App 一级响应更丰富的二级摘要。用户于 2026-08-16 明确批准。

## 快手评论方案 B：Web 主链 + App 备用（不采用）

兼容旧矩阵，但当前成本更高且不符合用户已批准方向。

## 快手评论方案 C：App/Web 自动 fallback（不采用）

可能隐藏 Provider 语义漂移、造成不可预测双倍费用和重复数据；用户明确禁止。

## API family 备用判定

候选按三档记录：

1. `verified_backup`：同业务输入真实 A/B 已成功，稳定 ID/结构可归一化，价格已核验；
2. `candidate_pending_probe`：官方 endpoint/参数已确认，但尚无当前真实 A/B；
3. `not_equivalent`：语义不同或当前不存在同语义 endpoint，不作为备用。

默认 Capability 只登记正式主 Operation；即使达到 `verified_backup` 也不自动注册为 fallback。

# 公共接口与数据兼容

- 不新增 Stage 8 公开 HTTP API；OpenAPI/Generated Client 保持零漂移。
- `ProviderPlatformCapabilityV1` Contract 字段结构不变；快手只修改实例中的 provider operation 值。
- Canonical V1 不改变；候选比较基于 Provider 稳定 ID，不把 API family 写进 Canonical 公共字段。
- 本次快手 Operation/Pricing 切换不需要数据库 Migration；已有 `0014` Scheduler Migration 仍按既定流程验证。

# 安全、费用、性能与运维风险

- 真实 TikHub Probe 使用“爱玛”或已知测试内容，单页/小样本，不做全量翻页。
- API Key 只从 Secret/环境边界读取，不写仓库、日志、Fixture 或报告。
- 每个候选 endpoint 在真实发送前先做 endpoint-level Pricing 核验；无法查价或超过硬上限时 fail closed。
- 当前执行沙箱无法建立到 `api.tikhub.io` 的外部连接；因此新增平台 A/B 在网络恢复前保持 `candidate_pending_probe`，不得伪造已验证结果。
- 已有快手 Web/App A/B 证据来自 2026-08-16 GitHub-hosted Runner 的真实受限请求，可用于本次主链选型与 Web 备用记录。

# 任务

[步骤 1]
→ 修改范围：Scheduler 领域/Repository/entrypoint/Migration/Blueprint
→ 预期结果：`latest_only + max_catch_up_runs=0` 成为领域、数据库与运行时长期事实
→ 验证方式：Unit + PostgreSQL 并发/恢复 + Migration round-trip

[步骤 2]
→ 修改范围：五平台真实 Fixture/Mapper/Capability/Registry
→ 预期结果：当前主 Operation 能归一化到既有 Canonical 并完成 Ingestion 纵切
→ 验证方式：Fixture/Mapper/Canonical/Integration/Secret Scan

[步骤 3]
→ 修改范围：快手 Operation/Capability/Pricing、平台文档与测试
→ 预期结果：App 成为唯一默认评论主链；Web 保留为已验证显式备用；无自动 fallback
→ 验证方式：Red/Green Unit、Pricing fail-closed 回归、Capability 测试、Docs/Secret 门禁

[步骤 4]
→ 修改范围：抖音/微博/B站/快手及必要的小红书 API family 候选 Operation、比较模块与受限 Probe
→ 预期结果：同关键词/同内容可重复比较数量与稳定 ID 重合；证据状态严格区分 verified/pending/not-equivalent
→ 验证方式：候选 builder Unit、比较算法 Unit、Pricing gate/Fake Transport；真实网络可用时执行受限 A/B

[步骤 5]
→ 修改范围：正式 `collection.run.v1` Handler / Operation Probe / Business Pipeline Probe
→ 预期结果：Scheduler Job 可消费，调试与真实运行复用生产 Provider/Mapper/Decision/Ingestion
→ 验证方式：Fake/Fixture Unit + PostgreSQL Integration + 受限 Real Probe

[步骤 6]
→ 修改范围：长期文档、Stage 7 CI、Change/PR
→ 预期结果：机器事实、Blueprint、平台文档、CI 与 Git 状态一致
→ 验证方式：相关 workflows + Review + 正常 PR 合并 + main 新鲜 CI

# 验证

## 计划

- Red：目标行为先写测试并确认因目标能力缺失失败。
- Green：只补当前批准的主链、候选 builder、Pricing 和比较行为，不把候选接入默认 fallback。
- Refactor：绿色后再消除重复并保持 Operation/Mapper 生产入口唯一。
- 目标测试：`tests/unit/collection/`、五平台 TikHub Operation/Mapper/Capability/Pricing、Scheduler PostgreSQL integration。
- 相关回归：Stage 4 Job Runtime、Stage 5 Collection/Dispatch、Stage 6 XHS、Stage 7 Provider Config/Keyword/Budget/Plan。
- 静态检查：Ruff format/check、mypy、Contract generate/compatibility、Architecture、Table Ownership、Secret Scan、Docs。
- Migration：执行上一正式 Revision→head、base→head、downgrade/upgrade、`alembic check`。
- 真实 Probe：仅显式执行、请求数和费用封顶，不进入普通 CI。

## 新鲜证据

- 2026-08-16 快手同作品/同有回复根评论 Web/App A/B：两套一级、二级均 HTTP 200 且非空；App 一级/二级 endpoint-info 均为 0.001 USD；Web 一级 0.002 USD、Web 二级 0.010 USD。
- Commit `f53857b17b16ab32f27b7bda3c91f57a86401234` 已把快手默认 Capability 改为 App comment operations；Operation generic builder 也已指向 App，Web builder 保持显式独立。
- Commit `761f2868bdb6615ffd42bb98f4cab4ae94607aa7` 新增 API family/快手 App Pricing Red 测试；PR CI run `31921882814` 的 Stage 1 在 `Backend and repository checks` 失败，前置环境、启动 smoke 与 Contract 生成已成功。Actions 日志正文当前未能从连接器取得，因此不伪造具体 traceback。
- 当前执行沙箱到 `api.tikhub.io` 的 DNS/直连均不可用；新增外部 A/B 尚不能从本环境取得新鲜真实结果。

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
- `tests/fixtures/providers/tikhub/README.md`
- `backend/src/aima_ugc/modules/collection/README.md`

# 部署与回滚

- 当前任务只合并代码/文档，不自动部署生产服务器。
- 快手切换不涉及数据库 Migration；应用回滚可以恢复旧代码，但不得删除已有 Raw/Canonical/预算事实。
- App 主链故障时不自动切 Web；如需正式回切 Web，先显式核验当前 Pricing/兼容证据并提交新的 Operation 选型变更。
- Scheduler 可通过不启动 Scheduler 进程停止自动调度；Occurrence/Run/Job 历史事实保留。

# 交付

- 基线 main：`2acc4b9e767c3cff06a0522f36242763ea9e44ee`
- 开发分支：`feature/stage7-completion`
- PR：#55，Draft / Open，未合并
- Commit：进行中
- 发布：本任务不部署生产
