---
schema: coding-change/v1
id: CHG-20260915-113043-release-latest-main
title: Release 发布绑定发布时最新 main
level: L3
status: in_progress
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

- [ ] GitHub Release 页面真正 `published` 时才进入网页正式发布链；单独创建 Tag 不再构建正式镜像。
- [ ] 网页正式发布与 `workflow_dispatch` 的正式候选源码都显式来自发布开始时最新 `main`，构建前和发布前均检查 `main` 没有漂移。
- [ ] 网页 Release Tag 必须精确指向候选 SHA；旧 Tag / 非 main Tag fail closed，绝不移动或覆盖版本 Tag。
- [ ] `workflow_dispatch` 继续允许 Workflow 创建新 Tag/GitHub Release；网页 `release: published` 对已存在的 Release 只上传 replay-tested assets。
- [ ] PR dry-run 继续真实构建 Linux/AMD64 Backend/Frontend、生成离线 Bundle 并用 `--no-build --pull never` 回放。
- [ ] Release 单元测试、文档/Secret/治理门禁、PR required checks、合并与 main-fresh CI 全部通过。

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
| R1 | Release 网页路径只在真正 published 时进入正式发布，单独 Tag create 不再发布 | #492 / AC1 | not_satisfied | 待实现与验证 |
| R2 | 正式网页发布使用发布时最新 main，并在构建前/发布前防漂移 | #492 / AC2 | not_satisfied | 待实现与验证 |
| R3 | Release Tag 必须精确等于候选 main SHA；旧 Tag fail closed 且不自动移动 | #492 / AC3 | not_satisfied | 待实现与验证 |
| R4 | workflow_dispatch 与 PR dry-run 保持现有正式/验证能力 | #492 / AC4 | not_satisfied | 待回归验证 |
| R5 | release.published 上传既有 Release assets；workflow_dispatch 继续创建 Release；所有发布身份同 SHA | #492 / AC5 | not_satisfied | 待实现与验证 |
| R6 | Release 单测、文档/治理、PR CI、main-fresh 全部闭环 | #492 / AC6 | not_satisfied | 待交付证据 |

# 实施计划

1. 修改 Release Workflow：`create` → `release: published`；正式候选 checkout 显式使用 `main`，PR dry-run 保持 PR revision。
2. 把 release event 的版本身份改为 `github.event.release.tag_name`；正式校验分别处理 `workflow_dispatch` 与 `release`。
3. 网页 Release 路径要求现有 Release/Tag 均存在且 Tag=current main；`workflow_dispatch` 继续要求同名 Release 不存在、Tag 不存在或精确匹配。
4. publish 阶段再次核验 main/tag；网页 Release 用 `gh release upload`，Actions 正式入口继续 `gh release create --target RELEASE_SHA`。
5. 更新 Release 静态回归测试和两份当前操作文档。
6. 执行 targeted unit/文档/治理验证，完成 Completion Audit 与独立 Review，再走 PR required CI、最新 main freshness、guarded merge 和 main-fresh 收尾。

# Validation Matrix

| 验证层 | 是否要求 | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | `tests/unit/test_release_workflow.py` 覆盖 release.published、main checkout、Tag/main 一致性和 create/upload 分流 |
| 接口 / Contract | required | Release identity invariant：Tag/main/manifest/image SHA 单一；workflow event/发布入口语义不漂移 |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不改数据库、文件持久化、Worker 或服务器 Runtime dependency |
| 用户 / Workflow Acceptance | required | GitHub Actions PR Release dry-run 对修改后的 workflow 完成实际候选构建/回放；正式发布副作用不在开发阶段执行 |
| 跨组件 Golden Path | required | Release dry-run：Docker build → images.tar → docker load → canonical Compose `--no-build --pull never` → readiness/migration smoke |
| External Dependency / Provider Probe | not_applicable | 不修改 TikHub/LLM/第三方业务 Provider；GitHub 平台语义以官方文档和 Actions CI 为证据 |
| Build / Package / Runtime | required | PR Release Workflow 真实构建 Linux/AMD64 Backend/Frontend 与离线部署包并回放 |
| Docs / Governance / Other | required | Change Completion、Release 单测、docs/secret/governance gates、PR required checks、main-fresh CI |

# Evidence Preservation Mapping

| 原证明责任 | 原位置 | 新位置 | 证据等级 | 依据 |
| --- | --- | --- | --- | --- |
| PR Release dry-run 构建/离线回放 | `build-verify` PR 路径 | 保持原 `build-verify` PR 路径 | 保持 | 不改变 PR dry-run 构建、Bundle、docker load、Compose replay 步骤 |
| 正式发布只使用当前 main | Tag create 校验 `CURRENT_MAIN_SHA == RELEASE_SHA` | release.published / workflow_dispatch 均显式 checkout main，并在 build/publish 两阶段复核 | 加强 | 检查时间从 Tag 创建推进到 Release 发布，并保留二次防漂移 |
| Tag 与候选 SHA 一致 | build/publish 两阶段 Tag target 检查 | 保持双阶段检查 | 保持/加强 | release.published 要求已存在 Tag；workflow_dispatch 仍可无 Tag 后由 release create 建立 |
| 离线候选不可变传递 | Actions artifact + SHA256SUMS | 保持 | 保持 | publish job 继续只消费 replay-tested artifact |
| Release asset 完整性 | `gh release create` + verify | workflow_dispatch create；release.published upload；统一 verify | 保持 | 两种正式入口最终验证相同 asset 集合和 tag target |

# 风险、兼容、部署与回滚

- 风险：网页 Release 若引用提前创建且已经落后的 Tag，会在正式构建前 fail closed；这是目标行为，避免旧代码镜像。
- 风险：`release: published` 事件发生时 GitHub Release 已可见，资产在 Workflow 成功后才出现；失败时不会上传错误镜像，需要维护者修正 Tag/版本后重新发布。
- 兼容：现有 `workflow_dispatch` 和 PR dry-run 保留；服务器 Bundle/Compose/镜像标签格式保持。
- Migration/Data：无。
- 部署：本任务只修改发布流水线，不直接部署生产服务器。
- 回滚：revert 本 PR 即恢复 Tag create 触发语义；不会回滚或改写已经发布的历史 Release/Tag。

# Completion Audit

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# 两阶段 Review

待实现与新鲜验证完成后补充 Review A1/A2、测试充分性、Findings 与最终交付边界。
