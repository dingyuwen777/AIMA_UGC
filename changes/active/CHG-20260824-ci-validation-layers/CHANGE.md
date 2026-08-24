---
schema: rvc-change/v1
id: CHG-20260824-ci-validation-layers
title: CI 按长期验证层收敛
level: L3
status: in_progress
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

- [ ] 删除只承担历史 Stage/Audit 验收外壳的永久 Workflow；仓库 Workflow 从当前 19 个收敛到 7 个长期职责 Workflow。
- [ ] `ci.yml` 不再按 Stage 命名，统一为 Repository Quality、PostgreSQL Integration、Windows Tooling 与稳定汇总 `CI Gate`。
- [ ] Unit、Contract、API、Frontend Unit/Build/Browser Mock、Ruff、mypy、架构/Owner/Secret/Docs、Wheel 构建等质量门禁只保留一套有效执行链，不因删除 Stage Workflow 丢失覆盖。
- [ ] PostgreSQL Integration 在一个隔离 PostgreSQL 18 Runner 中覆盖 `platform/database/jobs/collection/content/ingestion` 全部现有 Integration 目录，并保留旧 Workflow 中仍有独立价值的 Schema/Constraint/Trigger 与 Migration compatibility 断言。
- [ ] Stage 8F 真实 Full-stack 能力保留但改为长期职责命名；Local Dev、Linux canonical Compose、Windows Docker Desktop Runtime、Change Completion Gate、Release 仍分别保留独立证据边界。
- [ ] Release 的 main CI 前置检查从历史 `Stage 1` check 改为稳定 `CI Gate`，不降低 Release fail-closed 行为。
- [ ] 仅文档/Change 变动不再触发高成本 Runtime/Full-stack Workflow；代码、配置或 Workflow 变动仍保持原有运行验证。
- [ ] 正式测试/开发文档不再把永久 CI 导航建立在历史 Stage Workflow 名称上。

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
- 并行 `CHG-20260824-multi-keyword-pack-entrypoints` 的业务/Contract/前端实现不修改；当前可见路径没有语义重叠。

# 关键决策

## L3 方案比较

### 方案 A：保留 19 个 Workflow，只加 `paths` / cache

优点：迁移最少；历史 Stage 证据原样存在。缺点：Stage 4—7 已经成为历史，Ruff/mypy/Unit/Contract/Integration 仍被多次执行；Runner 和 PostgreSQL 重复成本的根因没有消失，也继续强化“Stage 名称=长期架构”的错误导航。

### 方案 B：按验证层收敛历史 Stage CI，保留独立 Runtime/Full-stack/Release 边界（采用）

把普通代码质量和 PostgreSQL Integration 收回 `ci.yml`，历史 Stage Workflow 删除；Runtime、Full-stack、Change Gate、Release 因证明边界、权限或环境不同继续独立。这样减少真正重复执行，而不是单纯减少 YAML 文件数量。

### 方案 C：所有检查合并成一个巨型 Workflow/单一 Runner

文件数量最少，但 Windows/Linux、Compose、Full-stack、Release 权限与普通 CI 生命周期不同；强行合并会放大失败域、延长单 Runner 串行时间，并让 Release 写权限与普通只读 CI 边界变差，因此不采用。

用户于 2026-08-24 明确要求“不降低任何有效测试能力，把按历史 Stage 组织的 CI 收敛成按长期风险/验证层组织的 CI，并显著减少重复 Runner、重复 PostgreSQL、重复 uv sync、重复 Ruff/mypy、重复 Integration Test”，据此采用方案 B。

## 迁移 / 部署 / 回滚

- 无数据库或业务 Migration；CI 配置随 PR 合并生效。
- 删除历史 Workflow 前，先把其独有断言映射到统一 `PostgreSQL Integration`；重复执行本身不作为独立能力保留。
- Release 只改 required check 名称引用，从 `Stage 1` 切换为 `CI Gate`；其他发布语义不变。
- 回滚可整体 revert 本 Change，恢复旧 Workflow 和旧 check 名称；不涉及生产数据回滚。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 不降低任何有效测试能力 | user:2026-08-24-ci-convergence | not_satisfied | 实现后由覆盖映射与 PR 各层 CI 新鲜证据证明 |
| R2 | 历史 Stage CI 改为按长期风险/验证层组织 | user:2026-08-24-ci-convergence | not_satisfied | `ci.yml`、`fullstack.yml` 与文档完成后证明 |
| R3 | 显著减少重复 Runner/PostgreSQL/uv/Ruff/mypy/Integration | user:2026-08-24-ci-convergence | not_satisfied | 删除 Stage Workflow，并在单 PostgreSQL Integration Runner 运行各 Integration 目录 |
| R4 | 各测试层只证明实际边界，Real Full-stack/Provider Probe 不与普通 CI 混淆 | docs/blueprint/06_开发约束与分阶段实施.md | not_satisfied | 保留独立 Full-stack；不新增 Real Provider Probe；文档同步 |
| R5 | PostgreSQL 真实语义、Migration 与数据库约束继续由 PostgreSQL Integration 验证 | .agents/skills/reliable-vibe-coding/references/testing-strategy.md | not_satisfied | `postgres:18.4` + Integration/Migration compatibility CI |
| R6 | Release/Runtime/Change Gate 不因 CI 收敛失去独立安全和运行边界 | docs/roadmap/02_生产上线实施路线.md | not_satisfied | Runtime/Change/Release Workflow 保留并由 PR CI 验证 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | required | `Repository Quality` 必须继续运行前端 Playwright Mock Acceptance；PR CI 提供新鲜证据 |
| Backend/API/PostgreSQL Integration | required | 单 PostgreSQL 18 Runner 覆盖现有全部 Integration 目录、readiness 与历史独有 Migration/Schema 断言 |
| Contract / Generated Client | required | `Repository Quality` 继续执行 Pydantic/OpenAPI/Orval drift、contracts tests 与 compatibility check |
| Real Full-stack Golden Path | required | `fullstack.yml` 保留真实 Excel Browser → API → PostgreSQL → Worker Golden Path 并在 PR 运行 |
| Real Provider Probe | not_applicable | 本次不改变 TikHub endpoint/shape/capability，且仓库明确规定真实付费 Probe 默认不进普通 CI |
| Docs / Governance / Other | required | Ruff/mypy/架构/Owner/Secret/Docs、Windows Tooling、Runtime Compose、Change Completion Gate、Release dry-run 与 Workflow 数量/导航检查 |

# Completion Audit

- [ ] upstream_re_read：进入 Ready 前重新读取本轮用户要求、AGENTS/Skill、测试分层、Roadmap/Release 与当前 Workflow 事实。
- [ ] change_coverage：确认历史 Workflow 的每个独立能力都进入覆盖映射，删除的只是重复外壳/重复执行。
- [ ] reverse_audit：从新 CI 各层反查旧 Workflow 能力，并从被删除 Workflow 反查新执行入口；复核 Release check、Runtime、Full-stack、Change Gate 未被误合并或失效。
- [ ] unresolved_cleared：所有 `not_satisfied` 清零；不适用项有正式依据。

# 任务

- [x] 调查当前 19 个 Workflow、测试分层、Release check 与 Active Change 冲突
- [ ] 建立历史 Workflow → 新长期验证层覆盖映射
- [ ] 重构 `ci.yml` 并保留历史独有 PostgreSQL/Migration 断言
- [ ] 删除历史 Stage/Audit Workflow，重命名 Full-stack Workflow
- [ ] 优化 Runtime/Full-stack 纯文档/Change 触发
- [ ] 更新 Release main CI check 与直接相关文档
- [ ] 取得 PR 最新 HEAD 各层 CI 新鲜证据
- [ ] 完成 Requirement Traceability、Completion Audit 与两阶段 Review

# 验证

## 计划

- Workflow/结构：检查 `.github/workflows/` 最终仅保留 7 个长期职责 Workflow；GitHub Actions YAML 能被 PR 正常解析并创建对应 checks。
- Repository Quality：Contract 生成/兼容、Ruff、mypy、Unit、Contract、API、Wheel、Frontend lint/typecheck/unit/build/Browser Mock。
- PostgreSQL Integration：真实 PostgreSQL 18；`tests/integration/{platform,database,jobs,collection,content,ingestion}`；Readiness；current-head schema invariants；历史 revision → head；base → head。
- Windows Tooling：保留原 Windows bootstrap validation。
- Runtime：Local Dev Bootstrap、Compose Golden Path、Windows Compose 现有 jobs 在代码变动 PR 上继续运行。
- Full-stack：真实 Excel Full-stack Acceptance。
- Release：修改 `release.yml` 的 PR dry-run，且 required main CI check 改为 `CI Gate`。
- Ready Check：`python .agents/skills/reliable-vibe-coding/scripts/ready_check.py --root . --require-active-ready`。

## 新鲜证据

- 尚未执行；等待实现 PR 的 GitHub Actions 当前 HEAD 结果。

# 文档影响

- `docs/blueprint/06_开发约束与分阶段实施.md`：固化长期 CI 按验证层组织，不按历史 Stage 永久扩张。
- `docs/roadmap/02_生产上线实施路线.md`：更新 Full-stack/CI 机器事实入口，不改变产品 Stage 状态。
- `docs/04_测试与调试说明.md`：更新当前 CI 角色和真实 Compose/Integration 导航中与本 Change 直接相关的过期说明。

# 交付

- 分支：`refactor/ci-validation-layers`
- Commit：开发中
- PR：待创建
- 发布：不直接发布；本 Change 只调整 CI/Workflow。