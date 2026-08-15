# 微博采集逻辑

## 1. 当前状态

微博 TikHub **Operation 请求构造与有证据的分页状态已经在 Stage 7 实现**。当前仍没有 Weibo Raw→Canonical Mapper、合法脱敏非空真实 Fixture、Real Provider Probe、Capability/默认 Registry 接线，因此只能确认“正式 Operation 已存在”，**不能宣称微博平台已兼容或已进入生产采集链路**。

当前机器路径：

```text
backend/src/aima_ugc/adapters/providers/tikhub/operations/weibo.py
tests/unit/collection/test_weibo_tikhub_operation.py
```

后续 Mapper/Fixture 只有真实实现存在后才成为机器事实：

```text
backend/src/aima_ugc/adapters/providers/tikhub/mappers/weibo.py
tests/unit/collection/test_weibo_tikhub_mapper.py
tests/fixtures/providers/tikhub/weibo/
```

## 2. 已批准并已实现的 TikHub Operation

| 业务动作 | Endpoint | 当前代码状态 | 官方文档 |
| --- | --- | --- | --- |
| 关键词搜索 | `GET /api/v1/weibo/web/fetch_search` | 已实现请求构造；page 状态不猜结果列表字段 | https://docs.tikhub.io/381269400e0 |
| 微博详情 | `GET /api/v1/weibo/app/fetch_status_detail` | 已实现请求构造，当前参数名为 `status_id` | https://docs.tikhub.io/410358103e0 |
| 一级评论 | `GET /api/v1/weibo/app/fetch_status_comments` | 已实现请求构造 + 官方 max_id 路径分页 | https://docs.tikhub.io/410358104e0 |
| 二级评论 | `GET /api/v1/weibo/web_v2/fetch_post_sub_comments` | 已实现请求构造 + 已提取 max_id 状态转换；不猜响应 path | https://docs.tikhub.io/381269410e0 |

Web/App/Web V2 的组合是四个业务 Operation 的固定职责，不是失败 fallback；当前代码不做不同 API family 之间的静默切换。

## 3. 搜索业务参数

Web Search 当前 Operation 接受规范化业务值并映射 TikHub 私有枚举：

| AIMA 业务值 | TikHub `search_type` |
| --- | ---: |
| `general` | 1 |
| `realtime` | 61 |
| `hot` | 60 |
| `video` | 64 |
| `image` | 63 |
| `article` | 21 |

时间范围：

```text
all   → 不发送 time_scope
hour  → time_scope=hour
day   → time_scope=day
week  → time_scope=week
month → time_scope=month
```

`page` 从 1 开始，由 Operation/Worker/Probe 管理，不属于普通业务 UI。

当前官方文档足以证明搜索请求参数，但**没有给出足以冻结 AIMA 搜索结果列表位置/空页字段的稳定非空响应 Fixture**。因此当前 Operation 不解析一个猜测的微博列表路径。`WeiboSearchPagination.from_page_observation()` 只接收上层在未来经真实 Fixture 可靠得到的 `has_results` observation：有结果时 `page+1`，无结果时 `empty_page` 停止。

这意味着“请求构造已实现”不等于“Search Raw Mapper 已完成”。

## 4. 详情和一级评论

详情固定使用 App `fetch_status_detail`，当前官方参数名为：

```text
status_id
```

不能继续沿用泛化的 `id` 名称猜测请求参数。

一级评论使用 App `fetch_status_comments`：

- `status_id`：微博 ID；
- `sort_type=0`：热度；
- `sort_type=1`：最新；
- 首屏不发送 `max_id`；
- 后续页使用上一页返回的 max_id。

当前唯一实现的响应游标提取路径严格来自官方文档：

```text
$.data.moreInfo.params.max_id
```

停止规则：

- max_id 为空 → `provider_exhausted`；
- max_id 与上一次相同 → `pagination_not_advanced`；
- 其他非空新 max_id → 继续。

Operation **不读取或猜测评论数组字段**；评论内容和业务字段必须等合法真实 Fixture 后由 Mapper 固化。

## 5. 二级评论

二级评论固定使用 Web V2 `fetch_post_sub_comments`：

```text
id      = 一级/root 评论 ID
max_id  = 首屏空字符串，后续游标
```

官方接口还存在可选 `count`，但当前 Operation 不覆盖它，避免把 Provider page size 当作普通业务配置。

当前官方资料说明后续请求使用返回的 max_id，但没有提供本仓库可以可靠冻结的响应 JSON path。因此当前实现刻意拆成两层：

```text
未来 Fixture/Adapter 可靠提取 returned_max_id
→ WeiboSubCommentPagination.from_returned_max_id(...)
→ 判断继续 / cursor_unavailable / pagination_not_advanced
```

本单元不猜 `data.xxx.max_id` 之类路径。合法脱敏真实 Fixture 到位后，再在同一个正式 Operation/Mapper 边界补充实际提取逻辑。

## 6. 微博标准 Pipeline

当前已经建立的部分：

```text
规范化业务参数
→ Weibo Operation
→ TikHub 请求描述 / 已证明的 Pagination State
```

完整目标链仍是：

```text
fetch_search（默认实时/最新）
→ Search Raw
→ Weibo Mapper / Observation
→ status_id 去重
→ CollectionDecisionService
→ 必要时 fetch_status_detail
→ Comment Eligibility
→ fetch_status_comments
→ 对有回复线程 fetch_post_sub_comments
→ Raw → Mapper → Canonical → Ingestion
```

后半段不能因为 Operation 代码已存在而自动视为完成。

## 7. 省钱与增量评论

通用短路目标保持：可靠 `comment_count=0` 不请求评论；重复微博 `comment_count` 未变化不请求；其他指标变化不自动重抓评论。

一级评论官方支持最新排序，因此**未来**在合法 Fixture/Real Probe 证明“最新排序 + comment_id 停止”稳定后，可以启用增量：

```text
comment_count 增加
→ sort_type=1
→ 从最新页开始
→ 摄取新评论
→ 遇到已知 comment_id
→ 停止
```

当前没有对应真实评论 Fixture/Probe，因此 Capability 仍不能宣称稳定增量停止；Operation 也没有实现“遇到已知 comment_id”这一未经证据支持的规则。

默认评论完整阈值 50、目标 50、每个一级线程二级目标 5 属上层 Decision/Plan 业务策略，不改变 Provider 自身分页事实。

## 8. 时间窗口

微博 Web Search 有原生 `hour/day/week/month` 时间筛选；`all` 表示不限制。

时间窗口小于调度周期只 Warning。例如每 6 小时运行但搜索 hour，会提示潜在发现盲区但允许保存；是否暴露给前端仍由未来 Weibo Capability 机器 Contract 决定，而不是 Vue 自己写 TikHub 枚举。

重叠窗口后续按 status_id 去重，不因此重复抓详情/评论。

## 9. Deep Collection

内容页发起时最终只提交内部 `content_id`，后端解析 status_id 和 Provider Config。系统未发现的微博才通过高级 status_id/分享链接入口补抓；解析完成后继续走正式 Provider Route/详情/评论/Budget/Raw/Mapper/Canonical。

Deep 模式可以提高一级/二级目标，但不能绕过 global/run/run_comments/content_comments 硬预算。

## 10. 独立调试和验收

当前 Operation 自动化测试入口：

```bash
uv run pytest tests/unit/collection/test_weibo_tikhub_operation.py -q
```

它验证：

- 当前官方搜索 `search_type/time_scope/page` 映射；
- 详情和一级评论使用 `status_id`；
- 一级评论只按官方 `data.moreInfo.params.max_id` 推进；
- 二级评论 `id/max_id` 请求和不覆盖 `count`；
- 二级 max_id 状态转换不猜响应 JSON path。

后续 Real Provider Probe 必须分别验证 Search、Detail、Comments、Sub-comments 的真实响应。平台兼容完成仍要求：

```text
合法脱敏非空真实 Fixture
+ Mapper Contract Test
+ Real Provider Probe
```

Business Pipeline Probe 还至少验证：

- 搜索重复 status_id 不重复付费抓评论；
- `comment_count` 不变时评论请求数为 0；
- 时间排序是否能可靠遇到已知 comment_id；
- 一级 max_id 为空/不推进时停止；
- 二级真实 max_id path、root/parent 关系只按来源字段映射，不按数组顺序猜。

官方文档与当前 Operation Unit Test 都不能替代这些真实兼容证据。
