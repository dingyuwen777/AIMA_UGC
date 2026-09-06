---
schema: coding-change/v1
id: CHG-20260906-183500-ci-test-impact-optimization
title: 收敛 CI/Test Impact 与 Actions 重复执行
level: L3
status: ready_for_review
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
  - scripts/quality/check_agent_governance.py
  - tests/unit/test_actions_runner_optimization.py
  - tests/unit/test_ci_scope.py
  - tests/unit/test_ci_test_impact_optimization.py
  - tests/unit/test_ci_workflow_structure.py
  - tests/unit/test_agent_governance.py
  - docs/blueprint/06_开发约束与分阶段实施.md
contracts: []
data_changes: []
---

# 背景与当前事实

Issue #370 要求在不降低仓库整体准入质量的前提下减少 GitHub Actions 次数和 Runner 时间。仓库原本已经有 changed-scope classifier、CI Gate、独立 Runtime/Release/Tooling/Full-stack Workflow 和 repository-native Change Archive，但仍存在重复或过宽执行：

- 受控 Change Archive 已执行 completion gate 与 exact two-path allowlist，机械归档 commit 仍会再次触发 main CI/Runtime；
- 纯文档治理只要同时修改文档质量脚本/专属测试，就可能因未知路径 fail-closed 为产品 full；
- Release dry-run 的 PR paths 包含纯部署文档/Roadmap；
- PostgreSQL Integration 固定安装与该 Job 证明责任无关的 CJK 字体；
- Draft PR 会进入 Job 后主动失败；
- Persistence 变化只能用单一 `postgres_required` 表达，无法选择最小充分 suite。

本 Change 只改变 CI/Test Impact/Actions 治理与对应测试、长期开发文档，不修改产品业务行为、HTTP Contract、Schema/Migration、依赖版本、生产数据或生产环境。

# 目标

1. 让文档/治理/repository-quality 变化只运行直接证明该风险的最小充分 Evidence。
2. 让 PostgreSQL Integration 能按受影响边界选择 suite，共享/未知/迁移风险继续保守扩大。
3. 删除 Change Archive、Release、字体准备和 Draft 处理中的无证明价值重复执行。
4. 保留 selector/Workflow 自身变化与未知路径的 `full` fail-closed 不变量。
5. 保持现有 required check 身份和 main 准入拓扑可持续满足，不通过旁路修改 Ruleset 获得绿色。

# 范围与非目标

## Included

- `scripts/quality/classify_ci_scope.py` 的 Evidence outputs、repository-quality 与 PostgreSQL suite selector；
- `.github/workflows/ci.yml`、`change-archive.yml`、`release.yml`、`runtime.yml` 的风险驱动执行与重复工作收敛；
- `check_agent_governance.py` 对 `python` / `python3` 两种真实 Change gate 执行入口的兼容识别；
- selector/workflow/项目治理自动化回归；
- `docs/blueprint/06_开发约束与分阶段实施.md` 中长期 CI/Test Impact 与归档闭环说明。

## Excluded

- 删除长期回归测试资产；
- 产品前后端业务功能；
- HTTP/Pydantic/OpenAPI Contract；
- Schema/Migration 内容；
- 依赖/Runtime 版本升级；
- 正式 Release/Deploy/生产写入；
- 通过放宽 unknown/CI-self/Workflow fail-closed 获得绿色；
- 为本任务重构所有独立 Workflow 为 `workflow_call` 或改变 Ruleset required-check 拓扑。

# 不变量

- selector 自身、CI Workflow、selector/Workflow 结构回归发生变化时必须 `full`；
- 未识别机器路径必须 `full`；
- Contract/shared/cross-component 风险只能单调扩大，不允许因为优化成本降级；
- Migration 源码、公共 DB 基础设施或无法唯一映射的 persistence 风险必须扩大到完整 PostgreSQL 证据；
- Change Archive 的 `[skip ci]` 只允许 repository-native Archivist 在当前 main、真实 merged PR、completion gate 与 exact active→archive two-path allowlist 全部成立后使用；普通 commit/PR 不获得该能力；
- Required status check 不得因 path-filter 缺失而长期 Pending；`Compose Golden Path` 保持稳定 check 身份并用 Runtime risk fast-path 控制成本；
- AIMA 顶层 Change gate 必须真实执行；项目治理静态检查可识别 `python` 或 `python3` 入口，但不接受注释、占位或 generic ready-check 旁路；
- 正式手工 Release 不因 PR 并发优化而自动取消。

# 方案比较

- 方案 A（采用）：保留现有稳定 CI Gate/required-check 身份与 fail-closed classifier，增加 repository-quality / targeted PostgreSQL 等 Evidence 轴，并删除已被前置精确门禁证明的重复工作。改动增量小，可通过 selector invariant 与 Workflow 静态回归验证。
- 方案 B（暂不采用）：立即把 Runtime/Tooling/Release 全部改成 `workflow_call` 并由单一 CI orchestrator 统一调用，同时调整 Ruleset。长期结构更整齐，但会同时改变 required-check/Workflow 拓扑，当前任务没有必要承担该额外平台风险。
- 方案 C（不采用）：直接删除慢测试或扩大 path-ignore。节省分钟最多，但无法证明不会漏测，违反本任务“不降低准入质量”的前提。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 纯 docs/README 不运行产品技术栈 CI/Release | #370 / AC1 | satisfied | `classify_ci_scope.py` 保留 `docs_only/governance_only` 白名单轻量 profile；Release PR paths 已移除部署说明/Roadmap；`test_ci_scope.py` 与 `test_ci_test_impact_optimization.py` 锁定边界 |
| R2 | 文档/治理质量脚本及其专属测试使用 repository-quality | #370 / AC2 | satisfied | 新增 `repository_quality_required`；只有明确白名单的治理/文档质量脚本及其专属测试进入该 profile，并运行锁定 Python + Ruff + targeted regression；`check_architecture.py`、`check_table_ownership.py` 等非白名单质量脚本按未知机器路径 fail-closed 到 `full` |
| R3 | 受控 Change Archive 不再触发后续业务 CI/Runtime | #370 / AC3 | satisfied | `change-archive.yml` 在 completion gate、exact two-path allowlist、当前 main 防漂移之后才提交带 `[skip ci]` 的机械 archive commit；静态回归验证执行顺序与 allowlist |
| R4 | Release dry-run 只由 Release 机器实现变化触发 | #370 / AC4 | satisfied | `release.yml` PR paths 只保留 Release Workflow、Dockerfile、Compose、生产 env 示例和两项直接回归；PR stale run 可取消，手工 Release 不取消 |
| R5 | CJK 字体只在报告渲染需要时安装 | #370 / AC5 | satisfied | 主 CI 使用 `report_font_required`；PostgreSQL Integration 删除 CJK 安装；静态回归锁定该条件 |
| R6 | Draft PR 不再主动失败消耗 Runner | #370 / AC6 | satisfied | CI `quality-core/ci-gate` 与 Runtime `compose-golden-path` 在 Job 分配前按 Draft 状态跳过，旧主动 `exit 1` 步骤已删除；Release build-verify 继续使用 Job-level Draft skip；`test_actions_runner_optimization.py`、`test_ci_workflow_structure.py` 同步锁定该正式语义 |
| R7 | Persistence 可选择最小充分 PostgreSQL suite | #370 / AC7 | satisfied | 新增 `postgres_suites`；collection/content/ingestion/jobs/system 与 integration suite 可按边界选择，`verify_migration_compatibility.py` 精确选择 `migration`，Migration 源码/共享/未知 persistence 仍升级为 `all` |
| R8 | 技术栈执行保持相关性，shared/unknown 单调扩大 | #370 / AC8 | satisfied | selector 按 backend/frontend/contract/persistence/cross-component 合并 Evidence；CI-self、Workflow、Migration、依赖、Compose/Docker、共享或未知机器路径直接 `full` |
| R9 | 自动化测试锁定关键 selector/workflow/治理不变量 | #370 / AC9 | satisfied | `test_ci_scope.py`、`test_ci_test_impact_optimization.py`、`test_actions_runner_optimization.py`、`test_ci_workflow_structure.py` 覆盖 docs/governance/repository-quality 白名单、非白名单 quality fail-closed、CI-self、unknown、PostgreSQL suite/migration verifier、font、Draft、Release、Archive 与 Workflow 结构；`test_agent_governance.py` 锁定真实 `python3` Change gate 仍被 GOV007 识别 |

AC10 是 current-head CI、L3 Deep Review、guarded merge、implementation main-fresh、repository-native Change Archive、Issue closure 与分支清理的交付/关闭门禁，由 PR、Commit、Actions、Review、Archive 和 Issue 状态持有，不伪造为 Ready 前已经完成。

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | selector、Workflow 与治理静态回归证明每类 changed scope 选择正确 Evidence；最终 current-head full CI 仍需实际执行 |
| 接口 / Contract | not_applicable | 不修改产品 Contract；但本 PR 修改 CI-self，最终 full profile 必须重新执行 generated Contract/client 漂移检查 |
| 集成 / Persistence / Runtime Dependency | required | 修改 PostgreSQL suite selector，最终 full CI 必须以 `postgres_suites=all` 运行完整 PostgreSQL Integration；`runtime.yml` 修改必须取得 fresh Compose Golden Path |
| 用户 / Workflow Acceptance | not_applicable | 不修改产品用户工作流；Draft/Release/Archive 属于研发治理 Workflow，由静态回归与实际 Actions 验证 |
| 跨组件 Golden Path | required | 本 Change 修改 CI selector/Workflow，自身必须 `full`，Real Full-stack Golden Path 用来证明 selector 没有错误跳过现有关键实链 |
| External Dependency / Provider Probe | not_applicable | 不改变 Provider 外部事实，不需要真实付费 Probe |
| Build / Package / Runtime | required | 最终 current-head full CI、Runtime Acceptance、Release dry-run 必须新鲜通过；不执行正式 Release/Deploy |
| Docs / Governance / Other | required | Requirement Source、Change completion、AIMA governance wiring、Secret/docs、CI selector/workflow regression 与长期 Blueprint 同步均需 current-head 证据 |

# 实施状态

- [x] 恢复 canonical 通用研发/测试/Review/交付规则与 AIMA 当前 AGENTS/Blueprint/CI/Ruleset 事实。
- [x] 搜索重复事项并创建 Issue #370。
- [x] 创建任务分支与本 L3 Active Change。
- [x] 实现 selector / repository-quality / CI / Archive / Release / Draft / PostgreSQL suite / report-font 优化。
- [x] 补 selector/workflow 自动化回归并同步长期 CI/Archive 文档。
- [x] 将任务分支以非强制 merge commit 同步到当前 main `e331d56884838d9c8a275c436c400b4c6afc9e7f`，没有重写共享历史。
- [x] 清理所有一次性 Workflow/脚本施工资产，最终 PR 只保留长期实现、测试、文档和 Change。
- [x] L3 静态 Review 已在最终动态取证前反向发现并修复两处降级空洞：`scripts/quality/**` 过宽白名单、Migration compatibility verifier suite 选择错误。
- [x] Ready 动态门禁进一步发现并修复 GOV007：真实 `python3 check_change_completion.py` 被治理检查器旧的单一字符串规则误判为未接线；现已兼容 `python`/`python3` 并补回归，不降低 Change gate 要求。
- [x] current-head full CI 进一步发现并修复两类测试治理漂移：Workflow 回归对未锁定 PyYAML 的非必要依赖，以及 `test_ci_workflow_structure.py` 仍锁定旧 Draft 主动失败语义；同时将该 Workflow 结构回归本身纳入 CI-self `full` 白名单。
- [ ] 完成最终 PR current-head full CI、Runtime Acceptance、Release dry-run 与最终 L3 Deep Review。
- [ ] guarded merge、implementation main-fresh、repository-native Change Archive、Issue closure、分支清理。

# Completion Audit

- [x] upstream_re_read：重新读取 Issue #370、当前 main、AIMA `AGENTS.md` / Blueprint 06、canonical Agent_Skills Coding/Testing/Review/Delivery 规则，并把 main 在任务期间的治理升级合入任务分支。
- [x] change_coverage：从 AC1–AC9 逐项回查 selector、四个永久 Workflow、治理 checker、所有相关 Workflow/selector 回归测试和长期文档；AC10 明确保留为交付门禁，没有把 Actions 绿色伪装成施工事实。
- [x] reverse_audit：从 selector/Workflow 所有降级路径反向检查证明责任；先修复 selector 回归自身未纳入 CI-self、`docs_navigation/issue_acceptance` 测试未归 repository-quality、长期文档仍要求 archive revision 重复 CI；Ready 后继续发现并修复“整个 `scripts/quality/**` 被错误视为轻量”和 `verify_migration_compatibility.py` 只选 database、不执行 migration verifier 两个空洞；动态 GOV007 又证明真实 Change gate 入口的静态识别需兼容 `python3`；后续 full CI 再暴露 `test_ci_workflow_structure.py` 仍锁定旧 Draft 主动失败且自身未纳入 CI-self，现已同步为 Job-level skip 语义并加入 CI-self fail-closed 白名单。最终只有显式治理/文档质量白名单可降级，CI/Workflow 结构回归、非白名单 quality、共享/未知路径均 fail-closed，顶层 Change gate 仍必须真实执行。
- [x] unresolved_cleared：临时 Patcher/文档同步/治理兼容 Workflow 与一次性脚本已全部删除；Workflow 静态回归不新增 PyYAML 等非必要依赖；Release/Runtime 使用正式 GitHub 写路径落地；无未决 Contract/Schema/数据/依赖/生产变化。剩余事项仅为最终 HEAD 的动态 CI/Review/merge/closure 证据。

`ready_for_review` 表示施工范围、需求覆盖、长期文档和完成定义已经闭环；下一步必须以 PR 最新 HEAD 取得新的 full CI、Runtime、Release dry-run 与最终 L3 Review，才能进入 merge。

# 兼容、部署与回滚

- 兼容：产品 API、Schema、数据、依赖和运行时业务语义不变；只改变 CI/Test Impact/Actions 的证明责任选择、AIMA 治理静态识别与研发治理文档。
- 部署：无需生产部署；本任务不触发正式 Release、生产数据写入或生产环境变更。
- 回滚：revert 本 Implementation PR 即恢复原 Workflow/classifier/governance checker；无数据库 Migration、数据或生产环境回滚要求。