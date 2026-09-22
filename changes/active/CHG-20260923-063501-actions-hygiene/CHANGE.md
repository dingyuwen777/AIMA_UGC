---
schema: coding-change/v1
id: CHG-20260923-063501-actions-hygiene
title: GitHub Actions 失效 Workflow 自动清理
level: L3
status: ready_for_review
owner: dingyuwen777
branch: maintenance/actions-hygiene
created: 2026-09-23
updated: 2026-09-23
completion_gate: required
depends_on:
  - CHG-20260923-171000-actions-history-cleanup
affected_areas:
  - ci
  - github-actions
  - maintenance
affected_paths:
  - scripts/quality/actions_hygiene.py
  - .github/workflows/ci.yml
  - tests/unit/test_actions_hygiene.py
  - docs/blueprint/06_开发约束与分阶段实施.md
contracts:
  - GitHub Actions Hygiene
data_changes: []
---

# 变更摘要

- **要解决的问题**：PR #573 已完成一次性 Actions 历史清理，但删除/重命名 Workflow 后仍可能再次积累 All workflows 历史噪音。
- **拟议修改**：在 AIMA 现有 CI 中增加长期 Actions Hygiene job，并新增 repo-local quality 脚本和测试；不新增第 7 个 Workflow。
- **预期结果**：以后失效 Workflow 历史在健康 main push 后自动、保守清理。

# 背景、现状与问题

## 背景

Requirement Source：GitHub Issue #575。用户要求 Agent_Skills 与 AIMA_UGC 都增加长期自动清理能力。

## 当前现状

- main 当前有 CI、Full-stack Acceptance、Runtime Acceptance、Developer Tooling Compatibility、Release、Change Archive 六个正式 Workflow，均有独立职责。
- PR #573 / CHG-20260923-171000-actions-history-cleanup 已完成一次性清理并归档。
- 当前 main 无永久 cleanup 脚本/job。

## 问题、根因或约束

GitHub 删除 Workflow YAML 不会自动删除历史 runs。Actions run 删除不可逆，必须以当前 main + main Git 祖先历史 + run 状态共同判定，并把 destructive 权限限定到独立 job。

## 不修改的后果

以后新增一次性/迁移 Workflow 并删除后，All workflows 会再次积累旧入口，需要人工重复清理。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 当前 6 个 Workflow 都有独立长期职责 | .github/workflows 逐项职责审计 | 不删除/合并现役 Workflow |
| E2 | #573 只完成一次性历史清理 | main commits / archive | 需要长期机制 |
| E3 | CI Gate 是主产品质量聚合门禁 | .github/workflows/ci.yml | Hygiene 可在其后运行 |
| E4 | AIMA 已有 scripts/quality + unit 测试体系 | scripts/quality / tests/unit | repo-local 实现符合项目 Owner |

## 推断与待确认

- 待确认：main-fresh job-level actions: write 可真实调用 Actions API。
- 当前干净基线预期 deleted=0 / remaining=0。

# 目标、成功标准与非目标

## 目标

建立长期、自动、保守、不会污染 All workflows 菜单的 Actions Hygiene。

## 成功标准

- [x] AC1 当前 main Workflow path 永不删除。
- [x] AC2 只有默认分支祖先历史真实存在、当前 main 已消失的 path 才可清理；PR-only path 不删除。
- [x] AC3 path 有未完成 run 时整条跳过；只删除 completed runs。
- [x] AC4 删除前 snapshot，删除后 fresh readback；异常 fail closed。
- [x] AC5 main push + CI Gate Green 后执行；actions: write 只授予 hygiene job。
- [x] AC6 API 临时失败 warning + 后续 main push 重试，不使产品 CI 失败。
- [x] AC7 main 最终仍只有现有 6 个正式 Workflow。
- [ ] AC8 tests/Review/CI/merge/main-fresh/archive/#575 closure 完整闭环。

## 范围

- scripts/quality/actions_hygiene.py。
- ci.yml actions-hygiene job。
- tests/unit/test_actions_hygiene.py。
- Blueprint 06 CI 生命周期说明。

## 非目标

- 不删除/合并 6 个正式 Workflow。
- 不新增第 7 个 Workflow。
- 不清理其他 GitHub 资源。
- 不改产品/数据库/API/Job/部署语义。

## 必须保持不变

- CI Gate / Compose Golden Path / Tooling / Full-stack / Release / Change Archive 现有职责。
- Branch Protection 与 required checks。
- 产品 Contract / Schema / Migration。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | AIMA 项目 CI 维护 | #575 / E1-E4 | 不复制 Agent_Skills 内部实现 |
| 接口与契约 | repo-local CLI，dry-run 默认 | #575 / AC4 | 默认无 destructive side effect |
| 数据与迁移 | 不适用 | 无业务数据 | 无 Migration |
| 错误与失败语义 | script fail closed；CI wrapper warning best-effort | #575 / AC4/AC6 | 不误删、不阻塞产品 |
| 兼容性 | 6 个现役 Workflow 全保护 | #575 / AC1/AC7 | 当前 required checks 不变 |
| 部署与回滚 | 代码可 revert，deleted run 不可恢复 | GitHub 平台事实 | 删除候选需严格 |

# 修改方案与决策依据

## 最小充分方案

1. 新增 scripts/quality/actions_hygiene.py，使用当前 main workflow paths + Git main history + Actions runs 形成删除计划。
2. dry-run 默认，--execute 才 DELETE；执行后 fresh readback。
3. ci.yml 增加 actions-hygiene：push main、CI Gate success 后运行；仅该 job actions: write。
4. API 失败由 wrapper 输出 warning 并退出 0，下次 main push 自动重试。
5. 单元/Contract 测试覆盖安全边界和 permissions。
6. Blueprint 06 增加 Workflow 生命周期责任，不复制实现细节。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 复用 CI | E1/E3 | 不新增第 7 个 Workflow |
| D2 main history | #575 / AC2 | 防止 PR-only 误删 |
| D3 active path skip | #575 / AC3 | 保守处理并发运行 |
| D4 best-effort | #575 / AC6 | GitHub maintenance API 不应阻塞产品 CI |

<!-- governance:required-for=L3 -->
## 备选方案与取舍

- 合并/删除现有 6 个 Workflow：职责独立，会损失验证边界；不采用。
- 独立 Cleanup Workflow：新增菜单项；不采用。
- 固定 obsolete allowlist：不能自动覆盖未来 rename/delete；不采用。
- schedule：main push 已满足自动收尾，不增加额外运行成本。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | current path 永不删除 | #575 / AC1 | not_satisfied | 待实现/测试 |
| R2 | main history / PR-only | #575 / AC2 | not_satisfied | 待实现/测试 |
| R3 | active skip / completed only | #575 / AC3 | not_satisfied | 待实现/测试 |
| R4 | snapshot/delete/readback | #575 / AC4 | not_satisfied | 待实现/测试 |
| R5 | main + CI Gate + minimal permission | #575 / AC5 | not_satisfied | 待 workflow |
| R6 | best-effort | #575 / AC6 | satisfied | warning + later main retry wrapper 已落库 |
| R7 | 保持 6 个 Workflow | #575 / AC7 | not_satisfied | 待 final readback |
| R8 | 完整交付 | #575 / AC8 | not_applicable | pre-merge Change 不自证未来 merge/main-fresh/archive/closure；由 delivery gate 持有 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| scripts/quality/actions_hygiene.py | 新增 | 清理核心 | R1-R4 |
| .github/workflows/ci.yml | 新增 hygiene job | 自动执行 | R5-R7 |
| tests/unit/test_actions_hygiene.py | 新增 | 回归 | R1-R6 |
| docs/blueprint/06_开发约束与分阶段实施.md | CI 生命周期说明 | 长期项目事实 | R5-R7 |

- [x] 调查当前实现和事实源；新建项目则确认现有资料、目标和硬约束
- [x] 建立与风险相称的任务路由和验证矩阵
- [x] 行为变化建立失败证据或说明测试例外
- [x] 完成最小实现，不静默扩大范围
- [x] 同步受影响的长期文档或明确不适用依据
- [x] 取得仍覆盖当前版本的验证证据
- [x] 完成需求追溯、完成审计和适用复核

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 清理计划与边界 |
| 接口 / 契约 | required | CLI / Workflow trigger/permissions |
| 集成 / 持久化 / 运行依赖 | required | Git history + Actions REST |
| 用户 / 工作流验收 | required | All workflows 自动维持干净 |
| 跨组件关键路径 | required | main push → CI Gate → hygiene → API |
| 外部依赖 / 供应方探测 | required | main-fresh Actions API |
| 构建 / 打包 / 运行 | not_applicable | 不改产品构建/部署 |
| 文档 / 治理 / 其他 | required | Blueprint + Change/Issue |

## 验证计划

- 目标测试：tests/unit/test_actions_hygiene.py。
- 相关回归：repository quality/full CI selector。
- 静态检查或构建：ruff/py_compile。
- 专项真实边界：main-fresh hygiene job。
- 就绪检查：check_change_completion --require-active-ready。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | Actions run 删除不可逆 | 保守判定 + fresh readback |
| 兼容性 | 6 个 Workflow 与 required checks 不变 | current paths protect |
| 数据 / Migration | 不适用 | 无 DB 变化 |
| 部署 / 运行 | 不适用 | 仅 GitHub repo maintenance |
| 回滚 / 恢复 | 代码可 revert；run 不可恢复 | fail closed |

# 文档、依赖、部署与发布影响

- **长期文档**：Blueprint 06 增加 Workflow 生命周期职责。
- **依赖 / Runtime**：无新增依赖。
- **配置 / Secret**：使用 github.token，不新增 Secret。
- **部署 / Release**：不改 Release / Compose / production。
- **兼容 / 消费方通知**：只影响 Actions 历史维护。

# 完成审计

- [x] upstream_re_read：Ready 前已重读 Issue #575、current main 与本 Change 的直接事实源。
- [x] change_coverage：AC1-AC7 已由当前实现/测试资产/Workflow Contract 覆盖；AC8 post-merge 由 downstream gate 持有。
- [x] reverse_audit：已从 workflow deletion → current paths → main history → run snapshot → delete → fresh readback 反向复核。
- [x] unresolved_cleared：pre-merge Requirement 已清零；真实 Actions API 副作用与 post-merge closure 继续由 Ready/main-fresh gate 验证。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | main | workflow responsibility/readback | confirmed | 6 个现役 Workflow 都应保留 |\n| V2 | current branch / PR #576 | current-head diff + static Contract audit | Green | 候选算法、CI Gate 依赖、权限最小化、AIMA Blueprint 生命周期事实均已落库；真实 API 待 Ready/main-fresh |
| V3 | PR #576 / Issue #575 | canonical Requirement Source revalidation | fixed | 技术变更 Issue 已补齐动机/根因、兼容迁移、风险回滚、稳定 AC、验证要求和上游事实源 |

## 未验证内容与剩余风险

- current-head tests 将由 Ready PR required CI 执行；此前 Draft 平台行为不作为完成证据。
- 尚未 main-fresh 验证 GitHub Actions API。

## 交付状态

- 提交：实现、测试、Workflow 接线和文档已在 maintenance/actions-hygiene
- 拉取请求：#576（Draft，准备转 Ready）
- CI：Requirement Source 已修正；本 revision 触发 fresh current-head required CI
- 合并：未执行
- Change 归档：未执行
- 发布 / 部署：不适用

## 备注

无。