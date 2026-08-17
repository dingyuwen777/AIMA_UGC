# 快手采集逻辑

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
