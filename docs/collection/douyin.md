# 抖音采集逻辑

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
