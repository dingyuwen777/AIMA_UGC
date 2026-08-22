---
schema: rvc-change/v1
id: CHG-20260822-documentation-governance-sync
title: 当前实现一致性审计与文档分层治理
level: L2
status: in_progress
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

基于当前代码、Migration、Contract、生成物、锁文件、测试和配置，完成一次当前状态一致性审计，并把文档重构为：

```text
核心 Blueprint
→ 只维护长期架构方向、边界和关键跨模块决定

Appendix / Guide / 模块 README
→ Scheduler、TikHub、Excel、AI、Figma、报告、数据库调试等具体实现和技术细节

Roadmap
→ 当前做到哪里、哪些阶段尚未完成、怎样继续开发直到生产服务器上线

机器事实
→ 代码 / Contract / Migration / generated / tests / locks

changes/archive
→ 历史变更原因和当时验证证据
```

本轮用户最终确认：**Blueprint 编号 09—17 属于已完成阶段/专题形成的详细材料。如果其中仍有效的事实已经被其他正式文档完整承接，就不需要继续保留在 Blueprint。**

因此最终目标是把核心 Blueprint 收敛为 `01—08 + README`，同时确保“去重不等于删知识”：当前实现细节进入 Appendix/模块 README，精确结构进入机器事实，未完成阶段进入 Roadmap，历史原因进入 `changes/archive/`。

# 不允许丢失什么

删除 Blueprint 09—17 前，必须确认以下知识仍有清晰、可落地的新入口：

- Scheduler `latest_only`、Cron、Occurrence、并发、防重、事务、Deadline、恢复和排障；
- TikHub 五平台真实响应结构、Endpoint、JSON 路径、Fixture、Mapper、接口 A/B 与备用策略、真实验证台账；
- Excel 统一数据 Contract、Exporter、源文件 Reader/Sheet 发现、大文件/安全规则、离线调试、正式数据库 Export 边界；
- Report Source、统计口径、Markdown 模板、Office Chart、OOXML、词云、数据一致性和失败边界；
- AI `relevance / voice_type / sentiment / labels`、Prompt/Taxonomy、Validator、Retry、并发、Checkpoint、正式 PostgreSQL Analysis；
- 前端 Feature/Page/Store/API、Figma/Design-to-Code、视觉基线和 Element Plus/TypeScript 当前兼容边界；
- Stage 8 形成的 Excel/TikHub 统一入库、Import Batch、正式页面/API/Job、来源追溯、两层去重等长期事实；
- 尚未完成的认证、Monitoring、Production Release、协调 Backup/Restore、旧数据迁移等后续开发路线。

历史施工过程本身不需要在 Blueprint 重复保存；需要追溯时使用 `changes/archive/`。

# 最终文档分层

```text
AGENTS.md
→ Agent/开发统一规则和导航

docs/代码结构与修改导航.md
→ 业务修改问题到真实代码/Contract/表/测试

docs/blueprint/
→ README + 01—08 核心长期架构

docs/roadmap/
→ Stage 0—12 当前状态、下一阶段和生产 Go-Live 路线

docs/appendix/
→ PostgreSQL / Scheduler / TikHub / Excel / AI / Word / Production Release 等具体技术细节

docs/guides/
→ Figma 等开发工作流

模块 README
→ 当前模块实现、Owner、入口、修改方式

Contract / Migration / tables.py / generated / tests / locks
→ 精确机器事实

changes/archive/
→ 历史原因和已完成阶段证据
```

# Blueprint 09—17 内容承接矩阵

这里按“原文中的知识去哪了”而不是“一篇旧文档只对应一篇新文档”记录。

| 原 Blueprint | 当前承载 | 保全重点 |
| --- | --- | --- |
| 09 Scheduler | `docs/appendix/Scheduler调度执行与停机恢复.md` + Collection README + Blueprint 04/07/08 | `latest_only`、Occurrence 唯一身份、事务、Job Deadline、多 Scheduler、防重、停机恢复、排障 |
| 10 TikHub 真实响应 | `docs/appendix/TikHub五平台真实响应与字段映射.md` + `docs/collection/` + `tests/fixtures/providers/tikhub/` | 五平台 Endpoint、真实 JSON 路径、Pagination、Mapper、Fixture、快手 App/Web 证据 |
| 11 TikHub 多接口 | `docs/appendix/TikHub多接口验证与备用策略.md` + TikHub Operation/Capability 代码 | App/Web/V1/V2/V3 A/B 方法、Candidate/verified backup、为何禁止自动 fallback |
| 12 TikHub 验证台账 | `docs/appendix/TikHub接口选型与真实验证台账.md` + endpoint ledger Fixture + `pricing.toml` | 真实 Probe、主/备用接口、价格快照、A/B 数量/Jaccard、B站比较器勘误、快手 App/Web 结论 |
| 13 Excel/Report | `docs/appendix/Excel统一数据导出与离线调试.md` + `docs/appendix/数据入口与统一入库实现.md` + `backend/.../imports_test/README.md` + `docs/appendix/Word舆情报告生成与排版实现.md` + Reporting README | UnifiedDataExcel、三 Sheet/列投影、源 Excel/Sheet、JSONL、共享 Exporter、write-only、安全/验证，以及 Report Source/统计/Markdown/Office Chart/OOXML/词云 |
| 15 AI | `docs/appendix/AI舆情打标与分析实现.md` + Analysis README + `backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md` | V3 输入输出、相关性/发声类型、Validator、Validation/Transport Retry、离线并发/Checkpoint、正式 Job/表/current identity；完整 taxonomy 只留 Prompt |
| 16 Frontend/Figma | `frontend/README.md` + `docs/guides/Figma与前端设计开发工作流.md` + Blueprint 04 | 当前 Route/Feature、Page/Store/API/generated Client、视觉基线、Element Plus/TS7 兼容、Figma→Vue Vertical Slice |
| 17 Stage 8 | `docs/appendix/数据入口与统一入库实现.md` + `docs/API接口说明.md` + Frontend README + Ingestion/Content/Collection README + Roadmap | Excel/TikHub 四类入口、Canonical 汇合、Import Batch/来源链、两层去重、正式 API/Job/页面当前事实；后续阶段不在 Stage 8 文档继续维护 |

## 刻意不复制、改为导航到机器事实的内容

下列内容从旧长文退出并不属于“丢失”，因为继续人工复制反而会形成第二事实源：

```text
完整 SQLAlchemy 列/约束
→ tables.py + Migration

完整 HTTP Request/Response 字段
→ Pydantic Contract + OpenAPI + generated Client

完整 Canonical Schema
→ contracts/canonical.py + generated JSON Schema

完整 AI 9×39 taxonomy
→ content_labeling_v3.md

精确 TikHub 当前 endpoint/参数构造
→ operations/*.py + capabilities.py

精确 Excel Header/列常量
→ contracts/export/models.py + platform/export/excel.py
```

Appendix/README 必须解释这些结构为什么存在、调用链如何工作、要改哪里和怎么验证，但不长期复制第二套机器 Schema。

如果 CI 中还有测试直接依赖旧 Blueprint 路径，应把测试迁到新的正式事实源；不得通过保留过期 Blueprint 或删除/降低测试来绕过。

# AI taxonomy 特别处理

当前运行时完整 taxonomy 的唯一业务事实源继续是：

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md
```

现有 Analysis 单测曾直接解析 Blueprint 15 的 9×39 树作为重复文档基线。这与“Prompt 是唯一完整 taxonomy 事实源”的最终文档治理方向冲突。

本轮将该测试改为：

- 继续验证 Prompt 当前有 9 个一级、39 个二级；
- 验证正式 AI Appendix 明确导航到 Prompt；
- 不再要求 Blueprint 复制一份完整 taxonomy。

这样不是降低业务门禁，而是消除第二套 taxonomy 手工事实源。

# Roadmap 必须保留的未完成阶段

Blueprint 09—17 删除不等于“后续都完成”。Roadmap 继续明确：

```text
已完成基础
→ Stage 1—8 主要业务实现

部分完成
→ Stage 9 Analysis 已完成，Monitoring/Alert/VOC/Ticket 待产品确认/实现
→ Stage 10 Excel Export/离线 Word 已有，Word 报告中心是否产品化待业务决定

生产阻塞
→ 企业认证/后端授权
→ Stage 11A Dockerfile/Compose/Production Config
→ Stage 11B 离线 Release Bundle / 固定 image digest / SBOM / 来源验证
→ Stage 11C PostgreSQL + Artifact 协调 Backup/Restore
→ Stage 11D 部署/回滚自动化
→ Stage 11E 重启/reboot/容量/安全/恢复的真实生产服务器验收

按需
→ Stage 12 旧数据迁移与对账
```

未完成阶段不允许因为文档重构消失。

# 范围

- 当前实现一致性审计；
- Blueprint 01—08、README 和导航治理；
- Appendix/Guide/模块 README 当前实现说明；
- Roadmap 生产上线实施路线；
- 仅为迁移文档事实源而调整直接绑定旧文档路径的测试。

# 非目标

- 不修改运行时业务行为；
- 不修改 HTTP/Canonical/Job Contract；
- 不修改 Schema/Migration；
- 不修改 Prompt taxonomy 内容；
- 不修改 Provider/调度/Analysis/Export 业务语义；
- 不升级依赖；
- 不在本 Change 实现认证、Monitoring 或 Stage 11 Production Release。

# 成功标准

- [ ] `docs/blueprint/` 最终只保留 README + 01—08 核心文档；
- [ ] 原 09—17 的当前有效事实均能从 Appendix/Guide/模块 README/核心 Blueprint/机器事实找到；
- [ ] Stage 0—12 的当前状态、未完成阶段和生产上线阻塞项完整存在于 Roadmap；
- [ ] PostgreSQL 调试附录使用真实当前表/Owner/Migration，不复制第二套 Schema；
- [ ] Prompt 继续是完整 AI taxonomy 唯一业务事实源；测试不再依赖 Blueprint 15 复制 taxonomy；
- [ ] 所有旧 Blueprint 09—17 链接和测试依赖完成迁移；
- [ ] 不修改运行时代码、Contract、Schema、Migration、generated、依赖；
- [ ] 仅有必要的“文档事实源迁移测试”发生代码差异，不改变业务测试语义；
- [ ] `check_docs.py`、架构/Owner/Secret 门禁和相关测试通过；
- [ ] PR 最新 HEAD 的全部 GitHub Actions 成功后才进入合并。

# 已有验证与当前失败历史

候选 HEAD `ab9d7d00aaee4fbb02e15aeef803e058add5f913` 曾取得主 CI 与全部 Stage 专项全绿，但该结果只属于当时的候选，不可用于最终合并证明。

后续删除 Blueprint 15 时，Stage 5A 暴露了一个真实耦合：

```text
tests/unit/analysis/test_content_labeling.py
→ 直接解析 docs/blueprint/15-舆情AI打标与统一分析契约.md
→ 读取 ### 5.1 完整父子关系
```

这不是运行时代码缺陷，而是旧文档路径作为测试事实源的技术债。最终处理是把测试迁到 Prompt + AI Appendix 的新事实层级，而不是恢复 Blueprint 15 的第二套 taxonomy。

Scheduler 文档回归测试同理迁移到 `docs/appendix/Scheduler调度执行与停机恢复.md`，继续验证 `latest_only` 和 Job Deadline 等关键语义，不以保留 Blueprint 09 作为通过条件。

# 验证计划

1. 完成 09—17 → Appendix/Guide/README/Roadmap/机器事实的承接矩阵检查；
2. 更新直接绑定旧 Blueprint 路径的文档回归测试；
3. 删除 Blueprint 09—17 及本轮临时产生的重复兼容页；
4. 更新 `AGENTS.md`、根 README、Blueprint README、Appendix/Guide/Roadmap 导航；
5. 核对 `docs/环境运行与部署.md`：保留详细开发环境内容，修正当前 Migration 和生产 No-Go 事实；
6. 运行 PR 最新 HEAD 的 GitHub Actions；
7. 失败则读取具体 Job 日志修根因，不降低测试；
8. 全绿后将 Change 标记 `ready_for_review`、解除 Draft、合并 main；
9. 按仓库规则归档本 Change，并确认最终 main 新鲜状态。
