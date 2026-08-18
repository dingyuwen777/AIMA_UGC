# 小红书采集逻辑

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
from aima_ugc.adapters.providers.tikhub_test import run_xiaohongshu

run_xiaohongshu(keyword="爱玛", sort_mode="latest", published_within="1d")
```

输出 Raw、Canonical、`run_summary.json`、跨运行 `state.json` 和原始数据 Excel。
