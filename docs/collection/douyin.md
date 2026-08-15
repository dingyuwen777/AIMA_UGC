# 抖音采集逻辑

## 1. 当前状态

抖音 TikHub **Operation 请求构造与基础分页状态机已在 Stage 7 实现**；Raw→Canonical Mapper、合法脱敏非空真实 Fixture、Real Provider Probe、平台 Capability/默认 Registry 接线仍未完成。因此当前只能确认“正式 Operation 代码已存在”，**不能宣称抖音平台已经兼容或可进入生产采集链路**。

当前机器路径：

```text
backend/src/aima_ugc/adapters/providers/tikhub/operations/douyin.py
tests/unit/collection/test_douyin_tikhub_operation.py
```

后续 Mapper/Fixture 目标路径只有真实实现存在后才成为机器事实：

```text
backend/src/aima_ugc/adapters/providers/tikhub/mappers/douyin.py
tests/unit/collection/test_douyin_tikhub_mapper.py
tests/fixtures/providers/tikhub/douyin/
```

## 2. 已批准并已实现的 TikHub Operation

| 业务动作 | Endpoint | 当前代码状态 | 官方文档 |
| --- | --- | --- | --- |
| 关键词视频搜索 | `POST /api/v1/douyin/search/fetch_video_search_v2` | 已实现请求构造 + 搜索分页状态 | https://docs.tikhub.io/370212780e0 |
| 作品详情 | `GET /api/v1/douyin/app/v3/fetch_one_video_v3` | 已实现请求构造 | https://docs.tikhub.io/406098636e0 |
| 一级评论 | `GET /api/v1/douyin/app/v3/fetch_video_comments` | 已实现请求构造 + cursor/has_more 分页 | https://docs.tikhub.io/186826225e0 |
| 评论回复 | `GET /api/v1/douyin/app/v3/fetch_video_comment_replies` | 已实现请求构造 + cursor/has_more 分页 | https://docs.tikhub.io/186826226e0 |

搜索属于 Douyin Search API family，详情/评论属于 App V3 family；这是不同业务 Operation 的固定职责，不是 fallback。当前代码没有 Web/V1 静默回退。

## 3. Search V2 业务参数映射

Operation 接受规范化业务值，再映射 TikHub 私有枚举：

| 业务语义 | AIMA 值 | TikHub 值 |
| --- | --- | --- |
| 排序 | `general` / `most_liked` / `latest` | `sort_type=0/1/2` |
| 发布时间 | `all` / `1d` / `7d` / `180d` | `publish_time=0/1/7/180` |
| 时长 | `all` / `under_1m` / `1_5m` / `over_5m` | `filter_duration=0/0-1/1-5/5-10000` |
| 内容类型 | `all` / `video` / `image` / `article` | `content_type=0/1/2/3` |

这些映射已经进入 Operation 自动化测试，但**尚未注册为面向 Plan/前端的 Douyin Capability**。只有对应 Mapper/Fixture 等机器事实补齐后，才能把实际可运行能力接入默认 Provider Registry；前端仍不能自己保存 TikHub 私有枚举。

以下始终由 Operation 内部维护，不开放给普通业务 UI：

```text
cursor
search_id
backtrace
Provider 私有分页状态
```

首屏固定 `cursor=0`、`search_id=''`、`backtrace=''`；后续把上一页返回的 cursor/search_id/backtrace 原样带入下一页请求。

## 4. 搜索分页状态机

Search V2 当前只依据已经由官方文档明确、且不需要 Mapper 猜测的结构推进：

```text
business_data
cursor
has_more
search_id
backtrace
```

停止条件：

- `business_data` 为空 → `empty_page`；
- 页面 aweme_id 集合与上一页完全重复 → `duplicate_page`；
- Provider `has_more` 明确结束 → `provider_exhausted`；
- cursor 没有推进或倒退 → `pagination_not_advanced`。

Operation 只从 `business_data[].data.aweme_info.aweme_id` 提取分页去重所需稳定 ID，不解释标题、作者、发布时间、指标等 Canonical 业务字段；这些字段必须等真实 Fixture 后由 Mapper 负责。

## 5. 详情和评论

详情固定使用 `fetch_one_video_v3`，参数为 `aweme_id`。

一级评论 `fetch_video_comments`：

- `aweme_id` 是内容身份；
- cursor 首屏为 0；
- TikHub 官方明确提示 `count` 应保持默认，因此正式 Operation **不传 `count`**，普通前端也不能配置评论 page size。

二级回复 `fetch_video_comment_replies`：

- 使用 `item_id + comment_id + cursor`；
- 同样不传 `count`。

当前评论/回复分页只使用官方明确的 `cursor + has_more` 判断是否继续和是否推进。由于仓库还没有合法脱敏非空评论/回复 Fixture，本单元**没有猜测评论数组字段，也没有实现“空评论页”或“遇到已知 comment_id”增量停止**。这些行为必须在真实 Fixture/Real Probe 证明响应结构后补充。

## 6. 抖音标准 Pipeline

当前已实现部分：

```text
规范化业务参数
→ Douyin Operation
→ TikHub 请求描述 / Pagination State
```

完整目标链仍是：

```text
fetch_video_search_v2
→ Search Raw
→ Douyin Search Mapper / Observation
→ aweme_id 去重
→ CollectionDecisionService
→ 必要时 fetch_one_video_v3
→ fetch_video_comments / replies
→ Raw → Mapper → Canonical → Ingestion
```

第二条链路尚未因 Operation 已存在而自动成立。

## 7. 省钱短路

Search V2 响应可能包含评论数和评论许可，但只有合法脱敏真实 Fixture 确认 Mapper 路径后才能成为 AIMA 的机器观察字段。目标 Decision 仍按 Blueprint 08：

- `allow_comment=false` → 不请求评论；
- `comment_count=0` → 不请求评论；
- 重复内容 `comment_count` 未变化 → 不请求评论；
- 点赞/播放/分享变化但评论数未变化 → 不因此重抓评论；
- 评论数增加 → 经 Capability/Fixture 证明后选择增量或受控刷新；
- 评论数减少 → 记录下降并受控刷新，不凭部分样本猜删除。

当前评论 Operation 没有批准的业务排序参数，Capability 不能伪造“最新/最热”。只有真实 Fixture/Probe 证明稳定排序和停止语义后才允许声明增量能力。

## 8. 时间窗口

抖音 Search V2 有原生发布时间筛选。6 小时调度配最近一天会产生有意重叠；重复 aweme_id 后续由统一 Decision Pipeline 减少详情/评论重复费用。

业务时间范围短于调度周期只 Warning。Provider 不支持的值或非法类型才 Error。

## 9. Deep Collection

已入库内容最终从内部 `content_id` 发起，后端解析 aweme_id 与 Provider Config。未发现内容才允许通过抖音分享链接/aweme_id 高级入口建立内容。

Deep Collection 仍必须走同一 Provider Route/Operation/Budget/Raw/Mapper/Canonical；前端不能直接拿 TikHub Credential 请求第三方。

## 10. 独立调试和验收

当前 Operation 自动化测试覆盖：

```bash
uv run pytest tests/unit/collection/test_douyin_tikhub_operation.py -q
```

它验证 endpoint、规范化参数映射、Search 状态继承、空/重复/Provider 结束/分页不推进，以及评论/回复不覆盖 `count`。

后续 Operation Real Probe 仍需要逐个验证真实 Search V2、V3 Detail、一级评论和回复响应。Mapper 和“抖音已兼容”结论必须满足：

```text
合法脱敏非空真实 Fixture
+ Mapper Contract Test
+ Real Provider Probe
```

Business Pipeline Probe 还要连续运行至少两次，验证重复 comment_count 不变不二次抓评论、零评论/关闭短路、评论变化动作、实际请求次数、Raw/Canonical/Decision/XLSX 可追溯。官方文档和当前 Operation Unit Test 都不能替代这些真实兼容证据。
