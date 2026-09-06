---
schema: coding-change/v1
id: CHG-20260906-145000-documentation-governance
title: 收敛当前文档体系并强化事实漂移门禁
level: L3
status: done
owner: dingyuwen777
branch: docs/368-documentation-governance
created: 2026-09-06
updated: 2026-09-06
completion_gate: required
depends_on: []
affected_areas:
  - docs
  - quality
  - tests
affected_paths:
  - README.md
  - docs/
  - scripts/quality/check_docs_facts.py
  - tests/unit/test_docs_facts.py
contracts: []
data_changes: []
---

# 背景与当前事实

Issue #368 确认当前 live docs 同时混入当前事实、已完成 Stage、运行手册和候选未来能力，并存在后端模块、前端路由、Release/认证状态等过时声明。原 `check_docs_facts.py` 主要做包含检查，能发现“新事实没有写进去”，但不能稳定发现“旧事实仍然留在当前文档里”。

本 Change 只治理文档、文档质量门禁和对应最小测试；不修改业务代码、HTTP Contract、数据库 Schema/Migration、依赖或生产环境。

# 目标

1. 建立统一文档总入口、产品文档层和运维文档层。
2. 让 Blueprint 只承载长期架构/决策，Roadmap 只承载已批准且未完成的工作。
3. 将已完成 Stage 文档在迁移仍有效知识后退出 live docs；历史继续由 `changes/archive/` 与 Git 承载。
4. 把当前关键机器事实改为可机器校验的 exact fact block，并增加 live Roadmap 生命周期门禁。
5. 保持当前业务行为、API、Schema、依赖、Compose/Release 运行方式不变。

# 范围与非目标

## Included

- 根 README 与 `docs/` 当前文档职责、导航、状态和交叉链接；
- Product / Operations 文档层；
- Blueprint 当前事实校准；
- Roadmap 收敛；
- 已完成 Stage/旧提示词退出 live docs；
- `scripts/quality/check_docs_facts.py` 和对应回归测试。

## Excluded

- 新产品功能；
- Figma/前端代码；
- Provider/LLM 调用；
- Contract/Schema/Migration；
- 依赖升级；
- 生产部署、生产写入和 4000 万实际迁移。

# 不变量

- 删除 live 文档前先迁移仍有效知识；
- 当前精确事实仍以代码、Contract、Migration、生成物、测试和锁文件为最终机器事实；
- 未完成且已批准的生产门禁必须继续保留；
- 不新增 `docs/archive` / `docs/history` 等第二套历史事实源；
- 不通过删除或放宽质量门禁获得绿色。

# 方案比较

- 方案 A（采用）：建立中央 Source of Truth 导航、Product/Operations 职责层，并只对小型高漂移集合做 exact-set；解释性架构继续人工维护。这样既能抓“少写/多写旧事实”，又不把整份架构文档生成化。
- 方案 B（不采用）：只修现有过时段落，不调整职责。短期 diff 小，但 Stage/Runbook/Roadmap 继续混杂，后续仍会重复漂移。
- 方案 C（不采用）：把全部当前文档自动生成。会丢失设计原因、运维解释和业务语义，并把机器输出误当技术文档。

# 当前文档结构

```text
docs/README.md
→ 总导航 / Source of Truth / 文档生命周期

docs/product/
→ 产品边界、当前能力、用户流程、角色与产品状态

docs/blueprint/
→ 长期架构和跨模块决定

docs/operations/
→ 生产部署/Release 与 4000 万运行手册

docs/roadmap/
→ 只保留 Production Hardening 与 4000 万生产执行

docs/appendix/ / docs/collection/ / docs/guides/
→ 深入专题、平台实现和开发操作

changes/archive/ + Git
→ 已完成 Stage 和历史施工证据
```

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 当前模块、前端路由和系统状态与机器事实一致 | #368 / AC1 | satisfied | `docs/blueprint/01_总体架构与技术选型.md` 的 backend-modules/frontend-routes exact block 来自当前模块目录和 `frontend/src/app/routes.ts`；Blueprint 07 与代码导航同步 |
| R2 | 建立总导航、Product 和 Operations 文档层 | #368 / AC2 | satisfied | `docs/README.md`、`docs/product/01_产品概述与边界.md`、`02_当前产品能力与用户流程.md`、`03_角色权限与产品状态.md`、`docs/operations/README.md` 与两篇运行手册均已建立 |
| R3 | 已完成 Stage 退出 live docs 且有效知识有新承载 | #368 / AC3 | satisfied | 内网 V1、Stage 8F、业务配置建设路线和旧持续提示词已退出 live docs；Release 与 4000 万运行知识迁入 Operations；测试分层原则保留在 `docs/04_测试与调试说明.md`；历史仍由 `changes/archive/` 与 Git 追溯 |
| R4 | Roadmap 只保留已批准且尚未完成事项 | #368 / AC4 | satisfied | `docs/roadmap/` 当前只保留 README、02 Production Hardening、03 4000 万生产执行；两篇 live Roadmap 均声明 `- 状态：Active` 并有退出条件和依赖 |
| R5 | Release、认证、4000 万与 Analysis Run 当前边界表述准确 | #368 / AC5 | satisfied | Operations 01 保留已实现离线 Release 并改为长期运行手册；Blueprint 05/Operations 02 明确已有 Principal/后端授权但企业 Authentication 未接入；Operations 02 同步 Analysis Run `selected/all` Contract；Roadmap 03 只保留容量、授权、生产执行和全量对账 |
| R6 | 文档事实门禁能发现小型关键集合的缺失、旧值、重复与生命周期回归 | #368 / AC6 | satisfied | `check_docs_facts.py` 新增 backend modules/frontend routes/permanent workflows exact-set、duplicate、retired-path 与 Roadmap Active 检查；`tests/unit/test_docs_facts.py` 增加对应隔离夹具回归 |

AC7 与 AC8 是 PR/current-head CI、独立 Review、merge、main-fresh、自动归档和 Issue closure 的交付/关闭门禁，由 PR、Commit、Actions、Change Archive 与 Issue 状态持有，不伪造为 Ready 前已经完成的施工要求。

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | PR #369 implementation HEAD `c2a10087a3c6304450ffac66cf8e9843d9ad3080`，CI run `34024343376` 的 Unit/Contract/API tests 全部 success；`tests/unit/test_docs_facts.py` 覆盖 exact-set 缺失/旧值/重复、Markdown link、Roadmap lifecycle、退役路径 |
| 接口 / Contract | not_applicable | 不修改 HTTP/Pydantic/OpenAPI/Schema；同一 run 的 generated Contract/client 校验 success，确认没有意外漂移 |
| 集成 / Persistence / Runtime Dependency | not_applicable | 本任务不修改 PostgreSQL/持久化；CI run `34024343376` 仍完整运行 PostgreSQL Integration 并 success |
| 用户 / Workflow Acceptance | not_applicable | 不修改产品 UI/业务工作流；Product 文档只描述当前机器事实 |
| 跨组件 Golden Path | not_applicable | 无产品接线变化；CI run `34024343376` 的 Real Full-stack Golden Path 仍 success，证明文档治理未意外破坏现有真实链 |
| External Dependency / Provider Probe | not_applicable | 不改变 Provider/LLM 外部边界，不需要真实付费 Probe |
| Build / Package / Runtime | required | CI run `34024343376` 的 Ruff/mypy、Wheel、Frontend unit/build/Browser Mock success；Runtime Acceptance run `34024343172` 正确识别 Runtime unchanged 并 fast-path success |
| Release dry-run | required | Release run `34024343182`：linux/amd64 镜像构建、immutable facts、离线 Bundle、`images.tar` 重载、`--no-build --pull never` replay、deploy archive 全部 success |
| Docs / Governance / Other | required | CI run `34024343376` 的 Requirement Source、AIMA governance、Change Ready、Secret/docs、`check_docs.py`、`check_docs_facts.py` 均 success；CI Gate success |

# Deep Review Evidence

- Review target：PR #369，L3 Deep Review。
- reviewed_base_sha：`12e76097928aab03a71cb95b166a81acf7f4b89a`。
- reviewed_head_sha：`c2a10087a3c6304450ffac66cf8e9843d9ad3080`。
- current_base_sha：`12e76097928aab03a71cb95b166a81acf7f4b89a`，Review 时 main 未漂移。
- PR review：`5124918350`。
- A1：按 Issue #368 AC1–AC8 从上游重新建立完成定义；AC1–AC6 已由本 Change 实现，AC7–AC8 保留为交付/关闭门禁。
- A2：从文档、checker、tests 和 current-head CI 反查每项要求的真实证据；未发现 Contract/Schema/Migration/依赖/Runtime 行为变化。
- Review 中发现 Operations01 仍以 Stage 11A–E 组织现行运行手册；已改为当前部署/Release/Backup-Restore/rollback/Production hardening 边界并完成 re-review。
- 结论：`NO_FINDINGS_WITHIN_SCOPE`；没有遗留 BLOCKER/HIGH/MEDIUM Finding。
- 边界：GitHub Runner/开发环境证据不等于真实 Production Go-Live；Production Hardening 与 4000 万正式生产执行仍由 Active Roadmap 管理。

# 实施状态

- [x] 恢复 Agent_Skills canonical 与 AIMA 当前规则、主分支和机器事实。
- [x] 建立 Issue #368 并完成重复项/Active Change 检查。
- [x] 重组文档职责并迁移有效知识。
- [x] 校准后端模块、前端路由、Release、Principal/Authentication 与 Analysis Run 当前事实。
- [x] 强化文档事实与 Roadmap 生命周期门禁。
- [x] 补 exact-set / lifecycle 最小回归测试。
- [x] 创建 PR #369 并通过 Requirement Source / Change Ready 门禁。
- [x] implementation HEAD `c2a10087a3c6304450ffac66cf8e9843d9ad3080` 的主 CI、PostgreSQL Integration、Real Full-stack、Runtime Acceptance 与 Release dry-run 全部通过。
- [x] 完成 L3 Deep Review；唯一发现的 Operations Stage 化表达已修复并 re-review，当前无未解决 Finding。
- [ ] 对本次仅更新 Change 证据记录的最终 PR HEAD 完成 fresh CI / review delta 校验。
- [ ] 合并 main，验证 main fresh、Change 自动归档，最后关闭 Issue #368。

# Completion Audit

- [x] upstream_re_read：重新读取 Issue #368（含稳定 AC1–AC8）、当前 AIMA `AGENTS.md` / `docs/AGENTS.md`、canonical Docs/Coding/Review 规则，以及当前模块、Route、Release、Identity/Analysis Contract 等机器事实。
- [x] change_coverage：R1–R6 覆盖 AC1–AC6 的施工内容；AC7–AC8 明确保留为 PR/merge/main-fresh/归档/Issue closure 交付门禁，没有把候选产品愿望重新塞入 Active Roadmap。
- [x] reverse_audit：从当前模块/Route/Workflow/Release/Identity/Analysis Contract 反查对应文档 Owner；再从 Product/Blueprint/Operations/Roadmap 声明反查机器事实或批准的未完成目标。Stage 历史由 Change/Git 承载，不需要 live 文档继续复制。
- [x] unresolved_cleared：本 Change 无 Contract/Schema/数据/依赖/Runtime 变化；Production Hardening 与 4000 万生产操作保持明确未完成；Review Finding、CI 文档断链、Ruff format/lint 均已按根因修复，没有通过删除或放宽门禁制造绿色。

`ready_for_review` 表示施工范围和完成定义已闭环。实现 HEAD 已完成 CI 和 Deep Review；本次证据记录更新后仍必须以新的 PR current HEAD 再取得 fresh CI，才能进入 merge。

# 兼容、部署与回滚

- 兼容：业务 API、Schema、数据、依赖和 Runtime 不变；文档路径变化已由当前文档导航/链接门禁和 current-head CI 验证。
- 部署：无需生产部署；合并后仅改变仓库文档与质量门禁。
- 回滚：如治理结构或门禁存在错误，可 revert 实现 PR；不得通过放宽业务/安全门禁来制造绿色。
