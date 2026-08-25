---
schema: rvc-change/v1
id: CHG-20260825-coding-skill-migration-cleanup
title: Coding Skill 迁移遗留清理
level: L2
status: ready_for_review
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

- [x] 当前 live Coding Skill 的规范性文本不再把 `Reliable Vibe Coding` 作为现行名称。
- [x] 当前 live Coding Skill 的可执行路径不再引用 `.agents/skills/reliable-vibe-coding/` 或把 `rvc.py` 作为现行 CLI。
- [x] `12_规则保留映射.md` 继续保留迁移前旧名称/旧命令的历史事实，但明确区分历史命令与当前 `coding.py` 命令。
- [x] `CHANGE.template.md` 的所有 live Skill/reference/Ready Check 路径都指向 `.agents/skills/coding/`。
- [x] `rvc-change/v1` 等明确历史兼容标识保持不变；`changes/archive/**` 历史叙事不改写。
- [x] 新增回归检查能在当前残留存在时失败，并在迁移遗留清理后通过。
- [x] 除上述迁移遗留与回归检查外，不修改任何规则含义、产品代码、Contract、Schema/Migration、依赖、Runtime、Blueprint 或其他治理机制。

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
| R1 | 全面清理当前 live Coding Skill 的旧名称、旧路径和旧 CLI 迁移遗留 | user:current-request | satisfied | `test_migration_cleanliness.py` 在 Red run `32852518744` 精确命中 3 类 live 残留；Green run `32853655171` 的 18 个 Coding self-tests 全部通过 |
| R2 | 不总结或改变任一既有规则及含义，只做迁移遗留最小替换 | user:current-request | satisfied | `5f63cb77...0ff859a1` diff：02 仅 3 处品牌替换、03 仅 1 处品牌替换、09 仅 1 处 CLI 文件名替换、template 仅 4 处路径替换；12 仅迁移历史/当前标注与当前路径修正 |
| R3 | 历史迁移事实与兼容标识保持，不误改 archive 或 rvc-change/v1 | user:current-request | satisfied | compare 仅 7 个本 Change 文件且无 `changes/archive/**`；回归测试明确保留迁移前 `.reliable-vibe-coding`/`rvc.py` 历史并断言 `schema: rvc-change/v1` |
| R4 | 当前 Coding Skill 必须保持可用，并用自动化回归阻止 live 旧引用再次出现 | AGENTS.md | satisfied | Green run `32853655171`：`python -m unittest discover .agents/skills/coding/tests -v` → `Ran 18 tests` / `OK`，并实际执行 `coding.py discover/status/conflicts --help` |
| R5 | 当前正式入口继续为 .agents/skills/coding/SKILL.md 和 coding.py，不建立旧路径兼容层 | .agents/skills/coding/SKILL.md | satisfied | 完成前重读 `AGENTS.md`/`SKILL.md`；回归测试确认旧 Skill 目录不存在且当前 live 指引只使用 `coding.py`/`.agents/skills/coding/` |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | Green run `32853655171`：Coding self-tests `18/18` 通过；迁移测试同时验证 live 品牌/路径/CLI、历史白名单与真实 `coding.py` 子命令 |
| 接口 / Contract | not_applicable | 不修改任何产品/public Contract；`rvc-change/v1` 明确保留，不发生 Schema 迁移 |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改数据库、文件持久化、Runtime dependency 或运行时代码 |
| 用户 / Workflow Acceptance | not_applicable | 不修改产品用户工作流；Coding CLI 实现不变，只校正规则中的使用路径 |
| 跨组件 Golden Path | not_applicable | 不存在产品跨组件接线变化 |
| External Dependency / Provider Probe | not_applicable | 不涉及任何第三方 Provider 当前事实 |
| Build / Package / Runtime | not_applicable | 不修改 build/package/runtime 实现或产物 |
| Docs / Governance / Other | required | compare `5f63cb77...0ff859a1` 仅 7 个范围内文件；无 archive/产品/Blueprint/Contract 差异；最终 PR Ready Check/CI 由 Ready HEAD 永久门禁继续验证 |

# Completion Audit

- [x] upstream_re_read：已在转 Ready 前重新读取用户当前要求、`AGENTS.md` 和 `.agents/skills/coding/SKILL.md`，独立重建完成定义：只清迁移遗留，不改规则语义，历史事实/兼容标识保留。
- [x] change_coverage：已逐项覆盖 02、03、09、12、`CHANGE.template.md` 的全部已确认 live 遗留，并以回归测试覆盖当前 live 表面和历史白名单；没有扩大到其他规则或产品范围。
- [x] reverse_audit：已从当前 Skill identity、Agent/template/reference、CLI 指引反向检查 canonical 指向；`references/01—11` 与 template 不得出现旧 live 品牌/路径，12 只允许明确迁移历史，当前 `08` 路径必须为 `coding/`。
- [x] unresolved_cleared：R1—R5 均有实现、diff 或新鲜 self-test 证据，所有 `not_satisfied` 已清零；required 验证层已有当前证据。

# 两阶段 Review

## Review A1：上游要求 → Change

重新从用户当前要求与仓库规则独立核对：

- 必须彻底完成 `reliable-vibe-coding` → `coding` live 迁移清理；
- 不允许总结、精简或改变任何既有规则含义；
- 迁移历史可以并且必须保留真实旧名称/路径/CLI，但不能再冒充当前事实；
- 当前 Skill 必须保持干净、可执行、可回归验证；
- 不扩大到产品代码、Blueprint、兼容 Schema、Branch Protection 或历史归档重写。

R1—R5 覆盖上述全部上游要求，未发现遗漏、延期或伪造不适用项。

## Review A2：Change → 实现 / 测试 / 文档

- 02：仅把 3 个现行 `Reliable Vibe Coding` 品牌文本替换为 `Coding`。
- 03：仅把开头现行品牌替换为 `Coding`。
- 09：仅把已不存在的 `rvc.py conflicts` 指引改成真实 `coding.py conflicts`。
- `CHANGE.template.md`：仅把 4 个旧 Skill canonical 路径改成 `.agents/skills/coding/`；`rvc-change/v1` 保持不变。
- 12：标题改为当前 `Coding`；迁移前缓存路径与 `rvc.py` 命令原文保留并明确标成历史，同时补当前 `.agents/project-context.json`/`coding.py` 对应项；“当前专项事实源路径”改到 `coding/08`。
- 回归测试：精确区分 live surface、迁移历史和兼容标识，并真实检查 `coding.py discover/status/conflicts --help`。
- compare 证明没有 archive、产品、Blueprint、Contract、Schema/Migration、依赖或 Runtime 差异。

未发现 Change 承诺但未实现的项目。

# Code Quality Review

- 正确性：所有旧 live 指向均由 Red 复现并由 Green 回归覆盖；没有通过兼容旧目录或旧 CLI 绕过问题。
- 边界：迁移历史只在 12 中保留；current/live surface 与历史 white-list 明确分离。
- 兼容：`rvc-change/v1` 保持；不修改 `coding.py`/`ready_check.py` 行为、产品 Contract 或持久化格式。
- 可维护性：只新增一个聚焦 migration cleanliness 的 stdlib unittest，没有新增依赖或第二套扫描框架。
- 注释：新增/修改测试函数均有中文函数级文档字符串。
- 安全/隐私：不接触 Secret、外部服务或生产数据。
- 无关改动：compare 仅包含 5 个 live 迁移文件、1 个回归测试和本 Change；未发现其他差异。

未发现严重或重要问题。

# 任务

- [x] 从最新 main 恢复仓库与 Coding Skill 当前事实。
- [x] 枚举并区分 live 迁移残留、历史迁移事实和兼容标识。
- [x] 建立能命中当前残留的最小失败回归测试并确认 Red。
- [x] 仅修正当前 live 旧名称、旧路径和旧 CLI 指向。
- [x] 完成 Green self-tests、diff 审计、Requirement Traceability、Completion Audit 和两阶段 Review。
- [ ] 在本 Ready HEAD 取得最终 Change Completion Gate 与 Repository CI 成功证据并补入交付记录。

# 验证

## 计划

- Red：永久 `Change Completion Gate` 中运行 `.agents/skills/coding/tests`，确认新增迁移完整性测试因当前 live 残留失败。
- Green：`python -m unittest discover .agents/skills/coding/tests -v`
- CLI/治理：`python .agents/skills/coding/scripts/ready_check.py --root . --changed-since <base-sha>`；Change 转 Ready 后应通过。
- Repository CI：当前 PR Ready HEAD 触发的永久 CI/Change Completion Gate 必须成功。
- Diff 审计：确认仅本 Change 列出的 Coding migration 文件和测试发生变化，`changes/archive/**` 无 diff。

## 新鲜证据

- 基线 main `5f63cb77bd747b6d8fc1ec3c2b047ab323abfe35`：CI `32848053733`、Runtime Acceptance `32848053725`、Change Completion Gate `32848053747` 均为 success。
- Red HEAD `195cdf9f46f12bd93a8ff80668bc9442002fc41b`：Change Completion Gate `32852518744` / job `97816555660`，`Ran 18 tests`，仅新增迁移检查 3 项按预期失败，已有测试和 `rvc-change/v1` 兼容断言通过。
- Green 实现 HEAD `0ff859a11188307f632d8687c5b2332af1cc1b7e`：Change Completion Gate `32853655171` / job `97820290125`，Coding self-tests `Ran 18 tests` / `OK`；随后 Ready Check 唯一失败为 Change 当时仍是 `in_progress`，没有实现/测试失败。
- Diff 审计：compare `5f63cb77...0ff859a1` 为 `ahead_by=8 / behind_by=0`，仅 7 个范围内文件；无 `changes/archive/**`、产品代码、Blueprint、Contract、Schema/Migration、依赖或 Runtime 差异。

# 文档影响

- 只修正 Coding Skill 自身 live reference/template 的迁移遗留；Blueprint、Roadmap、Appendix、Guide 的当前技术内容不受影响，因此不修改。

# 交付

- Branch：`fix/coding-skill-migration-cleanup`
- PR：#235 `清理 Coding Skill 迁移遗留`
- 当前状态：`ready_for_review`，等待本 Ready HEAD 永久门禁最终证据。
- 发布：不适用
