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

彻底清除已完成 Skill 改名后遗留在当前 live Coding Skill 中的旧品牌、旧目录、旧 CLI 和旧 reference 文件名，使当前规则只描述正式 `Coding` 名称、`.agents/skills/coding/` 路径、`.agents/project-context.json` 缓存与 `coding.py` CLI；不保留任何旧迁移标识作为 live 规则示例或历史白名单。

# 成功标准

- [x] 当前 `.agents/skills/coding/` 的 live 文本不再包含旧品牌、旧目录、旧 CLI 或旧 reference 文件名。
- [x] `12_规则保留映射.md` 保留所有规则细节和内容守恒要求，但只描述当前 canonical reference、缓存路径和 CLI，不保留迁移前标识。
- [x] `CHANGE.template.md` 的所有 live Skill/reference/Ready Check 路径都指向 `.agents/skills/coding/`。
- [x] `rvc-change/v1` 作为仍在使用的 Change schema 标识保持不变；本次不做 Change Schema 迁移。
- [x] 新增回归检查能先命中遗留，再在彻底清理后证明整个 live Coding Skill 无旧迁移标识。
- [x] 除迁移历史表述清理与对应回归检查外，不修改任何既有规则含义、产品代码、Contract、Schema/Migration、依赖、Runtime、Blueprint 或其他治理机制。

# 范围

- 修正 `.agents/skills/coding/` 当前 live 文件中的旧品牌、旧 canonical 路径、旧 CLI 与旧 reference 文件名。
- 清理 `12_规则保留映射.md` 中仅用于迁移历史追溯的旧标识，同时逐条保留其规则内容、触发条件、例外、失败处理和验证责任。
- 新增并收紧一个迁移完整性回归测试，用于阻止相同 live 遗留再次出现。
- 本 Change 与 PR 记录只描述本次迁移清理和验证证据，不再把旧标识写成需要保留的当前事实。

# 非目标

- 不总结、精简、删减、合并或调整 Coding Skill 任一既有规则的语义、触发条件、例外、失败处理、验证责任、安全边界或兼容要求。
- 不重写 Git 历史；既有已归档 Change 继续作为历史证据存在。
- 不修改 `rvc-change/v1` Change Schema 标识；本次没有 Change Schema 迁移。
- 不修改产品代码、HTTP Contract、OpenAPI/generated client、数据库 Schema/Migration、依赖、Runtime、部署或 Branch Protection/Ruleset。
- 不删除远端历史/临时分支；分支治理不属于 live Skill 内容迁移。

# 必须保持不变

- `.agents/skills/coding/SKILL.md` 当前全部规则语义保持不变。
- `references/01_—12_` 中所有实际规则、触发条件、例外、失败处理、验证责任、安全边界和兼容要求保持不变；只允许修改迁移标识和迁移历史组织文字。
- `agents/openai.yaml` 当前 `Coding` metadata/default prompt 保持不变。
- `coding.py`、`ready_check.py` 的代码和 CLI 行为保持不变。
- `rvc-change/v1` 的历史兼容读取保持不变。
- 产品代码、Blueprint、Contract、Schema/Migration、依赖和 Runtime 保持不变。

# 关键决策

- 当前名称唯一使用 `Coding`；当前 canonical 路径唯一使用 `.agents/skills/coding/`；项目缓存唯一使用 `.agents/project-context.json`；当前 CLI 唯一使用 `coding.py`。
- live `12_规则保留映射.md` 不再承担保存旧命名字符串的职责；它只负责逐条证明当前规则内容没有因重组、通用化、拆分或改名而丢失。
- 回归检查扫描整个 live Coding Skill 的 Markdown/YAML/Python 文本，并显式禁止旧品牌、旧目录、旧 CLI 和旧 reference 文件名；测试自身使用字符串拼接避免把被禁止标识重新写入 live Skill。
- `rvc-change/v1` 是仍在使用的 Change schema 标识，不等同于 Skill 的品牌、目录或 CLI；迁移它会扩大到 Change Parser 与历史 Change Schema，不属于本次范围。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 当前 live Coding Skill 不保留任何旧品牌、旧目录、旧 CLI 或旧 reference 文件名 | user:current-request | satisfied | 收紧后的 Red HEAD `559a4432` 在 Change Gate `32854881826` 中仅因 `12_规则保留映射.md` 仍含旧迁移标识失败；Green HEAD `d057060b` 的 Change Gate `32855148851` 中该检查通过 |
| R2 | 不总结或改变任一既有规则及含义，只清迁移历史与标识 | user:current-request | satisfied | `12_规则保留映射.md` 仍逐项保留 13 条基础不变量、1—11 工作流、设计/调试细节、分层测试、Change/Completion、协作、Review、Overlay 和自动化守护；只删除旧命名历史并改成当前 canonical 表述 |
| R3 | 当前 Coding Skill 必须保持可用，并用自动化回归阻止迁移遗留再次出现 | AGENTS.md | satisfied | Green HEAD `d057060b`：Change Gate `32855148851` success，Coding self-tests `Ran 18 tests` / `OK`，Ready Check `gated=38, strict=38, legacy=72` |
| R4 | 当前正式入口继续为 `.agents/skills/coding/SKILL.md`、`.agents/project-context.json` 与 `coding.py`，不建立旧路径兼容层 | .agents/skills/coding/SKILL.md | satisfied | 迁移完整性测试全量扫描 live Skill，并真实执行 `coding.py discover/status/conflicts --help`；`12` 只保留当前 cache/CLI/reference 路径 |
| R5 | 不扩大到产品、Blueprint、Contract、Schema/Migration、依赖和 Runtime | user:current-request | satisfied | PR diff 仅涉及 5 个 Coding live 规则/模板、1 个 Coding 回归测试和本 Change；未修改产品与正式系统事实源 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | Green HEAD `d057060b`：Change Gate `32855148851` 中 Coding self-tests `18/18` 通过；回归扫描整个 live Skill 并验证当前 CLI 子命令 |
| 接口 / Contract | not_applicable | 不修改任何产品/public Contract；`rvc-change/v1` 继续保持，不发生 Change Schema 迁移 |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改数据库、文件持久化、Runtime dependency 或运行时代码 |
| 用户 / Workflow Acceptance | not_applicable | 不修改产品用户工作流；Coding CLI 实现不变，只清理规则指引和迁移历史标识 |
| 跨组件 Golden Path | not_applicable | 不存在产品跨组件接线变化 |
| External Dependency / Provider Probe | not_applicable | 不涉及任何第三方 Provider 当前事实 |
| Build / Package / Runtime | not_applicable | 不修改 build/package/runtime 实现或产物 |
| Docs / Governance / Other | required | `12` 内容守恒人工逐节复核 + live Skill 全量旧标识自动扫描 + Ready Check；Repository CI/Runtime/Full-stack 作为仓库永久门禁继续运行 |

# Completion Audit

- [x] upstream_re_read：用户补充明确要求“迁移完成后不再保留旧标识”；已据此重新读取当前 `AGENTS.md`、`SKILL.md` 与 live `12`，将完成定义更新为“当前 Skill 只保留当前 canonical 表述”。
- [x] change_coverage：旧标识检查从 01—11/template 扩展为整个 `.agents/skills/coding/` live Markdown/YAML/Python 文本；`12` 不再作为历史白名单例外。
- [x] reverse_audit：从 Skill identity、Agent metadata、全部 reference、Change template、CLI 指引和缓存路径反向检查，当前 live Skill 均指向 `Coding` / `.agents/skills/coding/` / `.agents/project-context.json` / `coding.py`。
- [x] unresolved_cleared：R1—R5 均有新的 Red/Green、diff 或范围证据；required 验证层已有当前证据。

# 两阶段 Review

## Review A1：上游要求 → Change

重新从用户当前要求与仓库规则独立核对：

- 迁移结束后，live Coding Skill 不得再保留旧品牌、旧目录、旧 CLI 或旧 reference 文件名；
- 不允许为了清理迁移历史而总结、删减或改变既有规则含义；
- `12_规则保留映射.md` 继续承担内容守恒审计，但只使用当前 canonical 表述；
- 不扩大到产品代码、Blueprint、Contract、Schema/Migration、依赖、Runtime 或 Branch Protection；
- Git 历史和既有 archive 不重写。

R1—R5 覆盖上述全部上游要求，未发现遗漏、延期或伪造不适用项。

## Review A2：Change → 实现 / 测试 / 文档

- 02：只把现行 Skill 名称统一为 `Coding`。
- 03：只把现行 Skill 名称统一为 `Coding`。
- 09：只把冲突检查指引切到真实 `coding.py` CLI。
- `CHANGE.template.md`：只把 Skill/reference/Ready Check 的 canonical 路径统一到 `.agents/skills/coding/`；Change schema 保持不变。
- 12：所有规则细节继续逐项存在；删除旧命名、旧路径、旧 CLI、旧 reference 文件名及对应迁移演进叙事，改为当前 canonical reference/缓存/CLI 与当前规则归属。
- 回归测试：从“允许 12 保留历史白名单”收紧为“整个 live Coding Skill 无旧迁移标识”，并继续真实检查 `coding.py discover/status/conflicts --help`。

未发现 Change 承诺但未实现的项目。

# Code Quality Review

- 正确性：新增更严格的 Red 明确证明此前保留策略不满足用户最新要求；Green 证明整个 live Skill 已无被禁止迁移标识。
- 规则守恒：`12` 仍完整列出基础不变量、统一工作流、设计/调试、分层测试、Change/Completion、协作、Review、Overlay 与自动化守护；没有删除规则条款。
- 边界：只有迁移历史组织文字允许调整；产品、Contract、Schema/Migration、依赖和 Runtime 未动。
- 兼容：`rvc-change/v1` 保持；不修改 `coding.py`/`ready_check.py` 行为或产品持久化格式。
- 可维护性：使用一个 stdlib unittest 扫描 live Skill 文本；不新增依赖或第二套扫描框架。
- 注释：新增/修改测试 helper 与 test function 均有中文函数级文档字符串。
- 安全/隐私：不接触 Secret、外部服务或生产数据。

未发现严重或重要问题。

# 任务

- [x] 从最新 main 恢复仓库与 Coding Skill 当前事实。
- [x] 枚举当前 live 迁移遗留。
- [x] 建立初始 Red/Green，清理 02、03、09、template 等直接 live 指向。
- [x] 根据用户补充要求收紧回归：`12` 不再允许历史白名单。
- [x] 确认收紧后的 Red 仅命中 `12` 的迁移历史遗留。
- [x] 清理 `12` 的旧迁移标识，同时逐项保留所有规则语义和细节。
- [x] 确认 Green self-tests 与 Ready Check 通过。
- [ ] 等待最终证据 HEAD 的永久 CI、Runtime Acceptance、Full-stack Acceptance 全部完成并补交付记录。

# 验证

## 计划

- 初始 Red：验证直接 live 品牌/路径/CLI 遗留可被回归捕获。
- 收紧 Red：整个 live Skill 扫描，`12` 也不得保留旧迁移标识。
- Green：`python -m unittest discover .agents/skills/coding/tests -v`
- CLI/治理：`python .agents/skills/coding/scripts/ready_check.py --root . --changed-since <base-sha>`。
- Repository CI：最终 Ready HEAD 触发的永久 CI、Change Completion Gate、Runtime Acceptance、Full-stack Acceptance 必须成功。
- Diff 审计：确认没有产品、Blueprint、Contract、Schema/Migration、依赖或 Runtime 差异。

## 新鲜证据

- 基线 main `5f63cb77bd747b6d8fc1ec3c2b047ab323abfe35`：CI `32848053733`、Runtime Acceptance `32848053725`、Change Completion Gate `32848053747` 均为 success。
- 初始 Red HEAD `195cdf9f46f12bd93a8ff80668bc9442002fc41b`：Change Gate `32852518744`，新增迁移检查 3 项准确命中直接 live 残留。
- 初始 Green/Ready HEAD `7ce5b45108687a6f5b550c3fa025656bdb62df15`：Change Gate `32854010045`、CI `32854010334`、Runtime `32854009971`、Full-stack `32854009983` 均 success，但用户随后明确不允许 `12` 继续保留任何旧迁移标识，因此该状态不再作为最终完成结论。
- 收紧 Red HEAD `559a44323fd8cee30ea80d4364c6aae194676c67`：Change Gate `32854881826`，18 个 Coding self-tests 中仅 `test_live_skill_contains_no_legacy_migration_identifiers` 失败，失败点为 `12_规则保留映射.md` 的旧迁移标识，其余测试通过。
- 收紧 Green HEAD `d057060b833418d60646cdaa0dcb4c01727378e4`：Change Gate `32855148851` success；Coding self-tests `Ran 18 tests` / `OK`；`test_live_skill_contains_no_legacy_migration_identifiers` 和 `test_preservation_map_uses_only_current_canonical_locations` 均通过；Ready Check `gated=38, strict=38, legacy=72`。

# 文档影响

- 只修改 Coding Skill 自身 live reference/template 与本次迁移记录；Blueprint、Roadmap、Appendix、Guide 的当前技术内容不受影响，因此不修改。

# 交付

- Branch：`fix/coding-skill-migration-cleanup`
- PR：#235 `清理 Coding Skill 迁移遗留`
- 当前状态：`ready_for_review`
- 最终规则口径：live Coding Skill 不保留任何旧品牌、旧目录、旧 CLI 或旧 reference 文件名。
- 发布：不适用
