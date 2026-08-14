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
- 抖音、微博、B站、快手 Operation/Mapper 尚未进入 main，平台文档记录的是 Stage 7 已批准目标链路和实施门禁，不得理解为代码已存在；
- 五个平台默认 Provider 都是 TikHub，但架构允许以后逐平台显式替换 Provider；
- Real Provider Probe 的安全、Raw、Canonical、XLSX 边界已经固化；
- Stage 7 Scheduler 仍等待 misfire/catch-up 决策，不能因为 Provider 开始开发就提前启用自动调度。

## 3. 通用抓取逻辑

所有平台都遵守：

```text
关键词搜索
→ 保存 Search Raw
→ Mapper 得到当前 Observation
→ 按 platform + external_content_id 去重
→ 与数据库/Probe 上一次状态比较
→ 决定是否抓详情
→ 决定是否抓一级评论
→ 决定是否抓二级回复
→ 每个真实 HTTP Attempt 先取得预算
→ 保存每次 Raw
→ Mapper → Canonical
→ Ingestion → PostgreSQL
```

搜索结果重复并不丢失本次发现来源，只是尽量避免重复付费抓详情/评论。

## 4. 评论决策最简表

| 内容状态 | 当前评论数 | 与上次相比 | 默认评论动作 |
| --- | ---: | --- | --- |
| 新内容 | 0 | — | 跳过，`provider_reported_zero` |
| 新内容 | >0 | — | 按自适应策略采集 |
| 新内容 | 未知 | — | 先看 Capability/详情；必要时受预算首屏探测 |
| 已有内容 | 0 | 未变化 | 跳过 |
| 已有内容 | >0 | 未变化 | **跳过，不重新抓评论** |
| 已有内容 | >0 | 增加 | 增量评论或受控刷新 |
| 已有内容 | >0 | 减少 | 记录下降 + 受控刷新；不猜具体删除 |
| 任意 | 任意 | 任意 | 人工 Deep Collection 可加深，但仍受预算 |

点赞、分享、收藏、播放等变化但 `comment_count` 不变时，默认只更新对应指标，不因此重抓评论。

## 5. 默认省钱参数

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
- 重复帖子评论数不变时不重抓；
- 真正硬限制是请求/费用 Budget，不是“刚好 50 行”。

## 6. 前端配置和内部参数

前端配置业务语义：关键词、排序、发布时间范围、内容类型、评论阈值/目标/排序、二级回复目标、Deep Collection、预算。

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

前端只能看到 Capability 明确支持的选项；不支持发布时间筛选的平台不能伪装支持。

## 7. 时间窗口

- 搜索时间范围小于调度周期：只 Warning，仍允许保存和运行；
- Provider 不支持或参数非法：Error；
- Provider 最小时间窗大于调度周期：允许重叠抓取，依靠去重和 Decision Pipeline 减少下游费用。

## 8. Deep Collection

内容已经存在时，内容页按钮只需要提交内部 `content_id`，后端解析平台、外部 ID 和 Provider；用户不需要手抄 note_id/aweme_id/photo_id。

系统尚未发现的内容可以走高级“外部内容 ID / 分享链接直接采集”。两种入口最终都必须复用正式 Operation、Budget、Raw、Mapper、Canonical 和 Ingestion。

## 9. 费用怎么理解

页面区分：

1. **预计费用**：有历史时按历史 Run 估算，无历史时保守估算；
2. **理论请求上限**：由 Plan 的请求/分页上限计算；
3. **数据库硬预算**：每个真实 Attempt 发送前原子预留，才是实际费用控制。

消费优先级：

```text
关键词发现
→ 必要详情
→ 一级评论
→ 二级回复
→ 可选 enrichment / Deep Collection
```

## 10. 评论覆盖必须说实话

页面、Excel、报告必须能区分：

```text
complete
partial
not_requested
unavailable
```

并能展示排序、目标数量、实际数量、平台报告总量、停止原因和采集时间。比如“最新评论 50 / 平台显示 1278”不能写成“分析了全部 1278 条评论”。

## 11. 单独业务调试

### Operation Probe

只验证一个真实/Fixture Operation：请求参数、分页、Raw、Mapper、Canonical。

### Business Pipeline Probe

验证完整业务逻辑：

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
- 评论数增加是否进入增量路径；
- 零评论是否直接短路；
- Budget 到达时是否安全停止。

生产使用 PostgreSQL previous state，Probe 使用 Probe Snapshot；**决策实现必须是同一份生产代码**。

## 12. 平台差异不能被“统一参数”掩盖

统一的是业务语义和 Canonical，不是第三方 API：

- 小红书有 App V2 原生排序/时间筛选；
- 抖音搜索和详情/评论属于不同 TikHub API family；
- 微博首版明确混合 Web 搜索、App 详情/一级评论、Web V2 二级评论；
- B站当前搜索没有批准的原生时间过滤，弹幕是独立 enrichment；
- 快手 App Search V2 只有 keyword + pcursor，首版评论明确使用 Web 评论接口。

具体参数和停止条件必须看目标平台文档，不能照抄其他平台。

## 13. 文档更新要求

修改某个平台的 endpoint、分页、业务配置、Mapper、Fixture 或 Probe 时，同任务检查并更新对应平台文档；跨平台规则变化再同步 Blueprint 08/07。

平台文档必须如实写“已实现 / 待实现 / 已 Fixture 验证 / 仅官方文档确认 / 已 Real Probe”，不能用一个状态替代另一个状态。
