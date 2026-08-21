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
affected_paths:
  - AGENTS.md
  - README.md
  - docs
  - backend/src/aima_ugc/modules/*/README.md
  - backend/src/aima_ugc/platform/*/README.md
  - changes/active
  - changes/archive/2026-08
contracts: []
data_changes: []
---

# 目标

基于当前 `main` 的代码、Migration、Contract、生成物、锁文件、测试与现有正式文档，完成一次当前状态一致性审计，并把文档体系收敛为长期架构 Blueprint、模块当前实现 README、专题附录/操作指南和机器事实四层，避免 Blueprint 持续膨胀为实现手册或阶段流水账。

# 成功标准

- [ ] 以当前机器事实为准逐项核对核心架构、数据库、采集、Scheduler、导入、分析、导出、报告和前端边界；发现实现与已批准设计冲突时先判定正确事实源，不机械让文档追随代码。
- [ ] `docs/blueprint/` 只保留长期稳定的架构、领域边界、技术决策和实施门禁；阶段历史、具体 Provider 响应、接口验证台账、调试 SQL、具体业务实现细节迁入附录/指南/模块 README。
- [ ] 新增统一 `docs/appendix/README.md` 与 PostgreSQL 调试/常用 SQL 附录，SQL 以当前真实表、Migration 和 Owner 为依据，不复制第二套 Schema。
- [ ] Scheduler、TikHub、Excel、AI 打标、报告等专题文档按内容归档为附录或指南，核心长期原则回写对应 Blueprint；不机械按编号搬家，不丢失有效知识。
- [ ] `AGENTS.md`、Blueprint README、根 README、相关模块 README、测试/部署/API/采集说明的导航与交叉链接全部同步。
- [ ] 当前已合并但仍残留在 `changes/active` 的 Change 按真实 PR 状态归档，不篡改历史实现证据。
- [ ] 不修改运行时业务行为、Contract、Schema、Migration、生成 Client 或依赖；若审计发现真实代码缺陷，仅记录并报告，除非修正文档本身无法解决一致性问题。
- [ ] 通过仓库文档检查、架构检查和旧路径全仓检索；如能触发 CI，则以新分支最新 CI 作为最终交付证据。

# 文档写作原则

本轮以及后续正式文档统一从第一性原理和实际使用出发：

1. 先回答“为什么需要这个东西、它解决什么问题、输入是什么、输出是什么、数据怎么走”，再介绍类名、表名或框架名。
2. 假设读者基础一般。必要术语第一次出现时必须用一句白话解释；如果不用术语也能说清楚，就不要为了显得专业而引入术语。
3. 是否贴代码、目录、表名、命令或时序，要看它能否帮助理解和调试；不是每份文档都必须结合源码，也不能把实现细节全部复制到 Blueprint。
4. 示例优先使用最小、真实、可验证的例子，例如一条内容如何从 Provider 进入 PostgreSQL、一条 Job 如何从 queued 变成 succeeded、一次 SQL 如何安全查询最近内容。
5. 不重复维护机器 Schema、完整 Prompt taxonomy、OpenAPI 字段清单或 Migration SQL；需要精确字段时指向唯一事实源。
6. 长文档必须提供清晰导航、流程图/伪流程或分层说明，让读者能够先建立整体理解，再按需下钻。
7. 所有“当前已经实现”“尚未实现”“默认行为”“限制条件”必须能够从当前代码、Migration、Contract、测试或配置中找到依据。
8. 不写空泛的“高可用、企业级、先进架构”等表述；除非紧接着说明具体机制、解决的问题和当前真实实现。

# 范围

- 正式长期文档、模块 README、导航、交叉链接、当前状态摘要、附录/指南目录结构。
- 对当前代码/Migration/Contract/测试的只读事实核对。
- 已完成 Change 的状态与归档位置一致性。

# 非目标

- 不新增业务能力。
- 不修改数据库结构、API、Prompt taxonomy、数据口径、Provider 行为、调度行为或前端交互。
- 不重写历史 Migration 或 archived Change。
- 不升级依赖，不做无关代码重构。

# 必须保持不变

- 代码、Migration、Contract、生成 OpenAPI/Client、锁文件和测试继续作为机器事实源。
- Prompt Markdown 继续作为 AI taxonomy/输出语义的唯一业务事实源；Blueprint/附录只解释边界与引用。
- PostgreSQL 继续是唯一业务事实库；Provider → Raw → Mapper → Canonical → Ingestion → Owner Repository → PostgreSQL 主链不变。
- 当前公共 API、数据库、启动、部署、Job、Excel/报告入口和合法行为不变。

# 验证计划

1. 审计根规则、Blueprint、模块 README、Migration/Schema、Contract、测试和当前 Git/PR 状态。
2. 建立“机器事实 → 当前文档 → 冲突 → 处理”的证据清单并实施文档重构。
3. 全仓搜索旧 Blueprint 路径、Stage 8 过期表述、已实现却写成未实现的说明、重复 taxonomy/Schema 描述。
4. 执行 `scripts/quality/check_docs.py`、`scripts/quality/check_architecture.py`；必要时执行相关静态/测试门禁。
5. 创建 PR，读取最终 head 的新鲜 CI；通过后按用户本轮授权完成合并和 Change 归档。
