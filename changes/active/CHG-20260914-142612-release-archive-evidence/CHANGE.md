---
schema: coding-change/v1
id: CHG-20260914-142612-release-archive-evidence
title: 修复手工 Tag 与归档提交 Release 门禁
level: L3
status: ready_for_review
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
  - frontend/e2e/voice-plaza-media-carousel.spec.ts
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

- [x] Actions 手工输入 `vMAJOR.MINOR.PATCH` 仍可从最新 `main` 构建候选、创建 Tag 和 GitHub Release。
- [x] 手工推送指向最新 `main` 的标准 SemVer Tag 后，以不受 `[skip ci]` 影响的 Tag create 事件触发同一正式发布链路。
- [x] 当前发布提交已有完整必需检查时只使用当前提交证据。
- [x] 当前发布提交三项检查全部缺失且被严格证明为单一 Change 的确定性归档提交时，才继承唯一父提交的绿色证据。
- [x] 部分缺失、失败检查、伪造归档消息、正文篡改、额外文件、错误 Tag SHA、重复 Release 均 fail closed。
- [x] 目标单元测试、Release workflow 回归、文档与治理检查通过。
- [x] PR required CI 不再被轮播截图中的非正式平台缩写阻塞。

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
| R1 | 修复 Release #321 因自动归档提交缺少同 SHA 检查而失败 | #482 / AC1 | satisfied | `release_evidence.py` 严格识别确定性归档；真实 `cefbcfb` 解析到唯一父提交 `6ff41bc6`，父提交三项检查均为 success |
| R2 | 用户可以手工建立标准 Tag 并 Release 一个版本 | #482 / AC2 | satisfied | `create` Tag 事件进入正式链路；构建前和发布前均校验 SemVer、最新 main、Tag 目标及重复 Release；Operations 给出手工命令 |
| R3 | Actions 手工输入版本的既有入口继续可用 | #482 / AC3 | satisfied | 保留 `workflow_dispatch` 身份解析、最新 main 校验及缺少 Tag 时由 `gh release create --target` 创建 Tag 的既有路径；静态回归覆盖 |
| R4 | 不降低 main、CI、GHCR、重复版本和不可变候选安全门禁 | #482 / AC4 | satisfied | 49 项 Release/CI/Docker/归档专项测试通过；Tag/Release 查询仅明确 HTTP 404 才视为不存在，其他 API 异常 fail closed |
| R5 | 清除阻塞本 PR 的轮播截图非正式平台缩写，不改变 E2E 行为 | #482 / AC5 | satisfied | 截图产物改为 `xiaohongshu-media-carousel-navigation.png`；干净 tracked snapshot 中平台标识 Contract 13 项通过 |

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

- [x] upstream_re_read：已重读 #482、用户要求、Release #321 原始失败、当前 Workflow、Operations、归档实现和 CI run 34817799145 的平台标识失败。
- [x] change_coverage：已逐项映射手工 Tag、workflow_dispatch、归档证据继承、失败关闭边界和最小 CI unblock。
- [x] reverse_audit：已从两个正式触发入口反查 main/Tag/检查/候选/发布身份，从 publish 动作反查授权与不可变候选，并确认截图改名不改变 E2E 行为。
- [x] unresolved_cleared：Requirement Traceability 无 `not_satisfied`，不适用层有范围依据；PR Runner dry-run 和全量 CI 在最新提交推送后重跑。

# 两阶段 Review

## Review A1：上游要求 → Change

重读 #482、用户本轮“手工建 Tag 并 Release”要求、Release #321 失败事实和 Ready CI run 34817799145 后，独立重建为五项边界：手工 Tag 必须成为正式入口、既有 Actions 手工入口不能回归、归档提交只能继承严格可证明的父提交证据、所有既有发布安全门禁必须保留、轮播 E2E 诊断产物必须使用正式平台标识。R1–R5 已覆盖上述边界，没有把任意 `[skip ci]`、旧 main 或非正式平台别名扩展为合法发布事实。

## Review A2：Change → 实现、测试与文档

逐层复核结果：Workflow 仅接受 `workflow_dispatch` 或 Tag `create`，分支 create 在 Job 分配前跳过；两个正式入口都绑定最新 `main`，已有 Tag 必须精确指向候选 SHA，Tag/Release 查询异常和重复 Release 均失败关闭；publish 仍只消费已回放候选且保持最小写权限。证据 helper 只允许当前 SHA 的完整检查，或严格两路径、单父、确定性生命周期冻结的归档提交继承父证据。Operations 文档与实现一致。独立审查发现并修复 Release 存在性查询的非 404 异常误判；Ready CI 又发现并最小修正轮播截图文件名中的 `xhs` 别名，E2E 逻辑未改。修复后 Release 专项 49 项、Ruff、YAML 解析和干净 tracked snapshot 平台标识 Contract 13 项通过；最终治理门禁与 GitHub CI 在最新提交上复验。
