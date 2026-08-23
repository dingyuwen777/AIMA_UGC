---
schema: rvc-change/v1
id: CHG-20260823-numbered-doc-filenames
title: 统一 docs 技术文档编号文件名
level: L2
status: in_progress
owner: chatgpt
branch: docs/numbered-document-filenames
created: 2026-08-23
updated: 2026-08-23
completion_gate: required
depends_on: []
affected_areas:
  - documentation
  - developer-workflow
affected_paths:
  - docs/
  - AGENTS.md
  - README.md
  - .agents/skills/reliable-vibe-coding/SKILL.md
contracts: []
data_changes: []
---

# 目标

统一 `docs/` 下技术文档文件名：除各目录 `README.md` 外，Markdown 技术文档使用两位数字加下划线前缀（例如 `01_`），并按代码/功能开发与阅读依赖顺序编号；`docs/blueprint/` 仅把现有 `01-` 至 `08-` 前缀中的连字符改为下划线。

# 成功标准

- [ ] `docs/` 根目录及 `blueprint`、`appendix`、`collection`、`guides`、`roadmap` 中所有非 README 技术 Markdown 文档均使用 `NN_` 前缀。
- [ ] `docs/blueprint/01-...` 至 `08-...` 仅改名为 `01_...` 至 `08_...`，编号和正文语义不变。
- [ ] 其他目录编号按当前代码/功能开发与阅读依赖顺序确定，README 不编号。
- [ ] 文档正文技术内容、标题、结论和业务语义不改；只允许因文件重命名而同步路径/链接文本。
- [ ] 当前正式导航、README、AGENTS 和 Skill 中的路径引用全部指向新文件名。
- [ ] Reliable Vibe Coding Skill 固化后续新增/调整 `docs/` 技术文档的命名规则。
- [ ] 不修改业务代码、Contract、Schema、Migration、依赖或运行行为。

# 范围

- 重命名 `docs/` 下非 README 的技术 Markdown 文档。
- 同步当前正式文档、根 README、AGENTS、Skill 中受影响的路径引用。
- 在 Skill 中增加 `docs/` 技术文档编号规范。

# 非目标

- 不修改文档技术正文、标题或业务结论。
- 不重写 `changes/archive/` 历史 Change 中的当时路径证据。
- 不给模块 README 或 `docs/assets/` 资源文件编号。
- 不新增业务能力、依赖或 CI 机制。

# 必须保持不变

- README 文件名保持 `README.md`。
- Blueprint 现有 01—08 顺序保持不变，只替换编号后的 `-` 为 `_`。
- 历史 Change 保持历史事实，不为新路径批量改写归档证据。
- 公共 API、数据库、配置、运行入口和测试语义不变。

# 关键决策

1. 编号以每个 `docs` 目录为独立序列，不做跨目录全局连续编号。
2. 编号表达代码/功能开发与阅读依赖顺序；平台文档沿当前生产入口顺序：小红书、抖音、微博、B站、快手。
3. 文件重命名后只同步必要的路径/Markdown 链接，不改正文语义。
4. 规则写入 `.agents/skills/reliable-vibe-coding/SKILL.md`，后续 Agent 在创建或整理 `docs/` 技术文档时必须遵守。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | docs 非 README 技术文档统一使用 `NN_` 前缀 | user:docs-number-prefix | not_satisfied | 待实施并核对仓库树 |
| R2 | 编号按代码及功能开发先后顺序组织 | user:docs-development-order | not_satisfied | 待实施并核对各目录顺序 |
| R3 | Blueprint 只把开头编号后的 `-` 替换为 `_` | user:blueprint-separator-only | not_satisfied | 待完成 01—08 精确重命名 |
| R4 | 不改变文档正文内容 | user:preserve-doc-content | not_satisfied | 仅允许路径引用同步，待 diff/内容核对 |
| R5 | 把固定命名规则写入 Skill | user:skill-governance | not_satisfied | 待修改 Skill |
| R6 | 现有仓库治理和验证规则继续生效 | AGENTS.md | not_satisfied | 待完成链接/导航、Ready Check 和 CI 验证 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改页面或用户业务行为 |
| Backend/API/PostgreSQL Integration | not_applicable | 不修改后端、数据库或异步业务行为 |
| Contract / Generated Client | not_applicable | 无 Pydantic/OpenAPI/generated client 变化 |
| Real Full-stack Golden Path | not_applicable | 无跨组件运行链变化 |
| Real Provider Probe | not_applicable | 不修改 TikHub/LLM Provider |
| Docs / Governance / Other | required | 核对仓库树、文件命名、路径引用、文档内容差异、Skill 规则、文档质量门禁与 PR CI |

# Completion Audit

- [ ] upstream_re_read：已重新读取本轮用户明确要求、AGENTS、Skill 和当前 docs 树。
- [ ] change_coverage：已确认所有 docs 技术 Markdown 文档都纳入编号或 README/资源例外。
- [ ] reverse_audit：已从新文件名反查导航/链接，并确认历史 Change 不被重写。
- [ ] unresolved_cleared：所有 `not_satisfied` 已清零，不适用项有明确依据。

# 任务

- [x] 调查当前实现和事实源
- [x] 说明测试例外：纯文档/治理重命名不伪造 Red-Green；改用树、链接、diff、质量门禁和 CI 验证
- [x] 建立 Validation Matrix
- [ ] 完成 docs 文件名映射与重命名
- [ ] 同步当前正式引用和 Skill 规则
- [ ] 核对文档正文无语义改动
- [ ] 取得新鲜验证证据
- [ ] 完成 Requirement Traceability 与 Completion Audit

# 验证

## 计划

- 树检查：所有 `docs/**/*.md`（README 除外）满足 `^[0-9]{2}_`。
- Blueprint 检查：01—08 只发生 `-` → `_` 文件名前缀变化。
- 内容检查：重命名文档正文仅允许路径/链接目标随新文件名变化。
- 文档门禁：`uv run python scripts/quality/check_docs.py`。
- Ready Check：`python .agents/skills/reliable-vibe-coding/scripts/ready_check.py --root . --require-active-ready`。
- PR CI：按仓库永久工作流执行。

## 新鲜证据

- 尚未执行。

# 文档影响

- `docs/` 文件名和内部路径引用调整；技术正文语义保持不变。
- `AGENTS.md`、根 `README.md` 的导航路径同步。
- `SKILL.md` 新增长期文档命名规范。

# 交付

- Commit：待完成
- PR：待创建
- 发布：不涉及运行发布
