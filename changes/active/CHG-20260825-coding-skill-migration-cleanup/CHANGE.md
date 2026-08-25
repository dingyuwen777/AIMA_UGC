---
schema: rvc-change/v1
id: CHG-20260825-coding-skill-migration-cleanup
title: Coding Skill 迁移遗留清理
level: L2
status: in_progress
owner: aima
branch: fix/coding-skill-migration-cleanup
created: 2026-08-25
updated: 2026-08-25
completion_gate: required
depends_on: []
affected_areas:
  - developer-tooling
  - agent-workflow
  - testing-governance
affected_paths:
  - .agents/skills/coding/references/02_跨项目研发任务路由.md
  - .agents/skills/coding/references/03_编程语言与工具链适配规则.md
  - .agents/skills/coding/references/09_多人和多智能体并行协作.md
  - .agents/skills/coding/references/12_规则保留映射.md
  - .agents/skills/coding/assets/CHANGE.template.md
  - .agents/skills/coding/tests/test_migration_cleanliness.py
  - changes/active/CHG-20260825-coding-skill-migration-cleanup/CHANGE.md
contracts: []
data_changes: []
---

# 目标

彻底清除 `reliable-vibe-coding` → `coding` 已完成迁移后仍遗留在当前 live Coding Skill 中的旧名称、旧目录路径和旧 CLI 使用指引，使当前规则只使用正式 `Coding` 名称、`.agents/skills/coding/` 路径与 `coding.py` CLI；历史迁移事实和明确兼容标识保持原样。

# 成功标准

- [ ] 当前 live Coding Skill 的规范性文本不再把 `Reliable Vibe Coding` 作为现行名称。
- [ ] 当前 live Coding Skill 的可执行路径不再引用 `.agents/skills/reliable-vibe-coding/` 或把 `rvc.py` 作为现行 CLI。
- [ ] `12_规则保留映射.md` 继续保留迁移前旧名称/旧命令的历史事实，但明确区分历史命令与当前 `coding.py` 命令。
- [ ] `CHANGE.template.md` 的所有 live Skill/reference/Ready Check 路径都指向 `.agents/skills/coding/`。
- [ ] `rvc-change/v1` 等明确历史兼容标识保持不变；`changes/archive/**` 历史叙事不改写。
- [ ] 新增回归检查能在当前残留存在时失败，并在迁移遗留清理后通过。
- [ ] 除上述迁移遗留与回归检查外，不修改任何规则含义、产品代码、Contract、Schema/Migration、依赖、Runtime、Blueprint 或其他治理机制。

# 范围

- 仅修正 `.agents/skills/coding/` 当前 live 文件中的旧品牌、旧 canonical 路径和旧 CLI 使用指引。
- 新增一个最小迁移完整性回归测试，用于阻止相同 live 遗留再次出现。
- 本 Change 自身只记录本次迁移清理和验证证据。

# 非目标

- 不总结、精简、重写、合并或调整 Coding Skill 任一既有规则的语义、触发条件、例外、失败处理、验证责任、安全边界或兼容要求。
- 不修改 `changes/archive/**` 的历史叙事、Evidence、Review、状态或迁移前事实。
- 不修改 `rvc-change/v1` Change Schema 标识；本次没有 Change Schema 迁移。
- 不修改产品代码、HTTP Contract、OpenAPI/generated client、数据库 Schema/Migration、依赖、Runtime、部署或 Branch Protection/Ruleset。
- 不删除远端历史/临时分支；分支治理不属于 live Skill 内容迁移。

# 必须保持不变

- `.agents/skills/coding/SKILL.md` 当前全部规则语义保持不变。
- `references/01_—12_` 中除迁移名称/路径/CLI 指向外的所有文字和规则含义保持不变。
- `agents/openai.yaml` 当前 `Coding` metadata/default prompt 保持不变。
- `coding.py`、`ready_check.py` 的代码和 CLI 行为保持不变。
- `rvc-change/v1` 的历史兼容读取保持不变。
- Archive 历史事实保持原样。

# 关键决策

- 当前名称统一使用 `Coding`；当前 canonical 路径统一使用 `.agents/skills/coding/`；当前 CLI 统一使用 `coding.py`。
- `12_规则保留映射.md` 是迁移历史/知识守恒文件，因此允许保留明确标注为迁移前事实的 `Reliable Vibe Coding`/`rvc.py`，但不能把它们写成当前命令或当前名称。
- 回归检查只扫描明确的 live Skill 表面，不对 `changes/archive/**` 和 `rvc-change/v1` 做误报。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 全面清理当前 live Coding Skill 的旧名称、旧路径和旧 CLI 迁移遗留 | user:current-request | not_satisfied | 当前已确认 02、03、09、12 与 CHANGE.template.md 存在 live 残留 |
| R2 | 不总结或改变任一既有规则及含义，只做迁移遗留最小替换 | user:current-request | not_satisfied | 完成前按 diff 逐项复核仅名称/路径/CLI 指向变化 |
| R3 | 历史迁移事实与兼容标识保持，不误改 archive 或 rvc-change/v1 | user:current-request | not_satisfied | 完成前检查 archive 无 diff、template/schema 仍为 rvc-change/v1 |
| R4 | 当前 Coding Skill 必须保持可用，并用自动化回归阻止 live 旧引用再次出现 | AGENTS.md | not_satisfied | 新增 migration cleanliness self-test，并由永久 Change Completion Gate 执行 |
| R5 | 当前正式入口继续为 .agents/skills/coding/SKILL.md 和 coding.py，不建立旧路径兼容层 | .agents/skills/coding/SKILL.md | not_satisfied | 完成前验证 current paths、CLI 和 self-tests |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | Coding migration cleanliness self-test：live 品牌/路径/CLI 与历史兼容白名单 |
| 接口 / Contract | not_applicable | 不修改任何产品/public Contract；rvc-change/v1 明确保留，不发生 Schema 迁移 |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改数据库、文件持久化、Runtime dependency 或运行时代码 |
| 用户 / Workflow Acceptance | not_applicable | 不修改产品用户工作流；Coding CLI 实现不变，只校正规则中的使用路径 |
| 跨组件 Golden Path | not_applicable | 不存在产品跨组件接线变化 |
| External Dependency / Provider Probe | not_applicable | 不涉及任何第三方 Provider 当前事实 |
| Build / Package / Runtime | not_applicable | 不修改 build/package/runtime 实现或产物 |
| Docs / Governance / Other | required | Skill live 文本、模板、历史边界、Change Ready Check 与永久 CI 一致性 |

# Completion Audit

- [ ] upstream_re_read：完成前重新读取用户当前要求、AGENTS.md 和 Coding Skill 迁移边界，独立重建完成定义。
- [ ] change_coverage：完成前确认本 Change 覆盖全部已发现 live 迁移残留且没有扩大到规则语义或产品范围。
- [ ] reverse_audit：完成前从 current Skill/agent/template/reference/CLI 指引反向检查不存在旧 live 指向，并复核历史白名单。
- [ ] unresolved_cleared：完成前所有 not_satisfied 清零，所有 required 验证都有新鲜证据。

# 任务

- [x] 从最新 main 恢复仓库与 Coding Skill 当前事实。
- [x] 枚举并区分 live 迁移残留、历史迁移事实和兼容标识。
- [ ] 建立能命中当前残留的最小失败回归测试并确认 Red。
- [ ] 仅修正当前 live 旧名称、旧路径和旧 CLI 指向。
- [ ] 运行 Coding self-tests、Ready Check 与相关永久 CI。
- [ ] 逐文件复核 diff，确认规则语义和历史 archive 未改变。
- [ ] 完成 Requirement Traceability、Completion Audit 和两阶段 Review。

# 验证

## 计划

- Red：永久 `Change Completion Gate` 中运行 `.agents/skills/coding/tests`，确认新增迁移完整性测试因当前 live 残留失败。
- Green：`python -m unittest discover .agents/skills/coding/tests -v`
- CLI/治理：`python .agents/skills/coding/scripts/ready_check.py --root . --require-active-ready`
- Repository CI：当前 PR 触发的永久 CI/Change Completion Gate 必须成功。
- Diff 审计：确认仅本 Change 列出的 Coding migration 文件和测试发生变化，`changes/archive/**` 无 diff。

## 新鲜证据

- 基线 main `5f63cb77bd747b6d8fc1ec3c2b047ab323abfe35`：CI `32848053733`、Runtime Acceptance `32848053725`、Change Completion Gate `32848053747` 均为 success。

# 文档影响

- 只修正 Coding Skill 自身 live reference/template 的迁移遗留；Blueprint、Roadmap、Appendix、Guide 的当前技术内容不受影响，因此不修改。

# 交付

- Branch：`fix/coding-skill-migration-cleanup`
- Commit：开发中
- PR：待创建
- 发布：不适用
