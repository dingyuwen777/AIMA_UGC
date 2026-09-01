# 抖音采集实现

本文是抖音当前 TikHub 生产实现的代码导航。真实 JSON 路径和 Fixture 见：

[`docs/appendix/02_TikHub五平台真实响应与字段映射.md`](../appendix/02_TikHub五平台真实响应与字段映射.md)

## 1. 当前代码

```text
Operation / Pagination
→ backend/src/aima_ugc/adapters/providers/tikhub/operations/douyin.py

Mapper
→ backend/src/aima_ugc/adapters/providers/tikhub/mappers/douyin.py

Capability
→ backend/src/aima_ugc/adapters/providers/tikhub/capabilities.py

Fixture
→ tests/fixtures/providers/tikhub/douyin/
```

生产 Collection 串联：

- [`backend/src/aima_ugc/bootstrap/collection_scope.py`](../../backend/src/aima_ugc/bootstrap/collection_scope.py)

## 2. 当前正式主 Operation

```text
Search
POST /api/v1/douyin/search/fetch_video_search_v2

Detail
GET /api/v1/douyin/app/v3/fetch_one_video_v3

Comments
GET /api/v1/douyin/app/v3/fetch_video_comments

Replies
GET /api/v1/douyin/app/v3/fetch_video_comment_replies
```

Search 当前主链是 V2；代码还保留 V1 Candidate Builder，只用于显式 A/B，不自动 fallback。

## 3. Search 当前 Capability

排序：

```text
general
most_liked
latest
```

发布时间：

```text
all
1d
7d
180d
```

时长：

```text
all
under_1m
1_5m
over_5m
```

内容类型：

```text
all
video
image
```

当前：

```text
native_time_filter = true
observes_comment_count = true
```

这些不是前端静态常量，精确业务参数由 `capabilities.py + operations/douyin.py` 决定。

## 4. Search 请求和真实响应

当前 Search Builder 会把业务参数翻译成 TikHub V2 参数；真实业务 item 位于：

```text
data.business_data[]
```

其中包含：

```text
aweme_info
```

Fixture：

- [`tests/fixtures/providers/tikhub/douyin/search_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/douyin/search_page1.sanitized.json)

如果 TikHub 改了 wrapper/path，应先用新 Sanitized Fixture 让 Extractor/Mapper 测试暴露问题，再改代码。

## 5. Search Pagination

当前分页状态主要围绕：

```text
cursor
search_id
backtrace
has_more
```

生产 `DouyinSearchPagination` 从实际响应的 business config / next page 信息推进，不把这些 Provider 私有状态放进 Canonical。

分页要防：

- 空页；
- `has_more=false`；
- cursor 不推进；
- search_id/backtrace 丢失或异常；
- 技术安全上限。

要改分页：

```text
operations/douyin.py
→ pagination unit tests
```

不要把 `cursor/search_id` 写进 Collection 通用 Domain。

## 6. Detail

当前：

```text
GET /api/v1/douyin/app/v3/fetch_one_video_v3
```

真实内容：

```text
data.aweme_detail
```

Fixture：

- [`tests/fixtures/providers/tikhub/douyin/detail.sanitized.json`](../../tests/fixtures/providers/tikhub/douyin/detail.sanitized.json)

Mapper 可从当前真实 Detail 观察标题/正文、作者、发布时间、互动指标、视频信息等 Canonical 事实。精确字段映射直接看 [`backend/src/aima_ugc/adapters/providers/tikhub/mappers/douyin.py`](../../backend/src/aima_ugc/adapters/providers/tikhub/mappers/douyin.py)。

## 7. 一级评论

当前：

```text
GET /api/v1/douyin/app/v3/fetch_video_comments
```

真实列表：

```text
data.comments[]
```

Fixture：

- [`tests/fixtures/providers/tikhub/douyin/comments_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/douyin/comments_page1.sanitized.json)

当前 Capability：

```text
supports_reply_count = true
supports_sub_comments = true
supports_incremental_comment_sort = false
```

所以抖音可以抓回复数和二级回复，但**当前不声明安全 newest-first 增量评论**。

## 8. 二级回复

当前：

```text
GET /api/v1/douyin/app/v3/fetch_video_comment_replies
```

真实列表：

```text
data.comments[]
```

真实样本提供：

```text
root_comment_id
reply_id / reply_to_reply_id
```

Mapper 只有在 Provider 明确给出直接父评论关系时才填 `parent_comment_id`。

Fixture：

- [`tests/fixtures/providers/tikhub/douyin/replies_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/douyin/replies_page1.sanitized.json)

## 9. 为什么当前不做评论增量 stop

虽然评论接口有分页，但当前 Capability：

```text
supports_incremental_comment_sort = false
```

原因不是“代码没写”，而是当前正式 Comments Operation 没有足够证据证明稳定 newest-first 排序，不能安全用“遇到已知 Comment ID 就停止后续页”。

因此当前走受控刷新，并把真实 Coverage/stop reason 记录下来。

如果以后要打开增量：

```text
真实 same-operation Fixture/Probe
→ 证明排序和边界
→ Pagination tests
→ Capability=true
→ Decision/Collection tests
```

不能只改一个 bool。

## 10. Search V1 Candidate

代码中存在：

```text
POST /api/v1/douyin/search/fetch_video_search_v1
```

Builder：

```text
build_video_search_v1_candidate_request(...)
```

历史受限 A/B 曾在同关键词/条件第一页得到 7/7 稳定内容 ID 一致，但 Raw shape 差异很大；这个证据不足以让 V1 自动成为生产 fallback。

当前规则：

```text
V2 = 主链
V1 = candidate_pending_probe / 显式 A/B 候选
```

详情见：

- [`docs/appendix/03_TikHub多接口验证与备用策略.md`](../appendix/03_TikHub多接口验证与备用策略.md)
- [`docs/appendix/04_TikHub接口选型与真实验证台账.md`](../appendix/04_TikHub接口选型与真实验证台账.md)

## 11. 要改什么时改哪里

### Search Endpoint / 参数

```text
operations/douyin.py
→ Request/Pagination Test
→ Real Fixture/Probe
→ pricing.toml / capabilities.py（按影响）
→ 本文/TikHub附录
```

### Raw shape / 字段路径

```text
新 Sanitized Fixture
→ mappers/douyin.py / extractor
→ Mapper Contract Test
→ 必要 PostgreSQL Vertical Slice
```

### 评论策略

```text
capabilities.py
→ modules/collection/decision.py
→ bootstrap/collection_scope.py
→ comment coverage tests
```

### 切 Search V1

不能只把 URL 替换掉；需要重新确认 Pagination、Extractor、Mapper、Pricing、Fixture、Capability 和真实 A/B。

## 12. 调试顺序

```text
Collection Run / Scope
→ Provider Request / Attempt
→ Douyin Raw Artifact
→ Candidate
→ operations/douyin.py Extractor
→ mappers/douyin.py
→ Canonical
→ Rule Relevance / Decision
→ Content / Comment Ingestion
```

SQL：

[`docs/appendix/01_PostgreSQL查询与调试实战.md`](../appendix/01_PostgreSQL查询与调试实战.md)
