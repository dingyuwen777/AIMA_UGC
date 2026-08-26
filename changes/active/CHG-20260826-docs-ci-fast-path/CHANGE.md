---
schema: rvc-change/v1
id: CHG-20260826-docs-ci-fast-path
title: 文档与治理变更 CI 风险分层快速路径
level: L2
status: in_progress
owner: dingyuwen777
branch: feature/docs-ci-fast-path
created: 2026-08-26
updated: 2026-08-26
completion_gate: required
depends_on: []
affected_areas:
  - ci
  - agent-governance
  - documentation-governance
affected_paths:
  - .github/workflows/ci.yml
  - .github/workflows/fullstack.yml
  - scripts/quality/classify_ci_scope.py
  - scripts/quality/scan_secrets.py
  - .agents/skills/coding/SKILL.md
  - .agents/skills/coding/README.md
  - .agents/skills/coding/references/07_通用验证与证据策略.md
  - .agents/skills/coding/references/12_规则保留映射.md
  - .agents/skills/coding/tests/test_docs_ci_fast_path.py
  - docs/blueprint/06_开发约束与分阶段实施.md
contracts: []
data_changes: []
---

# 目标

让 AIMA_UGC 的永久 CI 按真实风险选择验证层，而不是纯文档或纯治理变更也机械执行完整产品 CI。

核心行为：

1. 仅修改不影响机器业务行为的文档时，进入 `docs_only` profile，只运行文档、Secret 和仓库治理相关轻量验证；
2. 仅修改 `changes/**`、`AGENTS.md`、`.agents/**` 等研发治理事实时，进入 `governance_only` profile，仍保留文档/Secret/Change/Skill 等治理门禁，但不运行 PostgreSQL、Wheel、Frontend Browser Mock、真实 Full-stack 等产品验证；
3. 一旦存在机器行为、Prompt、Contract、Migration、依赖/lock、build/config/workflow、产品代码或无法安全归类的路径，进入 `full` profile，保持现有完整 CI 证明责任；
4. `CI Gate` check identity 始终存在，不使用简单 `paths-ignore` 让主 CI check 消失。

# 成功标准

- [ ] Coding Skill 明确 Documentation / Governance Fast Path：required/not_applicable 按风险决定，纯文档不得为了形式机械跑完整产品 CI。
- [ ] `07_通用验证与证据策略.md` 定义保守的 docs/governance/full changed-scope 分类和退出 fast path 条件。
- [ ] `scripts/quality/classify_ci_scope.py` 用标准库实现可测试的保守分类；未知路径默认 `full`。
- [ ] `.github/workflows/ci.yml` 始终产生 `CI Gate`，轻量 profile 只跑 docs/governance job，full profile 保持现有 Repository Quality + PostgreSQL Integration。
- [ ] `.github/workflows/fullstack.yml` 对安全的 docs/governance-only 路径不再触发真实 Full-stack，但 Prompt/未知 Markdown 不进入忽略列表。
- [ ] 轻量 profile 仍运行当前 `check_docs.py` 和 `scan_secrets.py`；Secret scan 覆盖 `.agents/**`。
- [ ] Blueprint 06 把“PR 最新 HEAD CI”改为“PR 最新 HEAD 风险相关 required CI profile”，并解释纯文档 fast path 边界。
- [ ] 回归测试先在旧实现上失败，再在修改后通过，并覆盖 `docs_only / governance_only / full` 分类、Prompt `.md` 保守回退、CI Gate 身份和 Full-stack 路径边界。
- [ ] 不删除或降低原产品 CI 的 Unit/Contract/API/PostgreSQL/Wheel/Frontend/Browser Mock 证明责任；full profile 仍实际执行原命令。

# 非目标

- 不改变产品业务代码、Contract、Schema/Migration 或数据库行为。
- 不删除现有永久 Workflow。
- 不把任意 `.md` 都视为文档；Prompt、机器消费 Markdown 和未知路径默认走 full。
- 不通过改 check name、关闭门禁或 `continue-on-error` 达到“加速”。
- 不在本 Change 顺手重构 Runtime/Tooling/Release 的其他职责。

# 必须保持不变

- `CI Gate`、`Repository Quality`、`PostgreSQL Integration` 的 check identity 和 full profile 证明范围。
- Change Completion Gate 继续独立运行 Requirement Traceability / Coding Skill regression / Ready Check。
- Runtime Acceptance 现有 risk-detection / fast-path 机制保持。
- Full-stack 的真实 Excel Golden Path 在产品相关变更时继续运行。
- Docs/Coding/Review 路由、Completion Audit、中文提交、北京时间和安全边界保持。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 纯文档变更在不影响业务和仓库级门禁时，不跑完整产品 CI | user:current-request | not_satisfied | 待实现 docs_only profile |
| R2 | 只跑文档相关 CI，而不是简单跳过所有检查 | user:current-request | not_satisfied | 待实现 docs-governance job + CI Gate |
| R3 | 文档 fast path 必须保守，Prompt/机器行为 Markdown 不能误判 | user:approved-plan | not_satisfied | 待实现 allowlist classifier |
| R4 | required check identity 不因优化消失 | user:approved-plan | not_satisfied | 待保持 CI Gate + jobs 结果路由 |
| R5 | Skill 与 Blueprint 同步表达风险相关 CI，而非机械全量 CI | user:approved-plan | not_satisfied | 待修改 Coding/07/12/README/Blueprint 06 |
| R6 | 不降低原 Unit/Contract/API/PostgreSQL/Wheel/Frontend/Full-stack 证明责任 | current Coding Workflow governance | not_satisfied | 待 Evidence Preservation Mapping + full profile 验证 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | classifier 单元回归：docs_only/governance_only/full/Prompt `.md`/未知路径 |
| 接口 / Contract | not_applicable | 不改变产品 public Contract；CI profile 输出仅供本 workflow 内部消费 |
| 集成 / Persistence / Runtime Dependency | required | full profile 最终 HEAD 仍实际运行 PostgreSQL Integration；轻量 profile 通过单独 docs-only 验证提交证明不会启动该 Job |
| 用户 / Workflow Acceptance | required | GitHub Actions PR 实际结果：CI Gate 在 full 和轻量 profile 均存在且结论正确 |
| 跨组件 Golden Path | required | 本 Change 修改 Full-stack workflow，本 feature HEAD 仍需真实 Full-stack success；后续 docs-only 路径验证不触发 Full-stack |
| External Dependency / Provider Probe | not_applicable | 不改变 Provider 或外部接口事实 |
| Build / Package / Runtime | required | full profile 保持 Wheel/frontend build/startup 等原步骤并在最终 feature HEAD 成功 |
| Docs / Governance / Other | required | Coding Skill tests、check_docs、scan_secrets、Change Gate、Docs targeted review、Review Skill 审查 |

# Evidence Preservation Mapping

| 原证明责任 | 原位置 | 新位置 | 证据等级 | 依据 |
| --- | --- | --- | --- | --- |
| Python lint/type/unit/contract/API | CI / Repository Quality | full profile / Repository Quality | 保持 | 原命令不删除，只条件化到产品风险存在时 |
| Secret + docs gates | CI / Repository Quality | full profile 原位置；轻量 profile docs-governance | 保持 | 两种 profile 均运行同一质量脚本 |
| Wheel + Frontend unit/build/Browser Mock | CI / Repository Quality | full profile / Repository Quality | 保持 | 纯文档无对应机器行为风险；产品变化仍完整执行 |
| PostgreSQL transaction/migration/integration | CI / PostgreSQL Integration | full profile / PostgreSQL Integration | 保持 | 纯文档无数据库风险；产品变化仍使用真实 PostgreSQL |
| CI 总门禁身份 | CI / CI Gate | CI / CI Gate | 保持 | check 始终创建，按 profile 验证所需 jobs |
| Real Full-stack Golden Path | Full-stack Acceptance | 产品相关 path 保持；安全 docs/governance path 不触发 | 保持 | 仅缩小无关触发，不用较弱证据替代产品接线证据 |

# Completion Audit

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# 任务

- [x] 恢复当前 main / AGENTS / Coding / Docs / CI / Full-stack / Blueprint 事实
- [x] 建立 L2 Change 与 Evidence Preservation Mapping
- [ ] 建立 Red 回归并 Verify Red
- [ ] 实现 scope classifier
- [ ] 实现 CI lightweight/full profile 路由
- [ ] 收敛 Full-stack docs/governance 无关触发
- [ ] 更新 Skill/reference/preservation/README/Blueprint
- [ ] Verify Green + full profile
- [ ] 验证真实 docs-only/governance-only fast path
- [ ] Docs targeted review + Review Skill
- [ ] Ready Check / PR 最终 HEAD 门禁 / 合并 / main 集成验证 / Change 归档

# 文档影响

Docs Impact: targeted。

- Coding Skill/reference/README 需要同步新的通用 fast-path 规则；
- Blueprint 06 需要把 AIMA 实际交付流程从“机械全量 CI”改成“风险相关 required CI profile”；
- Docs Skill 本体已经支持 targeted/not_applicable，不需要改变。
