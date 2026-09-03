# TikHub 五平台真实响应与字段映射

> 真实结构实证日期：2026-08-15 至 2026-08-16  
> Provider：TikHub  
> Real Probe Base URL：`https://api.tikhub.io`  
> 验证关键词：`爱玛`

本文回答开发中最具体的问题：

> TikHub 当前某个平台到底调用哪个 Endpoint？真实 JSON 从哪个路径取 item？Operation 怎样分页？Mapper 怎样把字段转成 Canonical？出现结构漂移时应该改哪些代码和测试？

这里的真实响应证据来自仓库 Sanitized Fixture；当前生产事实则由 **Operation + Mapper + Capability + Fixture + Test** 共同确认。本文保留人类理解必须知道的 JSON 路径和实证结论，但不建立第二套完整 Provider Schema。

---

## 1. 先看代码地图

### 请求和分页

```text
backend/src/aima_ugc/adapters/providers/tikhub/operations/
├─ xiaohongshu.py
├─ douyin.py
├─ weibo.py
├─ bilibili.py
└─ kuaishou.py
```

这里决定：

- 当前生产 Endpoint；
- HTTP method；
- 业务参数 → TikHub 参数；
- cursor/page/search_id 等分页推进；
- 怎样从 Raw Response 找到业务 item。

### 字段映射

```text
backend/src/aima_ugc/adapters/providers/tikhub/mappers/
├─ common.py
├─ xiaohongshu.py
├─ douyin.py
├─ weibo.py
├─ bilibili.py
└─ kuaishou.py
```

这里决定：

```text
Provider JSON 字段
→ CanonicalContentV1 / CanonicalCommentV1
→ observed_fields
```

### 当前能力、HTTP 和价格

```text
capabilities.py
→ 当前 Provider + Platform 正式支持什么业务 Operation

runtime.py
→ TikHub Runtime 如何注册/执行 Operation 与 Mapper

transport.py
→ 真正的一次 HTTP 发送边界

pricing.py / pricing.toml
→ 当前运行时 endpoint Pricing 事实
```

### 真实响应 Fixture

```text
tests/fixtures/providers/tikhub/
```

如果本文和当前 Operation/Mapper/Fixture/Test 冲突，以当前机器事实为准，并修正文档。

---

## 2. Real Probe 当时怎样做

实证使用受限采样，不做全量抓取：

```text
Search
→ 每个平台最多 1 页

Detail
→ 从 Search 结果选 1 条真实内容
→ xiaohongshu 额外验证图文和视频

Comments
→ 每个平台最多 1 页

Sub-comments / Replies
→ 找到确实存在回复的根评论
→ 最多 1 页
```

跨接口使用真实 Provider ID 串联：

```text
Search content_id
→ Detail / Comments
→ root_comment_id
→ Sub-comments / Replies
```

提交仓库前才做脱敏。因此：

- Real Probe 证明跨接口真实 ID 可用；
- Sanitized Fixture 用于后续结构回归；
- Fixture 中脱敏后的 ID 不需要保持原真实值。

---

## 3. 五平台当前证据总览

| 平台 | Search | Detail | 一级评论 | 二级评论/回复 | 当前结论 |
| --- | --- | --- | --- | --- | --- |
| 小红书 | 非空 | 图文/视频均非空 | 非空 | 非空 | 当前 Canonical 可表达 |
| 抖音 | 非空 | 非空 | 非空 | 非空 | 当前 Canonical 可表达 |
| 微博 | 非空 | 非空 | 非空 | 非空 | 当前 Canonical 可表达 |
| B站 | 非空 | 非空 | 非空 | 非空 | 当前 Canonical 可表达 |
| 快手 | 非空 | 非空 | App 主链非空，Web 备用同样本非空 | App/Web 同样本均实测非空 | App 当前正式主链 |

这些 Fixture 已经用于生产 Extractor / Mapper → Canonical，并在相关纵切中进入 PostgreSQL Ingestion；现有证据没有要求为 Provider 私有结构扩大 Canonical V1。

---

# 4. 小红书 Xiaohongshu

当前生产 Operation：

- [`backend/src/aima_ugc/adapters/providers/tikhub/operations/xiaohongshu.py`](../../backend/src/aima_ugc/adapters/providers/tikhub/operations/xiaohongshu.py)

当前 Mapper：

- [`backend/src/aima_ugc/adapters/providers/tikhub/mappers/xiaohongshu.py`](../../backend/src/aima_ugc/adapters/providers/tikhub/mappers/xiaohongshu.py)

Operation 当前还包含 App V1 / Web V3 的显式 A/B Candidate Builder，但它们不等于自动 fallback。

## 4.1 Search

当前主 Endpoint：

```text
GET /api/v1/xiaohongshu/app_v2/search_notes
```

真实主要结构：

```json
{
  "code": 200,
  "data": {
    "data": {
      "items": [
        {
          "note": {
            "note_id": "...",
            "type": "...",
            "title": "...",
            "desc": "...",
            "user": {},
            "interact_info": {}
          }
        }
      ]
    }
  }
}
```

业务 item 容器：

```text
data.data.items[]
```

当前 `XiaohongshuSearchPagination` 还会从响应中观察：

```text
search_id
search_session_id
next_page
has_more
```

并对空页、重复页、分页不前进做停止判断。

Fixture：

[`tests/fixtures/providers/tikhub/xiaohongshu/search_notes_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/xiaohongshu/search_notes_page1.sanitized.json)

## 4.2 Detail

图文：

```text
GET /api/v1/xiaohongshu/app_v2/get_image_note_detail
```

视频：

```text
GET /api/v1/xiaohongshu/app_v2/get_video_note_detail
```

真实 item 路径：

```text
图文: data.data[0].note_list[0]
视频: data.data[0]
```

Fixture：

- [`tests/fixtures/providers/tikhub/xiaohongshu/image_detail.sanitized.json`](../../tests/fixtures/providers/tikhub/xiaohongshu/image_detail.sanitized.json)
- [`tests/fixtures/providers/tikhub/xiaohongshu/video_detail.sanitized.json`](../../tests/fixtures/providers/tikhub/xiaohongshu/video_detail.sanitized.json)

## 4.3 一级评论

```text
GET /api/v1/xiaohongshu/app_v2/get_note_comments
```

真实列表：

```text
data.data.comments[]
```

真实分页状态存在两种兼容形态：

```text
data.data.cursor + data.data.index + data.data.pageArea
或
data.data.cursor = {"cursor":"...","index":2,"pageArea":"ALL"} 的 JSON 字符串
```

后一种形态必须先解码，再把 `cursor`、`index`、`pageArea` 分别传入下一页 `get_note_comments` 请求。把整个 JSON 字符串原样作为 cursor、同时沿用旧 index/pageArea，会让续页错误地返回空列表。当前解析 Owner 是 [`backend/src/aima_ugc/adapters/providers/tikhub/operations/xiaohongshu.py`](../../backend/src/aima_ugc/adapters/providers/tikhub/operations/xiaohongshu.py)，共享 Runtime 负责把解析后的状态构造成下一页请求。

根评论可以观察到：

- 评论 ID；
- 用户；
- 文本；
- 点赞；
- 回复数；
- 内嵌 `sub_comments[]`（样本存在时）。

Canonical 根评论：

```text
root_comment_id = external_comment_id
parent_comment_id = null
```

Fixture：

[`tests/fixtures/providers/tikhub/xiaohongshu/comments_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/xiaohongshu/comments_page1.sanitized.json)

## 4.4 二级评论

```text
GET /api/v1/xiaohongshu/app_v2/get_note_sub_comments
```

真实列表：

```text
data.data.comments[]
```

二级回复复用同一个分页状态解析器；其 `data.data.cursor` 也可能是包含 `cursor` 与 `index` 的 JSON 字符串，下一页 `get_note_sub_comments` 必须拆分后传参。

Fixture：

[`tests/fixtures/providers/tikhub/xiaohongshu/sub_comments_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/xiaohongshu/sub_comments_page1.sanitized.json)

---

# 5. 抖音 Douyin

Operation：

- [`backend/src/aima_ugc/adapters/providers/tikhub/operations/douyin.py`](../../backend/src/aima_ugc/adapters/providers/tikhub/operations/douyin.py)

Mapper：

- [`backend/src/aima_ugc/adapters/providers/tikhub/mappers/douyin.py`](../../backend/src/aima_ugc/adapters/providers/tikhub/mappers/douyin.py)

当前主 Search 是 V2；代码中有 V1 Candidate Builder，仅用于显式 A/B。

## 5.1 Search

```text
POST /api/v1/douyin/search/fetch_video_search_v2
```

真实业务列表：

```text
data.business_data[]
```

业务 item 中包含 `aweme_info`。

当前 `DouyinSearchPagination` 会从真实 `business_config/next_page` 等位置处理：

```text
cursor
search_id
backtrace
has_more
```

这些 Provider 私有分页字段不会进入 Canonical Content。

Fixture：

[`tests/fixtures/providers/tikhub/douyin/search_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/douyin/search_page1.sanitized.json)

## 5.2 Detail

```text
GET /api/v1/douyin/app/v3/fetch_one_video_v3
```

真实 item：

```text
data.aweme_detail
```

已真实观察视频时长、播放、下载、转发等可映射事实。

Fixture：

[`tests/fixtures/providers/tikhub/douyin/detail.sanitized.json`](../../tests/fixtures/providers/tikhub/douyin/detail.sanitized.json)

## 5.3 一级评论

```text
GET /api/v1/douyin/app/v3/fetch_video_comments
```

真实列表：

```text
data.comments[]
```

Fixture：

[`tests/fixtures/providers/tikhub/douyin/comments_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/douyin/comments_page1.sanitized.json)

## 5.4 评论回复

```text
GET /api/v1/douyin/app/v3/fetch_video_comment_replies
```

真实列表：

```text
data.comments[]
```

样本提供：

```text
root_comment_id
reply_id / reply_to_reply_id
```

当 Provider 明确给出直接父回复时，Mapper 才写 `parent_comment_id`；不根据用户名或数组位置猜。

Fixture：

[`tests/fixtures/providers/tikhub/douyin/replies_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/douyin/replies_page1.sanitized.json)

---

# 6. 微博 Weibo

Operation：

- [`backend/src/aima_ugc/adapters/providers/tikhub/operations/weibo.py`](../../backend/src/aima_ugc/adapters/providers/tikhub/operations/weibo.py)

Mapper：

- [`backend/src/aima_ugc/adapters/providers/tikhub/mappers/weibo.py`](../../backend/src/aima_ugc/adapters/providers/tikhub/mappers/weibo.py)

当前主 Search 使用 Web；代码里保留 App Search All Candidate。一级评论当前主链使用 App，另有 Web V2 Candidate；二级评论当前使用 Web V2。

## 6.1 Search

```text
GET /api/v1/weibo/web/fetch_search
```

真实结构：

```text
data.data.cards[].mblog
```

这是 Real Probe 纠正过的结构。不能假设微博也有统一 `items/results`。

当前 Search 业务参数包括：

```text
keyword
page
search_type
可选 time_scope
```

Fixture：

[`tests/fixtures/providers/tikhub/weibo/search_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/weibo/search_page1.sanitized.json)

## 6.2 Detail

```text
GET /api/v1/weibo/app/fetch_status_detail
```

真实 item：

```text
data.detailInfo.status
```

Operation 当前会 fail closed：缺少这个路径时直接视为响应结构错误，而不是到处猜对象位置。

Fixture：

[`tests/fixtures/providers/tikhub/weibo/detail.sanitized.json`](../../tests/fixtures/providers/tikhub/weibo/detail.sanitized.json)

## 6.3 一级评论

```text
GET /api/v1/weibo/app/fetch_status_comments
```

真实列表：

```text
data.items[].data
```

真实分页 `max_id`：

```text
data.moreInfo.params.max_id
```

Fixture：

[`tests/fixtures/providers/tikhub/weibo/comments_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/weibo/comments_page1.sanitized.json)

## 6.4 二级评论

```text
GET /api/v1/weibo/web_v2/fetch_post_sub_comments
```

真实列表：

```text
data.data[]
```

`reply_comment` 可用于确认直接父评论；`rootid/rootidstr` 不应被误当原内容 ID。

Fixture：

[`tests/fixtures/providers/tikhub/weibo/sub_comments_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/weibo/sub_comments_page1.sanitized.json)

---

# 7. B站 Bilibili

Operation：

- [`backend/src/aima_ugc/adapters/providers/tikhub/operations/bilibili.py`](../../backend/src/aima_ugc/adapters/providers/tikhub/operations/bilibili.py)

Mapper：

- [`backend/src/aima_ugc/adapters/providers/tikhub/mappers/bilibili.py`](../../backend/src/aima_ugc/adapters/providers/tikhub/mappers/bilibili.py)

当前 App 是主链；Search/Detail/Comments/Reply 都存在显式 Web Candidate Builder，但不会自动切换。

## 7.1 Search

```text
GET /api/v1/bilibili/app/fetch_search_by_type
```

真实列表：

```text
data.data.items[]
```

当前正式 Search 只允许：

```text
search_type = video
```

当前样本观察到：

- `aid/bvid`；
- 标题；
- 摘要；
- UP 主；
- 播放量；
- 弹幕量。

Search Fixture 没有证明 `comment_count`，所以 Capability 不应仅凭平台常识宣称 Search 已观察评论数。

Fixture：

[`tests/fixtures/providers/tikhub/bilibili/search_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/bilibili/search_page1.sanitized.json)

## 7.2 Detail

```text
GET /api/v1/bilibili/app/fetch_one_video
```

真实 item：

```text
data.data
```

Fixture：

[`tests/fixtures/providers/tikhub/bilibili/detail.sanitized.json`](../../tests/fixtures/providers/tikhub/bilibili/detail.sanitized.json)

## 7.3 一级评论

```text
GET /api/v1/bilibili/app/fetch_video_comments
```

真实列表：

```text
data.data.replies[]
```

当前请求使用 `mode` 映射 `latest/hot`，首屏明确发送：

```text
next_offset = 0
```

真实下一页路径：

```text
data.data.cursor.pagination_reply.next_offset
```

Fixture：

[`tests/fixtures/providers/tikhub/bilibili/comments_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/bilibili/comments_page1.sanitized.json)

## 7.4 回复详情

```text
GET /api/v1/bilibili/app/fetch_reply_detail
```

真实回复树：

```text
data.data.root
data.data.root.replies[]
```

已观察：

```text
rpid
root
parent
ctime
like
rcount
```

Provider 数字 ID 最终转为 Canonical 字符串身份。

Fixture：

[`tests/fixtures/providers/tikhub/bilibili/replies_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/bilibili/replies_page1.sanitized.json)

---

# 8. 快手 Kuaishou

Operation：

- [`backend/src/aima_ugc/adapters/providers/tikhub/operations/kuaishou.py`](../../backend/src/aima_ugc/adapters/providers/tikhub/operations/kuaishou.py)

Mapper：

- [`backend/src/aima_ugc/adapters/providers/tikhub/mappers/kuaishou.py`](../../backend/src/aima_ugc/adapters/providers/tikhub/mappers/kuaishou.py)

当前代码事实非常明确：

```text
Search / Detail / Comments / Sub-comments
→ App 主链

Web Comments / Sub-comments
→ 已验证备用
→ 不自动 fallback
```

## 8.1 Search

当前主 Endpoint：

```text
GET /api/v1/kuaishou/app/search_video_v2
```

真实结构：

```text
data.mixFeeds[].feed
```

分页：

```text
data.pcursor
```

当前 `KuaishouSearchPagination` 对以下情况停止：

```text
response_data_unavailable
empty_page
cursor_unavailable
pagination_not_advanced
```

Fixture：

[`tests/fixtures/providers/tikhub/kuaishou/search_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/kuaishou/search_page1.sanitized.json)

代码里还有：

```text
/api/v1/kuaishou/app/search_comprehensive
```

Candidate，但它包含非视频对象，语义不等价，不能自动当成 `search_video_v2` 的备用。

## 8.2 Detail

```text
GET /api/v1/kuaishou/app/fetch_one_video
```

真实 item：

```text
data.photos[0]
```

Fixture：

[`tests/fixtures/providers/tikhub/kuaishou/detail.sanitized.json`](../../tests/fixtures/providers/tikhub/kuaishou/detail.sanitized.json)

## 8.3 当前 App 一级评论主链

```text
GET /api/v1/kuaishou/app/fetch_video_comment
```

真实列表：

```text
data.rootComments[]
```

真实根评论样本已证明存在：

```text
comment_id
content
likedCount
subCommentCount
displaySubCommentCount
user_id
timestamp
```

必须区分：

```text
subCommentCount
→ integer
→ 实际回复数量
→ 可映射 Canonical metrics.reply_count


displaySubCommentCount
→ boolean
→ 是否展示回复入口/数量类 UI 信号
→ 不能转成 0/1 当回复数
```

字段缺失时：

```text
reply_count = unknown/null
```

不能从 `subCommentsMap` 的当前数组长度猜“总回复数”。

当前同轮 endpoint ledger 曾观察到非零 `subCommentCount`，所以 `supports_reply_count=true` 有真实响应和 Mapper 证据。

App 一级响应可能同时包含：

```text
data.subCommentsMap.<root>.subComments[]
```

Real Probe 选二级评论候选时，不能简单取 `rootComments[0]`；应选择有：

```text
subCommentCount > 0
```

或其他明确回复存在证据的根评论。

正式 ledger：

[`tests/fixtures/providers/tikhub/endpoint_ledger/2026-08-16/kuaishou.sanitized.json`](../../tests/fixtures/providers/tikhub/endpoint_ledger/2026-08-16/kuaishou.sanitized.json)

## 8.4 当前 App 二级评论主链

```text
GET /api/v1/kuaishou/app/fetch_video_sub_comments
```

请求参数：

```text
photo_id
root_comment_id
pcursor
count
```

当前 `count` 领域校验：

```text
1..20
```

同样本 Real Probe：

```text
HTTP 200
data.subComments[] 非空
```

`root_comment_id` 来自请求上下文。如果响应没有可靠“直接父评论 ID”，Mapper 保留：

```text
parent_comment_id = null
```

不根据数组位置/用户名猜。

## 8.5 Web 评论链：验证过，但不是生产自动 fallback

备用 Endpoint：

```text
GET /api/v1/kuaishou/web/fetch_one_video_comment
GET /api/v1/kuaishou/web/fetch_one_video_sub_comment
```

2026-08-16 同样本 A/B 证明：

```text
Web 一级 HTTP 200 + 非空
Web 二级 HTTP 200 + data.subComments[] 非空
```

历史 Fixture：

- [`tests/fixtures/providers/tikhub/kuaishou/comments_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/kuaishou/comments_page1.sanitized.json)
- [`tests/fixtures/providers/tikhub/kuaishou/sub_comments_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/kuaishou/sub_comments_page1.sanitized.json)

Web 样本 `reply_to` 没有足够证据证明一定是另一个评论 ID，所以不猜成 `parent_comment_id`。

当前生产 `build_video_comments_request()` / `build_video_sub_comments_request()` 明确委托 App builder，不会自动调用 Web。

## 8.6 Web / App 同样本 A/B 证据

| 项目 | Web | App |
| --- | --- | --- |
| 一级评论 HTTP | 200 | 200 |
| 一级评论非空 | 是 | 是 |
| 二级评论 HTTP | 200 | 200 |
| `data.subComments[]` 非空 | 是 | 是 |
| 一级响应内嵌部分二级回复 | 样本有 `subCommentsMap` | 样本有 `subCommentsMap.<root>.subComments[]` |
| 2026-08-16 Probe endpoint_cost / 一级 | 0.002 USD | 0.001 USD |
| 2026-08-16 Probe endpoint_cost / 二级 | 0.010 USD | 0.001 USD |

上表价格只是历史 Probe 快照，**不是运行时价格配置**。

当前价格事实看：

- [`backend/src/aima_ugc/adapters/providers/tikhub/pricing.toml`](../../backend/src/aima_ugc/adapters/providers/tikhub/pricing.toml)

当前生产选型：

```text
App 一级/二级
→ 正式主链

Web 一级/二级
→ verified backup
→ 不自动 fallback
```

---

# 9. Canonical 统一规则

## 9.1 外部 ID 一律是字符串

业务身份：

```text
Content
= platform + external_content_id

Comment
= content_id + external_comment_id
```

即使 TikHub 返回 JSON number，Mapper 也转换为字符串。原因：

- 避免大整数溢出；
- 避免前导零丢失；
- 不让第三方 JSON 类型决定数据库业务身份。

精确评论 Contract：[`backend/src/aima_ugc/contracts/canonical/comment.py`](../../backend/src/aima_ugc/contracts/canonical/comment.py)。

## 9.2 评论树只写有证据的父子关系

根评论：

```text
root_comment_id = external_comment_id
parent_comment_id = null
```

二级/更深回复：

```text
root_comment_id = 已知根评论 ID
parent_comment_id = Provider 明确提供直接父评论 ID 时才写
```

没有证据就保留 `null`。

不能从：

- 用户名；
- 数组顺序；
- 文本 @；
- 语义不明确的 `reply_to`；

猜直接父评论。

## 9.3 未返回字段不是 0

不同 Operation 的字段密度不同。

例如 Search 没返回：

```text
comment_count
```

不能写：

```text
comment_count = 0
```

Mapper 只把本次真实看到的字段加入：

```text
observed_fields
```

Content Owner 之后使用 `field_observed_at` 做字段级 freshness。

---

# 10. 从一条 Fixture 追到数据库：实际学习方法

假设你要理解微博一级评论。

### 第一步：看真实 JSON

- [`tests/fixtures/providers/tikhub/weibo/comments_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/weibo/comments_page1.sanitized.json)

确认：

```text
data.items[].data
```

### 第二步：看 Operation

```text
operations/weibo.py
```

找到：

```python
build_status_comments_request(...)
extract_comment_items(...)
```

确认 Endpoint、参数、`max_id` 分页。

### 第三步：看 Mapper

- [`backend/src/aima_ugc/adapters/providers/tikhub/mappers/weibo.py`](../../backend/src/aima_ugc/adapters/providers/tikhub/mappers/weibo.py)

确认：

```text
评论 ID
作者
正文
published_at
like/reply metrics
root/parent
observed_fields
```

怎样进入 `CanonicalCommentV1`。

### 第四步：看 Contract

查看 [`backend/src/aima_ugc/contracts/canonical/comment.py`](../../backend/src/aima_ugc/contracts/canonical/comment.py)，确认系统允许保存哪些公共字段。

### 第五步：看 Ingestion

- [`backend/src/aima_ugc/modules/content/ingestion.py`](../../backend/src/aima_ugc/modules/content/ingestion.py)

再沿 PostgreSQL Owner 看：

```text
comments
comment_versions
comment_metric_observations
```

这样文档、Fixture、代码和数据库能够串成完整学习链。

---

# 11. Endpoint 或响应结构变化时怎么改

## 场景 A：Endpoint 变了，但响应结构没变

```text
operations/<platform>.py
→ Request builder test
→ Pricing/Capability（如果 endpoint 身份变化）
→ Real Probe
→ 本文 / 平台文档
```

一般不需要改 Canonical。

## 场景 B：JSON 路径变了

```text
先保存新的 Sanitized Fixture
→ Operation Extractor Test 先失败
→ 修改 extractor
→ Mapper Test
→ Canonical Contract Test
→ 必要的 PostgreSQL 纵切
```

## 场景 C：TikHub 新增了一个业务字段

```text
真实 Fixture 证明字段存在
→ 判断现有 Canonical 能否表达
→ 能表达：改 Mapper + observed_fields + tests
→ 不能表达：先做 Canonical Contract 设计
→ 再评估 Content Schema / API / Frontend
```

不要看到 Provider 多一个字段就直接加数据库列。

## 场景 D：想启用备用 API family

先看：

[`docs/appendix/03_TikHub多接口验证与备用策略.md`](03_TikHub多接口验证与备用策略.md)

当前备用接口必须显式选型，不能在 Transport 里偷偷自动 fallback。

---

# 12. Fixture 与 Real Probe 维护规则

Provider endpoint、版本或响应结构变化时：

1. 先用**生产 Operation**做显式、受限 Real Probe；
2. 不在普通 CI 自动产生真实付费请求；
3. 提交前完成 Secret/直接标识脱敏；
4. 保存/更新：

```text
tests/fixtures/providers/tikhub/<platform>/
```

5. 先让 Fixture 回归暴露结构漂移；
6. 再修改 Operation / Pagination / Mapper / Capability；
7. Fixture 继续通过 Canonical Contract；
8. 关键链路继续通过 PostgreSQL Ingestion 纵切；
9. 同步平台文档和本附录；
10. Pricing 变化更新运行时 Pricing，不用旧 Probe 价格覆盖配置。

禁止：

- 从 TikHub 官网示例手工拼“真实 Fixture”；
- 用历史聊天作为当前 JSON 结构事实；
- 为了让测试通过删掉真实 Fixture 字段；
- 在日志/Fixture 中提交真实 Secret。

---

# 13. 五个平台的人类导航

平台级当前说明：

- [`docs/collection/01_xiaohongshu.md`](../collection/01_xiaohongshu.md)
- [`docs/collection/02_douyin.md`](../collection/02_douyin.md)
- [`docs/collection/03_weibo.md`](../collection/03_weibo.md)
- [`docs/collection/04_bilibili.md`](../collection/04_bilibili.md)
- [`docs/collection/05_kuaishou.md`](../collection/05_kuaishou.md)

接口家族验证与备用边界：

- [`docs/appendix/03_TikHub多接口验证与备用策略.md`](03_TikHub多接口验证与备用策略.md)

真实 Probe / 选型历史台账：

- [`docs/appendix/04_TikHub接口选型与真实验证台账.md`](04_TikHub接口选型与真实验证台账.md)

采集总架构：

- [`docs/blueprint/02_采集系统与数据标准化.md`](../blueprint/02_采集系统与数据标准化.md)
- [`docs/blueprint/08_采集策略与平台能力.md`](../blueprint/08_采集策略与平台能力.md)

---

## Excel 补采 Lookup Identity

截至 2026-08-23 当前生产主链：小红书 Detail/Comments 使用 `note_id`；抖音 Detail/Comments 使用 `aweme_id`；微博普通帖子 Detail/Comments 使用数字 `status_id`，`tv/show` 视频链接必须先经视频详情取得真实 `idstr`，不能把 URL 中视频 ID 直接用于评论；B站 App Detail/Comments/Reply 使用 `av_id` 或 `bv_id` 二选一；快手 App Detail/Comments 使用 `photo_id`。

Excel 标准 URL 的 typed identity 必须与这些正式 Operation 参数一致。Comment ID/Root Comment ID 只来自评论响应，不从 Excel URL 推导。真实 Probe 必须复用生产 Operation/Transport/Extractor/Mapper，并限制请求数和费用；删除、私密、失效内容允许跳过候选，但不能把空响应伪装成接口成功。
