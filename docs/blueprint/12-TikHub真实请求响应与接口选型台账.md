# TikHub 五平台真实请求、响应与接口选型台账

> 状态：Stage 7 长期核查台账  
> 首次实证：2026-08-15 至 2026-08-16  
> Provider：TikHub  
> Real Probe Base URL：`https://api.tikhub.io`  
> 搜索关键词：`爱玛`

## 1. 本文解决什么问题

本文用于长期回答四类问题：

1. AIMA_UGC 对五个平台实际调用了哪个 TikHub endpoint、用什么 Method 和业务参数；
2. TikHub 的真实响应字段、列表路径、分页字段在哪里；
3. 为什么当前生产主链选择这组接口，而不是同平台的 App/Web/V1/V2/V3 候选；
4. 哪些候选已经做过真实 A/B、哪些只是候选、哪些不能视为等价备用。

本文是**人类核查入口**，不建立第二套 Provider Schema。完整真实响应仍以仓库中的 Sanitized Fixture 为机器事实：

```text
tests/fixtures/providers/tikhub/
```

“真实请求/响应”均指：真实 TikHub 调用产生；提交仓库前移除 API Key、Authorization、真实账号/内容 ID、正文、媒体资源 URL 等直接标识，但保留 Method、endpoint、业务参数语义、JSON 字段名、层级、容器类型、数值/布尔类型以及 Mapper/分页所需代表值。

## 2. 最新 Real Probe 证据边界

### 2.1 五平台正式主链

2026-08-16 GitHub-hosted Ubuntu Runner 多次使用生产 `Operation builder + TikHubOperationProbe + TikHubHttpTransport + Pricing` 执行：

```text
Search
→ 使用 Search 返回的真实内容 ID
→ Detail
→ 一级 Comments
→ 选择真实有回复的根评论
→ Sub-comments / Replies
```

最近一次完整业务步骤中五个平台主链全部执行成功；Probe 使用生产 Transport 的 45 秒超时且没有隐藏重试。公开 Evidence 导出在后续严格去标识化门禁被阻止，因此**不得把未上传的 Runner 临时文件当成仓库 Fixture**。当前长期响应样本仍使用此前已经合法脱敏并经过 Mapper → Canonical → PostgreSQL 18 纵切验证的 Fixture。

这一区分很重要：

```text
“当前 endpoint 实际可调用”
≠
“本次 Runner 临时响应已经允许公开提交”
```

### 2.2 API family A/B

2026-08-16 的受限 A/B Runner `31938229417` 实际执行 10 个业务请求，预计业务费用 0.046 USD，无隐藏重试。已得到：

- 抖音 Video Search V2 vs V1；
- 微博 Web Search vs App Search All；
- B站 App Search vs Web Search；
- 快手 App Video Search V2 vs App Comprehensive；
- 微博 App Comments vs Web V2 Comments。

该次原始 Artifact 之后又按 Endpoint Ledger 更严格的隐私规则做二次审查；包含资源域名的原始 Artifact 不直接进入仓库。本文记录其 HTTP、价格、数量与稳定 ID 集合比较结果。

## 3. 统一选型原则

主链优先级按以下事实综合决定，而不是只看接口版本号：

1. 当前 endpoint 实际可调用；
2. 稳定内容 ID / 评论 ID 能跨 Search → Detail → Comments → Replies 串联；
3. 响应字段足以映射现有 `CanonicalContentV1 / CanonicalCommentV1`；
4. 分页状态可明确解析，不猜 Provider 私有 sentinel；
5. endpoint-level Pricing 已核验，Budget 可在发送前 fail closed；
6. 当前生产 Operation/Mapper/Fixture/测试覆盖更完整；
7. 同等可用时优先请求更少、价格更低、同一 API family 更一致的链路；
8. 备用接口即使实测成功，也**不自动 fallback**。自动 fallback 会新增一次付费 Attempt，并改变 Budget、Raw lineage、失败语义和审计，因此必须单独设计。

---

# 4. 小红书 Xiaohongshu

## 4.1 正式主链

```text
Search      App V2 /api/v1/xiaohongshu/app_v2/search_notes
ImageDetail App V2 /api/v1/xiaohongshu/app_v2/get_image_note_detail
VideoDetail App V2 /api/v1/xiaohongshu/app_v2/get_video_note_detail
Comments    App V2 /api/v1/xiaohongshu/app_v2/get_note_comments
SubComments App V2 /api/v1/xiaohongshu/app_v2/get_note_sub_comments
```

当前五个 endpoint 的已核验基础单价均为 `0.010 USD/request`；运行时仍以版本化 `pricing.toml` 为事实源，不以本文价格作为 Dispatch 配置。

## 4.2 真实 Search 请求

本轮 Endpoint Ledger 为了提高后续评论非空概率，图文发现实际使用：

```http
GET /api/v1/xiaohongshu/app_v2/search_notes
```

```json
{
  "keyword": "爱玛",
  "page": 1,
  "sort_type": "comment_descending",
  "note_type": "普通笔记",
  "time_filter": "不限",
  "source": "explore_feed"
}
```

支持视频详情的第二个最小 Search 使用：

```json
{
  "keyword": "爱玛",
  "page": 1,
  "sort_type": "general",
  "note_type": "视频笔记",
  "time_filter": "不限",
  "source": "explore_feed"
}
```

真实响应主要业务路径：`data.data.items[]`；完整脱敏响应：

- [`xhs/search_notes_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/xhs/search_notes_page1.sanitized.json)

## 4.3 真实 Detail 请求/响应

图文：

```http
GET /api/v1/xiaohongshu/app_v2/get_image_note_detail?note_id=<sanitized-note-id>
```

真实主要路径：`data.data[0].note_list[0]`。  
完整响应：[`xhs/image_detail.sanitized.json`](../../tests/fixtures/providers/tikhub/xhs/image_detail.sanitized.json)

视频：

```http
GET /api/v1/xiaohongshu/app_v2/get_video_note_detail?note_id=<sanitized-note-id>
```

真实主要路径：`data.data[0]`。  
完整响应：[`xhs/video_detail.sanitized.json`](../../tests/fixtures/providers/tikhub/xhs/video_detail.sanitized.json)

## 4.4 真实一级/二级评论请求/响应

一级：

```http
GET /api/v1/xiaohongshu/app_v2/get_note_comments
```

```json
{
  "note_id": "<sanitized-note-id>",
  "cursor": "",
  "index": 0,
  "pageArea": "UNFOLDED",
  "sort_strategy": "latest_v2"
}
```

业务列表：`data.data.comments[]`。  
完整响应：[`xhs/comments_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/xhs/comments_page1.sanitized.json)

二级：

```http
GET /api/v1/xiaohongshu/app_v2/get_note_sub_comments
```

```json
{
  "note_id": "<sanitized-note-id>",
  "comment_id": "<sanitized-root-comment-id>",
  "cursor": "",
  "index": 1
}
```

业务列表：`data.data.comments[]`。  
完整响应：[`xhs/sub_comments_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/xhs/sub_comments_page1.sanitized.json)

## 4.5 为什么选择 App V2

- Search、图文/视频 Detail、一级评论、二级评论均已有真实非空结构；
- 同一 family 内可串联稳定 note/comment ID；
- Search 提供排序、时间和内容类型过滤，适合舆情发现；
- 现有 XHS Mapper、Raw Replay、Canonical/Ingestion 和 Stage 6 回归最成熟；
- App/Web 其他 family 虽然官方存在，但当前尚未完成同输入真实 A/B，因此继续作为候选，不因“版本名字相似”自动降级/切换。

---

# 5. 抖音 Douyin

## 5.1 正式主链

```text
Search   /api/v1/douyin/search/fetch_video_search_v2
Detail   /api/v1/douyin/app/v3/fetch_one_video_v3
Comments /api/v1/douyin/app/v3/fetch_video_comments
Replies  /api/v1/douyin/app/v3/fetch_video_comment_replies
```

已核验基础单价：Search `0.010 USD`；其余三个 App V3 endpoint 均 `0.001 USD`。

## 5.2 真实 Search 请求/响应

```http
POST /api/v1/douyin/search/fetch_video_search_v2
```

Endpoint Ledger 默认业务输入：

```json
{
  "keyword": "爱玛",
  "cursor": 0,
  "sort_type": "0",
  "publish_time": "0",
  "filter_duration": "0",
  "content_type": "0",
  "search_id": "",
  "backtrace": ""
}
```

真实业务列表：`data.business_data[]`，内容事实位于其 `data.aweme_info`。  
完整响应：[`douyin/search_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/douyin/search_page1.sanitized.json)

## 5.3 Detail / Comments / Replies

Detail：

```http
GET /api/v1/douyin/app/v3/fetch_one_video_v3?aweme_id=<sanitized-aweme-id>
```

主要路径：`data.aweme_detail`。  
完整响应：[`douyin/detail.sanitized.json`](../../tests/fixtures/providers/tikhub/douyin/detail.sanitized.json)

一级评论：

```http
GET /api/v1/douyin/app/v3/fetch_video_comments?aweme_id=<sanitized-aweme-id>&cursor=0
```

列表：`data.comments[]`。  
完整响应：[`douyin/comments_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/douyin/comments_page1.sanitized.json)

回复：

```http
GET /api/v1/douyin/app/v3/fetch_video_comment_replies?item_id=<sanitized-aweme-id>&comment_id=<sanitized-comment-id>&cursor=0
```

列表：`data.comments[]`；真实响应已观察 `root_comment_id`、`reply_id/reply_to_reply_id`。  
完整响应：[`douyin/replies_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/douyin/replies_page1.sanitized.json)

## 5.4 Video Search V2 vs V1 真实 A/B

同关键词 `爱玛`、最新、7 天、视频条件下：

| 指标 | V2 主接口 | V1 候选 |
| --- | ---: | ---: |
| HTTP | 200 | 200 |
| 单价 | 0.010 | 0.010 |
| 首屏稳定内容 ID 数 | 7 | 7 |
| 共享 ID | 7 | 7 |
| 仅一侧 ID | 0 | 0 |
| Jaccard | 1.0 | 1.0 |
| 本次唯一内容集合 | 完全相同 | 完全相同 |

但两套 Raw shape 差异很大，字段路径 Jaccard 约 `0.0156`。因此本次实验只证明**相同输入下首屏内容集合一致且两边可调用**，不证明两套响应可直接共用当前 V2 extractor/Mapper，也不证明全量分页永远一致。

当前状态：V1 保持显式候选；完成候选 Extractor/Mapper 兼容回归后才能升级为 `verified_backup`。

## 5.5 为什么主链仍选 V2 + App V3

- V2 是当前生产 Search 的事实源，分页 `cursor/search_id/backtrace` 已按真实响应实现；
- App V3 Detail/Comments/Replies 已真实非空并能稳定归一化评论树；
- 非 Search endpoint 成本低；
- V1 虽本次首屏 7/7 一致，但 Raw shape 明显不同，直接切换会破坏当前 extractor 事实，故不为“看起来结果一样”而静默切换。

---

# 6. 微博 Weibo

## 6.1 正式主链

```text
Search      Web    /api/v1/weibo/web/fetch_search
Detail      App    /api/v1/weibo/app/fetch_status_detail
Comments    App    /api/v1/weibo/app/fetch_status_comments
SubComments Web V2 /api/v1/weibo/web_v2/fetch_post_sub_comments
```

四个主 endpoint 当前已核验基础单价均为 `0.001 USD/request`。

## 6.2 真实 Search

Endpoint Ledger 为了找到更适合评论结构验证的内容，实际使用 `hot`：

```http
GET /api/v1/weibo/web/fetch_search
```

```json
{
  "keyword": "爱玛",
  "page": 1,
  "search_type": 60
}
```

业务路径：`data.data.cards[].mblog`。  
完整响应：[`weibo/search_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/weibo/search_page1.sanitized.json)

生产 Operation 同时支持 `latest=61` 等已验证参数；Probe 使用 `hot` 只是为提高评论非空概率，不改变正式 Search endpoint 选型。

## 6.3 Detail / Comments / SubComments

Detail：

```http
GET /api/v1/weibo/app/fetch_status_detail?status_id=<sanitized-status-id>
```

主要路径：`data.detailInfo.status`。  
完整响应：[`weibo/detail.sanitized.json`](../../tests/fixtures/providers/tikhub/weibo/detail.sanitized.json)

一级评论：

```http
GET /api/v1/weibo/app/fetch_status_comments?status_id=<sanitized-status-id>&sort_type=1
```

列表：`data.items[].data`；分页 `max_id` 来自 `data.moreInfo.params.max_id`。  
完整响应：[`weibo/comments_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/weibo/comments_page1.sanitized.json)

二级评论：

```http
GET /api/v1/weibo/web_v2/fetch_post_sub_comments?id=<sanitized-root-comment-id>&max_id=
```

列表：`data.data[]`；`reply_comment` 可证明直接父评论。  
完整响应：[`weibo/sub_comments_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/weibo/sub_comments_page1.sanitized.json)

## 6.4 Web Search vs App Search All 真实 A/B

同关键词、可对齐的搜索类型下：

| 指标 | Web 主接口 | App 候选 |
| --- | ---: | ---: |
| HTTP | 200 | 200 |
| 单价 | 0.001 | 0.001 |
| 唯一 ID | 10 | 11 |
| 共享 | 9 | 9 |
| 仅主接口 | 1 | - |
| 仅候选 | - | 2 |
| 并集 | 12 | 12 |
| Jaccard | 0.75 | 0.75 |

结论：两者高度重合但并不等价，且 Raw shape 差异明显。Web 还支持当前业务已使用的 `time_scope`，App 候选不能伪造这个过滤语义。因此生产 Search 继续使用 Web。

## 6.5 App Comments vs Web V2 Comments 真实 A/B

同一个真实微博内容：

| 指标 | App 主接口 | Web V2 候选 |
| --- | ---: | ---: |
| HTTP | 200 | 200 |
| 单价 | 0.001 | 0.001 |
| 本次稳定评论 ID | 1 | 1 |
| 共享 ID | 1 | 1 |
| Jaccard | 1.0 | 1.0 |

两边 Raw shape 差异较大，因此 Web V2 目前作为候选证据，不自动替代 App Mapper/分页。

## 6.6 为什么采用混合 Web/App/Web V2 主链

不是为了“统一版本号”，而是每个业务动作分别选择真实证据最完整的 endpoint：

- Web Search：关键词发现与过滤语义更符合当前 Plan；
- App Detail/Comments：真实结构、分页和 Mapper 已闭环；
- Web V2 SubComments：真实非空回复关系中可观察直接父评论字段。

---

# 7. B站 Bilibili

## 7.1 正式主链

```text
Search   App /api/v1/bilibili/app/fetch_search_by_type
Detail   App /api/v1/bilibili/app/fetch_one_video
Comments App /api/v1/bilibili/app/fetch_video_comments
Replies  App /api/v1/bilibili/app/fetch_reply_detail
```

四个主 endpoint 当前基础单价均为 `0.001 USD/request`。

## 7.2 真实 Search

```http
GET /api/v1/bilibili/app/fetch_search_by_type
```

```json
{
  "keyword": "爱玛",
  "search_type": "video",
  "order": 0
}
```

业务列表：`data.data.items[]`，视频事实位于 item 的 `av`；当前生产 extractor 使用该真实结构。  
完整响应：[`bilibili/search_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/bilibili/search_page1.sanitized.json)

## 7.3 Detail / Comments / Replies

Detail：

```http
GET /api/v1/bilibili/app/fetch_one_video?av_id=<sanitized-av-id>
```

主要路径：`data.data`。  
完整响应：[`bilibili/detail.sanitized.json`](../../tests/fixtures/providers/tikhub/bilibili/detail.sanitized.json)

一级评论：

```http
GET /api/v1/bilibili/app/fetch_video_comments?av_id=<sanitized-av-id>&mode=3
```

Endpoint Ledger 最多检查前三个 Search 候选，找到首个非空评论页后停止；真实列表为 `data.data.replies[]`。  
完整响应：[`bilibili/comments_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/bilibili/comments_page1.sanitized.json)

回复：

```http
GET /api/v1/bilibili/app/fetch_reply_detail?root=<sanitized-root-rpid>&av_id=<sanitized-av-id>
```

真实树：`data.data.root` 与 `data.data.root.replies[]`。  
完整响应：[`bilibili/replies_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/bilibili/replies_page1.sanitized.json)

## 7.4 App Search vs Web Search A/B 当前结论

两边 HTTP 均为 200、单价均为 `0.001 USD`。旧 A/B 汇总曾显示 App `0` 条、Web `20` 条，但该 `0` 已确认是**比较器没有从 App wrapper 的 `param/av` 结构提取稳定视频 ID**，不能解释成 TikHub App 搜索返回 0 条。

因此这一组数量/Jaccard 结果作废：

```text
status = candidate_pending_probe
reason = comparison_extractor_invalid
```

在修复比较器并重新做 B站最小单页 A/B 前，不把 Web Search 标成 `verified_backup`。

## 7.5 为什么主链选择 App

- Search/Detail/Comments/Reply 全部已经有真实非空结构与生产 extractor；
- `aid/bvid/rpid/root/parent` 可归一化到统一字符串 ID；
- 同一 App family 减少跨 family 语义差异；
- Web 候选存在，但当前 A/B 数量比较证据无效，不能据错误统计切换主链。

---

# 8. 快手 Kuaishou

## 8.1 正式主链

2026-08-16 用户已明确批准：一级、二级评论正式切换到 App；Web 不自动 fallback，只作为已验证备用。

```text
Search      App /api/v1/kuaishou/app/search_video_v2
Detail      App /api/v1/kuaishou/app/fetch_one_video
Comments    App /api/v1/kuaishou/app/fetch_video_comment
SubComments App /api/v1/kuaishou/app/fetch_video_sub_comments
```

基础单价：Search `0.010 USD`；Detail/Comments/SubComments 均 `0.001 USD`。

## 8.2 真实 Search

```http
GET /api/v1/kuaishou/app/search_video_v2?keyword=爱玛&pcursor=
```

真实业务列表：`data.mixFeeds[].feed`；分页 `data.pcursor`。  
完整响应：[`kuaishou/search_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/kuaishou/search_page1.sanitized.json)

## 8.3 Detail / Comments / SubComments

Detail：

```http
GET /api/v1/kuaishou/app/fetch_one_video?photo_id=<sanitized-photo-id>
```

主要路径：`data.photos[0]`。  
完整响应：[`kuaishou/detail.sanitized.json`](../../tests/fixtures/providers/tikhub/kuaishou/detail.sanitized.json)

一级评论：

```http
GET /api/v1/kuaishou/app/fetch_video_comment?photo_id=<sanitized-photo-id>&pcursor=
```

当前真实响应支持 `rootComments` 与 `subCommentsMap` 相关结构。  
完整响应：[`kuaishou/comments_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/kuaishou/comments_page1.sanitized.json)

二级评论：

```http
GET /api/v1/kuaishou/app/fetch_video_sub_comments
```

```json
{
  "photo_id": "<sanitized-photo-id>",
  "root_comment_id": "<sanitized-root-comment-id>",
  "pcursor": "",
  "count": 8
}
```

完整响应：[`kuaishou/sub_comments_page1.sanitized.json`](../../tests/fixtures/providers/tikhub/kuaishou/sub_comments_page1.sanitized.json)

## 8.4 为什么评论从 Web 切到 App

同一个真实作品、同一个明确有回复的根评论实测：

| 接口 | Web | App |
| --- | ---: | ---: |
| 一级评论 HTTP | 200 | 200 |
| 二级评论 HTTP | 200 | 200 |
| 二级 `subComments[]` | 非空 | 非空 |
| 一级基础单价 | 0.002 | 0.001 |
| 二级基础单价 | 0.010 | 0.001 |

App 一级响应还能够携带部分 `subCommentsMap`。在两套接口都真实可用的前提下，App 请求成本更低、Search/Detail/Comments family 更一致，因此选择 App 作为主链。

Web 保留为：

```text
verified_backup
```

但不自动 fallback。

## 8.5 Search V2 vs Web / Comprehensive

TikHub 当前没有与快手关键词视频搜索同语义的 Web Search，因此不存在合法的 App-vs-Web 搜索数量比较：

```text
App Search V2 vs Web Search = not_equivalent / no_same_semantic_web_search
```

App 内部 `search_comprehensive` 是更宽的综合搜索，不是等价视频搜索。真实单页 A/B：

| 指标 | Video Search V2 | Comprehensive |
| --- | ---: | ---: |
| HTTP | 200 | 200 |
| 单价 | 0.010 | 0.010 |
| 唯一内容 ID | 17 | 8 |
| 共享 ID | 0 | 0 |
| 并集 | 25 | 25 |
| Jaccard | 0.0 | 0.0 |

因此 `search_comprehensive` 明确记录为**不同业务语义的补充发现候选**，不能作为 `search_video_v2` 自动备用。

---

# 9. 当前 API family 验证矩阵

| 平台 | 业务动作 | 主接口 | 候选/备用 | 当前结论 |
| --- | --- | --- | --- | --- |
| XHS | Search/Detail/Comments/Sub | App V2 | App/Web 其他 family | `candidate_pending_probe` |
| 抖音 | Search | Video Search V2 | Video Search V1 | 真实首屏 7/7 同集合；Raw shape 不同，候选归一化门禁待闭环 |
| 抖音 | Detail/Comments/Replies | App V3 | Web family | 候选 builder 已存在，真实同内容 A/B 待补 |
| 微博 | Search | Web | App Search All | 真实 Jaccard 0.75；不等价，候选归一化门禁待闭环 |
| 微博 | Comments | App | Web V2 | 本次 1/1 同评论；Raw shape 不同，候选归一化门禁待闭环 |
| 微博 | Detail/Replies | App / Web V2 Sub | Web V2 / Web Replies | 候选 builder 已存在，真实同内容 A/B 待补 |
| B站 | Search | App | Web | 两边 200；旧数量比较 extractor 无效，需最小重验 |
| B站 | Detail/Comments/Replies | App | Web | 候选 builder 已存在，真实同内容 A/B 待补 |
| 快手 | Search | App Video V2 | 无等价 Web；App Comprehensive 更宽 | Web `not_equivalent`；Comprehensive 非等价补充发现 |
| 快手 | Detail | App | Web V2 | 候选待最小 A/B |
| 快手 | Comments/Sub | App | Web | `verified_backup`；不自动 fallback |

# 10. 后续新增/修改接口时如何维护本文

任何 TikHub endpoint 或 API family 变化必须按以下顺序：

1. 当前官方 endpoint/参数确认；
2. `get_endpoint_info` 取得 endpoint-level 单价；
3. GitHub-hosted Runner 做最小真实 Probe；
4. 保存脱敏 Request、Response、HTTP、价格和字段路径；
5. Search 比较稳定内容 ID；Comments 比较稳定 comment ID；
6. 验证 Extractor/Mapper → Canonical；
7. 必要时验证 Canonical → PostgreSQL；
8. 更新本文“选型理由”和 Blueprint 11 状态；
9. 只有显式批准才能切换生产主接口；
10. 备用接口不自动 fallback，除非另有经过审批的失败/预算/Raw lineage 设计。

禁止因为 TikHub 文档示例、接口名称、旧聊天或一次 HTTP 200 就写成“生产兼容”。
