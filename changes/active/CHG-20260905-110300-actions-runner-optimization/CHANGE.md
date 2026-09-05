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
  - .github/workflows/tooling.yml
  - .github/workflows/release.yml
  - .github/workflows/fullstack.yml
  - .github/workflows/change-archive.yml
  - tests/unit/test_ci_workflow_structure.py
  - tests/unit/test_actions_runner_optimization.py
  - tests/unit/test_release_workflow.py
contracts:
  - AIMA CI Evidence Preservation Contract
  - AIMA Required Check Identity Contract
  - AIMA Change Archive Trigger Contract
data_changes: []
---

# 目标

在不删除 PostgreSQL、Real Full-stack、Compose Runtime、Windows Tooling、Release 等独立高价值证据的前提下，减少 PR metadata、Draft 迭代、无持久 Change PR 和重复依赖下载造成的 GitHub Actions Runner 消耗。

# 成功标准

- [x] Metadata edit 只重新验证 Requirement Source 等治理事实，并绑定同 SHA 已成功完整证据，不进入产品重路径。
- [x] Draft PR 的昂贵产品/Tooling/Release 证据延后到 Ready，且 required CI gate 保持 fail-closed。
- [x] Change Archive 不再为没有持久 Change 的 merged PR 启动。
- [x] Runtime required `Compose Golden Path` 保持每个 PR/main SHA 存在，未命中风险继续用现有 fast-path，命中风险仍跑真实 Compose。
- [x] Ready/non-draft/main/release 的原独立证明责任和 required check identity 全部保留。
- [x] npm/uv 依赖缓存只复用下载缓存，不复用当前 HEAD 的测试结论或产品产物。

# 范围

- 调整 AIMA CI、Tooling、Release、Full-stack、Change Archive 的事件、Draft fast-path、path scope 与依赖缓存。
- 更新永久回归，锁定 Evidence Preservation Mapping、required check identity 与 Runtime fast-path 守恒。
- 对照 `docs/04_测试与调试说明.md` 当前长期 CI 说明，确认细粒度 event/cache 规则无需复制进长期文档。

# 非目标

- 不删除任何独立测试层或正式 Release 验证。
- 不修改 Runtime Acceptance 的既有 required check/真实 Compose 责任；不使用 path filter 让 `Compose Golden Path` 消失。
- 不改变业务 API、Schema、Migration、数据语义、前端功能或生产部署拓扑。
- 不降低 Ruleset required checks。
- 不用历史 Run 代替当前 HEAD fresh evidence。

# 必须保持不变

- `CI Gate`、`Requirement Traceability and Completion Audit`、`Compose Golden Path` 的 required context 继续存在。
- Ready/non-draft PR 与 main push 仍按真实 changed scope 运行需要的 Unit/Contract/API/Frontend/PostgreSQL/Full-stack/Runtime 证据。
- Runtime 风险仍必须运行真实 Compose；无 Runtime 风险时继续使用当前 scope fast-path，不把 Runtime 迁入较弱的 Unit/Mock。
- Tooling/Release 命中原风险路径且 PR Ready/non-draft 时仍运行原完整证明。
- Draft 轻量路径不得成为可合并的最终证据，Ready 后必须重新触发完整 profile。
- Change Archive 的 `workflow_dispatch(pr_number)`、strict allowlist、App identity 和 direct governance push 语义不变。

# 关键决策

- 优化顺序遵循 event/path filter → changed-scope/fast-path → setup/cache；不以较弱证据替代较强证据。
- Draft CI 通过明确失败的 required gate 保证 Ready 前不能把轻量证据当最终证据；`ready_for_review` 负责重新取得完整证据。Tooling/Release 不是 Ruleset required context，因此 Draft 直接不启动昂贵 Job，Ready event 再恢复。
- Metadata edit 继续实时重验 Requirement Source；只有同一 HEAD 已有 `CI Gate` + `Compose Golden Path` 成功基线才允许 metadata-only run 变绿，防止 PR 文本编辑覆盖失败的完整 CI。
- `Compose Golden Path` 是稳定 required context；本次不加 path filter、不把它并入 CI。无 Runtime 风险的现有 fast-path 已经是低成本且不产生缺失 check 的安全实现。
- Cache 只缓存包管理器下载内容，当前源码、构建产物、数据库状态和测试结果仍由本 SHA 重新生成。
- `docs/04` 当前只维护长期职责与 Runtime fast-path，不复制易漂移的具体 Draft/event/cache 矩阵，因此保持不改比追加第二份细节更符合文档事实源边界。
- 回滚只需恢复 Workflow/测试；无数据 Migration 或运行时迁移。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | edited 仍重验 Requirement Source，且必须绑定同 SHA 完整绿灯，不运行 metadata 无关重路径 | #360 / AC1 | satisfied | `ci.yml` metadata-only path 只运行 Checkout/Classify/Requirement Source/baseline；baseline 必须找到同 SHA 成功 `CI Gate` + `Compose Golden Path`，永久回归锁定。 |
| R2 | Draft 轻量且 fail-closed，Ready/non-draft/main 恢复完整 profile | #360 / AC2 | satisfied | Draft run 33941673565：Requirement Source success 后在 Setup Python 前明确 failure，PostgreSQL/Full-stack skipped；`ready_for_review` 已加入触发。 |
| R3 | Runtime required context/真实 Compose 责任不变，无风险继续现有 fast-path | #360 / AC3 | satisfied | Draft run 33941673465 的 `Compose Golden Path` success，仅执行 Detect + Fast-path；真实 Compose steps skipped；`runtime.yml` 本次未改且永久回归锁定 heavy owner。 |
| R4 | Tooling/Release Draft 跳过昂贵 Job，Ready/non-draft 恢复 | #360 / AC4 | satisfied | Draft Tooling run 33941673446：Linux/Windows jobs 均 skipped；Release run 33941673448：build/publish jobs 均 skipped；两 Workflow 均监听 `ready_for_review`。 |
| R5 | Change Archive 增加 active Change path scope，dispatch 保留 | #360 / AC5 | satisfied | `change-archive.yml` 增加 `changes/active/**` path filter；dispatch/App/allowlist/drift guard 不变；永久回归覆盖。 |
| R6 | 依赖缓存不缓存测试/产品产物 | #360 / AC6 | satisfied | CI/PostgreSQL/Full-stack/Tooling 增加 uv/npm 下载 cache，key 绑定 lock/version；未缓存 `dist`、数据库、`.runtime-dist` 或测试结论，永久回归覆盖。 |
| R7 | 永久回归证明 Evidence Preservation 和 required contexts | #360 / AC7 | satisfied | `test_ci_workflow_structure.py`、`test_actions_runner_optimization.py`、`test_release_workflow.py` 锁定 required identity、Runtime fast-path、Draft/Ready、Archive filter、cache 和 Release/Tooling owner。 |
| R8 | 长期测试文档不复制易漂移事件细节，现有职责说明继续正确 | #360 / AC8 | satisfied | `docs/04` 当前仍准确描述 6 个长期 Owner、Compose 每 PR/main SHA 的 fast-path 和 current-head evidence；新回归显式对照这些长期事实，低层 event/cache 由 Workflow+tests 持有。 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 永久 Workflow 结构回归已加入；Draft Actions 已证明 fail-closed/skipped/Runtime fast-path。 |
| 接口 / 契约 | required | required check names、PR event contract、dispatch contract 未漂移；tests 锁定。 |
| 集成 / 持久化 / 运行依赖 | required | Runtime required context在 Draft current SHA 已成功；Ready 后 Tooling/Release/完整 CI 由真实 Actions 证明。 |
| 用户 / 工作流验收 | required | Draft → Ready → full profile；Draft 已取得真实托管平台证据，Ready current-head 待 Actions Owner 给出。 |
| 跨组件关键路径 | not_applicable | 不改变产品跨组件业务接线；Full-stack Owner 未删除/弱化。 |
| 外部依赖 / 供应方探测 | not_applicable | 不改变 TikHub/LLM 等外部 Provider 事实。 |
| 构建 / 打包 / 运行 | required | Ready 后 Workflow 自身变更必须由完整 CI/Runtime/Tooling/Release dry-run验证。 |
| 文档 / 治理 / 其他 | required | Change/Issue/Workflow/Regression/docs长期职责一致。 |

# 完成审计

- [x] upstream_re_read：已重读 #360 AC1-AC8、当前 Ruleset、Workflow 与 `docs/04` CI 长期职责。
- [x] change_coverage：R1-R8 均有实现、永久回归或 Draft 实际 evidence。
- [x] reverse_audit：已从 Draft/Ready/edited/main/archive/release 反查；PostgreSQL、Full-stack、Runtime、Tooling、Release 独立证据 Owner 未丢失。
- [x] unresolved_cleared：没有 `not_satisfied`；Ready current-head run ID 属于 PR/Actions 新鲜外部证据，不预写未来事实。

# 任务

- [x] 调查当前 Workflow、实际 Run 频率和 Runner 时长。
- [x] 建立 Workflow Responsibility Audit / Evidence Preservation 方案。
- [x] 增加永久回归锁定目标触发和证据责任。
- [x] 实现 Draft/metadata/path/cache 优化；Runtime required fast-path 保持不改。
- [x] 对照正式测试文档，确认长期职责描述继续准确且无需复制低层 event/cache 矩阵。
- [x] 取得 PR Draft fail-closed evidence。
- [x] 完成 Requirement Traceability / Completion Audit，进入 Ready。
- [ ] 取得 Ready current-head fresh Actions evidence 与独立 Review。

# 验证

## Draft Evidence

- PR #361 CI run `33941673565`：Requirement Source success 后在 `Defer full CI while PR is Draft` 明确 failure；Setup Python/产品依赖/Unit/API/Frontend/PostgreSQL/Full-stack 全部未执行。
- Tooling run `33941673446`：Linux/Windows 两个昂贵 Job 均 skipped。
- Release run `33941673448`：Build/replay 与 publish Job 均 skipped。
- Runtime run `33941673465`：`Compose Golden Path` success，仅 Detect + `Fast-path unchanged Runtime`，真实 Compose 重步骤 skipped。

## Ready 计划

- 标记 PR #361 Ready 后，必须取得同一 current HEAD 的完整 CI、Runtime、Tooling 与 Release dry-run fresh evidence；随后再做 metadata `edited` 实测，确认只在同 SHA 已有完整绿灯时 metadata-only 变绿。

# 文档影响

- `docs/04_测试与调试说明.md` 当前长期职责和 Runtime required fast-path 说明继续准确；不复制具体 Draft/event/cache 细节，避免形成第二份易漂移 Workflow 实现说明。

# 交付

- Requirement Source：#360
- PR：#361
- merge：未授权，本任务只交付到 PR Ready
- 发布：不适用
