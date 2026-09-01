---
schema: coding-change/v1
id: CHG-20260901-ci-test-scope
title: 收敛 CI Scope、Full-stack 门禁与测试组织
level: L3
status: done
owner: dingyuwen777
branch: refactor/ci-test-scope
created: 2026-09-01
updated: 2026-09-01
completion_gate: required
depends_on: []
affected_areas:
  - ci
  - fullstack-acceptance
  - test-organization
  - project-governance
affected_paths:
  - .github/workflows/ci.yml
  - .github/workflows/fullstack.yml
  - scripts/quality/classify_ci_scope.py
  - tests/unit/test_ci_scope.py
  - tests/unit/collection/test_collection_planning.py
  - tests/contracts/test_canonical_v1.py
  - tests/unit/platform/test_logging.py
  - tests/unit/test_docs_facts.py
  - tests/unit/collection/test_collection_run_executor.py
  - tests/unit/collection/test_stage1_stage7_comprehensive_corrective.py
  - changes/archive/2026-09/CHG-20260901-ci-test-scope/CHANGE.md
contracts: []
data_changes: []
---

# 目标

在不降低任何独立质量证据的前提下，把“除纯文档/治理外统一进入 full + 独立 Full-stack 再跑一遍”的 CI，收敛为按 changed scope 保守选择证据层的持续验证模型；同时把明显历史 Stage/“全面整改”测试包装迁回真实 Owner，降低长期维护认知成本。

# 成功标准

- [x] `CI Gate` 的 Required Check 身份保持不变，并始终产生可审计结果。
- [x] changed scope 分类具有永久 Unit 回归；未知、混合、CI 自身和无法可靠分类的路径 fail closed 到最强证据。
- [x] 纯前端变更只要求前端质量与 Browser Mock 等独立证据，不机械要求 PostgreSQL / Real Full-stack。
- [x] 后端、Contract、Persistence、跨组件和 CI/Runtime 控制面按风险运行对应 Python、Contract、PostgreSQL、Real Full-stack 证据。
- [x] Real Full-stack 保留真实 Golden Path；已知单一路径可 targeted，跨组件/未知场景/控制面变化以 `all` 失败关闭，并由 `CI Gate` 对结果负责。
- [x] `check_agent_governance.py` 只由 Change Completion Gate 承担永久治理责任，不在产品 CI 重复运行。
- [x] `tests/unit/collection/test_stage1_stage7_comprehensive_corrective.py` 的长期有效断言迁回真实 Owner；没有删除独立回归语义。
- [x] 正式 CI/测试文档做了 targeted 复核；现有 Blueprint 已表达“风险相关 profile + 稳定总 Gate + 少量 Real Full-stack Golden Path”，无需制造无事实变化的 Markdown diff。
- [x] 最终 PR revision 完成 revision-bound Deep Review 与 Required Checks 后正常合并；`main` 对 merge commit 取得 fresh CI / Completion / Runtime；本 Change 进入独立归档流程。

# 范围

- 重构 CI changed-scope classifier 与机器输出。
- 按证据责任拆分 `ci.yml` 的后端、前端、Contract、PostgreSQL 和 Real Full-stack 执行条件。
- 将 `fullstack.yml` 作为可复用真实 Golden Path workflow，由 CI 条件调用并接收 targeted spec 或 `all`。
- 移除产品 CI 中重复的 AIMA governance checker 调用，保留 Change Completion Gate 作为唯一 Owner。
- 最小拆分历史“全面整改”测试文件；只迁移已经存在且长期有效的断言。
- 定向复核正式 CI/测试文档与当前实现的一致性。

# 非目标

- 不修改业务 API、Contract、Schema/Migration、数据库语义、Provider、Figma 或部署拓扑。
- 不升级 Python、Node、npm、uv、PostgreSQL、GitHub Actions 或业务依赖。
- 不批量重命名所有历史 Stage 测试；本次只处理证据清楚、Owner 明确的高价值包装。
- 不减少 Unit / Contract / API / PostgreSQL Integration / Browser Mock / Real Full-stack 的独立证明责任。
- 不把 Real Provider Probe 加入普通 CI。
- 不修改 Ruleset 中 `CI Gate`、`Requirement Traceability and Completion Audit`、`Compose Golden Path` 的 Required Check 名称。

# 必须保持不变

- `CI Gate` 始终存在；轻量路径由 Gate 明确验证 required/skipped 组合，而不是让 Required Check 消失。
- scope 分类只能白名单降低成本；未知路径、混合高风险路径、CI 自身、Full-stack 控制面或分类失败必须回退更强验证。
- Browser Mock 不冒充真实 API/PostgreSQL/Worker；PostgreSQL Integration 不冒充 Browser；Real Full-stack 只证明实际运行的 Golden Path。
- Change Completion Gate 继续实际运行 `scripts/quality/check_agent_governance.py` 和 `ready_check.py`。
- 当前锁定 Runtime、依赖、Contract、Schema/Migration、部署与业务行为保持不变。

# 关键决策

1. **保留稳定 `CI Gate`，内部条件执行**：采用。避免 Required Check 因 path filter 消失，并让一个稳定 Gate 持续拥有产品质量合并责任。
2. **删除 Real Full-stack**：不采用。保留真实跨组件证明，但从“几乎所有代码 PR 都跑全部场景”改为“按 changed scope 运行相关 Golden Path”。
3. **把所有测试合并成更少文件**：不采用。测试文件数量不是目标；只拆历史包装、收敛重复 Owner。
4. **未知路径默认轻量**：不采用。未知路径 fail closed 到最强证据。
5. **Full-stack 全量用固定旧 allowlist 表示**：不采用。全量责任统一输出 `all`，由 Playwright 扫描整个 `frontend/e2e-fullstack`，防止未来新增 spec 静默漏跑；只有已知单一路径允许 targeted。
6. **修改 Ruleset Required Check 名称**：不采用。当前三个 Required Check 身份保持稳定。

# Requirement Traceability

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 按已确认方案精简 CI 与测试，但不降低质量 | https://github.com/dingyuwen777/AIMA_UGC/issues/282 | satisfied | PR #283 保留 Unit/Contract/API/PostgreSQL/Browser Mock/Real Full-stack 证明责任；最终 PR CI 与 main fresh CI 均全层 success |
| R2 | `CI Gate` 稳定存在，并按风险选择证据层 | https://github.com/dingyuwen777/AIMA_UGC/issues/282 | satisfied | `.github/workflows/ci.yml` 保留 `CI Gate`；`tests/unit/test_ci_scope.py` 覆盖 docs/governance/frontend/backend/contract/persistence/cross-component/unknown/CI-self 等边界；最终 PR 与 main fresh `CI Gate` success |
| R3 | Real Full-stack 保留高价值 Golden Path，并由 CI 条件门禁 | https://github.com/dingyuwen777/AIMA_UGC/issues/282 | satisfied | `fullstack.yml` 为 reusable workflow；CI-self/未知/控制面以 `all` 失败关闭；最终 PR 与 main fresh 都实际启动 PostgreSQL/API/Worker/Browser 并 success |
| R4 | 消除 `check_agent_governance.py` 在 CI/Completion Gate 的重复 Owner | https://github.com/dingyuwen777/AIMA_UGC/issues/282 | satisfied | 产品 CI 的 Docs/Governance 仅保留 Secret/docs；Change Completion Gate 为唯一 governance checker Owner；PR/main fresh Completion 均 success |
| R5 | 历史 Stage/整改测试按真实 Owner 收敛，不按数量删测试 | https://github.com/dingyuwen777/AIMA_UGC/issues/282 | satisfied | 旧 comprehensive 文件的 5 类断言分别迁入 Planning/Canonical/Logging/Docs Facts/Run Executor；最终 Unit 721 passed |
| R6 | 不升级依赖、不改业务 Contract/Schema/Runtime/部署 | AGENTS.md | satisfied | 实现 PR changed files 仅 CI/classifier/tests/Change；Contract generation/compatibility、Wheel、Runtime Acceptance、PostgreSQL migration/integration 均 success |

# Validation Matrix

| 验证层 | 状态 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / Unit / Component | passed | 初始 Red run `33499143177` / job `99828181148` 因 `classify_requirements` 不存在 exit 2；Review Red run `33501013170` / job `99834151769` 为 **2 failed / 719 passed**；最终 PR Unit **721 passed** |
| 接口 / Contract | passed | 最终 PR Repository Quality 重新生成 OpenAPI/Analysis/Canonical/Provider/Collection/Export 与 Orval client，git diff + compatibility 通过；Contract **92 passed**，API **38 passed** |
| 集成 / Persistence / Runtime Dependency | passed | 最终 PR PostgreSQL 18.4 + Alembic upgrade/current/check + migration compatibility + real readiness + Platform/Database/Job/Collection/Content/Ingestion integration 全部 success；main fresh 同层重新 success |
| 用户 / Workflow Acceptance | passed | 最终 PR Vitest **56 passed**、production build success、Browser Mock Playwright **39 passed**；main fresh Repository Quality 重新 success |
| 跨组件 Golden Path | passed | 最终 PR Real Full-stack `all` 真实 PostgreSQL/API/Worker/local fake LLM/Playwright **6/6 passed**；main fresh Real Full-stack 再次 success |
| 外部依赖 Probe | not_applicable | 本次不修改 Provider/远端 API 当前事实；不以真实远端 Probe 冒充 CI 必要证据 |
| Build / Package / Runtime | passed | Wheel build/install/import、Frontend build、最终 PR Runtime Acceptance 与 main fresh Runtime Acceptance 均 success |
| Docs / Governance / Other | passed | Docs/Secret gates、PR Completion、main fresh Completion 均 success；Required Check identities 保持不变 |

# Evidence Preservation Mapping

| 原证明责任 | 原位置 | 新位置 | 证据等级 | 依据 |
| --- | --- | --- | --- | --- |
| Python format/lint/type + Unit/Contract/API | `CI / Repository Quality` | `CI` 条件 Repository Quality | 保持 | 同一锁定 Python/uv 环境；最终 PR 为 531 files format clean、ruff clean、mypy 254 files clean、Unit 721、Contract 92、API 38 |
| Frontend lint/type/unit/build/Browser Mock | `CI / Repository Quality` | `CI` 条件 Repository Quality | 保持 | 同一 npm lock、lint/typecheck/Vitest/build/Playwright Mock；最终 PR Vitest 56、Browser 39 |
| Contract / Generated Client drift | `CI / Repository Quality` | Repository Quality 内条件 Contract 步骤 | 保持 | 仍运行正式 generator、Orval、git diff、`generate.py --check`、compatibility |
| PostgreSQL migration/integration/readiness | `CI / PostgreSQL Integration` | `CI` 条件 PostgreSQL Integration | 保持 | 仍运行 PostgreSQL 18.4、Alembic、真实 readiness 与全部 Integration suites |
| Real Full-stack Browser→API→Worker→PostgreSQL | 独立 PR/push `Full-stack Acceptance` | `CI` 条件调用 reusable `fullstack.yml` | 保持 | 仍启动同一真实组件；已知单链 targeted，未知/跨组件/控制面用 `all` 失败关闭 |
| Project governance wiring | `CI` + `Change Completion Gate` | `Change Completion Gate` | 保持且去重 | 同一 checker 继续在稳定 Required Completion Check 中执行，产品 CI 不重复 Owner |
| `CI Gate` 合并身份 | `CI / CI Gate` | `CI / CI Gate` | 保持 | Ruleset consumer 名称未变化，Gate 对 required success / non-required skipped 做显式核对 |

# Completion Audit

- [x] upstream_re_read：Ready 前重新读取 Issue #282、PR #283 base/head、main-quality-gate Ruleset、AIMA Workflow/Test/Ready Check 和 Agent_Skills canonical CI/Review/Completion 规则；归档前又重新读取 fresh `main` 与根 `AGENTS.md`。
- [x] change_coverage：逐项对照 Issue #282 的目标、非目标、兼容/回滚和验收标准；实现只收敛触发与 Owner，没有删除 Unit、Contract、PostgreSQL、Browser Mock 或 Real Full-stack 独立证据。
- [x] reverse_audit：从 `CI Gate` 反向追到 Scope、Docs、Repository Quality、PostgreSQL、Reusable Full-stack，并从原 Workflow 责任反向核对新 Owner；最终 PR 与 main fresh 对 CI-self 变更都实际走 full/all 路径并成功。
- [x] unresolved_cleared：R1–R6 均有 current-head / main-fresh 证据；Deep Review 发现的 Full-stack 控制面和未知新增 spec 漏跑风险先形成 2-fail Red，再修为 `all` 失败关闭；最终 revision Review PASS、无 unresolved thread。

# 任务

- [x] 为 changed-scope classifier 增加永久 Red/Green Unit 回归
- [x] 扩展 classifier 输出风险层与 Full-stack spec 选择
- [x] 重构 `ci.yml` 条件 Job 与稳定 `CI Gate`
- [x] 将 `fullstack.yml` 改为 reusable Golden Path workflow 并支持 targeted / `all`
- [x] 移除 CI 重复 governance checker
- [x] 拆分 `test_stage1_stage7_comprehensive_corrective.py` 到真实 Owner
- [x] 定向复核正式 CI/测试文档；当前文档无需修改
- [x] 更新 Change 并固化 Completion Audit
- [x] 对最终 PR revision 执行 revision-bound L3 Deep Review / re-review
- [x] Required Checks 全绿后正常合并，并取得 main fresh CI / Completion / Runtime
- [x] 进入独立 Change 归档流程

# 验证

## Red

1. **初始能力 Red**：run `33499143177` / Repository Quality job `99828181148`。静态检查通过后，`pytest tests/unit -q` 在收集 `tests/unit/test_ci_scope.py` 时因 `classify_requirements` 尚不存在产生 `KeyError`，exit 2；证明新 scope 能力并非先实现后补测试。
2. **Deep Review 回归 Red**：run `33501013170` / Repository Quality job `99834151769`。`ruff` / `mypy` 通过，Unit 明确为 **2 failed / 719 passed**，分别命中 Full-stack Playwright 控制面未升级、未知新增 Full-stack spec 未失败关闭；随后才修实现。

## Green / PR

最终实现 revision：`64226ad1de8231652c8da8e98c6053c9847bc79c`。

- CI run `33502017532`：`CI Scope`、`Docs and Governance`、`Repository Quality`、`PostgreSQL Integration`、`Real Full-stack Golden Path`、最终 `CI Gate` 全部 success。
- Repository Quality job `99837326726`：531 files format clean；ruff clean；mypy 254 files clean；Unit **721 passed**；Contract **92 passed**；API **38 passed**；Vitest **56 passed**；Frontend build success；Browser Mock Playwright **39 passed**；Wheel build/install/import success；npm audit 0 vulnerabilities。
- PostgreSQL job `99837326760`：PostgreSQL 18.4 + Alembic + migration compatibility + readiness + Platform/Database/Job/Collection/Content/Ingestion integration 全部 success。
- Real Full-stack job `99837327054`：真实 PostgreSQL + API + Worker + local fake LLM + Playwright，`all` 模式 **6/6 passed**。
- Change Completion Gate run `33502017236` / job `99837295033`：success。
- Runtime Acceptance run `33502017177` / job `99837295741`：success（无 Runtime 风险改动，正式 fast-path）。
- revision-bound L3 Deep Review：base `df8f4fccb156528dc301129ba1dc8cd6a7745ea9` → head `64226ad1de8231652c8da8e98c6053c9847bc79c`，PASS；无 unresolved review thread。

## Merge

- 实现 PR：#283。
- merge method：正常 `merge`，未 bypass protected branch。
- merge commit：`f577079df375cb8941ba40680bd4915c8595122b`。

## Main fresh validation

对 merge commit `f577079df375cb8941ba40680bd4915c8595122b`：

- CI run `33502405382`：completed **success**；`CI Scope`、`Docs and Governance`、`Repository Quality`、`PostgreSQL Integration`、`Real Full-stack Golden Path`、最终 `CI Gate` 均 success。由于变更包含 CI-self 路径，main fresh 仍实际走 `full/all`，没有利用轻量 profile 自证。
- Runtime Acceptance run `33502405095`：completed **success**。
- Change Completion Gate run `33502405343` / job `99838536700`：completed **success**；`Enforce main Active Change readiness` 实际执行并 success。

# 文档影响

已按 Docs Skill 对 `docs/blueprint/06_开发约束与分阶段实施.md` 做 targeted 复核。当前文档已经明确：

- CI 应按风险 profile 选择执行层；
- 总 Gate 必须始终给出明确结果；
- 测试证据存在层级，不能用低成本 Mock 冒充真实 Integration / Browser / Full-stack；
- Full-stack 只保留少量高价值真实链路。

因此本次实现没有改变需要用户理解的正式工程原则，只把机器执行接线与该原则对齐；不为了“有文档变更”而制造重复、易漂移的 Workflow 细节说明。

# Git / PR / Release 状态

- Requirement Source：Issue #282。
- 实现分支：`refactor/ci-test-scope`（保留，不删除）。
- 实现 PR：#283，已正常合并。
- 最终实现 head：`64226ad1de8231652c8da8e98c6053c9847bc79c`。
- merge commit：`f577079df375cb8941ba40680bd4915c8595122b`。
- main fresh CI：`33502405382` success。
- main fresh Runtime：`33502405095` success。
- main fresh Completion：`33502405343` / job `99838536700` success。
- 归档分支：`archive/ci-test-scope`。
- 归档 PR：#284，当前 open；归档 PR 合并并完成 archive-merge main fresh validation 后关闭 Issue #282。
- Release / deploy：不适用，本次没有发布或部署动作。
