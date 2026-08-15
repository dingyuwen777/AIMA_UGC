---
schema: rvc-change/v1
id: CHG-20260815-stage7-douyin-operation
title: 建立 Stage 7 抖音 TikHub Operation 与分页状态机
level: L2
status: ready_for_review
owner: dingyuwen777
branch: feature/stage7-douyin-operation
created: 2026-08-15
updated: 2026-08-15
depends_on: [CHG-20260815-stage7-decision-capability]
affected_areas: [collection, provider, testing, documentation, blueprint]
affected_paths: [backend/src/aima_ugc/adapters/providers/tikhub/operations/douyin.py, tests/unit/collection/test_douyin_tikhub_operation.py, docs/collection/douyin.md, backend/src/aima_ugc/modules/collection/README.md, docs/blueprint/README.md, docs/blueprint/08-采集策略与平台能力.md]
contracts: []
data_changes: []
---

# 目标与当前结果

按 Blueprint 08 已批准且 2026-08-15 重新核验的 TikHub 官方接口，建立抖音首版四类正式 Operation 的请求构造与分页状态机：Search V2、App V3 详情、App V3 一级评论、App V3 评论回复。该单元只建立 Provider 请求/分页机器事实，不在没有合法脱敏非空真实 Fixture 时猜 Mapper 字段或宣称抖音平台已兼容。

当前代码已经建立 Search V2 规范化业务参数映射、搜索分页状态、V3 Detail/Comments/Replies 请求构造，以及评论/回复仅依赖 `cursor + has_more` 的基础分页。Douyin Mapper、合法脱敏非空真实 Fixture、Real Probe、Capability/默认 Registry 接线仍明确不在当前结果中。

# 成功标准

- [x] 关键词搜索固定使用 `POST /api/v1/douyin/search/fetch_video_search_v2`，首次 `cursor=0`、`search_id/backtrace=''`，后续分页使用上次响应状态。
- [x] 规范化业务排序 `general/most_liked/latest` 映射 TikHub `sort_type=0/1/2`；发布时间 `all/1d/7d/180d` 映射 `publish_time=0/1/7/180`。
- [x] 搜索视频时长 `all/under_1m/1_5m/over_5m` 与内容类型 `all/video/image/article` 由 Operation 映射到当前官方值，调用方不直接维护第三方字符串。
- [x] 搜索分页处理 provider exhausted、空页、cursor 不推进和重复页；重复页按 aweme_id 集合判断，不因返回顺序变化漏掉防循环。
- [x] 详情固定使用 `GET /api/v1/douyin/app/v3/fetch_one_video_v3?aweme_id=...`。
- [x] 一级评论固定使用 `GET /api/v1/douyin/app/v3/fetch_video_comments`；首屏 `cursor=0`，后续使用响应 cursor；不传业务自定义 `count`，保持 TikHub 官方默认。
- [x] 评论回复固定使用 `GET /api/v1/douyin/app/v3/fetch_video_comment_replies`；传 `item_id/comment_id/cursor`，不传业务自定义 `count`。
- [x] 评论类分页只按当前官方 `cursor/has_more` 处理 provider exhausted 与分页不推进；在真实 Fixture 证明评论数组字段前不猜空页字段或稳定增量停止。
- [x] Red 测试先因 `operations.douyin` 尚不存在而正确失败；Green 后已有 Collection/Content/Provider Contract Unit 68 passed 的中间证据，最终 head 仍需重新通过完整 CI。
- [x] 不新增 Migration、数据库表、依赖、公共 HTTP API、Mapper、Capability、Registry 或前端代码。
- [x] `docs/collection/douyin.md`、Collection README、Blueprint README、Blueprint 08 如实区分“Operation 已实现”和“Mapper/Fixture/Real Probe/Capability 未完成”。

# 范围

- 抖音 TikHub Search V2 请求体业务参数映射。
- Search V2 cursor、search_id、backtrace、has_more 和结果 aweme_id 去重分页状态。
- V3 Detail/Comments/Comment Replies 请求构造。
- 评论 cursor/has_more 分页推进事实。
- Unit Test、平台开发文档与 Blueprint 当前状态同步。

# 非目标

- 不实现 Douyin Raw→Canonical Mapper。
- 不提交未经脱敏的真实 Provider 响应。
- 不把官方文档字段说明冒充真实非空 Fixture 验证。
- 不注册 `DOUYIN_TIKHUB_CAPABILITY` 到当前默认 Provider Registry；平台可运行 Capability 要在 Operation + 合法 Fixture/Mapper/Probe 证据闭环后建立。
- 不实现 Plan、Budget、Scheduler、Stage 8 API/前端。
- 不实现静默 fallback 到 Douyin Web/V1 或其他 endpoint。

# 必须保持不变

- 每个业务 Operation 使用 Blueprint 08 批准的唯一主 endpoint，不做通用 fallback。
- Provider 私有 cursor/search_id/backtrace 不进入前端业务 Contract。
- `count` 对 App V3 评论/回复保持 TikHub 官方默认，不暴露业务 page size。
- 外部 ID 使用字符串；Operation 不访问数据库、不写 Artifact、不做 Canonical Mapper。
- Secret 不进入请求描述、测试、日志或 Git。

# 已确认关键决策与一手资料

2026-08-15 已重新核验 TikHub 官方文档：

- Search V2: https://docs.tikhub.io/370212780e0
- Detail V3: https://docs.tikhub.io/406098636e0
- Comments V3: https://docs.tikhub.io/186826225e0
- Comment Replies V3: https://docs.tikhub.io/186826226e0

官方当前说明 Search V2 首屏 `cursor=0`、`search_id=''`，支持 sort 0/1/2、publish_time 0/1/7/180；评论和回复的 `count` 均提示保持默认，否则可能出现问题。本 Change 使用这些已批准和当前核验的一手事实，不切换到其他候选 endpoint。

# Red → Green

## Red

PR #38 Red head `f261da0ccec42abfcf34b2dca81ed879daed9153`，Stage 6 XHS Vertical Slice run `31856482313` / Unit job `94942102485`：

- 锁定 Python/uv 环境安装成功；
- pytest 在 collection 阶段失败；
- `ModuleNotFoundError: No module named 'aima_ugc.adapters.providers.tikhub.operations.douyin'`；
- `Interrupted: 1 error during collection`；
- pytest 退出码 2。

失败来自本 Change 目标生产模块尚不存在，不是依赖、数据库或旧测试故障。

## Green 中间证据

首次 Green 后的 Stage 6 Unit job 完整日志显示：

- `68 passed`；
- 0 failed；
- pytest 退出码 0。

同一 head 的 Stage 6 Quality 与 PostgreSQL jobs 也为 success。随后 Review 增加“乱序但 aweme_id 集合相同仍视为重复页”的回归行为、同步 Blueprint README/08 和平台/模块 README；最终 head 必须重新跑新鲜 CI 后才允许 Ready/merge。

# 两阶段 Review

## 第一阶段：需求符合性

- 四个 endpoint 与 Blueprint 08 已批准主链一致，没有静默切换 Web/V1 或增加 fallback。
- Search 参数只暴露规范化业务值，Provider 私有 cursor/search_id/backtrace 保持 Operation 内部状态。
- 评论/回复没有覆盖官方要求保持默认的 `count`。
- 没有实现 Mapper、Capability、Registry、Plan、Budget、Scheduler 或 Stage 8 UI，非目标未越界。
- 文档明确 Operation 已实现不等于抖音平台兼容完成。

## 第二阶段：代码质量

- Operation 是纯请求/分页逻辑，没有 DB、Artifact、Secret 或 Mapper 副作用。
- Search 只读取分页去重所需的 `business_data[].data.aweme_info.aweme_id`，不解释标题/作者/指标等业务字段。
- 评论分页只依赖已确认的 `cursor/has_more`，没有在缺 Fixture 时猜评论数组或增量停止字段。
- Review 发现重复页最初要求 ID 顺序完全一致，可能漏掉仅排序变化的完整重复页；已改为长度相同且 aweme_id 集合相同即停止，并补乱序回归测试。
- 无依赖、锁文件、Migration、公共 Contract/API 或前端生成物变化。

# 实施与验证计划

最终 PR head 需要执行并读取新鲜结果：

```text
uv lock --check
uv run ruff format --check backend tests scripts
uv run ruff check backend tests scripts
uv run mypy backend/src
uv run pytest tests/unit/collection -q
uv run pytest tests/unit/content -q
uv run pytest tests/contracts/test_provider_v1.py -q
uv run python scripts/quality/check_architecture.py
uv run python scripts/quality/check_table_ownership.py
uv run python scripts/quality/scan_secrets.py
uv run python scripts/quality/check_docs.py
```

相关 workflow 还会继续执行当前 Stage 6 PostgreSQL/Migration 回归和主 CI。当前执行宿主没有可用本地 AIMA checkout；Red/Green 与完整命令证据使用 GitHub Actions，不能把远端状态当用户本地工作区状态。

# 文档影响

已同步：

- `docs/collection/douyin.md`：当前 Operation、参数映射、分页、未验证边界；
- `backend/src/aima_ugc/modules/collection/README.md`：生产入口、独立验证与限制；
- `docs/blueprint/README.md`：Stage 7 当前机器进度与剩余单元；
- `docs/blueprint/08-采集策略与平台能力.md`：Operation Matrix 当前状态和 Stage 7 门禁。

Blueprint 08 的 endpoint/业务设计没有变化，只同步“抖音 Operation/分页已实现、Mapper/Fixture/Probe 未完成”的当前状态。

# 兼容、依赖、Migration、部署和回滚

- 现有 Contract/API/Schema：无变化。
- Migration/数据库：无变化。
- 依赖/锁文件：无变化。
- 部署：无变化，不新增进程/配置。
- 回滚：回滚本 Change 的 Operation/测试/文档提交即可，无数据回滚。

# Git

- 基线 main：`86bcafb84005858af865e506ed4885dbceb2ffb0`
- 当前 main 已包含 Provider Config Change 的后续归档提交；PR #38 当前与 main 可合并，归档 Change 与本 PR 路径无冲突。
- 分支：`feature/stage7-douyin-operation`
- PR：#38，Draft；最终 CI 成功后转 Ready
- 正确 Red：head `f261da0ccec42abfcf34b2dca81ed879daed9153`，run `31856482313` / job `94942102485`
- 中间 Green：Collection/Content/Provider Contract Unit `68 passed`
- 最终 CI：待最新 head 完成
- 合并：未执行
- Change：ready_for_review，仍在 `changes/active/`
