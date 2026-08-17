# 快手采集逻辑

## 1. 当前状态

快手当前正式主链为：

```text
App Search V2
→ App Detail
→ App 一级评论
→ App 二级评论
```

2026-08-16 用户已明确批准把一级、二级评论从 Web 正式切换到 App。Web 评论链不做自动 fallback，只保留为**已验证备用方案**，需要人工显式选择才能使用。

当前任务分支已经具备：

- App Search / Detail / Comments / Sub-comments 生产 Operation；
- Web Comments / Sub-comments 显式备用 Operation；
- 基于真实 TikHub 响应的 Search / Detail / Comment / Reply Mapper；
- 合法脱敏非空 Fixture；
- `CanonicalContentV1 / CanonicalCommentV1` 回归；
- Web/App 评论链同样本 A/B Real Probe 证据；
- Kuaishou Capability / 默认 Registry 接线；
- App 一级/二级正式 endpoint-level Pricing；
- App 一级评论真实 `subCommentCount → metrics.reply_count` 映射。

完整真实结构查询见 [`../blueprint/10-TikHub真实响应结构附录.md`](../blueprint/10-TikHub真实响应结构附录.md)。多 API family 的验证与备用判定规则见 [`../blueprint/11-TikHub多接口验证与备用策略.md`](../blueprint/11-TikHub多接口验证与备用策略.md)。

机器 Fixture 位于：

```text
tests/fixtures/providers/tikhub/kuaishou/
```

## 2. 当前正式 TikHub Operation

| 业务动作 | 正式 Endpoint | 状态 |
| --- | --- | --- |
| 视频搜索 | `GET /api/v1/kuaishou/app/search_video_v2` | primary |
| 作品详情 | `GET /api/v1/kuaishou/app/fetch_one_video` | primary |
| 一级评论 | `GET /api/v1/kuaishou/app/fetch_video_comment` | primary |
| 二级评论 | `GET /api/v1/kuaishou/app/fetch_video_sub_comments` | primary |
| 一级评论备用 | `GET /api/v1/kuaishou/web/fetch_one_video_comment` | verified backup |
| 二级评论备用 | `GET /api/v1/kuaishou/web/fetch_one_video_sub_comment` | verified backup |

默认 Capability 和通用 `build_video_comments_request` / `build_video_sub_comments_request` 只指向 App。Web 有独立显式 builder，但生产主链不会因 App 请求失败自动调用 Web。

## 3. Search V2

当前正式 Search V2 业务参数只有：

```text
keyword
pcursor
```

真实响应主要路径：

```text
data.mixFeeds[].feed
data.pcursor
```

当前主 Operation 没有真实证明可用的排序或发布时间原生筛选，所以 Capability 不对前端伪造这些选项：

```text
native_time_filter = false
supported_sort_modes = ()
supported_time_filters = ()
```

### 3.1 App/Web 搜索数量和内容是否一致

当前 TikHub 快手 Web API family **没有与关键词视频搜索同语义的 Web Search endpoint**，因此不存在合法的：

```text
App Search V2 vs Web Search
```

同关键词 A/B 对象。

所以当前结论不是“二者一致”或“不一致”，而是：

```text
not_equivalent / no_same_semantic_web_search
```

禁止拿 Web 热榜、用户接口或评论接口冒充 Web 搜索进行数量对比。

### 3.2 App 综合搜索候选

TikHub App 另有：

```text
GET /api/v1/kuaishou/app/search_comprehensive
```

它支持关键词、排序、发布时间、时长等筛选，但属于综合搜索语义，不是 Web Search，也不是纯视频 Search V2 的严格等价替代。

代码提供显式 `build_comprehensive_search_candidate_request` 供未来 A/B。当前状态：

```text
candidate_pending_probe
```

未来真实实验必须只比较其中可识别的视频稳定 ID，并记录主/候选单页数量、交集、仅主、仅候选、并集和 Jaccard。综合搜索返回的非视频对象不得进入视频集合数量。

## 4. Detail

App Detail：

```text
GET /api/v1/kuaishou/app/fetch_one_video
photo_id=<external_content_id>
```

真实业务 item 路径：

```text
data.photos[0]
```

Provider 中出现的数字 ID 进入 Canonical 时统一转成字符串。

## 5. App 一级评论主链

请求：

```text
GET /api/v1/kuaishou/app/fetch_video_comment
photo_id
pcursor
```

真实一级列表：

```text
data.rootComments[]
```

响应还可以包含：

```text
data.subCommentsMap.<root>.subComments[]
```

2026-08-16 的真实 endpoint ledger 已确认一级根评论存在两个不同语义的字段：

```text
displaySubCommentCount   # boolean，仅表示是否显示回复数/回复入口
subCommentCount          # integer，实际回复数量
```

因此：

- `displaySubCommentCount == true` 只能作为“该 root 可能存在回复”的正向显示信号，**不能当回复数量**；
- `subCommentCount > 0` 是选择有回复 root 的直接数量证据；
- Mapper 在 `subCommentCount` 实际存在时写入 `metrics.reply_count` 并声明 `metrics.reply_count` 已观察；
- 不存在该字段时保持 `reply_count = null`，不从布尔显示开关或 `subCommentsMap` 长度猜总数。

评论 Probe 不能机械使用 `rootComments[0]` 请求二级评论。需要验证二级结构时，应优先选择存在以下正向回复信号的 root：

```text
subCommentCount > 0
或 displaySubCommentCount == true
或已返回非空 subCommentsMap
```

## 6. App 二级评论主链

请求：

```text
GET /api/v1/kuaishou/app/fetch_video_sub_comments
photo_id
root_comment_id
pcursor
count = 1..20
```

2026-08-16 的真实 A/B 已证明该 App 二级接口对同一个有回复根评论返回：

```text
HTTP 200
data.subComments[] 非空
```

Mapper 继续使用统一评论树规则：

- `comment_id` → `external_comment_id`；
- `photo_id` / 请求上下文 → `external_content_id`；
- `root_comment_id` 由请求上下文明确给出；
- `likedCount` → 评论点赞指标；
- 一级根评论 `subCommentCount` → `metrics.reply_count`；
- `user_id` → 公开作者账号 ID；
- 没有明确直接父评论 ID 时，不猜 `parent_comment_id`。

## 7. Web 已验证备用评论链

备用请求：

```text
GET /api/v1/kuaishou/web/fetch_one_video_comment
GET /api/v1/kuaishou/web/fetch_one_video_sub_comment
```

2026-08-16 使用同一个真实作品、同一个明确具有回复数的根评论做 Web/App 对照：

| 项目 | Web | App |
| --- | --- | --- |
| 一级评论 | HTTP 200、非空 | HTTP 200、非空 |
| 二级评论 | HTTP 200、非空 | HTTP 200、非空 |
| 二级主要路径 | `data.subComments[]` | `data.subComments[]` |
| 一级响应携带部分回复 | `subCommentsMap` | `subCommentsMap.<root>.subComments[]` 更丰富 |
| 当次 endpoint_cost：一级 | 0.002 USD | 0.001 USD |
| 当次 endpoint_cost：二级 | 0.010 USD | 0.001 USD |

因此 Web 一级/二级当前状态为：

```text
verified_backup
```

但该状态只说明“真实兼容证据存在”，不建立任何运行时 fallback。

### 7.1 为什么不自动 fallback

App 失败后自动切 Web 会同时引入：

- Provider 响应语义漂移被隐藏；
- 同一逻辑请求可能产生双倍费用；
- 重复 Raw/Attempt 与去重复杂度；
- 故障排查时无法快速判断实际使用了哪套 family。

因此首版固定：

```text
App failure → 正常失败/重试/审计路径
           → 不自动调用 Web
```

如果以后要正式回切 Web，必须显式修改 Operation Matrix、Pricing/Capability/测试/文档，并形成新的变更证据。

## 8. 当前 Capability

当前快手 Capability 正式声明：

```text
comments operation = fetch_video_comment
comments.supports_reply_count = true
comments.supports_sub_comments = true
sub_comments operation = fetch_video_sub_comments
```

`supports_reply_count = true` 的机器含义是：当前 App 一级评论真实响应已经证明存在 `subCommentCount`，且生产 Mapper 能把它映射为 `CanonicalCommentV1.metrics.reply_count`；它不是仅由文档声明的能力。

仍不声明：

```text
supports_incremental_comment_sort = true
```

因为当前评论接口没有真实证明可依赖的稳定“最新增量”业务排序语义。

Web `fetch_one_video_comment` / `fetch_one_video_sub_comment` 不进入默认 Capability。

## 9. Pricing 与执行审计

当前正式 App 评论 endpoint 已进入版本化 `pricing.toml`：

```text
/api/v1/kuaishou/app/fetch_video_comment       0.001 USD/request
/api/v1/kuaishou/app/fetch_video_sub_comments 0.001 USD/request
```

价格来自 2026-08-16 同样本 A/B 前的 `get_endpoint_info` 核验。Web 备用价格继续保留用于显式 Probe/人工切换评估。

当前 Stage 1—7 **没有请求次数/金额 Budget Runtime、Budget Account 或 Reservation Ledger**。真实发送仍必须经过版本化 Pricing、Provider Request/Attempt、Billing 快照、Dispatch/Fencing 与不可变 Raw 审计边界；不能把历史价格记录理解为发送预算门禁，也不能绕过 Provider 执行审计。

## 10. 评论成本控制

主链切 App 不改变通用评论成本策略：

- `comment_count=0` → 不请求评论；
- 重复内容 `comment_count` 未变化 → 默认不重抓；
- 其他互动变化但评论数不变 → 不因此重抓评论；
- 评论数增加 → 受控刷新；
- 评论数下降 → 记录下降并受控刷新，不根据部分页猜删除；
- 默认完整阈值 50、一级目标 50、每个一级线程二级目标 5；
- 返回页超过目标时整页保存；
- 每次真实发送继续受 Provider Request/Attempt、Pricing/Billing、Fencing 与 Raw 审计边界约束。

## 11. 标准 Pipeline

当前正式路径：

```text
search_video_v2
→ Search Raw
→ Kuaishou Mapper / Observation
→ photo_id 去重
→ 指标 / comment_count 比较
→ 必要时 app/fetch_one_video
→ Comment Eligibility
→ app/fetch_video_comment
→ 对有回复线程 app/fetch_video_sub_comments
→ Raw
→ Kuaishou Mapper
→ Canonical
→ Ingestion
```

API family 的变化只发生在 Provider Operation 边界；Canonical / Ingestion / 数据库不因 App/Web 选型变化而重写。

## 12. 时间窗口与 Deep Collection

Search V2 没有原生时间范围：

- 前端不能把“最近一天/一周”标成 Provider 原生筛选；
- 需要时间边界时只能基于已验证发布时间做本地停止/筛选；
- 无法可靠判断时间时按显式页数/执行策略停止，不伪造 Provider 能力。

Deep Collection 仍从内部 `content_id` 解析真实 `photo_id` 并走同一 Provider Operation、Raw、Mapper、Canonical 链，不允许浏览器直接调用 TikHub。

## 13. 独立验证

当前至少由以下真实证据/回归覆盖：

```text
tests/fixtures/providers/tikhub/kuaishou/
tests/fixtures/providers/tikhub/endpoint_ledger/2026-08-16/kuaishou.sanitized.json
tests/unit/collection/test_kuaishou_tikhub_operation.py
tests/unit/collection/test_tikhub_api_family_candidates.py
tests/unit/collection/test_tikhub_api_family_compare.py
tests/unit/collection/test_tikhub_real_search_mappers.py
tests/unit/collection/test_tikhub_real_detail_mappers.py
tests/unit/collection/test_tikhub_real_comment_mappers.py
tests/unit/collection/test_tikhub_real_reply_mappers.py
tests/unit/collection/test_tikhub_real_capabilities.py
tests/unit/collection/test_tikhub_pricing.py
tests/integration/content/test_tikhub_real_normalized_ingestion.py
```

Real Probe 只用于外部事实变化或现有 Fixture/endpoint ledger 证据不足时的最小验证，不应为普通单元测试重复产生 TikHub 费用。
