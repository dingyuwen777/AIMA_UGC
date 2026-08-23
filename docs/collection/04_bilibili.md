# B站采集实现

本文说明 B站当前 TikHub App 主链、Web Candidate、真实 Fixture、Capability 和最新评论增量边界。

真实 JSON 路径：

[`../appendix/03_TikHub五平台真实响应与字段映射.md`](../appendix/03_TikHub五平台真实响应与字段映射.md)

## 1. 当前代码

```text
Operation / Pagination
→ backend/src/aima_ugc/adapters/providers/tikhub/operations/bilibili.py

Mapper
→ backend/src/aima_ugc/adapters/providers/tikhub/mappers/bilibili.py

Capability
→ backend/src/aima_ugc/adapters/providers/tikhub/capabilities.py

Fixture
→ tests/fixtures/providers/tikhub/bilibili/
```

## 2. 当前正式主 Operation

```text
Search
GET /api/v1/bilibili/app/fetch_search_by_type

Detail
GET /api/v1/bilibili/app/fetch_one_video

Comments
GET /api/v1/bilibili/app/fetch_video_comments

Replies
GET /api/v1/bilibili/app/fetch_reply_detail
```

当前正式主链全部使用 App family。

代码里同时保留对应 Web Candidate Builder，用于显式 A/B，不进入自动 fallback。

## 3. Search Capability

当前排序：

```text
general
latest
play_count
danmaku_count
```

当前内容类型：

```text
video
```

当前：

```text
native_time_filter = false
observes_comment_count = false
```

这两条很重要。

### `native_time_filter=false`

表示当前正式 App Search 没有被系统认定为支持业务级原生时间过滤。业务可以在自己的处理/停止逻辑中控制时间窗口，但不能在前端写成“B站 Provider 原生支持 7 天筛选”。

### `observes_comment_count=false`

当前 Search Fixture 没有证明搜索卡片可靠提供评论总数。因此：

```text
Search 没 comment_count
→ unknown
```

不能写成 `0`。Detail 可以提供更完整互动事实。

## 4. Search 真实响应

业务列表：

```text
data.data.items[]
```

Fixture：

```text
tests/fixtures/providers/tikhub/bilibili/search_page1.sanitized.json
```

当前可观察：

- `aid/bvid`；
- 标题/摘要；
- UP 主；
- 播放；
- 弹幕等当前 Fixture 证明的字段。

精确 Mapper 以 `mappers/bilibili.py` 为准。

## 5. Detail

```text
GET /api/v1/bilibili/app/fetch_one_video
```

真实 item：

```text
data.data
```

Fixture：

```text
tests/fixtures/providers/tikhub/bilibili/detail.sanitized.json
```

Detail 可以补充 Search 没有观察到的评论数、收藏、投币、时长等事实；哪些字段进入 Canonical 以 Mapper 的 `observed_fields` 为准。

## 6. 一级评论

```text
GET /api/v1/bilibili/app/fetch_video_comments
```

真实列表：

```text
data.data.replies[]
```

当前评论排序：

```text
latest
hot
```

首屏分页当前明确使用：

```text
next_offset = 0
```

真实下一页：

```text
data.data.cursor.pagination_reply.next_offset
```

Fixture：

```text
tests/fixtures/providers/tikhub/bilibili/comments_page1.sanitized.json
```

Capability：

```text
supports_reply_count = true
supports_sub_comments = true
supports_incremental_comment_sort = true
```

## 7. 回复详情

```text
GET /api/v1/bilibili/app/fetch_reply_detail
```

真实结构：

```text
data.data.root
data.data.root.replies[]
```

已观察字段包括：

```text
rpid
root
parent
ctime
like
rcount
```

Fixture：

```text
tests/fixtures/providers/tikhub/bilibili/replies_page1.sanitized.json
```

B站返回的数字 ID 最终转换成 Canonical 字符串身份，不把第三方 JSON number 直接当业务主键类型。

## 8. 为什么 B站当前可以做最新评论增量

Capability：

```text
supports_incremental_comment_sort = true
```

这表示当前 `latest` 评论 Operation、真实分页和样本排序已经足以支持稳定 known-comment boundary。

正确停止顺序：

```text
整页 Raw 保存
→ 整页 Mapper/Ingest
→ 检查是否出现已知稳定 Comment ID
→ 停止下一页
```

不能在当前页中途 `break` 丢掉同页其他新评论。

## 9. Web Candidate

当前代码包含：

```text
Search
/api/v1/bilibili/web/fetch_general_search

Detail
/api/v1/bilibili/web/fetch_one_video

Comments
/api/v1/bilibili/web/fetch_video_comments

Reply
/api/v1/bilibili/web/fetch_comment_reply
```

它们是显式候选。

### 旧 Search A/B 的重要勘误

旧历史比较曾出现：

```text
App = 0
Web = 20
```

后续确认这是**比较器没有正确从 App wrapper 提取稳定视频 ID**，不能解释成“App Search 返回 0 条”。

因此旧数量/Jaccard 结论作废，状态应理解为：

```text
comparison_extractor_invalid
→ 需要重新真实 A/B
```

不能把错误 Probe 输出升级成 Web 生产备用依据。

详细台账：

[`../appendix/05_TikHub接口选型与真实验证台账.md`](../appendix/05_TikHub接口选型与真实验证台账.md)

## 10. Search 排序对齐为什么要谨慎

如果未来做 App/Web A/B，只能比较明确可映射的排序，例如：

```text
latest ↔ pubdate
general ↔ totalrank
```

不能拿不同排序的首屏结果直接算集合差异，然后得出“接口不一致”。

时间过滤也要尊重当前 `native_time_filter=false`，不能在 Candidate 请求里虚构 App 当前没有的原生参数。

## 11. 要改什么时改哪里

### Search/Detail/Comment Endpoint 变化

```text
operations/bilibili.py
→ Real Fixture
→ Operation/Pagination Test
→ pricing.toml / capability（按影响）
→ 本文/TikHub附录
```

### Search 新增 comment_count 观察

必须先：

```text
真实 Search Fixture 证明字段存在
→ Mapper 加 observed_fields
→ Contract Test
→ capabilities.py observes_comment_count=true
```

不能只改 Capability。

### 开启 native time filter

必须证明正式 Operation 真能表达对应过滤，并通过真实验证/分页测试。

### 切 Web family

重新做同业务条件 A/B；旧错误比较结果不能复用。

## 12. 调试顺序

```text
Run / Scope
→ Request / Attempt
→ Bilibili Raw
→ Candidate
→ operations/bilibili.py
→ mappers/bilibili.py
→ Canonical
→ Decision / Coverage
→ Content / Comment
```

SQL：

[`../appendix/01_PostgreSQL查询与调试实战.md`](../appendix/01_PostgreSQL查询与调试实战.md)
