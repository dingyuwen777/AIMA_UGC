# 抖音采集逻辑

## 1. 当前状态

抖音 TikHub Operation/Mapper **尚未在 main 实现**。本文记录 Stage 7 已批准的首版目标链路；完成平台兼容验收仍需要合法脱敏非空真实 Fixture、Mapper Contract Test 和 Real Provider Probe。

目标代码路径：

```text
backend/src/aima_ugc/adapters/providers/tikhub/operations/douyin.py
backend/src/aima_ugc/adapters/providers/tikhub/mappers/douyin.py
tests/unit/collection/test_douyin_tikhub_operation.py
tests/unit/collection/test_douyin_tikhub_mapper.py
tests/fixtures/providers/tikhub/douyin/
```

路径只有实现真实存在后才成为机器事实；不得提前创建空壳目录/测试冒充完成。

## 2. 已批准 TikHub Operation

| 业务动作 | Endpoint | 官方文档 |
| --- | --- | --- |
| 关键词视频搜索 | `POST /api/v1/douyin/search/fetch_video_search_v2` | https://docs.tikhub.io/370212780e0 |
| 作品详情 | `GET /api/v1/douyin/app/v3/fetch_one_video_v3` | https://docs.tikhub.io/406098636e0 |
| 一级评论 | `GET /api/v1/douyin/app/v3/fetch_video_comments` | https://docs.tikhub.io/186826225e0 |
| 评论回复 | `GET /api/v1/douyin/app/v3/fetch_video_comment_replies` | https://docs.tikhub.io/186826226e0 |

搜索属于 Douyin Search API family，详情/评论属于 App V3 family；这是不同业务 Operation 的固定选型，不是 fallback。

## 3. 搜索可配置业务参数

Search V2 当前官方提供：

- keyword；
- 排序：综合、最多点赞、最新发布；
- 发布时间：不限、最近一天、最近一周等当前 Capability 验证支持值；
- 其他内容类型/时长筛选只有在官方文档 + Fixture 确认后才对前端开放。

以下由 Operation 内部维护，不开放给普通业务 UI：

```text
cursor
search_id
backtrace
Provider 私有分页状态
```

首屏 cursor=0、search_id 为空；后续严格使用响应状态推进。

## 4. 详情和评论

详情使用 `fetch_one_video_v3`，因为该 V3 Operation 明确用于图文/视频/文章等并改善受限内容覆盖。若未来需要其他详情 endpoint，只能作为独立 Operation 变更，不静默回退。

一级评论 `fetch_video_comments`：

- aweme_id 是内容身份；
- cursor 首屏为 0；
- TikHub 官方明确提示 `count` 应保持默认，否则可能出现问题，因此普通前端**不允许配置评论 page size**。

二级回复同理：item_id + comment_id + cursor；`count` 保持官方默认。

## 5. 抖音标准 Pipeline

```text
fetch_video_search_v2
→ Search Raw
→ Douyin Search Mapper / Observation
→ aweme_id 去重
→ comment_count / allow_comment / 指标比较
→ 必要时 fetch_one_video_v3
→ Comment Eligibility
→ fetch_video_comments
→ 对有回复线程 fetch_video_comment_replies
→ Raw → Mapper → Canonical → Ingestion
```

## 6. 省钱短路

Search V2 响应可表达评论数和评论是否允许；只有在真实 Fixture 确认 Mapper 路径后才能成为机器观察字段。目标决策：

- `allow_comment=false` → 不请求评论；
- `comment_count=0` → 不请求评论；
- 重复内容 `comment_count` 未变化 → 不请求评论；
- 点赞/播放/分享变化但评论数未变化 → 只更新指标，不因此重抓评论；
- 评论数增加 → 增量/受控评论；
- 评论数减少 → 记录下降并受控刷新，不凭部分样本猜删除。

评论默认目标 50、完整阈值 50、每一级线程回复目标 5；但抖音评论没有在当前批准接口中提供业务排序选项，因此 Capability 不能伪造“最新/最热”选择。只有真实 Fixture 证明返回顺序可支持稳定增量停止时才声明 `supports_incremental_comment_sort=true`；否则使用受控部分刷新。

## 7. 可选 enrichment

抖音额外统计/播放量等能力若需要额外付费 Operation，第一版默认关闭。只有 Plan 明确开启、Deep Collection 或业务规则需要时才请求，不能为了“字段越多越好”对每条内容追加调用。

批量详情/统计只有在正式 Pricing + Fixture 证明比逐条调用更合适时使用；不是看到 batch endpoint 就自动切换。

## 8. 时间窗口

抖音 Search V2 有原生发布时间筛选。6 小时调度配最近一天会产生有意重叠；重复 aweme_id 通过 Decision Pipeline 避免再次抓详情/评论。

业务时间范围短于调度周期只 Warning。Provider 不支持的值或非法类型才 Error。

## 9. Deep Collection

已入库内容从内部 `content_id` 发起，后端解析 aweme_id。未发现内容才允许通过抖音分享链接/aweme_id 高级入口建立内容。

Deep Collection 仍走同一 Client/Operation/Budget/Raw/Mapper/Canonical，前端不能直接拿 TikHub Credential 请求第三方。

## 10. 独立调试和验收

Operation Probe 需要逐个验证 Search V2、V3 Detail、一级评论、评论回复的真实参数/分页和 Raw。

Business Pipeline Probe 需要用真实关键词（例如开发者配置的测试关键词）连续运行至少两次，验证：

- 同 aweme_id + comment_count 不变不二次抓评论；
- zero/disabled comments 短路；
- 评论变化触发的动作与真实请求次数一致；
- `count` 没有被业务配置覆盖；
- Raw/Canonical/decisions/XLSX 可追溯。

**完成门禁**：官方文档只允许开始实现 Operation；Mapper 和“抖音已兼容”结论必须有合法脱敏非空真实 Fixture + Contract Test + Real Probe。