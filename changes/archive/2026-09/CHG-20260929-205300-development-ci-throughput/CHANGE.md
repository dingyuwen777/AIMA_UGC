---
schema: coding-change/v1
id: CHG-20260929-205300-development-ci-throughput
title: 优化开发全链路与FinalCI关键路径
level: L3
status: done
owner: dingyuwen777
branch: tech/671-development-flow-ci
created: 2026-09-29
updated: 2026-09-29
completion_gate: required
depends_on: []
affected_areas:
  - ci
  - developer-workflow
  - testing
  - git
  - governance
affected_paths:
  - .github/workflows/ci.yml
  - scripts/quality/classify_ci_scope.py
  - scripts/dev/validate_changed.py
  - tests/unit/test_ci_scope.py
  - tests/unit/test_ci_workflow_structure.py
  - tests/unit/test_ci_test_impact_optimization.py
  - tests/unit/test_validate_changed.py
  - AGENTS.md
  - docs/04_测试与调试说明.md
  - docs/blueprint/06_开发约束与分阶段实施.md
contracts:
  - CI Plan Evidence Routing
  - Development Changed-Scope Preflight
data_changes: []
---

# 变更摘要

- **要解决的问题**：Final CI 的 PostgreSQL/Real Full-stack 被完整 Core 串行阻塞；Backend/Frontend 仍以宽范围执行；开发期没有统一 changed-scope preflight，过程性 commit 与无关 main 同步增加 Review/交付成本。
- **拟议修改**：增加轻量 CI Plan；Backend/Frontend selector 与 PostgreSQL/Full-stack 共用 classifier；新增 `validate_changed`；固化 Commit Hygiene、Draft→Final 基线同步与 merge freshness。
- **预期结果**：不减少独立 Evidence 的前提下缩短 Final critical path，并让开发期更早发现格式/targeted regression 问题、减少过程 commit。

# 背景、现状与问题

## 背景

Requirement Source：#671。用户要求按全链路优化方案修改并合并 main；其中统一 preflight 与 Commit Hygiene 的通用原则同步到 Agent_Skills #331/#332。

## 当前现状

- `quality-core` 同时分类 scope 和执行大部分 Backend/Frontend Evidence。
- PostgreSQL/Real Full-stack 通过 `needs: quality-core` 读取输出，必须等待 Core 完整结束。
- classifier 已支持 PostgreSQL target/suite、Full-stack spec，但 Backend/Frontend 只有宽布尔量。
- Draft 普通 push 已不触发重 CI；Final Ready 才运行 current-head CI。
- 本地开发没有统一入口复用 classifier；近期复杂 PR 出现大量格式、generated、临时验证与同步 main 过程 commit。

## 问题、根因或约束

根因不是测试数量本身，而是风险分类和执行编排没有彻底分离，且开发期与 CI 之间缺少同源 preflight。修复必须保留 required check identity、所有独立 Evidence、未知路径 fail-closed、main-fresh 和 Review/Completion。

## 不修改的后果

Final CI 继续支付人为串行等待，复杂 PR 继续把可在 push 前闭环的过程状态写入 Git 历史并反复同步 base。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 | 支撑决策 |
| --- | --- | --- | --- |
| E1 | #664 Core 约 8m13 后 PostgreSQL 再约 6m42 | GitHub Actions | scope plan 应从 Core 拆出 |
| E2 | PostgreSQL/Full-stack 已有精准 selector | classifier + CI | 复用现有 Owner，不新建第二套映射 |
| E3 | #655/#658/#661 分别出现 61/69/50 commits | GitHub PR history | Commit Hygiene / preflight 有实际价值 |
| E4 | main Ruleset required contexts 为 CI Gate、Requirement Traceability、Compose Golden Path，strict=true | live Ruleset | check identity 与 fail-closed 不可削弱 |
| E5 | Agent_Skills #331 负责通用规则；AIMA 负责具体脚本/映射 | 用户决定 + canonical Ownership | 跨仓不共用 Change |

# 目标、成功标准与非目标

## 目标

将“scope 计算”与“Evidence 执行”分离；已知 Backend/Frontend 路径选择直接测试，未知回退 all；开发期统一使用同一 classifier；Final 前统一 base/freshness。

## 成功标准

- [ ] #671 / AC1：CI Plan 使 Core/PostgreSQL/Full-stack 可并行。
- [ ] #671 / AC2：Backend/Frontend targeted selector + fail-closed fallback。
- [ ] #671 / AC3：统一 `validate_changed` 复用 classifier。
- [ ] #671 / AC4：Commit Hygiene 项目规则生效。
- [ ] #671 / AC5：Draft 不追无关 main、Final 前统一同步；normal merge 不依赖 bypass。
- [ ] #671 / AC6：Review/CI/merge/main-fresh/archive/closure 完成。

## 范围

#671 所列 CI、classifier、preflight、测试与开发规则。

## 非目标

不删独立 Evidence；不改 Ruleset context；不改产品 Contract/Schema/数据/部署；不处理 Change Archive 批量化与 Runtime/Tooling 第二阶段优化。

## 必须保持不变

- Required contexts 名称与 strict fail-closed。
- Unit/Contract/PostgreSQL/Browser Mock/Full-stack/Runtime/Tooling/Release 独立职责。
- classifier unknown / CI-self change → full。
- main evidence reuse 只有 same-tree 才允许，否则真实验证。
- 不使用 bypass 替代 required gates。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| CI 架构 | 轻量 plan 唯一产出 scope；重 Job 并行消费 | E1-E2 | 降低 critical path |
| Backend/Frontend selector | 高频已知路径精准；未知 all | E2 | 安全渐进收窄 |
| 开发 preflight | 调 classifier CLI/结构输出 | E2/E5 | 单一风险 Owner |
| Commit | 过程态默认不 commit | E3 | 降低 lineage 噪声 |
| Base sync | Draft 不追无关 main；Final 前一次性 fresh | E3-E4 | 减少 Evidence 失效 |
| Merge | expected head/current base/fresh checks；不靠 bypass | E4 | 保持预合并质量 |

# 修改方案与决策依据

## Evidence Preservation Mapping

| 原证明责任 | 原位置 | 新位置 | 证据等级 | 说明 |
| --- | --- | --- | --- | --- |
| Requirement/Completion/Docs/Secret | quality-core | quality-core | 保持 | Job 名与命令不变 |
| Backend Unit/API/Contract | quality-core | quality-core targeted/all | 保持/更精准 | 未知 all |
| Frontend Unit/Build/Browser Mock | quality-core | quality-core targeted/all | 保持/更精准 | build/lint 保留；未知 all |
| PostgreSQL | postgres-integration after core | postgres-integration after plan | 保持 | 同一真实 PostgreSQL |
| Real Full-stack | real-fullstack after core | real-fullstack after plan | 保持 | 同一 reusable Workflow |
| Total Gate | CI Gate | CI Gate | 保持 | 同名 required context |
| Runtime/Tooling/Release | 独立 Workflows | 不变 | 保持 | 本 Change 不移 Owner |

## 最小充分方案

1. 增加 CI Plan：checkout/控制面校验/evidence reuse/classifier，只产出 scope。
2. quality-core / PostgreSQL / Full-stack 依赖 plan，并行运行；CI Gate 聚合 plan + 三层。
3. classifier 增加 Backend targets、Frontend unit/e2e targets；已知路径精准，unknown/full/contract fail closed。
4. classifier 增加机器可读 JSON；`validate_changed.py` 调该 CLI，输出/执行本地稳定层；真实 PostgreSQL/Full-stack 显式留给正式 CI。
5. 项目规则固化 commit/base/merge 节奏。
6. current-head self-change full Evidence + Review → merge → main-fresh。

## 备选方案与取舍

- **只保留原 `quality-core` 串行结构**：证据最简单，但 PostgreSQL/Real Full-stack 必须等待 Core 完整结束，无法解决关键路径瓶颈，不采用。
- **删除 PostgreSQL/Real Full-stack 或用较弱 Mock 代替**：会降低独立 Evidence 等级，不采用。
- **为本地开发单独维护第二套 impact mapping**：容易与 CI selector 漂移，不采用；统一复用 `classify_ci_scope.py`。
- **所有 Backend/Frontend 都继续全量**：安全但收益不足；仅对高置信 Owner 精准映射，共享/未知/CI-self 继续 `all` fail closed。
- **引入 Merge Queue/新 CI 平台**：不是本次根因所需最小机制，不采用。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | CI Plan 并行 | #671 / AC1 | satisfied | `ci-plan` 只产 scope/reuse；Core/PostgreSQL/Full-stack 都消费 Plan，PG/Full-stack 不再依赖 Core；CI Gate 显式校验 PLAN_RESULT。 |
| R2 | Backend/Frontend targeted | #671 / AC2 | satisfied | classifier 新增 backend/frontend targets；高置信 Owner 精准映射直接 Unit/API/Browser Mock，共享/未知/CI-self 回退 all；代表性 selected targets 已 live readback 存在并由永久回归锁定。 |
| R3 | validate_changed 同源 | #671 / AC3 | satisfied | `validate_changed.py` 直接调用 classifier；默认覆盖 base→working tree tracked/staged/unstaged/untracked，`--committed-only` 可复现 revision。 |
| R4 | Commit Hygiene | #671 / AC4 | satisfied | AGENTS/测试指南/Blueprint 已明确临时 CI/debug/formatter/generated/Red 过程态默认不形成正式 commit，并保留有价值 checkpoint 例外。 |
| R5 | Final base/merge freshness | #671 / AC5 | satisfied | 项目规则明确 Draft 不追无关 main；Final 前统一 current base；normal merge 不依赖 bypass，绑定 current head/base/required checks。 |
| R6 | 端到端交付 | #671 / AC6 | explicitly_deferred | current-head Final CI、guarded merge、main-fresh、Archive/Closure 只能在 Ready/merge 生命周期取得。 |

# 计划改动

- [x] 恢复 current main、Ruleset、Workflow、classifier、近期 PR/Actions Evidence。
- [x] 建立 CI Responsibility Audit / Evidence Preservation Mapping。
- [x] 建立永久 Red 回归文件。
- [x] 实现 CI Plan / selector / preflight。
- [x] 同步开发规则和测试文档。
- [x] Completion Audit + FIRST_ASSEMBLY/Repair delta Review 完成；current-head CI 正式延期到 Ready gate。
- [ ] guarded merge + main-fresh + archive + #671 Closure。

# 验证矩阵

| 验证层 | 是否要求 | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | classifier、validate_changed、workflow structure |
| 接口 / Contract | required | required check/output contract 与 classifier JSON |
| 集成 / Persistence / Runtime Dependency | required | Final CI 的真实 PostgreSQL；产品 Runtime 无改动 |
| 用户 / Workflow Acceptance | required | 开发者 preflight plan/execute；Final Ready 流程 |
| 跨组件关键路径 | required | CI Plan → Core/PG/Fullstack → CI Gate |
| 外部依赖 Probe | not_applicable | 无业务外部 Provider |
| Build / Package / Runtime | required | CI self-change full profile；Frontend build 保留 |
| Docs / Governance / Other | required | AGENTS/Blueprint/Test guide/Change/Review |

# 风险、兼容性、迁移与回滚

- Selector 漏测：unknown/contract/CI-self 全量 fallback + daily safety net。
- Plan 失败：quality-core/CI Gate 必须 fail closed，不能让 required job skipped 冒充通过。
- Preflight 环境不足：明确 deferred PostgreSQL/Full-stack，不伪造本地 Evidence。
- 数据/Schema/Migration：不适用。
- 回滚：恢复 Core 内 classification + 原 needs；项目开发规则可独立保留。

# 文档、依赖、部署与发布影响

- **长期文档**：已同步 `AGENTS.md`、`docs/04_测试与调试说明.md`、`docs/blueprint/06_开发约束与分阶段实施.md`，分别承载项目 Overlay、实际测试入口和 CI 架构事实。
- **依赖**：未新增、删除或升级 Python/Node/System 依赖，也未修改 lockfile。
- **配置 / Secret**：不新增环境变量、Secret、端口或生产配置。
- **部署**：不改变产品 Runtime/Compose/部署拓扑，无生产迁移步骤。
- **发布**：本任务不执行 Release/Deploy；Release Workflow 的 Owner/证明责任不变。
- **回滚**：Workflow 变更可通过恢复原 Core 内 classification 与 `needs: quality-core` 回滚；无数据恢复动作。

# 完成审计

- [x] upstream_re_read：已重读 #671、live Ruleset、current main、current PR diff、CI/classifier/preflight/项目规则。
- [x] change_coverage：AC1-AC5 实现责任已覆盖；AC6 只保留 Ready/merge 后直接 Evidence。
- [x] reverse_audit：已反查 Plan fail-closed、Draft PG/Full-stack guard、shared/unknown all fallback、working tree scope、API baseline、required check identity/main reuse。
- [x] unresolved_cleared：无 not_satisfied；只有 AC6 生命周期项 explicitly_deferred。

# 完成证据与状态

当前实现 Head 为 `df81a390eeeb605ad75eaa8fb6c5fa671db9d34c`；FIRST_ASSEMBLY + Repair delta review 当前 `NO_FINDINGS_WITHIN_SCOPE`。精准 Backend/Frontend selector 的代表性目标已逐个 live readback 存在，并增加永久存在性回归。Draft control-plane 实跑为 `CI Plan=success`、Core/CI Gate 明确 failure、PostgreSQL/Real Full-stack skipped；current-head 完整 Green Evidence 只在 Final Ready 取得。

- 分支：tech/671-development-flow-ci
- PR：#672 Draft；本 Change 转 Ready 后保持 Draft，先完成轻量 control-plane check，再切 Ready。
- Review：`NO_FINDINGS_WITHIN_SCOPE`；current-head full CI/merge/main-fresh 仍是交付门禁。
- Release/Deploy：不适用。
