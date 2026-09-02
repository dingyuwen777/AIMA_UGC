---
schema: coding-change/v1
id: CHG-20260902-u4-analysis-scheme
title: U4 Analysis Scheme 原子版本与生产切换
level: L3
status: in_progress
owner: codex
branch: main
created: 2026-09-02
updated: 2026-09-02
completion_gate: required
depends_on: [CHG-20260902-u3-admin-identity-config]
affected_areas: [analysis, identity, api, worker, contracts, frontend, documentation]
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

- [x] upstream_re_read
- [x] change_coverage
- [x] reverse_audit
- [ ] unresolved_cleared

当前未清零项：Scheme 编译/Contract/前端已验证，但真实 PostgreSQL 下的 bootstrap、并发发布、Migration、Worker 冻结与 Real Full-stack 仍受本机 Docker/PostgreSQL 不可用阻塞；Gold Set、双人审批不在第一版范围。本 Change 保持 `in_progress`。

# 本轮验证证据

- API/Contract/Unit 受支持范围：`866 passed, 8 skipped, 0 failed`；生成后 Contract 专项 `101 passed`；
- Scheme 编译、受控 Taxonomy、显式 unknown、发布/回滚 Contract、Run 冻结身份和人工分维度锁的代码/测试/文档已反向核对；
- 管理员 Scheme 草稿、发布、回滚和审计 UI 已通过 ESLint/typecheck、前端 `67 passed` 与 production build；
- Alembic 静态 head 是 `20260902_0036`；并发 active 唯一性、审计事务和 Worker 真实冻结执行仍须 PostgreSQL/Full-stack 证据。
