---
schema: rvc-change/v1
id: CHG-20260813-stage3b-canonical-v1
title: Stage 3B Canonical 数据契约 V1
level: L3
status: ready_for_review
owner: dingyuwen777
branch: feature/stage3b-canonical-v1
created: 2026-08-13
updated: 2026-08-13
depends_on: []
affected_areas: [canonical, collection, content, architecture, contracts, ci]
affected_paths: [backend/src/aima_ugc/contracts/canonical/, contracts/canonical/, tests/contracts/, scripts/contracts/, docs/blueprint/01-总体架构与技术选型.md, docs/blueprint/02-采集系统与数据标准化.md, docs/blueprint/03-数据库与文件存储.md, docs/blueprint/04-后端任务API与前端.md, docs/blueprint/06-开发约束与分阶段实施.md, docs/blueprint/07-技术决策与实施门禁.md, docs/blueprint/README.md, README.md, AGENTS.md, .github/workflows/ci.yml]
contracts: [CanonicalContentV1, CanonicalCommentV1, CanonicalAuthorV1, CanonicalMetricsV1, CanonicalMediaV1, CanonicalSourceV1, CanonicalCommentThreadV1, CanonicalContentAggregateV1]
data_changes: []
---

# 目标

先从 AIMA 自身业务语义设计理想的 Provider/平台无关 Canonical，再让 TikHub、平台官方 API、Apify、自建采集器、文件/历史导入以及小红书、抖音、微博、B站、快手分别适配。任何现有 Provider 的响应字段都只能作为现实校验样本，不能反向定义 Canonical。

请求级 Provider 原始响应继续作为不可变 Raw Evidence 尽可能完整保存；Canonical 对作者、内容、媒体、公开 URL、互动指标、话题/提及、评论关系和来源追溯等稳定业务语义尽量完整表达，但不复制 Provider 调试字段、临时签名、实验字段或完整私有响应。

写入路径使用原子 Contract：Mapper 输出 `CanonicalContentV1` / `CanonicalCommentV1`，Ingestion Service 调 Owner Repository 写 PostgreSQL。读取/交换路径以一条帖子/笔记/视频/微博为聚合根，由 Query Repository/Read Model 组装 `CanonicalContentAggregateV1`，包含作者、媒体、最新指标、一级评论和各线程回复。数据库不把整棵帖子评论树保存为单行巨大 JSON。

# 可观察成功标准

- [x] Pydantic 是 Canonical 唯一手写事实源，JSON Schema 由脚本生成到 `contracts/canonical/`。
- [x] 原子模型至少包含 `CanonicalContentV1`、`CanonicalCommentV1`、`CanonicalAuthorV1`、`CanonicalMetricsV1`、`CanonicalMediaV1`、`CanonicalSourceV1`。
- [x] 读取聚合至少包含 `CanonicalCommentThreadV1`、`CanonicalContentAggregateV1` 与评论抓取覆盖状态，能区分 complete/partial/not_requested/unavailable。
- [x] 用户已批准作者信息方案 B：内容作者与评论作者均尽量保存平台公开返回的外部 ID、账号/handle、显示昵称、头像 URL、主页 URL、认证、简介、地区以及公开作者统计；缺失或不可靠时为 null，不猜测。
- [x] 内容至少可表达点赞、评论、分享、原生转发/转贴、收藏、播放/浏览、弹幕、投币、下载等明确可得互动指标；评论至少可表达点赞与明确提供时的回复数。未知必须为 null，不能以 0 冒充未知。
- [x] 内容结构支持标题、正文、内容类型、稳定 URL/分享 URL、发布时间/更新时间、媒体列表、话题、@提及、公开地点/IP归属等可确认语义。
- [x] 评论结构严格区分所属内容 ID、评论自身 ID、一级线程根 `root_comment_id`、直接回复 `parent_comment_id`，并保存评论者公开信息、正文、时间、指标、媒体/提及等可得信息。
- [x] Provider/平台可以拥有多个外部稳定 ID；通过 `external_id` + `alternate_ids` 表达，不为 B站 `aid/bvid`、小红书 `userid/red_id`、抖音 `uid/unique_id/sec_uid` 分别污染顶层公共字段。
- [x] `CanonicalContentAggregateV1` 以一条内容为聚合根，能按一级评论组织回复，同时每条回复仍保留自身 ID/root/parent，不能只靠数组位置表达关系。
- [x] 固定合法脱敏示例能被生产 Pydantic Model 与生成 JSON Schema 校验；Schema CI 重生零漂移。
- [x] Canonical 不依赖 TikHub SDK/Endpoint/私有字段；`provider` 只是来源 Adapter 标识。
- [x] Blueprint 明确支持 TikHub、官方 API、Apify、自建采集器、文件/历史导入和以后其他 Provider；传输可为 HTTP/SDK/文件，但都遵守 Raw → Mapper → Canonical。
- [x] 写入边界固定为 `Provider → Raw → Mapper → Canonical → Ingestion Service → Owner Repository → PostgreSQL`。
- [x] 读取边界固定为 `PostgreSQL → Query Repository/Read Model → Query/Application Service → API/AI/Reporting`。
- [x] PostgreSQL 长期事实按内容/作者/媒体/评论/Current+Version+Metric Observation 等关系保存，查询时组装 Aggregate；不创建独立数据库中间微服务。
- [x] Stage 1/2/3A/Windows 既有 CI 继续通过，并增加 Canonical Contract 门禁。

# 理想 Canonical 结构

## Author

公共语义包括：主外部作者 ID、`alternate_ids`、handle/账号名、显示昵称、主页 URL、头像 URL、简介、认证状态/认证说明、公开地区，以及粉丝/关注/作品/累计获赞等来源明确提供的公开统计。评论者复用同一 Author Contract。

## Content

公共语义包括：平台、外部内容 ID/备用 ID、内容类型、标题、正文、稳定 URL/分享 URL、作者、发布时间/来源更新时间/观察时间、媒体、话题、提及、公开地点/IP归属、内容状态和 Metrics。

## Metrics

内容 Metrics 使用明确语义字段且全部允许未知：`like_count`、`comment_count`、`share_count`、`repost_count`、`favorite_count`、`view_count`、`play_count`、`danmaku_count`、`coin_count`、`download_count`。平台没有该概念或本次响应未提供时为 null。

评论 Metrics 至少包含 `like_count`、`reply_count`，后续确有跨平台稳定语义时通过兼容新增 optional 字段扩展。

## Comment

公共语义包括：平台、所属内容 ID、评论 ID/备用 ID、`root_comment_id`、`parent_comment_id`、作者、正文、发布时间/更新时间/观察时间、Metrics、公开地区/IP归属、媒体/提及、是否内容作者本人（来源能确认时）、状态与 Source。

## Aggregate

`CanonicalContentAggregateV1` 顶层以内容为根，包含 `content`、`comment_threads[]` 和 `coverage`。每个 `CanonicalCommentThreadV1` 包含 `root_comment`、`replies[]`、平台报告回复总数/已采集数以及线程是否完整。Aggregate 是 Read Model/交换/导出结构，不是 Mapper 必须一次生成的数据库写入大对象。

# 范围

## 本次实现

- 上述 Canonical V1 Pydantic Models；
- JSON Schema 生成/漂移检查；
- 固定脱敏 Canonical examples；
- Contract Tests 与兼容性基本门禁；
- Provider-agnostic 采集架构；
- Canonical → Ingestion/Persistence 与 DB → Query 中间层；
- 未来数据库持久化目标结构的 Blueprint 设计；
- 相关 `AGENTS.md`/Blueprint/README/CI 同步。

## 非目标

- 具体 TikHub/Apify/官方 API Client、Operation 或 Mapper；
- 五个平台批量实现；
- `contents/comments/authors/media` 数据库 Migration 与 Repository 正式实现；
- API/前端业务页面、Job Runtime、登录、Retention、生产 Release。

# 方案比较

## A. 直接按 TikHub 或某一平台字段设计统一 JSON

不采用。Provider 字段变化会成为系统公共语义，其他采集途径被迫模仿 TikHub，违背可替换目标。

## B. 理想 Canonical，但把整帖+全部评论作为数据库单行 JSON

不采用。单评论/指标更新会重写大对象，查询、索引、历史、并发和幂等维护成本高。

## C. 理想 Canonical + 原子写入 + 关系化持久化 + 内容聚合读取（采用）

先定义 AIMA 理想业务 Contract，各 Provider/平台 Mapper 适配；原子 Content/Comment 进入 Ingestion，数据库按关系保存，读取时组装内容根 Aggregate。Raw 保证信息不丢，Canonical 保证系统语义稳定。

# 已确认关键决策

- TikHub 只是一个 Provider Adapter；未来官方 API、Apify、自建采集器、文件导入等与 TikHub 同级。
- 先设计理想数据结构，再让各 Provider/平台适配；不得以某个 Provider 当前响应作为 Canonical 事实源。
- 用户选择作者信息方案 B，并明确希望尽可能多保存平台公开可获得信息，包括帖子/笔记 ID、作者 ID/URL、评论者 ID/URL、媒体、点赞/评论/分享/转发/收藏/播放等指标。
- 系统对外/读取结构以帖子/笔记/视频/微博为聚合根，组织一级评论和每个线程的回复；数据库内部仍按关系拆分。
- Raw Evidence 负责 Provider 原始完整性；Canonical 不为追求“字段多”复制调试信息、短期 Token、实验字段和编码流全部细节。
- Canonical 后的 Ingestion/Persistence 与 Query 边界与 Provider 无关；Mapper 不查数据库也不写数据库。
- PostgreSQL 仍是唯一业务事实库；中间层是模块化单体内部边界，不增加微服务。

# 五平台现实校验结论

实施设计时已核对 TikHub 当前官方文档及用户已有真实响应：

- 小红书可获得内容/作者/媒体/点赞评论收藏分享，并有一级/二级评论接口；
- 抖音搜索/详情可获得作者、媒体、点赞/评论/分享/收藏/播放等，部分播放统计需要独立统计接口；
- 微博详情可获得全文、图片/视频、点赞/评论/转发，评论包含评论者与点赞；
- B站内容具有播放、弹幕、评论、收藏、投币、分享、点赞等平台语义，并有根评论/回复接口；
- 快手有作品一级评论和显式 `root_comment_id` 的二级评论接口，用户详情可提供公开统计。

这些平台事实只用于证明理想 Contract 足够承载现实数据；具体 Operation 和字段 Mapping 仍需后续逐平台 Fixture/Contract Test 冻结。

# 兼容、Migration、部署与回滚

- 这是首个正式 Canonical V1，没有旧机器 Contract 的数据迁移；旧 Blueprint 示例不是运行时兼容承诺。
- 本阶段不创建内容数据库 Migration；目标持久化结构先写 Blueprint，后续独立 L3 Change 实施。
- Canonical V1 合并后，删除字段、改类型/语义、身份规则变化、optional→required 属破坏性变化；新增 optional 通常可在 V1 兼容演进。
- 回滚为回退本 Stage 3B PR/Contract；不存在生产数据回填；生产部署仍 No-Go。

# TDD / 验证计划

1. Red：Contract Test 要求 Canonical 模块/Schema/帖子聚合和评论线程存在，确认因实现缺失失败。
2. Green：最小 Pydantic Models、Schema 生成脚本和固定 examples。
3. 验证：Ruff、mypy、Contract Tests、Schema drift、现有完整 CI。
4. Review：先检查 Provider 无关性、聚合/原子边界、未知值、ID/root/parent/指标语义，再检查实现质量和文档一致性。

# TDD 与验证证据

- Red：PR #11 Run `31710331120`，Stage 1 Contract Test 因 `ModuleNotFoundError: No module named 'aima_ugc.contracts'` 按正确原因失败；Stage 2/3A 正常。
- Green：Run `31719449984` 的 Stage 1、Stage 2 Platform、Stage 3A Database、Windows bootstrap 四 Job 全部 success；Stage 1 已通过 Contract 生成/漂移、Ruff、mypy、Unit/Contract/API、Wheel 和前端完整检查。
- 两阶段 Review：确认未混入业务 Migration、Provider 实现、Job Runtime 或前端业务页面；补强评论树/coverage 关系校验、`null` 与 `0` 语义、`observed_fields` 叶子路径和数据库目标 DDL 空值语义。

# Git

- 基线 main：`4440e9b156ca0ddf52aaf3eed80cdcea28a7bad1`
- 分支：`feature/stage3b-canonical-v1`
- Draft PR：#11 `建立 Stage 3B Canonical 数据契约 V1`
- 候选验证：Run `31719449984` 四 Job 全绿；本状态提交仍需再次执行完整 PR CI 后才可转正式 Review/合并。
