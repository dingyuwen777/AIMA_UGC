---
schema: rvc-change/v1
id: CHG-20260815-stage7-douyin-operation
title: 建立 Stage 7 抖音 TikHub Operation 与分页状态机
level: L2
status: in_progress
owner: dingyuwen777
branch: feature/stage7-douyin-operation
created: 2026-08-15
updated: 2026-08-15
depends_on: [CHG-20260815-stage7-decision-capability]
affected_areas: [collection, provider, testing, documentation]
affected_paths: [backend/src/aima_ugc/adapters/providers/tikhub/operations/douyin.py, tests/unit/collection/test_douyin_tikhub_operation.py, docs/collection/douyin.md, backend/src/aima_ugc/modules/collection/README.md]
contracts: []
data_changes: []
---

# 目标

按 Blueprint 08 已批准且 2026-08-15 重新核验的 TikHub 官方接口，建立抖音首版四类正式 Operation 的请求构造与分页状态机：Search V2、App V3 详情、App V3 一级评论、App V3 评论回复。该单元只建立 Provider 请求/分页机器事实，不在没有合法脱敏非空真实 Fixture 时猜 Mapper 字段或宣称抖音平台已兼容。

# 成功标准

- [ ] 关键词搜索固定使用 `POST /api/v1/douyin/search/fetch_video_search_v2`，首次 `cursor=0`、`search_id/backtrace=''`，后续分页使用上次响应状态。
- [ ] 规范化业务排序 `general/most_liked/latest` 映射 TikHub `sort_type=0/1/2`；发布时间 `all/1d/7d/180d` 映射 `publish_time=0/1/7/180`。
- [ ] 搜索视频时长与内容类型只接受 TikHub 当前官方支持值，并由 Operation 映射第三方枚举；调用方不直接维护第三方字符串。
- [ ] 搜索分页能处理 provider exhausted、空页、cursor 不推进和重复页，不复制 Mapper 逻辑。
- [ ] 详情固定使用 `GET /api/v1/douyin/app/v3/fetch_one_video_v3?aweme_id=...`。
- [ ] 一级评论固定使用 `GET /api/v1/douyin/app/v3/fetch_video_comments`；首屏 `cursor=0`，后续使用响应 cursor；不传业务自定义 `count`，保持 TikHub 官方默认。
- [ ] 评论回复固定使用 `GET /api/v1/douyin/app/v3/fetch_video_comment_replies`；传 `item_id/comment_id/cursor`，不传业务自定义 `count`。
- [ ] 评论类分页至少按官方 `cursor/has_more` 处理 provider exhausted 与分页不推进；在真实 Fixture 证明评论数组字段前不猜空页字段或稳定增量停止。
- [ ] Red 测试先因 `operations.douyin` 尚不存在而正确失败；Green 后相关 Unit/Quality/主 CI 成功。
- [ ] 不新增 Migration、数据库表、依赖、公共 HTTP API、Mapper、Capability、Registry 或前端代码。
- [ ] `docs/collection/douyin.md` 和 Collection README 如实区分“Operation 已实现”和“Mapper/Fixture/Real Probe 尚未完成”。

# 范围

- 抖音 TikHub Search V2 请求体业务参数映射。
- Search V2 游标、search_id、backtrace、has_more 和结果 ID 去重分页状态。
- V3 Detail/Comments/Comment Replies 请求构造。
- 评论 cursor/has_more 分页推进事实。
- Unit Test 与平台开发文档。

# 非目标

- 不实现 Douyin Raw→Canonical Mapper。
- 不提交未经脱敏的真实 Provider 响应。
- 不把官方文档字段说明冒充真实非空 Fixture 验证。
- 不注册 `DOUYIN_TIKHUB_CAPABILITY` 到当前默认 Provider Registry；平台可运行 Capability 要在对应 Operation + 合法 Fixture/Mapper 证据闭环后建立。
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

# 实施步骤

[步骤 1：Red]
→ 修改范围：`tests/unit/collection/test_douyin_tikhub_operation.py`
→ 预期结果：测试明确四类 endpoint、业务参数映射和分页行为，并因目标生产模块尚不存在而失败。
→ 验证方式：PR GitHub Actions 中 pytest 目标错误完整日志与退出码。

[步骤 2：Green]
→ 修改范围：`backend/src/aima_ugc/adapters/providers/tikhub/operations/douyin.py`
→ 预期结果：唯一生产 Operation 实现请求构造与分页状态机；无 DB/Mapper/Secret 副作用。
→ 验证方式：目标 Unit Test + 现有 Collection Unit 回归。

[步骤 3：文档与 Review]
→ 修改范围：`docs/collection/douyin.md`、Collection README（如导航/当前状态受影响）。
→ 预期结果：文档描述当前机器事实，不把 Operation 完成写成 Mapper/平台兼容完成。
→ 验证方式：文档门禁 + 两阶段 Review + PR diff。

# 验证计划

```text
uv lock --check
uv run ruff format --check backend tests scripts
uv run ruff check backend tests scripts
uv run mypy backend/src
uv run pytest tests/unit/collection/test_douyin_tikhub_operation.py -q
uv run pytest tests/unit/collection -q
uv run python scripts/quality/check_architecture.py
uv run python scripts/quality/check_table_ownership.py
uv run python scripts/quality/scan_secrets.py
uv run python scripts/quality/check_docs.py
```

当前执行宿主没有可用本地 AIMA checkout；Red/Green 与完整命令证据使用 GitHub Actions，不能把远端状态当用户本地工作区状态。

# 文档影响

只同步抖音平台实现状态和 Collection 调试导航；不修改 Blueprint Operation Matrix，因为端点选择未变化。若实现发现官方一手事实与 Blueprint 冲突，则停止并按 L3 设计变更处理，而不是静默换 endpoint。

# 兼容、依赖、Migration、部署和回滚

- 现有 Contract/API/Schema：无变化。
- Migration/数据库：无变化。
- 依赖/锁文件：无变化。
- 部署：无变化。
- 回滚：回滚本 Change 的 Operation/测试/文档提交即可，无数据回滚。

# Git

- 基线 main：`86bcafb84005858af865e506ed4885dbceb2ffb0`
- 分支：`feature/stage7-douyin-operation`
- PR：待 Red 提交后创建
- CI：待本轮实际运行
- 合并：未执行
- Change：in_progress
