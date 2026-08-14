---
schema: rvc-change/v1
id: CHG-20260815-stage7-collection-pipeline
title: 固化 Stage 7 五平台采集策略与开发导航
level: L3
status: done
owner: dingyuwen777
branch: docs/stage7-collection-pipeline
created: 2026-08-15
updated: 2026-08-15
depends_on: [CHG-20260814-stage7-real-provider-probe]
affected_areas: [collection, provider, budget, frontend, testing, documentation, blueprint]
affected_paths: [docs/blueprint/README.md, docs/blueprint/02-采集系统与数据标准化.md, docs/blueprint/07-技术决策与实施门禁.md, docs/blueprint/08-采集策略与平台能力.md, docs/collection/]
contracts: []
data_changes: []
---

# 目标

把已经确认的五平台 TikHub 默认 Provider、可替换 Provider、统一采集 Decision Pipeline、重复内容省钱、零评论短路、自适应评论、增量评论、Deep Collection、Capability 驱动前端、费用预测/硬预算以及 Operation/Business Pipeline Probe 等决定固化为 Stage 7 正式设计，并增加可直接导航到具体平台采集逻辑的长期文档。

# 成功标准

- [x] 新增 `docs/blueprint/08-采集策略与平台能力.md`，作为 Stage 7 采集业务语义和平台能力的正式设计入口。
- [x] 新增 `docs/collection/README.md`，说明通用抓取流程、决策顺序、成本控制、独立业务调试和文档事实层级。
- [x] 为小红书、抖音、微博、B站、快手各建一篇采集逻辑文档，记录批准的 TikHub Operation 链、业务参数、内部分页、平台差异、成本策略和当前实现/Fixture/Probe 状态。
- [x] Blueprint README 建立 `07 → 08 → collection 总览 → 目标平台文档 → 当前代码/Fixture/Test` 的开发导航。
- [x] Blueprint 07 版本推进到 1.16，固化五平台首版 Operation Matrix 和 Stage 7 Provider/Collection 可开工边界，同时保留真实 Fixture/兼容验收和 Scheduler misfire/catch-up 门禁。
- [x] Blueprint 02 移除旧候选 Operation 与“高价值才抓评论”等冲突描述，保留 Raw/Mapper/Canonical/来源链基础并导航到 08。
- [x] 明确当前只有小红书 Operation/Mapper 已实现，其余四平台仍是 Stage 7 目标实现，不能把设计文档冒充代码事实。
- [x] 未改写 Stage 1—6 Contract/Migration、依赖、锁文件或生产代码；未把对 `03-数据库与文件存储.md` 的实验性整篇改写带入最终 diff。
- [x] PR #31 CI 成功，合并后 main CI 与 Stage 6 独立回归再次成功。

# 范围

- 五平台默认 Provider=`tikhub`，平台与 Provider 解耦，每个平台可单独显式替换 Provider。
- 每个 `Provider + Platform + Business Operation` 固定一个批准主 endpoint；不做通用静默 fallback。
- Decision Pipeline：Search → Raw → Observation → 去重/比较 → Detail Decision → Comment Eligibility → Comment Depth → Replies → Budget → Raw/Mapper/Canonical/Ingestion。
- 评论默认 `new_or_comment_changed`；可靠 `comment_count=0` 或评论关闭直接短路；重复内容评论数未变化不重抓评论。
- 自适应评论默认 `full_fetch_threshold=50`、`sample_target=50`、`reply_target_per_root=5`；目标是软目标，已付费返回的整页数据全部保留。
- 评论增加优先增量；评论下降记录事实并受控刷新，非完整覆盖不得猜具体删除。
- 时间范围小于调度周期只 Warning；Provider 不支持/参数非法才 Error。
- Deep Collection 正常从内部 `content_id` 触发；系统未发现内容时才使用外部 ID/分享链接高级入口。
- Provider Capability 驱动 API/前端业务选项，不暴露 cursor/search_id/pageArea/API Key 等技术状态或 Secret。
- 费用区分预计费用、理论请求上限和数据库硬预算；最终评论预算需要 Run 级评论隔离语义。
- Operation Probe 与 Business Pipeline Probe 都必须复用生产实现，Business Probe 支持连续运行验证重复内容省钱逻辑。

# 非目标

- 本 Change 不实现 Stage 7 代码、HTTP API、前端页面、Migration 或 Excel Exporter。
- 不执行新的真实付费 TikHub 调用，不生成新的真实 Fixture。
- 不批准 Scheduler `misfire_policy`、`max_catch_up_runs` 或补跑费用/容量数值。
- 不批准生产 SLO/RPO/RTO、Raw 保留/删除期限或最终生产容量。
- 不把官方 endpoint 文档冒充真实响应/Mapper 已验收。

# 必须保持不变

- PostgreSQL 是业务事实源；Raw 是 Provider 原始证据；Canonical 是 Provider 无关业务 Contract。
- Provider、Mapper、Probe 不绕过 Raw → Canonical → Ingestion/Owner 边界。
- 每个真实 HTTP Attempt 独立留痕、独立预算；网络重试不能复用上一 Attempt 预算。
- Secret 不进入代码、Git、日志、Raw、Canonical、XLSX、Job Payload 或数据库明文。
- 新平台 Mapper 必须以合法脱敏真实 Fixture/明确上下文证明字段，不能猜字段。
- 前端只配置业务语义，Provider 私有分页状态由 Operation 管理。
- 已发布 Stage 1—6 Migration/Contract 不改写。

# 已确认关键决策

1. 五个平台默认 Provider 均为 TikHub；未来每个平台可以单独显式更换 Provider，上层 Canonical/Ingestion/数据库不感知 Provider 私有 JSON。
2. App/Web/V2/V3 是 TikHub 内部 API family；每个业务 Operation 选择一个主 endpoint，不建立笼统“App 优先/失败自动 Web”规则。
3. 普通评论资格不依赖模糊“高价值”；高价值仅用于升级 Deep Collection，Stage 7 自动 Deep 默认关闭。
4. 默认评论触发 `new_or_comment_changed`：新内容有评论时采集；重复内容 comment_count 未变化不重抓；变化时增量/受控刷新；可靠零评论直接短路。
5. 评论默认自适应 50/50/5，均是业务默认/可配置值；软目标不裁剪整页已返回数据。
6. 时间窗口小于调度间隔只 Warning；Provider 不支持或非法参数才拒绝。
7. Capability 只展示实际支持的业务选项；cursor/search_id/search_session_id/backtrace/pageArea/max_id/Secret 等不开放给业务用户。
8. 费用展示分历史/保守预计、理论请求上限、数据库硬预算；TikHub 单价不硬编码进长期 Blueprint，历史 Attempt 保留实际单价/费用快照。
9. 评论预算目标同时保护 global、run、run_comments、content_comments，并在后续 Migration 中绑定稳定 Provider 配置身份。
10. Deep Collection 从内容页内部 `content_id` 触发；系统未发现的内容才用外部 ID/分享链接入口。
11. Business Pipeline Probe 与生产系统复用同一个 Decision Service：生产 previous state 来自 PostgreSQL，Probe 可来自上一 Probe Snapshot。
12. 首版 Operation Matrix：小红书 App V2；抖音 Search V2 + App V3 详情/评论；微博 Web 搜索 + App 详情/一级评论 + Web V2 二级评论；B站 App；快手 App Search V2/详情 + Web 一级/二级评论。不同 API family 是固定业务职责，不是 fallback。

# 方案比较

## 方案 A：Blueprint 08 + `docs/collection/`（采用）

08 冻结跨平台业务语义、Capability、预算和 Operation Matrix；`docs/collection/` 按平台解释实际 API、当前代码状态和调试入口；README/07 负责导航和门禁。这样避免把同一 Pipeline/平台接口重复塞进 02/03/04/06。

## 方案 B：全部拆回 02/03/04/06（拒绝）

文件数量少，但同一规则会被拆散并重复，Provider/Operation 变化容易产生文档漂移。

## 方案 C：只写 `docs/collection/`（拒绝）

缺少正式 Blueprint 地位，后续 Agent 可能按仓库导航漏读已确认业务门禁。

# 实施与 Review

本任务为 L3 设计/文档固化，不伪造 Red→Green。提交前完成需求符合性和文档质量两阶段复核：

- 重新核对 main 的 XHS Operation/Mapper、Unit Test 和非空脱敏 Search Fixture；
- 重新核对抖音、微博、B站、快手当前 main 尚无 Operation/Mapper；
- 用 TikHub 当前官方文档核对首版主 endpoint、业务参数和分页语义；
- 明确抖音评论/回复 `count` 不开放给业务 UI；B站/快手不伪造当前 Search Operation 不具备的原生时间筛选；
- 发现最初对 `03-数据库与文件存储.md` 的整篇改写顺带压缩未变 Job/索引/备份约束，已在 PR 前恢复为 main 原文；最终 diff 不包含 03；
- 最终无代码、Pydantic Contract、Migration、依赖或锁文件变化。

# 验证证据

当前宿主无本地 Git 工作区/终端，因此没有本地 `git status` 或 `uv run ...` 证据；使用 GitHub 远端 diff 与 GitHub Actions 作为本轮新鲜集成证据。

PR #31 head `63d2e71164e8080ff3711186cd58b8930d80e7c2`：

- CI #247 / run `31827743699`：success；Stage 1、Stage 2 Platform、Stage 3A Database、Windows bootstrap 均 success。
- Stage 6 XHS Vertical Slice #85 / run `31827743662`：success；Quality、Unit、PostgreSQL 均 success，PostgreSQL Job 验证 Stage 5D→head、Stage 6 多升级路径与 base round trip。

PR #31 merge commit：

`acf85537f6c783ea4cc60926e0bd2342f75ac9e9`

合并后 main：

- CI #248 / run `31827889049`：success；Stage 1、Stage 2 Platform、Stage 3A Database、Windows bootstrap 均 success。
- Stage 6 XHS Vertical Slice #86 / run `31827889051`：success；Quality、Unit、PostgreSQL 均 success并重新验证 Migration 多路径。

# 兼容、Contract、Migration、部署和回滚

- 当前运行行为：无变化，仅正式设计/导航变化。
- 公共 Contract/API：无机器变化；Stage 7 实现时按 08 建立版本化 Pydantic Capability/Plan/Decision Contract。
- Migration/数据库：无变化；`run_comments`、Provider 预算身份、Plan 平台策略、评论抽样解释字段是后续 Stage 7 Migration 目标，实现时精准同步 03，禁止改写 Stage 1—6 Revision。
- 依赖/锁文件：无变化。
- 部署：无变化。
- 回滚：如需撤销，只回滚本 Change 的文档提交，不涉及数据回滚。

# Git

- 基线 main：`ea57681d58fc9859a7963aab386a4de524f2024b`
- 开发分支：`docs/stage7-collection-pipeline`
- PR：#31
- PR CI：CI #247 / `31827743699` success；Stage 6 #85 / `31827743662` success
- 合并：`acf85537f6c783ea4cc60926e0bd2342f75ac9e9`
- 合并后 main CI：CI #248 / `31827889049` success；Stage 6 #86 / `31827889051` success
- Change：done，归档到 `changes/archive/2026-08/`
