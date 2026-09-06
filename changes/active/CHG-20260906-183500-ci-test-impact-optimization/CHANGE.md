---
schema: coding-change/v1
id: CHG-20260906-183500-ci-test-impact-optimization
title: 收敛 CI/Test Impact 与 Actions 重复执行
level: L3
status: in_progress
owner: dingyuwen777
branch: ci/370-test-impact-optimization
created: 2026-09-06
updated: 2026-09-06
completion_gate: required
depends_on: []
affected_areas:
  - ci
  - quality
  - tests
  - docs
affected_paths:
  - .github/workflows/
  - scripts/quality/classify_ci_scope.py
  - tests/unit/test_ci_scope.py
  - tests/unit/test_actions_runner_optimization.py
  - docs/blueprint/06_开发约束与分阶段实施.md
contracts: []
data_changes: []
---

# 背景与当前事实

Issue #370 要求在不降低仓库整体准入质量的前提下减少 GitHub Actions 次数和 Runner 时间。当前仓库已经有 changed-scope classifier、CI Gate、独立 Runtime/Release/Tooling/Full-stack Workflow 和 repository-native Change Archive，但仍存在重复或过宽执行：

- 受控 Change Archive 已执行 completion gate 与 exact two-path allowlist，归档 commit 仍会再次触发 main CI/Runtime；
- 纯文档治理只要同时修改文档质量脚本/专属测试，就可能因未知路径 fail-closed 为产品 full；
- Release dry-run 的 PR paths 包含纯部署文档/Roadmap；
- PostgreSQL Integration 固定安装与该 Job 证明责任无关的 CJK 字体；
- Draft PR 会进入 Job 后主动失败；
- Persistence 变化目前只能用单一 `postgres_required` 表达，无法选择最小充分 suite。

本 Change 只改变 CI/Test Impact/Actions 治理与对应测试、文档，不修改产品业务行为、HTTP Contract、Schema/Migration、依赖版本或生产环境。

# 目标

1. 让文档/治理/repository-quality 变化只运行直接证明该风险的最小充分 Evidence。
2. 让 PostgreSQL Integration 能按受影响边界选择 suite，共享/未知/迁移风险继续保守扩大。
3. 删除 Change Archive、Release、字体准备和 Draft 处理中的无证明价值重复执行。
4. 保留 selector/Workflow 自身变化与未知路径的 `full` fail-closed 不变量。
5. 保持现有 main required checks 可持续满足；没有安全托管平台写能力时不通过旁路修改 Ruleset。

# 范围与非目标

## Included

- `scripts/quality/classify_ci_scope.py` 的 Evidence outputs 与 PostgreSQL suite selector；
- `.github/workflows/ci.yml`、`change-archive.yml`、`release.yml` 与必要 Runtime/Draft 调整；
- selector/workflow 自动化回归；
- `docs/blueprint/06_开发约束与分阶段实施.md` 中 AIMA CI profile/current evidence 说明。

## Excluded

- 删除长期回归测试资产；
- 产品前后端业务功能；
- HTTP/Pydantic/OpenAPI Contract；
- Schema/Migration 内容；
- 依赖/Runtime 版本升级；
- 正式 Release/Deploy/生产写入；
- 通过放宽 unknown/CI-self/Workflow fail-closed 获得绿色。

# 不变量

- selector 自身、CI Workflow/测试 selector 回归发生变化时必须 `full`；
- 未识别机器路径必须 `full`；
- Contract/shared/cross-component 风险只能单调扩大，不允许因为优化成本降级；
- Migration、公共 DB 基础设施或无法唯一映射的 persistence 风险必须扩大到完整 PostgreSQL 证据；
- Change Archive 跳过后续 CI 只允许 repository-native Archivist 在本次 Workflow 已验证 exact allowlist 后使用；普通 commit/PR 不获得该能力；
- Required status check 不得因为 path-filter 缺失而长期 Pending；若平台 Ruleset 无安全写通路，保持现有 `Compose Golden Path` required check 和兼容 fast-path。

# 方案比较

- 方案 A（采用）：保留现有单一 CI Gate 与 fail-closed classifier，增加 repository-quality / targeted PostgreSQL 等 Evidence 轴，并删除已被前置精确门禁证明的重复工作。改动增量小，可通过 selector invariant 测试验证。
- 方案 B（暂不采用）：立即把 Runtime/Tooling/Release 全部改成 `workflow_call` 并由单一 CI orchestrator 统一调用，同时调整 Ruleset。长期结构更整齐，但当前 GitHub 连接未暴露 Ruleset 写动作，贸然删除现有 required check 会产生 PR Pending 风险。
- 方案 C（不采用）：直接删除慢测试或扩大 path-ignore。节省分钟最多，但无法证明不会漏测，违反本任务“不降低准入质量”的前提。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 纯 docs/README 不运行产品技术栈 CI/Release | #370 / AC1 | not_satisfied | 待实现与 selector/workflow 回归 |
| R2 | 文档/治理质量脚本及其专属测试使用 repository-quality | #370 / AC2 | not_satisfied | 待实现与 targeted quality tests |
| R3 | 受控 Change Archive 不再触发后续业务 CI/Runtime | #370 / AC3 | not_satisfied | 待更新 archive workflow 与静态回归 |
| R4 | Release dry-run 只由 Release 机器实现变化触发 | #370 / AC4 | not_satisfied | 待收敛 paths 与回归 |
| R5 | CJK 字体只在报告渲染需要时安装 | #370 / AC5 | not_satisfied | 待更新 CI 条件 |
| R6 | Draft PR 不再主动失败消耗 Runner | #370 / AC6 | not_satisfied | 待更新 CI/Runtime 触发/Job 条件 |
| R7 | Persistence 可选择最小充分 PostgreSQL suite | #370 / AC7 | not_satisfied | 待实现 postgres_suites 与 fail-closed mapping |
| R8 | 技术栈执行保持相关性，shared/unknown 单调扩大 | #370 / AC8 | not_satisfied | 待 selector invariant 回归 |
| R9 | 自动化测试锁定关键 selector/workflow 不变量 | #370 / AC9 | not_satisfied | 待补回归 |

AC10 是 current-head CI、L3 Review、merge、main-fresh、自动归档与 Issue closure 的交付门禁，不伪造为实现阶段已完成。

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | selector 与 workflow 静态回归，证明每类 changed scope 选择正确 Evidence |
| 接口 / Contract | not_applicable | 不修改产品 Contract；但本 PR 因 CI-self 变化仍由旧/current full profile 检查 generated Contract/client 漂移 |
| 集成 / Persistence / Runtime Dependency | required | 修改 PostgreSQL suite selector，必须由 full CI/current PostgreSQL Integration 验证 selector 自身 fail-closed；Runtime workflow 如修改需 fresh Runtime evidence |
| 用户 / Workflow Acceptance | not_applicable | 不修改产品用户工作流 |
| 跨组件 Golden Path | required | 本 Change 修改 CI selector/Workflow，自身必须 full，现有 Real Full-stack Golden Path 作为防误跳过证据 |
| External Dependency / Provider Probe | not_applicable | 不改变 Provider 外部事实，不需要真实付费 Probe |
| Build / Package / Runtime | required | 当前 full CI、Runtime/Release dry-run（相关 workflow 变更时）必须新鲜通过 |
| Docs / Governance / Other | required | Requirement Source、Change completion、Secret/docs、CI workflow static/invariant tests |

# 实施状态

- [x] 恢复 canonical 通用研发/测试/Review/交付规则与 AIMA 当前 AGENTS/Blueprint/CI/Ruleset 事实。
- [x] 搜索重复事项并创建 Issue #370。
- [x] 创建任务分支与本 L3 Active Change。
- [ ] 实现 selector / CI / Archive / Release / Draft / PostgreSQL suite 优化。
- [ ] 补自动化回归并同步长期 CI 文档。
- [ ] 完成 current-head full CI、Runtime/Release 相关验证与 L3 Deep Review。
- [ ] guarded merge、main-fresh、repository-native Change Archive、Issue closure、分支清理。

# Completion Audit

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# 兼容、部署与回滚

- 兼容：产品 API、Schema、数据、依赖和运行时业务语义不变；仅 CI/Test Impact 与 Actions 执行范围改变。
- 部署：无需生产部署；本任务不触发正式 Release。
- 回滚：revert 本 Implementation PR 即恢复原 Workflow/classifier；无数据库或生产数据回滚要求。