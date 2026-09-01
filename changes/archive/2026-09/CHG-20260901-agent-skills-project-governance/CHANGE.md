---
schema: coding-change/v1
id: CHG-20260901-agent-skills-project-governance
title: 收敛 AIMA_UGC 项目治理与 CI 接线
level: L3
status: done
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
  - frontend/README.md
  - backend/src/aima_ugc/**/README.md
  - tests/fixtures/**/README.md
  - scripts/quality/check_docs.py
  - scripts/quality/check_docs_facts.py
  - scripts/quality/check_agent_governance.py
  - tests/unit/test_docs_navigation.py
  - tests/unit/test_docs_facts.py
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

本 Change 同时承担 2026-09-01 新增的全仓文档治理要求：

1. 全面审计当前项目文档域，把承担实现定位、事实验证、进一步阅读、修改入口或排障导航职责的真实仓库文件引用统一改成可点击的仓库相对 Markdown 链接；命令、目录树、glob、占位路径、协议/流程示例、时区标识和运行时代码字面量不机械链接化。
2. 不只检查“链接能否打开”，还要把当前文档中的实现性描述与当前仓库机器事实逐域核对；当前实现、已批准未来设计和历史原因必须明确区分。凡是能够由代码、Contract/OpenAPI/Schema、Migration、Manifest/lock、配置、路由、Workflow、测试和部署文件直接确认的当前事实，以这些当前事实为准修正文档；不得为迎合旧文档去改产品行为，也不得把未来计划写成已实现。

# 成功标准

- [x] 项目当前正式文档不再要求目标仓库本地存在 Agent_Skills canonical `references/`。
- [x] AIMA 的治理/Completion Gate 不再执行目标项目中不存在的 `.agents/skills/*/tests`。
- [x] AIMA 自己的治理回归只验证项目 Overlay、项目文档和项目 CI 接线，不复制 Agent_Skills canonical Reference 文件数量、正文或内部路由测试。
- [x] `docs/blueprint/01_总体架构与技术选型.md` 的 Worker Registry 与当前生产装配一致，明确八种持久 Job。
- [x] 当前项目文档域中，能够唯一解析到真实仓库文件且承担导航职责的引用均为可点击相对 Markdown 链接；代码块中的纯文件导航改为代码块外链接表达。
- [x] 文档链接审计不会把 `Asia/Shanghai` 等时区标识、命令参数、代码字面量或其他偶然可解析到仓库文件的非导航文本误判为文件导航。
- [x] 当前项目文档域的“当前实现”描述已按领域与当前仓库事实交叉核对，至少覆盖：运行时/依赖基线、架构与进程/Job、API/Contract、数据库/Schema/Migration、采集/Provider、AI/报告、前端路由与页面、测试/CI、部署/Release；发现的硬错误和语义漂移均已修正或明确标注为未来/历史。
- [x] 当前正式文档不复制第二套容易漂移的机器定义；精确版本、字段、路由、表、Job type、Workflow 命令等机器事实优先链接/引用对应 Owner，并在需要解释时只保留人类语义。
- [x] `check_docs.py` 持续检查当前项目文档域的本地链接有效性和未链接真实文件导航，避免后续回归；高置信、可机器验证的文档事实一致性约束在确有长期价值时纳入项目级回归，不用脆弱正则冒充完整语义审查。
- [x] `ready_check.py` 仍是 AIMA Change 的 Requirement Traceability / Completion Audit 机器门禁；Secret、docs、full product CI 等现有独立证明责任不降低。
- [x] `AGENTS.md` 的项目自有 Overlay 对本次已修复偏差形成当前事实，且 installer-owned managed block、legacy v3 install manifest、Runtime binary 不被手工修改。
- [x] PR 最新 HEAD 的相关永久 CI 全绿；合并后 `main` 取得新鲜 CI；Change 最终归档。


# 范围

- 定向校准根 `AGENTS.md` 的项目自有治理区，不手工修改 managed marker 内文本。
- 修正 Blueprint 中已确认的 Job 列表和失效治理导航。
- 全量审计当前项目文档域：根 README/AGENTS、`docs/**/*.md`、前后端/模块 README、测试 Fixture README；把真实仓库文件导航改为可点击相对链接。
- 对同一当前文档域执行语义事实审计：按机器事实 Owner 核对运行时/依赖、架构与调用链、API/Contract、数据库/Migration、采集/Provider、AI/Reporting、Frontend、测试/CI、部署/Release 等当前状态。
- 对 Roadmap/Blueprint 中本来承担未来设计或上线计划职责的内容保留其规划语义，但明确“已实现 / 待实施 / 历史证据”的边界，不能仅因当前代码尚未实现就删除已批准未来设计。
- 历史 `changes/archive/`、installer-owned `.agents`、运行时 Prompt 等机器消费 Markdown 不作为本次“当前项目文档域”批量改写对象；当前文档引用历史 Change 时可以保留链接，但不回写历史内容。
- 新增/维护 AIMA 项目级治理静态检查与回归测试。
- 删除三份把 Agent_Skills canonical 源码结构当作 AIMA 单元测试事实的旧 `test_coding_*`。
- 修复 `ci.yml` 与 `change-completion-gate.yml` 的治理证明责任。

# 非目标

- 不为了让旧文档成立而修改业务 API、Pydantic Contract、OpenAPI、Schema、Migration、数据库数据语义、generated client 或产品行为；若文档与当前实现冲突，本任务默认修正文档，除非上游批准事实明确证明实现才是错误方。
- 不升级 Python、Node、npm、uv、框架、依赖或 PostgreSQL。
- 不修改 `.agents` installer-owned Skill Core、Runtime binary、legacy `agent-skills-install/v3` manifest、MCP 配置或 managed block；这些等待后续正式 Agent_Skills Runtime Release/upgrade。
- 不调整产品功能、Figma、Provider、Prompt、部署拓扑或 Production Go-Live 范围。
- 不把命令、目录树、glob、占位路径、协议/流程示例、时区标识或代码字面量为了形式统一机械转换成链接。
- 不改写 `changes/archive/` 历史状态与当时证据。
- 不在本任务启用 GitHub Branch Protection；当前 required checks 先恢复为可靠绿色，再单独治理平台保护策略。
- 不建立一套声称能自动理解全部自然语言语义的“文档真相正则”；机器 gate 只固定高置信、长期稳定的不变量，其余语义一致性由本次全量人工/Agent 审查完成。

# 必须保持不变

- AIMA 当前模块化单体、API/Worker/Scheduler/Migration 分进程、PostgreSQL 18、Python 3.14、Vue 3 + TypeScript + Vite、根 uv 工程等已批准长期基线；精确版本继续由版本文件、Manifest/lock、Docker/Compose 机器事实维护。
- 当前八种持久 Job 的代码行为和 Job type 字符串不变化，本任务只修正文档与治理接线。
- Pydantic/OpenAPI/generated client、Alembic Migration、表 Owner、Secret、Artifact、Job Runtime 和生产部署规则不变化。
- 内网 V1 已完成、完整 Production Go-Live 仍 No-Go 的 Roadmap 语义不变化，除非当前 Roadmap 自身的状态证据证明已有更新。
- 现有 full CI 的 Unit/Contract/API、PostgreSQL Integration、Browser、Runtime、Release 等独立产品证据不得因治理收敛被较弱检查替代。
- `ready_check.py` 继续验证 AIMA 自己的 `coding-change/v1` carrier；不把 Agent_Skills 源仓库自测复制到业务仓库。
- 链接迁移不删除有效技术内容；语义审计只修复与当前机器事实冲突、状态表述错误、重复机器定义或已失效导航，不为“简化文档”压缩仍有维护价值的信息。

# 关键决策

## 方案比较

1. **把 Agent_Skills `references/` 与内部 tests 再复制回 AIMA**：能让旧 CI 暂时绿色，但重新制造双 canonical，升级后必然漂移；拒绝。
2. **直接删除 Completion Gate / 治理检查**：能绕过当前失败，但降低持续证明责任；拒绝。
3. **AIMA 只保留项目 Overlay + 项目治理接线检查，Agent_Skills 自测回归 canonical Owner；保留 `ready_check.py` 与现有产品 CI**：职责清晰、无双副本、可持续升级；采用。
4. **文档路径全部机械正则替换为链接**：会误伤命令、目录树、glob、占位符、时区标识和协议示例；拒绝。
5. **以真实文件可解析性 + 导航语义为门禁，仓库相对链接作为统一表达**：既可点击又可随仓库移动验证；采用，但解析器必须过滤非导航字面量。
6. **仅让链接检查通过，不核对文档正文**：会留下版本、接口、Job、路由、Schema、部署状态等语义漂移；拒绝。
7. **当前实现事实按机器 Owner 逐域核对，规划/历史按其正式状态保留；高置信不变量才进入自动 gate**：能兼顾准确性、可维护性和低误报；采用。

## Evidence Preservation Mapping

| 原证明责任 | 原位置 | 新位置 / Owner | 证据等级 | 依据 |
| --- | --- | --- | --- | --- |
| Agent_Skills canonical Skill/Reference 的完整性、路由、内容守恒 | AIMA `.agents/skills/coding/tests` 假设与 `tests/unit/test_coding_*` | `dingyuwen777/Agent_Skills` 自身 Skill Tests | 保持且归位 | 这些规则不是 AIMA 项目事实，目标项目 Runtime 也不分发 canonical References/tests |
| AIMA 根治理入口、项目 Overlay、禁止把本地 canonical Reference 当项目事实源 | 零散 `test_coding_*` | `scripts/quality/check_agent_governance.py` + `tests/unit/test_agent_governance.py` | 保持并更直接 | 新检查只验证 AIMA 自己可维护的接线与文档 |
| AIMA 当前文档本地链接和仓库文件导航 | 原 `check_docs.py` 只检查固定入口链接，无真实文件导航门禁 | `scripts/quality/check_docs.py` + `tests/unit/test_docs_navigation.py` | 增强 | 当前项目文档域统一验证链接存在和真实文件导航可点击，同时过滤非导航字面量 |
| AIMA 当前文档与仓库事实一致性 | 主要依赖人工维护，缺少本次全域复核 | 本 Change 的领域事实矩阵 + 当前机器 Owner + 必要高置信静态回归 | 增强 | 语义一致性不能由链接存在性证明；精确事实回到代码/Contract/Schema/lock/CI Owner |
| AIMA 文档/Secret 静态门禁 | `ci.yml` docs-governance | 原 `check_docs.py` / `scan_secrets.py`，并增强 `check_docs.py` | 保持 | 原项目级证明责任不删除 |
| Requirement Traceability / Completion Audit 结构与状态 | `change-completion-gate.yml` | 原 `ready_check.py` | 保持 | 继续运行同一项目受管 CLI，不用供应方内部 test suite 冒充 Ready 证明 |
| 产品 Unit/Contract/API/DB/Browser/Build/Runtime | `ci.yml` full profile 与其他 workflows | 原位置保持 | 保持 | 本任务不删除或收缩产品证明层 |

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 第一次使用 Agent_Skills 开发 AIMA_UGC 时完成有证据的项目治理，并按确认方案落库 | user:2026-09-01-aima-agent-skills-governance | satisfied | PR #274 在 b9217cc8 的治理、文档与永久 CI 变更已落库；CI 33463204045、Completion Gate 33463204034、Full-stack 33463204036、Runtime 33463204099、Release dry-run 33463204038、Tooling 33463204060 全部 success。 |
| R2 | 项目规则和项目真实事实始终先读；Source/Runtime 模式只改变通用治理取得方式，不能跳过 AIMA Overlay | AGENTS.md | satisfied | 最终 AGENTS.md 保持项目事实优先；本轮重新读取目标项目规则与 Agent_Skills canonical Source Mode 入口后完成复核。 |
| R3 | Project Governance Bootstrap 只维护 managed block 外项目 Overlay，不把 Agent_Skills 内部实现写成项目规则 | user:2026-09-01-aima-agent-skills-governance | satisfied | AGENTS.md 只修改 managed block 外项目 Overlay；scripts/quality/check_agent_governance.py 与 tests/unit/test_agent_governance.py 固定 AIMA 自有接线，PR 不修改 installer-owned .agents 运行资产。 |
| R4 | Worker Registry 文档必须与当前生产装配的八种持久 Job 一致 | backend/src/aima_ugc/bootstrap/worker.py | satisfied | docs/blueprint/01_总体架构与技术选型.md 已列当前八种生产 Job；check_docs_facts.py 从 bootstrap/worker.py 实际 register_* 装配动态发现 Job，CI 文档事实门禁 success。 |
| R5 | 修复当前 main 的 Completion Gate 根因，不能通过删除/降低门禁绕过 | .github/workflows/change-completion-gate.yml | satisfied | .github/workflows/change-completion-gate.yml 保留 ready_check.py 并用 AIMA 项目治理检查替代不存在的 supplier tests；final-shape run 33463204034 success。 |
| R6 | 不手工迁移 legacy v3 Runtime/manifest/managed block；正式升级留给后续 Agent_Skills Release | .agents/agent-skills-install.json | satisfied | PR changed files 不包含 installer-owned .agents Runtime/manifest/managed asset；AGENTS managed block 未手工迁移，项目治理 gate success。 |
| R7 | AIMA 当前技术栈、Contract/Schema/Migration、产品行为和 Production Roadmap 不因治理任务变化 | docs/blueprint/07_技术决策与实施门禁.md | satisfied | 本 PR 未修改产品实现、Contract、Schema/Migration、依赖或 Runtime 版本；generated contract drift、PostgreSQL Integration、Full-stack、Runtime 与 Release dry-run 均在 b9217cc8 成功。 |
| R8 | 全面检查仓库当前文档，把其中引用的其他真实仓库文件改成可点击链接 | user:2026-09-01-doc-repository-file-links | satisfied | check_docs.py 已覆盖本地链接、未链接文件导航、纯文件/文件职责代码块和完整仓库相对路径标签；tests/unit/test_docs_navigation.py 回归存在，final CI 文档 gate success。 |
| R9 | 不只修链接，还要全面保证当前文档描述与当前仓库事实一致 | user:2026-09-01-doc-fact-consistency | satisfied | check_docs_facts.py 对 OpenAPI、Schema、生产 Worker Job、永久 Workflow、前端 Route、TikHub Provider、版本、Analysis 与 Release 高置信事实持续校验；final CI 文档事实 gate success。 |


# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | AIMA governance checker、docs navigation checker 与对应 unit test，证明 marker、Ready 入口、项目文档、workflow 接线、真实文件导航链接约束和非导航字面量过滤 |
| 接口 / Contract | required | 本任务不修改 Contract，但文档 API/字段/接口描述必须与当前 Pydantic/OpenAPI/JSON Schema/generated client 机器事实核对；运行既有 Contract/generated drift 检查证明未被文档治理改坏 |
| 集成 / Persistence / Runtime Dependency | required | 不修改数据库行为，但数据库/运行时文档要与当前 Schema/Migration/Compose/实际进程事实核对；保留并读取 PostgreSQL Integration 等既有 final HEAD 证据 |
| 用户 / Workflow Acceptance | required | GitHub PR/main 上真实永久 CI workflow 运行，证明开发者合并门禁与文档检查可执行；前端/运行说明与真实入口、路由和用户工作流对照 |
| 跨组件 Golden Path | required | 不新增产品链路，但当前文档覆盖 API/Worker/Frontend/DB 等跨组件关系；保留并读取 final HEAD Real Full-stack/Runtime Acceptance 作为“产品行为未被治理变更破坏”的交叉证据 |
| External Dependency / Provider Probe | not_applicable | 不修改 Provider/LLM/远端协议；文档中 Provider 当前能力优先对照仓库 capability/fixture/既有已验证台账，不为本次纯文档治理重复付费 Probe |
| Build / Package / Runtime | required | 不修改产品 build/package/runtime 语义，但文档中的版本/镜像/启动/部署事实需与 Manifest/lock/Dockerfile/Compose/Workflow 核对，并保留 final HEAD build/runtime CI 证据 |
| Docs / Governance / Other | required | 全当前项目文档域链接扫描、语义事实矩阵、失效链接清零、DOC007/DOC008 零错误、Secret gate、project governance gate、`ready_check.py`、Workflow Responsibility Audit、PR/main fresh CI |

# 实施步骤

1. 建立项目级治理 gate，先编码 AIMA 自己必须保持的治理不变量。
2. 删除三份错误 Ownership 的 Agent_Skills 源码结构单测，把仍属于 AIMA 的断言迁移到项目 gate/test。
3. 修正 Blueprint Job 列表、开发流程文档与根项目 Overlay 的已知偏差状态。
4. 扩展 `check_docs.py` 到当前项目文档域：验证所有相对链接，并识别未链接的真实仓库文件导航；用单元测试固定“真实文件导航要可点击、命令/示例/时区标识不机械链接化”的边界。
5. 以 GitHub Runner 的 DOC007/DOC008 全量结果为导航迁移清单，逐文档把真实文件导航迁移为相对链接；重新运行直到零错误，并补人工反查未被保守规则捕获的导航代码块/短路径。
6. 建立本次文档事实矩阵并逐域核对：
   - 运行时与依赖：`.python-version`、`.node-version`、`.uv-version`、`pyproject.toml`、`frontend/package.json`、lock；
   - 架构/进程/Job：entrypoints、bootstrap、Job Registry、模块 README；
   - API/Contract：Pydantic Contract、generated OpenAPI/JSON Schema/generated client；
   - 数据：`database_schema.py`、各模块 table Owner、Alembic Migration；
   - 采集/Provider：capabilities、operations/mappers、pricing/fixture 和当前路由；
   - AI/Reporting：Prompt/analysis runtime、LLM adapter、Excel/Word/reporting implementation；
   - Frontend：routes、feature pages、真实 API client 与状态；
   - 测试/CI：测试目录、package scripts、永久 workflows、quality gates；
   - 部署/Release：Dockerfile、Compose、env examples、deploy scripts、release workflow。
7. 对每个发现分类为“文档错误 / 实现错误 / 未来设计 / 历史事实 / 暂无法验证”；默认只修文档错误。若发现实现违反更高优先级已批准事实，停止把文档改成错误实现的说明并单独记录实现问题。
8. 修改永久 CI：governance-only 与 Completion Gate 改为运行 AIMA 项目治理 gate + 既有 docs/secret/ready checks；full 产品测试职责保持。
9. 运行/读取 PR fresh CI；完成 Completion Audit 与独立 Review，只有 final HEAD 全绿才合并。
10. 合并后读取 `main` fresh CI；将 Change 标记 `done` 并独立归档，归档 PR 也走新鲜 CI。

# Completion Audit

- [x] upstream_re_read：已重新读取本轮用户确认的项目治理、全仓文件链接与文档事实一致性要求，并重新读取 AIMA AGENTS/Blueprint、当前机器 Owner、final-shape CI 与 Agent_Skills canonical Source Mode 规则。
- [x] change_coverage：A1 从上游要求反查 Change：项目 Overlay、Completion Gate 根因、supplier self-test Ownership、Runtime managed 边界、全当前文档链接和事实一致性均已进入 R1-R9，没有未批准遗漏或延期。
- [x] reverse_audit：A2 从实现反查证据：永久 Workflow 证明责任未收缩；check_docs/check_docs_facts/check_agent_governance 与 Unit 回归覆盖新增治理；Contract、PostgreSQL、Full-stack、Runtime、Release dry-run 交叉证明产品边界未被文档治理破坏。
- [x] unresolved_cleared：Ready 范围内 R1-R9 均为 satisfied，required 验证在 b9217cc8 有新鲜证据；仅合并后 main fresh CI 与 Change archive 保留为 post-merge 交付步骤，不冒充 Ready 前已完成。

# 验证证据

- Red 基线：AIMA `main@e9d43c7d04a8c1fd595381fbc4add308adad8e62` 的 Change Completion Gate run `33374658066` 在 `Run Coding completion-gate tests` 失败，错误为 `ImportError: Start directory is not importable: '.agents/skills/coding/tests'`，退出码 1；后续 Ready Check 被跳过。
- PR #274 第一轮 `head@0c8371ef0fc24476eb8965326b2dbffd2eb7d3b9`：Change Completion Gate 的 AIMA project governance wiring 与 changed PR Ready Check 均实际执行成功；`check_docs.py`、Secret gate、project governance gate 也成功。Repository Quality 唯一已确认失败为新增 `check_agent_governance.py` Ruff format，已在后续 commit 修正。
- PR #274 `head@69577e143c9952f538c4854216afc4beb195efb0`：Runtime Acceptance、Full-stack Acceptance、Change Completion Gate 成功；CI 中 PostgreSQL Integration 成功，Repository Quality 的 format/lint/mypy、691 Unit、92 Contract、38 API、Architecture/Ownership、Secret 均成功；唯一失败层为 docs gate 的 DOC003/DOC007/DOC008 全域 Red 清单。
- 文档文件链接 Red 基线：当前 Runner 已枚举根文档、`docs/**`、前后端/模块 README 和 Fixture README 的大量 DOC007/DOC008；同时发现 `Asia/Shanghai` 被偶然解析到 `.agents/.../zoneinfo/Asia/Shanghai` 的误报，必须先修解析边界再完成迁移。
- 文档事实一致性 Red 基线：已确认精确运行基线为 Python 3.14.7、Node 24.19.0、npm 11.17.0、uv 0.12.3、PostgreSQL 18.4；后续按领域矩阵继续扫描文档中的旧版本、旧路径、旧接口/Job/路由/部署描述。

- Ready 前 final-shape 证据：PR #274 `head@b9217cc8bd9f47f3d8a2d5fbf33431e8681397ad` 的 CI run `33463204045`、Change Completion Gate `33463204034`、Full-stack Acceptance `33463204036`、Runtime Acceptance `33463204099`、Release dry-run `33463204038`、Developer Tooling Compatibility `33463204060` 均为 `success`；本次 Ready 元数据提交后仍需在新 HEAD 重新取得 fresh CI。

## Ready 前独立复核摘要

- Review A1：重新从用户要求和项目正式事实源构建完成定义，没有发现未进入当前 Change 的适用要求。
- Review A2：实现、测试、文档与 Validation Matrix 对应；CI/Workflow 证明责任保持或增强，没有用文档/治理 gate 替代产品 Unit、Contract、PostgreSQL、Browser、Full-stack、Runtime 或 Release 证据。
- 第二阶段质量复核：已修复生产 Job 事实源手写列表、仓库文件链接显示路径/同目录短文件解析等维护风险；当前没有剩余 BLOCKER/HIGH/MEDIUM Finding。
- 未验证边界：真实生产服务器状态、Provider/LLM 当前额度、正式 Production Go-Live 不属于本 Change，继续按 Roadmap 维持未确认状态。

## 合并与归档证据

- Draft PR #274 因当前宿主 Draft → Ready mutation 返回已知 GraphQL 字段错误而关闭，`merged=false`；未作为最终交付 PR。
- 最终 PR #275：reviewed head `9a716d9e24de810a510dd7cd47c3c2deb8a123f9`，Deep Review `5073545285` 结论 `NO_FINDINGS_WITHIN_SCOPE`，无未解决 review thread。
- PR #275 fresh CI 全绿：CI `33464113553`、Change Completion Gate `33464113561`、Full-stack Acceptance `33464113556`、Runtime Acceptance `33464113613`、Release dry-run `33464113589`、Developer Tooling Compatibility `33464113537` 均为 `success`。
- PR #275 使用 expected-head SHA 合并，merge commit 为 `ebebd5fd7d001d4aadec53fd486f8c6d163b88df`。
- 合并后 `main@ebebd5fd7d001d4aadec53fd486f8c6d163b88df` fresh push CI 全绿：CI `33464376086`、Change Completion Gate `33464376112`、Full-stack Acceptance `33464376092`、Runtime Acceptance `33464376171`、Developer Tooling Compatibility `33464376109` 均为 `success`。
- 本归档只把已完成 Change 从 `changes/active/` 移到 `changes/archive/2026-09/` 并封存最终证据，不修改产品实现、Contract、Schema/Migration、依赖或运行时。

# 文档影响

- 根 `AGENTS.md`：只更新项目自有 Overlay/校准结果，不动 installer-managed block；其当前实现性描述也纳入事实审计。
- 根 README、`docs/**/*.md`、`frontend/README.md`、模块 README、Fixture README：真实仓库文件导航链接化；同时按当前机器 Owner 修正硬错误和语义漂移，保留仍有效的技术细节。
- Blueprint：既核对当前架构/Job/Contract/数据/部署事实，也保留经批准但尚未落地的未来设计，并明确状态。
- Roadmap：状态描述必须与当前实现/验收事实一致；规划项不能被误写成当前能力。
- Appendix/Guides：实现细节、命令、接口、测试、部署说明必须与当前仓库真实入口一致，不复制第二套机器定义。
- 历史 `changes/archive/` 不改写。

# Git / PR / Release

- 用户已明确授权本任务修改、提交、PR、合并到 `main`；2026-09-01 又明确要求把全仓当前文档中的其他仓库文件引用改为链接，并进一步要求保证文档描述与仓库事实一致。
- 当前分支：`chore/agent-skills-project-governance`，基于 `main@e9d43c7d04a8c1fd595381fbc4add308adad8e62`。
- PR：#274，当前 Draft，实施和验证继续在该 PR 完成。
- Release：not_applicable，本任务不创建 AIMA 或 Agent_Skills Release/tag。
