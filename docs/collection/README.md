# AIMA_UGC 采集逻辑总览

本文是开发、调试和维护采集能力时的人类可读入口。Stage 7 的正式业务决策以 [`../blueprint/08-采集策略与平台能力.md`](../blueprint/08-采集策略与平台能力.md) 和 [`../blueprint/07-技术决策与实施门禁.md`](../blueprint/07-技术决策与实施门禁.md) 为准；代码、Pydantic Contract、Migration、Fixture 和测试仍是机器事实。

## 1. 开发时怎么读

处理某个平台的采集代码前：

```text
AGENTS.md
→ .agents/skills/reliable-vibe-coding/SKILL.md
→ docs/blueprint/README.md
→ docs/blueprint/07-技术决策与实施门禁.md
→ docs/blueprint/08-采集策略与平台能力.md
→ 本文
→ 目标平台文档
→ 实际 Operation / Mapper / Contract / Fixture / Test
```

平台文档：

- [小红书](xiaohongshu.md)
- [抖音](douyin.md)
- [微博](weibo.md)
- [B站](bilibili.md)
- [快手](kuaishou.md)

## 2. 当前实现事实

截至本文编制时：

- 小红书 TikHub App V2 Operation/Mapper 已在 Stage 6 实现；
- Stage 7 已建立跨平台 `CollectionDecisionService` / Capability，以及 Provider Config/Platform Route 机器基础：`ProviderConfigV1`、`ProviderPlatformRouteV1`、System `provider_configs`、PostgreSQL Repository、Provider Registry 和 `20260815_0010`；
- 同一种 Provider 可以有多个独立配置实例；配置实例不绑定平台，后续平台/Plan 选择具体 `provider_config_id`；当前默认 Registry 只接线已有机器能力的 `tikhub + xhs`；
- Provider Config 数据库只保存非敏感配置和 `secret_ref`，不保存 API Key/Token 明文；TikHub 当前允许的 Base URL 为 `https://api.tikhub.io`，可配置 URL 仍受 Provider Adapter allowlist 保护；
- 当前 Decision Service 已把零评论短路、评论数不变跳过、评论数增减/未知、详情触发和二级回复目标等规则统一到一份生产逻辑；Provider Capability 只暴露当前代码实际实现的能力；
- 当前 XHS 评论 Operation 固定 `latest_v2`，所以 Capability 只暴露规范化 `latest`；仓库尚无合法脱敏非空评论 Fixture/Real Probe 证明“遇到已知 comment_id 即可安全停止”，因此当前 XHS 不声明稳定增量停止能力；
- 抖音、微博、B站和快手 Operation 已有机器实现与自动测试，但均尚无对应 Mapper、合法脱敏非空真实 Fixture、Real Probe、Capability/默认 Registry。平台文档不得把“Operation 已实现”写成“平台已兼容”；
- 五个平台默认 Provider 类型都是 TikHub，但架构允许以后逐平台显式选择不同 Provider Config / Provider；
- Real Provider Probe 的安全、Raw、Canonical、XLSX 边界已经固化，但统一真实 Operation Probe 和完整 Business Pipeline Probe 仍需在后续 Stage 7 实现；当前已有的是不访问 Provider/数据库的 Decision Probe；
- Stage 7 Scheduler 仍等待 misfire/catch-up 决策，不能因为 Provider 开始开发就提前启用自动调度。

## 3. Provider 配置与平台选择

Provider 管理与采集 Plan 是两个不同层次：

```text
Provider Config
├─ TikHub 主账号：provider_config_id=A
├─ TikHub 备用账号：provider_config_id=B
└─ Provider B：provider_config_id=C

Plan / Platform Policy
├─ 小红书 → A
├─ 抖音   → C
└─ B站    → B
```

同一个 Provider Config 可以被多个平台复用；同一种 Provider 类型也可以存在多个账号/实例。稳定引用只使用 `provider_config_id`，不依赖显示名称。

Provider Config 当前机器字段包括 Provider 类型、显示名称、HTTPS Base URL、`secret_ref` 和启用状态。原始 Secret 不进入数据库；Stage 8 以后如果提供网页凭据编辑，必须通过后端安全 SecretStore/SecretService 写入，并且读取接口不能回显原始 Key。

平台选择 Provider Config 后，再由正式 Registry 解析 `Provider + Platform Capability`。禁用 Config、未知 Provider、Base URL 不在 allowlist、或当前 Provider 尚无该平台 Capability 时关闭失败。

## 4. 通用抓取逻辑

所有平台都遵守：

```text
平台/Plan 选择 provider_config_id
→ Registry / Capability
→ 关键词搜索
→ 保存 Search Raw
→ Mapper 得到当前 Observation
→ 按 platform + external_content_id 去重
→ 与数据库/Probe 上一次状态比较
→ 正式 CollectionDecisionService 决定详情/评论/回复动作
→ 每个真实 HTTP Attempt 先取得预算
→ 保存每次 Raw
→ Mapper → Canonical
→ Ingestion → PostgreSQL
```

搜索结果重复并不丢失本次发现来源，只是尽量避免重复付费抓详情/评论。Decision Service 只接收规范化事实和 Capability，不解析 TikHub Raw、不访问数据库、不拼 Provider URL。

## 5. 评论决策最简表

| 内容状态 | 当前评论数 | 与上次相比 | 默认评论动作 |
| --- | ---: | --- | --- |
| 新内容 | 0 | — | 跳过，`provider_reported_zero` |
| 新内容 | >0 | — | 按自适应策略采集 |
| 新内容 | 未知 | — | 先看 Capability/详情；必要时受预算首屏探测 |
| 已有内容 | 0 | 未变化 | 跳过 |
| 已有内容 | >0 | 未变化 | **跳过，不重新抓评论** |
| 已有内容 | >0 | 增加 | Capability 已证明稳定增量时增量抓取，否则受控刷新 |
| 已有内容 | >0 | 减少 | 记录下降 + 受控刷新；不猜具体删除 |
| 任意 | 任意 | 任意 | 人工 Deep Collection 可加深，但仍受预算 |

点赞、分享、收藏、播放等变化但 `comment_count` 不变时，默认只更新对应指标，不因此重抓评论。

## 6. 默认省钱参数

```text
comment_trigger = new_or_comment_changed
comment_mode = adaptive
full_fetch_threshold = 50
sample_target = 50
comment_sort = latest_if_supported
reply_target_per_root = 5
comment_refresh_when_count_unchanged = false
auto_deep_collection = false
```

解释：

- 评论数 1–50：尽量抓完整；
- 评论数 >50：目标抓 50 条，不追求全量；
- 目标是软目标：一页已经付费返回的数据全部保留；
- 一级评论明确没有回复时不请求二级评论；
- 平台 Capability 不支持二级评论时不生成二级回复目标；
- 重复帖子评论数不变时不重抓；
- 真正硬限制是请求/费用 Budget，不是“刚好 50 行”。

## 7. 前端配置和内部参数

前端最终分两类配置：

1. Provider 管理：维护多个 Provider Config 的显示名称、Provider 类型、允许 Base URL 和凭据写入；原始凭据只写入服务端 Secret 边界，不回显；
2. 采集 Plan：每个平台选择具体 `provider_config_id`，再配置关键词、排序、发布时间范围、内容类型、评论阈值/目标/排序、二级回复目标、Deep Collection、预算等业务语义。

Operation 自己维护第三方技术状态：

```text
cursor / pcursor
page
search_id / search_session_id
backtrace
pageArea
max_id / next_offset
Secret / Authorization
```

前端只能看到 Capability 明确支持且当前 Operation 实际实现的选项；“第三方 API 支持”不等于“AIMA 当前代码已支持”。不支持发布时间筛选的平台不能伪装支持。

## 8. 时间窗口

- 搜索时间范围小于调度周期：只 Warning，仍允许保存和运行；
- Provider 不支持或参数非法：Error；
- Provider 最小时间窗大于调度周期：允许重叠抓取，依靠去重和 Decision Pipeline 减少下游费用。

## 9. Deep Collection

内容已经存在时，内容页按钮只需要提交内部 `content_id`，后端解析平台、外部 ID 和当前 Provider Config；用户不需要手抄 note_id/aweme_id/photo_id。

系统尚未发现的内容可以走高级“外部内容 ID / 分享链接直接采集”。两种入口最终都必须复用正式 Provider Route、Operation、Budget、Raw、Mapper、Canonical 和 Ingestion。

## 10. 费用怎么理解

页面区分：

1. **预计费用**：有历史时按历史 Run 估算，无历史时保守估算；
2. **理论请求上限**：由 Plan 的请求/分页上限计算；
3. **数据库硬预算**：每个真实 Attempt 发送前原子预留，才是实际费用控制。

预算账户后续绑定具体 `provider_config_id`。因此多个平台共享一个 TikHub Config 时共享该实例的 global 预算；选择不同 TikHub 账号或 Provider 时按配置实例隔离。

消费优先级：

```text
关键词发现
→ 必要详情
→ 一级评论
→ 二级回复
→ 可选 enrichment / Deep Collection
```

## 11. 评论覆盖必须说实话

页面、Excel、报告必须能区分：

```text
complete
partial
not_requested
unavailable
```

并能展示排序、目标数量、实际数量、平台报告总量、停止原因和采集时间。比如“最新评论 50 / 平台显示 1278”不能写成“分析了全部 1278 条评论”。

## 12. 单独业务调试

### 当前已实现：Decision Probe

生产入口是正式 `CollectionDecisionService`。当前可以用：

```text
scripts/dev/probe_collection_decision.py
```

输入显式 `CollectionDecisionRequestV1` JSON，默认注入当前 XHS Capability，输出正式 `CollectionDecisionV1` JSON。它只验证业务 Decision，不访问 TikHub、不访问 PostgreSQL、不需要 Secret，也不复制决策逻辑。

### 当前已实现：Provider Config / Route 验证

生产入口是 System Provider Config + `ProviderRegistry`。自动测试验证：

- 同一 Provider 类型可以有多个稳定配置实例；
- `provider_config_id + platform` 解析到当前 Capability；
- 禁用 Config、未知 Provider、未实现平台、Base URL 不在 allowlist 时关闭失败；
- 数据库只有 `secret_ref`，没有 API Key/Token 明文列。

### 后续 Stage 7：Operation Probe

目标是只验证一个真实/Fixture Operation：请求参数、分页、Raw、Mapper、Canonical。真实 Probe 必须复用正式 Provider Config/Registry/Client/Operation/Mapper，通过正式 Secret 边界读取凭据，默认关闭、不进入普通 CI、不写生产业务数据库。

### 后续 Stage 7：Business Pipeline Probe

完整目标链路是：

```text
Search
→ previous state
→ 正式 Decision Service
→ Detail/Comment/Reply action
→ Budget limit
→ Raw/Canonical
→ decisions.jsonl
→ XLSX
```

第一次运行保存 Probe Snapshot；第二次读取上一次 Snapshot，验证：

- 重复内容评论数不变是否真的没有再次请求评论；
- 评论数增加是否进入增量路径或受控刷新；
- 零评论是否直接短路；
- Budget 到达时是否安全停止。

生产使用 PostgreSQL previous state，Probe 使用 Probe Snapshot；**决策实现必须是同一份生产代码**。在这个完整 Probe 真实实现进入 main 前，不得因为 Decision Probe 已存在就宣称 Business Pipeline Probe 已完成。

## 13. 平台差异不能被“统一参数”掩盖

统一的是业务语义和 Canonical，不是第三方 API：

- 小红书有 App V2 原生排序/时间筛选；
- 抖音搜索和详情/评论属于不同 TikHub API family；
- 微博首版明确混合 Web 搜索、App 详情/一级评论、Web V2 二级评论；
- B站当前搜索没有批准的原生时间过滤，弹幕是独立 enrichment；
- 快手 App Search V2 只有 keyword + pcursor，首版评论明确使用 Web 评论接口。

具体参数和停止条件必须看目标平台文档，不能照抄其他平台。

## 14. 文档更新要求

修改 Provider Config 身份/Secret/Base URL/平台选择、某个平台的 endpoint、分页、业务配置、Mapper、Fixture 或 Probe 时，同任务检查并更新对应长期事实文档；跨平台规则变化再同步 Blueprint 08/07。

平台文档必须如实写“已实现 / 待实现 / 已 Fixture 验证 / 仅官方文档确认 / 已 Real Probe”，不能用一个状态替代另一个状态。新对话恢复 Stage 7 时，先按 [`../blueprint/README.md`](../blueprint/README.md) 的恢复流程确认当前进度，再读取本文件和目标平台机器事实。