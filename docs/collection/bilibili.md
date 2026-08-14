# B站采集逻辑

## 1. 当前状态

B站 TikHub Operation/Mapper **尚未在 main 实现**。本文冻结 Stage 7 首版主链路；完成兼容验收仍需要合法脱敏真实 Fixture、Mapper Contract Test 和 Real Provider Probe。

目标路径：

```text
backend/src/aima_ugc/adapters/providers/tikhub/operations/bilibili.py
backend/src/aima_ugc/adapters/providers/tikhub/mappers/bilibili.py
tests/unit/collection/test_bilibili_tikhub_operation.py
tests/unit/collection/test_bilibili_tikhub_mapper.py
tests/fixtures/providers/tikhub/bilibili/
```

## 2. 已批准 TikHub Operation

| 业务动作 | Endpoint | 官方文档 |
| --- | --- | --- |
| 分类关键词搜索 | `GET /api/v1/bilibili/app/fetch_search_by_type` | https://docs.tikhub.io/382707670e0 |
| 视频详情 | `GET /api/v1/bilibili/app/fetch_one_video` | https://docs.tikhub.io/382707662e0 |
| 一级评论 | `GET /api/v1/bilibili/app/fetch_video_comments` | https://docs.tikhub.io/382707663e0 |
| 二级回复 | `GET /api/v1/bilibili/app/fetch_reply_detail` | https://docs.tikhub.io/382707664e0 |

第一版全部使用 TikHub Bilibili App API family，不建立 Web fallback。

## 3. 搜索业务参数

分类搜索当前支持：

- keyword；
- search_type：video、bangumi、pgc、live、article、user 等；
- order：综合、最新发布、播放量、弹幕数；
- page_size：只有正式 Capability 决定是否允许业务配置；
- cursor：内部技术分页，使用上一页 `data.pagination.next`。

首版舆情内容发现默认 `search_type=video`；以后需要文章/直播等内容时通过明确 Capability/Plan 扩展，不在 Mapper 中把不同对象硬装成视频。

## 4. 时间范围是平台差异

当前批准的 `fetch_search_by_type` 没有观察到 Provider 原生发布时间筛选，所以：

```text
native_time_filter = false
```

前端不能显示一个看似由 B站/TikHub 原生支持的“最近一天/一周”筛选。

如果 Stage 7 以后在 `order=最新发布` 下用返回 `published_at` 做本地越界停止，必须：

- Capability 明确标记为本地时间边界而非 Provider 原生筛选；
- 用 Fixture/Probe 验证排序和时间字段足够稳定；
- UI 给出说明，不能承诺 Provider 已在服务端过滤；
- 非最新排序时不能套用同一停止假设。

## 5. 详情和评论

详情接受 av_id 或 bv_id，稳定外部身份仍按 Canonical 的字符串 ID 处理。

一级评论：

- av_id/bv_id 二选一；
- mode=3 热门、mode=2 时间；
- next_offset 是技术分页。

二级回复：

- root：一级评论 ID；
- av_id/bv_id；
- next_offset；
- ps：只有 Capability/真实测试证明需要业务配置时才开放。

## 6. B站标准 Pipeline

```text
fetch_search_by_type
→ Search Raw
→ Bilibili Mapper / Observation
→ bv/av 稳定身份去重
→ 指标/comment_count 比较
→ 必要时 fetch_one_video
→ Comment Eligibility
→ fetch_video_comments
→ 对有回复线程 fetch_reply_detail
→ Raw → Mapper → Canonical → Ingestion
```

## 7. 评论省钱与增量

通用规则：

- 可靠 comment_count=0 → 不请求评论；
- 重复内容 comment_count 不变 → 不请求；
- 其他指标变化但评论数不变 → 只更新指标；
- 评论数增加 → 优先增量/受控刷新；
- 评论数下降 → 记录下降，不凭部分 coverage 猜删除。

B站一级评论支持时间排序 `mode=2`。只有真实 Fixture/Probe 证明按时间读取并遇到已知 comment_id 能形成稳定停止条件后才开启增量评论能力。

默认完整阈值 50、目标 50、每线程回复目标 5；整页已返回数据全部保留。

## 8. 弹幕不是评论

B站有独立弹幕能力和弹幕指标。第一版把弹幕作为可选 enrichment：

```text
dan m aku_policy = off（默认）
```

未来可以开放：关闭 / Deep Collection / 指定高价值内容采集，但必须单独预算、单独 Raw/Mapper 语义，不能把弹幕混入 `comments` 伪装成评论树。

搜索按“弹幕数”排序只是搜索排序能力，不等于已经采集弹幕正文。

## 9. Deep Collection

已入库视频从内部 `content_id` 发起，后端解析 bv_id/av_id。未发现内容可以通过 BV/AV ID 或分享链接高级入口补抓。

Deep Collection 可以提高评论目标或开启弹幕 enrichment，但仍受真实 Provider 预算。

## 10. 独立调试和验收

Operation Probe 验证：分类搜索 cursor、详情 av/bv、一级评论 mode/next_offset、二级 root/next_offset。

Business Pipeline Probe 验证：

- 重复视频评论数不变不抓评论；
- `mode=2` 是否适合增量停止；
- `data.pagination.next` 缺失/空时正确停止；
- 没有原生时间过滤时 UI/决策不伪造服务端过滤；
- 弹幕 enrichment 默认不会增加请求。

官方文档允许开始 Operation 实现；B站“已兼容”必须等合法脱敏非空真实 Fixture、Mapper Contract Test 和 Real Probe。