---
schema: coding-change/v1
id: CHG-20260902-u4-analysis-scheme
title: U4 Analysis Scheme 原子版本与生产切换
level: L3
status: done
owner: codex
branch: test/294-vp5-u1-u5-runtime-validation
created: 2026-09-02
updated: 2026-09-02
completion_gate: required
depends_on:
  - CHG-20260902-u3-admin-identity-config
affected_areas:
  - analysis
  - identity
  - api
  - worker
  - contracts
  - frontend
  - documentation
affected_paths:
  - backend/src/aima_ugc/modules/analysis/
  - backend/src/aima_ugc/bootstrap/
  - backend/src/aima_ugc/contracts/administration.py
  - backend/src/aima_ugc/contracts/http.py
  - migrations/versions/
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/
  - frontend/src/features/admin-configuration/
  - tests/
  - docs/
contracts:
  - Analysis Scheme draft/validate/publish/rollback
  - Analysis Run frozen scheme identity
data_changes:
  - analysis_schemes
  - analysis_scheme_versions
  - analysis_content_runs.analysis_scheme_version_id
---

# 背景、目标与边界

把 relevance、情感、voice_type、标签、Prompt 模板与 Validator 配置作为一个版本化 Analysis Scheme 原子治理。结构化配置是主事实，Prompt 只通过受控占位符引用；发布与回滚整体生效，新 Run 冻结 Scheme Version，旧 Run 继续按原身份执行。Git Prompt 仅用于首个数据库 Scheme bootstrap/灾备，不再与数据库形成双写主事实。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Prompt 与 voice_type、情感、标签作为一个耦合配置单元 | user:前序确认 + docs/roadmap/04_业务目录内容查询与AI配置中心实施路线.md | satisfied | Analysis Scheme Version |
| R2 | 允许无法判断，不把未知静默映射成中性或其他既有分类 | user:2026-09-02-recommended-decisions | satisfied | Validator 与 Scheme 校验 |
| R3 | 编辑/发布后端权限检查；不强制双人审批；变更必须审计 | user:2026-09-02-approval-decision | satisfied | administrator guard + audit |
| R4 | Run 冻结 Scheme，发布只影响新 Run | docs/roadmap/04_业务目录内容查询与AI配置中心实施路线.md | satisfied | nullable 兼容身份 + 新 Run version FK |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | Scheme 校验、受控模板、发布冲突、回滚与冻结 |
| 接口 / Contract | required | Scheme API、Run additive identity、generated client |
| Backend/API/PostgreSQL | required | 单一 active、审计原子性、Run FK/旧数据兼容 |
| Browser Mock Acceptance | required | 草稿/校验失败/发布/回滚/权限态 |
| Real Full-stack Golden Path | required | 发布 Scheme→新 Run 冻结→旧 Run 不变 |
| External Provider Probe | not_applicable | 不需要真实 LLM 调用证明配置治理 |
| Build / Runtime | required | API/Worker/frontend 构建与启动 |
| Docs / Governance / Other | required | Prompt 主事实切换、部署/回滚说明 |

# Completion Audit

- [x] upstream_re_read：已重新读取 Scheme 耦合配置、发布审计决定、路线、Contract、Schema、实现与最终验证事实。
- [x] change_coverage：Prompt、Taxonomy、校验、发布、回滚、Run 冻结和审计均有实现与测试证据。
- [x] reverse_audit：已从管理员操作与 Analysis Run 结果反查权限、数据库原子性和 Worker 冻结身份。
- [x] unresolved_cleared：Gold Set 与双人审批按确认范围延期，其余 Required 项均满足，无 `not_satisfied`。

当前无语义未决项：本地 required 验证与独立 Review 已完成，Gold Set、双人审批不在第一版范围。

# 本轮验证证据

- API/Contract/Unit 受支持范围：`866 passed, 8 skipped, 0 failed`；生成后 Contract 专项 `101 passed`；
- Scheme 编译、受控 Taxonomy、显式 unknown、发布/回滚 Contract、Run 冻结身份和人工分维度锁的代码/测试/文档已反向核对；
- 管理员 Scheme 草稿、发布、回滚和审计 UI 已通过 ESLint/typecheck、前端 `67 passed` 与 production build；
- PostgreSQL 18.4 空库及既有 `0037` 开发库均真实升级到 `0038`；Schema 重编译生命周期测试、单一 active、审计事务和 Worker Run 冻结均已通过；
- Real Full-stack 已证明“发布 Scheme→新 Run 冻结新版本→旧 Run 身份与终态不变”；只使用本机假 LLM，不把它写成真实模型质量证据。

# 交付完成证据

- PR #289 已把 U1–U5 前端与文档接线合并到 `main`（merge commit `b5622e2308193da4bb6878672944f38938bf46d5`）；PR #295 又完成恢复验证与基线修复（merge commit `f60f598c84e0696873cc01fc30f4d817ed51ae52`）；
- `main` 的 CI run #33589659720 与 Runtime Acceptance run #33589659537 均成功，覆盖产品、PostgreSQL、真实浏览器和 Compose 门禁；
- 本 Change 的实现、验证、Review、合并与 main 新鲜验证已闭环，因此转为 `done` 并归档。
