---
schema: rvc-change/v1
id: CHG-20260815-stage7-weibo-operation
title: 建立 Stage 7 微博 TikHub Operation 与分页状态机
level: L2
status: ready_for_review
owner: dingyuwen777
branch: feature/stage7-weibo-operation
created: 2026-08-15
updated: 2026-08-15
depends_on: [CHG-20260815-stage7-decision-capability]
affected_areas: [collection, provider, testing, documentation, blueprint]
affected_paths: [backend/src/aima_ugc/adapters/providers/tikhub/operations/weibo.py, tests/unit/collection/test_weibo_tikhub_operation.py, docs/collection/weibo.md, backend/src/aima_ugc/modules/collection/README.md, docs/blueprint/README.md, docs/blueprint/08-采集策略与平台能力.md]
contracts: []
data_changes: []
---

# 目标与当前结果

按 Blueprint 08 已批准并于 2026-08-15 重新核验的 TikHub 官方接口，建立微博首版四类 Operation：Web 搜索、App 详情、App 一级评论、Web V2 二级评论。只实现官方资料足以证明的请求构造和分页状态；没有合法脱敏非空真实 Fixture 的响应列表字段不猜、不提前写 Mapper，也不宣称微博平台兼容完成。

当前代码已经建立：Web Search 规范化业务参数映射与 page 状态、App Detail 请求、App 一级评论请求与官方 `data.moreInfo.params.max_id` 游标、Web V2 二级评论请求与不猜响应路径的 max_id 状态转换。Weibo Mapper、合法脱敏非空真实 Fixture、Real Provider Probe、Capability/默认 Registry 接线仍明确不在本单元结果中。

# 成功标准

- [x] 搜索固定使用 `GET /api/v1/weibo/web/fetch_search`；页码从 1 开始；规范化 `general/latest/hot/video/image/article` 映射当前官方 `search_type=1/61/60/64/63/21`。
- [x] AIMA 关键词监控默认搜索使用 `latest`，映射 TikHub 官方“实时/最新优先” `search_type=61`；不把 Provider 文案 `realtime` 作为第二套上层业务语义。
- [x] 搜索时间 `all/hour/day/week/month` 中，`all` 不发送 `time_scope`，其余映射官方同名值；page 状态只负责下一页，搜索结果列表位置/空页识别留待合法真实 Fixture 证明后接线。
- [x] 详情固定使用 `GET /api/v1/weibo/app/fetch_status_detail`，参数使用当前官方 `status_id`。
- [x] 一级评论固定使用 `GET /api/v1/weibo/app/fetch_status_comments`，使用 `status_id`、可选 `max_id`、`sort_type=0/1`；AIMA 默认 `latest → sort_type=1`，首屏不传 `max_id`。
- [x] 一级评论严格按官方 `$.data.moreInfo.params.max_id` 提取下一游标；返回空值或与上一次相同即停止，不猜评论数组字段。
- [x] 二级评论固定使用 `GET /api/v1/weibo/web_v2/fetch_post_sub_comments`，`id` 表示根评论 ID，首次 `max_id=''`，后续使用返回 max_id；当前不覆盖可选 `count`。
- [x] 二级评论只根据“上次 max_id + 已可靠提取的返回 max_id”做状态转换；当前官方文档没有稳定响应 JSON path，本单元不猜提取路径。
- [x] Red 先因 `operations.weibo` 不存在而正确失败；首次 Green 后 Collection/Content/Provider Contract Unit 已有 `82 passed` 中间证据。
- [x] 不新增 Mapper、Capability、Registry、Migration、数据库、依赖、公共 HTTP API 或前端代码。
- [x] `docs/collection/weibo.md`、Collection README、Blueprint README/08 如实区分“Operation 已实现”与“Mapper/Fixture/Probe/Capability 待完成”。
- [ ] 最终 PR head 重新通过相关 Unit/Quality/PostgreSQL/Stage 5A—5D/Stage 6/Stage 7/主 CI 后才转 Ready 并合并。

# 范围

- Weibo Web Search 请求参数与 page 状态。
- Weibo App Detail 请求。
- Weibo App 一级评论请求和官方 `max_id` JSON path 提取/停止。
- Weibo Web V2 二级评论请求和不猜响应结构的 cursor 状态转换。
- Unit Test、平台文档、Collection README 与 Blueprint 当前实现状态同步。

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
- AIMA 上层使用统一业务语义 `latest`；Provider 私有 `search_type/sort_type` 只在 Operation 内映射。
- 外部微博/评论 ID 使用字符串。
- Operation 不访问数据库、不写 Artifact、不做 Canonical Mapper。
- Secret 不进入请求描述、测试、日志或 Git。

# 已确认关键决策与一手资料

2026-08-15 重新核验 TikHub 官方文档：

- Search: https://docs.tikhub.io/381269400e0
- Detail: https://docs.tikhub.io/410358103e0
- Comments: https://docs.tikhub.io/410358104e0
- Sub comments: https://docs.tikhub.io/381269410e0

当前官方事实：Search `page` 从 1 开始；`search_type` 为综合=1、实时=61（按时间、最新优先）、热门=60、视频=64、图片=63、文章=21；`time_scope` 支持 hour/day/week/month，留空表示不限时间。Detail 参数为 `status_id`。一级评论参数为 `status_id/max_id/sort_type`，下一游标 JSON path 固定为 `$.data.moreInfo.params.max_id`，没有更多评论时 max_id 为空或相同。二级评论参数为根评论 `id`、可选 `count` 和 `max_id`，首次 max_id 为空，后续使用返回值，但当前文档没有给响应 max_id 的稳定 JSON path。

# Red → Green

## Red

PR #40 Red head `f71d48a19900b4af447494e034f654d6a811cb0a`，Stage 6 XHS Vertical Slice run `31857426164` / Unit job `94944721799`：

- 锁定 Python/uv 环境安装成功；
- pytest 在 collection 阶段失败；
- `ModuleNotFoundError: No module named 'aima_ugc.adapters.providers.tikhub.operations.weibo'`；
- `Interrupted: 1 error during collection`；
- pytest 退出码 2。

失败来自本 Change 目标生产模块尚不存在，不是依赖、数据库或旧测试故障。

## Green 中间证据

首次 Green head `4555d0cd32e84efd9a012709e53625451409bb72`：

- Stage 6 Unit 完整日志：`82 passed in 2.91s`，0 failed，退出码 0；
- 同一 head 的 CI、Stage 5A、5B、5C、5D、Stage 6、Stage 7 共 7 条 workflow 全部 success。

随后两阶段 Review 修正业务语义和默认值，最终 head 必须重新跑新鲜 CI 后才允许 Ready/merge。

# 两阶段 Review

## 第一阶段：需求符合性

- 四个 endpoint 与 Blueprint 08 已批准主链一致，没有切换到其他 App/Web endpoint 或增加 fallback。
- Search 只冻结官方请求参数和 page 状态；没有在缺真实 Fixture 时猜搜索结果列表字段。
- 一级评论只解析官方明确的 `data.moreInfo.params.max_id`；二级评论不猜返回 max_id JSON path。
- 没有实现 Mapper、Capability、Registry、Plan、Budget、Scheduler、Stage 8 API/UI，非目标未越界。
- Blueprint README/08、Collection README、微博平台文档均明确 Operation 完成不等于微博平台兼容完成。

## 第二阶段：代码质量

- Review 发现最初使用 `realtime → 61` 作为 AIMA 业务值，与已冻结跨平台 `latest` 语义不一致；已改为 `latest → 61`，未保留未合并别名。
- Review 发现最初 Search/一级评论默认分别为 `general/hot`，与已批准关键词监控“最新”及 `comment_sort=latest_if_supported` 默认策略不一致；已改为默认 `latest`，显式 `general/hot` 仍保留。
- Operation 保持纯请求/分页逻辑，没有 DB、Artifact、Secret 或 Mapper 副作用。
- 错误输入采用明确 ValueError；Provider 私有枚举集中在单一 Operation 模块。
- 无依赖、锁文件、Migration、公共 Contract/API 或前端生成物变化。

# 验证计划

最终 PR head 必须执行并读取新鲜结果：

```text
uv lock --check
uv run ruff format --check backend tests scripts
uv run ruff check backend tests scripts
uv run mypy backend/src
uv run pytest tests/unit/collection/test_weibo_tikhub_operation.py -q
uv run pytest tests/unit/collection -q
uv run pytest tests/unit/content -q
uv run pytest tests/contracts/test_provider_v1.py -q
uv run python scripts/quality/check_architecture.py
uv run python scripts/quality/check_table_ownership.py
uv run python scripts/quality/scan_secrets.py
uv run python scripts/quality/check_docs.py
```

相关主 CI/Stage 5A—5D/Stage 6/Stage 7 回归继续作为集成证据。当前执行宿主没有可用本地 AIMA checkout；Red/Green 与命令证据使用 GitHub Actions，不能把远端状态当用户本地工作区状态。

# 文档影响

已同步：

- `docs/collection/weibo.md`：当前 endpoint、AIMA→Provider 参数映射、分页已证明边界、未验证边界；
- `backend/src/aima_ugc/modules/collection/README.md`：生产入口、独立验证和当前限制；
- `docs/blueprint/README.md`：Stage 7 当前机器进度与剩余单元；
- `docs/blueprint/08-采集策略与平台能力.md`：Operation Matrix、微博当前状态与 Stage 7 门禁。

Blueprint 的主 endpoint/业务设计没有改变；本 Change 只同步当前实现状态，并按既有跨平台业务语义统一 `latest`。

# 兼容、依赖、Migration、部署和回滚

- Contract/API/Schema：无变化。
- Migration/数据库：无变化。
- 依赖/锁文件：无变化。
- 部署：无变化，不新增进程/配置。
- 回滚：回滚本 Change 的 Operation/测试/文档提交即可，无数据回滚。

# Git

- 基线 main：`d12bcfcb454609b37408f8ff98531d6fd2a4e125`
- 分支：`feature/stage7-weibo-operation`
- PR：#40，Draft；最终 CI 成功后转 Ready
- 正确 Red：head `f71d48a19900b4af447494e034f654d6a811cb0a`，run `31857426164` / job `94944721799`
- 中间 Green：head `4555d0cd32e84efd9a012709e53625451409bb72`，7 条相关 workflow success，Stage 6 Unit `82 passed`
- 最终 PR CI：待最新 head 完成
- 合并：未执行
- 合并后 main 验证：未执行
- Change：ready_for_review，仍在 `changes/active/`
- 生产部署：未执行
