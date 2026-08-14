# 微博采集逻辑

## 1. 当前状态

微博 TikHub Operation/Mapper **尚未在 main 实现**。本文记录 Stage 7 已批准的首版主链路。实际字段映射和兼容结论必须等合法脱敏真实 Fixture、Mapper Contract Test 和 Real Provider Probe。

目标路径：

```text
backend/src/aima_ugc/adapters/providers/tikhub/operations/weibo.py
backend/src/aima_ugc/adapters/providers/tikhub/mappers/weibo.py
tests/unit/collection/test_weibo_tikhub_operation.py
tests/unit/collection/test_weibo_tikhub_mapper.py
tests/fixtures/providers/tikhub/weibo/
```

## 2. 已批准 TikHub Operation

| 业务动作 | Endpoint | 官方文档 |
| --- | --- | --- |
| 关键词搜索 | `GET /api/v1/weibo/web/fetch_search` | https://docs.tikhub.io/381269400e0 |
| 微博详情 | `GET /api/v1/weibo/app/fetch_status_detail` | https://docs.tikhub.io/410358103e0 |
| 一级评论 | `GET /api/v1/weibo/app/fetch_status_comments` | https://docs.tikhub.io/410358104e0 |
| 二级评论 | `GET /api/v1/weibo/web_v2/fetch_post_sub_comments` | https://docs.tikhub.io/381269410e0 |

Web/App/Web V2 的组合是各业务 Operation 的固定选型，不是失败 fallback。

## 3. 搜索业务参数

Web Search 当前官方支持：

- keyword；
- search_type：综合、实时、热门以及视频/图片/文章等类型；
- time_scope：不限、hour、day、week、month；
- page：技术分页，从 1 递增。

舆情关键词发现默认规范化语义：

```text
sort = latest
→ search_type = 61（实时/最新）
```

普通 UI 可展示 Capability 允许的排序/内容类型/时间范围，但不能直接让用户填写 `search_type=61` 这类第三方枚举。

`page` 属 Operation 分页状态，由 Worker/Probe 管理。

## 4. 详情和评论

详情使用 App `fetch_status_detail(status_id)`，获取完整文本、媒体和互动数据。

一级评论使用 App `fetch_status_comments`：

- status_id；
- max_id：后续页使用响应值；
- sort_type：0 热度、1 时间；
- 官方说明每页约 20 条，max_id 为空或不推进时结束。

二级评论使用 Web V2 `fetch_post_sub_comments`：

- id：一级评论 ID；
- count：默认 10，只有 Capability/真实测试证明允许业务控制时才开放；
- max_id：分页状态。

## 5. 微博标准 Pipeline

```text
fetch_search（默认实时/最新）
→ Search Raw
→ Weibo Mapper / Observation
→ status_id 去重
→ 指标/comment_count 比较
→ 必要时 fetch_status_detail
→ Comment Eligibility
→ fetch_status_comments（时间排序用于增量候选）
→ 对有回复线程 fetch_post_sub_comments
→ Raw → Mapper → Canonical → Ingestion
```

## 6. 省钱与增量评论

通用短路保持：可靠 comment_count=0 不请求；重复微博 comment_count 未变化不请求；其他指标变化不自动重抓评论。

一级评论支持按时间排序，因此在合法 Fixture/Real Probe 证明时间排序与 comment_id 停止可稳定工作后，允许：

```text
comment_count 增加
→ sort_type=1
→ 从最新页开始
→ 摄取新评论
→ 遇到已知 comment_id
→ 停止
```

在该证据完成前 Capability 不宣称增量停止已验收，可使用受控部分刷新。

默认评论完整阈值 50、目标 50、每个一级线程二级目标 5；实际整页返回全部保留。

## 7. 时间窗口

微博搜索有原生 hour/day/week/month，因此前端可以按 Capability 展示这些业务范围。

时间窗口小于调度周期只 Warning；比如每 6 小时运行但只搜 hour，提示潜在发现盲区但允许保存。

重叠窗口按 status_id 去重，不因此重复抓详情/评论。

## 8. Deep Collection

内容页发起时只提交内部 `content_id`，后端解析 status_id。系统未发现的微博可以通过高级 status_id/分享链接入口补抓；解析完成后继续走正式详情/评论/预算链。

Deep 模式可以提高一级/二级目标，但不能绕过 global/run/run_comments/content_comments 硬预算。

## 9. 独立调试和验收

Operation Probe 分别验证搜索、详情、一级评论、二级评论。

Business Pipeline Probe 至少验证：

- 搜索重复 status_id 不重复付费抓评论；
- comment_count 不变时评论请求数为 0；
- 时间排序的一级评论是否能可靠遇到已知 comment_id；
- max_id 为空/不推进时停止；
- 二级评论真实 root/parent 关系只按来源字段映射，不按数组顺序猜。

官方文档允许开始实现请求/分页；平台完成必须有合法脱敏非空真实 Fixture、Mapper Contract Test 和 Real Probe。