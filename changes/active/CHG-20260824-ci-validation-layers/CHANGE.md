---
schema: rvc-change/v1
id: CHG-20260824-ci-validation-layers
title: CI 按长期验证层收敛
level: L3
status: ready_for_review
owner: aima
branch: refactor/ci-validation-layers
created: 2026-08-24
updated: 2026-08-24
completion_gate: required
depends_on: []
affected_areas:
  - ci
  - testing
  - runtime
  - release
affected_paths:
  - .github/workflows/
  - docs/blueprint/06_开发约束与分阶段实施.md
  - docs/roadmap/02_生产上线实施路线.md
  - docs/04_测试与调试说明.md
contracts: []
data_changes: []
---

# 目标

不降低任何当前有效测试能力，把按历史 Stage 拆分的 GitHub Actions CI 收敛成按长期风险/验证层组织的永久门禁，显著减少重复 Runner、PostgreSQL Service、`uv sync`、Ruff/mypy 和重复 Integration Test，同时保持 Runtime、Full-stack、Change Gate 与 Release 的独立证明边界。

# 成功标准

- [x] 删除只承担历史 Stage/Audit 验收外壳的永久 Workflow；仓库 Workflow 从 19 个收敛到 7 个长期职责 Workflow。
- [x] `ci.yml` 不再按 Stage 命名，统一为 Repository Quality、PostgreSQL Integration、Windows Tooling 与稳定汇总 `CI Gate`。
- [x] Unit、Contract、API、Frontend Unit/Build/Browser Mock、Ruff、mypy、架构/Owner/Secret/Docs、Wheel 构建等质量门禁只保留一套有效执行链，不因删除 Stage Workflow 丢失覆盖。
- [x] PostgreSQL Integration 在一个隔离 PostgreSQL 18 Runner 中覆盖 `platform/database/jobs/collection/content/ingestion` 全部现有 Integration 目录，并保留旧 Workflow 中仍有独立价值的 Schema/Constraint/Trigger 与 Migration compatibility 断言。
- [x] Stage 8F 真实 Full-stack 能力保留但改为长期职责命名；Local Dev、Linux canonical Compose、Windows Docker Desktop Runtime、Change Completion Gate、Release 仍分别保留独立证据边界。
- [x] Release 的 main CI 前置检查从历史 `Stage 1` check 改为稳定 `CI Gate`，不降低 Release fail-closed 行为。
- [x] 仅文档/Change 变动不再作为高成本 Runtime/Full-stack Workflow 的独立触发理由；代码、配置或 Workflow 变动仍保持运行验证。
- [x] 正式测试/开发/Roadmap 文档不再把永久 CI 导航建立在历史 Stage Workflow 名称上。

# 范围

- 重构 `.github/workflows/ci.yml` 的 Job 组织、重复测试执行与 Check 名称。
- 删除 Stage 4、Stage 5A/5B/5C/5D、Stage 6、Stage 7 各历史永久 Workflow，以及一次性 Stage 1-7 Audit Workflow。
- 将 `stage8f-fullstack.yml` 重命名为长期 `fullstack.yml`，保持真实 Browser → API → PostgreSQL → Worker Golden Path。
- 对 Local Dev、Internal V1-A、Windows Compose、Full-stack 增加只忽略纯文档/Change 变动的安全触发优化。
- 更新 `release.yml` 对正式 main CI check 的依赖名称。
- 同步与永久 CI/Full-stack 入口直接相关的开发流程、测试和 Roadmap 文档。

# 非目标

- 不修改业务代码、公共 HTTP/Canonical Contract、数据库 Schema/Migration 或前端产品行为。
- 不删除 Runtime、Full-stack、Change Completion Gate 或 Release 的有效验证能力。
- 不把真实 TikHub Provider Probe 放进普通 CI。
- 不在本 Change 引入新的第三方 Action、CI SaaS、缓存服务或依赖升级。
- 不配置 GitHub Branch Protection/Ruleset；其 required checks 是独立仓库治理动作，本 Change 只提供稳定 check 名称。

# 必须保持不变

- PostgreSQL Integration 继续使用真实 `postgres:18.4`，不得用 SQLite/Fake 替代。
- Unit/Contract/API/Browser Mock/Real Full-stack/Runtime/Release 各层只能声明其实际运行边界。
- 现有 Migration 历史不修改；有独立价值的 downgrade/upgrade compatibility 检查必须继续存在。
- `Change Completion Gate` 的 Requirement Traceability / Ready Check 行为不改变。
- `release.yml` 继续只允许当前 `main` 最新 SHA 正式发布，现有 Tag/Release 防覆盖、离线 Bundle replay 和权限隔离不改变。
- 并行业务 Change 的业务/Contract/前端实现不由本 Change 修改。

# 关键决策

## L3 方案比较

### 方案 A：保留 19 个 Workflow，只加 `paths` / cache

优点：迁移最少；历史 Stage 证据原样存在。缺点：Stage 4—7 已经成为历史，Ruff/mypy/Unit/Contract/Integration 仍被多次执行；Runner 和 PostgreSQL 重复成本的根因没有消失，也继续强化“Stage 名称=长期架构”的错误导航。

### 方案 B：按验证层收敛历史 Stage CI，保留独立 Runtime/Full-stack/Release 边界（采用）

把普通代码质量和 PostgreSQL Integration 收回 `ci.yml`，历史 Stage Workflow 删除；Runtime、Full-stack、Change Gate、Release 因证明边界、权限或环境不同继续独立。这样减少真正重复执行，而不是单纯减少 YAML 文件数量。

### 方案 C：所有检查合并成一个巨型 Workflow/单一 Runner

文件数量最少，但 Windows/Linux、Compose、Full-stack、Release 权限与普通 CI 生命周期不同；强行合并会放大失败域、延长单 Runner 串行时间，并让 Release 写权限与普通只读 CI 边界变差，因此不采用。

用户于 2026-08-24 明确要求“不降低任何有效测试能力，把按历史 Stage 组织的 CI 收敛成按长期风险/验证层组织的 CI，并显著减少重复 Runner、重复 PostgreSQL、重复 uv sync、重复 Ruff/mypy、重复 Integration Test”，据此采用方案 B。

## PostgreSQL Suite 隔离策略

历史 Stage Workflow 为每个阶段启动独立 PostgreSQL Service，因此天然提供测试数据隔离。合并成一个 PostgreSQL Runner 后，第一次 CI 暴露了真实交叉污染：前一个 Integration suite 留下 `processing_import_batches → jobs` 外键引用，使后续 `tests/integration/jobs` 的 `DELETE FROM jobs` 被 PostgreSQL 正确拒绝。

采用的修复不是重新拆 Runner，而是在 `tests/integration/conftest.py` 中恢复“每个 Integration pytest 进程从空业务数据开始”的边界：

- 仅 `GITHUB_ACTIONS=true` 时生效；
- 仅允许 `127.0.0.1/localhost`；
- 必须匹配专用 CI PostgreSQL credential；
- 保留 `alembic_version`，对其余业务表执行 `TRUNCATE ... RESTART IDENTITY CASCADE`；
- 本地/手工 Integration 运行不改变数据库生命周期。

因此仍只需要一个 PostgreSQL 18 Service 和一次 `uv sync`，但不会把原来独立 Runner 所提供的数据隔离能力丢掉。

## 迁移 / 部署 / 回滚

- 无数据库或业务 Migration；CI 配置随 PR 合并生效。
- 删除历史 Workflow 前，已把其独有断言映射到统一 `PostgreSQL Integration`；重复执行本身不作为独立能力保留。
- Release 只改 required check 名称引用，从 `Stage 1` 切换为 `CI Gate`；其他发布语义不变。
- 回滚可整体 revert 本 Change，恢复旧 Workflow 和旧 check 名称；不涉及生产数据回滚。

# 历史 Workflow → 长期验证层覆盖映射

| 历史 Workflow | 有效能力 | 新长期入口 |
| --- | --- | --- |
| `stage4-job-runtime.yml` | Job Unit、PostgreSQL Job Runtime、base/`20260813_0001` Migration round-trip | Repository Quality；PostgreSQL Integration；`verify_migration_compatibility.py` |
| `stage5a-provider-raw.yml` | P1/Provider/Raw Unit+Contract、Contract drift、Ruff/mypy/架构/Owner/Secret/Docs、Collection Raw integration | Repository Quality 全量 Unit/Contract/质量门禁；PostgreSQL Integration Collection |
| `stage5b-collection-execution.yml` | Collection Unit/PG Integration、Run/Scope FK/Unique/Index、base/`20260814_0002` | Repository Quality；PostgreSQL Integration；`test_schema_runtime_invariants.py`；Migration compatibility |
| `stage5c-provider-persistence.yml` | Provider Request/Attempt FK/Unique/Check/Index/Trigger、Collection PG、base/`20260814_0003` | PostgreSQL Integration；Schema invariants；Migration compatibility |
| `stage5d-provider-dispatch.yml` | Dispatch Check/Trigger Function、Nonretryable/Coverage/Recovery PG、Migration `0004→head`、特定 Migration Ruff | PostgreSQL Integration 全 Collection；Schema invariants；Migration compatibility；Repository Quality Ruff |
| `stage6-xiaohongshu-vertical-slice.yml` | Collection/Content Unit+PG、`0005/0006/0008/0015/base→head`、质量门禁 | Repository Quality；PostgreSQL Integration Collection+Content；Migration compatibility |
| `stage7-keyword-packs.yml` | Keyword Unit/Repository、`0010/base→head`、质量门禁 | Repository Quality；PostgreSQL Integration Database；Migration compatibility |
| `stage7-plan-occurrence-run-snapshot.yml` | Plan Unit/Repository、`0012/base→head`、Migration `0013` Ruff | Repository Quality；PostgreSQL Integration Collection；Migration compatibility；Repository Quality Ruff |
| `stage7-provider-config-routing.yml` | Routing/Contract、Provider Config Repository、`0009/base→head` | Repository Quality；PostgreSQL Integration Database；Migration compatibility |
| `stage7-scheduler-runtime.yml` | Scheduler Unit、Planning/Scheduler PostgreSQL、`0013/base→head`、Migration `0014` Ruff | Repository Quality；PostgreSQL Integration Collection；Migration compatibility；Repository Quality Ruff |
| `stage7-tikhub-real-shape.yml` | Sanitized/real-shape Fixture Unit 与质量检查；不包含真实付费 Provider 调用 | Repository Quality 全量 Unit + Ruff/mypy/Secret；真实 Provider Probe 仍按条件式策略独立执行 |
| `stage1-stage7-audit-correctness.yml` | Content Audit 与 Pending Raw Recovery 两条 PostgreSQL 回归 | PostgreSQL Integration Content + Collection |

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 不降低任何有效测试能力 | user:2026-08-24-ci-convergence | satisfied | 上述逐 Workflow 双向覆盖映射；核心实现 HEAD `d10946881dd55b69b9229d99c8a2349e90c9f01b` 上 CI/Runtime/Full-stack/Release dry-run 均有成功新鲜证据 |
| R2 | 历史 Stage CI 改为按长期风险/验证层组织 | user:2026-08-24-ci-convergence | satisfied | `.github/workflows/` 已只有 7 个长期职责 Workflow；`ci.yml` 使用 Repository Quality / PostgreSQL Integration / Windows Tooling / CI Gate，真实 Full-stack 使用 `fullstack.yml` |
| R3 | 显著减少重复 Runner/PostgreSQL/uv/Ruff/mypy/Integration | user:2026-08-24-ci-convergence | satisfied | 19 个 Workflow 收敛为 7 个；历史 Stage PostgreSQL Runner 统一为一个 `postgres:18.4` Integration Runner；Ruff/mypy/Unit/Contract/Integration 由长期层单次执行，不再按 Stage 重复 |
| R4 | 各测试层只证明实际边界，Real Full-stack/Provider Probe 不与普通 CI 混淆 | docs/blueprint/06_开发约束与分阶段实施.md | satisfied | Browser Mock 仍在 Repository Quality；真实 Excel Browser→API→PostgreSQL→Worker 仍由独立 `fullstack.yml` 证明；本 Change 未发起真实 Provider Probe |
| R5 | PostgreSQL 真实语义、Migration 与数据库约束继续由 PostgreSQL Integration 验证 | .agents/skills/reliable-vibe-coding/references/testing-strategy.md | satisfied | `postgres:18.4` + 全部 Integration 目录 + `test_schema_runtime_invariants.py` + `verify_migration_compatibility.py`；CI run `32716699870` 成功 |
| R6 | Release/Runtime/Change Gate 不因 CI 收敛失去独立安全和运行边界 | docs/roadmap/02_生产上线实施路线.md | satisfied | 同一核心实现 HEAD 上 Local Dev `32716699878`、Windows Runtime `32716700064`、Full-stack `32716699986`、Internal V1-A `32716699880`、Release dry-run `32716700257` 均成功；Completion Gate 保留独立 Workflow，其先前失败仅因 Change 尚未进入 Ready 状态 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | required | `Repository Quality` 继续执行前端 Playwright Mock Acceptance；CI run `32716699870` 成功 |
| Backend/API/PostgreSQL Integration | required | 单 PostgreSQL 18 Runner 覆盖现有全部 Integration 目录、readiness、历史独有 Migration/Schema 断言；CI run `32716699870` 成功 |
| Contract / Generated Client | required | `Repository Quality` 执行 Pydantic/OpenAPI/Orval drift、contracts tests 与 compatibility check；CI run `32716699870` 成功 |
| Real Full-stack Golden Path | required | `fullstack.yml` 保留真实 Excel Browser → API → PostgreSQL → Worker Golden Path；run `32716699986` 成功 |
| Real Provider Probe | not_applicable | 本次不改变 TikHub endpoint/shape/capability；被删除的 `stage7-tikhub-real-shape.yml` 也只运行 Sanitized/real-shape Fixture Unit，并非真实付费 Probe |
| Docs / Governance / Other | required | Ruff/mypy/架构/Owner/Secret/Docs、Windows Tooling、Local Dev、Linux/Windows Compose、Release dry-run 均保留；相关正式文档已同步到长期 Workflow 名称 |

# Completion Audit

- [x] upstream_re_read：完成 Ready 前重读本轮用户要求、目标分支 `AGENTS.md`、RVC Skill、Testing Strategy、Blueprint 06/07、Roadmap 与当前 PR/Workflow 事实；没有以历史聊天替代仓库事实。
- [x] change_coverage：逐一复核被删除的 Stage 4/5/6/7/Audit Workflow；独有 Schema/Constraint/Trigger/Migration 断言进入正式 Integration Test，重复 Unit/Contract/Ruff/mypy/同目录 Integration 只保留一套长期执行链。
- [x] reverse_audit：从新 Repository Quality/PostgreSQL Integration/Runtime/Full-stack/Release 反查旧能力，并从每个被删除 Workflow 反查新入口；Release check、Runtime、Full-stack、Change Gate 均未被误合并或删除。
- [x] unresolved_cleared：初次合并 PostgreSQL Runner 暴露的跨 suite 数据污染与架构门禁旧 Workflow 路径均已修复；没有通过 skip、删除断言、降低数据库约束或关闭门禁消除失败。

# 两阶段 Review

## A1：上游要求 → Change

结论：通过。用户要求的三个核心点——不降低有效测试能力、从历史 Stage 转为长期风险/验证层、显著减少重复 Runner/PostgreSQL/uv/Ruff/mypy/Integration——均进入 R1-R3；测试层证据边界与 Runtime/Release 独立性进入 R4-R6，没有遗漏或擅自扩展业务语义。

## A2：Change → 实现/测试/文档

结论：通过。覆盖映射证明被删除的是历史执行外壳和重复运行，不是独立测试能力；数据库独有断言已迁入正式测试，Migration checkpoint 已统一；真实 Full-stack、Runtime、Release 仍独立；长期文档已切换到 `fullstack.yml` 与长期 CI 角色。

## 代码质量 Review

结论：通过，无未解决 P1/P2。重点复核：

- PostgreSQL 清库 fixture 仅在 GitHub Actions、本地 DB Host、专用 CI credential 三重条件下工作，fail closed；
- 本地/人工 Integration 数据库生命周期不改变；
- 没有修改业务代码、公共 Contract、Schema/Migration 或依赖；
- 没有测试 skip、断言削弱、Branch Protection/CI 绕过；
- `check_architecture.py` 只是从已删除历史 Workflow 路径迁到长期 Workflow 路径，架构 import/ownership 约束未降低；
- Release 仅替换稳定 required check 名称，正式发布权限、main HEAD、Tag/Release 防覆盖与 Bundle replay 语义保持不变。

# 任务

- [x] 调查当前 19 个 Workflow、测试分层、Release check 与 Active Change 冲突
- [x] 建立历史 Workflow → 新长期验证层覆盖映射
- [x] 重构 `ci.yml` 并保留历史独有 PostgreSQL/Migration 断言
- [x] 删除历史 Stage/Audit Workflow，重命名 Full-stack Workflow
- [x] 优化 Runtime/Full-stack 纯文档/Change 触发
- [x] 更新 Release main CI check 与直接相关文档
- [x] 取得核心实现 HEAD 各层 CI 新鲜证据
- [x] 完成 Requirement Traceability、Completion Audit 与两阶段 Review

# 验证

## 核心实现新鲜证据

核心实现 HEAD：`d10946881dd55b69b9229d99c8a2349e90c9f01b`

```text
CI                                  32716699870  success
Local Dev Bootstrap                 32716699878  success
Internal V1-A Deployable Stack      32716699880  success
Full-stack Acceptance               32716699986  success
Windows Docker Desktop              32716700064  success
Release dry-run for PR #205         32716700257  success
```

该 HEAD 的 Change Completion Gate `32716699909` 按设计失败，因为当时 Change 仍是 `status: in_progress`；本次 Completion Audit/Traceability/Review 完成后已切换为 `ready_for_review`，由后续当前 HEAD Gate 重新验证。

## 初次合并后的 Red 证据

- 初始统一 PostgreSQL Integration 中 `tests/integration/jobs` 因前置 suite 留下 `processing_import_batches.job_id → jobs.id` 引用而触发 PostgreSQL FK violation；证明不能在一个 DB 中直接串行复用旧测试而不恢复隔离边界。
- 初始 Repository Quality 的 Ruff format 对新增数据库测试文件失败；按实际 Ruff 要求修正格式。
- 后续 Repository Quality 发现 `check_architecture.py` 仍把已删除 Stage Workflow 当必需文件；修正为 7 个长期 Workflow 后通过，没有删除架构 import/ownership 规则。

# 文档影响

- `docs/blueprint/06_开发约束与分阶段实施.md`：Full-stack 长期入口改为 `.github/workflows/fullstack.yml`，质量门禁导航不再使用 Stage 专项作为长期组织方式。
- `docs/roadmap/02_生产上线实施路线.md`：机器事实与 Stage 8F 证据入口同步为 `.github/workflows/fullstack.yml`，不改变产品 Stage/上线优先级。
- `docs/04_测试与调试说明.md`：固化 7 个长期 Workflow、统一 PostgreSQL Integration 与 suite 数据隔离策略。

# 交付

- 分支：`refactor/ci-validation-layers`
- 核心实现证据 HEAD：`d10946881dd55b69b9229d99c8a2349e90c9f01b`
- PR：#205 `收敛历史 Stage CI 为长期验证层`
- 发布：不直接发布；本 Change 只调整 CI/Workflow。
