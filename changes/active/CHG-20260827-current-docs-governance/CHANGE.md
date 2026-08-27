---
schema: rvc-change/v1
id: CHG-20260827-current-docs-governance
title: 按当前机器事实治理现行文档
level: L2
status: in_progress
owner: aima
branch: main
created: 2026-08-27
updated: 2026-08-27
completion_gate: required
depends_on: []
affected_areas:
  - documentation
  - architecture
  - roadmap
  - ingestion
  - analysis
  - frontend
  - operations
affected_paths:
  - README.md
  - docs/01_代码结构与修改导航.md
  - docs/blueprint/README.md
  - docs/blueprint/04_后端任务API与前端.md
  - docs/blueprint/07_技术决策与实施门禁.md
  - docs/roadmap/01_内网V1上线实施计划.md
  - docs/roadmap/02_生产上线实施路线.md
  - docs/roadmap/03_4000万历史数据迁移实施方案.md
  - docs/appendix/08_数据入口与统一入库实现.md
  - docs/appendix/11_生产部署与离线Release方案.md
  - backend/src/aima_ugc/modules/ingestion/README.md
  - backend/src/aima_ugc/modules/analysis/README.md
  - frontend/README.md
contracts: []
data_changes: []
---

# 目标

以当前 `main` 的代码、Pydantic Contract、Alembic Migration、generated client、测试、锁文件和已完成 Change 为机器事实，对现行文档做一次受影响域内的 `full` 治理，修复已经过期、互相矛盾或把历史施工状态写成当前状态的内容。

本 Change 只治理当前仍承担事实说明、开发导航、Roadmap 或实施方案职责的文档。`changes/archive/**` 是历史证据，不因当前实现变化而改写。

# 成功标准

- [ ] 现行文档不再把 Stage 12 软件开发写成“当前下一正式单元”或“当前第一优先级开发”；明确区分“软件实现已完成”“公司服务器 500 万/等效比例容量门禁待完成”“生产 4000 万执行待独立授权”。
- [ ] Worker Job Registry、Analysis Planner、Historical Campaign 等当前能力以真实代码中的版本化 Job Type 和调用链为准，不继续复制旧 4-Job 清单。
- [ ] Stage 12 实施方案从“施工中”口径收敛为“已实现的软件基线 + 尚未完成的生产门禁/操作手册”，不把已通过 Completion Audit/CI 的能力继续写成待实现。
- [ ] 统一“导入数据”入口、本地/服务器两类来源、`standard_observation / historical_fill_only` 两种独立策略、Artifact/Campaign/Chunk/逐行账本、手动 Analysis Run 的当前说明与代码一致。
- [ ] Production Roadmap 继续保留尚未实现的认证授权、Coordinated Backup/Restore、SBOM/签名/provenance、Deploy/Rollback、完整 Production Acceptance 等批准目标，并明确它们是未来能力，不因代码尚未实现而删除。
- [ ] 当前路由、模块边界、部署拓扑、持久化边界、兼容入口与实际实现一致；未发现证据的能力不写成已实现。
- [ ] 不修改业务代码、Contract、Schema/Migration、generated client、依赖、Prompt、Workflow 或历史归档 Change。
- [ ] 完成受影响文档域的反向审计、两阶段 Review 和仓库适用文档/治理门禁，所有“通过”结论具有本轮新鲜证据。

# 范围

1. 根 README、代码导航、Blueprint 导航/后端任务与技术决策。
2. Internal V1 / Production / Stage 12 Roadmap 与 Stage 12 正式实施方案。
3. 数据入口、Analysis、Production Release 相关 Appendix/模块 README/Frontend README。
4. 仅在实际审计证明有漂移时修改文件；审计后确认无漂移的候选路径从 `affected_paths` 移除。

# 非目标

- 不新增、删除或改变任何业务能力。
- 不修改 HTTP Contract、OpenAPI/generated client、数据库 Schema/Migration、Job Payload、Prompt、依赖或 Runtime 配置。
- 不把完整 Production Backlog 提前实现。
- 不执行公司服务器 500 万/等效比例容量演练，也不执行生产 4000 万迁移。
- 不机械扫描/重写所有 Markdown，不做无关润色、编号重排或格式化。
- 不改写 `changes/archive/**` 的历史过程、当时状态或验收证据。

# 必须保持不变

- 模块化单体；API / Worker / Scheduler / Migration 分进程。
- PostgreSQL 18 是唯一业务事实库；长任务继续使用 PostgreSQL Durable Job Runtime。
- Provider/File → Raw/Input Artifact → Mapper → Canonical → Relevance → Ingestion → Owner Repository → PostgreSQL 的主链。
- Content Current + Version + Metric、表 Owner、Artifact、Pydantic/OpenAPI/generated client 等长期边界。
- Stage 12 历史补空策略只补空、不覆盖非空、冲突留痕；导入与 AI 解耦。
- 公司内网 V1 已完成与完整 Production Go-Live 仍为 No-Go 是两个不同里程碑。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 以代码等机器事实为准治理当前文档，包括实施方案 | user:current-request | not_satisfied | 待完成目标文档审计与修正 |
| R2 | 已实现能力由机器事实证明，不用旧聊天/旧 Stage 代替 | AGENTS.md | not_satisfied | 已读取 AGENTS/Coding/Docs Skill；待完成逐项反查 |
| R3 | Stage 12 当前状态与真实归档 Change、Job Registry 和测试证据一致 | backend/src/aima_ugc/bootstrap/worker.py | not_satisfied | 已确认 Historical Jobs 与 Analysis Planner 已注册；待同步文档 |
| R4 | 保留已批准但未实现的 Production 目标，并明确未来状态 | docs/roadmap/02_生产上线实施路线.md | not_satisfied | 待与实际 deploy/runtime 机器事实交叉核对 |
| R5 | 历史 Change 不作为当前文档重写对象 | .agents/skills/docs/references/01_事实源与同步判断.md | satisfied | 本 Change 明确排除 `changes/archive/**` |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | not_applicable | 不改变业务代码 |
| 接口 / Contract | not_applicable | 不修改 Pydantic/OpenAPI/generated client |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改数据库或 Runtime 行为 |
| 用户 / Workflow Acceptance | not_applicable | 不改变产品交互行为 |
| 跨组件 Golden Path | not_applicable | 只同步已经存在的接线事实 |
| External Dependency / Provider Probe | not_applicable | 不修改 Provider 行为 |
| Build / Package / Runtime | not_applicable | 不修改构建与部署配置 |
| Docs / Governance / Other | required | 受影响域审计、引用/链接/治理检查、Completion Gate 与适用 CI |

# 分步任务

- [ ] 对照真实 Worker Registry、API/Contract、Migration、前端 Router/Feature、模块目录、Compose/Release 机器事实建立漂移清单。
- [ ] 修正根 README、代码导航、Blueprint 中的当前实现清单和导航。
- [ ] 修正 Roadmap 02/03 中 Stage 12 的当前状态、执行顺序和剩余生产门禁。
- [ ] 修正受影响 Appendix、模块 README、Frontend README；未发现漂移的候选文件不做无关修改。
- [ ] 执行 Docs targeted re-review：从修改后的文档反查机器事实，检查当前/未来/历史三类状态是否混淆。
- [ ] 执行需求符合性与文档质量两阶段 Review。
- [ ] 更新 Requirement Traceability、Validation Matrix、Completion Audit 和验证证据。
- [ ] 通过仓库适用门禁后归档本 Change。

# Completion Audit

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared
