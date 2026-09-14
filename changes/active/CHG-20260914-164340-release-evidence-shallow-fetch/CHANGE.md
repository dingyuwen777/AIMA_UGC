---
schema: coding-change/v1
id: CHG-20260914-164340-release-evidence-shallow-fetch
title: 修复 Release 证据浅克隆父提交丢失
level: L3
status: ready_for_review
owner: Codex
branch: fix/release-evidence-shallow-fetch
created: 2026-09-14
updated: 2026-09-14
completion_gate: required
depends_on: []
affected_areas:
  - ci
  - release
affected_paths:
  - .github/workflows/release.yml
  - tests/unit/test_release_workflow.py
  - changes/active/CHG-20260914-164340-release-evidence-shallow-fetch/CHANGE.md
contracts:
  - Release workflow 的最新 main 校验不得破坏归档证据提交图
data_changes:
  - 无 Schema、Migration、业务数据或运行数据变化
---

# 变更摘要

修复 Release workflow 在完整 checkout 后再次执行 `git fetch --depth=1`，导致归档提交父提交从本地提交图消失、正式发布无法解析 main 必需检查证据的问题。

# 目标、范围与非目标

## 成功标准

- [x] Release #325 的失败条件由自动化回归覆盖。
- [x] 正式发布核对远程最新 `main` 时不修改本地 Git 提交图或浅克隆边界。
- [x] 严格归档提交仍能访问唯一父提交并继承该父提交的三项绿色检查证据。
- [x] `workflow_dispatch`、SemVer Tag create、PR dry-run、Tag/Release/GHCR 失败关闭与不可变候选门禁保持不变。
- [x] 目标测试、Workflow 解析和本地治理门禁通过；PR dry-run 与主分支新鲜 CI 按受保护交付顺序继续执行。

## 范围

- `.github/workflows/release.yml` 中正式发布的最新 main 校验。
- `tests/unit/test_release_workflow.py` 中浅 fetch 回归保护。
- 本 Change 的追溯、验证和交付证据。

## 非目标

- 不改变归档提交识别算法或放宽必需检查。
- 不改变版本号、Tag、Release、GHCR、Bundle、镜像或部署格式。
- 不升级 Actions、Runtime、依赖或基础镜像。
- 本次开发与合并不自动重跑 v3.1.0 Release。

## 必须保持不变

- 正式发布仍只允许最新 `main`，旧 SHA 必须失败关闭。
- PR dry-run 保持只读，publish job 只消费已经回放的同一候选。
- Tag/Release 查询只有明确 HTTP 404 才视为不存在。
- 当前发布 SHA、Tag、GitHub Release、镜像与 Manifest 身份继续一致。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 修复 Release #325 在归档 main 上无法访问父提交的问题 | #482 / AC1 | satisfied | 当前 Workflow 浅 fetch 使新增回归 Red（1 failed, 7 passed）；改为 REST ref 后目标 8 项和 Release 关联 23 项全绿；真实 API 查询前后 `c465a17 584534f` 提交图不变 |
| R2 | 完成修改并合并到主分支 | user:完成修改合并到主分支 / AC1 | explicitly_deferred | 实现和本地验证已完成并建立 PR #484；受保护合并、main 新鲜 CI、自动归档、Issue 关闭与分支清理只能在 Ready 和 current-head CI 后按顺序执行 |
| R3 | 不降低现有 Release 安全门禁且不自动重跑正式发布 | #482 / AC4 | satisfied | 只替换最新 main 的取值方式；静态回归继续断言 Tag/main/404 边界并禁止 shallow fetch，YAML 解析和独立 Review 无 Finding；本任务未创建 Tag、Release 或镜像 |

# 实施与验证计划

1. 修改 Workflow 回归断言，使当前浅 fetch 配置产生正确 Red。
2. 用 GitHub REST ref 查询替换会改变提交图的浅 fetch，保持最新 main 比较语义。
3. 运行目标测试、YAML 解析、Release/CI 专项门禁与治理检查。
4. 完成 Completion Audit、独立 Review、PR CI、受保护合并和合并后收尾。

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | Workflow 回归断言禁止正式验证步骤执行浅 fetch，并要求 REST main ref 比较 |
| 接口 / Contract | not_applicable | 不改变应用 public API、Schema、生成 Client 或数据格式 |
| 集成 / Persistence / Runtime Dependency | required | 隔离 Git 实验复现 depth=1 截断父提交；真实 GitHub API/main SHA 查询保持提交图不变 |
| 用户 / Workflow Acceptance | required | PR Release dry-run 在 GitHub Runner 完成候选构建与离线回放 |
| 跨组件 Golden Path | not_applicable | 不改变应用前后端、API、数据库或 Worker 接线 |
| External Dependency / Provider Probe | not_applicable | 不修改或调用 TikHub、LLM 等业务 Provider |
| Build / Package / Runtime | required | Release workflow YAML 解析和 PR dry-run 构建/Bundle/Compose 回放 |
| Docs / Governance / Other | required | Change Completion、Secret/Docs/Workflow 静态门禁与 main fresh CI |

# Workflow Responsibility Audit

- 正式入口仍为 `workflow_dispatch` 与 SemVer Tag create；PR 仍为只读 dry-run。
- 最新 main 校验仍负责拒绝旧 SHA，只把取值方式从会修改本地提交图的 shallow fetch 改为只读 GitHub REST ref。
- 归档证据解析、必需检查查询、GHCR 私有性、候选构建/回放和 publish 权限均不迁移、不删除、不降级。
- Evidence Preservation Mapping：`remote main SHA == RELEASE_SHA` 的原证明责任保留在 `Validate formal release request`，证据等级保持为 GitHub 当前远程 ref；本地提交图不再作为该查询的副作用对象。

# 风险、兼容、部署与回滚

- 风险：GitHub ref API 查询失败或无权限；保持 `set -euo pipefail`，任何非成功结果失败关闭。
- 兼容：不改变两个正式入口、PR dry-run、Tag/Release 身份和既有发布物格式。
- 部署：仅 GitHub Actions 控制面修复，不需要应用部署或数据迁移。
- 回滚：通过新 PR 恢复原 main 校验实现；已存在的 Tag/Release/镜像不自动删除或覆盖。

# Completion Audit

- [x] upstream_re_read：已重读用户要求、#482、Release #325、当前 Workflow、前一归档证据 Change 和 Release Contract；#325 的 `Validate formal release request` 成功后才在证据解析失败，与浅 fetch 副作用一致。
- [x] change_coverage：已逐项覆盖浅克隆根因、最新 main 语义、既有安全门禁、回归验证和受保护合并交付；未扩大到版本、镜像、Bundle、依赖或业务运行时。
- [x] reverse_audit：已从 `workflow_dispatch`、Tag create 和 PR dry-run 反查 checkout → main 校验 → 归档证据 → 必需检查 → 候选 → publish；publish 的第二次 main ref 复核与新实现一致。
- [x] unresolved_cleared：R1/R3 已满足，R2 的 post-Ready 外部交付按门禁显式延期；所有 required 本地层有新鲜证据，PR Runner 与 main fresh 证据将在对应阶段取得。

# 两阶段 Review

## Review A1：上游要求 → Change

独立重建 #482 AC1/AC4、用户合并要求和 Release #325 失败链路后，当前缺口不是归档继承算法，而是正式校验步骤在完整 checkout 后执行 `--depth=1`，把当前归档提交标成浅边界并隐藏唯一父提交。Change 已覆盖：消除本地提交图副作用、保留远程最新 main 比较、保持既有失败关闭和按受保护流程合并；没有把任意旧提交或缺失检查扩大为合法发布证据。

## Review A2：Change → 实现、测试与文档

Review Target 为 `origin/main@c465a17...HEAD@b402b779`，模式为已授权 review-and-fix。实现只把正式验证中的 shallow fetch/FETCH_HEAD 比较替换为 GitHub REST ref SHA 比较，复用 publish 阶段既有模式；`set -euo pipefail` 和 `contents: read` 使 API/权限/网络异常继续失败关闭。回归测试同时要求 REST main ref 比较并禁止 shallow fetch；目标 8 项、Release 关联 23 项、Ruff 与 YAML 解析通过，真实 GitHub ref 查询前后唯一父提交保持可见。当前 Operations 文档描述的是既有手工 Tag/Release 契约，未描述内部取值实现，因此无需修改。范围内未发现 BLOCKER/HIGH/MEDIUM/LOW Finding；PR Runner dry-run、current-head required CI 与 main fresh CI 尚待对应交付阶段验证。
