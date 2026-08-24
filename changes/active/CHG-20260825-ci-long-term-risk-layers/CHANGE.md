---
schema: rvc-change/v1
id: CHG-20260825-ci-long-term-risk-layers
title: CI 长期风险分层与 Runtime Tooling 收敛
level: L3
status: in_progress
owner: aima
branch: refactor/ci-long-term-risk-layers
created: 2026-08-25
updated: 2026-08-25
completion_gate: required
depends_on: []
affected_areas:
  - ci
  - testing
  - runtime
  - developer-tooling
  - release
affected_paths:
  - .github/workflows/
  - docs/04_测试与调试说明.md
  - docs/blueprint/06_开发约束与分阶段实施.md
  - docs/roadmap/02_生产上线实施路线.md
contracts: []
data_changes: []
---

# 背景与当前事实

2026-08-24 的 `CHG-20260824-ci-validation-layers` 已把 19 个按历史 Stage 分裂的永久 Workflow 收敛为当前 7 个长期入口，并把 Ruff/mypy/Unit/Contract 与 PostgreSQL Integration 的 Stage 重复执行归并到 `ci.yml`。当前剩余重复主要位于运行与开发工具边界：

- `internal-v1a.yml` 与 `compose-windows-desktop.yml` 都会构建/启动 Compose Runtime；
- `local-dev-bootstrap.yml`、`ci.yml` 的 Windows Tooling 与 `compose-windows-desktop.yml` 的 Windows CLI/镜像脚本检查存在工具链职责交叉；
- Local Dev、Windows Runtime、Linux Runtime 仍以历史里程碑/平台实现名组织，而不是长期风险层；
- 仅业务逻辑变化也会触发多个与开发工具/Compose 拓扑无关的 Runner。

当前正式运行事实仍是 `compose.yaml`，Windows Docker Desktop 仅叠加 `compose.windows.yaml` 的 storage override；因此需要保留 Runtime/Packaging Acceptance 来证明镜像装配、Migration/Bootstrap、Secret、Readiness、持久化和端口边界，但不需要在多个独立 Runner 重复 build 同一套镜像。

# 目标

在不降低任何当前有效测试能力的前提下，把当前 7 个 Workflow 进一步收敛成按长期风险/验证层组织的 6 个职责：

```text
CI
→ 代码质量、Contract、Browser Mock、PostgreSQL Integration

Full-stack Acceptance
→ 少量 Browser → Real API → PostgreSQL → Worker Golden Path

Runtime Acceptance
→ canonical Compose / Windows overlay / Runtime & Packaging 风险

Developer Tooling Compatibility
→ Local Dev bootstrap、跨平台 launcher、Windows PowerShell / Compose CLI

Change Completion Gate
→ Requirement Traceability / Completion Audit

Release
→ 已验证 main SHA 的离线候选构建、回放与发布
```

同时显著减少无关变更触发的 Windows/Local Dev/Compose 重 Runner，并把 Linux canonical Compose 与 Windows overlay 的重运行合并到同一 Runtime Runner，避免重复 Docker build。

# 成功标准

- [ ] Workflow 不再以 `Internal V1-A` / `Local Dev Bootstrap` / `Windows Docker Desktop` 作为永久 CI 架构名称，长期职责可直接从文件名和 job 名理解。
- [ ] 当前 `ci.yml` 中 Unit、Contract、API、Ruff、mypy、Frontend Unit/Build/Browser Mock、PostgreSQL Integration 各只保留一套有效执行链。
- [ ] Local Dev 与 Windows 工具链独有验证全部迁移到 Developer Tooling Compatibility；普通业务变更不再启动这些额外 Runner。
- [ ] canonical Linux Compose 与 `compose.windows.yaml` overlay 的有效 Runtime 断言全部保留，但共用同一个 Ubuntu Runtime Runner 和同一轮镜像 build。
- [ ] 保留稳定 check `CI Gate`、`Compose Golden Path`、`Requirement Traceability and Completion Audit`，避免 Release/潜在 Branch Protection 因 check 名漂移失效。
- [ ] `release.yml` 的正式发布 fail-closed 语义、Tag/Release 防覆盖、offline bundle replay 不降低。
- [ ] Real Full-stack Golden Path 与真实 Provider Probe 的测试边界不被 Runtime/Tooling 混淆；本 Change 不把真实付费 Provider Probe 塞进普通 CI。
- [ ] 正式测试/Roadmap 文档同步为长期风险层导航，不再把当前 CI 架构建立在历史 Stage/里程碑名称上。
- [ ] 最终 PR 最新 HEAD 的所有永久门禁成功，并完成 A1/A2 与代码质量 Review。

# 范围

- 重构 `.github/workflows/ci.yml`，移出仅属于开发工具链的 Windows job，避免其对每个业务变更常驻运行。
- 新增 `.github/workflows/tooling.yml`，合并 `local-dev-bootstrap.yml` 的有效验证、Windows bootstrap/tooling、Docker Desktop mirror 静态/CLI 兼容检查，并使用精确 `paths` 只在相关工具/配置变化时运行。
- 新增 `.github/workflows/runtime.yml`，迁移 `internal-v1a.yml` 与 `compose-windows-desktop.yml` 的有效 Runtime 断言；同一 Ubuntu Runner 先验证 canonical Compose，再在复用已构建镜像的前提下验证 Windows overlay。
- 删除被完全迁移的 `local-dev-bootstrap.yml`、`internal-v1a.yml`、`compose-windows-desktop.yml`。
- 保持 `fullstack.yml`、`change-completion-gate.yml`、`release.yml` 的独立职责；只在事实需要时做最小引用/路径同步。
- 同步测试与 Roadmap 文档中的永久 Workflow 导航和职责说明。

# 非目标

- 不修改业务代码、公共 HTTP/Canonical Contract、数据库 Schema/Migration、前端产品行为。
- 不删除 Unit/Contract/API/PostgreSQL Integration/Browser Mock/Real Full-stack/Runtime/Local Dev/Windows compatibility 中任何当前有独立价值的断言。
- 不把所有检查塞进一个巨型 Workflow 或单一 Runner。
- 不引入新的第三方 Action、CI SaaS、依赖升级或真实 TikHub/LLM 付费调用。
- 不在本 Change 修改 GitHub Branch Protection/Ruleset；当前 GitHub App 对该设置读取权限不足，因此稳定 required-check 名称保持不变。

# 必须保持不变

- PostgreSQL 语义测试继续使用真实 `postgres:18.4`，不得用 SQLite/Fake 替代。
- `CI Gate` 继续 fail closed 聚合 Repository Quality 与 PostgreSQL Integration。
- `Compose Golden Path` 继续作为 Runtime 发布前置 check；无 Runtime 风险变化时可以快速成功，但不能因整个 Workflow 不触发而让同一 main SHA 缺失该 check。
- `Requirement Traceability and Completion Audit` 行为不变。
- Release 继续只允许当前远端 `main` 最新 SHA 正式发布。
- Windows overlay 继续只改变 storage source，不形成第二套业务 Runtime。

# 方案比较与已确认决策

## 方案 A：保留 7 个 Workflow，只加 paths/cache

优点：改动最少。缺点：`internal-v1a` 与 Windows hybrid runtime 仍各自 build/start 同一套镜像；Local Dev/Windows 工具链职责仍分散，重复计算根因没有消除。

## 方案 B：6 个长期风险/验证层（采用）

将 Linux canonical Compose + Windows overlay 收敛为 `Runtime Acceptance`，重运行共用一个 Ubuntu Runner/一轮 build；将 Local Dev + Windows setup/CLI 收敛为 `Developer Tooling Compatibility`，只在工具/配置变化时触发；普通代码质量与 PostgreSQL Integration 继续由 `ci.yml` 唯一承担。

优点：不丢有效断言，能直接消除重复 Compose build 和大量无关 Windows/Local Dev Runner；职责边界稳定。缺点：需要一次性迁移较长 Runtime/Tooling workflow，并同步文档。

## 方案 C：压成 5 个，把 Tooling 塞回 ci.yml

优点：文件最少。缺点：CI Gate 又同时承担产品代码质量与开发机工具链，必须引入更多 job 条件/skip 聚合，长期职责变模糊；文件数减少不等于有效成本下降。

用户已明确要求“不降低任何有效测试能力，按长期风险/验证层组织，并显著减少重复 Runner、PostgreSQL、uv sync、Ruff/mypy、Integration Test”，且允许补充真正有作用的 Workflow，因此采用方案 B。

# 实施计划

1. `[事实映射] -> .github/workflows/{ci,internal-v1a,local-dev-bootstrap,compose-windows-desktop,fullstack,release}.yml -> 建立断言级迁移表 -> 逐项核对命令与职责，不按文件名猜测。`
2. `[Tooling 收敛] -> ci.yml + tooling.yml -> Windows/Local Dev 独有能力集中且按相关路径触发 -> 对照旧三个 tooling job 的命令/断言无遗漏。`
3. `[Runtime 收敛] -> runtime.yml -> canonical + Windows overlay 共用一次镜像 build，保持 Secret/Readiness/Persistence/Fail-closed/Windows storage 断言 -> PR Actions 真正运行验证。`
4. `[删除旧外壳] -> local-dev-bootstrap.yml + internal-v1a.yml + compose-windows-desktop.yml -> 旧职责全部有新入口后删除 -> 搜索旧路径/Workflow 名无当前导航残留。`
5. `[文档同步] -> docs/04 + Blueprint 06 + Roadmap 02 -> 当前 CI 拓扑与机器事实一致 -> docs gate。`
6. `[验证与 Review] -> Change/PR -> Completion Gate、CI、Full-stack、Runtime、Tooling（按本次相关路径应触发）及 Release dry-run（如 release 相关路径受影响） -> 最新 HEAD 全绿后 A1/A2 + 代码质量 Review。`

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 不降低任何当前有效测试能力 | user:2026-08-25-ci-risk-layer-convergence | not_satisfied | 待完成断言级迁移与最终 CI 证据 |
| R2 | 按长期风险/验证层组织，不再按历史 Stage/里程碑堆 workflow | user:2026-08-25-ci-risk-layer-convergence | not_satisfied | 待建立 CI/Full-stack/Runtime/Tooling/Governance/Release 长期拓扑 |
| R3 | 显著减少重复 Runner、PostgreSQL、uv sync、Ruff/mypy、Integration Test | user:2026-08-25-ci-risk-layer-convergence | not_satisfied | 第一轮已消除 Stage 级 Ruff/mypy/Integration 重复；本轮待消除 Runtime build 与无关 Tooling Runner |
| R4 | Compose 验证只保留真实部署契约价值，不盲目堆砌 | docs/roadmap/02_生产上线实施路线.md | not_satisfied | 待把 canonical + Windows overlay 收敛为单一 Runtime Acceptance 层 |
| R5 | 测试层只证明真实边界，Real Full-stack/Provider Probe 不被替代或夸大 | .agents/skills/reliable-vibe-coding/references/testing-strategy.md | not_satisfied | 待最终 Validation Matrix 与 Workflow 证据 |
| R6 | Release 与稳定 required check 不因重构失效 | docs/blueprint/07_技术决策与实施门禁.md | not_satisfied | 待保持 `CI Gate` / `Compose Golden Path` / Completion Audit 并跑 Release dry-run |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | required | 由 `ci.yml` Repository Quality 保持现有 Playwright Mock Acceptance；待最终 CI run |
| Backend/API/PostgreSQL Integration | required | 由 `ci.yml` 单 PostgreSQL 18 Runner 保持全部现有 Integration；待最终 CI run |
| Contract / Generated Client | required | 保持 Pydantic→OpenAPI→Orval drift/compatibility；待最终 CI run |
| Real Full-stack Golden Path | required | 保持 `fullstack.yml` 真 Browser→API→PostgreSQL→Worker；待最终 run |
| Real Provider Probe | not_applicable | 本 Change 不修改 Provider endpoint/shape/capability，也不需要真实付费外部调用 |
| Docs / Governance / Other | required | Runtime/Tooling/Release/Change Gate 与正式文档必须同步；待最终 runs 与 Completion Audit |

# Completion Audit

- [ ] upstream_re_read：完成前重新读取本轮用户要求、AGENTS、Skill、Blueprint 06/07、Testing Strategy、Roadmap 02。
- [ ] change_coverage：逐项确认 R1—R6 均有实现/运行证据且无能力遗漏。
- [ ] reverse_audit：从旧 7 Workflow 的每个独有断言反向核对新入口，确认没有只因“看起来重复”而删除独立风险证明。
- [ ] unresolved_cleared：所有 `not_satisfied` 清零；required Validation Matrix 均有最新 PR HEAD 证据。

# A1 / A2 与代码质量 Review

- A1：待完成。
- A2：待完成。
- 代码质量 Review：待完成。

# 部署、兼容、回滚

- 不产生业务 Schema/Data Migration，也不改变生产 Compose 使用命令。
- CI 配置合并后立即生效；旧 Workflow 文件删除不删除其历史 Actions 记录。
- 回滚方式是 revert 本 Change，对生产数据没有回滚影响。
- 由于 Branch Protection/Ruleset 无读取权限，`CI Gate`、`Compose Golden Path` 与 `Requirement Traceability and Completion Audit` 名称保持不变以控制兼容风险。

# 交付

- 分支：`refactor/ci-long-term-risk-layers`
- PR：待创建。
- 合并：必须等待最终 PR HEAD 永久门禁成功与 Review 完成后再决定。