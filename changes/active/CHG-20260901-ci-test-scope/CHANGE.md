---
schema: coding-change/v1
id: CHG-20260901-ci-test-scope
title: 收敛 CI Scope、Full-stack 门禁与测试组织
level: L3
status: in_progress
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
  - tests/unit/collection/
  - tests/unit/platform/
  - tests/unit/content/
  - docs/blueprint/06_开发约束与分阶段实施.md
  - changes/active/CHG-20260901-ci-test-scope/CHANGE.md
contracts: []
data_changes: []
---

# 目标

在不降低任何独立质量证据的前提下，把当前“除纯文档/治理外全部进入 full + 独立 Full-stack 再跑一遍”的 CI，收敛为按 changed scope 保守选择证据层的持续验证模型；同时把明显历史 Stage/“全面整改”测试包装迁回真实 Owner，降低长期维护认知成本。

# 成功标准

- [ ] `CI Gate` 的 Required Check 身份保持不变，并始终产生可审计结果。
- [ ] changed scope 分类具有永久 Unit 回归；未知、混合、CI 自身和无法可靠分类的路径 fail closed 到最强证据。
- [ ] 纯前端变更只运行前端质量与 Browser Mock 等独立证据，不机械运行 PostgreSQL / Real Full-stack。
- [ ] 后端、Contract、Persistence、跨组件和 Runtime/CI 变更按风险运行对应 Python、Contract、PostgreSQL、Real Full-stack 证据。
- [ ] Real Full-stack 保留现有 Golden Path，但按 changed scope 只运行相关 spec；需要它时由 `CI Gate` 对其结果负责。
- [ ] `check_agent_governance.py` 只由 Change Completion Gate 承担永久治理责任，不在产品 CI 重复运行。
- [ ] `tests/unit/collection/test_stage1_stage7_comprehensive_corrective.py` 的长期有效断言迁回真实 Owner；不删除任何独立回归语义。
- [ ] 受影响正式 CI/测试文档与当前实现一致。
- [ ] 当前 PR head 通过 Completion Audit、Deep Review、Required Checks；合并后 `main` 对 changed scope 取得 fresh CI。

# 范围

- 重构 CI changed-scope classifier 与其机器输出。
- 按证据责任拆分 `ci.yml` 的后端、前端、Contract、PostgreSQL 和 Real Full-stack 执行条件。
- 将 `fullstack.yml` 作为可复用真实 Golden Path workflow，由 CI 条件调用并接收本次需要执行的 spec。
- 移除产品 CI 中重复的 AIMA governance checker 调用，保留 Change Completion Gate 作为唯一 Owner。
- 最小拆分历史“全面整改”测试文件；只迁移已经存在且长期有效的断言。
- 同步正式开发/CI 文档。

# 非目标

- 不修改业务 API、Contract、Schema/Migration、数据库语义、Provider、Figma 或部署拓扑。
- 不升级 Python、Node、npm、uv、PostgreSQL、GitHub Actions 或业务依赖。
- 不批量重命名所有历史 Stage 测试；本次只处理证据清楚、Owner 明确的高价值包装。
- 不减少 Unit / Contract / API / PostgreSQL Integration / Browser Mock / Real Full-stack 的独立证明责任。
- 不把 Real Provider Probe 加入普通 CI。
- 不修改 Ruleset 中 `CI Gate`、`Requirement Traceability and Completion Audit`、`Compose Golden Path` 的 Required Check 名称。

# 必须保持不变

- `CI Gate` 始终存在；任何轻量路径都必须由 Gate 明确验证 required/skipped 组合，而不是让 Required Check 消失。
- scope 分类只能白名单降低成本；未知路径、混合高风险路径或分类失败必须回退到更强验证。
- Browser Mock 不冒充真实 API/PostgreSQL/Worker；PostgreSQL Integration 不冒充 Browser；Real Full-stack 只证明实际运行的 Golden Path。
- Change Completion Gate 继续实际运行 `scripts/quality/check_agent_governance.py` 和 `ready_check.py`。
- 当前锁定 Runtime、依赖、Contract、Schema/Migration、部署与业务行为保持不变。

# 关键决策

1. **保留稳定 `CI Gate`，内部条件执行**：采用。避免 Required Check 因 path filter 消失，并让一个稳定 Gate 持续拥有产品质量合并责任。
2. **删除 Real Full-stack**：不采用。保留真实跨组件证明，但从“几乎所有代码 PR 都跑全部场景”改为“按 changed scope 运行相关 Golden Path”。
3. **把所有测试合并成更少文件**：不采用。测试文件数量不是目标；只拆历史包装、收敛重复 Owner。
4. **未知路径默认轻量**：不采用。未知路径 fail closed 到最强证据。
5. **修改 Ruleset Required Check 名称**：不采用。当前三个 Required Check 身份保持稳定。

# Requirement Traceability

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 按已确认方案精简 CI 与测试，但不降低质量 | GitHub Issue #282 | not_satisfied | 待实现并取得当前 PR/main 新鲜证据 |
| R2 | `CI Gate` 稳定存在，并按风险选择证据层 | GitHub Issue #282 | not_satisfied | 待 classifier/Workflow 回归与真实 PR CI |
| R3 | Real Full-stack 只保留少量高价值 Golden Path，并由 CI 条件门禁 | GitHub Issue #282 | not_satisfied | 待 reusable workflow 与 PR CI 证据 |
| R4 | 消除 `check_agent_governance.py` 在 CI/Completion Gate 的重复 Owner | GitHub Issue #282 | not_satisfied | 待 Workflow diff 与 Change Completion Gate 证据 |
| R5 | 历史 Stage/整改测试按真实 Owner 收敛，不按数量删测试 | GitHub Issue #282 | not_satisfied | 待测试迁移与 targeted/full regression |
| R6 | 不升级依赖、不改业务 Contract/Schema/Runtime/部署 | AIMA_UGC AGENTS.md | not_satisfied | 待最终 diff、lock/Contract/Schema 检查 |

# Validation Matrix

| 验证层 | 状态 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / Unit / Component | required | classifier Red→Green；历史测试迁移后目标回归与相关 Unit |
| 接口 / Contract | required | 本次不改业务 Contract，但 CI 仍必须证明 Contract / Generated Client 原责任没有丢失 |
| 集成 / Persistence / Runtime Dependency | required | 本次改变 PostgreSQL Integration 的触发责任；当前 CI 变更必须实际命中并通过真实 PostgreSQL 层 |
| 用户 / Workflow Acceptance | required | Browser Mock 责任保持；本次 CI 变更在保守 full/self profile 下实际运行 |
| 跨组件 Golden Path | required | Real Full-stack reusable/条件门禁必须在当前 CI 变更中实际执行现有 Golden Path |
| 外部依赖 Probe | not_applicable | 不修改 Provider/远端 API 当前事实，不运行真实外部 Probe |
| Build / Package / Runtime | required | Wheel、Frontend build 与 Compose Golden Path 责任保持；当前 CI/Runtime fresh checks |
| Docs / Governance / Other | required | Workflow/Change/Docs/governance checker/Ready Check/Ruleset identity |

# Evidence Preservation Mapping

| 原证明责任 | 原位置 | 新位置 | 证据等级 | 依据 |
| --- | --- | --- | --- | --- |
| Python format/lint/type + Unit/Contract/API | `CI / Repository Quality` | `CI` 条件后端质量 Job | 保持 | 仍使用同一锁定 Python 环境与正式命令 |
| Frontend lint/type/unit/build/Browser Mock | `CI / Repository Quality` | `CI` 条件前端质量 Job | 保持 | 仍使用 npm lock、Vitest、Playwright Mock 与正式 build |
| Contract / Generated Client drift | `CI / Repository Quality` | `CI` 条件 Contract Job | 保持 | 仍运行正式生成器、git diff 与 compatibility check |
| PostgreSQL migration/integration/readiness | `CI / PostgreSQL Integration` | `CI` 条件 PostgreSQL Job | 保持 | 仍运行 PostgreSQL 18.4、Alembic、真实 Integration suites |
| Real Full-stack Browser→API→Worker→PostgreSQL | 独立 `Full-stack Acceptance` | `CI` 条件调用 reusable `fullstack.yml` | 保持 | 仍启动同一真实组件，只收敛到相关 Golden Path spec |
| Project governance wiring | `CI` + `Change Completion Gate` | `Change Completion Gate` | 保持且去重 | 同一 checker 继续在稳定 Required Completion Check 中执行 |
| `CI Gate` 合并身份 | `CI / CI Gate` | `CI / CI Gate` | 保持 | Ruleset consumer 名称不改变 |

# Completion Audit

- [ ] upstream_re_read：Ready 前重新读取 Issue #282、AIMA 当前 Ruleset/Workflow/Test 事实和 Agent_Skills CI 证明责任规则。
- [ ] change_coverage：逐项比较 Issue #282 验收标准与本 Change，确认没有把“降低成本”误实现为删除独立证据。
- [ ] reverse_audit：从 `CI Gate` 反向追每个 required 输出到实际 Job/命令，并从原 Workflow 责任反向确认新 Owner。
- [ ] unresolved_cleared：R1–R6 无 `not_satisfied`；所有 required Matrix 层有当前 HEAD 证据。

# 任务

- [ ] 为 changed-scope classifier 增加永久 Red/Green Unit 回归
- [ ] 扩展 classifier 输出风险层与 Full-stack spec 选择
- [ ] 重构 `ci.yml` 条件 Job 与稳定 `CI Gate`
- [ ] 将 `fullstack.yml` 改为 reusable Golden Path workflow 并支持 targeted specs
- [ ] 移除 CI 重复 governance checker
- [ ] 拆分 `test_stage1_stage7_comprehensive_corrective.py` 到真实 Owner
- [ ] 同步正式 CI/测试文档
- [ ] 更新 Change 为 ready_for_review 并通过机器 Ready Check
- [ ] 对 PR 当前 revision 执行 Deep Review / re-review
- [ ] Required Checks 全绿后合并，并取得 main fresh CI
- [ ] 单独归档 Change

# 验证

## Red

待记录。

## Green / PR

待记录。

## Main fresh validation

待记录。

# 文档影响

`docs/blueprint/06_开发约束与分阶段实施.md` 当前承担开发与 CI 门禁说明；本次改变 CI 的实际分层触发责任，因此需要 targeted 同步。其他 Blueprint 只有发现直接冲突时才修改，不做机械全量文档审计。

# Git / PR / Release 状态

- Requirement Source：Issue #282。
- 分支：`refactor/ci-test-scope`。
- PR：待创建。
- merge：未执行。
- Release / deploy：不适用。
