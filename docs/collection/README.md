# 采集能力说明

本文描述当前任务分支已经落地的采集主链、Stage 7 运行事实以及仍受门禁约束的能力。长期设计以 `docs/blueprint/` 为准，机器事实以代码、Migration、Contract、Fixture 与测试为准。

五个平台 TikHub 真实响应的人类查询入口见 [`../blueprint/10-TikHub真实响应结构附录.md`](../blueprint/10-TikHub真实响应结构附录.md)。同平台 App/Web/V1/V2/V3 的验证与备用规则见 [`../blueprint/11-TikHub多接口验证与备用策略.md`](../blueprint/11-TikHub多接口验证与备用策略.md)。

## 1. 当前稳定主链

采集主链保持：

```text
Plan / Run / Scope
→ Provider Request / Attempt
→ Raw Artifact
→ Provider + Platform Mapper
→ Canonical
→ Ingestion
→ Owner Repository
→ PostgreSQL
```

边界要求：

- Provider 负责外部 API 调用，不直接写业务表；
- Raw Artifact 先于 Mapper 保存；
- Mapper 只做纯映射，不访问数据库、不发 HTTP；
- Canonical 表由对应业务 Owner 写入；
- Provider 私有 cursor / page / search_id 等分页状态只留在 Provider Adapter / Request / Attempt 的内部边界；
- Secret 不进入代码、日志、Raw、Fixture、Job Payload、Plan 配置或数据库明文。

## 2. Run / Scope 与 Provider 执行

`CollectionExecutionService + PostgresCollectionRepository` 创建 Run / Scope 父事实，一个 Run 只绑定一个正式 Job。

当前 Run 触发方式：

- `manual`
- `api`
- `backfill`
- `scheduled`

其中：

- `manual/api/backfill` 保持既有兼容行为，并可选记录 `manual_plan_id`；
- `scheduled` 必须绑定唯一 `occurrence_id`，不得同时写 `manual_plan_id`；
- Run 的 `config_snapshot` 保存该次执行不可变配置快照，Plan / Schedule Version 的关系身份以数据库 FK 为准；
- Scheduler 创建 scheduled Run 时会冻结实际可执行关键词 Scope，避免 Job 入队后重新读取已经变化的词包内容。

Provider Request / Attempt、Dispatch、Recovery 继续复用现有 Stage 5D / Stage 7 生产实现；Billing/成本字段用于执行审计，当前没有 Budget Account/Reservation Ledger。

## 3. Stage 7 Plan 与 Scheduler 事实

当前数据库已经存在：

- `collection_plans`
- `collection_plan_platforms`
- `collection_plan_keyword_packs`
- `collection_schedule_occurrences`
- `collection_runs.manual_plan_id`
- `collection_runs.occurrence_id`

### 3.1 Plan 与已批准恢复策略

首版 Plan 固定：

```text
timezone = Asia/Shanghai
misfire_policy = latest_only
max_catch_up_runs = 0
```

领域层和数据库都拒绝与该策略冲突的 Plan。完整语义见 [Scheduler 运行与恢复策略](../blueprint/09-Scheduler运行与恢复策略.md)。

停机恢复若累计多个到期 slot：

- 最新一个创建 `enqueued` Occurrence；
- 更早的 slot 创建 `skipped` Occurrence；
- `skip_reason = misfire_superseded`；
- 不额外执行历史 Run；
- `last_scheduled_at` 推进到最新已处理 slot；
- `next_run_at` 推进到第一个未来 slot。

### 3.2 Plan → Platform

Plan 的平台配置通过 `collection_plan_platforms` 保存：

- 一个 Plan 的同一 `platform` 只能出现一次；
- Provider 选择通过稳定 `provider_config_id` 引用 `provider_configs`；
- `config` 只保存平台业务配置 JSON object；
- API Key、Token、Cookie、Password 等 Secret 形态字段由领域入口拒绝；
- Provider 私有分页状态不属于 Plan 配置。

### 3.3 Plan → Keyword Pack / Scope Snapshot

Plan 与关键词包通过 `collection_plan_keyword_packs` 建立真实关联，不把词包 ID 列表塞入 Plan JSON。

Scheduler 在创建实际 Run 时读取当时有效的词包版本并展开为明确的平台关键词 Scope：

- `platform=all` 只展开到该 Plan 已显式配置的平台；
- 停用关键词不进入 Scope；
- 同平台同关键词去重；
- 词包版本写入审计快照；
- Worker 后续消费持久化 Scope，而不是重新解释当前可变词包。

### 3.4 Schedule Occurrence

Occurrence 唯一身份为：

```text
(plan_id, schedule_version, scheduled_for)
```

状态只允许：

- `enqueued`：必须有唯一 `job_id`，不得有 `skip_reason`；
- `skipped`：不得有 Job，必须有非空 `skip_reason`。

数据库 deferred constraint 在事务提交前验证：

- `enqueued` Occurrence 恰好有一个反向 `scheduled` Run；
- Occurrence 与 Run 使用同一个 Job；
- `skipped` Occurrence 没有 Run。

### 3.5 Scheduler Runtime

Scheduler 已实现首版持久化 Runtime：

```text
预扫可调度 Plan ID
→ 每个 Plan 独立短事务
→ SELECT ... FOR UPDATE 重读当前 Plan
→ 解析五字段数值 Cron
→ 计算 latest-only 决策
→ 冻结关键词 Scope
→ 写 skipped Occurrence
→ 写 Job
→ 写 enqueued Occurrence
→ 写 scheduled Run / Scope
→ 推进 last_scheduled_at / next_run_at
→ commit
```

当前五字段 Cron 支持数字、`*`、列表、范围和步长，不支持秒字段、年份字段、月份/星期英文名称或 Quartz 扩展。

多 Scheduler 可以同时预扫同一 Plan，但最终决定在 PostgreSQL 行锁内完成；第二个 Scheduler 必须重读已推进后的 cursor，因此不能重复创建同一 Occurrence/Run/Job。

## 4. 五平台 TikHub 真实兼容事实

2026-08-15 至 2026-08-16 已通过 GitHub-hosted Runner 对 `https://api.tikhub.io` 做受限 Real Probe，关键词使用“爱玛”，不做全量翻页。

当前仓库已经保存五个平台真实脱敏 Fixture：

```text
tests/fixtures/providers/tikhub/xhs/
tests/fixtures/providers/tikhub/douyin/
tests/fixtures/providers/tikhub/weibo/
tests/fixtures/providers/tikhub/bilibili/
tests/fixtures/providers/tikhub/kuaishou/
```

真实结构覆盖：

| 平台 | Search | Detail | 一级评论 | 二级评论/回复 |
| --- | --- | --- | --- | --- |
| 小红书 | 非空 | 图文/视频非空 | 非空 | 非空 |
| 抖音 | 非空 | 非空 | 非空 | 非空 |
| 微博 | 非空 | 非空 | 非空 | 非空 |
| B站 | 非空 | 非空 | 非空 | 非空 |
| 快手 | 非空 | 非空 | **Web 与 App 同样本均非空** | **Web 与 App 同样本均非空** |

五个平台真实 Search/Detail/Comments/Replies 已由生产 Extractor / Mapper 构造合法 Canonical；真实 Fixture 还通过 PostgreSQL 18 Ingestion 纵切验证，因此当前 Canonical V1 的核心统一结构已经有真实 Provider 证据。

### 4.1 当前默认 TikHub Capability

默认 Registry 已覆盖：

```text
xhs
douyin
weibo
bilibili
kuaishou
```

Capability 只公开当前真实响应和 Operation 已证明的能力，不因为 TikHub 文档存在某个字段/参数就自动声明支持。

快手正式评论 Capability 已切换为 App：

```text
comments = fetch_video_comment
comments.supports_reply_count = true
comments.supports_sub_comments = true
sub_comments = fetch_video_sub_comments
```

Web `fetch_one_video_comment` / `fetch_one_video_sub_comment` 已由真实同样本 A/B 证明可用，但只保留为显式 `verified_backup`，不进入默认 Capability，也不做自动 fallback。

### 4.2 快手 Web/App A/B 与搜索可比性

快手早先一次 Web `subComments=[]` 已被重新调查：旧 Probe 直接选择第一条根评论，没有确认其存在回复。

2026-08-16 对同一个有回复作品、同一个具有 `displaySubCommentCount/subCommentCount` 正向证据的根评论分别调用 Web/App：

- Web 一级评论 HTTP 200 且非空；
- App 一级评论 HTTP 200 且非空；
- Web 二级评论 HTTP 200 且 `data.subComments[]` 非空；
- App 二级评论 HTTP 200 且 `data.subComments[]` 非空；
- App 一级响应能直接带部分 `subCommentsMap.<root>.subComments[]`；
- 当次 endpoint-info：Web 一级 0.002 USD、Web 二级 0.010 USD；App 一级 0.001 USD、App 二级 0.001 USD。

用户已批准 App 为正式评论主链；App 一级/二级价格已经进入版本化 Pricing。Web 只作为已验证备用记录。

快手 Web family 当前没有与关键词视频搜索同语义的 Web Search，因此不能回答“同一关键词 App/Web 搜索结果数量和内容是否一致”。该项状态为：

```text
not_equivalent / no_same_semantic_web_search
```

App `search_comprehensive` 是不同语义候选，只能在未来 A/B 中比较其视频子集，不能当作 Web 搜索替身。

### 4.3 其他平台 API family 候选

当前代码只增加显式 A/B candidate builder，不修改其他平台默认 Capability：

- 抖音：Video Search V2 主链 vs Video Search V1 候选；
- 微博：Web Search 主链 vs App Search All 候选；App 一级评论主链 vs Web V2 Comments 候选；
- B站：App Search/Comments/Reply 主链 vs 对应 Web 候选；
- 小红书：保持 App V2 主链，其他 family 需要当前 endpoint 级重新确认后再实验。

除快手 Web 评论链外，这些候选当前均为 `candidate_pending_probe`。当前执行沙箱不能连接 TikHub，且现有 GitHub Runner RSA 公钥 artifact 无法通过当前工具安全取回，因此没有新鲜真实 A/B 的候选不得写成 `verified_backup`。

统一比较记录包括：主/候选结果数、去重稳定 ID 数、交集、仅主、仅候选、并集、Jaccard、排序/分页差异、结构兼容和 endpoint-level 价格。两边都返回空集合时保持 inconclusive。

## 5. 其他 Stage 7 已落地能力

当前还已经建立：

- Provider Config Registry / `secret_ref` 路由；
- Keyword / Keyword Pack 与数据库级并发串行化；
- 五平台 TikHub Operation / Mapper / Capability / Registry 的真实响应基础；
- endpoint-level Pricing fail-closed；
- XHS 已存 Raw Replay Job Handler，用于把既有 Raw 重新走正式 Mapper / Ingestion，不重新发 Provider HTTP；
- TikHub HTTP Transport 的 Secret 注入、一次发送和错误状态边界；
- API family 稳定 ID 集合比较模块与显式候选 Operation builder。

## 6. 当前仍未闭环的 Stage 7 能力

Stage 7 仍为进行中，当前不能因为 Scheduler、五平台 Mapper 或 Real Probe 已完成就宣称自动采集完整闭环。主要剩余：

1. **正式 `collection.run.v1` Worker Handler**：Scheduler 已能创建 scheduled Job / Occurrence / Run / Scope，但生产 Worker 仍需要完整复用 Provider Routing、Provider Billing/Pricing、Dispatch、Raw、Mapper、Decision、Ingestion 链，不能注册空 Handler 或第二套采集实现；
2. **统一 Operation / Business Pipeline Probe 的长期生产入口**：本轮一次性 Real Probe 已取得外部结构证据，但最终调试入口必须复用正式 Registry / Operation / Mapper / Decision Service，并保持 Provider Billing/Pricing 事实完整；
3. **其他平台 API family 真实 A/B**：抖音/微博/B站候选 builder 已建立，但在安全凭据交接和真实 Runner Probe 成功前保持 `candidate_pending_probe`；这不阻断当前正式主 Operation 的既有真实兼容证据，也不能被误报为已验证备用；
4. **最终 Stage 7 集成证据**：相关质量门禁、PR CI、Review、正常 PR 合并以及合并后 main 新鲜 CI 尚未全部完成。

## 7. 测试与调试

- 调试复用生产 Service / Repository / Provider Operation，不实现第二套路径；
- Real Probe 默认不进普通 CI，必须显式授权、设置请求数/分页上限并在运行前核对预计费用，Secret 不落盘；
- 普通回归使用已经合法脱敏的真实 Fixture，不重复产生 TikHub 费用；
- API family A/B 只使用显式候选 builder，不能注册隐式 fallback；
- Scheduler 专项验证 latest-only、并发去重、重复 tick 幂等、Plan 行锁重读、Scope Snapshot、Migration drift 与 round-trip；
- 数据库变化验证 Alembic 上一正式 Revision → head、base → head、downgrade / upgrade 与 `alembic check`；
- Contract / Ruff / mypy / Architecture / Table Ownership / Secret / Docs 门禁必须保持绿色；
- 不能用 Fixture 测试冒充本轮真实 TikHub 成功调用，也不能用旧版本 Provider 响应冒充当前 Operation 兼容性证据。
