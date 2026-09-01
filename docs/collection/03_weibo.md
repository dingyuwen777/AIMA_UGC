# 微博采集实现

本文说明微博当前 TikHub 生产链为什么是 **Web Search + App Detail/Comments + Web V2 SubComments** 的混合实现，以及相关 Operation、Mapper、Capability、Fixture 和候选接口在哪里。

真实 JSON 路径：

[`../appendix/02_TikHub五平台真实响应与字段映射.md`](../appendix/02_TikHub五平台真实响应与字段映射.md)

## 1. 当前代码

```text
Operation / Pagination
→ backend/src/aima_ugc/adapters/providers/tikhub/operations/weibo.py

Mapper
→ backend/src/aima_ugc/adapters/providers/tikhub/mappers/weibo.py

Capability
→ backend/src/aima_ugc/adapters/providers/tikhub/capabilities.py

Fixture
→ tests/fixtures/providers/tikhub/weibo/
```

## 2. 当前正式主 Operation

```text
Search
GET /api/v1/weibo/web/fetch_search

Detail
GET /api/v1/weibo/app/fetch_status_detail

Comments
GET /api/v1/weibo/app/fetch_status_comments

SubComments
GET /api/v1/weibo/web_v2/fetch_post_sub_comments
```

这里刻意没有为了“版本整齐”强制全部使用 App 或 Web。接口选择按**每个业务 Operation 的真实结构、分页、Mapper 和验证证据**决定。

## 3. Search Capability

当前业务搜索模式：

```text
general
latest
hot
```

时间：

```text
all
hour
day
week
month
```

当前：

```text
native_time_filter = true
observes_comment_count = true
```

微博当前 Search 的业务维度不要再拆成一套虚构的 `sort × video/image/article` 组合；精确合法输入以 `capabilities.py + operations/weibo.py` 为准。

## 4. Search 真实响应

当前 Web Search 真实业务对象：

```text
data.data.cards[].mblog
```

Fixture：

- [`tests/fixtures/providers/tikhub/weibo/search_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/weibo/search_page1.sanitized.json)

这一结构曾由 Real Probe 纠正，不能把其他平台的 `items[]` 模板套过来。

当前 Search 参数还可以表达 Web `time_scope`；这也是为什么 App Search All Candidate 不能简单视为完全等价备用。

## 5. Detail

当前：

```text
GET /api/v1/weibo/app/fetch_status_detail
```

真实内容：

```text
data.detailInfo.status
```

Fixture：

- [`tests/fixtures/providers/tikhub/weibo/detail.sanitized.json`](../../tests/fixtures/providers/tikhub/weibo/detail.sanitized.json)

当前 Operation 对这个核心路径 fail closed：找不到时不在响应其他位置漫游猜测。

## 6. 一级评论

当前：

```text
GET /api/v1/weibo/app/fetch_status_comments
```

真实评论项：

```text
data.items[].data
```

真实下一页 `max_id`：

```text
data.moreInfo.params.max_id
```

Fixture：

- [`tests/fixtures/providers/tikhub/weibo/comments_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/weibo/comments_page1.sanitized.json)

Capability：

```text
comment_sort_modes = hot / latest
supports_reply_count = true
supports_sub_comments = true
supports_incremental_comment_sort = false
```

## 7. 二级评论

当前正式：

```text
GET /api/v1/weibo/web_v2/fetch_post_sub_comments
```

真实列表：

```text
data.data[]
```

真实 `reply_comment` 可以帮助 Mapper 确定直接父评论；`rootid/rootidstr` 不能误当微博原内容 ID。

Fixture：

- [`tests/fixtures/providers/tikhub/weibo/sub_comments_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/weibo/sub_comments_page1.sanitized.json)

## 8. 为什么微博当前不声明最新评论增量

Capability：

```text
supports_incremental_comment_sort = false
```

即使业务参数有 `latest`，当前真实样本/排序语义仍不足以让通用 Collection 安全执行：

```text
遇到 known comment
→ 停止后续页
```

因此走受控刷新并记录 Coverage。

如果未来要开启，需要用当前正式 Comments Operation 重新证明：

- 稳定 newest-first；
- 分页顺序；
- 已知 ID 边界不会漏同页新项。

## 9. App Search All Candidate

代码中有：

```text
GET /api/v1/weibo/app/fetch_search_all
```

当前历史 A/B 曾得到：

```text
Web unique = 10
App unique = 11
shared = 9
union = 12
Jaccard = 0.75
```

这说明两者高度重合，但并不是完全相同的集合。

此外：

```text
Web Search 可表达 time_scope
App Candidate 不伪造这个 Web 私有参数
```

所以当前仍是显式候选，不自动 fallback。

## 10. Web V2 一级评论 Candidate

代码还保留：

```text
GET /api/v1/weibo/web_v2/fetch_post_comments
```

作为 App Comments 的候选。

历史同一真实内容 A/B 曾得到双方 1/1 稳定评论 ID 一致，但 Raw shape 不同，当前一级评论主链仍是 App。

## 11. 为什么一个平台可以混用不同 API family

架构判断单位是：

```text
Provider + Platform + Business Operation
```

而不是：

```text
“微博只能全 App”
或
“微博只能全 Web”
```

因为 Search、Detail、Comments、SubComments 本身是不同能力，可能在不同 family 上有更稳定的结构和分页。

但每次真实 Request/Attempt/Raw 都会记录实际 operation/endpoint 事实，来源链不会因为混用 family 变模糊。

## 12. 要改什么时改哪里

### Search 切 App

```text
operations/weibo.py candidate
→ 同条件 Real A/B
→ Pagination/Extractor
→ Mapper/Fixture
→ Pricing
→ Capability
→ Tests
→ 本文/TikHub台账
```

### Comments 切 Web V2

```text
同一 content_id A/B
→ 评论稳定 ID / reply_count / pagination
→ Mapper
→ Capability
→ Coverage/Decision tests
```

### JSON path 变化

```text
新 Sanitized Fixture
→ extractor / mappers/weibo.py
→ Canonical Contract Test
```

## 13. 调试顺序

```text
Run/Scope
→ Request/Attempt
→ Web/App Raw Artifact
→ Candidate
→ 对应 Operation Extractor
→ mappers/weibo.py
→ Canonical
→ Relevance/Decision
→ Content/Comment
```

SQL：

[`../appendix/01_PostgreSQL查询与调试实战.md`](../appendix/01_PostgreSQL查询与调试实战.md)
