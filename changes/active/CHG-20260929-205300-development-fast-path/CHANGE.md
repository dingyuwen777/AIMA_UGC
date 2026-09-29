---
schema: coding-change/v1
id: CHG-20260929-205300-development-fast-path
title: 优化开发全链路与FinalCI关键路径
level: L3
status: ready_for_review
owner: dingyuwen777
branch: tech/671-development-fast-path
created: 2026-09-29
updated: 2026-09-29
completion_gate: required
depends_on: []
affected_areas:
  - ci
  - developer-workflow
  - testing
  - git-governance
affected_paths:
  - .github/workflows/ci.yml
  - scripts/quality/classify_ci_scope.py
  - scripts/dev/validate_changed.py
  - tests/unit/test_ci_scope.py
  - tests/unit/test_ci_workflow_structure.py
  - tests/unit/test_ci_test_impact_optimization.py
  - tests/unit/test_validate_changed.py
  - AGENTS.md
  - docs/blueprint/06_开发约束与分阶段实施.md
contracts: []
data_changes: []
---

# 变更摘要

- **要解决的问题**：Final CI 的 PostgreSQL/Real Full-stack 等待完整 Core；Backend/Frontend 测试选择偏宽；开发期缺少与 CI 同源的 preflight；Git 历史包含过多过程态。
- **拟议修改**：引入轻量 CI Plan；细化安全 selector；新增 `validate_changed`；固化 commit hygiene、Draft/base 同步与 guarded merge freshness。
- **预期结果**：不减少独立 Evidence，缩短 Final CI 关键路径并减少无价值 commit/review 往返。

# 背景、现状与问题

## 背景

Requirement Source：#671。用户已授权修改并合并 main，并要求 preflight/commit hygiene 的通用原则同步到 Agent_Skills #331 / PR #332。

## 当前现状

- `quality-core` 同时分类 scope 和执行 6～8 分钟重验证。
- PostgreSQL/Real Full-stack 通过 `needs: quality-core` 串行等待。
- PostgreSQL/Full-stack 已支持 target/spec，Backend/Frontend 仍主要按 bool 全量。
- 开发期验证入口分散；复杂 PR 出现 50～69 个过程提交。

## 问题、根因或约束

风险分类与昂贵执行耦合，且开发期与 CI 没有一个统一入口。修复必须保持 required context、所有独立 Evidence、unknown fail-closed、current-head CI、Review 和 main-fresh。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 | 决策 |
| --- | --- | --- | --- |
| E1 | #664 Core ~8m13s 后 PostgreSQL ~6m42s 才启动 | Actions 日志 | 拆 CI Plan，让独立 Job 并行 |
| E2 | classifier 已选 PostgreSQL target/suite 与 Full-stack spec | 当前代码 | 扩展同一 Owner，不另造 mapping |
| E3 | #655/#658/#661 分别出现 61/69/50 commits | GitHub PR | 增加 preflight 与 commit hygiene |
| E4 | main Ruleset strict required contexts 保持 | 当前 Ruleset | 不更名、不 bypass |
| E5 | Agent_Skills #331 同步通用规则 | 用户决定 | AIMA 只实现项目 Overlay |

# 目标、成功标准与非目标

## 目标

缩短开发循环和 Final CI critical path，同时不降低任何质量门槛。

## 成功标准

- [x] #671 / AC1：CI Plan 分离 scope，PostgreSQL/Full-stack 不等待完整 Core。
- [x] #671 / AC2：Backend/Frontend 有安全 target selector，未知/共享/CI self full fallback。
- [x] #671 / AC3：统一 `validate_changed` 复用 classifier。
- [x] #671 / AC4：commit hygiene 固化。
- [x] #671 / AC5：Draft 不追无关 main；Final 前 sync；merge current base/head/fresh。
- [ ] #671 / AC6：Review/CI/merge/main-fresh/archive/closure 按正式交付生命周期完成。

## 非目标

不删测试层、不降 Ruleset、不改产品 Contract/Schema/数据/依赖/部署，不处理 Change Archive 批量化、Runtime/Tooling 二次精细化或治理载体自动投影。

# 约束与意图决策

| 维度 | 决定 | 依据 |
| --- | --- | --- |
| CI | plan 与执行分离，Evidence Owner 不变 | E1/E4 |
| selector | 只有稳定 Owner 映射才 targeted，其他 all | E2 |
| preflight | 复用 classifier，脚本只是 adapter | E2/E5 |
| Git | commit 是有审查价值 checkpoint | E3/E5 |
| base freshness | Draft 不追无关 main，Final 前统一恢复 current base | E3/E4 |

# 修改方案与决策依据

1. 新 `ci-plan` 只 checkout、main evidence resolver、scope classification。
2. Core/PostgreSQL/Full-stack 依赖 plan 并行；CI Gate 聚合四者。
3. classifier 增加 backend/frontend target tuples；共享/unknown → `all`。
4. `validate_changed.py` 直接加载 classifier，默认 plan，`--run` 执行安全本地层并明确外部层。
5. AGENTS/Blueprint 固化 commit/base/merge 规则。
6. CI self-change 走 full profile，当前 Head 验证整个新图。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | CI Plan 并行 | #671 / AC1 | satisfied | `.github/workflows/ci.yml` 当前 Head：`ci-plan` 独立分类；Core/PostgreSQL/Real Full-stack 都只依赖 plan，CI Gate 聚合；required context 名称未改。 |
| R2 | Backend/Frontend selector | #671 / AC2 | satisfied | `classify_ci_scope.py` 当前 Head：稳定 Backend domain 选择 domain Unit + 全 API/Contract，稳定 Frontend feature 选择直接 Unit/Browser；shared/unknown/CI-self → `all`；永久正反例已写入 CI scope/impact tests。 |
| R3 | validate_changed 同源入口 | #671 / AC3 | satisfied | `scripts/dev/validate_changed.py` 直接 `runpy` 加载 `scripts/quality/classify_ci_scope.py`；默认 plan、显式 `--run`；无第二 impact mapping。 |
| R4 | commit hygiene | #671 / AC4 | satisfied | `AGENTS.md` + Blueprint 已明确临时 Workflow/debug/formatter/generated/临时 Red 过程态默认不形成正式 commit，并保留有独立证据价值的 checkpoint 例外。 |
| R5 | Final 前 sync / guarded merge | #671 / AC5 | satisfied | `AGENTS.md` + Blueprint 已明确 Draft 不追无关 main、Final 前统一恢复 current base 并 preflight；正常 merge 不用 bypass 替代 current head/base/fresh checks。 |
| R6 | 完整交付 | #671 / AC6 | explicitly_deferred | AC6 自身要求 Ready 后 current-head Actions、guarded merge、main-fresh、Archive/Closure；这些是后续交付门禁，不能在 Change Ready 前伪造。 |

# Validation Matrix

| 验证层 | 是否要求 | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | classifier/preflight/workflow structure |
| 接口 / Contract | required | required check identity / outputs/needs |
| 集成 / Persistence / Runtime Dependency | required | CI self-change full PostgreSQL |
| 用户 / Workflow Acceptance | required | validate_changed CLI + GitHub Actions |
| 跨组件 Golden Path | required | CI self-change Real Full-stack |
| 外部依赖 Probe | not_applicable | 无第三方 Provider |
| Build / Package / Runtime | required | current-head CI + Runtime/Tooling 按现有门禁 |
| Docs / Governance / Other | required | AGENTS/Blueprint/Change/Issue |

# Completion Audit

- [x] upstream_re_read：已重读 #671、当前 main `3e8a3c6d…`、PR #673、active strict `main-quality-gate` 与最终 affected files。
- [x] change_coverage：AC1–AC5 均映射到当前实现/规则；AC6 的 current-head CI/merge/main-fresh/archive/closure 保持正式后续门禁。
- [x] reverse_audit：逐项反查原 Unit/API/Contract/PostgreSQL/Browser Mock/Real Full-stack Evidence Owner、required check identity、Draft fail-closed、metadata-only、main reuse/schedule；未发现被删除的独立责任。Backend targeted 在 Review 中已收紧为 domain Unit + 全 API/Contract。
- [x] unresolved_cleared：无 `not_satisfied`；仅 R6 按 #671/AC6 固有交付生命周期 `explicitly_deferred`。

# 风险、兼容性、迁移与回滚

- 主要风险：selector 漏测或 plan outputs/needs 失配；unknown/CI self 必须 full fallback。
- Contract/API/Schema/Migration/数据：无变化。
- 依赖/Runtime/Deploy：无变化。
- 回滚：恢复 Core 内 classification 与宽 Backend/Frontend 全量路径；无数据回滚。

# 完成证据与状态

- 实现 Head：`47c40075ddd7f41d697e227a37983e3187e7049f`。
- First Review：发现 Backend production target 只跑 domain Unit 可能弱化公共边界回归，已在 `47c40075…` 收紧为 domain Unit + 全 API/Contract；delta re-review 后 `NO_FINDINGS_WITHIN_SCOPE`。
- Workflow 静态反查：Core 中 `steps.classify.outputs`=0；全部 classification 只在 `ci-plan`；`CiRequirements` 3 个构造点均覆盖新增 target 字段；PostgreSQL/Full-stack 不再依赖 `quality-core`。
- 当前 main 与 PR base 均为 `3e8a3c6d601f963dc1429c81fe252c999b645bfd`，Final 前无 base drift。
- current-head CI / guarded merge / main-fresh / archive / closure：按 R6 在 Ready/merge 后取得。
