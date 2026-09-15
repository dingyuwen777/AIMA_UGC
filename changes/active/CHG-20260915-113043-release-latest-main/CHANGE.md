---
schema: coding-change/v1
id: CHG-20260915-113043-release-latest-main
title: Release 发布绑定发布时最新 main
level: L3
status: ready_for_review
owner: ChatGPT
branch: fix/release-published-latest-main
created: 2026-09-15
updated: 2026-09-15
completion_gate: required
depends_on: []
affected_areas:
  - release
  - ci
  - operations
affected_paths:
  - .github/workflows/release.yml
  - tests/unit/test_release_workflow.py
  - docs/02_环境运行与部署.md
  - docs/operations/01_生产部署与离线Release方案.md
  - changes/active/CHG-20260915-113043-release-latest-main/CHANGE.md
contracts:
  - 正式 Release revision identity：Release Tag、main、离线 Bundle、GHCR 镜像与 manifest 必须绑定同一 Git SHA
  - GitHub 网页 Release 发布入口与 workflow_dispatch 正式发布入口
data_changes:
  - 无 Schema、Migration、业务数据或运行数据变化
---

# 变更摘要

修复正式 Release 的时间语义：不再把“Git Tag 创建时”当成“GitHub Release 发布时”。GitHub Release 网页路径改由 `release: published` 触发，正式构建显式绑定发布时最新 `main`；Tag 若未精确指向该 SHA 则 fail closed，不生成或上传旧代码镜像，也不静默移动历史版本 Tag。`workflow_dispatch` 与 PR Release dry-run 保持现有能力。

# 目标、范围与非目标

## 成功标准

- [x] GitHub Release 页面真正 `published` 时才进入网页正式发布链；单独创建 Tag 不再构建正式镜像。
- [x] 网页正式发布与 `workflow_dispatch` 的正式候选源码都显式来自发布开始时最新 `main`，构建前和发布前均检查 `main` 没有漂移。
- [x] 网页 Release Tag 必须精确指向候选 SHA；旧 Tag / 非 main Tag fail closed，绝不移动或覆盖版本 Tag。
- [x] `workflow_dispatch` 继续允许 Workflow 创建新 Tag/GitHub Release；网页 `release: published` 对已存在的 Release 只上传 replay-tested assets。
- [x] PR dry-run 继续真实构建 Linux/AMD64 Backend/Frontend、生成离线 Bundle 并用 `--no-build --pull never` 回放。
- [x] 合并前证据已达到 Review/CI 门禁入口：Release dry-run 当前实现 revision 成功，文档已同步、两阶段 Review 无阻塞 Finding；PR required checks 在本 Change 进入 `ready_for_review` 后作为 current-head merge gate 执行。合并后的 main-fresh CI 与 Issue #492 Closure Audit 属于 post-merge Finalization，不伪造成 Change Ready 证据。

## 范围

- `.github/workflows/release.yml` 的触发事件、正式 revision 解析、Release 存在性校验与发布分流。
- `tests/unit/test_release_workflow.py` 对新正式发布语义的静态回归。
- 两份直接描述正式 Release 操作的当前文档。
- Requirement Source #492、当前 Change、PR/CI/Review/合并后收尾。

## 非目标

- 不修改 Dockerfile、Compose Runtime、业务代码、依赖、Contract、Schema 或 Migration。
- 不让已发布历史 Release 自动追踪未来 `main`；每个版本仍是不可变快照。
- 不静默移动已经存在且指向旧提交的版本 Tag。
- 开发验证不创建真实版本 Tag、GHCR 版本或 GitHub Release。

## 必须保持不变

- Release Bundle 继续包含 Backend、Frontend、固定 `postgres:18.4`，服务器继续 `docker load` + canonical Compose `--no-build --pull never`。
- GHCR application packages 继续要求 private；GitHub Release 离线压缩包继续作为公开 Release asset 的当前交付边界。
- Release manifest 的 `git_sha` 必须等于实际构建并发布的源码 SHA。
- `workflow_dispatch` 只能从 `main` 正式发布；PR 模式只 dry-run，不产生仓库/registry 发布副作用。
- 不绕过 Branch Ruleset、required checks、Review 或 expected-head merge 防漂移。

# 方案比较与关键决策

## 方案 A：继续使用 Tag `create` 事件，仅加强检查

- 优点：改动最小，沿用现有 Workflow。
- 缺点：检查发生在 Tag 创建时，不是 Release 真正发布时；Tag 创建后 `main` 前进，后续发布 Release 仍无法表达“发布时最新 main”。
- 结论：不满足 #492 AC1/AC2，淘汰。

## 方案 B：改用 `release: published`，显式从最新 main 构建，并要求 Tag 精确匹配

- 优点：触发时间与用户“发布 Release”的动作一致；仍保持 Tag/Bundle/Image/manifest 单一 SHA；旧 Tag fail closed，不篡改版本历史。
- 缺点：GitHub Release 页面会先进入 published 状态，Workflow 随后上传构建资产；若 Tag 已落后，Workflow 会失败且该 Release 需要维护者纠正版本/Tag 后重新发布。
- 结论：正确性、可审计性、不可变版本身份最佳，采用。

## 方案 C：Release 发布时自动把旧 Tag 强制移动到最新 main

- 优点：表面上最自动化。
- 缺点：会修改已经存在的版本身份，可能让外部 checkout、Release notes、镜像 provenance 与历史 Tag 发生漂移；高风险且难以审计。
- 结论：违反不可变 Release 身份原则，淘汰。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Release 网页路径只在真正 published 时进入正式发布，单独 Tag create 不再发布 | #492 / AC1 | satisfied | `.github/workflows/release.yml` 使用 `release: types: [published]`，删除正式 `create` 触发；`tests/unit/test_release_workflow.py` 固化该机器事实；Review A1/A2 已核对。 |
| R2 | 正式网页发布使用发布时最新 main，并在构建前/发布前防漂移 | #492 / AC2 | satisfied | 正式事件 checkout 显式 `ref=main`；build/publish 两阶段均读取远端 `git/ref/heads/main` 并要求等于 `RELEASE_SHA`；PR dry-run run `34926618924` 已证明修改后的 Workflow 能完成候选构建/回放。 |
| R3 | Release Tag 必须精确等于候选 main SHA；旧 Tag fail closed 且不自动移动 | #492 / AC3 | satisfied | build/publish 两阶段都解析 `${VERSION}` Tag target 并与 `RELEASE_SHA` 比较；不存在 `git tag -f`、`git update-ref` 或等价移动逻辑；相关静态回归已写入 `tests/unit/test_release_workflow.py`。 |
| R4 | workflow_dispatch 与 PR dry-run 保持现有正式/验证能力 | #492 / AC4 | satisfied | `workflow_dispatch` 保留；PR dry-run run `34926618924`：Build Linux AMD64 images、Bundle、`docker load`、canonical Compose `--no-build --pull never` replay、archive check 均 success；Publish job 在 PR 模式正确 skipped。 |
| R5 | release.published 上传既有 Release assets；workflow_dispatch 继续创建 Release；所有发布身份同 SHA | #492 / AC5 | satisfied | publish job 分流：`workflow_dispatch → gh release create --target ${RELEASE_SHA}`；`release → gh release upload`；统一最终 Tag/Release/assets 校验与 manifest `git_sha` 检查保留。 |
| R6 | Release 单测、文档/治理、PR CI、main-fresh 全部闭环 | #492 / AC6 | explicitly_deferred | Pre-merge：Change 已 Ready，PR current-head required CI/Release dry-run继续作为 merge gate；Post-merge：`Issue #492` Closure Audit 持有 main-fresh CI、Acceptance 写回/重读与关闭证据。main-fresh 只能在 merge 后取得，不能作为 Change Ready 的伪造前置证据。 |

# 实施结果

1. `.github/workflows/release.yml`：`create` → `release: published`；正式候选 checkout 显式使用 `main`，PR dry-run 保持 PR revision。
2. release event 版本身份使用 `github.event.release.tag_name`；正式校验分别处理 `workflow_dispatch` 与 `release`。
3. 网页 Release 路径要求现有 Release/Tag 均存在且 Tag=current main；`workflow_dispatch` 继续要求同名 Release 不存在、Tag 不存在或精确匹配。
4. publish 阶段再次核验 main/tag；网页 Release 用 `gh release upload`，Actions 正式入口继续 `gh release create --target RELEASE_SHA`。
5. `tests/unit/test_release_workflow.py` 新增/调整正式触发、main checkout、Tag/main 一致性、create/upload 分流与无强制移动的回归断言。
6. `docs/02_环境运行与部署.md` 与 `docs/operations/01_生产部署与离线Release方案.md` 已同步当前操作流程和 stale Tag fail-closed 边界。
7. 最新 `main` 已合入任务分支；相对该 main 只保留本 Change 的 5 个目标文件。

# Validation Matrix

| 验证层 | 是否要求 | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | `tests/unit/test_release_workflow.py` 覆盖 release.published、main checkout、Tag/main 一致性和 create/upload 分流；current-head CI 负责执行该回归，结果作为 PR merge gate。 |
| 接口 / Contract | required | Review A1/A2 已核对 Release identity invariant：Tag/main/manifest/image SHA 单一；正式事件只允许 `workflow_dispatch/release.published`；不存在 Tag force/move。 |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不改数据库、文件持久化、Worker 或服务器 Runtime dependency。 |
| 用户 / Workflow Acceptance | required | GitHub Actions PR Release dry-run run `34926618924` 在实现 revision `aa913fa0028809c00a06edf3a40a94bf35cf7d22` success；正式发布副作用未在开发阶段执行。 |
| 跨组件 Golden Path | required | 同 run `34926618924`：Docker build → images.tar → 删除本地候选 → docker load → canonical Compose `--no-build --pull never --wait` → Migration/Readiness/持久目录 smoke success。 |
| External Dependency / Provider Probe | not_applicable | 不修改 TikHub/LLM/第三方业务 Provider；GitHub `release: published` 与 `GITHUB_TOKEN` 事件语义已依据 GitHub 官方文档核验。 |
| Build / Package / Runtime | required | run `34926618924`：Linux/AMD64 Backend/Frontend build、immutable image/schema facts、离线 Bundle、deploy archive 均 success；Runtime Acceptance run `34926618929` success。 |
| Docs / Governance / Other | required | Requirement Source #492 已写后重读；两份正式文档 diff 均只修改 Release 段落；Change Completion Audit 完成；PR current-head CI 与 post-merge main-fresh 继续由交付门禁负责。 |

# Evidence Preservation Mapping

| 原证明责任 | 原位置 | 新位置 | 证据等级 | 依据 |
| --- | --- | --- | --- | --- |
| PR Release dry-run 构建/离线回放 | `build-verify` PR 路径 | 保持原 `build-verify` PR 路径 | 保持 | run `34926618924` 已实际证明 build、Bundle、docker load、Compose replay 全链 success。 |
| 正式发布只使用当前 main | Tag create 校验 `CURRENT_MAIN_SHA == RELEASE_SHA` | release.published / workflow_dispatch 均显式 checkout main，并在 build/publish 两阶段复核 | 加强 | 检查时间从 Tag 创建推进到 Release 发布，并保留二次防漂移。 |
| Tag 与候选 SHA 一致 | build/publish 两阶段 Tag target 检查 | 保持双阶段检查 | 保持/加强 | release.published 要求已存在 Tag；workflow_dispatch 仍可无 Tag 后由 release create 建立。 |
| 离线候选不可变传递 | Actions artifact + SHA256SUMS | 保持 | 保持 | publish job 继续只消费 replay-tested artifact；PR 模式 publish skipped。 |
| Release asset 完整性 | `gh release create` + verify | workflow_dispatch create；release.published upload；统一 verify | 保持 | 两种正式入口最终验证相同 asset 集合和 tag target。 |

# 风险、兼容、部署与回滚

- 风险：网页 Release 若引用提前创建且已经落后的 Tag，会在正式构建前 fail closed；这是目标行为，避免旧代码镜像。
- 风险：`release: published` 事件发生时 GitHub Release 已可见，资产在 Workflow 成功后才出现；失败时不会上传错误镜像，需要维护者修正 Tag/版本后重新发布。
- 兼容：现有 `workflow_dispatch` 和 PR dry-run 保留；服务器 Bundle/Compose/镜像标签格式保持。
- GitHub Token：`workflow_dispatch` 路径用仓库 `GITHUB_TOKEN` 创建 Release；GitHub 官方事件规则明确该 token 触发的普通 repository event 不递归创建新的 workflow run，因此不会因新 `release: published` 入口重复发布。
- Migration/Data：无。
- 部署：本任务只修改发布流水线，不直接部署生产服务器，也未创建真实版本 Tag/GitHub Release/GHCR 版本副作用。
- 回滚：revert 本 PR 即恢复 Tag create 触发语义；不会回滚或改写已经发布的历史 Release/Tag。

# Completion Audit

- [x] upstream_re_read：重读 Issue #492、当前 Release Workflow、Release 运维/运行文档、最新 main 和 Agent_Skills 当前交付/CI/Review 规则。
- [x] change_coverage：AC1—AC6 均进入 Traceability；AC6 的 main-fresh 明确由 post-merge Issue Closure Owner 持有，没有从 Change Ready 中伪造删除。
- [x] reverse_audit：从网页 Release/Actions 两个正式入口反查到 main checkout、Tag/Release identity、候选 build/replay、GHCR/asset 发布分流、最终 identity verify；服务器 Bundle/Compose 路径保持。
- [x] unresolved_cleared：R1—R5 已有实现/运行证据；R6 中不可在 merge 前取得的 main-fresh/Issue Closure 已显式转交 #492 post-merge Closure Audit，无 `not_satisfied` 残留。

# 两阶段 Review

## Review A1：上游要求 → Change

- Issue #492 AC1—AC5 均被 Change 明确覆盖，没有遗漏网页 `published` 时点、最新 main、stale Tag fail-closed、workflow_dispatch 保持和 create/upload 分流。
- AC6 被拆分为 pre-merge current-head gates 与 post-merge main-fresh/Closure；后者没有被错误声明为合并前已完成。
- 非目标保持：没有强制移动 Tag、没有真实 Release 副作用、没有扩大到 Docker Runtime/业务代码/Schema/依赖。

## Review A2：Change → 实现 / 测试 / 文档

- `.github/workflows/release.yml` 的正式事件、checkout、build/publish 两次 main/tag/release 校验和发布分流与 AC 一致。
- 原离线 Bundle、checksum、GHCR private、manifest、docker load、canonical Compose replay、最终 Release asset/tag 校验均保留；run `34926618924` 已实际证明 PR dry-run 全链。
- `tests/unit/test_release_workflow.py` 已针对新事件与防漂移规则更新；current-head CI 负责执行并作为 merge gate。
- `docs/02_环境运行与部署.md`、`docs/operations/01_生产部署与离线Release方案.md` 已同步，且逐提交 diff 未发现无关文档漂移。

## 代码质量 / 测试充分性 Review

- Review 结论：`NO_FINDINGS_WITHIN_SCOPE`（基于当前实现与已取得运行证据）。
- 重点反查风险：Release event ref、main 漂移、stale Tag、Tag force/move、workflow_dispatch 递归发布、PR 模式外部副作用、离线 Bundle/Compose 回放证据降级。
- 未执行真实正式 `release: published` 外部写入 Probe：开发阶段明确禁止创建真实版本 Release/GHCR 副作用；该事件路径通过官方 GitHub 事件语义 + 机器静态回归 + PR dry-run 的共享 build/replay 链验证，正式发布时仍由同一 Workflow 的 build/publish 双重 fail-closed 门禁保护。
- 当前剩余 merge gate：PR current-head CI/required checks；失败则返回 Coding 修复并重新 Review。
