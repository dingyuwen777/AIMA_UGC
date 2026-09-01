---
schema: coding-change/v1
id: CHG-20260901-agent-skills-project-governance
title: 收敛 AIMA_UGC 项目治理与 CI 接线
level: L3
status: in_progress
owner: dingyuwen777
branch: chore/agent-skills-project-governance
created: 2026-09-01
updated: 2026-09-01
completion_gate: required
depends_on: []
affected_areas:
  - project-governance
  - ci
  - docs
  - tests
affected_paths:
  - AGENTS.md
  - README.md
  - docs/
  - backend/src/aima_ugc/**/README.md
  - scripts/quality/check_docs.py
  - scripts/quality/check_agent_governance.py
  - tests/unit/test_docs_navigation.py
  - tests/unit/test_agent_governance.py
  - tests/unit/test_coding_global_language_rules.py
  - tests/unit/test_coding_portability.py
  - tests/unit/test_coding_skill_time_and_naming.py
  - .github/workflows/ci.yml
  - .github/workflows/change-completion-gate.yml
contracts: []
data_changes: []
---

# 目标

把 AIMA_UGC 的项目级治理从旧的 Agent_Skills 源码副本假设收敛为稳定的项目 Overlay 与接线契约：AIMA 只维护自己的架构、Contract、Schema、CI、部署、文档和长期工程规则；Agent_Skills 的通用 Skill/Reference/内部回归由 `dingyuwen777/Agent_Skills` canonical 仓库负责。修复当前 `main` 已确认的 Completion Gate 失败和正式文档漂移，同时不手工迁移当前 legacy Runtime 受管资产。

本 Change 同时承担 2026-09-01 新增的文档治理要求：全面审计当前项目文档域，把承担实现定位、事实验证、进一步阅读、修改入口或排障导航职责的真实仓库文件引用统一改成可点击的仓库相对 Markdown 链接；命令、目录树、glob、占位路径、协议/流程示例和运行时代码字面量不机械链接化。

# 成功标准

- [ ] 项目当前正式文档不再要求目标仓库本地存在 Agent_Skills canonical `references/`。
- [ ] AIMA 的治理/Completion Gate 不再执行目标项目中不存在的 `.agents/skills/*/tests`。
- [ ] AIMA 自己的治理回归只验证项目 Overlay、项目文档和项目 CI 接线，不复制 Agent_Skills canonical Reference 文件数量、正文或内部路由测试。
- [ ] `docs/blueprint/01_总体架构与技术选型.md` 的 Worker Registry 与当前生产装配一致，明确八种持久 Job。
- [ ] 当前项目文档域中，能够唯一解析到真实仓库文件且承担导航职责的引用均为可点击相对 Markdown 链接；代码块中的纯文件导航改为代码块外链接表达。
- [ ] `check_docs.py` 持续检查当前项目文档域的本地链接有效性和未链接真实文件导航，避免后续回归。
- [ ] `ready_check.py` 仍是 AIMA Change 的 Requirement Traceability / Completion Audit 机器门禁；Secret、docs、full product CI 等现有独立证明责任不降低。
- [ ] `AGENTS.md` 的项目自有 Overlay 对本次已修复偏差形成当前事实，且 installer-owned managed block、legacy v3 install manifest、Runtime binary 不被手工修改。
- [ ] PR 最新 HEAD 的相关永久 CI 全绿；合并后 `main` 取得新鲜 CI；Change 最终归档。

# 范围

- 定向校准根 `AGENTS.md` 的项目自有治理区，不手工修改 managed marker 内文本。
- 修正 Blueprint 中已确认的 Job 列表和本地 Reference 导航。
- 全量审计当前项目文档域：根 README/AGENTS、`docs/**/*.md`、模块 README；把真实仓库文件导航改为可点击相对链接。
- 历史 `changes/archive/`、installer-owned `.agents`、运行时 Prompt/Fixture 等机器消费 Markdown 不作为本次“当前项目文档域”批量改写对象。
- 新增 AIMA 项目级治理静态检查与回归测试。
- 删除三份把 Agent_Skills canonical 源码结构当作 AIMA 单元测试事实的旧 `test_coding_*`。
- 修复 `ci.yml` 与 `change-completion-gate.yml` 的治理证明责任。

# 非目标

- 不修改业务 API、Pydantic Contract、OpenAPI、Schema、Migration、数据库数据语义或 generated client。
- 不升级 Python、Node、npm、uv、框架、依赖或 PostgreSQL。
- 不修改 `.agents` installer-owned Skill Core、Runtime binary、legacy `agent-skills-install/v3` manifest、MCP 配置或 managed block；这些等待后续正式 Agent_Skills Runtime Release/upgrade。
- 不调整产品功能、Figma、Provider、Prompt、部署拓扑或 Production Go-Live 范围。
- 不把命令、目录树、glob、占位路径、协议/流程示例或代码字面量为了形式统一机械转换成链接。
- 不改写 `changes/archive/` 历史状态与当时证据。
- 不在本任务启用 GitHub Branch Protection；当前 required checks 先恢复为可靠绿色，再单独治理平台保护策略。

# 必须保持不变

- AIMA 当前模块化单体、API/Worker/Scheduler/Migration 分进程、PostgreSQL 18、Python 3.14、Vue 3 + TypeScript + Vite、根 uv 工程等已批准长期基线。
- 当前八种持久 Job 的代码行为和 Job type 字符串不变化，本任务只修正文档与治理接线。
- Pydantic/OpenAPI/generated client、Alembic Migration、表 Owner、Secret、Artifact、Job Runtime 和生产部署规则不变化。
- 内网 V1 已完成、完整 Production Go-Live 仍 No-Go 的 Roadmap 语义不变化。
- 现有 full CI 的 Unit/Contract/API、PostgreSQL Integration、Browser、Runtime、Release 等独立产品证据不得因治理收敛被较弱检查替代。
- `ready_check.py` 继续验证 AIMA 自己的 `coding-change/v1` carrier；不把 Agent_Skills 源仓库自测复制到业务仓库。
- 文档链接迁移只改变导航形式，不删除、压缩或静默改写原有有效技术事实。

# 关键决策

## 方案比较

1. **把 Agent_Skills `references/` 与内部 tests 再复制回 AIMA**：能让旧 CI 暂时绿色，但重新制造双 canonical，升级后必然漂移；拒绝。
2. **直接删除 Completion Gate / 治理检查**：能绕过当前失败，但降低持续证明责任；拒绝。
3. **AIMA 只保留项目 Overlay + 项目治理接线检查，Agent_Skills 自测回归 canonical Owner；保留 `ready_check.py` 与现有产品 CI**：职责清晰、无双副本、可持续升级；采用。
4. **文档路径全部机械正则替换为链接**：会误伤命令、目录树、glob、占位符和协议示例；拒绝。
5. **以真实文件可解析性 + 导航语义为门禁，仓库相对链接作为统一表达**：既可点击又可随仓库移动验证；采用。

## Evidence Preservation Mapping

| 原证明责任 | 原位置 | 新位置 / Owner | 证据等级 | 依据 |
| --- | --- | --- | --- | --- |
| Agent_Skills canonical Skill/Reference 的完整性、路由、内容守恒 | AIMA `.agents/skills/coding/tests` 假设与 `tests/unit/test_coding_*` | `dingyuwen777/Agent_Skills` 自身 Skill Tests | 保持且归位 | 这些规则不是 AIMA 项目事实，目标项目 Runtime 也不分发 canonical References/tests |
| AIMA 根治理入口、项目 Overlay、禁止把本地 canonical Reference 当项目事实源 | 零散 `test_coding_*` | `scripts/quality/check_agent_governance.py` + `tests/unit/test_agent_governance.py` | 保持并更直接 | 新检查只验证 AIMA 自己可维护的接线与文档 |
| AIMA 当前文档本地链接和仓库文件导航 | 原 `check_docs.py` 只检查固定入口链接，无真实文件导航门禁 | `scripts/quality/check_docs.py` + `tests/unit/test_docs_navigation.py` | 增强 | 当前项目文档域统一验证链接存在和真实文件导航可点击 |
| AIMA 文档/Secret 静态门禁 | `ci.yml` docs-governance | 原 `check_docs.py` / `scan_secrets.py`，并增强 `check_docs.py` | 保持 | 原项目级证明责任不删除 |
| Requirement Traceability / Completion Audit 结构与状态 | `change-completion-gate.yml` | 原 `ready_check.py` | 保持 | 继续运行同一项目受管 CLI，不用供应方内部 test suite 冒充 Ready 证明 |
| 产品 Unit/Contract/API/DB/Browser/Build/Runtime | `ci.yml` full profile 与其他 workflows | 原位置保持 | 保持 | 本任务不删除或收缩产品证明层 |

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 第一次使用 Agent_Skills 开发 AIMA_UGC 时完成有证据的项目治理，并按确认方案落库 | user:2026-09-01-aima-agent-skills-governance | not_satisfied | 待实现与 PR/main 新鲜 CI |
| R2 | 项目规则和项目真实事实始终先读；Source/Runtime 模式只改变通用治理取得方式，不能跳过 AIMA Overlay | AGENTS.md | satisfied | 当前根规则和本次 Source Mode 调查均保持项目事实优先；本任务不弱化该边界 |
| R3 | Project Governance Bootstrap 只维护 managed block 外项目 Overlay，不把 Agent_Skills 内部实现写成项目规则 | user:2026-09-01-aima-agent-skills-governance | not_satisfied | 待校准项目文档/治理检查；managed block 保持 installer ownership |
| R4 | Worker Registry 文档必须与当前生产装配的八种持久 Job 一致 | backend/src/aima_ugc/bootstrap/worker.py | not_satisfied | 待更新 `docs/blueprint/01_总体架构与技术选型.md` 并通过 docs gate |
| R5 | 修复当前 main 的 Completion Gate 根因，不能通过删除/降低门禁绕过 | .github/workflows/change-completion-gate.yml | not_satisfied | 当前 main run 33374658066 因不存在 `.agents/skills/coding/tests` 失败；待 PR CI 证明修复 |
| R6 | 不手工迁移 legacy v3 Runtime/manifest/managed block；正式升级留给后续 Agent_Skills Release | .agents/agent-skills-install.json | satisfied | 本 Change 明确非目标，affected paths 不包含 installer-owned `.agents` 资产 |
| R7 | AIMA 当前技术栈、Contract/Schema/Migration、产品行为和 Production Roadmap 不因治理任务变化 | docs/blueprint/07_技术决策与实施门禁.md | satisfied | 本 Change `contracts: []`、`data_changes: []`，不涉及产品实现/依赖/迁移 |
| R8 | 全面检查仓库当前文档，把其中引用的其他真实仓库文件改成可点击链接 | user:2026-09-01-doc-repository-file-links | not_satisfied | 已新增 DOC007/DOC008 审计与回归测试，待按 Runner 全量结果完成文档迁移并取得零错误证据 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | AIMA governance checker、docs navigation checker 与对应 unit test，证明 marker、Ready 入口、项目文档、workflow 接线、真实文件导航链接约束 |
| 接口 / Contract | not_applicable | 不修改 HTTP/CLI/public schema/serialization/generated contract |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改数据库、文件持久化、Job Runtime 或应用 Runtime 语义 |
| 用户 / Workflow Acceptance | required | GitHub PR/main 上真实永久 CI workflow 运行，证明开发者合并门禁与文档检查可执行 |
| 跨组件 Golden Path | not_applicable | 不改变 Browser/API/DB/Worker 等产品组件接线 |
| External Dependency / Provider Probe | not_applicable | 不修改 Provider/LLM/远端协议，无需真实调用 |
| Build / Package / Runtime | not_applicable | 不修改产品 build/package/container/runtime；相关既有 workflows 不被削弱 |
| Docs / Governance / Other | required | 全当前项目文档域扫描、相对链接存在性、DOC007/DOC008 零错误、Secret gate、project governance gate、`ready_check.py`、Workflow Responsibility Audit、PR/main CI |

# 实施步骤

1. 建立项目级治理 gate，先编码 AIMA 自己必须保持的治理不变量。
2. 删除三份错误 Ownership 的 Agent_Skills 源码结构单测，把仍属于 AIMA 的断言迁移到项目 gate/test。
3. 修正 Blueprint Job 列表、开发流程文档与根项目 Overlay 的已知偏差状态。
4. 扩展 `check_docs.py` 到当前项目文档域：验证所有相对链接，并识别未链接的真实仓库文件导航；用单元测试固定“真实文件导航要可点击、命令/示例不机械链接化”的边界。
5. 以 GitHub Runner 的 DOC007/DOC008 全量结果为审计清单，逐文档把真实文件导航迁移为相对链接；重新运行直到零错误，并补人工反查未被保守规则捕获的导航代码块/短路径。
6. 修改永久 CI：governance-only 与 Completion Gate 改为运行 AIMA 项目治理 gate + 既有 docs/secret/ready checks；full 产品测试职责保持。
7. 运行/读取 PR fresh CI；完成 Completion Audit 与独立 Review，只有 final HEAD 全绿才合并。
8. 合并后读取 `main` fresh CI；将 Change 标记 `done` 并独立归档，归档 PR 也走新鲜 CI。

# Completion Audit

- [ ] upstream_re_read：Ready 前重新读取本轮用户要求、根/文档 AGENTS、Blueprint 07、Worker 注册、当前 CI 和 Agent_Skills canonical 相关规则。
- [ ] change_coverage：逐项比较上游治理目标与本 Change，确认没有漏掉项目 Overlay、文档漂移、永久 CI、旧治理测试、Runtime ownership 边界和全仓当前文档链接要求。
- [ ] reverse_audit：从 AIMA 项目规则/正式文档/CI 反查各自唯一 Owner；从 CI step 反查实际命令和证据责任；从当前项目文档域反查真实文件导航是否可点击，确认没有供应方自测残留、独立产品证据丢失或导航遗漏。
- [ ] unresolved_cleared：所有 `not_satisfied` 清零；required 验证均有 final HEAD 新鲜证据；未验证项如实列出。

# 验证证据

- Red 基线：AIMA `main@e9d43c7d04a8c1fd595381fbc4add308adad8e62` 的 Change Completion Gate run `33374658066` 在 `Run Coding completion-gate tests` 失败，错误为 `ImportError: Start directory is not importable: '.agents/skills/coding/tests'`，退出码 1；后续 Ready Check 被跳过。
- PR #274 第一轮 `head@0c8371ef0fc24476eb8965326b2dbffd2eb7d3b9`：Change Completion Gate 的 AIMA project governance wiring 与 changed PR Ready Check 均实际执行成功；`check_docs.py`、Secret gate、project governance gate 也成功。Repository Quality 唯一已确认失败为新增 `check_agent_governance.py` Ruff format，已在后续 commit 修正。
- 文档文件链接 Red 基线：待 DOC007/DOC008 Runner 全量结果补充。

# 文档影响

- 根 `AGENTS.md`：只更新项目自有 Overlay/校准结果，不动 installer-managed block。
- 根 README、`docs/**/*.md`、模块 README：只对真实仓库文件导航做链接化和必要的导航结构调整，不删除有效技术内容。
- Blueprint 01：修正实际 Worker Registry。
- Blueprint 06：把开发入口写成项目规则 + 当前治理能力，而不是要求目标项目存在 canonical Reference 文件。
- 历史 `changes/archive/` 不改写。

# Git / PR / Release

- 用户已明确授权本任务修改、提交、PR、合并到 `main`；2026-09-01 又明确要求把全仓当前文档中的其他仓库文件引用改为链接。
- 当前分支：`chore/agent-skills-project-governance`，基于 `main@e9d43c7d04a8c1fd595381fbc4add308adad8e62`。
- PR：#274，当前 Draft，实施和验证继续在该 PR 完成。
- Release：not_applicable，本任务不创建 AIMA 或 Agent_Skills Release/tag。
