# B站采集逻辑

## 1. 当前状态

B站 TikHub App **Operation 已实现并有自动化请求/分页测试**；Raw→Canonical Mapper、合法脱敏非空真实 Fixture、Real Provider Probe、Capability/默认 Registry 仍未实现。因此当前只能宣称“B站 Operation 已实现”，**不能宣称 B站平台已兼容或可生产采集**。

当前机器路径：

```text
backend/src/aima_ugc/adapters/providers/tikhub/operations/bilibili.py
tests/unit/collection/test_bilibili_tikhub_operation.py
```

后续平台兼容仍需：

```text
backend/src/aima_ugc/adapters/providers/tikhub/mappers/bilibili.py
tests/unit/collection/test_bilibili_tikhub_mapper.py
tests/fixtures/providers/tikhub/bilibili/
Real Provider Probe
Capability / Registry 接线
```

## 2. 当前 TikHub Operation

| 业务动作 | Endpoint | 官方文档 |
| --- | --- | --- |
| 分类关键词搜索 | `GET /api/v1/bilibili/app/fetch_search_by_type` | https://docs.tikhub.io/382707670e0 |
| 视频详情 | `GET /api/v1/bilibili/app/fetch_one_video` | https://docs.tikhub.io/382707662e0 |
| 一级评论 | `GET /api/v1/bilibili/app/fetch_video_comments` | https://docs.tikhub.io/382707663e0 |
| 二级回复 | `GET /api/v1/bilibili/app/fetch_reply_detail` | https://docs.tikhub.io/382707664e0 |

第一版全部使用 TikHub Bilibili App API family，不建立 Web fallback。Operation 只负责 Provider 请求参数和有证据的分页状态，不访问数据库、不写 Artifact、不读取 Secret，也不解析尚未由 Fixture 固化的评论业务字段。

## 3. 分类搜索

舆情发现首版固定 `search_type=video`，避免在没有 Mapper/Canonical 设计的情况下把番剧、直播、文章、用户等不同对象静默当成视频。

规范化排序映射为当前 TikHub 官方值：

| 业务语义 | Provider `order` |
| --- | ---: |
| `general` | `0` |
| `latest` | `1` |
| `play_count` | `2` |
| `danmaku_count` | `3` |

当前 Operation 保留既有业务默认：未显式指定 `sort_mode` 时使用 `general`。分页规则：

```text
首屏：不发送 cursor
→ 响应 $.data.data.pagination.next
→ 非空且不同于上一 cursor：继续
→ 缺失/空：provider_exhausted
→ 与上一 cursor 相同：pagination_not_advanced
```

这里只解析 TikHub 当前官方文档明确给出的 `$.data.data.pagination.next`。搜索结果数组位置、业务字段和 Raw→Canonical 语义仍等待合法脱敏非空 Fixture。`page_size` 保留 Provider 默认值，不作为本单元业务参数开放。

## 4. 时间范围是平台差异

当前 `fetch_search_by_type` 没有批准的 Provider 原生发布时间筛选，因此：

```text
native_time_filter = false
```

前端不能显示一个看似由 B站/TikHub 原生支持的“最近一天/一周”筛选。以后若基于最新排序和发布时间做本地停止，必须由 Fixture/Probe 证明排序与时间字段足够稳定，并在 Capability/UI 中明确它是本地边界而不是 Provider 原生过滤。

## 5. 视频详情

详情请求必须使用以下二者之一，且不能同时提供：

```text
av_id
bv_id
```

外部 ID 始终按字符串处理。Operation 不负责决定哪个 ID 是 Canonical 主身份；该映射语义由后续 Mapper/Fixture 冻结。

## 6. 一级评论

一级评论同样要求 `av_id` / `bv_id` 二选一。当前业务排序映射：

```text
latest → mode=2
hot    → mode=3
```

首屏不发送 `next_offset`；后续页只在调用方已经从可靠响应事实提取到 offset 时发送 `next_offset`。当前 Operation **不猜**评论响应中的下一页 JSON 路径，也不解析评论数组。若调用方给出的数字 offset 没有严格前进，分页状态机会保守停止，避免回退或重复造成循环。

## 7. 二级回复

请求参数：

```text
root               # 一级评论 ID
av_id 或 bv_id      # 二选一
next_offset         # 可选，后续页
```

`ps` 保持 Provider 默认值，不在当前业务层覆盖。与一级评论相同，Operation 只消费调用方已可靠提取的下一 offset，不猜尚未由 Fixture 证明的响应路径。

## 8. B站标准 Pipeline

当前只完成最前面的 Operation 机器边界；完整平台纵切仍是：

```text
fetch_search_by_type
→ Search Raw
→ Bilibili Mapper / Observation
→ platform + external_content_id 去重
→ CollectionDecisionService
→ 必要时 fetch_one_video
→ fetch_video_comments
→ 对需要的线程 fetch_reply_detail
→ Raw → Mapper → Canonical → Ingestion
```

未实现的 Mapper/Fixture/Probe/Capability 不能被 Operation 测试替代。

## 9. 评论省钱与增量

跨平台通用规则保持不变：可靠 `comment_count=0` 短路；重复内容评论数不变默认不重抓；评论数增加仅在 Capability 已证明稳定增量时走增量，否则受控刷新；评论数下降只记录事实，不凭部分 coverage 猜具体删除。

B站 `mode=2` 只是“时间排序”请求能力。只有合法脱敏真实 Fixture/Probe 证明按时间读取并遇到已知 `comment_id` 可以稳定停止后，Capability 才能声明增量评论能力。

## 10. 弹幕不是评论

弹幕属于独立 enrichment，不进入 `comments` 评论树。搜索按弹幕数排序也不等于已经采集弹幕正文。第一版默认不因为普通舆情采集自动增加弹幕请求；若后续启用，必须有独立 Operation/Raw/Mapper/预算语义。

## 11. 独立验证与验收边界

不需要数据库或真实 Provider 即可运行 Operation 单测：

```bash
uv run pytest tests/unit/collection/test_bilibili_tikhub_operation.py -q
```

该测试证明：当前 endpoint、搜索 `cursor/order`、官方搜索下一 cursor 路径、详情 `av_id/bv_id`、一级评论 `mode/next_offset`、二级回复 `root/next_offset`、默认排序/分页保守兼容语义和关闭失败输入校验。

它**不证明**：真实非空响应字段、Mapper、评论数组/分页响应路径、稳定增量停止、真实 TikHub 兼容、Capability/Registry 或完整生产采集。

B站“已兼容”必须等合法脱敏非空真实 Fixture、Mapper Contract Test、Real Provider Probe 与正式 Capability/Registry 接线共同闭环。