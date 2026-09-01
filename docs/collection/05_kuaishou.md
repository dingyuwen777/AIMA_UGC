# 快手采集实现

本文说明快手当前 **App Search/Detail/Comments/SubComments 主链**、Web 评论备用、真实回复数字段和 `search_comprehensive` 非等价候选。

真实 JSON 路径：

[`../appendix/02_TikHub五平台真实响应与字段映射.md`](../appendix/02_TikHub五平台真实响应与字段映射.md)

## 1. 当前代码

```text
Operation / Pagination
→ backend/src/aima_ugc/adapters/providers/tikhub/operations/kuaishou.py

Mapper
→ backend/src/aima_ugc/adapters/providers/tikhub/mappers/kuaishou.py

Capability
→ backend/src/aima_ugc/adapters/providers/tikhub/capabilities.py

当前 App 主链真实验证账本
→ tests/fixtures/providers/tikhub/endpoint_ledger/2026-08-16/kuaishou.sanitized.json

历史 Web 备用 Fixture
→ tests/fixtures/providers/tikhub/kuaishou/comments_page1.sanitized.json
→ tests/fixtures/providers/tikhub/kuaishou/sub_comments_page1.sanitized.json
```

## 2. 当前正式主 Operation

```text
Search
GET /api/v1/kuaishou/app/search_video_v2

Detail
GET /api/v1/kuaishou/app/fetch_one_video

Comments
GET /api/v1/kuaishou/app/fetch_video_comment

SubComments
GET /api/v1/kuaishou/app/fetch_video_sub_comments
```

当前通用 `build_video_comments_request()` / `build_video_sub_comments_request()` 明确委托 App Builder。

所以：

```text
App = 当前生产主链
Web = verified backup
自动 fallback = 不存在
```

## 3. Search Capability

当前：

```text
content_type = video
native_time_filter = false
observes_comment_count = true
```

当前正式 Search V2 没有向上层暴露一套虚构的排序/时间过滤能力。

如果 UI 需要“最近 7 天”，不能直接翻译成快手 Provider 原生参数并声称 TikHub 已过滤；业务时间窗口需要按当前 Capability/处理链真实实现。

## 4. Search 真实响应和分页

业务 item：

```text
data.mixFeeds[].feed
```

分页 cursor：

```text
data.pcursor
```

Fixture：

- [`tests/fixtures/providers/tikhub/kuaishou/search_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/kuaishou/search_page1.sanitized.json)

当前 `KuaishouSearchPagination` 会对这些情况停止：

```text
response_data_unavailable
empty_page
cursor_unavailable
pagination_not_advanced
```

因此如果出现“第一页正常、第二页无限重复”，应该先看 `operations/kuaishou.py` 的 pagination state，而不是在外层 Worker 加一个平台私有 `seen_cursor` 补丁。

## 5. Detail

当前：

```text
GET /api/v1/kuaishou/app/fetch_one_video
```

真实 item：

```text
data.photos[0]
```

Fixture：

- [`tests/fixtures/providers/tikhub/kuaishou/detail.sanitized.json`](../../tests/fixtures/providers/tikhub/kuaishou/detail.sanitized.json)

Detail 补充 Search 卡片不足的内容/作者/互动事实；精确 `observed_fields` 看 [`mappers/kuaishou.py`](../../backend/src/aima_ugc/adapters/providers/tikhub/mappers/kuaishou.py)。

## 6. App 一级评论

当前：

```text
GET /api/v1/kuaishou/app/fetch_video_comment
```

真实根评论：

```text
data.rootComments[]
```

当前 App 真实样本已经证明存在：

```text
comment_id
content
likedCount
subCommentCount
displaySubCommentCount
user_id
timestamp
```

其中最容易写错的是下面两个字段。

### `subCommentCount`

```text
integer
→ 实际回复数量
→ 可以映射 CanonicalCommentV1.metrics.reply_count
```

### `displaySubCommentCount`

```text
boolean
→ UI 是否显示回复入口/数量类信号
→ 不能转换成 0/1 当 reply_count
```

如果 `subCommentCount` 没有返回：

```text
reply_count = unknown/null
```

不能拿：

```text
len(subCommentsMap[root])
```

猜总回复数。

当前 Capability：

```text
supports_reply_count = true
supports_sub_comments = true
supports_incremental_comment_sort = false
```

## 7. App 一级响应中的 `subCommentsMap`

一级评论响应还可能携带：

```text
data.subCommentsMap.<root>.subComments[]
```

这表示当前响应内嵌了部分二级回复，但不代表：

```text
数组长度 == 总回复数
```

真正回复总量优先使用明确 integer：

```text
subCommentCount
```

Real Probe 如果要找二级评论候选，不能机械选择第一条根评论；应选择：

```text
subCommentCount > 0
```

或其他明确存在回复的真实证据。

## 8. App 二级评论

当前：

```text
GET /api/v1/kuaishou/app/fetch_video_sub_comments
```

请求核心：

```text
photo_id
root_comment_id
pcursor
count
```

当前 `count` 的领域安全范围：

```text
1..20
```

真实响应：

```text
data.subComments[]
```

同样本验证：

```text
HTTP 200
+ data.subComments[] 非空
```

`root_comment_id` 来自请求上下文；如果响应没有可靠直接父评论 ID：

```text
parent_comment_id = null
```

不猜。

当前 App 评论/二级评论直接结构证据看：

- [`tests/fixtures/providers/tikhub/endpoint_ledger/2026-08-16/kuaishou.sanitized.json`](../../tests/fixtures/providers/tikhub/endpoint_ledger/2026-08-16/kuaishou.sanitized.json)

不要把历史 Web Fixture误认为当前 App 主链 Fixture。

## 9. Web 评论链为什么仍保留

已验证备用：

```text
GET /api/v1/kuaishou/web/fetch_one_video_comment
GET /api/v1/kuaishou/web/fetch_one_video_sub_comment
```

同一个真实作品、同一个有回复根评论，历史 A/B：

```text
Web 一级 200 / 非空
App 一级 200 / 非空
Web 二级 200 / 非空
App 二级 200 / 非空
```

历史 Probe 价格：

```text
Web 一级 0.002 USD
Web 二级 0.010 USD
App 一级 0.001 USD
App 二级 0.001 USD
```

当前运行时价格看：

- [`backend/src/aima_ugc/adapters/providers/tikhub/pricing.toml`](../../backend/src/aima_ugc/adapters/providers/tikhub/pricing.toml)

Web 当前状态：

```text
verified_backup
```

只是为未来显式切换保留证据，不代表 Runtime 会在 App 报错后自动发 Web 第二次请求。

## 10. 为什么当前没有安全评论增量

当前：

```text
supports_incremental_comment_sort = false
```

虽然有 `pcursor`，但 cursor 只能证明“能分页”，不能证明评论是可靠 newest-first。

所以不能使用：

```text
遇到已知评论 ID
→ 停后续页
```

的统一增量算法。

当前走受控刷新，并保存真实 Coverage/stop reason。

如果未来打开增量，需要当前正式 App Comments Operation 的真实排序/分页证据和测试。

## 11. `search_comprehensive` 为什么不是 Search V2 备用

代码有 Candidate：

```text
GET /api/v1/kuaishou/app/search_comprehensive
```

但它的业务语义更宽，会包含综合对象，而当前生产 Search V2 是关键词视频搜索。

历史受限 A/B 曾得到：

```text
Video Search V2 unique = 17
Comprehensive unique = 8
shared = 0
Jaccard = 0.0
```

结合本身语义差异，当前结论：

```text
not equivalent as automatic backup
```

未来最多把它作为新的补充发现能力单独设计，不能异常时静默替代 Video Search V2。

## 12. 为什么没有 Web Search A/B

当前快手 Web family 没有和：

```text
/app/search_video_v2
```

同语义的关键词视频 Web Search。

所以状态：

```text
not_equivalent / no_same_semantic_web_search
```

没有合法对照对象时，不应该编造“App/Web 搜索一致率”。

## 13. 要改什么时改哪里

### App Comments 出现字段变化

```text
新的 App Sanitized Fixture / endpoint ledger
→ operations/kuaishou.py extractor/pagination
→ mappers/kuaishou.py
→ Capability tests
→ 本文/TikHub字段附录
```

### 想切 Web Comments

```text
同 content/root 真实 A/B
→ Web Fixture
→ Mapper/分页
→ Pricing
→ Capability/正式 Builder
→ Tests
→ 接口选型台账
```

不能在 `transport.py` 自动 fallback。

### 想使用 Comprehensive Search

先作为**新的业务 Operation**评估，而不是修改现有 Video Search 的异常处理。

### `reply_count` 显示不对

先核对：

```text
subCommentCount
vs
displaySubCommentCount
```

再看 Mapper，不要先改数据库/前端显示。

## 14. 调试顺序

```text
Run / Scope
→ Provider Request / Attempt
→ Kuaishou App Raw
→ Candidate
→ operations/kuaishou.py
→ mappers/kuaishou.py
→ Canonical
→ Decision / Coverage
→ Content / Comment
```

SQL：

[`../appendix/01_PostgreSQL查询与调试实战.md`](../appendix/01_PostgreSQL查询与调试实战.md)
