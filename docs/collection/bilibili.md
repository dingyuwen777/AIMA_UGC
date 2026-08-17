# B站采集逻辑

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
