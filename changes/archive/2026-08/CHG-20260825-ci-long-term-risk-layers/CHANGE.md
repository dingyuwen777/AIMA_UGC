---
schema: rvc-change/v1
id: CHG-20260825-ci-long-term-risk-layers
title: CI 长期风险分层与 Runtime Tooling 收敛
level: L3
status: done
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
  - scripts/quality/check_architecture.py
  - docs/04_测试与调试说明.md
  - docs/roadmap/02_生产上线实施路线.md
  - changes/archive/2026-08/CHG-20260824-stop-local-backend-postgres/CHANGE.md
contracts: []
data_changes: []
---

# 背景与当前事实

2026-08-24 的 `CHG-20260824-ci-validation-layers` 已把 19 个按历史 Stage 分裂的永久 Workflow 收敛为 7 个长期入口，并把 Ruff/mypy/Unit/Contract 与 PostgreSQL Integration 的 Stage 重复执行归并到 `ci.yml`。本 Change 完成第二轮收敛：原 `internal-v1a.yml`、`local-dev-bootstrap.yml`、`compose-windows-desktop.yml` 仍按历史里程碑/平台实现分裂，导致普通业务变更启动无关 Windows/Local Dev Runner，canonical Linux Compose 与 Windows overlay 还会分别 build/start 同一套镜像。

当前正式运行入口仍是 `compose.yaml`，Windows Docker Desktop 只叠加 `compose.windows.yaml` 的 storage override。Compose 因此仍是正式 Runtime/Packaging Contract：CI 保留少量真实部署验收来证明 Docker image assembly、bootstrap/Migration/configure、Secret、Readiness、持久化、端口和 recovery，但不再复制 Unit/API/Integration 状态空间，也不在多个 Workflow 重复 build。

# 目标与最终拓扑

永久 CI 已收敛为按长期风险/验证层组织的 6 个职责：

```text
CI
→ Repository Quality + PostgreSQL Integration + CI Gate

Full-stack Acceptance
→ Browser → Real API → PostgreSQL → Worker Golden Path

Runtime Acceptance
→ canonical Compose + Windows storage overlay + Runtime/Packaging

Developer Tooling Compatibility
→ Local Dev bootstrap/launcher + Windows setup/mirror/Compose CLI

Change Completion Gate
→ Requirement Traceability + Completion Audit

Release
→ 离线候选构建、Bundle replay 与正式发布
```

真实 Provider Probe 继续保持按需、有界、普通 CI 外验证，没有因“追求更真实”塞入主回归链。

# 成功标准

- [x] 永久 Workflow 不再以 `Internal V1-A` / `Local Dev Bootstrap` / `Windows Docker Desktop` 作为 CI 架构名称，`.github/workflows/` 当前为 6 个长期职责入口。
- [x] `ci.yml` 中 Unit、Contract、API、Ruff、mypy、Frontend Unit/Build/Browser Mock、PostgreSQL Integration 各只保留一套正式执行链。
- [x] Local Dev 与 Windows 工具链独有断言迁入 `tooling.yml`，并使用真实依赖路径触发；普通业务逻辑变化不再常驻启动这些 Runner。
- [x] canonical Linux Compose 与 Windows overlay 的独有 Runtime 断言迁入 `runtime.yml`，同一 Ubuntu Runner 首次 build 一次，后续 repo-relative/Windows overlay 使用 `--no-build` 复用镜像。
- [x] `Compose Golden Path` 在每个 PR/main SHA 上保持稳定存在；无 Runtime 风险变化时走 fast-path，不因整个 Workflow 不触发造成 Release check 缺失。
- [x] 保持 `CI Gate`、`Compose Golden Path`、`Requirement Traceability and Completion Audit` 名称；`release.yml` 依赖的 check contract 不变。
- [x] `release.yml` 正式发布 fail-closed、Tag/Release 防覆盖、offline bundle replay 语义未降低；PR #220 Release dry-run 成功。
- [x] Real Full-stack 保持独立 Golden Path；Real Provider Probe 继续普通 CI 外按需验证。
- [x] `docs/04_测试与调试说明.md` 与 Production Roadmap 已同步当前长期验证层和 Runtime/Tooling 分工。
- [x] 删除旧 Workflow 后，历史 gated Change 中仍把旧路径作为 Requirement Source 的唯一漂移已迁移到当前 `tooling.yml` 来源，不恢复废弃 Workflow。
- [x] PR 最终 HEAD 与 merge 后 main 均有新鲜 CI 证据。

# 范围

- `ci.yml`：移出仅属于开发工具链的 Windows job，保留 Repository Quality、单一 PostgreSQL Integration 与稳定 `CI Gate`。
- `tooling.yml`：合并旧 Local Dev bootstrap、跨平台 launcher、Windows bootstrap、Docker Desktop mirror 与 CMD/PowerShell Compose CLI 验证；只在版本/锁、Local/Compose 配置、entrypoint/bootstrap/platform/system 等真实依赖变化时运行。
- `runtime.yml`：合并旧 canonical Linux Compose 与 Windows hybrid Runtime；保留 topology、Secret、Migration/configure、Readiness、mount/port/non-root、持久化、幂等、缺 Secret fail-closed、repo-relative Host Root、Windows storage/restart 等独有断言。
- 删除已完全迁移的 `local-dev-bootstrap.yml`、`internal-v1a.yml`、`compose-windows-desktop.yml`。
- `scripts/quality/check_architecture.py`：长期骨架要求改为新的 6 Workflow 入口，不降低架构边界检查。
- gated 历史归档若把被正式替代的旧 Workflow 当成 Requirement Source，只迁移其当前可解析来源，不改写历史 Evidence。
- 同步测试说明与生产 Roadmap 的当前机器事实。

# 非目标

- 不修改业务代码、公共 HTTP/Canonical Contract、数据库 Schema/Migration、前端产品行为。
- 不删除 Unit/Contract/API/PostgreSQL Integration/Browser Mock/Real Full-stack/Runtime/Local Dev/Windows compatibility 的有效断言。
- 不把所有验证塞进一个巨型 Workflow/Runner；不同风险层继续保持独立失败边界。
- 不新增第三方 CI SaaS、依赖升级或真实 TikHub/LLM 付费调用。
- 不修改 GitHub Branch Protection/Ruleset 设置。

# 必须保持不变

- PostgreSQL 语义测试继续使用真实 `postgres:18.4`，不用 SQLite/Fake 替代。
- `CI Gate` 继续 fail closed 聚合 Repository Quality 与 PostgreSQL Integration。
- `Compose Golden Path` 继续作为 Release 发布前置 check；Runtime 不相关变化只允许快速成功，不允许缺失该 check。
- `Requirement Traceability and Completion Audit` 行为不变。
- Release 继续只允许当前远端 `main` 最新 SHA 正式发布。
- Windows overlay 继续只改变 storage source，不形成第二套业务 Runtime。

# 方案比较与已确认决策

## 方案 A：保留 7 个 Workflow，只加 paths/cache

优点是改动小；缺点是 Linux/Windows Runtime 仍重复 build，Local Dev/Windows 工具职责仍分散，重复计算根因未消除。

## 方案 B：6 个长期风险/验证层（采用）

Linux canonical Compose + Windows overlay 收敛为 `Runtime Acceptance`，重运行共用同一 Ubuntu Runner/同一轮 build；Local Dev + Windows setup/CLI 收敛为 `Developer Tooling Compatibility`，只在真实相关路径变化时触发；代码质量与 PostgreSQL Integration 继续由 `ci.yml` 唯一承担。

## 方案 C：压成 5 个，把 Tooling 塞回 `ci.yml`

文件最少，但产品代码质量与开发机工具链重新耦合，必须引入更多条件/skip 聚合，职责变模糊；减少 YAML 数量并不能减少有效计算，因此未采用。

# 实施结果与资源模型

当前 `.github/workflows/`：

```text
change-completion-gate.yml
ci.yml
fullstack.yml
release.yml
runtime.yml
tooling.yml
```

按 Workflow/job 拓扑计算，对**普通、不修改 Runtime/Tooling/Release 表面**的业务 PR：

```text
旧 7-Workflow 结构
→ 约 12 个 job Runner
→ 约 5 个 PostgreSQL 实例
→ 约 4 次直接 uv sync
→ canonical + Windows Runtime 各自重 build

新结构
→ 约 6 个 job Runner
→ 约 2 个 PostgreSQL 实例
→ 约 3 次直接 uv sync
→ Runtime 只保留一个 fast-path Runner，不 build/start Compose
→ Tooling 不触发
```

普通业务 PR 的 Runner 拓扑约减少 50%，PostgreSQL 实例约减少 60%；Ruff/mypy 与正式 Integration suite 继续各只有一套。剩余 PostgreSQL/`uv sync` 分别属于 Core PostgreSQL Integration 与 Real Full-stack 等独立风险层，不再属于历史 Stage 重复。

对 Runtime 风险 PR，canonical 与 Windows overlay 共用一个 Runtime Runner，首次 canonical `--build` 后其余启动使用 `--no-build`，消除旧两套 Runtime Workflow 的重复镜像构建。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 不降低任何当前有效测试能力 | user:2026-08-25-ci-risk-layer-convergence | satisfied | 旧 Local Dev/Windows/Runtime 独有断言逐项迁移；PR 最终 HEAD `559cdd1df7fe66881877efbb0337fdaf62b76dac` 的 CI `32793422409`、Full-stack `32793422454`、Runtime `32793422393`、Tooling `32793422399`、Governance `32793422420`、Release dry-run `32793422509` 全部成功；merge 后 main `e8f974b6679a6e2ef8382324196d70311ec12b3a` 的 CI `32793732295`、Full-stack `32793732230`、Runtime `32793732234`、Tooling `32793732283`、Governance `32793732260` 全部成功 |
| R2 | 按长期风险/验证层组织，不再按历史 Stage/里程碑堆 Workflow | user:2026-08-25-ci-risk-layer-convergence | satisfied | `.github/workflows/` 已形成 CI/Full-stack/Runtime/Tooling/Governance/Release 6 个长期职责；旧三个实现型 Workflow 已删除 |
| R3 | 显著减少重复 Runner、PostgreSQL、uv sync、Ruff/mypy、Integration Test | user:2026-08-25-ci-risk-layer-convergence | satisfied | 普通业务 PR 静态拓扑约从 12→6 Runner、5→2 PostgreSQL、4→3 直接 uv sync；Ruff/mypy 与正式 Integration 各保持 1 套；Runtime 两次 build 收敛为 1 次 |
| R4 | Compose 验证只保留真实部署 Contract 价值，不盲目堆砌 | docs/roadmap/02_生产上线实施路线.md | satisfied | PR Runtime `32793422393` 与 post-merge Runtime `32793732234` 均验证 topology、canonical startup/security/persistence/recovery、repo-relative root、Windows storage/restart；Unit/API/Integration 未复制进 Runtime |
| R5 | 测试层只证明真实边界，Real Full-stack/Provider Probe 不被替代或夸大 | .agents/skills/reliable-vibe-coding/references/testing-strategy.md | satisfied | PR Full-stack `32793422454` 与 post-merge Full-stack `32793732230` 独立成功；Provider Probe 因未修改 Provider endpoint/shape/capability 保持 not_applicable，未进入普通 CI |
| R6 | Release 与稳定 check contract 不因重构失效 | docs/blueprint/07_技术决策与实施门禁.md | satisfied | `CI Gate`、`Compose Golden Path`、`Requirement Traceability and Completion Audit` 名称保持；PR Release dry-run `32793422509` 成功；merge 后 main 对应三类 push check 均成功 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | required | PR CI `32793422409` 与 post-merge CI `32793732295`：Frontend unit/build/Browser Mock Acceptance success |
| Backend/API/PostgreSQL Integration | required | PR CI `32793422409` 与 post-merge CI `32793732295`：Migration compatibility、Platform/DB/Jobs/Collection/Content/Ingestion 与 readiness 全部 success |
| Contract / Generated Client | required | PR CI `32793422409` 与 post-merge CI `32793732295`：generated contracts/client drift、compatibility、Contract/API tests success |
| Real Full-stack Golden Path | required | PR Full-stack `32793422454`、post-merge Full-stack `32793732230` success，保持 Browser→Real API→PostgreSQL→Worker 实链 |
| Real Provider Probe | not_applicable | 本 Change 未修改 Provider endpoint、字段 shape、pagination、capability 或 pricing，不需要真实付费外部调用 |
| Docs / Governance / Other | required | PR Runtime `32793422393`、Tooling `32793422399`、Governance `32793422420`、Release dry-run `32793422509` success；post-merge Runtime `32793732234`、Tooling `32793732283`、Governance `32793732260` success |

# Completion Audit

- [x] upstream_re_read：重新读取本轮用户要求、根 `AGENTS.md`、Reliable Vibe Coding Skill、Testing Strategy、Verification Review、Blueprint 06/07 与 Production Roadmap；完成定义仍是“不丢有效测试 + 按风险层收敛 + 降低重复计算”。
- [x] change_coverage：R1—R6 均有实现、PR 最终 HEAD 与 merge 后 main 的新鲜 Actions 证据；没有用“YAML 文件变少”替代真实资源/风险收益。
- [x] reverse_audit：从旧 7 Workflow 反向逐项核对 Local Dev launcher/bootstrap/lifecycle、Windows setup/mirror/Compose CLI、canonical Runtime、repo-relative Host Root、Secret/port/non-root/fail-closed、Windows storage/restart；发现并补齐 `.dockerignore`、`alembic.ini`、`deploy/nginx.conf`、`.gitignore`、`env.local.example`、`modules/system/**`、`entrypoints/**` 等触发依赖；Ready Gate 又暴露 gated 归档仍引用被删除 `local-dev-bootstrap.yml`，已把其 Requirement Source 迁移到现行 `tooling.yml`，历史 Evidence 未改写。
- [x] unresolved_cleared：R1-R6 无 `not_satisfied`；Validation Matrix required 层均有最终证据，唯一 not_applicable 的 Real Provider Probe 有明确事实依据；实现 PR 已合并且 post-merge main 门禁全绿。

# A1 / A2 与代码质量 Review

## A1：上游要求 → 当前 Change

通过。独立从本轮用户要求与正式 Testing/Roadmap/Blueprint 重建完成定义，覆盖：Compose 验证必要性边界、不降低有效测试能力、长期风险/验证层组织、重复 Runner/PostgreSQL/uv/Ruff/mypy/Integration 收敛、Workflow 必须有真实作用且不得漏测。没有 `explicitly_deferred` 项；Provider Probe 的不适用由本 Change 未修改 Provider 事实支持。

## A2：当前 Change → 实现 / 测试 / 文档

通过。6 个长期职责均有机器入口；旧三个 Workflow 的独有断言均有新归属；稳定 Release check 名保持；正式测试说明和 Roadmap 已同步；PR 最终 HEAD 与 merge 后 main 均有新鲜绿灯。删除旧 Workflow 对 gated 历史 Change 的来源解析影响也已最小同步，不恢复旧实现。

## 代码质量 Review

通过，未发现未解决的严重/重要问题。Review 中实际发现并修复：

1. 首轮 CI 暴露 `check_architecture.py` 仍硬编码已删除的三个旧 Workflow；保留门禁并将长期骨架改为新的 6 个入口，没有关闭检查。
2. 随后 Ruff format 暴露架构检查文件格式问题；修正后最终 Ruff/mypy 成功。
3. 反向依赖审计发现 Runtime classifier 漏掉 `.dockerignore`、`alembic.ini`、真实 `deploy/nginx.conf` 与 `modules/system/**`；Tooling classifier 漏掉 `.gitignore`、`env.local.example`、`entrypoints/**`、`modules/system/**`；已按真实 Dockerfile/launcher 调用链补齐，而没有退回“所有代码都跑所有 Workflow”。
4. Ready Gate 日志精确暴露归档 `CHG-20260824-stop-local-backend-postgres` 的 R4 仍把已删除 `local-dev-bootstrap.yml` 当 Requirement Source；只把 Source 迁到现行 `tooling.yml`，保留原历史 Evidence 和历史 affected path，不恢复旧 Workflow 绕过门禁。
5. 未新增依赖、Secret、业务日志或生产数据操作；Runtime/Tooling 使用 placeholder/隔离数据，真实 Provider Probe 未执行。

# 部署、兼容、回滚

- 无业务 Schema/Data Migration；不改变生产 `compose.yaml`/`compose.windows.yaml`、启动命令或 Secret 格式。
- CI Workflow 合并后立即生效；删除旧 Workflow 文件不会删除历史 Actions 记录。
- `main` 分支 API 在实施时报告 `protected=false`，但 Release workflow 显式查询 `CI Gate`、`Compose Golden Path`、`Requirement Traceability and Completion Audit`，因此这些 check 名保持兼容。
- 回滚为 revert 实现 merge commit；对生产数据、数据库 Migration 与部署持久目录没有回滚操作。

# Git / 交付

- Implementation branch: `refactor/ci-long-term-risk-layers`
- Implementation PR: #220 `按长期风险层收敛 CI Runtime 与 Tooling`
- Final PR HEAD: `559cdd1df7fe66881877efbb0337fdaf62b76dac`
- Implementation merge commit: `e8f974b6679a6e2ef8382324196d70311ec12b3a`
- Post-merge main verification: CI `32793732295`、Full-stack `32793732230`、Runtime `32793732234`、Tooling `32793732283`、Change Completion Gate `32793732260` 全部 success
- Archive: 本文件由独立归档分支/PR 从 `changes/active/` 移入 `changes/archive/2026-08/`；归档 PR/merge 状态由后续 GitHub PR 与提交历史记录
