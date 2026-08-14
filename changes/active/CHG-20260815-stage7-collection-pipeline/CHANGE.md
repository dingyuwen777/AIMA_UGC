---
schema: rvc-change/v1
id: CHG-20260815-stage7-collection-pipeline
title: 固化 Stage 7 五平台采集策略与开发导航
level: L3
status: ready_for_review
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
- [x] 为小红书、抖音、微博、B站、快手各建一篇采集逻辑文档，记录已批准 TikHub Operation 链、可配置业务参数、内部分页、平台差异、成本策略、代码/Fixture/测试状态和验收边界。
- [x] Blueprint README 明确 Provider/采集开发必须先读 08，再读 `docs/collection/README.md` 和目标平台文档，然后才读代码/Fixture/测试。
- [x] Blueprint 07 将版本推进到 1.16 并固化本轮跨模块决定，取消“其余四平台 Operation 尚未批准”的旧事实，同时保留真实脱敏 Fixture、实际字段兼容和 Scheduler misfire/catch-up 门禁。
- [x] Blueprint 02 移除旧候选 Operation/“高价值才抓评论”等与当前决策冲突的描述，并把 Stage 7 业务语义和平台细节唯一导航到 08/`docs/collection/`。
- [x] 文档明确：小红书当前已有 Operation/Mapper 机器实现；抖音、微博、B站、快手仍是 Stage 7 目标实现，不能把设计文档冒充代码事实。
- [x] 文档明确：Stage 7 Provider/Collection/Capability/预算/Probe 可以开始按边界清楚的 PR 开发；Scheduler 启用仍等待 `misfire_policy/max_catch_up_runs` 批准；新平台完成验收仍需合法脱敏真实 Fixture 和 Real Probe。
- [x] 未改写 `03-数据库与文件存储.md` 的未变 Job/索引/备份等约束；Stage 7 新 Plan/预算目标由更高优先级 07 + 08 冻结，真正建表时再与新 Migration 一起精准同步 03。
- [x] 不新增代码、Contract、Migration、依赖或锁文件；不泄露任何真实 Secret。
- [ ] PR CI 成功；合并后 main 相关 CI 成功后 Change 才归档。

# 范围

- 五平台默认 Provider=`tikhub`，平台与 Provider 解耦，每个平台可单独显式替换 Provider。
- 每个 `Provider + Platform + Business Operation` 固定一个批准的主 endpoint；不做通用静默 fallback。
- 统一 Decision Pipeline：Search → Raw → Observation → 去重/比较 → Detail Decision → Comment Eligibility → Comment Depth → Replies → Budget → Raw/Mapper/Canonical/Ingestion。
- 评论默认 `new_or_comment_changed`；可靠 `comment_count=0` 或评论关闭直接短路；重复且评论数未变化不重抓评论。
- 自适应评论默认 `full_fetch_threshold=50`、`sample_target=50`、`reply_target_per_root=5`，均为前端可配置业务参数；软目标不丢弃已经付费返回的超额页数据。
- 评论数增加优先增量抓取；评论数下降只记录事实并受控刷新，非完整覆盖不得猜具体删除。
- 时间范围小于调度周期只 Warning，不阻止保存；Provider 不支持/参数非法才 Error。
- Deep Collection 正常从内部 `content_id` 触发；高级入口允许外部内容 ID/分享链接直接采集，但仍走正式 Provider/预算/Raw/Mapper/Canonical。
- 费用展示区分预计费用、理论请求上限和数据库硬预算；最终评论预算增加 Run 级评论隔离语义。
- Provider Capability 驱动后端 API/前端可配置项，不向业务 UI 暴露 cursor/search_id/pageArea/API Key 等技术状态。
- Operation Probe 与 Business Pipeline Probe 都复用生产实现；后者输出决策证据并支持连续运行验证重复内容省钱逻辑。
- 建立正式开发导航：Blueprint 08 → `docs/collection/README.md` → 目标平台文档 → 当前代码/Fixture/Test。

# 非目标

- 不在本 Change 实现 Stage 7 代码、HTTP API、前端页面、Migration 或 Excel Exporter。
- 不执行真实付费 TikHub 调用，不生成新的真实 Fixture。
- 不批准 Scheduler `misfire_policy`、`max_catch_up_runs` 或具体补跑费用/容量数值。
- 不批准生产 SLO/RPO/RTO、Raw 保留/删除期限或最终生产部署容量。
- 不把官方 endpoint 文档冒充已验收的真实响应/Mapper 兼容性。
- 不顺手改写 Stage 1—6 未发生变化的数据库、Job、备份或部署设计。

# 必须保持不变

- PostgreSQL 是业务事实源；Raw 是 Provider 原始证据；Canonical 是 Provider 无关业务 Contract。
- Provider、Mapper、Probe 不得绕过现有 Raw → Canonical → Ingestion/Owner 边界。
- 每个真实 HTTP Attempt 独立留痕、独立预算；网络重试不能复用上一 Attempt 的预算。
- Secret 不进入代码、Git、日志、Raw、Canonical、XLSX、Job Payload 或数据库明文。
- 新平台 Mapper 只有在合法脱敏真实 Fixture/明确上下文证明字段后才能映射，不猜字段。
- 前端只配置业务语义；Provider 私有技术分页状态由 Operation 管理。
- 已发布 Stage 1—6 Migration/Contract 不改写。

# 已确认关键决策

1. 五个平台当前默认 Provider 均为 TikHub；以后每个平台可以单独显式更换 Provider，上层 Canonical/Ingestion/数据库不感知 Provider 私有 JSON。
2. App/Web/V2/V3 是 TikHub 内部 API family，不是 Provider；每个业务 Operation 选定唯一主 endpoint，不建立笼统的“App 优先/失败自动 Web”规则。
3. 普通评论资格不再依赖模糊“高价值”判断；高价值只用于升级为 Deep Collection，Stage 7 自动 Deep 默认关闭。
4. 默认评论触发为 `new_or_comment_changed`：新内容有评论时采集；重复内容 comment_count 未变化时不重抓；变化时增量/受控刷新；可靠零评论直接短路。
5. 评论默认自适应：50 条以内尽量完整，超过 50 条按平台支持的排序目标采集 50 条；一级线程二级回复目标 5 条；三个值均可配置。
6. “目标数量”不是硬裁剪：为达到 50 请求一整页而实际得到 60 时保留全部 60；硬上限由请求/费用预算决定。
7. 时间范围小于调度间隔只 Warning；无法映射到 Provider 支持值或参数非法才拒绝。
8. 前端 Capability 只展示目标 Provider/平台/Operation 实际支持的业务选项；cursor/search_id/search_session_id/backtrace/pageArea/max_id/Secret 等不开放给业务用户。
9. 费用展示分为历史/保守预计、理论请求上限、数据库硬预算；实际 TikHub 单价不硬编码在 Blueprint，实施时通过当前 Endpoint/Pricing 信息和 Attempt 单价快照维护。
10. 评论预算需要同时保护全局、Run、Run 评论总量和单内容评论，避免热门内容耗尽发现预算；最终数据库设计在 Stage 7 Migration 中用真实父事实和 Provider 身份完成约束。
11. Deep Collection 从内容页 `content_id` 触发并自动解析平台/外部 ID/Provider；只有系统尚未发现内容时才用高级外部 ID/分享链接入口。
12. 单独业务调试必须覆盖整套 Decision Pipeline：生产从 PostgreSQL 读取 previous state，Probe 从上一 Probe Snapshot 读取 previous state，两者复用同一生产决策实现。
13. 首版 Operation Matrix：小红书 App V2；抖音 Search V2 + App V3 详情/评论；微博 Web 搜索 + App 详情/一级评论 + Web V2 二级评论；B站 App；快手 App Search V2/详情 + Web 一级/二级评论。不同 API family 是固定业务职责，不是 fallback。

# 方案比较

## 方案 A：新增 Blueprint 08 + `docs/collection/` 平台文档（采用）

- 08 冻结 Stage 7 跨模块采集语义、Capability、预算和 Operation Matrix。
- `docs/collection/` 面向开发/调试，按平台解释真实 API、当前代码状态和验证入口。
- Blueprint README/07 负责导航和权威门禁；02 保留 Provider/Raw/Mapper/Canonical 基础并导航到 08。

优点：不把 02/03/04/06 继续膨胀成重复说明；平台 API 变化可只更新对应平台文档、Operation/Fixture 和必要的 08/07 决策；开发者有明确入口。缺点：增加一个 Blueprint 和一个平台文档目录，需要维护导航。

## 方案 B：把全部细节分别塞回 02/03/04/06（不采用）

优点是文件数量少；缺点是同一 Pipeline、参数、成本和平台 API 会被拆散/重复，后续 Provider/Operation 改动容易产生文档漂移，不利于实际开发导航。

## 方案 C：只写 `docs/collection/`，不改 Blueprint（不采用）

优点最轻；缺点是用户确认的跨模块业务语义缺少正式设计地位，未来 Agent 可能只读 Blueprint 而漏掉成本/评论/Capability 决策，不满足仓库用户决策门禁。

# 实施步骤

[步骤 1：建立 Stage 7 正式采集设计]
→ 修改范围：`docs/blueprint/08-采集策略与平台能力.md`
→ 预期结果：统一 Pipeline、Decision Table、Capability、成本/预算、前端和五平台主 Operation 链成为正式设计。
→ 验证方式：与 02/07、当前 XHS 代码和 TikHub 官方文档交叉复核。

[步骤 2：建立采集开发导航]
→ 修改范围：`docs/collection/README.md`、五个平台文档
→ 预期结果：开发某个平台时能快速确认实际 API、业务参数、内部参数、代码路径、Fixture/Probe 和成本停止条件。
→ 验证方式：Markdown 链接/文档入口门禁 + 与当前目录实际存在性核对。

[步骤 3：接入 Blueprint 导航和消除旧采集描述]
→ 修改范围：`docs/blueprint/README.md`、`docs/blueprint/02-采集系统与数据标准化.md`、`docs/blueprint/07-技术决策与实施门禁.md`
→ 预期结果：未来 Agent 自动被导航到 08 和目标平台文档；02 不再保留相反的旧候选接口/高价值评论规则；Stage 7 可开发范围与仍阻塞项明确。
→ 验证方式：文档入口/链接检查 + 术语/门禁冲突复核 + CI。

# 验证与 Review 证据

本任务是 L3 设计/文档固化，不伪造 Red→Green。当前宿主无本地 Git 工作区/终端，因此不能提供本地 `git status` 或 `uv run ...` 输出；远端分支、diff、PR 和 GitHub Actions 作为本轮可执行证据。

提交前事实核验：

- main 基线 `ea57681d58fc9859a7963aab386a4de524f2024b` 无 Open PR/Active Change；
- main 当前 TikHub `operations/` 与 `mappers/` 只有小红书实现；
- 小红书当前生产 Operation/Mapper、Unit Test 和非空脱敏 Search Fixture 路径已逐项核对；
- 抖音、微博、B站、快手当前文档都明确标记 `Stage 7 待实现`，没有虚构代码/Fixture；
- TikHub 官方当前文档重新核验了五平台首版主 endpoint、关键业务参数和分页游标语义；
- 抖音 App V3 评论/回复的 `count` 官方要求保持默认，因此文档明确不向业务 UI 开放；
- B站批准的分类搜索使用 cursor + `data.pagination.next`，没有把本地时间边界伪装为 Provider 原生时间过滤；
- 快手 App Search V2 的业务参数保持最小，不伪造排序/时间筛选；首版 App 搜索/详情 + Web 评论是固定 Operation 组合，不是 fallback；
- Git compare 最终没有代码、Contract、Migration、依赖、锁文件或 `03-数据库与文件存储.md` 差异。

两阶段 Review：

1. **需求符合性**：统一 Pipeline、7 个用户问题、五平台文档、开发导航、独立业务调试、成本/抽样/Deep/时间 Warning 均已落到 08/collection/02/07；Scheduler 决策没有被偷偷批准。
2. **文档质量**：发现最初对 03 的整篇替换顺带压缩未变数据库/Job/备份约束，已在提交 PR 前恢复到 main 原文；最终只保留本任务直接相关的文档差异。未发现需要阻止 PR 的已知问题。

PR 之后以 GitHub Actions 的 `check_docs`、Secret、架构及现有回归作为新鲜集成证据；合并后再次检查 main CI。

# 兼容、Contract、Migration、部署和回滚

- 本 Change 只改变正式设计/导航，不改变当前运行行为。
- 公共 Contract/API：本 Change 无机器变化；Stage 7 实现时再按 08 建立版本化 Pydantic Capability/Plan/Decision Contract。
- Migration/数据库：本 Change 无变化；`run_comments`/Provider 预算身份/Plan 平台策略/评论抽样解释字段是 07/08 已批准的 Stage 7 目标，必须通过后续 L3 Migration 实施；实现该 Migration 时精准同步 03，禁止改写 Stage 1—6 Revision。
- 依赖/锁文件：无变化。
- 部署：无变化。
- 回滚：如需撤销，只回滚本 Change 文档；不涉及数据回滚。

# Git

- 基线 main：`ea57681d58fc9859a7963aab386a4de524f2024b`
- 分支：`docs/stage7-collection-pipeline`
- Change：`ready_for_review`
- PR：待创建
- CI：待 PR 运行
- 合并：未执行
- 归档：未执行
