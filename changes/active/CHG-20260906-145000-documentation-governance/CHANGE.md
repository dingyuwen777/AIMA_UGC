---
schema: coding-change/v1
id: CHG-20260906-145000-documentation-governance
title: 收敛当前文档体系并强化事实漂移门禁
level: L3
status: in_progress
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

Issue #368 已确认当前 live docs 同时混入当前事实、已完成 Stage、运行手册和候选未来能力，并存在后端模块、前端路由、Release 状态等过时声明。当前 `check_docs_facts.py` 主要做包含检查，能发现“新事实没有写进去”，但不能稳定发现“旧事实仍然留在当前文档里”。

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
- 不通过删除/放宽质量门禁获得绿色。

# 方案

采用“职责收敛 + exact machine-fact block”方案：

- `docs/README.md` 作为总导航和 Source of Truth 矩阵；
- `docs/product/` 只讲产品边界、当前能力、用户流程、角色和产品状态；
- `docs/operations/` 承载部署/Release 与 4000 万运行手册；
- `docs/roadmap/` 只保留 Production Hardening 与 4000 万生产执行两条 Active 路线；
- 完成态 Stage 文档从 live docs 删除，不复制到新的 archive；
- Blueprint 的后端模块/前端路由使用标记块与代码事实做 exact set 校验；
- Roadmap 文件必须声明 Active、目标、退出条件和依赖。

# Requirement Traceability

| Requirement | Source | Implementation | Validation | Status |
| --- | --- | --- | --- | --- |
| R1 当前模块/路由/状态与机器事实一致 | #368 | README、Blueprint、代码导航 | docs facts + docs navigation | in_progress |
| R2 建立总导航、Product、Operations | #368 | `docs/README.md`、`docs/product/`、`docs/operations/` | docs checker | in_progress |
| R3 已完成 Stage 退出 live docs 且知识不丢 | #368 | Roadmap/Appendix/Guide 重组 | links + review | in_progress |
| R4 Roadmap 只保留已批准未完成事项 | #368 | Roadmap README/02/03 | roadmap lifecycle gate | in_progress |
| R5 exact fact block 能抓缺失与过时值 | #368 | `check_docs_facts.py` | `tests/unit/test_docs_facts.py` | in_progress |
| R6 当前 Release/4000万边界准确 | #368 | Operations + Roadmap | docs facts + review | in_progress |

# Validation Matrix

| Profile | Command / Evidence | Status |
| --- | --- | --- |
| syntax | `python -m py_compile scripts/quality/check_docs_facts.py` | pending |
| targeted | `uv run pytest tests/unit/test_docs_facts.py tests/unit/test_docs_navigation.py -q` | pending |
| docs | `python scripts/quality/check_docs.py` | pending |
| facts | `python scripts/quality/check_docs_facts.py` | pending |
| governance | `python scripts/quality/check_agent_governance.py` | pending |
| PR current HEAD CI | GitHub Actions on implementation PR | pending |
| independent review | L3 independent review of PR diff/evidence | pending |
| product runtime | 文档/质量门禁变更，不改变业务 Runtime | not_applicable |
| persistence | 无 Schema/Migration/数据写入变更 | not_applicable |
| provider live | 不修改 Provider 且不需要付费外部调用 | not_applicable |

# 任务

- [x] 恢复 Agent_Skills canonical 与 AIMA 当前规则、主分支和机器事实。
- [x] 建立 Issue #368 并完成重复项/Active Change 检查。
- [ ] 重组文档职责并迁移有效知识。
- [ ] 强化文档事实与 Roadmap 生命周期门禁。
- [ ] 补最小回归测试。
- [ ] 运行当前 HEAD 相关 CI 并修复回归。
- [ ] 完成独立复核与 Completion Audit。
- [ ] 合并 main，验证 main fresh、Change 归档，最后关闭 Issue。

# Completion Audit

当前状态：施工中。Completion Gate 只有在实现、验证、独立 Review 和 PR current-head CI 都形成新鲜证据后才会切换到 `ready_for_review`。

# 兼容、部署与回滚

- 兼容：业务 API、Schema、数据和 Runtime 不变；文档路径变化会同步修复 live links。
- 部署：无需生产部署；合并后仅改变仓库文档与质量门禁。
- 回滚：如治理结构或门禁误报影响维护，可 revert 本 PR；不得通过放宽现有业务门禁回滚。
