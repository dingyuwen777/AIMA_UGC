---
schema: coding-change/v1
id: CHG-20260904-231800-change-archive-automation
title: 落地 Change 合并后自动归档与多人交付权限模型
level: L3
status: ready_for_review
owner: dingyuwen777
branch: chg/20260904-change-archive-automation
created: 2026-09-04
updated: 2026-09-04
completion_gate: required
depends_on: []
affected_areas:
  - change-governance
  - github-actions
  - delivery-lifecycle
  - requirement-traceability
affected_paths:
  - .agents/skills/coding/assets/CHANGE.template.md
  - .agents/skills/coding/scripts/ready_check.py
  - scripts/quality/archive_change_after_merge.py
  - scripts/quality/check_change_completion.py
  - .github/workflows/change-archive.yml
  - tests/unit/test_change_archive_automation.py
  - tests/unit/test_change_completion.py
  - docs/04_测试与调试说明.md
  - docs/guides/05_多人协作与Change自动归档.md
  - docs/guides/README.md
contracts:
  - AIMA Change Archive Automation Contract
  - AIMA Change Completion Gate Contract
  - AIMA Post-Merge Finalization Contract
data_changes: []
---

# 目标

保留 `changes/active/` / `changes/archive/` 的直观状态视图，同时消除普通功能的第二个归档 PR：Implementation PR 只人工合并一次；merge 后由仓库专用自动化把该 PR 携带的同一 Change ID 从 active 归档到 `archive/YYYY-MM` 并置为 done。Agent/Reviewer 不负责搬目录，只验证归档与后续 Closure 条件。

# 成功标准

- [x] 普通 PR 不能提前归档 Change；开发/Review 阶段 Change 保持 active/ready_for_review。
- [x] merged PR 能触发确定性、幂等且严格 allowlist 的归档自动化。
- [x] 归档失败不会被误报为完成，且可以通过 workflow_dispatch 安全重跑。
- [x] 现有 Requirement/Completion、CI scope 与历史 archive 的职责不被删除或弱化。

# 范围

- 新增 Change archive 脚本与 GitHub Actions workflow。
- 调整项目 Change completion wrapper，禁止普通 PR active→archive，并强制 Ready Change 使用稳定 Acceptance 绑定。
- 同步 AIMA 项目实际调用的 Agent_Skills Change 模板与 Ready validator 契约。
- 增加永久回归与正式开发/交付指南。

# 非目标

- 不让归档 Workflow 做业务 Review、业务测试、自动 merge Implementation PR 或自然语言 AC Closure。
- 不再创建独立 Finalization/Archive PR。
- 不在仓库提交 GitHub App 私钥或个人 Token。
- 本 Change 不直接修改 GitHub Ruleset；需要的 Settings 由仓库 Owner 手工完成。
- 不为了操作流程变化重写未发生架构变化的 Blueprint 正文。

# 必须保持不变

- main 正常业务更新仍需当前 required PR/CI 门禁。
- Change archive 自动化只能修改本次对应 Change 的路径和 lifecycle 字段，不能修改产品代码、Migration、Docs、Workflow 或其他 Change。
- Issue Acceptance Criteria 仍是最终 Requirement Closure Owner；archive/done 不等价于 Issue closed。
- 历史 untouched archive 不做批量迁移。

# 关键决策

- 自动归档由专用 GitHub App identity 直接产生治理 commit；普通 GitHub Actions `GITHUB_TOKEN` 不获得无限 main bypass。
- 自动触发使用 merged PR `closed` event；支持 `workflow_dispatch(pr_number)` 重跑；不监听 push，因此 archive commit 不递归触发自己。
- 专用 App 尚未配置时 Workflow 安全 no-op；平台配置完成后按 merged PR 手工 dispatch 可补归档，不阻塞首次代码落地主分支。
- 归档按 PR changed files 唯一定位 current-schema active Change；0 个为 N/A，>1 个或歧义 fail closed。
- 归档还绑定 merged PR 的 `merge_commit_sha`：该 revision 必须属于当前 main 历史，当前 Active Change 必须与 merged revision 原文一致；幂等 archive 也必须能由同一 merged revision 精确重建，避免多人先后修改同一 Change 时冻结错误版本。
- `status` 只从 `ready_for_review` 变为 `done`，`updated` 按 merge 时间的北京时间日期更新；其他 Change 正文逐字保持。
- AIMA 项目 wrapper 仍复用 installed Agent_Skills validator；本次只同步项目实际依赖的模板/validator 契约，并由 wrapper 显式打开稳定 Acceptance binding，不在项目脚本复制第二套解析规则。
- PR #353 已把 Requirement Traceability / Completion Audit 收敛进 `ci.yml`；本 Change 复用最新 CI Core，不恢复已删除的独立 Completion Workflow。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 普通 PR Change 保持 active/ready_for_review，PR 内 archive 被拒绝 | external:https://github.com/dingyuwen777/AIMA_UGC/issues/354#AC1 | satisfied | `check_change_completion.py` 对 PR `active→archive` 明确 fail closed；`test_current_change_cannot_move_from_active_to_archive_in_pr` 固化行为。 |
| R2 | merged PR 自动归档同一 Change ID并置 done | external:https://github.com/dingyuwen777/AIMA_UGC/issues/354#AC2 | satisfied | `archive_change_after_merge.py` 从 merged PR changed paths 唯一定位 Change，并绑定该 PR `merge_commit_sha` 原文，按北京时间月归档且只冻结 lifecycle；`change-archive.yml` 在 merged PR 后调用。 |
| R3 | 严格 path/content allowlist，越界 fail closed | external:https://github.com/dingyuwen777/AIMA_UGC/issues/354#AC3 | satisfied | helper 的 `_verify_lifecycle_only` 只允许 `status/updated`；Workflow staged diff 只允许本次 source/target 两个 Change 路径后才 commit。 |
| R4 | 幂等与歧义 fail closed | external:https://github.com/dingyuwen777/AIMA_UGC/issues/354#AC4 | satisfied | helper 覆盖已归档精确同源 no-op、active/archive 同时存在失败、多个 Active Change 失败、source/target 均不存在失败；当前 Active 或既有 archive 与 merged revision 内容不一致也 fail closed，避免并发归属猜测。 |
| R5 | 串行、dispatch 重跑、无递归、配置前安全 no-op | external:https://github.com/dingyuwen777/AIMA_UGC/issues/354#AC5 | satisfied | Workflow 使用固定 `change-archive-main` concurrency、`workflow_dispatch(pr_number)`，没有 push trigger；App secrets 缺失时 notice + success no-op。 |
| R6 | implementation main-fresh 与 archive governance fresh 分离，archive 不等价 Closure | external:https://github.com/dingyuwen777/AIMA_UGC/issues/354#AC6 | satisfied | 正式指南明确两类 revision Evidence 与 Closure 边界；archive commit 仍触发现有 main push governance/CI，Implementation merge 的 main-fresh 不被归档动作替代。 |
| R7 | 继续复用 installed Ready validator，新 Change 使用稳定 AC 引用，历史 archive 不迁移 | external:https://github.com/dingyuwen777/AIMA_UGC/issues/354#AC7 | satisfied | AIMA 同步 Agent_Skills 当前 `CHANGE.template.md` / `ready_check.py`；项目 wrapper 动态加载该 validator 并对 Active Ready 显式启用 `require_acceptance_binding`，未复制解析规则；`test_ready_current_change_requires_stable_acceptance_binding` 固化泛化来源失败，legacy untouched archive 仍兼容。 |
| R8 | 正式开发指南同步单 PR + repository archive automation 生命周期 | external:https://github.com/dingyuwen777/AIMA_UGC/issues/354#AC8 | satisfied | 新增 `docs/guides/05_多人协作与Change自动归档.md` 并加入 Guide 导航；按 #353 最新事实把 Requirement/Completion Owner 指向 `.github/workflows/ci.yml`，`docs/04_测试与调试说明.md` 同步 6 个永久 Workflow，正常路径无第二归档 PR。 |
| R9 | 永久测试覆盖归档、幂等、allowlist、workflow 与现有 required responsibilities | external:https://github.com/dingyuwen777/AIMA_UGC/issues/354#AC9 | satisfied | `test_change_archive_automation.py` 覆盖成功归档、精确同源幂等、当前 Active/既有 archive 与 merged revision 不一致的并发归属反例、歧义、窄权限/触发/concurrency/main push 漂移约束；`test_change_completion.py` 保留历史兼容与提前归档拒绝；required responsibilities 不被删除。 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | archive helper、PR transition gate、稳定 AC binding、精确同源幂等、并发归属失败路径永久单元回归已加入 current head。 |
| 接口 / 契约 | required | workflow merged PR/dispatch input、`merge_commit_sha` revision binding、专用 App token、Change path/status contract 与 installed Ready validator acceptance-binding contract 有明确机器实现和回归。 |
| 集成 / 持久化 / 运行依赖 | required | Workflow 在真实 Git checkout 上把 merged revision Source 与当前 main Change 绑定，stage、validate、commit，push 前重新 fetch main 并用 parent==current-main 防二次漂移。 |
| 用户 / 工作流验收 | required | 正式指南覆盖 developer PR → maintainer merge → archive automation → Closure pending。 |
| 跨组件关键路径 | required | merged PR metadata/revision → changed files → helper → Change carrier → installed validator → 当前 `ci.yml` Requirement/Completion 门禁已真实接线。 |
| 外部依赖 / 供应方探测 | not_applicable | 不访问业务 Provider；GitHub App/Ruleset 的平台 Settings 不能由当前仓库代码自证，将在落地后按真实配置验证。 |
| 构建 / 打包 / 运行 | not_applicable | 不修改产品构建、镜像或运行产物。 |
| 文档 / 治理 / 其他 | required | Guide、Workflow、模板/validator、quality scripts 与 latest-main CI responsibility audit 已同步；current-head Actions 作为最终新鲜机器证据。 |

# 完成审计

- [x] upstream_re_read：已重读 #354 最新 AC1–AC9，并在 main 漂移后重读 #353 合并后的 CI Owner 事实。
- [x] change_coverage：R1–R9 一一映射当前 AC，没有把 Change 自身当需求全集。
- [x] reverse_audit：已从普通 PR、merged PR、稳定 AC binding、重复执行、active/archive 歧义、merged revision 内容漂移、越界修改、main push 漂移、App 未配置和 archive failure 反向审计。
- [x] unresolved_cleared：所有 R 均已有当前实现/永久回归或明确平台配置边界；远程 current-head CI 仍由 PR 提供，不伪造未来 Run。

# 任务

- [x] 调查现有 main Ruleset、Change Gate、quality scripts 与 Workflow 事实。
- [x] 增加永久回归覆盖旧模型缺口。
- [x] 实现 archive helper。
- [x] 实现 Change Archive Workflow 与配置前安全 no-op。
- [x] 修改 PR Change gate 禁止提前 archive，并接入稳定 AC binding。
- [x] 同步 AIMA 项目使用的 Agent_Skills Change 模板/validator 契约。
- [x] 同步正式 Guide、永久 Workflow 事实与导航。
- [x] 对齐 #353 合并后的 CI Core，不恢复已删除 Completion Workflow。
- [x] 完成 Requirement Traceability / Completion Audit。
- [ ] PR current-head CI / 独立 Review / guarded merge / main-fresh。

# 验证

## 计划

- targeted：`tests/unit/test_change_archive_automation.py`、`tests/unit/test_change_completion.py`。
- governance：Requirement Traceability and Completion Audit。
- CI responsibility：确认不新增重复业务测试，归档 Workflow 只负责 lifecycle write。

## 新鲜证据

- current branch 已包含脚本、Workflow、项目 gate、稳定 Acceptance validator/template、永久回归与正式 Guide；已按 #353 最新 main 对齐 CI Owner，PR current-head Actions 待最终 head 执行。

# 文档影响

- 新增正式多人协作/Change 自动归档 Guide 并更新 Guide 导航；同步 `docs/04_测试与调试说明.md` 的永久 Workflow 机器事实；Blueprint 长期架构没有变化，不为操作流程重复正文。

# 交付

- Requirement Source：#354
- PR：#355
- GitHub Settings：代码合并后仍需要 Owner 配置专用 GitHub App、`change-archive-main` Environment secrets 与 Ruleset bypass/Restrict Updates。
