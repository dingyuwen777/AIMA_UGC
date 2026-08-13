---
schema: rvc-change/v1
id: CHG-20260813-stage3b-canonical-v1
title: Stage 3B Canonical 数据契约 V1
level: L3
status: in_progress
owner: dingyuwen777
branch: feature/stage3b-canonical-v1
created: 2026-08-13
updated: 2026-08-13
depends_on: []
affected_areas: [canonical, collection, content, architecture, contracts, ci]
affected_paths: [backend/src/aima_ugc/contracts/canonical/, contracts/canonical/, tests/contracts/, scripts/contracts/, docs/blueprint/01-总体架构与技术选型.md, docs/blueprint/02-采集系统与数据标准化.md, docs/blueprint/03-数据库与文件存储.md, docs/blueprint/04-后端任务API与前端.md, docs/blueprint/06-开发约束与分阶段实施.md, docs/blueprint/07-技术决策与实施门禁.md, docs/blueprint/README.md, README.md, AGENTS.md, .github/workflows/ci.yml]
contracts: [CanonicalContentV1, CanonicalCommentV1, CanonicalAuthorV1, CanonicalMetricsV1, CanonicalSourceV1]
data_changes: []
---

# 目标

建立 Provider 无关的 Canonical V1 机器 Contract，使 TikHub、平台官方 API、Apify、自建采集器、文件/历史导入等不同采集途径只能在 Canonical 之前各自适配，Canonical 之后复用统一 Ingestion/Persistence 与 Query 边界。

同时固化数据持久化与查询中间层：Mapper 不写数据库；Ingestion Service 只消费 Canonical 并调用 Owner Repository；API/页面不直接 SQL，而通过 Query Repository/Read Model 与 Application/Query Service 获取数据。

# 可观察成功标准

- [ ] Pydantic 是 Canonical 唯一手写事实源，JSON Schema 由脚本生成到 `contracts/canonical/`。
- [ ] `CanonicalContentV1`、`CanonicalCommentV1`、`CanonicalAuthorV1`、`CanonicalMetricsV1`、`CanonicalSourceV1` 具有明确版本、字段语义、空值和时间规则。
- [ ] 固定合法脱敏示例可以被生产 Pydantic Model 与生成 JSON Schema 校验。
- [ ] JSON Schema 生成物由 CI 重生检查零漂移，禁止手工编辑。
- [ ] Canonical 不依赖 TikHub SDK/字段/Endpoint；`provider` 是 Adapter 标识而不是固定为 TikHub。
- [ ] Blueprint 明确支持 TikHub 之外的 Provider/采集途径，Provider 可使用 HTTP、SDK、本地文件等不同传输方式，但都产出不可变 Raw Evidence/Candidate 再进入 Mapper。
- [ ] Blueprint 明确 `Provider → Raw → Mapper → Canonical → Ingestion Service → Owner Repository → PostgreSQL` 的写入边界。
- [ ] Blueprint 明确 `PostgreSQL → Query Repository/Read Model → Query/Application Service → API` 的读取边界。
- [ ] 不新增独立数据库中间微服务；中间层是模块化单体中的应用/持久化边界。
- [ ] Stage 1/2/3A/Windows 既有 CI 继续通过，并增加 Canonical Contract 门禁。

# 范围

## 本次实现

- Canonical V1 Pydantic Models；
- JSON Schema 生成/检查；
- 固定脱敏 Canonical examples；
- Contract Tests 与兼容性基本门禁；
- Provider-agnostic 采集架构文档；
- Canonical → Ingestion/Persistence 与 DB → Query 中间层文档边界；
- 对相关 `AGENTS.md`/Blueprint 的术语和硬约束同步。

## 非目标

- 任何具体 TikHub/Apify/官方 API Client、Operation 或 Mapper；
- 五平台批量实现；
- `contents/comments` 数据库表、Ingestion Repository 正式实现；
- API/前端业务页面；
- Job Runtime；
- 登录/飞书/OIDC；
- 自动 Retention；
- 生产 Release。

# 方案比较

## A. 每个采集途径直接映射数据库 Schema

不采用。Provider/平台变化会直接扩散到数据库和 API，无法替换 TikHub，也会让每个采集器分别实现去重、历史和持久化规则。

## B. 统一 Canonical，但 Mapper 直接调用 Repository；读取端直接复用写 Repository

不采用。虽然字段统一，但采集映射、业务摄取、事务/历史规则和 SQL 仍耦合；写模型和页面查询也会相互污染。

## C. Provider Adapter → Raw → Mapper → Canonical → Ingestion + Owner Repository；Query Repository/Read Model 独立读取（采用）

Canonical 是所有采集方式共同的数据交换 Contract。Mapper 只翻译事实；Ingestion 负责幂等、历史、事务和模块协作；Owner Repository 负责 PostgreSQL 写入；查询走独立 Query Repository/Read Model。该方案满足替换采集途径与数据库边界隔离，又不新增微服务或万能 Repository。

# 已确认关键决策

- TikHub 只是首个 Provider Adapter，不是系统采集架构本身；以后可以增加官方 API、Apify、自建采集器、文件/历史导入等 Adapter。
- Provider Adapter 可以使用不同传输机制，但 Provider 私有响应只能停留在 Raw/Adapter/Mapper 边界，不能成为公共业务结构。
- Canonical 之后的 Ingestion/Persistence 与读取 Query 边界与具体 Provider 无关。
- 中间层是模块化单体中的逻辑/代码边界，不额外创建独立服务进程。
- PostgreSQL 仍是唯一业务事实库；Repository/Query 边界不是第二事实源。

# 用户待决策门禁

Canonical 作者字段会冻结个人信息能力。当前 Blueprint 示例包含内容作者外部 ID/昵称、评论作者外部 ID/昵称哈希，但阶段 0 仍把个人信息规则标记为未决。

依照 `AGENTS.md`，在最终冻结 `CanonicalAuthorV1` 前必须由用户决定。与该决定无关的 Provider-agnostic 架构、生成链和中间层边界可以继续。

# 兼容、Migration、部署与回滚

- 这是首个正式 Canonical V1，没有旧 Canonical 机器 Contract 需要数据迁移；旧 Blueprint 示例不是可兼容运行时 Schema。
- 本阶段不创建数据库 Migration；`contents/comments` Schema 仍留后续阶段。
- Canonical V1 一旦合并，删除字段、改类型/语义、可选改必填属于破坏性变化，必须新 Change 并评估版本升级。
- 回滚为回退本 PR/Contract；不存在生产数据回填。
- 生产部署仍 No-Go。

# TDD / 验证计划

1. Red：先加入 Contract Test，要求 Canonical 模块和生成 JSON Schema 存在，确认因实现缺失失败。
2. Green：最小 Pydantic Model、生成脚本、examples；只实现已批准字段。
3. 验证：Ruff、mypy、Contract Tests、Schema drift、现有完整 CI。
4. Review：先检查 Provider 无关性/用户决策边界/兼容，再检查类型、校验、时间、空值和生成链。

# Git

- 基线 main：`4440e9b156ca0ddf52aaf3eed80cdcea28a7bad1`
- 分支：`feature/stage3b-canonical-v1`
- PR/CI/合并：实施后记录。
