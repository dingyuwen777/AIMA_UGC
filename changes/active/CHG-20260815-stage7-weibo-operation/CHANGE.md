---
schema: rvc-change/v1
id: CHG-20260815-stage7-weibo-operation
title: 建立 Stage 7 微博 TikHub Operation 与分页状态机
level: L2
status: in_progress
owner: dingyuwen777
branch: feature/stage7-weibo-operation
created: 2026-08-15
updated: 2026-08-15
depends_on: [CHG-20260815-stage7-decision-capability]
affected_areas: [collection, provider, testing, documentation]
affected_paths: [backend/src/aima_ugc/adapters/providers/tikhub/operations/weibo.py, tests/unit/collection/test_weibo_tikhub_operation.py, docs/collection/weibo.md, backend/src/aima_ugc/modules/collection/README.md]
contracts: []
data_changes: []
---

# 目标

按 Blueprint 08 已批准并于 2026-08-15 重新核验的 TikHub 官方接口，建立微博首版四类 Operation：Web 搜索、App 详情、App 一级评论、Web V2 二级评论。只实现官方资料足以证明的请求构造和分页状态；没有合法脱敏非空真实 Fixture 的响应列表字段不猜、不提前写 Mapper，也不宣称微博平台兼容完成。

# 成功标准

- [ ] 搜索固定使用 `GET /api/v1/weibo/web/fetch_search`；页码从 1 开始，规范化 `general/realtime/hot/video/image/article` 映射当前官方 `search_type=1/61/60/64/63/21`。
- [ ] 搜索时间 `all/hour/day/week/month` 中，`all` 不发送 `time_scope`，其余映射官方同名值；页码状态只负责 `page+1`，搜索结果列表位置/空页识别留待合法真实 Fixture 证明后接线。
- [ ] 详情固定使用 `GET /api/v1/weibo/app/fetch_status_detail`，参数名以当前官方文档为准使用 `status_id`。
- [ ] 一级评论固定使用 `GET /api/v1/weibo/app/fetch_status_comments`，使用 `status_id`、可选 `max_id`、`sort_type=0/1`；首屏不传 `max_id`。
- [ ] 一级评论严格按官方 `$.data.moreInfo.params.max_id` 提取下一游标；返回空值或与上一次相同即停止，不猜评论数组字段。
- [ ] 二级评论固定使用 `GET /api/v1/weibo/web_v2/fetch_post_sub_comments`，`id` 表示根评论 ID，首次 `max_id=''`，后续使用返回 max_id；当前不覆盖可选 `count`，避免把 Provider page size 暴露为业务参数。
- [ ] 二级评论的游标状态机可根据“上次 max_id + 已解析返回 max_id”判断继续/不推进；官方没有给稳定响应 JSON path，因此本单元不猜提取路径，待合法 Fixture 后补足。
- [ ] Red 先因 `operations.weibo` 不存在而正确失败；Green 后目标 Unit、Collection 回归、Quality、主 CI 成功。
- [ ] 不新增 Mapper、Capability、Registry、Migration、数据库、依赖、公共 HTTP API 或前端代码。
- [ ] `docs/collection/weibo.md`、Collection README 和受影响 Blueprint 如实区分“Operation 已实现”与“Mapper/Fixture/Probe 待完成”。

# 范围

- Weibo Web Search 请求参数与 page 状态。
- Weibo App Detail 请求。
- Weibo App 一级评论请求和官方 `max_id` JSON path 提取/停止。
- Weibo Web V2 二级评论请求和不猜响应结构的 cursor 状态转换。
- Unit Test、平台文档与当前实现状态同步。

# 非目标

- 不实现 Weibo Raw→Canonical Mapper。
- 不提交未经脱敏的真实 Provider 响应。
- 不注册 Weibo Capability/默认 Registry。
- 不实现搜索结果/二级评论响应列表字段解析，直到合法脱敏真实 Fixture 证明字段。
- 不实现 Plan、Budget、Scheduler、Stage 8 API/前端。
- 不做 App/Web 之间的静默 fallback。

# 必须保持不变

- Web 搜索、App 详情/一级评论、Web V2 二级评论是四个已批准业务 Operation 的固定职责，不是 fallback 顺序。
- Provider 私有 page/max_id 不进入普通前端业务 Contract。
- 外部微博/评论 ID 使用字符串。
- Operation 不访问数据库、不写 Artifact、不做 Canonical Mapper。
- Secret 不进入请求描述、测试、日志或 Git。

# 已确认关键决策与一手资料

2026-08-15 已重新核验 TikHub 官方文档：

- Search: https://docs.tikhub.io/381269400e0
- Detail: https://docs.tikhub.io/410358103e0
- Comments: https://docs.tikhub.io/410358104e0
- Sub comments: https://docs.tikhub.io/381269410e0

当前官方事实：Search `page` 从 1 开始；`search_type` 当前为综合=1、实时=61、热门=60、视频=64、图片=63、文章=21；`time_scope` 支持 hour/day/week/month，留空表示不限时间。Detail 参数为 `status_id`。一级评论参数为 `status_id/max_id/sort_type`，下一游标 JSON path 固定为 `$.data.moreInfo.params.max_id`，没有更多评论时 max_id 为空或相同。二级评论参数为根评论 `id`、可选 `count` 和 `max_id`，首次 max_id 为空，后续使用返回值，但当前文档没有给响应 max_id 的稳定 JSON path。

# 实施步骤

[步骤 1：Red]
→ 修改范围：`tests/unit/collection/test_weibo_tikhub_operation.py`
→ 预期结果：测试冻结四个 endpoint、业务参数映射和有证据的分页状态，并因生产模块尚不存在而失败。
→ 验证方式：PR GitHub Actions 完整 pytest 日志与退出码。

[步骤 2：Green]
→ 修改范围：`backend/src/aima_ugc/adapters/providers/tikhub/operations/weibo.py`
→ 预期结果：唯一生产 Operation 实现请求构造和不猜字段的分页状态；无 DB/Mapper/Secret 副作用。
→ 验证方式：目标 Unit + Collection Unit 回归。

[步骤 3：文档与 Review]
→ 修改范围：`docs/collection/weibo.md`、Collection README、如当前状态受影响则同步 Blueprint README/08。
→ 预期结果：正式文档描述当前机器事实，不把 Operation 完成写成 Mapper/平台兼容完成。
→ 验证方式：文档门禁 + 两阶段 Review + PR diff。

# 验证计划

```text
uv lock --check
uv run ruff format --check backend tests scripts
uv run ruff check backend tests scripts
uv run mypy backend/src
uv run pytest tests/unit/collection/test_weibo_tikhub_operation.py -q
uv run pytest tests/unit/collection -q
uv run python scripts/quality/check_architecture.py
uv run python scripts/quality/check_table_ownership.py
uv run python scripts/quality/scan_secrets.py
uv run python scripts/quality/check_docs.py
```

相关主 CI/Stage 6 回归继续作为集成证据。当前执行宿主没有可用本地 AIMA checkout；Red/Green 与命令证据使用 GitHub Actions，不能把远端状态当用户本地工作区状态。

# 文档影响

按实际机器状态同步微博平台文档、Collection README 和 Blueprint 当前进度；端点方案若与官方核验冲突则先走设计变更，不能静默换 endpoint。

# 兼容、依赖、Migration、部署和回滚

- Contract/API/Schema：无变化。
- Migration/数据库：无变化。
- 依赖/锁文件：无变化。
- 部署：无变化。
- 回滚：回滚本 Change 的 Operation/测试/文档即可，无数据回滚。

# Git

- 基线：创建分支时的最新 `main`
- 分支：`feature/stage7-weibo-operation`
- PR：待 Red 提交后创建
- CI：待本轮实际运行
- 合并：未执行
- Change：in_progress
