---
schema: rvc-change/v1
id: CHG-20260822-documentation-governance-sync
title: 当前实现一致性审计与文档分层治理
level: L2
status: ready_for_review
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
→ 长期架构方向、边界和关键跨模块决定

Appendix / Guide / 模块 README
→ Scheduler、TikHub、Excel、AI、Figma、报告、数据库调试等具体实现和技术细节

Roadmap
→ 当前做到哪里、哪些阶段尚未完成、怎样继续开发直到生产服务器上线

机器事实
→ 代码 / Contract / Migration / generated / tests / locks

changes/archive
→ 历史变更原因和当时验证证据
```

本轮最终确认：Blueprint 09—17 属于已完成阶段/专题形成的详细材料；其中仍有效的事实已被 Appendix、Guide、模块 README、核心 Blueprint、Roadmap 或机器事实完整承接，因此从核心 Blueprint 删除，避免重复维护。

核心 Blueprint 最终收敛为 `README + 01—08`。去重不等于删知识：当前实现细节进入 Appendix/模块 README，精确结构进入机器事实，未完成阶段进入 Roadmap，历史过程进入 `changes/archive/`。

# 不允许丢失的技术信息

删除 Blueprint 09—17 前，本 Change 已逐项确认以下知识有新的正式承载：

- Scheduler `latest_only`、Cron、Occurrence、并发、防重、事务、Deadline、恢复和排障；
- TikHub 五平台真实响应结构、Endpoint、JSON 路径、Fixture、Mapper、接口 A/B、备用策略和真实验证台账；
- Excel 统一数据 Contract、Exporter、源文件 Reader/Sheet 发现、大文件/安全规则、离线调试和正式数据库 Export；
- Report Source、统计口径、Markdown 模板、Office Chart、OOXML、词云、数据一致性和失败边界；
- AI `relevance / voice_type / sentiment / labels`、Prompt/Taxonomy、Validator、Retry、并发、Checkpoint 和正式 PostgreSQL Analysis；
- 前端 Feature/Page/Store/API、Figma/Design-to-Code、视觉基线和 Element Plus/TypeScript 当前兼容边界；
- Stage 8 形成的 Excel/TikHub 统一入库、Import Batch、正式页面/API/Job、来源追溯和两层去重；
- 尚未完成的认证、Monitoring、Production Release、协调 Backup/Restore、旧数据迁移等后续开发路线。

历史施工过程不在当前技术文档重复保存，需要追溯时使用 `changes/archive/`。

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

| 原 Blueprint | 当前承载 | 保全重点 |
| --- | --- | --- |
| 09 Scheduler | `docs/appendix/Scheduler调度执行与停机恢复.md` + Collection README + Blueprint 04/07/08 | `latest_only`、Occurrence 唯一身份、事务、Job Deadline、多 Scheduler、防重、停机恢复、排障 |
| 10 TikHub 真实响应 | `docs/appendix/TikHub五平台真实响应与字段映射.md` + `docs/collection/` + `tests/fixtures/providers/tikhub/` | 五平台 Endpoint、真实 JSON 路径、Pagination、Mapper、Fixture、快手 App/Web 证据 |
| 11 TikHub 多接口 | `docs/appendix/TikHub多接口验证与备用策略.md` + TikHub Operation/Capability 代码 | App/Web/V1/V2/V3 A/B 方法、Candidate/verified backup、禁止自动 fallback 的原因 |
| 12 TikHub 验证台账 | `docs/appendix/TikHub接口选型与真实验证台账.md` + endpoint ledger Fixture + `pricing.toml` | 真实 Probe、主/备用接口、价格快照、A/B 数量/Jaccard、B站比较器勘误、快手 App/Web 结论 |
| 13 Excel/Report | Excel 附录 + 统一入库附录 + `imports_test` README + Word 报告附录 + Reporting README | UnifiedDataExcel、三 Sheet/列投影、源 Excel/Sheet、JSONL、共享 Exporter、write-only、安全/验证、Report Source/统计/Markdown/Office Chart/OOXML/词云 |
| 15 AI | AI 附录 + Analysis README + `backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md` | V3 输入输出、相关性/发声类型、Validator、Validation/Transport Retry、离线并发/Checkpoint、正式 Job/表/current identity；完整 taxonomy 只留 Prompt |
| 16 Frontend/Figma | `frontend/README.md` + Figma Guide + Blueprint 04 | 当前 Route/Feature、Page/Store/API/generated Client、视觉基线、Element Plus/TS7 兼容、Figma→Vue Vertical Slice |
| 17 Stage 8 | 统一入库附录 + API 文档 + Frontend/Ingestion/Content/Collection README + Roadmap | Excel/TikHub 四类入口、Canonical 汇合、Import Batch/来源链、两层去重、正式 API/Job/页面当前事实 |

# 刻意只导航到机器事实的内容

下列内容不再在多份文档手工复制，这不是信息丢失，而是消除第二事实源：

```text
完整 SQLAlchemy 列/约束
→ tables.py + Migration

完整 HTTP Request/Response 字段
→ Pydantic Contract + OpenAPI + generated Client

完整 Canonical Schema
→ contracts/canonical.py + generated JSON Schema

完整 AI 9×39 taxonomy
→ content_labeling_v3.md

精确 TikHub endpoint/参数构造
→ operations/*.py + capabilities.py

精确 Excel Header/列常量
→ contracts/export/models.py + platform/export/excel.py
```

Appendix/README 负责解释为什么存在、完整调用链、修改入口、调试方法和边界；精确结构由机器事实维护。

# AI taxonomy 与 Scheduler 文档门禁迁移

完整 AI taxonomy 的唯一业务事实源继续是：

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md
```

`tests/unit/analysis/test_content_labeling.py` 不再解析已删除 Blueprint 15 的 9×39 重复树，而是：

- 直接验证 Prompt 当前 9 个一级、39 个二级；
- 验证 AI Appendix 明确导航到 Prompt；
- 继续验证生产 Python 不硬编码具体标签。

Scheduler 文档回归测试同理迁到：

```text
docs/appendix/Scheduler调度执行与停机恢复.md
```

继续验证 `latest_only`、Job Deadline 等关键语义，不通过保留 Blueprint 09 制造重复文档。

这两处只是文档事实源迁移，不改变运行时行为，也不降低业务断言。

# Roadmap 必须保留的未完成阶段

Blueprint 09—17 删除不等于后续阶段都完成。`docs/roadmap/生产上线实施路线.md` 明确保留：

```text
已完成基础
→ Stage 1—8 主要业务实现

部分完成
→ Stage 9 Analysis 已完成；Monitoring/Alert/VOC/Ticket 待产品确认/实现
→ Stage 10 Excel Export/离线 Word 已有；Word 报告中心是否产品化待业务决定

生产阻塞
→ 企业认证/后端授权
→ Stage 11A Dockerfile/Compose/Production Config
→ Stage 11B 离线 Release Bundle / 固定 image digest / SBOM / 来源验证
→ Stage 11C PostgreSQL + Artifact 协调 Backup/Restore
→ Stage 11D 部署/回滚自动化
→ Stage 11E restart/reboot/容量/安全/恢复的真实生产服务器验收

按需
→ Stage 12 旧数据迁移与对账
```

未完成阶段不会因为文档重构消失。

# 范围

- 当前实现一致性审计；
- Blueprint 01—08、README 和导航治理；
- Appendix/Guide/模块 README 当前实现说明；
- Roadmap 生产上线实施路线；
- 仅为迁移文档事实源而调整直接绑定旧文档路径的两处测试。

# 非目标

- 不修改运行时业务行为；
- 不修改 HTTP/Canonical/Job Contract；
- 不修改 Schema/Migration；
- 不修改 Prompt taxonomy 内容；
- 不修改 Provider/调度/Analysis/Export 业务语义；
- 不升级依赖；
- 不在本 Change 实现认证、Monitoring 或 Stage 11 Production Release。

# 成功标准

- [x] `docs/blueprint/` 只保留 README + 01—08 核心文档；
- [x] 原 09—17 的当前有效事实能从 Appendix/Guide/模块 README/核心 Blueprint/机器事实找到；
- [x] Stage 0—12 当前状态、未完成阶段和生产上线阻塞项完整存在于 Roadmap；
- [x] PostgreSQL 调试附录使用当前真实表/Owner/Migration，不复制第二套 Schema；
- [x] Prompt 继续是完整 AI taxonomy 唯一业务事实源；测试不再依赖 Blueprint 15 复制 taxonomy；
- [x] 旧 Blueprint 09—17 链接和测试事实源完成迁移；
- [x] 不修改运行时代码、Contract、Schema、Migration、generated、依赖；
- [x] 两处文档事实源测试不改变业务测试语义；
- [x] 文档、架构、Owner、Secret、Contract、Unit、PostgreSQL、Migration 等永久门禁在候选 HEAD `fb6b03a85a1590b7db015047131129377b00c2f5` 全部通过；
- [ ] `ready_for_review` 状态提交后的最终 HEAD 再取得全部 GitHub Actions 成功后合并。

# 验证历史与最终候选证据

曾出现的失败均已定位并修根因：

1. 删除 Blueprint 09/15 后，旧测试仍把旧文档当事实源：迁到 Scheduler Appendix / Prompt + AI Appendix；
2. 迁移后的 Analysis 文档事实源测试有一处 Ruff format 差异：只修格式，不改断言；
3. 早期简版附录信息密度不足：撤销摘要式重写，以旧长文为知识保全基线，并按当前代码补充/勘误。

候选 HEAD：

```text
fb6b03a85a1590b7db015047131129377b00c2f5
```

该 HEAD 的永久 GitHub Actions 已全部实际成功：

```text
CI                                  run #1842  success
Stage 5A Provider Raw               run #1331  success
Stage 5B Collection Execution       run #1289  success
Stage 5C Provider Persistence       run #1286  success
Stage 5D Provider Dispatch          run #1287  success
Stage 6 XHS Vertical Slice          run #1657  success
Stage 7 Keyword Packs               run #1452  success
Stage 7 Provider Config Routing     run #1565  success
Stage 7 Plan Occurrence Run Snapshot run #1450 success
Stage 7 Scheduler Runtime           run #1792  success
Stage 1-7 Audit Correctness         run #787   success
```

其中可确认的具体门禁包括：

- Analysis/Excel/P1 相关目标测试 184 passed；
- Stage 6 Unit / Quality / PostgreSQL 与多条 Migration 升降级路径成功；
- Scheduler Unit / Quality / PostgreSQL、previous revision、base round-trip 成功；
- Stage 5D Unit/Contract、PostgreSQL/Artifact、Raw replay、Ruff、Mypy、Architecture/Owner、Secret/Docs、Contract、Migration round-trip 成功；
- 主 CI 的 Windows bootstrap、Platform、Database、Contract、Backend/Frontend 等当前工作流门禁成功。

这组证据只证明 `fb6b03a...` 候选。当前文件把 Change 提升为 `ready_for_review` 会生成新 HEAD；**最终合并仍必须等待新 HEAD 的全部永久 CI 再次成功**。

# 后续交付步骤

1. 等待本次 `ready_for_review` 提交的新 HEAD 全部永久 CI；
2. 任一失败则读取具体 Job 日志修根因，不降低门禁；
3. 全绿后解除 Draft，并使用已验证 HEAD 合并 PR #137 到 `main`；
4. 按 Change 管理规则将本 Change 标记 `done` 并移动到 `changes/archive/2026-08/`；
5. 归档提交同样通过相应 CI/PR 后合并；
6. 最终重新读取 `main`，确认 Blueprint、Appendix、Roadmap、Change 状态和最终 SHA。
