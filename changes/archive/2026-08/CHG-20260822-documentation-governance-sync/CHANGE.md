---
schema: rvc-change/v1
id: CHG-20260822-documentation-governance-sync
title: 当前实现一致性审计与文档分层治理
level: L2
status: done
owner: dingyuwen777
branch: docs/documentation-governance-sync
created: 2026-08-22
updated: 2026-08-22
depends_on: []
affected_areas:
  - documentation
  - architecture
  - database
  - collection
  - scheduler
  - ingestion
  - analysis
  - reporting
  - frontend
  - release
affected_paths:
  - AGENTS.md
  - README.md
  - docs
  - frontend/README.md
  - backend/src/aima_ugc/**/README.md
  - tests/unit/analysis/test_content_labeling.py
  - tests/unit/collection/test_stage1_stage7_comprehensive_corrective.py
  - changes/active
  - changes/archive/2026-08
contracts: []
data_changes: []
---

# 目标

基于当时 `main` 的当前代码、Migration、Contract、生成物、锁文件、测试和配置，对正式技术文档做一致性审计和结构治理，使文档能够真正用于理解代码、定位实现、调试和继续开发到生产上线。

最终文档分层固定为：

```text
核心 Blueprint
→ 长期架构方向、边界和关键跨模块决定

Appendix / Guide / 模块 README
→ Scheduler、TikHub、Excel、AI、Figma、报告、数据库、Production Release 等具体实现和技术细节

Roadmap
→ 当前做到哪里、哪些阶段尚未完成、怎样继续开发直到生产服务器上线

机器事实
→ 代码 / Contract / Migration / generated / tests / locks

changes/archive
→ 历史变更原因和当时验证证据
```

本 Change 不新增运行时业务能力，不修改 HTTP/Canonical/Job Contract、Schema、Migration、依赖、Prompt taxonomy 或 generated Client。

# 关键决策

## 1. 文档重构不能等于信息压缩

原 Blueprint 09—17 中仍有效的 Endpoint、真实 JSON 路径、Fixture、分页、状态机、事务/恢复边界、SQL、AI Retry/Checkpoint、Excel/Word/OOXML、前端视觉和生产 Release 设计必须先迁到正确 Owner，才能删除重复文档。

早期候选曾把 Appendix 写成过度摘要，导致信息密度下降。该方向被撤销，后续以旧长文作为“知识保全基线”，再用当前代码事实做勘误和补充。

## 2. Blueprint 收敛为 README + 01—08

原 09—17 是已完成 Stage/专题开发过程中形成的详细材料。当前有效内容已经由 Appendix、Guide、模块 README、核心 Blueprint、Roadmap 或机器事实完整承接，因此最终从核心 Blueprint 删除，避免重复维护。

## 3. 未完成开发阶段必须保留

删除 Stage 型旧文档不等于后续阶段完成。新增：

```text
docs/roadmap/生产上线实施路线.md
```

作为 Stage 0—12 当前状态和生产 Go-Live 路线的长期事实源。

当前仍需继续实施的主要工作包括：

```text
Stage 9
→ Analysis 已完成
→ Monitoring / Alert / VOC / Ticket 待产品确认和实现

Stage 10
→ 正式 Excel Export 与离线 Word Report 已实现
→ 是否产品化成网页报告中心待业务决定

生产前置
→ 企业认证与后端 Authorization

Stage 11A
→ Dockerfile / Compose / Production Config

Stage 11B
→ 离线 Release Bundle / 固定 image digest / SBOM / 来源与完整性验证

Stage 11C
→ PostgreSQL + Artifact 协调 Backup/Restore 与恢复演练

Stage 11D
→ 部署 / 回滚自动化

Stage 11E
→ 真实生产服务器部署、restart/reboot、容量、安全和关键业务 Smoke 验收

Stage 12（按需）
→ 旧数据迁移与对账
```

## 4. 精确机器结构不复制第二份

下列内容由唯一机器事实维护：

```text
完整 SQLAlchemy 列/约束
→ tables.py + Migration

完整 HTTP Request/Response
→ Pydantic Contract + OpenAPI + generated Client

完整 Canonical Schema
→ canonical Contract + generated JSON Schema

完整 AI 9×39 taxonomy
→ backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md

精确 TikHub endpoint/参数构造
→ operations/*.py + capabilities.py

精确 Excel Header/列常量
→ contracts/export/models.py + platform/export/excel.py
```

文档负责讲清设计原因、数据/调用链、代码入口、修改方法、测试和限制，不再长期复制第二套 Schema/Taxonomy。

# Blueprint 09—17 内容承接矩阵

| 原 Blueprint | 最终承载 | 保全重点 |
| --- | --- | --- |
| 09 Scheduler | `docs/appendix/Scheduler调度执行与停机恢复.md` + Collection README + Blueprint 04/07/08 | `latest_only`、Occurrence、事务、Job Deadline、多 Scheduler、防重、停机恢复、排障 |
| 10 TikHub 真实响应 | `docs/appendix/TikHub五平台真实响应与字段映射.md` + `docs/collection/` + Provider Fixture | 五平台 Endpoint、真实 JSON 路径、Pagination、Mapper、Fixture、快手 App/Web 实证 |
| 11 TikHub 多接口 | `docs/appendix/TikHub多接口验证与备用策略.md` + Operation/Capability 代码 | App/Web/V1/V2/V3 A/B、Candidate/verified backup、禁止静默自动 fallback |
| 12 TikHub 验证台账 | `docs/appendix/TikHub接口选型与真实验证台账.md` + endpoint ledger Fixture + Pricing | 真实 Probe、主/备用接口、价格、A/B/Jaccard、历史勘误 |
| 13 Excel/Report | Excel 附录 + 统一入库附录 + `imports_test` README + Word 报告附录 + Reporting README | UnifiedDataExcel、三 Sheet、源 Excel/Sheet、JSONL、共享 Exporter、安全/验证、统计/Markdown/Chart/OOXML/词云 |
| 15 AI | AI 附录 + Analysis README + Prompt | V3 输入输出、相关性/发声类型、Validator、两类 Retry、离线并发/Checkpoint、正式 Job/表/current identity；完整 taxonomy 只留 Prompt |
| 16 Frontend/Figma | `frontend/README.md` + Figma Guide + Blueprint 04 | Route/Feature、Page/Store/API/generated Client、视觉基线、Element Plus/TS7 兼容、Design-to-Code |
| 17 Stage 8 | 统一入库附录 + API 文档 + Frontend/Ingestion/Content/Collection README + Roadmap | Excel/TikHub 统一入口、Canonical 汇合、Import Batch、来源链、两层去重、API/Job/页面当前事实 |

# 主要交付

- 重构 `AGENTS.md`、根 README 和 Blueprint README 的事实与导航；
- 新增 `docs/代码结构与修改导航.md`；
- 将 Blueprint 01—08、API、测试/调试、环境部署、前端、Collection 平台文档和模块 README 更新到当前代码事实；
- 新增/增强 PostgreSQL、Scheduler、TikHub、统一入库、Excel、AI、Word 报告、Production Release 等专题附录；
- 新增 Figma/Design-to-Code Guide；
- 新增生产上线 Roadmap；
- 删除内容已完整承接的 Blueprint 09—17；
- 修正旧文档中“已实现/未实现”互相矛盾、旧表名/Job 名、旧路由/页面、旧 Stage 描述等问题；
- 将 PostgreSQL 常用查询、Job/Run/Batch/Analysis/Export 排障、Alembic 和安全事务操作固化为可实践附录；
- 保留前端 Stage 8C/8D/8E 视觉基线、Element Plus/TypeScript 7 兼容决策；
- 保留共享 LLM Adapter 当前模型价格、计费时段、Transport/Validation Retry 和请求审计说明；
- 保留并明确 Production Release 的目标宿主目录、服务拓扑、离线 Bundle、Backup/Restore、发布和回滚设计，同时明确当前仓库还没有 Dockerfile/Compose。

# 关键事实勘误

本轮以当前机器事实确认：

- 后端业务模块为 `system / collection / content / ingestion / analysis / reporting`；当前没有正式 Monitoring/Alert/VOC/Ticket/Dashboard 模块；
- Worker Job 为 `collection.run.v1 / ingestion.import-excel.v1 / analysis.content-label.v1 / reporting.content-export-excel.v1`；
- Vue 路由为 `/`、`/collection-runtime`、`/collection-strategy`、`/voice-plaza`；
- `voice_type` 当前 7 类，真实用户发声唯一业务判断为 `voice_type=user_voice`；
- 规则 Relevance 与 AI Semantic Relevance 是两层能力；AI relevance 保存于 `analysis_content_results.relevance`，`contents` 没有平行 `is_relevant` AI 列；
- Analysis 正式表为 `analysis_content_results / analysis_content_requests / analysis_content_request_items / analysis_content_label_pairs`；Result 当前没有 token/cost 列；
- Reporting 正式表为 `reporting_data_exports / reporting_data_export_items`，Job 为 `reporting.content-export-excel.v1`；
- 正式数据库 Excel Export 与离线 Markdown/Word Renderer 是不同能力；
- 当前仓库根没有 `Dockerfile`、`compose.yaml`、`compose.production.yaml`、`env.production.example`；Production Release 是 Stage 11 待实现；
- 旧 Provider Budget Account / Reservation Ledger 设计已被后续正式决定替代，不再作为当前待办。

# 文档事实源测试迁移

删除 Blueprint 09/15 后，两个既有测试暴露了对旧文档路径的直接耦合：

```text
tests/unit/collection/test_stage1_stage7_comprehensive_corrective.py
→ Scheduler 文档事实源迁到 Scheduler Appendix

tests/unit/analysis/test_content_labeling.py
→ taxonomy 基线直接从 Prompt 读取
→ AI Appendix 只需明确导航到唯一完整 taxonomy 事实源
```

测试仍验证原关键业务/文档语义，没有删除或放宽断言。

# 验证与 Git 交付

PR：#137 `重构技术文档并固化生产上线实施路线`

最终 PR Head：

```text
554ccedafbcfedb8d50ba8de7715abadba1d4a3c
```

该 Head 的永久 GitHub Actions 全部成功：

```text
CI                                   #1843 success
Stage 5A Provider Raw                #1332 success
Stage 5B Collection Execution        #1290 success
Stage 5C Provider Persistence        #1287 success
Stage 5D Provider Dispatch           #1288 success
Stage 6 XHS Vertical Slice           #1658 success
Stage 7 Keyword Packs                #1453 success
Stage 7 Provider Config Routing      #1566 success
Stage 7 Plan Occurrence Run Snapshot #1451 success
Stage 7 Scheduler Runtime            #1793 success
Stage 1-7 Audit Correctness          #788  success
```

主 CI 的 Stage 1（Backend/Repository、Wheel、Frontend）、Stage 2 Platform、Stage 3A Database、Windows bootstrap 全部成功；Stage 5D 的 Unit/Contract、PostgreSQL/Artifact、Raw replay、Ruff、Mypy、Architecture/Owner、Secret/Docs、Contract 和 Migration round-trip 全部成功。

PR #137 无 Review/Thread 阻塞，使用 `expected_head_sha=554cced...` 合并，防止候选漂移。

合并结果：

```text
main merge commit
6dcfd3613badb8640c5e8e5e9c36ef450cea9eb6
```

合并后重新读取 `main/AGENTS.md`，确认新的 Blueprint/Appendix/Roadmap 导航已经成为主分支当前规则。

# 兼容、数据、部署与回滚

- 运行时代码行为：未修改；
- HTTP/Canonical/Job Contract：未修改；
- 数据库 Schema/Migration：未修改；
- Prompt taxonomy：未修改；
- 依赖/Lock/generated Client：未修改；
- 本 Change 本身不部署生产服务；
- 当前生产状态仍是 No-Go，真实上线继续按 `docs/roadmap/生产上线实施路线.md` 推进认证和 Stage 11；
- 若需要回退本次文档治理，可回退 PR #137 merge，但不会涉及数据库 downgrade。

# 最终状态

成功标准全部完成，PR #137 已合并到 `main`。本 Change 现在仅做历史归档，当前系统技术事实由 Blueprint、Appendix、Guide、Roadmap、模块 README 和机器事实维护。