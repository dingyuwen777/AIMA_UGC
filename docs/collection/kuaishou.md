# 快手采集逻辑

## 1. 当前状态

快手 TikHub Operation/Mapper **尚未在 main 实现**。本文冻结 Stage 7 首版主链路。平台完成仍需要合法脱敏非空真实 Fixture、Mapper Contract Test 和 Real Provider Probe。

目标路径：

```text
backend/src/aima_ugc/adapters/providers/tikhub/operations/kuaishou.py
backend/src/aima_ugc/adapters/providers/tikhub/mappers/kuaishou.py
tests/unit/collection/test_kuaishou_tikhub_operation.py
tests/unit/collection/test_kuaishou_tikhub_mapper.py
tests/fixtures/providers/tikhub/kuaishou/
```

## 2. 已批准 TikHub Operation

| 业务动作 | Endpoint | 官方文档 |
| --- | --- | --- |
| 视频搜索 | `GET /api/v1/kuaishou/app/search_video_v2` | https://docs.tikhub.io/467698481e0 |
| 作品详情 | `GET /api/v1/kuaishou/app/fetch_one_video` | https://docs.tikhub.io/467698469e0 |
| 一级评论 | `GET /api/v1/kuaishou/web/fetch_one_video_comment` | https://docs.tikhub.io/336972174e0 |
| 二级评论 | `GET /api/v1/kuaishou/web/fetch_one_video_sub_comment` | https://docs.tikhub.io/343506804e0 |

App 搜索/详情 + Web 评论是四个业务 Operation 的明确首版选型，不是运行时 fallback。

TikHub App 目录也存在评论能力；在其具体 Contract、价格和真实 Fixture 被单独验证前，不因为“App 看起来更新”而静默改掉本表主 Operation。

## 3. 搜索能力很有限，前端不能伪造选项

App Search V2 当前官方只明确：

```text
keyword
pcursor
```

`pcursor` 是技术分页，首页为空，后续使用响应值。

当前批准 Operation **没有排序参数和发布时间筛选参数**，因此 Capability 必须表达：

```text
native_time_filter = false
supported_sort_modes = provider_default only
```

前端不能给快手显示“最新/最多点赞/最近一天”等看似可用但实际上没有传给当前 Provider 的选项。

如果以后实现本地发布时间边界，必须标明是本地停止条件并用 Fixture/Probe 证明，不得说 TikHub Search V2 已原生过滤。

## 4. 搜索成本需要特别控制

TikHub 官方当前明确说明 App `search_video_v2` **收费更贵，但稳定性更高**，具体价格以用户后台/Endpoint Pricing 为准。因此快手首版优先用以下机制省钱：

1. 关键词搜索结果先 Raw/Mapper，再按 photo_id 去重；
2. 重复内容有效指标/评论数未变化，不请求详情/评论；
3. 明确零评论不请求评论；
4. 评论目标使用自适应 50，不默认全量；
5. 单内容和 Run 评论预算防止热门内容扩散费用；
6. 预计费用使用当前 endpoint Pricing，不在文档硬编码单价。

不要为了减少搜索费用切到未经批准/未验证的便宜接口；价格变化或替代 endpoint 要单独评估数据质量和总成本。

## 5. 详情和评论

App Detail `fetch_one_video` 使用 photo_id，官方说明支持数字 ID 和短字符串 eID；Canonical 外部 ID 一律按字符串保存。

Web 一级评论：

```text
photo_id
pcursor
```

首屏 pcursor 为空，后续使用响应 pcursor。

Web 二级评论：

```text
photo_id
root_comment_id
pcursor
```

同样使用 pcursor 翻页。

当前 Web 评论 Operation 没有批准业务排序选项，所以普通 UI 不显示“最新/最热”评论排序。只有未来主 Operation 变更并完成 Fixture/Probe 后再更新 Capability。

## 6. 快手标准 Pipeline

```text
search_video_v2
→ Search Raw
→ Kuaishou Mapper / Observation
→ photo_id 去重
→ 指标/comment_count 比较
→ 必要时 app/fetch_one_video
→ Comment Eligibility
→ web/fetch_one_video_comment
→ 对有回复线程 web/fetch_one_video_sub_comment
→ Raw → Mapper → Canonical → Ingestion
```

## 7. 评论省钱规则

通用规则保持：

- 可靠 `comment_count=0` → 不请求评论；
- 重复内容 comment_count 未变化 → 不请求；
- 其他互动变化但评论数不变 → 不因此重抓评论；
- 评论数增加 → 当前接口没有批准稳定最新排序时，使用受控部分刷新而不是假装增量；
- 评论数下降 → 记录下降 + 受控刷新，不凭部分样本猜删除。

默认完整阈值 50、目标 50、每个一级线程二级目标 5；如果 comment/reply 返回页超过目标，整页全部保存。

## 8. 时间窗口与调度

因为 Search V2 没有原生时间范围：

- 前端不能把“最近一天/一周”显示为 Provider 原生筛选；
- 需要业务时间边界时只能在实际返回时间字段经 Fixture 验证后做本地停止/筛选；
- 本地边界和调度周期不匹配只 Warning，不阻止；
- 无法可靠判断发布时间时宁可继续按显式页数/预算停止，也不能伪造发布时间。

## 9. Deep Collection

已入库内容从内部 `content_id` 发起，后端解析 photo_id 和 Provider。系统未发现的内容可以通过 photo_id/快手分享链接高级入口补抓。

Deep Collection 仍使用相同 App Detail + Web Comment Operations，并受数据库 Budget；不能绕过预算或直接从浏览器调 TikHub。

## 10. 独立调试和验收

Operation Probe 至少验证：

- Search V2 pcursor 首页/下一页/末页；
- App Detail 数字 photo_id/eID；
- Web root comments pcursor；
- Web subcomments root_comment_id + pcursor；
- Provider 返回空页/pcursor 不推进时停止。

Business Pipeline Probe 连续两次运行，重点确认昂贵 Search V2 后是否通过去重和 comment_count 判断避免额外详情/评论请求。

**完成门禁**：当前官方文档允许开始 Operation/分页实现；没有快手合法脱敏非空真实 Fixture、Mapper Contract Test 和 Real Probe 前，不得称“快手已兼容”。