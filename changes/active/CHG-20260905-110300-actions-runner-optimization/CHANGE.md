---
schema: coding-change/v1
id: CHG-20260905-110300-actions-runner-optimization
title: 收敛 Actions 触发与风险分层以降低 Runner 消耗
level: L3
status: ready_for_review
owner: dingyuwen777
branch: chg/20260905-actions-runner-optimization
created: 2026-09-05
updated: 2026-09-05
completion_gate: required
depends_on: []
affected_areas:
  - github-actions
  - ci-governance
  - runner-cost
  - change-lifecycle
affected_paths:
  - .github/workflows/ci.yml
  - .github/workflows/runtime.yml
  - .github/workflows/tooling.yml
  - .github/workflows/release.yml
  - .github/workflows/fullstack.yml
  - .github/workflows/change-archive.yml
  - tests/unit/test_ci_workflow_structure.py
  - tests/unit/test_actions_runner_optimization.py
  - tests/unit/test_release_workflow.py
  - docs/04_测试与调试说明.md
contracts:
  - AIMA CI Evidence Preservation Contract
  - AIMA Required Check Identity Contract
  - AIMA Change Archive Trigger Contract
data_changes: []
---

# 目标

在不删除 PostgreSQL、Real Full-stack、Compose Runtime、Windows Tooling、Release 等独立高价值证据的前提下，减少 PR metadata、Draft 迭代、无持久 Change PR 和重复依赖下载造成的 GitHub Actions Runner 消耗。

# 成功标准

- [x] Metadata edit 只重新验证 Requirement Source，并绑定同 SHA 已成功完整证据，不进入产品重路径。
- [x] Draft PR 的昂贵产品 CI、Runtime、Tooling、Release 证据延后到 Ready，required CI/Runtime gate 保持 fail-closed。
- [x] Change Archive 不再为没有持久 Change 的 merged PR 启动。
- [x] Ready/non-draft/main/release 的原独立证明责任和 required check identity 全部保留。
- [x] npm/uv 依赖缓存只复用下载缓存，不复用当前 HEAD 的测试结论或产品产物。

# 范围

- 调整 AIMA CI、Runtime、Tooling、Release、Full-stack、Change Archive 的事件、Draft fast-path、path scope 与依赖缓存。
- 更新永久回归，锁定 Evidence Preservation Mapping、required check identity、Draft→Ready 与 Runtime 证明责任守恒。
- 同步 `docs/04_测试与调试说明.md` 的长期 Runner 优化边界，不复制易漂移的低层 Workflow 实现细节。

# 非目标

- 不删除任何独立测试层或正式 Release 验证。
- 不改变 Runtime 风险判定后的真实 Compose 证明内容，也不使用 path filter 让 `Compose Golden Path` required context 消失。
- 不改变业务 API、Schema、Migration、数据语义、前端功能或生产部署拓扑。
- 不降低 Ruleset required checks。
- 不用历史 Run 代替当前 HEAD fresh evidence。

# 必须保持不变

- `CI Gate`、`Requirement Traceability and Completion Audit`、`Compose Golden Path` 的 required context 继续存在。
- Ready/non-draft PR 与 main push 仍按真实 changed scope 运行需要的 Unit/Contract/API/Frontend/PostgreSQL/Full-stack/Runtime 证据。
- Draft 的 CI 和 Runtime 只能 fail-closed，不能产生可被 merge 使用的假绿色；Ready 后必须重新触发完整 profile。
- Runtime 风险在 Ready/main 仍必须运行真实 Compose；无 Runtime 风险时继续使用既有可解释 fast-path。
- Tooling/Release 命中原风险路径且 PR Ready/non-draft 时仍运行原完整证明。
- Change Archive 的 `workflow_dispatch(pr_number)`、strict allowlist、App identity 和 direct governance push 语义不变。

# 关键决策

- 优化顺序遵循 event/path filter → changed-scope/fast-path → setup/cache；不以较弱证据替代较强证据。
- Draft CI 与 Runtime 都在昂贵 setup/Checkout/Compose 前明确失败；`ready_for_review` 事件重新取得完整证据。Tooling/Release 不是 Ruleset required context，因此 Draft 直接不启动昂贵 Job，Ready event 再恢复。
- Metadata edit 继续实时重验 Requirement Source；只有同一 HEAD 已有 `CI Gate` + `Compose Golden Path` 成功基线才允许 metadata-only run 变绿，防止 PR 文本编辑覆盖失败的完整 CI。
- `Compose Golden Path` 的 Runtime risk classifier 与真实 Compose 验证正文保持原 Owner；本次只把 Draft 的昂贵运行延后到 Ready。
- Cache 只缓存包管理器下载内容，当前源码、构建产物、数据库状态和测试结果仍由本 SHA 重新生成。
- `docs/04` 只记录长期可维护边界：Draft/Ready、metadata 同 SHA 基线、Runtime required fast-path、Tooling/Release 延后、Archive path scope、dependency cache 与 current-head evidence；具体 YAML 条件仍由 Workflow + 回归持有。
- 回滚只需恢复 Workflow/测试/文档；无数据 Migration 或运行时迁移。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | edited 仍重验 Requirement Source，且必须绑定同 SHA 完整绿灯，不运行 metadata 无关重路径 | #360 / AC1 | satisfied | `ci.yml` metadata-only path 只运行 Checkout/Classify/Requirement Source/baseline；baseline 必须找到同 SHA 成功 `CI Gate` + `Compose Golden Path`，永久回归锁定。 |
| R2 | Draft CI 轻量且 fail-closed，Ready/non-draft/main 恢复完整 profile | #360 / AC2 | satisfied | `ci.yml` 在 Requirement Source 后、Python/Node/产品依赖前失败；`ready_for_review` 重新触发；永久回归锁定。 |
| R3 | Draft Runtime 在 Checkout/Compose 前 fail-closed，Ready/main 恢复既有 Runtime 风险证据 | #360 / AC3 | satisfied | `runtime.yml` 增加 Draft early-fail 与 `ready_for_review`；Runtime risk classifier、无风险 fast-path、真实 Compose 验证正文未弱化；永久回归覆盖。 |
| R4 | Tooling/Release Draft 跳过昂贵 Job，Ready/non-draft 恢复 | #360 / AC4 | satisfied | Tooling Linux/Windows 与 Release build-verify 均以 Draft 状态为条件，且监听 `ready_for_review`；原完整步骤未删除。 |
| R5 | Change Archive 增加 active Change path scope，dispatch 保留 | #360 / AC5 | satisfied | `change-archive.yml` 增加 `changes/active/**` path filter；dispatch/App/allowlist/drift guard 不变；永久回归覆盖。 |
| R6 | 依赖缓存不缓存测试/产品产物 | #360 / AC6 | satisfied | CI/PostgreSQL/Full-stack/Tooling 增加 uv/npm 下载 cache，key 绑定 lock/version；未缓存 `dist`、数据库、`.runtime-dist` 或测试结论，永久回归覆盖。 |
| R7 | 永久回归证明 Evidence Preservation 和 required contexts | #360 / AC7 | satisfied | `test_ci_workflow_structure.py`、`test_actions_runner_optimization.py`、`test_release_workflow.py` 锁定 required identity、Runtime Draft/Ready、Archive filter、cache 和 Release/Tooling Owner。 |
| R8 | 正式测试文档同步长期 Runner 优化边界 | #360 / AC8 | satisfied | `docs/04_测试与调试说明.md` 已同步 Draft/Ready、metadata baseline、Runtime fast-path、Tooling/Release、Archive filter、cache 与 current-head 证据边界，并由新回归反向校验。 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Workflow 结构、Draft/Ready、Runtime early-fail、Archive path filter 与 cache 永久回归。 |
| 接口 / 契约 | required | required check names、PR event contract、dispatch contract 不漂移。 |
| 集成 / 持久化 / 运行依赖 | required | Ready 后完整 CI/Runtime/Tooling/Release 由 GitHub Actions 对 current HEAD 证明。 |
| 用户 / 工作流验收 | required | Draft → Ready → full profile；Draft/Ready 托管平台行为分别取证。 |
| 跨组件关键路径 | not_applicable | 不改变产品跨组件业务接线；Full-stack Owner 未删除/弱化。 |
| 外部依赖 / 供应方探测 | not_applicable | 不改变 TikHub/LLM 等外部 Provider 事实。 |
| 构建 / 打包 / 运行 | required | Workflow 自身变更需由完整 CI/Runtime/Tooling/Release dry-run 验证。 |
| 文档 / 治理 / 其他 | required | Change/Issue/Workflow/Regression/docs 长期职责一致。 |

# 完成审计

- [x] upstream_re_read：已重读 #360 AC1-AC8、当前 Ruleset、Workflow 与 `docs/04` CI 长期职责。
- [x] change_coverage：R1-R8 均有实现与永久回归覆盖。
- [x] reverse_audit：已从 Draft/Ready/edited/main/archive/release 反查；PostgreSQL、Full-stack、Runtime、Tooling、Release 独立证据 Owner 未丢失。
- [x] unresolved_cleared：没有 `not_satisfied`；PR/Actions 的 current-head Run 由平台 Owner 持有，不写入 Change 伪造未来事实。

# 任务

- [x] 调查当前 Workflow、实际 Run 频率和 Runner 时长。
- [x] 建立 Workflow Responsibility Audit / Evidence Preservation 方案。
- [x] 增加永久回归锁定目标触发和证据责任。
- [x] 实现 Draft/metadata/path/cache 优化，包括 Runtime Draft early-fail。
- [x] 同步正式测试文档的长期 Runner 优化边界。
- [x] 完成 Requirement Traceability / Completion Audit，达到 ready_for_review。
- [ ] 取得最终 Draft fail-closed、Ready current-head、metadata-only fresh Actions evidence 与独立 Review。

# 验证

## 计划

- Draft：最终实现已验证 CI/Runtime early-fail，Tooling/Release heavy jobs skipped。
- Ready：最终 HEAD 必须取得完整 CI、Runtime、Tooling 与 Release dry-run fresh evidence。
- Metadata：完整 Ready evidence 成功后编辑 PR body，确认 metadata-only CI 在同 SHA 基线绿时成功且不进入产品重路径。

# 文档影响

- `docs/04_测试与调试说明.md` 已同步长期 Runner 优化边界；具体 YAML 事件条件仍以 Workflow + 永久回归为机器事实源。

# 交付

- Requirement Source：#360
- PR：#361
- merge：未授权，本任务只交付到 PR Ready
- 发布：不适用
