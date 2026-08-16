# 快手采集逻辑

## 1. 当前状态

快手当前首版正式主链仍为：

```text
App Search V2
→ App Detail
→ Web 一级评论
→ Web 二级评论
```

当前任务分支已经具备：

- Search / Detail / Web Comments / Web Sub-comments 生产 Operation；
- 基于真实 TikHub 响应的 Search / Detail / Comment / Reply Mapper；
- 合法脱敏非空 Fixture；
- `CanonicalContentV1 / CanonicalCommentV1` 回归；
- Web 二级评论非空实证；
- Kuaishou Capability / 默认 Registry 接线；
- Web/App 评论链同样本 A/B Real Probe 证据。

完整真实结构查询见 [`../blueprint/10-TikHub真实响应结构附录.md`](../blueprint/10-TikHub真实响应结构附录.md)。机器 Fixture 位于：

```text
tests/fixtures/providers/tikhub/kuaishou/
```

## 2. 当前正式 TikHub Operation

| 业务动作 | 当前正式 Endpoint |
| --- | --- |
| 视频搜索 | `GET /api/v1/kuaishou/app/search_video_v2` |
| 作品详情 | `GET /api/v1/kuaishou/app/fetch_one_video` |
| 一级评论 | `GET /api/v1/kuaishou/web/fetch_one_video_comment` |
| 二级评论 | `GET /api/v1/kuaishou/web/fetch_one_video_sub_comment` |

App 搜索/详情 + Web 评论是当前批准的四个业务 Operation，不是运行时 fallback。

## 3. Search V2

当前 Search V2 业务参数只有：

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

## 5. Web 一级评论

请求：

```text
GET /api/v1/kuaishou/web/fetch_one_video_comment
photo_id
pcursor
```

真实一级列表：

```text
data.rootComments[]
```

响应还可包含：

```text
data.subCommentsMap
```

评论 Probe 不能机械使用 `rootComments[0]` 请求二级评论。2026-08-16 的 A/B 调查证明，之前一次 Web 二级空页就是弱样本：所选第一条 root 没有正向回复证据。

正确的结构验证应优先选择实际存在以下正向回复信号的 root：

```text
displaySubCommentCount > 0
subCommentCount > 0
或已返回非空 subCommentsMap
```

## 6. Web 二级评论已真实非空验证

请求：

```text
GET /api/v1/kuaishou/web/fetch_one_video_sub_comment
photo_id
root_comment_id
pcursor
```

2026-08-16 使用同一个真实作品、同一个明确具有回复数的根评论重新验证：

```text
HTTP 200
data.subComments[] 非空
data.pcursor 非空
```

因此当前事实是：

> TikHub Web 二级评论接口可返回真实非空回复；早先一次 `subComments=[]` 不能解释成 TikHub 不支持快手二级评论。

对应仓库 Fixture：

```text
tests/fixtures/providers/tikhub/kuaishou/sub_comments_page1.sanitized.json
```

Mapper 规则：

- `comment_id` → `external_comment_id`；
- `photo_id` / 请求上下文 → `external_content_id`；
- `root_comment_id` 由本次请求上下文明确给出；
- `likedCount` → 评论点赞指标；
- `user_id` → 公开作者账号 ID；
- 当前真实响应虽然存在 `reply_to`，但证据不足以证明它必然是另一个评论 ID，因此 **不猜 `parent_comment_id`**。

## 7. Web vs App 评论链 A/B

TikHub 当前还提供两条 App 候选 Operation：

```text
GET /api/v1/kuaishou/app/fetch_video_comment
GET /api/v1/kuaishou/app/fetch_video_sub_comments
```

App 二级评论参数：

```text
photo_id
root_comment_id
pcursor
count = 1..20
```

2026-08-16 用同一个真实作品、同一个有回复根评论做对照：

| 项目 | Web | App |
| --- | --- | --- |
| 一级评论 | HTTP 200、非空 | HTTP 200、非空 |
| 二级评论 | HTTP 200、非空 | HTTP 200、非空 |
| 二级主要路径 | `data.subComments[]` | `data.subComments[]` |
| 一级响应携带部分回复 | `subCommentsMap` | `subCommentsMap.<root>.subComments[]` 更丰富 |
| 当次 endpoint_cost：一级 | 0.002 USD | 0.001 USD |
| 当次 endpoint_cost：二级 | 0.010 USD | 0.001 USD |

上述价格只是本次 `get_endpoint_info` 快照，不能作为永久运行时单价。运行时费用仍由版本化 Pricing + endpoint-level verified 事实控制。

### 当前建议

基于当前样本，**推荐后续把快手评论主链切换到 App**，原因：

1. 同样本一级、二级均能取得真实非空数据；
2. 当前实测 endpoint 单价明显更低；
3. App 一级响应可携带部分二级回复，存在减少后续请求的机会；
4. Search/Detail 本来就在 App family，主链更一致。

但这是正式 Provider Operation Matrix 变更。在用户/业务 Owner 批准前：

- 当前正式主链仍保持 Web 评论；
- 不静默切 App；
- 不实现 Web→App 或 App→Web 自动 fallback；
- App builder 只作为本次候选验证事实，不等于生产 Capability 已切换。

## 8. 当前 Capability

基于 Web 非空真实证据，当前快手 Capability 可以正确声明：

```text
comments.supports_reply_count = true
comments.supports_sub_comments = true
sub_comments operation = fetch_one_video_sub_comment
```

仍不声明：

```text
supports_incremental_comment_sort = true
```

因为当前评论接口没有真实证明可依赖的稳定“最新增量”业务排序语义。

## 9. 评论成本控制

无论最终使用 Web 或 App，通用策略保持：

- `comment_count=0` → 不请求评论；
- 重复内容 `comment_count` 未变化 → 默认不重抓；
- 其他互动变化但评论数不变 → 不因此重抓评论；
- 评论数增加 → 受控刷新；
- 评论数下降 → 记录下降并受控刷新，不根据部分页猜删除；
- 默认完整阈值 50、一级目标 50、每个一级线程二级目标 5；
- 返回页超过目标时整页保存；
- 每次真实发送继续受 Provider Pricing / Budget Ledger 硬门禁。

## 10. 标准 Pipeline

当前正式路径：

```text
search_video_v2
→ Search Raw
→ Kuaishou Mapper / Observation
→ photo_id 去重
→ 指标 / comment_count 比较
→ 必要时 app/fetch_one_video
→ Comment Eligibility
→ web/fetch_one_video_comment
→ 对有回复线程 web/fetch_one_video_sub_comment
→ Raw
→ Kuaishou Mapper
→ Canonical
→ Ingestion
```

如果后续明确批准切换 App，只替换评论 Operation/分页/Mapper 证据边界；Canonical / Ingestion / 数据库不因 Provider API family 改变而重写。

## 11. 时间窗口与 Deep Collection

Search V2 没有原生时间范围：

- 前端不能把“最近一天/一周”标成 Provider 原生筛选；
- 需要时间边界时只能基于已验证发布时间做本地停止/筛选；
- 无法可靠判断时间时按显式页数/预算停止，不伪造 Provider 能力。

Deep Collection 仍从内部 `content_id` 解析真实 `photo_id` 并走同一 Provider Operation、Raw、Mapper、Canonical、Budget 链，不允许浏览器直接调用 TikHub。

## 12. 独立验证

当前至少由以下真实证据/回归覆盖：

```text
tests/fixtures/providers/tikhub/kuaishou/
tests/unit/collection/test_kuaishou_tikhub_operation.py
tests/unit/collection/test_tikhub_real_search_mappers.py
tests/unit/collection/test_tikhub_real_detail_mappers.py
tests/unit/collection/test_tikhub_real_comment_mappers.py
tests/unit/collection/test_tikhub_real_reply_mappers.py
tests/unit/collection/test_tikhub_real_capabilities.py
tests/integration/content/test_tikhub_real_normalized_ingestion.py
```

Real Probe 只用于外部事实变化或现有 Fixture 证据不足时的最小验证，不应为普通单元测试重复产生 TikHub 费用。
