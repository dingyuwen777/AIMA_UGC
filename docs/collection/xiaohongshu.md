# 小红书采集逻辑

## 1. 当前状态

小红书是当前**唯一已经在 main 建立 TikHub Operation/Mapper 的平台**。Stage 6 已实现 App V2 搜索、图文详情、视频详情、一级评论和二级评论的请求构造/分页，以及 XHS → Canonical Mapper。

机器事实优先看：

```text
backend/src/aima_ugc/adapters/providers/tikhub/operations/xiaohongshu.py
backend/src/aima_ugc/adapters/providers/tikhub/mappers/xiaohongshu.py
tests/unit/collection/test_xhs_tikhub_operation.py
tests/unit/collection/test_xhs_tikhub_mapper.py
tests/fixtures/providers/tikhub/xhs/
```

当前合法脱敏非空搜索 Fixture：

```text
tests/fixtures/providers/tikhub/xhs/search_notes_page1.sanitized.json
```

详情/评论当前仍主要由确定性结构测试覆盖，不能把搜索 Fixture 冒充真实详情/评论兼容证据。

## 2. 已批准 TikHub Operation

| 业务动作 | Endpoint | 官方文档 |
| --- | --- | --- |
| 关键词搜索 | `GET /api/v1/xiaohongshu/app_v2/search_notes` | https://docs.tikhub.io/420136398e0 |
| 图文详情 | `GET /api/v1/xiaohongshu/app_v2/get_image_note_detail` | TikHub Xiaohongshu App V2 |
| 视频详情 | `GET /api/v1/xiaohongshu/app_v2/get_video_note_detail` | TikHub Xiaohongshu App V2 |
| 一级评论 | `GET /api/v1/xiaohongshu/app_v2/get_note_comments` | https://docs.tikhub.io/420136394e0 |
| 二级评论 | `GET /api/v1/xiaohongshu/app_v2/get_note_sub_comments` | https://docs.tikhub.io/420748830e0 |

第一版不为这些 Operation 增加运行时 Web fallback。

## 3. 搜索可配置业务参数

Search Notes 官方支持的业务能力由 Capability 暴露，前端至少可以在实际 Contract 中选择：

- keyword：来自词包/单词；
- sort：综合、最新、点赞、评论、收藏等当前正式 Operation 支持的排序；
- note_type：全部/视频/图文/直播等已验证类型；
- published_within：当前 Operation 支持的发布时间范围。

当前代码内部还管理：

```text
page
search_id
search_session_id
source
```

这些是分页/Provider 技术状态，不开放给普通业务用户。

## 4. 当前代码与 Stage 7 的差异

当前 `xiaohongshu.py` 已经：

- 使用 `/api/v1/xiaohongshu/app_v2`；
- 构造 `search_notes` 参数；
- 保存 `page/search_id/search_session_id`；
- 评论保存 `cursor/index/pageArea`；
- 评论当前固定 `sort_strategy=latest_v2`；
- 实现空页、重复页、Provider 末页、分页不推进等停止条件。

Stage 7 不重写这套实现，而是在上层增加：

```text
Capability
+ Collection Decision Service
+ Plan 平台策略
+ Budget
+ Business Pipeline Probe
```

评论排序以后可由前端选择时，仍必须通过规范化业务枚举进入 Operation，不能让前端直接传任意 `sort_strategy` 字符串。

## 5. 小红书标准 Pipeline

```text
search_notes
→ Search Raw
→ XHS Mapper / Observation
→ note_id 去重
→ 比较上次内容/指标/comment_count
→ Detail Decision
→ get_image_note_detail 或 get_video_note_detail（仅必要时）
→ Comment Eligibility
→ get_note_comments
→ 对有回复的一级评论按策略 get_note_sub_comments
→ 每次 Raw
→ XHS Mapper
→ Canonical
→ Ingestion
```

## 6. 评论省钱规则

统一规则在 [采集逻辑总览](README.md)，小红书补充：

1. Search/Detail 明确观察到 `comment_count=0` 时不请求评论；
2. 重复笔记 `comment_count` 未变化时默认不重抓评论；
3. 增加时优先使用稳定最新排序做增量；
4. App V2 评论官方提供 `latest_v2`，且官方文档提示默认排序不适合稳定分页，因此首版增量评论以 `latest_v2` 作为默认最新语义；
5. 评论目标默认 50，50 以内尽量完整；二级回复默认每一级线程目标 5；
6. 已经付费返回的整页数据全部保存，不按目标数字裁剪。

## 7. 分页停止

搜索当前实现必须保持：

- 空页；
- Provider 无更多；
- 页面完全重复；
- page/search session 不推进；
- 业务时间边界；
- 请求/费用预算；
- 技术安全页数；
- 取消。

一级评论还要检查 `cursor/index/pageArea` 是否推进；二级评论检查 `cursor/index`。

## 8. 时间窗口

小红书 Search Notes 有 Provider 原生发布时间筛选，因此前端可以展示 Capability 证明存在的时间范围。

如果 Plan 每 6 小时执行但 Provider 选择“一天内”，允许 24 小时窗口重叠；系统通过 `platform + external_content_id` 去重，并利用“重复且 comment_count 未变化不抓评论”减少重叠成本。

如果用户把业务窗口设置得比调度间隔更短，只 Warning，不阻止保存；非法/Provider 不支持值才拒绝。

## 9. Deep Collection

内容页已经有内部 `content_id` 时，用户只点击“深度抓取”。后端解析出：

```text
platform=xhs
external_content_id=note_id
provider=tikhub
```

然后按用户 Deep 参数调用正式详情/评论 Operation。

只有系统尚未发现笔记时，才需要高级入口输入 note_id 或小红书分享链接。

## 10. 独立调试

### Operation Probe

支持单独测试：

```text
search_notes
detail
get_note_comments
get_note_sub_comments
```

并保存 Raw → Canonical → XLSX。

### Business Pipeline Probe

至少验证两次连续运行：

```text
第一次：爱玛 → 建立 Probe Snapshot
第二次：爱玛 → 比较相同 note_id
```

人工重点看：

- comment_count 未变化的重复笔记是否没有再次调评论；
- comment_count=0 是否短路；
- comment_count 增加是否进入增量；
- decisions.jsonl 的 reason 是否与真实请求次数一致。

## 11. 完成 Stage 7 小红书扩展的验收

小红书 Stage 6 已建立平台纵切；Stage 7 对它主要是**接入统一 Decision/Capability/Plan/Budget/Business Probe**。不得为了统一五平台而复制一套新的 XHS Client/Mapper。

如果 TikHub App V2 官方参数、响应结构或当前代码发生实质变化，同任务更新本文件、Operation/Mapper、Fixture 和相关测试；代码事实优先于本说明。
