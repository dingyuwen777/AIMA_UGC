"""一次性五平台采集文档最终化；执行后删除。"""
from pathlib import Path
from textwrap import dedent


docs = {
    "docs/collection/xiaohongshu.md": '''# 小红书采集逻辑

## 1. 当前状态

小红书已具备完整 TikHub 生产链：App V2 Search、图文/视频 Detail、一级/二级评论 Operation，生产 Extractor/Mapper、合法脱敏真实 Fixture、Capability/Registry、Canonical/Ingestion、正式 Collection Worker 与独立 `tikhub_test` 调试入口均已建立。

## 2. 正式 Operation

| 业务动作 | Endpoint |
| --- | --- |
| 搜索 | `GET /api/v1/xiaohongshu/app_v2/search_notes` |
| 图文详情 | `GET /api/v1/xiaohongshu/app_v2/get_image_note_detail` |
| 视频详情 | `GET /api/v1/xiaohongshu/app_v2/get_video_note_detail` |
| 一级评论 | `GET /api/v1/xiaohongshu/app_v2/get_note_comments` |
| 二级评论 | `GET /api/v1/xiaohongshu/app_v2/get_note_sub_comments` |

第一版不做 App/Web 自动 fallback。Provider 私有分页状态只由生产 Operation/Runtime 管理。

## 3. 评论增量与省钱

一级评论固定 `sort_strategy=latest_v2`。官方最新优先语义与当前真实 Runner 的严格非增时间顺序共同支持：

```text
supports_incremental_comment_sort = true
```

`comment_count` 不变默认不请求评论；增加进入 `fetch_incremental`；下降走 `refresh_controlled`。增量时当前已付费页先完整 Raw/Mapper/Ingestion；只有从本页第一个已知历史 `comment_id` 到页尾全部都是已知历史评论，才 `known_comment_reached` 并停止下一页。生产系统从 PostgreSQL 一次读取历史一级评论 ID，`tikhub_test` 用文件 state 适配，但两者调用同一生产规则。

当前没有请求次数/金额 Budget Runtime。

## 4. Pipeline 与独立调试

```text
search_notes → Raw → Mapper/Observation → identity/compare → Decision
→ 必要时 Detail → Comments/Replies → Raw → Mapper → Canonical → Ingestion
```

```python
from aima_ugc.adapters.providers.tikhub_test.xiaohongshu import run_xiaohongshu

run_xiaohongshu(keyword="爱玛", sort_mode="latest", published_within="1d")
```

输出 Raw、Canonical、`run_summary.json`、跨运行 `state.json` 和原始数据 Excel。
''',
    "docs/collection/douyin.md": '''# 抖音采集逻辑

## 1. 当前状态

抖音已建立 Search V2、App V3 Detail/一级评论/回复 Operation，生产 Extractor/Mapper、合法脱敏真实 Fixture、Capability/Registry、Canonical/Ingestion、正式 Collection Worker 与 `tikhub_test` 独立调试入口。

## 2. 正式 Operation

| 业务动作 | Endpoint |
| --- | --- |
| 搜索 | `POST /api/v1/douyin/search/fetch_video_search_v2` |
| 详情 | `GET /api/v1/douyin/app/v3/fetch_one_video_v3` |
| 一级评论 | `GET /api/v1/douyin/app/v3/fetch_video_comments` |
| 回复 | `GET /api/v1/douyin/app/v3/fetch_video_comment_replies` |

Search V2 支持规范化排序、发布时间、时长和内容类型；`cursor/search_id/backtrace` 是 Provider 技术状态。真实兼容复核发现 Search 会混入不含稳定 `aweme_id` 的展示卡片，生产 extractor 现在只把具有稳定视频 ID 的业务卡片送入 Mapper。

## 3. 评论省钱与排序边界

App V3 一级评论没有已批准的“最新评论排序”业务参数，因此：

```text
supports_incremental_comment_sort = false
```

`comment_count` 增加时走 `refresh_controlled`，不能把遇到旧 comment ID 解释成安全历史边界；不变时默认跳过评论。未来只有官方排序语义与真实多评论页顺序都能证明安全后才能开启增量。

## 4. Pipeline 与调试

```text
fetch_video_search_v2 → Raw → Mapper → aweme_id identity/compare → Decision
→ 必要时 fetch_one_video_v3 → Comments/Replies → Raw → Mapper → Canonical → Ingestion
```

```python
from aima_ugc.adapters.providers.tikhub_test.douyin import run_douyin

run_douyin(keyword="爱玛", sort_mode="latest", published_within="1d")
```

当前没有 Budget/Cost Guard；调试输出 Raw、Canonical、`run_summary.json`、state 和原始数据 Excel。
''',
    "docs/collection/weibo.md": '''# 微博采集逻辑

## 1. 当前状态

微博已建立 Web Search、App Detail/一级评论、Web V2 二级评论 Operation，生产 Extractor/Mapper、合法脱敏真实 Fixture、Capability/Registry、Canonical/Ingestion、正式 Collection Worker 与 `tikhub_test` 独立调试入口。

## 2. 正式 Operation

| 业务动作 | Endpoint |
| --- | --- |
| 搜索 | `GET /api/v1/weibo/web/fetch_search` |
| 详情 | `GET /api/v1/weibo/app/fetch_status_detail` |
| 一级评论 | `GET /api/v1/weibo/app/fetch_status_comments` |
| 二级评论 | `GET /api/v1/weibo/web_v2/fetch_post_sub_comments` |

不同 API family 是固定职责，不是 fallback。一级评论生产 extractor 只接收具有稳定 `idstr/mid/id` 的真实评论；展示卡片不进入 Comment Mapper。分页优先消费 `data.moreInfo.params.max_id`，当前真实形状缺少 `moreInfo` 时按 Provider 末页处理，不猜另一个私有游标路径。

## 3. 为什么当前不开增量

一级评论可发送 `sort_type=1`，但 2026-08-18 当前真实 Probe 的 20 条有效评论：

```text
time_count = 20
time_nonincreasing = false
```

因此参数名“latest”不足以证明安全历史边界：

```text
supports_incremental_comment_sort = false
```

`comment_count` 增加时继续 `refresh_controlled`；不变时默认跳过评论。

## 4. Pipeline 与调试

```text
fetch_search → Raw → Mapper → status_id identity/compare → Decision
→ 必要时 Detail → Comments/Sub-comments → Raw → Mapper → Canonical → Ingestion
```

```python
from aima_ugc.adapters.providers.tikhub_test.weibo import run_weibo

run_weibo(keyword="爱玛", sort_mode="latest", published_within="day")
```

当前没有 Budget/Cost Guard；调试输出 Raw、Canonical、`run_summary.json`、state 和原始数据 Excel。
''',
    "docs/collection/bilibili.md": '''# B站采集逻辑

## 1. 当前状态

B站已建立 App Search/Detail/一级评论/回复 Operation，生产 Extractor/Mapper、合法脱敏真实 Fixture、Capability/Registry、Canonical/Ingestion、正式 Collection Worker 与 `tikhub_test` 独立调试入口。

## 2. 正式 Operation

| 业务动作 | Endpoint |
| --- | --- |
| 分类视频搜索 | `GET /api/v1/bilibili/app/fetch_search_by_type` |
| 视频详情 | `GET /api/v1/bilibili/app/fetch_one_video` |
| 一级评论 | `GET /api/v1/bilibili/app/fetch_video_comments` |
| 二级回复 | `GET /api/v1/bilibili/app/fetch_reply_detail` |

Search 没有 Provider 原生发布时间筛选，所以 `native_time_filter=false`。

## 3. 评论首屏与排序

正式排序：`latest → mode=2`，`hot → mode=3`。当前真实验证确认 App 一级评论首屏必须显式发送 `next_offset=0`；省略或误从 1 开始会造成当前样本返回空页，因此生产 builder/Runtime 已固定首屏 0，后续只消费正式分页 extractor 证明的 offset。

## 4. 已验证增量能力

TikHub 官方把 `mode=2` 定义为时间排序。2026-08-18 GitHub-hosted Runner 使用生产 Runtime、关键词“爱玛”，从前五个候选中选择 Provider 报告评论数最高的样本：

```text
reported_comment_count = 105
mode = 2
next_offset = 0
returned_root_comments = 20
unique_comment_ids = 20
time_count = 20
time_nonincreasing = true
```

因此：

```text
supports_incremental_comment_sort = true
```

`comment_count` 增加时走统一 `fetch_incremental`；当前已付费页先完整 Raw/Mapper/Ingestion，再由共享 `known_comment_reached` 决定是否请求下一页。

## 5. Pipeline 与调试

```text
fetch_search_by_type → Raw → Mapper → content identity/compare → Decision
→ 必要时 fetch_one_video → Comments/Reply → Raw → Mapper → Canonical → Ingestion
```

```python
from aima_ugc.adapters.providers.tikhub_test.bilibili import run_bilibili

run_bilibili(keyword="爱玛", sort_mode="latest")
```

弹幕是独立 enrichment，不等同评论；当前没有 Budget/Cost Guard。
''',
    "docs/collection/kuaishou.md": '''# 快手采集逻辑

## 1. 当前状态

快手正式主链固定为 App Search V2 → App Detail → App 一级评论 → App 二级评论。Web 一级/二级评论已有真实兼容证据，但只作为显式 `verified_backup`，App 失败时不自动 fallback。

## 2. 正式 Operation

| 业务动作 | Endpoint | 状态 |
| --- | --- | --- |
| 搜索 | `GET /api/v1/kuaishou/app/search_video_v2` | primary |
| 详情 | `GET /api/v1/kuaishou/app/fetch_one_video` | primary |
| 一级评论 | `GET /api/v1/kuaishou/app/fetch_video_comment` | primary |
| 二级评论 | `GET /api/v1/kuaishou/app/fetch_video_sub_comments` | primary |
| Web 评论链 | Web family 对应接口 | verified backup |

Search V2 当前只有 `keyword/pcursor`，没有批准的原生排序和发布时间筛选，`native_time_filter=false`。

## 3. 评论与回复

一级真实列表来自 `data.rootComments[]`；`subCommentCount` 映射 `metrics.reply_count`，`displaySubCommentCount` 只是显示信号。二级回复使用明确 `root_comment_id`；没有直接父 ID 时不根据数组位置猜 `parent_comment_id`。

## 4. 为什么当前不开增量

当前 App 评论没有已批准的“最新评论排序”参数。真实 Runner 对当前样本取得 94 条一级评论，ID 唯一，但发布时间顺序并非严格非增。因此：

```text
supports_incremental_comment_sort = false
```

`comment_count` 增加时受控刷新；不变时默认跳过评论。不能为了省请求而在混排页面中遇到旧 comment ID 后提前停止。

## 5. Pipeline 与调试

```text
search_video_v2 → Raw → Mapper → photo_id identity/compare → Decision
→ 必要时 fetch_one_video → Comments/Sub-comments → Raw → Mapper → Canonical → Ingestion
```

当前 App endpoint Pricing 继续用于 Provider Billing 审计，但系统没有请求次数/金额 Budget Runtime。

```python
from aima_ugc.adapters.providers.tikhub_test.kuaishou import run_kuaishou

run_kuaishou(keyword="爱玛")
```

调试输出 Raw、Canonical、`run_summary.json`、state 和原始数据 Excel。
''',
}

for path, content in docs.items():
    Path(path).write_text(dedent(content).lstrip(), encoding="utf-8")
