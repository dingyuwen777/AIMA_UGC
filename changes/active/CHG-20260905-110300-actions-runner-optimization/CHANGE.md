---
schema: coding-change/v1
id: CHG-20260905-110300-actions-runner-optimization
title: 收敛 Actions 触发与风险分层以降低 Runner 消耗
level: L3
status: proposed
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
  - tests/unit/test_change_archive_automation.py
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

- [ ] Metadata edit 只重新验证 Requirement Source 等治理事实，不进入产品重路径。
- [ ] Draft PR 的昂贵产品/Runtime/Tooling/Release 证据延后到 Ready，且 required gate 保持 fail-closed。
- [ ] Change Archive 不再为没有持久 Change 的 merged PR 启动。
- [ ] Ready/non-draft/main/release 的原独立证明责任和 required check identity 全部保留。
- [ ] npm/依赖缓存只复用下载缓存，不复用当前 HEAD 的测试结论或产品产物。

# 范围

- 调整 AIMA 永久 GitHub Actions 的事件、Draft fast-path、path scope 与依赖缓存。
- 更新永久回归，锁定 Evidence Preservation Mapping 和 required check identity。
- 同步测试/调试文档中的当前 CI 运行事实。

# 非目标

- 不删除任何独立测试层或正式 Release 验证。
- 不改变业务 API、Schema、Migration、数据语义、前端功能或生产部署拓扑。
- 不降低 Ruleset required checks。
- 不用历史 Run 代替当前 HEAD fresh evidence。

# 必须保持不变

- `CI Gate`、`Requirement Traceability and Completion Audit`、`Compose Golden Path` 的 required context 继续存在。
- Ready/non-draft PR 与 main push 仍按真实 changed scope 运行需要的 Unit/Contract/API/Frontend/PostgreSQL/Full-stack/Runtime 证据。
- Runtime 风险仍必须运行真实 Compose；Tooling/Release 命中原风险路径时仍运行原完整证明。
- Draft 轻量路径不得成为可合并的最终证据，Ready 后必须重新触发完整 profile。
- Change Archive 的 `workflow_dispatch(pr_number)`、strict allowlist、App identity 和 direct governance push 语义不变。

# 关键决策

- 优化顺序遵循 event/path filter → changed-scope/fast-path → setup/cache；不以较弱证据替代较强证据。
- Draft 阶段通过明确失败/阻塞的 required gate 保证 Ready 前不能把轻量证据当最终证据；`ready_for_review` 负责重新取得完整证据。
- Metadata edit 继续实时重验 Requirement Source，但跳过与 PR 文本变化无关的产品/文档全仓扫描。
- Cache 只缓存包管理器下载内容，当前源码、构建产物、数据库状态和测试结果仍由本 SHA 重新生成。
- 回滚只需恢复 Workflow/测试/文档；无数据 Migration 或运行时迁移。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | edited 仍重验 Requirement Source，但不运行 metadata 无关重路径 | #360 / AC1 | not_satisfied | 尚未实现 |
| R2 | Draft 轻量且 fail-closed，Ready/non-draft/main 恢复完整 profile | #360 / AC2 | not_satisfied | 尚未实现 |
| R3 | Draft Runtime 不跑真实 Compose，Ready/main 风险命中仍跑 | #360 / AC3 | not_satisfied | 尚未实现 |
| R4 | Tooling/Release Draft 跳过昂贵 Job，Ready/non-draft 恢复 | #360 / AC4 | not_satisfied | 尚未实现 |
| R5 | Change Archive 增加 active Change path scope，dispatch 保留 | #360 / AC5 | not_satisfied | 尚未实现 |
| R6 | 依赖缓存不缓存测试/产品产物 | #360 / AC6 | not_satisfied | 尚未实现 |
| R7 | 永久回归证明 Evidence Preservation 和 required contexts | #360 / AC7 | not_satisfied | 尚未实现 |
| R8 | 正式测试文档同步新触发语义 | #360 / AC8 | not_satisfied | 尚未实现 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Workflow 结构、Draft/Ready、Archive path filter 与 cache 永久回归 |
| 接口 / 契约 | required | required check names、workflow_call/dispatch/event contract 不漂移 |
| 集成 / 持久化 / 运行依赖 | required | Runtime/Tooling/Release 命中路径仍由原真实依赖证据负责；本变更 PR 需触发相关当前 HEAD Actions |
| 用户 / 工作流验收 | required | Draft → Ready → required full profile、merged Change → archive 的托管工作流闭环 |
| 跨组件关键路径 | not_applicable | 不改变产品跨组件业务接线；原 Full-stack Owner 只需证明未被删除/弱化 |
| 外部依赖 / 供应方探测 | not_applicable | 不改变 TikHub/LLM 等外部 Provider 事实 |
| 构建 / 打包 / 运行 | required | Workflow 自身变更 fail-closed；Runtime/Release 原正式构建责任保持并由 Actions 验证 |
| 文档 / 治理 / 其他 | required | Workflow Responsibility Audit、Evidence Preservation Mapping、Change Ready、docs facts |

# 完成审计

- [ ] upstream_re_read：完成前重读 #360 AC1-AC8 与当前 Ruleset/Workflow。
- [ ] change_coverage：逐项确认 R1-R8 均有实现和当前证据。
- [ ] reverse_audit：从 Draft/Ready/main/archive/release 反查是否有独立证据丢失。
- [ ] unresolved_cleared：所有 not_satisfied 清零且无静默 skip。

# 任务

- [x] 调查当前 Workflow、实际 Run 频率和 Runner 时长。
- [x] 建立 Workflow Responsibility Audit / Evidence Preservation 方案。
- [ ] 增加永久回归锁定目标触发和证据责任。
- [ ] 实现 Draft/metadata/path/cache 优化。
- [ ] 同步测试文档。
- [ ] 取得 PR current-head fresh Actions 证据。
- [ ] 完成 Completion Audit / Review。

# 验证

## 计划

- targeted：`tests/unit/test_ci_workflow_structure.py`、`tests/unit/test_change_archive_automation.py`、`tests/unit/test_release_workflow.py`。
- governance：Change completion、docs/secret/CI scope 相关当前门禁。
- Actions：验证 Draft fast-path 与 Ready current-head 完整 profile；必要时以 PR event 观察真实 Job 是否按预期 skipped/required。
- 就绪：`python scripts/quality/check_change_completion.py --root . --changed-since <base>`。

## 新鲜证据

- 尚未执行。

# 文档影响

- `docs/04_测试与调试说明.md` 需要同步 Draft/metadata/Archive/caching 当前事实。

# 交付

- Requirement Source：#360
- 提交：待实现
- 拉取请求：待创建
- 发布：不适用
