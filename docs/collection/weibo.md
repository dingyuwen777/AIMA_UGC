# 微博采集逻辑

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
from aima_ugc.adapters.providers.tikhub_test import run_weibo

run_weibo(keyword="爱玛", sort_mode="latest", published_within="day")
```

当前没有 Budget/Cost Guard；调试输出 Raw、Canonical、`run_summary.json`、state 和原始数据 Excel。
