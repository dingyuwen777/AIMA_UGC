---
schema: rvc-change/v1
id: CHG-20260822-current-implementation-audit
title: 当前代码实现与文档一致性审计
level: L2
status: ready_for_review
owner: dingyuwen777
branch: docs/current-implementation-audit-20260822
created: 2026-08-22
updated: 2026-08-22
depends_on: []
affected_areas:
  - documentation
  - architecture_navigation
  - roadmap
  - module_readme
  - change_history
affected_paths:
  - docs/blueprint/01-总体架构与技术选型.md
  - docs/API接口说明.md
  - docs/测试与调试说明.md
  - docs/roadmap/生产上线实施路线.md
  - changes/active
  - changes/archive
contracts: []
data_changes: []
---

# 目标

基于当前 `main` 的代码、Contract、Migration、测试、依赖和已合并 PR 事实，系统检查仓库正式文档是否准确描述当前实现；修正文档中已经过期、互相冲突、指向不存在文件、遗漏关键业务/技术语义或把未来设计误写成当前事实的内容，并重新评估生产上线后续阶段是否仍然合理。

本 Change 只同步事实与阶段导航，不改变运行时代码、公共 Contract、Schema、Migration、依赖或业务行为。

# 可观察成功标准

- [x] 当前模块、进程、Job、前端路由、数据入口、Analysis、Reporting、日志、部署边界等关键事实都由机器事实重新核对。
- [x] Blueprint、Roadmap、Appendix、Guide、模块 README、根 README、API/测试/运行文档中的本轮已发现实现冲突已修正。
- [x] 已合并但仍停留在 Active/`ready_for_review` 的历史 Change 按真实 Git 状态收口，旧 Blueprint 路径改为当前长期承载路径并归档。
- [x] 关键业务/逻辑方案按正确文档层表达；精确 Schema/Prompt/OpenAPI 仍由机器事实维护，不复制第二份。
- [x] 已批准但未实现的生产目标仍只保留为 Roadmap/正式设计，不误写成当前机器事实。
- [x] 后续阶段按当前代码重新评估，明确合理项、需要重排项、需要用户上游决策项和下一最小正式开发单元。
- [x] 实质文档内容 HEAD `22a0b21e01f31868dcbb5d04d5ec634f72a9c2c8` 的本轮新鲜 CI/专项 Workflow 全部通过；本次仅收口 Change/PR 元数据后，仍以 PR 最新 HEAD 的新鲜 Workflow 为最终合并门禁。

# 范围

- 根导航、核心 Blueprint、Roadmap、Appendix/Guide、前后端/模块 README、API/测试/运行说明与 Change 状态中的当前事实核对。
- 读取与文档主张直接相关的实现、Contract、Migration、测试、锁文件和已合并 PR 作为证据。
- 修正旧文档路径、旧阶段状态、错误的“当前/未实现/已完成”描述。
- 评估 Roadmap 的阶段划分和顺序，但不实现未来阶段。

# 非目标

- 不新增业务功能。
- 不修改 API、Contract、Schema、Migration、依赖、Prompt 业务分类或运行时代码。
- 不因为文档审计顺手重构生产代码。
- 不恢复已经被正式后续决策替代的历史方案。

# 必须保持不变

- 当前代码和机器事实不因文档便利被改写。
- Blueprint 只维护长期架构和跨模块边界；Appendix/README 承载实现细节；Roadmap 承载未完成阶段。
- 完整 Taxonomy、数据库字段和 OpenAPI 继续以机器事实为唯一精确来源。
- CI、Branch Protection、PR 与质量门禁不绕过。

# 已确认关键决策

- 本轮冲突判断不是机械“代码优先”；先区分代码缺陷、文档过期、未来设计和已批准但未实现目标。
- 文档更新遵循“改变职责，不减少知识”；已有高价值实现/调试细节不能因结构整理被压缩丢失。
- 用户要求对后续设计阶段做合理性评估，本轮只更新 Roadmap/文档，不提前实现生产能力。

# 审计事实与修正

## 1. 生产部署当前事实被 Blueprint 01 写错

机器事实和正式运行文档证明当前仓库根没有：

```text
Dockerfile
compose.yaml
compose.production.yaml
env.production.example
```

但 `docs/blueprint/01-总体架构与技术选型.md` 原文把：

```text
Docker Compose = 当前部署基础
Nginx = 当前前端/反向代理
```

写成当前事实，目录树也列出 `Dockerfile / compose*.yaml`。

修正为：

- PostgreSQL/Job/Local ArtifactStore/Vue+Vite 是当前机器事实；
- Docker/Compose/Nginx 是 Stage 11A 已批准但尚未实现的生产目标；
- 当前目录树不再列不存在的文件；
- Stage 11 目标继续由 Roadmap/Production Appendix 保留。

## 2. PostgreSQL Integration 文档指向不存在 Compose

`docs/测试与调试说明.md` 原文把：

```text
compose.yaml
compose.local.yaml
```

列为当前本地数据库配置源，但仓库没有这些文件；`docs/环境运行与部署.md` 也明确要求开发者自行提供可访问 PostgreSQL 18 实例。

修正为：

```text
env.local.example
PlatformSettings
+ 自行提供的隔离 PostgreSQL 18
```

并明确 CI Service Container 不等于仓库已经提供本地/生产 Compose。

## 3. Export 列表 API 被文档虚构了分页/筛选

当前：

```text
GET /api/v1/data-exports
```

Route 没有 Query 参数；`PostgresReportingHttpService.list_exports()` 直接调用 Repository 的 `list_recent()` 并返回 `DataExportListResponse.items`。

`docs/API接口说明.md` 原文却写“支持当前 Contract 定义的分页/筛选”。已经改为当前真实语义，并明确不要把创建 Export 时的 `ContentFilterSnapshot` 和 Export 列表筛选混为一谈。

## 4. 两个已合并 Change 仍错误留在 Active

真实 Git：

```text
PR #111 已合并
merge = 36e8ed6c23b73c08a85f632fe06725aaae97905c

PR #113 已合并
merge = a86b80a4d9c3246b9dcb3f5a688497c82565d084
```

但对应 Change 仍写 `ready_for_review / 未合并`，且继续引用已经删除的旧 Blueprint 09/13。

已按真实状态移动到：

```text
changes/archive/2026-08/CHG-20260821-report-visual-fidelity/
changes/archive/2026-08/CHG-20260821-diagnostic-logging/
```

并记录当前长期承载分别是 Word Report Appendix、Blueprint 05 和 Scheduler Appendix。

## 5. 后续 Stage 拆分合理，但原执行顺序需要纠正

Stage 0—12 的能力拆分总体合理；问题在于旧 Roadmap 把它表达成过度串行的 P0→P8，并把 Legacy Migration 固定排在最终生产验收和可选产品能力之后。

修正为两条轨道：

```text
生产硬门禁
→ Auth / Stage 11A—11E
→ 如果首发必须带旧数据，Stage 12 也成为 Stage 11E 前置

条件产品轨
→ Stage 9B Monitoring/Alert/VOC/Ticket
→ Stage 10B Web Report Center
→ 是否阻塞首发由产品/SLO 决策
```

P0 冻结后，Auth、11A、11C 和条件 Legacy Migration 可以按独立 Change 并行；11B 依赖 11A，11D 依赖可部署 Release + 可恢复 Backup，11E 是最终综合验收。

## 6. 本轮重新确认但无需修改的关键事实

- 当前模块仍为 `system / collection / content / ingestion / analysis / reporting`；没有正式 Monitoring/Alert/VOC/Ticket/Dashboard 模块。
- Worker Registry 仍为 `collection.run.v1 / ingestion.import-excel.v1 / analysis.content-label.v1 / reporting.content-export-excel.v1`。
- 前端路由仍为 `/ /voice-plaza /collection-runtime /collection-strategy`。
- AI V3 仍以 `relevance + voice_type + sentiment + labels` 为当前正式输出；真实用户发声唯一规则仍是 `voice_type == user_voice`。
- Rule Relevance 与 AI Semantic Relevance 仍是不同层；AI irrelevant 数据库保留、默认业务列表过滤的语义仍由 Analysis/Content 当前实现和文档一致表达。
- 正式 PostgreSQL Excel Export 与离线 Word Report 仍是不同能力；当前没有正式 `/reports` API/Report Center。
- Production Appendix、环境运行文档、根 README、Frontend README、主要模块 README 和核心 Blueprint 02—08 的本轮重点事实与代码一致，不需要为了“全部更新”制造无意义改动。

# 后续设计评估

当前推荐先完成 P0 仍缺的上游决定：

```text
企业身份 Provider
角色 / Permission
生产网络暴露边界
RPO / RTO
Raw / Content / Artifact / Log 保留周期
容量/性能验收目标
首次上线是否必须迁旧历史数据
```

这些决定一旦冻结，下一批可以拆成独立 L3 Change：

```text
企业认证 / Backend Authorization
Stage 11A Docker / Compose / Production Config
Stage 11C Coordinated Backup / Restore（在 RPO/RTO/目录冻结后）
Stage 12 Legacy Migration（仅首发需要旧数据时）
```

不要默认先做 Monitoring 或 Web Report Center，也不要在没有 P0 决策时直接把生产安全参数写死进 Docker/Backup 实现。

# 任务

- [x] 读取当前 `main` 的 `AGENTS.md`、Reliable Vibe Coding Skill、Blueprint 导航/门禁、Roadmap 和代码导航。
- [x] 检查 Active Change 与已合并 PR 状态并修正历史状态冲突。
- [x] 复核当前机器事实与主要正式文档。
- [x] 修正发现的文档冲突与遗漏。
- [x] 更新 Roadmap 阶段评估与下一步建议。
- [x] 实质文档内容 HEAD 的本轮新鲜 CI/专项 Workflow 全部通过；最终仍检查 PR 最新 HEAD。
- [x] 创建 Draft PR #139；当前 Change 进入 `ready_for_review`，满足最新 HEAD 门禁后可把 PR 标记 Ready。归档只在 PR 实际合并后进行。

# 验证结果

实质文档内容 HEAD：

```text
22a0b21e01f31868dcbb5d04d5ec634f72a9c2c8
```

新鲜 Workflow：

```text
CI #1847                                  success
Stage 6 XHS Vertical Slice #1662         success
Stage 7 Keyword Packs #1457              success
Stage 7 Provider Config Routing #1570    success
Stage 7 Plan Occurrence Run Snapshot #1455 success
Stage 7 Scheduler Runtime #1797          success
```

主 CI 中：

- Stage 1：锁定 Python/Node 环境、generated contract/client、backend/repository checks、Wheel、frontend checks 全部通过；
- Stage 2 Platform：unit + PostgreSQL integration + real readiness smoke 通过；
- Stage 3A Database：Schema/Owner、空库 migration、repository integration、Stage 8B import、previous revision/base round trip 通过；
- Windows bootstrap 通过。

其中 `Backend and repository checks` 包含当前仓库的 Ruff/mypy/pytest 与架构、table ownership、secret、docs 等质量门禁，未为本轮文档修改绕过任何检查。

本次提交只更新 Change 交付状态与上述验证记录；它会产生新的 PR HEAD，因此**真正允许合并时仍必须以 PR 最新 HEAD 的新鲜 Workflow 为准**。

# 文档影响

实际修改：

```text
docs/blueprint/01-总体架构与技术选型.md
docs/API接口说明.md
docs/测试与调试说明.md
docs/roadmap/生产上线实施路线.md
changes/active → changes/archive（两个已合并历史 Change）
```

未修改运行时代码、公共 Contract、Schema、Migration、Prompt 或依赖。

# Git / PR / 发布

- 分支：`docs/current-implementation-audit-20260822`
- PR：#139 `校正文档当前实现事实并重排生产阶段依赖`
- 当前 PR 状态：Draft；本 Change 为 `ready_for_review`，待最新 HEAD 新鲜 Workflow 全绿后将 PR 标记 Ready。
- Merge：仅在 PR 最新 HEAD 质量门禁通过且有合并授权后执行。
- 归档：仅在 PR 实际合并后把本 Change 移入 `changes/archive/`。
- 发布/生产部署：不属于本 Change。
