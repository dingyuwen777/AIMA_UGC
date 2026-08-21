# TikHub 五平台真实响应结构附录

> 实证日期：2026-08-15 至 2026-08-16  
> Provider：TikHub  
> Real Probe Base URL：`https://api.tikhub.io`  
> 搜索关键词：`爱玛`  
> 适用范围：五平台 Search / Detail / Comments / Sub-comments / Replies 的响应结构查询

本文从原 `docs/blueprint/10-TikHub真实响应结构附录.md` 迁移到 Appendix。**迁移只改变文档职责，不降低信息密度。** 长期 Provider-neutral 架构见 `docs/blueprint/02-采集系统与数据标准化.md` 与 `docs/blueprint/08-采集策略与平台能力.md`；本文继续保留真实 Endpoint、JSON 路径、Fixture、评论树映射和实证边界。

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
| 快手 | 非空 | 非空 | **App 主链非空；Web 备用同样本非空** | **App 主链与 Web 备用同样本均实测非空** | 可表达；App 当前正式主链 |

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

### 8.3 当前 App 一级评论主链

正式 Endpoint：`GET /api/v1/kuaishou/app/fetch_video_comment`

主要列表路径：

```text
data.rootComments[]
```

当前 App 根评论真实响应已经证明存在：

```text
comment_id                  # 评论 ID
content                     # 文本
likedCount                  # 点赞数
subCommentCount             # integer，实际回复数量
displaySubCommentCount      # boolean，回复数/入口显示标志
user_id                     # 用户 ID
timestamp                   # 发布时间
```

这里必须区分：

- `subCommentCount` 是实际回复数量，生产 Mapper 在字段存在时映射为 `CanonicalCommentV1.metrics.reply_count` 并声明 `metrics.reply_count` 已观察；
- `displaySubCommentCount` 是布尔显示标志，不能转换成 `0/1` 充当回复数；
- 字段缺失时 `reply_count` 保持未知，不从 `subCommentsMap` 长度猜总数。

真实 App endpoint ledger 中同一轮样本已经出现 `subCommentCount=25/2/11` 等非零值，因此 `supports_reply_count=true` 有真实 Provider 证据和生产 Mapper 双重支撑。

App 一级响应还可能包含：

```text
data.subCommentsMap.<root>.subComments[]
```

不能仅取 `rootComments[0]` 就推断该根评论有二级回复。Real Probe 应优先选择 `subCommentCount > 0`，或在仅需发现候选时参考 `displaySubCommentCount == true` / 非空 `subCommentsMap`。

正式结构证据：[`endpoint_ledger/2026-08-16/kuaishou.sanitized.json`](../../tests/fixtures/providers/tikhub/endpoint_ledger/2026-08-16/kuaishou.sanitized.json)

### 8.4 当前 App 二级评论主链

正式 Endpoint：`GET /api/v1/kuaishou/app/fetch_video_sub_comments`

请求使用：

```text
photo_id
root_comment_id
pcursor
count
```

2026-08-16 同样本 A/B Probe 已确认 App endpoint 对明确有回复的根评论返回：

```text
HTTP 200
data.subComments[] 非空
```

`root_comment_id` 由请求上下文明确提供；如果响应没有可靠直接父评论 ID，Mapper 保留 `parent_comment_id = null`，不根据数组位置、用户名或语义不明字段猜测。

正式结构证据同样保存在：[`endpoint_ledger/2026-08-16/kuaishou.sanitized.json`](../../tests/fixtures/providers/tikhub/endpoint_ledger/2026-08-16/kuaishou.sanitized.json)

### 8.5 Web 评论链：已验证备用，不自动 fallback

Web 备用 Endpoint：

```text
GET /api/v1/kuaishou/web/fetch_one_video_comment
GET /api/v1/kuaishou/web/fetch_one_video_sub_comment
```

2026-08-16 的同样本 A/B Probe 已纠正早先一次空页结论：选择具有明确回复数证据的真实根评论后，Web 一级和二级同样返回 HTTP 200 且非空。Web 二级主要路径为：

```text
data.subComments[]
```

历史 Web 脱敏 Fixture 继续保留：

- [`kuaishou/comments_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/kuaishou/comments_page1.sanitized.json)
- [`kuaishou/sub_comments_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/kuaishou/sub_comments_page1.sanitized.json)

Web 样本中的 `reply_to` 当前没有足够证据证明一定是另一个评论 ID，所以 Mapper 不把它猜成 `parent_comment_id`；`root_comment_id` 由请求上下文明确提供。

Web 已验证可用，但**不是当前默认 Capability 主链，也没有 App 失败后的自动 Web fallback**。如未来回切 Web，必须通过显式 Operation/Capability/Pricing/测试/文档变更完成。

### 8.6 Web vs App 评论 API 同样本 A/B 实证

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

2026-08-16 的 Operation 选型已经批准并在当前机器实现中落地：**App 一级/二级为正式主链，Web 为 verified backup，不做自动 fallback。** 因此本附录不能再把 Web 写成“当前主链”或把 App 切换写成待批准建议。

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

## 11. 从这篇文档追到当前代码

如果目标是“读懂实现”，不要只停在 Endpoint 表。按下面顺序往代码走：

### 11.1 先找某个平台怎样构造请求

```text
backend/src/aima_ugc/adapters/providers/tikhub/operations/xiaohongshu.py
backend/src/aima_ugc/adapters/providers/tikhub/operations/douyin.py
backend/src/aima_ugc/adapters/providers/tikhub/operations/weibo.py
backend/src/aima_ugc/adapters/providers/tikhub/operations/bilibili.py
backend/src/aima_ugc/adapters/providers/tikhub/operations/kuaishou.py
```

这些文件回答：

```text
业务 operation 名叫什么？
实际 HTTP method / endpoint 是什么？
业务参数怎样变成 Provider 参数？
分页状态怎样推进？
响应里的业务 item 怎样被 extractor 找出来？
```

不要从本文复制 Endpoint 去另写 HTTP 请求；生产事实仍以这些 Operation 为准。

### 11.2 再看 Provider JSON 怎样变成 Canonical

```text
backend/src/aima_ugc/adapters/providers/tikhub/mappers/xiaohongshu.py
backend/src/aima_ugc/adapters/providers/tikhub/mappers/douyin.py
backend/src/aima_ugc/adapters/providers/tikhub/mappers/weibo.py
backend/src/aima_ugc/adapters/providers/tikhub/mappers/bilibili.py
backend/src/aima_ugc/adapters/providers/tikhub/mappers/kuaishou.py
backend/src/aima_ugc/adapters/providers/tikhub/mappers/common.py
```

这里回答：

```text
真实 JSON 哪个字段 → Canonical 哪个字段？
数字 ID 为什么转字符串？
缺字段为什么保持 unknown/null 而不是写 0？
评论 root / parent 怎样确定？
observed_fields 怎样生成？
```

### 11.3 再看整个 TikHub Runtime 怎样把 Operation 串起来

```text
backend/src/aima_ugc/adapters/providers/tikhub/runtime.py
backend/src/aima_ugc/adapters/providers/tikhub/capabilities.py
backend/src/aima_ugc/adapters/providers/tikhub/transport.py
```

- `runtime.py`：生产 TikHub 能力怎样被装配并执行；
- `capabilities.py`：Provider + Platform 当前允许哪些业务 Operation；
- `transport.py`：真正的 HTTP 发送边界、Origin/Secret/错误处理；
- `pricing.py` + `pricing.toml`：当前 endpoint Pricing 的运行时事实，不用本文中的历史 Probe 价格代替。

### 11.4 最后用 Fixture 和测试验证理解是否正确

```text
tests/fixtures/providers/tikhub/
tests/unit/collection/
tests/contracts/
```

例如你想确认“微博一级评论为什么从 `data.items[].data` 取”：

```text
本文找到真实路径
→ 打开 tests/fixtures/providers/tikhub/weibo/comments_page1.sanitized.json
→ 打开 operations/weibo.py 看 extractor
→ 打开 mappers/weibo.py 看字段映射
→ 跑对应 unit/contract test
```

这个顺序能把“文档说明”落回真实代码和可重复验证证据。
