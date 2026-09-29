---
schema: coding-change/v1
id: CHG-20260928-001000-ci-evidence-optimization
title: CI证据复用与数据库测试精准化
level: L2
status: done
owner: dingyuwen777
branch: tech/636-ci-evidence-optimization
created: 2026-09-28
updated: 2026-09-28
completion_gate: required
depends_on: []
affected_areas:
  - ci
  - testing
  - github-actions
affected_paths:
  - .github/workflows/ci.yml
  - .github/workflows/runtime.yml
  - .github/workflows/tooling.yml
  - scripts/quality/classify_ci_scope.py
  - scripts/quality/resolve_main_evidence.py
  - tests/unit/test_ci_scope.py
  - tests/unit/test_ci_test_impact_optimization.py
  - tests/unit/test_ci_workflow_structure.py
  - tests/unit/test_ci_main_evidence_reuse.py
  - docs/04_测试与调试说明.md
  - docs/blueprint/06_开发约束与分阶段实施.md
contracts: []
data_changes: []
---

# 变更摘要

- **要解决的问题**：当前 changed-scope 仍会让未精确映射的 PostgreSQL / Full-stack 变化退化为宽泛回归，且 PR 已成功验证的同一 Git tree 在 merge 后 main 再次执行昂贵证据。
- **拟议修改**：增加 main tree-based Evidence Reuse，细化 PostgreSQL target/domain/all 与 Full-stack journey 映射，并把依赖审计、Wheel 等专项成本绑定到真实影响面。
- **预期结果**：PR 负责生成主要产品证据；main 内容与最终 PR tree 相同且来源证据完整时只做轻量复用验证，无法证明时自动回退正常执行；数据库与真实浏览器测试只运行本次真实相关范围。

# 背景、现状与问题

## 背景

Issue #636 / AC1–AC7 来自用户对当前 Actions 成本的直接要求。用户明确要求在不降低质量的前提下优化 PostgreSQL、主质量、Real Full-stack、Runtime 与 Tooling，并完成 PR 合并到 main。

## 当前现状

- `.github/workflows/ci.yml` 在 pull_request 与 push(main) 上都可运行 Quality Core、PostgreSQL、Real Full-stack。
- `classify_ci_scope.py` 对无法精确映射的 persistence adapter 使用 `POSTGRES_ALL`；普通 backend+frontend 混合 diff 会把 Real Full-stack 升级为全部 specs。
- PR #635 最终 HEAD 与 merge commit 的 Git tree SHA 完全相同，但 PostgreSQL Integration 在 PR 与 main 分别执行约 7 分钟。
- Runtime Acceptance 与 Developer Tooling 也同时监听 PR 与 main；Runtime 已有 changed-scope fast path，但没有复用最终 PR 同 tree 的现有成功证据。
- main Ruleset 的 required contexts 包括 `CI Gate`、`Requirement Traceability and Completion Audit`、`Compose Golden Path`。

## 问题、根因或约束

根因不是 PostgreSQL 本身必须慢，而是 Evidence Selection 与 Evidence Freshness 没有完全闭合：未知 persistence 被当作跨域全量风险；cross-component 被技术目录组合替代真实 user journey；merge 后 commit SHA 改变被误当成内容变化。优化必须保留真实 PostgreSQL/Runtime 边界和 required check identity，不能通过删测试、降低断言或绕过保护规则换速度。

## 不修改的后果

高频 PR 会持续重复支付无关和重复的 Runner 时间，数据库集成测试随着目录增长进一步变慢；团队难以从 CI 日志解释“为什么这次需要跑这一层”，影响开发反馈速度和 Actions 成本。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | PR #635 head 与 merge commit 的 tree SHA 相同 | GitHub commit API：均为 `145be0086d24e78b84bd3059e82445b82c4baa8b` | main 可按内容身份复用最终 PR Evidence，而不是按 commit SHA 机械重跑 |
| E2 | PR #635 PostgreSQL Integration 在 PR 与 main 分别约 7m10s / 7m09s | GitHub Actions jobs | 重复数据库 Evidence 是当前最高收益优化点 |
| E3 | 当前 classifier 未识别 workbench/historical_import adapter 时回退 `POSTGRES_ALL` | `scripts/quality/classify_ci_scope.py` | 增加 target/domain/all 分层映射 |
| E4 | `CI Gate` 已聚合 Core/PostgreSQL/Real Full-stack required 结果 | `.github/workflows/ci.yml` | main 复用可验证 PR `CI Gate` 后跳过重复产品 Evidence |
| E5 | Runtime 独立 required context 为 `Compose Golden Path` | main Ruleset + `.github/workflows/runtime.yml` | Runtime 必须独立复用/回退，不能由 CI Gate 替代 |
| E6 | Tooling 已有 path filters，但 PR 与 main 仍可重复实际执行 | `.github/workflows/tooling.yml` | 同 tree main 可复用对应 PR check |
| E7 | Agent_Skills Fresh Evidence Contract 允许相关实现/Contract/环境未变化时复用现有 Evidence | 当前 canonical Agent_Skills Router/Coding | 证据复用应基于内容与覆盖范围，不以阶段切换本身触发重跑 |

## 推断与待确认

- GitHub main push 上关联 merged PR 的 API 返回在当前仓库需要由新 workflow 实跑确认；设计采用 fail-closed，无法唯一解析时直接回退正常执行，因此不阻塞实施。

# 目标、成功标准与非目标

## 目标

让 CI 从“技术栈触发全量 + PR/main 重复”收敛为“真实风险精准 Evidence + 同 tree 证据安全复用 + 无法证明时自动回退”。

## 成功标准

- [ ] main tree 与来源 PR 最终 HEAD tree 一致且来源 required Evidence 绿色时，main 不重复执行对应昂贵层。
- [ ] Workbench / Historical Import 等已知 PostgreSQL Owner 选择目标测试或最小 domain suite，不再自动 `all`。
- [ ] 普通 backend+frontend 混合变化不再自动运行全部 Real Full-stack，已知 journey 精准选择。
- [ ] npm audit / Wheel 等专项成本只在相关依赖/打包风险变化时运行。
- [ ] CI Gate / Compose Golden Path 保持 fail-closed 与稳定 check identity。
- [ ] CI classifier、Evidence Reuse、Workflow structure 的自动化回归覆盖正负路径。
- [ ] 当前 PR CI、独立 Review、merge 后 main reuse/fallback 与 Change Archive 完成。

## 范围

- CI/Runtime/Tooling workflows、CI impact classifier、main Evidence Resolver、相关单元回归。
- 直接描述 CI changed-scope 与 Evidence 复用行为的测试/开发文档。

## 非目标

- 不删除 PostgreSQL Integration、Real Full-stack、Runtime Acceptance 或 Tooling 资产。
- 不改变业务 public API、数据库 Schema/Migration、依赖版本、生产部署或生产数据。
- 不移动大量 integration tests；先由 classifier 选择现有资产。
- 不引入第三方 CI 平台或新测试框架。

## 必须保持不变

- PostgreSQL 真实事务/锁/约束风险仍由真实 PostgreSQL Evidence 证明。
- Runtime/Compose 独立失败边界不能被 Unit/Mock/CI Gate 冒充。
- required check identity 不因优化消失；无法安全复用必须 fail closed。
- Draft、Requirement/Change、Review、Branch Ruleset 与 merge head guard 等治理门禁继续生效。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 只修改 CI Evidence Selection / Reuse Owner | E1–E7 / #636 | 不触碰业务 Owner |
| 接口与契约 | 产品 Contract 不变；新增内部 CI 输出字段 | #636 / AC1–AC6 | 仅 workflow/classifier consumers |
| 数据与迁移 | 不适用 | 无 Schema/数据变化 | 无 Migration |
| 错误与失败语义 | 任何来源 PR、tree、check 无法确认均返回不可复用并执行原正常路径 | #636 / AC1、AC5 | 优化失败不会跳过 Evidence |
| 兼容性 | 保持 CI Gate / Compose Golden Path 名称与独立责任 | E4、E5 | Branch Ruleset 不被绕过 |
| 部署与回滚 | 普通仓库 CI 变更；回滚 commit 即恢复旧策略 | 无生产运行数据改变 | 不需要 Deploy/Migration |

# 修改方案与决策依据

## 最小充分方案

1. 新增纯标准库 main Evidence Resolver：只在 main push 上解析已合并 PR，比较 current/pr-head tree，并核验指定 check 的最终成功状态；输出可复用/原因。
2. CI Core 在 main 可复用时只执行 resolver/classification fast path，令 PostgreSQL/Full-stack 按不适用跳过；不可复用时保持原 changed-scope。
3. PostgreSQL classifier 增加 target → domain suite → all：已知窄 leaf adapter / 单个 integration test 优先跑目标文件；Historical Import 等宽 Repository 运行拥有其真实失败边界的相关 domain suites；真正横切或未知 persistence 才 `all`。
4. Full-stack 使用显式三态 Owner/Journey 映射：已知 journey 选择 specs、已知无需真实全栈则不运行、未知用户入口 fail closed 到 `all`；移除“任意 backend+frontend=all”的机械升级。
5. Runtime 与 Linux/Windows Tooling 在同 tree main 上分别核验其 PR check 后走轻量复用；不满足条件继续原验证。
6. npm audit 仅依赖清单/锁变化时执行；Wheel 仅 Python package/build 输入变化时执行。Reporting 字体暂保留，因为当前完整 backend unit suite仍包含 Reporting 渲染测试，不能在未拆 test impact 前删先决条件。
7. 加每日 CI 全量回归、每周 Runtime/Tooling 全量回归，作为 impact mapping 安全网；更新当前测试说明。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 tree-based reuse | E1、E7 | 证明内容身份而非 commit metadata；同时能覆盖 merge commit SHA 改变 |
| D2 CI Gate 作为产品聚合 Evidence | E4 | 已包含 Core/PostgreSQL/Full-stack，不重复枚举所有内部 job |
| D3 Runtime 独立 reuse | E5 | Runtime 是独立失败边界，不能被产品 CI 聚合取代 |
| D4 target→suite→all | E2、E3 | 保留真实 PostgreSQL 语义，同时显著缩小常见 leaf change 成本 |
| D5 定时全量安全网 | E3、#636 | 精准 impact map 发生遗漏时提供低频全量检测，不把成本放在每次交互提交 |

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | main 只在同 tree + 来源 required Evidence 成功时复用，否则重跑 | #636 / AC1 | satisfied | `resolve_main_evidence.py` + CI/Runtime/Tooling reuse gate；API/tree/check 任一不可确认时返回 reusable=false。 |
| R2 | Workbench/Historical Import PostgreSQL 精准选择 | #636 / AC2 | satisfied | Workbench 使用两个直接 `postgres_targets`；Historical Import 经 Review 证明属于宽 Repository，改为 `content + ingestion` 两个 owned domain suites，避免错误过度收窄。 |
| R3 | Full-stack 按真实 journey 选择，普通混合 diff 不自动 all | #636 / AC3 | satisfied | 删除普通 frontend+backend→all 机械升级；已知 collection/ingestion/analysis/content/admin journey 继续映射 spec，全局 Contract/显式未知 fullstack spec 保持 all。 |
| R4 | 专项 Core 成本按真实依赖/打包风险运行 | #636 / AC4 | satisfied | npm audit 绑定 frontend dependency inputs；Wheel 绑定 Python package inputs。Reporting 字体因完整 Unit suite 真实依赖保留并在 Change 中记录边界。 |
| R5 | CI Gate / Runtime 继续 fail closed | #636 / AC5 | satisfied | check 名称/聚合责任不变；resolver 单元回归覆盖 tree mismatch、check missing/failure；Runtime 独立核验 Compose Golden Path。 |
| R6 | CI impact / workflow / evidence reuse tests 与 PR CI 绿色 | #636 / AC6 | explicitly_deferred | 结构/行为回归已写入当前分支；#636 / AC6 明确 PR Ready 后由 GitHub Actions 执行并作为 merge gate，当前不得提前声称 CI 绿色。 |
| R7 | merge 后 main 行为、归档与 Issue Closure 完成 | #636 / AC7 | explicitly_deferred | #636 / AC7 明确只能在 merge 后验证；repository-native Archive 与 Issue Closure 属于 post-merge 收尾。 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| `scripts/quality/resolve_main_evidence.py` | 安全解析 merged PR/tree/check Evidence | 支持 main 复用且 fail closed | R1、R5 / E1、E4–E7 |
| `scripts/quality/classify_ci_scope.py` | PostgreSQL targets、Full-stack journey、专项 Core flags | 降低无关 Evidence | R2–R4 / E2–E3 |
| `.github/workflows/ci.yml` | reuse fast path、target execution、专项成本、daily full | 主 CI 责任闭环 | R1–R6 |
| `.github/workflows/runtime.yml` | Compose Evidence reuse + weekly full | 保留独立 Runtime 责任 | R1、R5 |
| `.github/workflows/tooling.yml` | Linux/Windows Evidence reuse + weekly full | 避免 main 重复工具链验证 | R1、R5 |
| CI unit tests | 正负路径和 structure regressions | 防止以后回退到粗粒度/重复执行 | R1–R6 |
| 测试/治理文档 | 同步 changed-scope 与 reuse 当前事实 | 让维护者可理解/定位 | R1–R6 |

- [x] 调查当前实现和事实源。
- [x] 建立与风险相称的任务路由和验证矩阵。
- [x] 行为变化建立失败证据：先提交 resolver Red 测试，再实现。
- [x] 完成最小实现，不静默扩大范围。
- [x] 同步受影响的长期文档。
- [x] 当前分支已完成代码/测试/文档 readback；PR current-head CI 按 #636 / AC6 作为 Ready 后 merge gate。
- [x] 完成需求追溯与 pre-merge 完成审计；post-merge 条目按 #636 / AC7 延后。

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | resolver tree/check 判定；classifier target/suite/journey/special-cost 输出 |
| 接口 / 契约 | not_applicable | 产品 public Contract 不变；内部 GITHUB_OUTPUT 由同一 PR workflow structure tests 覆盖 |
| 集成 / 持久化 / 运行依赖 | required | PR changed-scope 实际 PostgreSQL Evidence，验证新的 target/suite 执行路径 |
| 用户 / 工作流验收 | not_applicable | 本任务无终端用户产品 UI 行为变化 |
| 跨组件关键路径 | required | PR→CI Gate→merge→main reuse/fallback；Runtime 独立 Compose check |
| 外部依赖 / 供应方探测 | not_applicable | 不涉及 TikHub/LLM/第三方产品 API；GitHub Actions 是交付平台本身，由实际 PR/main Actions 验证 |
| 构建 / 打包 / 运行 | required | Workflow YAML 当前 HEAD 实际执行；package flag 回归 |
| 文档 / 治理 / 其他 | required | Requirement/Change、Ruleset identity、Docs targeted、Review/CI/Archive |

## 验证计划

- 目标测试：`tests/unit/test_ci_main_evidence_reuse.py`、CI classifier/structure tests。
- 相关回归：现有 CI impact optimization、workflow structure、actions runner optimization。
- 静态检查或构建：Ruff 对新增 Python；workflow 由 GitHub Actions 当前 HEAD 解析并实际执行。
- 专项真实边界：PR PostgreSQL/Real Full-stack/Runtime/Tooling 按 classifier 真实分配；main post-merge 验证 reuse。
- 就绪检查：`python scripts/quality/check_change_completion.py --root . --require-active-ready`。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 错复用、impact map 漏边界、check identity 漂移 | 同 tree + exact merged PR + latest successful check；无法确认 fail closed；结构回归 |
| 兼容性 | 产品行为保持；GitHub required contexts 名称保持 | 不改 public Contract；CI Gate/Compose 名称不变 |
| 数据 / Migration | 不适用 | 无 Schema/数据变化 |
| 部署 / 运行 | 只改变 GitHub Actions 执行策略 | 不改变生产 Compose/Release 配置 |
| 回滚 / 恢复 | 可回滚本 PR | 恢复旧 classifier/workflow 即重新支付原全量成本，不影响业务数据 |

# 文档、依赖、部署与发布影响

- **长期文档**：targeted 更新 `docs/04_测试与调试说明.md`、`docs/blueprint/06_开发约束与分阶段实施.md`。
- **依赖 / Runtime**：不新增/升级依赖；resolver 仅 Python 标准库。
- **配置 / Secret**：只使用现有 GitHub token 读取本仓 PR/check/commit facts，不新增 Secret。
- **部署 / Release**：不适用；不改变生产部署与 Release artifact。
- **兼容 / 消费方通知**：CI 维护者需以 classifier 输出理由定位 selected target/suite/spec；产品消费者无影响。

# 完成审计

- [x] upstream_re_read：已重读 #636 / AC1–AC7、当前 Ruleset、CI/Runtime/Tooling workflows 与 classifier。
- [x] change_coverage：R1–R5 已实现；R6 是 PR Ready 后 merge gate，R7 是 merge 后收尾，均有 #636 正式阶段依据。
- [x] reverse_audit：PostgreSQL、Real Full-stack、CI Gate、Runtime、Linux/Windows Tooling 均保留独立 Owner；每个 reuse 路径都有无法确认即回退的 fail-closed 机制。独立 Review 另发现并修复两处过度优化风险：Historical Import 从过窄 target 提升为 Content+Ingestion suites；main Evidence reuse 继续运行 Active Change / governance / Secret+Docs 轻量门禁。
- [x] unresolved_cleared：无 `not_satisfied`；R6/R7 按 #636 明确生命周期阶段记录为 `explicitly_deferred`。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | `tech/636-ci-evidence-optimization` | `tests/unit/test_ci_main_evidence_reuse.py` readback | 正负路径回归已建立，等待 Ready 后 CI 执行 | 同 tree/check 成功、tree mismatch、missing/failed check 的预期语义 |
| V2 | 当前分支 | classifier / workflow structure test readback | 精确 target/journey/special-cost 与 schedule/reuse 断言已建立，等待 Ready 后 CI 执行 | Evidence Preservation Mapping 已转成自动回归 |
| V3 | 当前 PR HEAD | GitHub PR CI | explicitly_deferred 到 #636 / AC6 merge gate | 当前 HEAD workflow 可运行且 required gates 绿色 |
| V4 | merge 后 main | GitHub Actions + Change Archive | explicitly_deferred 到 #636 / AC7 | 实际 tree-based reuse/fallback 与 archive |

## 未验证内容与剩余风险

- 尚未取得 PR current-head CI 与 post-merge main Evidence；两者分别由 #636 / AC6、AC7 明确绑定到 Ready 后 merge gate 与 post-merge 阶段，不能提前伪造。当前实现仍需以 GitHub Actions 实跑结果决定是否可合并。

## 交付状态

- 提交：Red、resolver、classifier、workflow、回归与文档提交已在 `tech/636-ci-evidence-optimization`。
- 拉取请求：#637，Draft；关联 #636。
- CI：待切换 Ready 后由当前 HEAD 实跑。
- 合并：待独立 Review / required CI 通过并以 expected head merge。
- Change 归档：待 merge 后 repository-native workflow。
- 发布 / 部署：不适用；本任务只改变仓库 CI，不执行生产发布。

## 备注

Reporting CJK font 暂不作为本轮删除成本：当前完整 backend unit suite 含 Reporting 渲染测试；在未建立 backend unit test impact map 前移除字体会把“省时”变成降低测试环境完整性。