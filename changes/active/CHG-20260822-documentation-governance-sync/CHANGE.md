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
  - changes/active
  - changes/archive/2026-08
contracts: []
data_changes: []
---

# 目标

基于当前代码、Migration、Contract、生成物、锁文件、测试与现有正式文档，完成一次当前状态一致性审计，并把文档整理成一套**真正可以帮助开发者读代码、修改代码、调试系统，并继续完成剩余 Stage 直到生产服务器上线**的技术文档体系。

这次治理不是“把文档写短”。核心要求是：

```text
当前实现
→ 必须服从当前机器事实

已经批准但尚未实现的长期设计
→ 必须保留并明确标记待实现

已经被后续正式决策替代的历史设计
→ 可以保留演进原因，但必须标记已被替代，禁止照旧实现
```

# 成功标准

- [ ] 以当前代码、Migration、Contract、生成物、测试和配置为主要事实源，核对总体架构、数据库、采集、Scheduler、导入、Analysis、Export、Word Report、前端和运行部署边界。
- [ ] 文档能让第一次进入仓库的开发者知道“为什么这样设计、一次数据/请求怎样流、当前代码在哪里、改这个行为该动什么、怎么测试和排障”。
- [ ] 原文有价值的 Endpoint、真实 JSON 路径、Fixture、状态机、事务/恢复边界、SQL、调试方式、阶段设计和生产部署方案不得因为重构被压缩丢失。
- [ ] `docs/blueprint/01—08` 继续作为核心架构入口；原 `09—17` 本轮继续保留为详细设计/阶段技术材料，不做机械删除。
- [ ] `docs/appendix/` 提供 PostgreSQL、Scheduler、TikHub、统一入库、Excel、AI、Word Report、Production Release 等可操作专题入口，并在原详细设计基础上做当前事实勘误、代码地图和调试增强，而不是短摘要替代原文。
- [ ] 新增 `docs/roadmap/`，完整承接 Stage 0—12 的持续实施路线，明确“已完成 / 部分完成 / 待实现 / 已被后续决策替代”，保证后续会话仍能按既有技术方案继续开发到生产上线。
- [ ] Stage 11 Production Release、认证/授权、协调 PostgreSQL + Artifact Backup/Restore、回滚和真实生产验收等未完成设计必须继续存在于长期文档，不能因为当前代码没有实现就删除。
- [ ] `AGENTS.md`、根 README、Blueprint README、Roadmap、Appendix README、模块 README、API/测试/部署/前端/采集说明的导航与交叉链接全部同步。
- [ ] PostgreSQL 调试附录使用当前真实表/Owner/Migration，提供安全只读查询和排障方法，但不复制第二套完整 Schema。
- [ ] AI 完整 taxonomy 继续只由当前 Prompt Markdown 维护；文档解释语义和代码路径，不建立第二套可漂移标签表。
- [ ] 不修改运行时业务行为、公共 Contract、Schema、Migration、生成 Client 或依赖；业务测试不因文档治理改变。
- [ ] PR 最终 diff 仅包含 Markdown/Change 等文档类文件。
- [ ] 通过当前仓库的文档、架构、安全和相关 CI 门禁；最终完成结论只依据 PR 最新 HEAD 的新鲜 CI。

# 内容保全门禁

任何旧文档的删除、缩减或迁移都必须先回答：

```text
旧主题是什么？
→ 当前是否仍有效？
→ 当前代码事实在哪里？
→ 新承载位置在哪里？
→ 是否保留了理解实现必须知道的细节？
→ 是否影响后续 Stage / Production Release？
```

没有明确承载位置的有效内容不得删除。

本轮对 `docs/blueprint/09—17` 采用保守策略：**继续保留**。Appendix/Guide 先增强可用性和当前代码导航，未来如果要真正删除旧文件，应另起文档治理 Change 做逐主题保全映射和链接迁移。

# 文档写作原则

1. 先解释“为什么存在、解决什么问题、输入/输出是什么、数据怎么流”，再出现类名和框架名。
2. 面向基础一般的开发者和需要理解整体系统方案的人；必要术语第一次出现用白话解释。
3. 文档不是代码索引列表。关键调用链、状态变化、错误/恢复边界、业务身份等理解实现必须知道的内容要直接讲清。
4. 固定且容易漂移的精确 Schema/完整 Contract 可以导航到 `tables.py`、Pydantic、Migration、OpenAPI；不要手工复制第二套机器事实。
5. Provider 真实 JSON 路径、Endpoint、Fixture、分页、接口 A/B 结论、调试 SQL、部署/回滚顺序等人工理解需要的细节可以直接在 Appendix 展开。
6. 每个专题尽量提供“代码地图”和“修改指南”：生产入口、关键类/函数、表、Contract、Migration、Fixture、测试。
7. 给真实最小例子，例如一条 Provider 数据怎样进入 Content、一条 Job 怎样完成、一次 SQL 怎样反查来源、一处页面改动怎样追到 Contract。
8. 所有“当前已实现 / 当前未实现 / 已批准待实现 / 已被替代 / 默认行为 / 限制”必须有当前机器事实或正式决策依据。
9. 不写空泛的“企业级、高可用、先进”等词替代机制。
10. 文档结构为开发服务，不为目录整齐或篇幅短牺牲知识密度。

# 当前文档分层

```text
AGENTS.md
→ 开发/Agent 统一规则和导航

docs/代码结构与修改导航.md
→ 常见修改任务到真实代码/Contract/表/测试

docs/blueprint/01—08
→ 核心长期架构和跨模块决定

docs/blueprint/09—17
→ 当前继续保留的详细设计/真实验证/Stage 8 技术方案

docs/roadmap/
→ Stage 0—12 当前状态、未完成开发、生产 Go-Live 路线

模块 README
→ 当前模块实现和修改入口

docs/appendix/
→ 专题实现/字段/状态/SQL/调试/Production Release

docs/guides/
→ Figma 等开发流程

docs/collection/
→ 五平台当前实现和 Provider 证据导航

代码 / Contract / Migration / generated / tests / locks
→ 精确机器事实

changes/archive/
→ 历史为什么改、当时怎么验证
```

# 当前生产事实勘误

当前仓库已经有：

```text
API / Worker / Scheduler / Migration 入口
五平台 Collection / Scheduler
Excel Import
Content Current / Version / Metric / Coverage
Analysis
正式 Excel Export
离线 Word Report
采集运行中心 / 采集策略 / 声音广场
```

当前仓库根没有：

```text
Dockerfile
compose.yaml
compose.production.yaml
env.production.example
```

当前生产 Go-Live 仍受以下工作阻塞：

```text
企业认证/后端授权
Stage 11 Docker/Compose/生产配置
离线 Release Bundle / image digest / SBOM / source verification
PostgreSQL + Artifact 协调 Backup/Restore
正式恢复和回滚演练
生产服务器 smoke / restart / reboot / capacity / security 验收
```

这些剩余工作已经固化到 `docs/roadmap/生产上线实施路线.md` 和 `docs/appendix/生产部署与离线Release方案.md`。

# 范围

- 正式长期文档、模块 README、导航、交叉链接、当前状态摘要、Appendix/Guide/Roadmap。
- 对当前代码/Migration/Contract/测试/配置的只读事实核对。
- 已完成 Change 的状态与归档位置一致性。

# 非目标

- 不新增业务能力。
- 不修改数据库结构、API、Prompt taxonomy、数据口径、Provider 行为、调度行为或前端交互。
- 不重写历史 Migration 或 archived Change 的事实过程。
- 不升级依赖，不做运行时代码重构。
- 本轮不删除 Blueprint 09—17。
- 本轮不实现 Stage 11；只保证其已批准技术路线不丢失并与当前事实明确区分。

# 必须保持不变

- 代码、Migration、Contract、生成 OpenAPI/Client、锁文件和测试继续作为机器事实源。
- Prompt Markdown 继续作为 AI taxonomy/输出语义的唯一业务事实源。
- PostgreSQL 继续是唯一业务事实库；Provider → Raw → Mapper → Canonical → Ingestion → Owner Repository → PostgreSQL 主链不变。
- 当前公共 API、数据库、Job、Excel/报告入口和合法行为不变。
- 旧 Provider Budget Account / Reservation Ledger 设计已被后续正式决策替代；当前不能作为“未完成 Stage 7”自动恢复实现。

# 验证计划

1. 核对根规则、Blueprint、Roadmap、模块 README、Migration/Schema、Contract、测试和当前 Git/PR 状态。
2. 全仓检查当前正式文档中的过期 Stage 状态、错误文件路径、已实现却写未实现、未实现却写已存在、重复 taxonomy/Schema 等问题。
3. 逐项检查原 09—17 的有效知识是否在保留原文/增强 Appendix/Guide/Roadmap 中可继续找到。
4. 确认 PR 没有运行时代码、测试、Contract、Migration、依赖或 generated 文件差异。
5. 执行/通过当前仓库 `check_docs.py`、`check_architecture.py`、`check_table_ownership.py`、`scan_secrets.py` 等相关门禁。
6. 读取 PR 最新 HEAD 的 GitHub Actions；失败则修根因后重新验证。
7. 最新 HEAD 全绿后，按用户授权完成 PR 合并到 `main`，再按仓库规则归档本 Change，并确认最终 `main` 状态。
