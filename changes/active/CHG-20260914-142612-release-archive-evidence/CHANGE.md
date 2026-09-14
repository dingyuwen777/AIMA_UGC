---
schema: coding-change/v1
id: CHG-20260914-142612-release-archive-evidence
title: 修复手工 Tag 与归档提交 Release 门禁
level: L3
status: in_progress
owner: Codex
branch: fix/release-archive-evidence
created: 2026-09-14
updated: 2026-09-14
completion_gate: required
depends_on: []
affected_areas:
  - ci
  - release
  - docs
affected_paths:
  - .github/workflows/release.yml
  - scripts/quality/release_evidence.py
  - tests/unit/test_release_evidence.py
  - tests/unit/test_release_workflow.py
  - tests/unit/test_docker_build_sources.py
  - docs/02_环境运行与部署.md
  - docs/operations/01_生产部署与离线Release方案.md
  - changes/active/CHG-20260914-142612-release-archive-evidence/CHANGE.md
contracts:
  - Release workflow 的正式触发、Tag 身份和主分支检查证据门禁
data_changes:
  - 无 Schema、Migration、业务数据或运行数据变化
---

# 变更摘要

修复自动 Change 归档提交携带 `[skip ci]` 后，正式 Release 无法在当前 `main` 找到三项必需检查的问题；同时保留 Actions 手工输入版本入口，并增加手工推送标准 SemVer Tag 触发同一正式发布链路。

# 目标、范围与非目标

## 成功标准

- [ ] Actions 手工输入 `vMAJOR.MINOR.PATCH` 仍可从最新 `main` 构建候选、创建 Tag 和 GitHub Release。
- [ ] 手工推送指向最新 `main` 的标准 SemVer Tag 后，以不受 `[skip ci]` 影响的 Tag create 事件触发同一正式发布链路。
- [ ] 当前发布提交已有完整必需检查时只使用当前提交证据。
- [ ] 当前发布提交三项检查全部缺失且被严格证明为单一 Change 的确定性归档提交时，才继承唯一父提交的绿色证据。
- [ ] 部分缺失、失败检查、伪造归档消息、正文篡改、额外文件、错误 Tag SHA、重复 Release 均 fail closed。
- [ ] 目标单元测试、Release workflow 回归、文档与治理检查通过。

## 范围

- GitHub Release workflow 的正式触发和检查证据解析。
- 可单元测试的归档证据解析脚本及回归测试。
- 正式 Release 操作说明。

## 非目标

- 不允许发布非最新 `main`、任意旧 SHA 或非 SemVer Tag。
- 不覆盖、移动或删除已有 Tag/Release。
- 不绕过失败、取消、进行中或部分缺失的 required checks。
- 不改变镜像、Bundle、GHCR 可见性、Manifest、Compose、Migration 或生产部署语义。
- 本地实现阶段不创建真实 Tag、GHCR 镜像或 GitHub Release。

## 必须保持不变

- PR dry-run 保持只读，不获得 `contents: write` 或 `packages: write`。
- 正式发布仍先构建并离线回放候选，publish job 只消费同一候选。
- 当前 `main`、Tag、Release SHA 与最终 Manifest 必须一致。
- 已有版本身份不可覆盖，真实发布仍须用户单独授权和手工触发。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 修复 Release #321 因自动归档提交缺少同 SHA 检查而失败 | user:2026-09-14-release-321 | not_satisfied | 待实现严格归档证据继承并完成回归 |
| R2 | 用户可以手工建立标准 Tag 并 Release 一个版本 | user:2026-09-14-manual-tag-release | not_satisfied | 待增加 Tag create 正式触发与 main/Tag 身份校验 |
| R3 | Actions 手工输入版本的既有入口继续可用 | docs/operations/01_生产部署与离线Release方案.md | not_satisfied | 待保持 workflow_dispatch 并覆盖兼容回归 |
| R4 | 不降低 main、CI、GHCR、重复版本和不可变候选安全门禁 | AGENTS.md / release.yml | not_satisfied | 待完成失败路径测试和实现复核 |

# 实施与验证计划

1. 增加 Release workflow 与归档证据解析失败回归，取得 Red。
2. 实现严格的当前 SHA / 确定性归档父提交证据选择，并接入 Release gate。
3. 增加 SemVer Tag push 正式触发，保持 workflow_dispatch 与 PR dry-run 兼容。
4. 同步 Operations 文档，运行目标测试、质量检查、Completion Audit 与两阶段 Review。

# 验证矩阵

| 验证层 | 是否要求 | 范围 |
| --- | --- | --- |
| Unit | required | 检查集合选择、归档父提交验证、篡改与额外文件拒绝 |
| Workflow static / semantic | required | 触发器、权限、版本/Tag/main、候选复用与发布身份 |
| Release dry-run | required_after_pr | GitHub Runner 构建、离线 Bundle 和 canonical Compose 回放 |
| Contract / API / PostgreSQL | not_applicable | 不修改业务 Contract、API、Schema 或数据 |
| External Provider | not_applicable | 不修改或调用 TikHub/LLM |
| Docs / Governance | required | Operations、Change、Secret/Docs/Completion 检查 |

# 风险、兼容、部署与回滚

- 风险：伪造普通提交冒充归档提交继承旧证据；通过精确消息、唯一父提交、严格两路径 diff 和生命周期全文确定性比较 fail closed。
- 风险：Tag 指向旧提交或被移动；正式构建和 publish 前均复核 Tag/当前 main/候选 SHA。
- 兼容：保留 workflow_dispatch 和 PR dry-run；不修改业务、依赖、Schema、镜像或 Bundle 格式。
- 部署：仅 GitHub Actions 发布控制面变化，不需要应用部署或数据迁移。
- 回滚：撤销 workflow、helper、测试和文档；已存在 Tag/Release 不由回滚自动删除。

# Completion Audit

- [ ] upstream_re_read：Ready 前重读用户要求、Release #321 原始失败、当前 Workflow、Operations 与归档实现。
- [ ] change_coverage：逐项映射手工 Tag、workflow_dispatch、归档证据继承和失败关闭边界。
- [ ] reverse_audit：从两个正式触发入口反查 main/Tag/检查/候选/发布身份，从 publish 动作反查授权与不可变候选。
- [ ] unresolved_cleared：Requirement Traceability 无 `not_satisfied`，不适用层有范围依据。

# 两阶段 Review

## Review A1：上游要求 → Change

待实现完成后独立重建。

## Review A2：Change → 实现、测试与文档

待实现完成后独立审查。
