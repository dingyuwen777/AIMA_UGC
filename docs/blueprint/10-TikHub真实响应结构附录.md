# TikHub 五平台真实响应结构附录

> 实证日期：2026-08-15 至 2026-08-16  
> Provider：TikHub  
> Real Probe Base URL：`https://api.tikhub.io`  
> 搜索关键词：`爱玛`  
> 适用范围：Stage 7 五平台 Search / Detail / Comments / Sub-comments / Replies 的响应结构查询

## 1. 本附录的用途

本文是五个平台 TikHub **真实响应结构的人类查询入口**。它解决开发时频繁需要回答的几类问题：

- 某个平台实际返回的帖子/视频列表在哪个 JSON 路径；
- 内容 ID、评论 ID、分页游标、评论树字段从哪里取得；
- 某个字段是 TikHub 当前真实返回，还是代码自己猜出来的；
- Mapper 为什么把某个 Provider 字段映射到某个 Canonical 字段；
- 某个 Capability 是否已经有真实非空响应证据。

仓库不会保存未经脱敏的真实用户数据。本文中的“真实原始响应”指：**由真实 TikHub 请求取得、在提交仓库前完成 Secret/直接标识脱敏，同时保留 JSON 层级、字段名、数据类型和 Mapper 所需代表值的 Sanitized Fixture**。

完整机器事实位于：

```text
tests/fixtures/providers/tikhub/
```

本文不建立第二套 Provider Schema。若本文摘要与 Fixture、Operation、Mapper 或测试冲突，以当前 Fixture + 生产代码 + 测试为准，并在同一任务修正文档。

## 2. 真实 Probe 边界

本轮验证采用最小结构采样，不进行全量爬取：

```text
Search: 每个平台最多 1 页
Detail: 从 Search 结果选 1 条可用内容，最多 1 次；XHS 额外分别验证图文/视频
Comments: 每个平台最多 1 页
Sub-comments / Replies: 找到有回复的根评论后最多 1 页
```

跨接口身份链在脱敏前使用真实 Provider ID 串联：

```text
Search content_id
→ Detail / Comments
→ root_comment_id
→ Sub-comments / Replies
```

因此 Fixture 用于结构回归，Real Probe 用于证明跨接口真实 ID 可以工作。Fixture 中的脱敏 ID 不要求跨文件保持真实原值。

## 3. 五平台证据总览

| 平台 | Search | Detail | 一级评论 | 二级评论/回复 | 当前 Canonical 结论 |
| --- | --- | --- | --- | --- | --- |
| 小红书 | 非空 | 图文、视频非空 | 非空 | 非空 | `CanonicalContentV1` / `CanonicalCommentV1` 可表达 |
| 抖音 | 非空 | 非空 | 非空 | 非空 | 可表达 |
| 微博 | 非空 | 非空 | 非空 | 非空 | 可表达 |
| B站 | 非空 | 非空 | 非空 | 非空 | 可表达 |
| 快手 | 非空 | 非空 | 非空 | **Web 与 App 同样本均实测非空** | 可表达；Web 当前主链可用 |

真实 Fixture 已通过生产 Extractor / Mapper → Canonical → Ingestion → PostgreSQL 18 纵切验证。当前样本没有证明需要把 Provider 私有字段加入 Canonical V1 公共 Contract。

## 4. 小红书 Xiaohongshu

### 4.1 Search

Endpoint：

```text
GET /api/v1/xiaohongshu/app_v2/search_notes
```

主要真实结构：

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

业务 item 容器：`data.data.items[]`。生产 extractor 再提取其中可映射的笔记事实。

完整脱敏响应：[`xhs/search_notes_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/xhs/search_notes_page1.sanitized.json)

### 4.2 Detail

图文：`GET /api/v1/xiaohongshu/app_v2/get_image_note_detail`  
视频：`GET /api/v1/xiaohongshu/app_v2/get_video_note_detail`

已观察 item 路径：

```text
图文: data.data[0].note_list[0]
视频: data.data[0]
```

完整脱敏响应：

- [`xhs/image_detail.sanitized.json`](../../tests/fixtures/providers/tikhub/xhs/image_detail.sanitized.json)
- [`xhs/video_detail.sanitized.json`](../../tests/fixtures/providers/tikhub/xhs/video_detail.sanitized.json)

### 4.3 一级评论

Endpoint：`GET /api/v1/xiaohongshu/app_v2/get_note_comments`

主要列表路径：

```text
data.data.comments[]
```

真实根评论已经观察到 `sub_comments[]`、点赞和回复数，可形成：

```text
一级评论:
root_comment_id = external_comment_id
parent_comment_id = null
```

完整脱敏响应：[`xhs/comments_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/xhs/comments_page1.sanitized.json)

### 4.4 二级评论

Endpoint：`GET /api/v1/xiaohongshu/app_v2/get_note_sub_comments`

主要列表路径：

```text
data.data.comments[]
```

完整脱敏响应：[`xhs/sub_comments_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/xhs/sub_comments_page1.sanitized.json)

## 5. 抖音 Douyin

### 5.1 Search

Endpoint：

```text
POST /api/v1/douyin/search/fetch_video_search_v2
```

主要真实结构：

```text
data.business_data[]
```

业务 item 中包含真实 `aweme_info` 内容事实。分页状态来自 TikHub Search V2 的业务配置/next-page 响应，Provider 私有 `cursor/search_id/backtrace` 不进入 Canonical。

完整脱敏响应：[`douyin/search_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/douyin/search_page1.sanitized.json)

### 5.2 Detail

Endpoint：`GET /api/v1/douyin/app/v3/fetch_one_video_v3`

主要 item 路径：

```text
data.aweme_detail
```

已真实观察播放、下载、转发、视频时长等字段。

完整脱敏响应：[`douyin/detail.sanitized.json`](../../tests/fixtures/providers/tikhub/douyin/detail.sanitized.json)

### 5.3 一级评论

Endpoint：`GET /api/v1/douyin/app/v3/fetch_video_comments`

主要列表路径：

```text
data.comments[]
```

已真实观察评论 ID、用户、点赞数、回复数等。

完整脱敏响应：[`douyin/comments_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/douyin/comments_page1.sanitized.json)

### 5.4 评论回复

Endpoint：`GET /api/v1/douyin/app/v3/fetch_video_comment_replies`

主要列表路径：

```text
data.comments[]
```

真实响应提供 `root_comment_id`、`reply_id` / `reply_to_reply_id` 等回复关系事实。Mapper 在 Provider 明确提供直接父回复时使用该字段，不靠文本或数组位置猜父子关系。

完整脱敏响应：[`douyin/replies_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/douyin/replies_page1.sanitized.json)

## 6. 微博 Weibo

### 6.1 Search

Endpoint：`GET /api/v1/weibo/web/fetch_search`

主要真实结构：

```text
data.data.cards[].mblog
```

这是 Real Probe 纠正过的结构，不能假设微博 Search 与其他平台共享 `items/results` 形式。

完整脱敏响应：[`weibo/search_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/weibo/search_page1.sanitized.json)

### 6.2 Detail

Endpoint：`GET /api/v1/weibo/app/fetch_status_detail`

主要 item 路径：

```text
data.detailInfo.status
```

完整脱敏响应：[`weibo/detail.sanitized.json`](../../tests/fixtures/providers/tikhub/weibo/detail.sanitized.json)

### 6.3 一级评论

Endpoint：`GET /api/v1/weibo/app/fetch_status_comments`

主要列表路径：

```text
data.items[].data
```

分页的真实 `max_id` 位于响应 `data.moreInfo.params.max_id`。

完整脱敏响应：[`weibo/comments_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/weibo/comments_page1.sanitized.json)

### 6.4 二级评论

Endpoint：`GET /api/v1/weibo/web_v2/fetch_post_sub_comments`

主要列表路径：

```text
data.data[]
```

真实响应中的 `reply_comment` 可用于确认直接父评论；`rootid/rootidstr` 不应被误当原内容 ID。

完整脱敏响应：[`weibo/sub_comments_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/weibo/sub_comments_page1.sanitized.json)

## 7. B站 Bilibili

### 7.1 Search

Endpoint：`GET /api/v1/bilibili/app/fetch_search_by_type`

主要列表路径：

```text
data.data.items[]
```

真实 Search 已观察 `aid/bvid`、标题、正文摘要、UP 主、播放量、弹幕量等；当前 Search Fixture 没有证明 `comment_count`，因此 Search Capability 不宣称 `observes_comment_count=True`。

完整脱敏响应：[`bilibili/search_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/bilibili/search_page1.sanitized.json)

### 7.2 Detail

Endpoint：`GET /api/v1/bilibili/app/fetch_one_video`

主要 item 路径：

```text
data.data
```

已真实观察 `aid/bvid`、评论数、收藏、投币、封面和时长等。

完整脱敏响应：[`bilibili/detail.sanitized.json`](../../tests/fixtures/providers/tikhub/bilibili/detail.sanitized.json)

### 7.3 一级评论

Endpoint：`GET /api/v1/bilibili/app/fetch_video_comments`

主要列表路径：

```text
data.data.replies[]
```

分页真实路径包含 `data.data.cursor.pagination_reply.next_offset`。

完整脱敏响应：[`bilibili/comments_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/bilibili/comments_page1.sanitized.json)

### 7.4 回复详情

Endpoint：`GET /api/v1/bilibili/app/fetch_reply_detail`

真实回复树路径：

```text
data.data.root
data.data.root.replies[]
```

已观察 `rpid/root/parent/ctime/like/rcount`，因此可以把 Provider 数字/字符串 ID 归一化为 Canonical 字符串评论树。

完整脱敏响应：[`bilibili/replies_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/bilibili/replies_page1.sanitized.json)

## 8. 快手 Kuaishou

### 8.1 Search

当前主 Endpoint：`GET /api/v1/kuaishou/app/search_video_v2`

主要真实结构：

```text
data.mixFeeds[].feed
```

分页游标：`data.pcursor`。

完整脱敏响应：[`kuaishou/search_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/kuaishou/search_page1.sanitized.json)

### 8.2 Detail

Endpoint：`GET /api/v1/kuaishou/app/fetch_one_video`

主要 item 路径：

```text
data.photos[0]
```

完整脱敏响应：[`kuaishou/detail.sanitized.json`](../../tests/fixtures/providers/tikhub/kuaishou/detail.sanitized.json)

### 8.3 当前 Web 一级评论主链

Endpoint：`GET /api/v1/kuaishou/web/fetch_one_video_comment`

主要列表路径：

```text
data.rootComments[]
```

真实响应还存在 `subCommentsMap`。不能仅取 `rootComments[0]` 就推断该根评论有二级回复；Real Probe 应优先选择 `displaySubCommentCount/subCommentCount` 等正向回复证据存在的 root。

完整脱敏响应：[`kuaishou/comments_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/kuaishou/comments_page1.sanitized.json)

### 8.4 当前 Web 二级评论主链

Endpoint：`GET /api/v1/kuaishou/web/fetch_one_video_sub_comment`

2026-08-16 的同样本 A/B Probe 已纠正早先一次空页结论：选择具有明确回复数证据的真实根评论后，Web endpoint 返回：

```json
{
  "code": 200,
  "data": {
    "pcursor": "...",
    "subComments": [
      {
        "comment_id": 100002,
        "photo_id": 100001,
        "user_id": 100003,
        "content": "<redacted-text>",
        "likedCount": 15,
        "reply_to": 473331688
      }
    ]
  }
}
```

即：**Web 二级评论已真实非空验证，不应再写成“TikHub 不支持快手二级评论”。**

`reply_to` 的业务含义当前没有足够证据证明一定是另一个评论 ID，所以 Mapper 不把它猜成 `parent_comment_id`；`root_comment_id` 由请求上下文明确提供。

完整脱敏响应：[`kuaishou/sub_comments_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/kuaishou/sub_comments_page1.sanitized.json)

### 8.5 Web vs App 评论 API 同样本 A/B 实证

TikHub 当前还提供：

```text
GET /api/v1/kuaishou/app/fetch_video_comment
GET /api/v1/kuaishou/app/fetch_video_sub_comments
```

2026-08-16 使用同一个 Search 命中的真实作品、同一个具有 `displaySubCommentCount/subCommentCount` 正向回复证据的根评论做最小对照：

| 项目 | Web | App |
| --- | --- | --- |
| 一级评论 HTTP | 200 | 200 |
| 一级评论非空 | 是 | 是 |
| 二级评论 HTTP | 200 | 200 |
| `data.subComments[]` 非空 | 是 | 是 |
| 一级响应内嵌部分二级回复 | 当前样本有 `subCommentsMap` | 当前样本有大量 `subCommentsMap.<root>.subComments[]` |
| Probe 时 endpoint_cost / 一级 | 0.002 USD | 0.001 USD |
| Probe 时 endpoint_cost / 二级 | 0.010 USD | 0.001 USD |

价格只表示 **2026-08-16 Real Probe 的 endpoint-info 快照**，不是运行时永久常量。生产发送仍以版本化 Pricing + endpoint-level verified 事实为准。

当前正式主 Operation Matrix 仍使用 Web 评论链，直到 Provider Operation 选型决策被明确批准。不得因为 App 本次更便宜就在运行时静默 Web→App fallback。

**基于当前证据的推荐：后续将快手评论主链切到 App，Web 保留为已验证的备选事实但不做自动 fallback。** 原因是同样本结构可用，而当前 App 一级/二级评论 endpoint 单价都更低，并且一级响应可携带部分二级回复，理论上可减少后续请求。正式切换前仍需用户/业务 Owner 批准并同步 Operation Matrix、Pricing、Runtime、Fixture/测试和 Change。

## 9. Canonical 统一规则

### 9.1 外部 ID

所有 Provider 外部 ID 最终统一保存为字符串：

```text
platform + external_content_id
platform + external_comment_id
```

即使 TikHub 在快手/B站响应中返回 JSON number，Mapper 也转换为字符串，不让数据库主身份受第三方 JSON 数字类型影响。

### 9.2 评论树

```text
一级评论:
root_comment_id = external_comment_id
parent_comment_id = null

二级/更深回复:
root_comment_id = 已知根评论 ID
parent_comment_id = 仅在 Provider 明确给出“直接父评论 ID”时写入
```

缺乏直接父评论证据时保留 `parent_comment_id = null`，不能从用户名、数组位置、`reply_to` 等语义不明确字段猜测。

### 9.3 稀疏观察字段

TikHub 不同 Operation 返回字段集合不同。Mapper 只把本次真实观察到的字段加入 `observed_fields`，未返回字段不是 `0/false/空字符串` 的同义词。

## 10. Fixture 与文档维护规则

Provider endpoint、版本或响应结构变化时：

1. 先用生产 Operation 做显式、受限的 Real Probe；
2. 在提交前完成 Secret/直接标识脱敏；
3. 保存/更新 `tests/fixtures/providers/tikhub/<platform>/`；
4. 先让真实 Fixture 回归暴露结构漂移；
5. 再修改 Operation / Pagination / Mapper / Capability；
6. 真实 Fixture 必须继续通过 Canonical Contract 和必要的 PostgreSQL Ingestion 纵切；
7. 同步本文的路径/证据状态；
8. 价格变化只更新 Pricing 事实，不把本文 Probe 快照当运行时价格源。

禁止从 TikHub 文档示例、历史聊天或旧接口响应人工拼一个“真实 Fixture”。
