---
schema: rvc-change/v1
id: CHG-20260823-numbered-doc-filenames
title: 统一 docs 技术文档编号文件名
level: L2
status: ready_for_review
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
  - changes/archive/2026-08/*/CHANGE.md
contracts: []
data_changes: []
---

# 目标

统一 `docs/` 下技术文档文件名：除各目录 `README.md` 外，Markdown 技术文档使用两位数字加下划线前缀（例如 `01_`），并按代码/功能开发与阅读依赖顺序编号；`docs/blueprint/` 仅把现有 `01-` 至 `08-` 前缀中的连字符改为下划线。

# 成功标准

- [x] `docs/` 根目录及 `blueprint`、`appendix`、`collection`、`guides`、`roadmap` 中所有非 README 技术 Markdown 文档均使用 `NN_` 前缀。
- [x] `docs/blueprint/01-...` 至 `08-...` 仅改名为 `01_...` 至 `08_...`，编号和正文语义不变。
- [x] 其他目录编号按当前代码/功能开发与阅读依赖顺序确定，README 不编号。
- [x] 文档正文技术内容、标题、结论和业务语义不改；只允许因文件重命名而同步路径/链接文本。
- [x] 当前正式导航、README、AGENTS 和 Skill 中的路径引用全部指向新文件名。
- [x] Reliable Vibe Coding Skill 固化后续新增/调整 `docs/` 技术文档的命名规则。
- [x] 不修改业务代码、Contract、Schema、Migration、依赖或运行行为。

# 范围

- 重命名 `docs/` 下非 README 的技术 Markdown 文档。
- 同步当前正式文档、根 README、AGENTS、Skill、测试说明字符串和永久 CI path filter 中受影响的路径引用。
- 在 Skill 中增加 `docs/` 技术文档编号规范。
- 刷新 Reliable Vibe Coding 项目事实源索引，使其记录新路径。

# 非目标

- 不修改文档技术正文、标题或业务结论。
- 不改写 `changes/archive/` 历史 Change 的状态、证据与结论；仅允许同步 Ready Check 要求持续可解析的 `Requirement Source` 仓库路径。
- 不给模块 README 或 `docs/assets/` 资源文件编号。
- 不新增业务能力、依赖或永久 CI 机制。

# 必须保持不变

- README 文件名保持 `README.md`。
- Blueprint 现有 01—08 顺序保持不变，只替换编号后的 `-` 为 `_`。
- 历史 Change 保持历史事实，不为新路径批量改写归档证据。
- 公共 API、数据库、配置、运行入口和测试语义不变。

# 关键决策

1. 编号以每个 `docs` 目录为独立序列，不做跨目录全局连续编号。
2. 编号表达代码/功能开发与阅读依赖顺序；平台文档沿当前生产入口顺序：小红书、抖音、微博、B站、快手。
3. Appendix 依据当前 Roadmap 的正式阶段事实排序：PostgreSQL → TikHub → Scheduler → Excel → AI → 数据入口 → Stage 8F 验收 → Word 报告 → Production。
4. 文件重命名后只同步必要的路径/Markdown 链接，不改正文语义。
5. 规则写入 `.agents/skills/reliable-vibe-coding/SKILL.md`，后续 Agent 在创建或整理 `docs/` 技术文档时必须遵守。
6. 归档 Change 的历史状态、证据和结论保持不变；仅同步 Ready Check 持续校验的 `Requirement Source` 路径，使重命名后仍指向同一事实源。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | docs 非 README 技术文档统一使用 `NN_` 前缀 | user:docs-number-prefix | satisfied | Runner `32636480935` / job `97186918732` 的编号集合检查通过；33 个技术 Markdown 均纳入映射，README 例外保留 |
| R2 | 编号按代码及功能开发先后顺序组织 | user:docs-development-order | satisfied | Appendix 依据 `docs/roadmap/02_生产上线实施路线.md` 的正式 Stage 事实调整为 PostgreSQL → TikHub → Scheduler → 后续能力；collection 维持正式平台实现顺序 |
| R3 | Blueprint 只把开头编号后的 `-` 替换为 `_` | user:blueprint-separator-only | satisfied | Runner 对 `docs/blueprint` 01—08 精确文件集合校验通过；首轮重命名提交复用原 Blob |
| R4 | 不改变文档正文内容 | user:preserve-doc-content | satisfied | 初始 33 篇重命名提交 `ea87400fd5a7cb0c5d4dd4dc62d8a1c6790a47b3` 复用原 Blob；Runner 将每篇新文档与 `origin/main` 旧路径进行仅允许文件名/链接迁移的内容对比并通过 |
| R5 | 把固定命名规则写入 Skill | user:skill-governance | satisfied | `.agents/skills/reliable-vibe-coding/SKILL.md` 新增唯一 `docs/` 技术文档文件名规范，Runner 对关键约束逐项检查通过 |
| R6 | 现有仓库治理和验证规则继续生效 | AGENTS.md | satisfied | Runner 刷新 `rvc discover` 成功，项目事实源索引仅含新路径；`python scripts/quality/check_docs.py` 成功；最终永久 PR CI 作为合并门禁继续执行，不绕过 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改页面或用户业务行为 |
| Backend/API/PostgreSQL Integration | not_applicable | 不修改后端、数据库或异步业务行为 |
| Contract / Generated Client | not_applicable | 无 Pydantic/OpenAPI/generated client 变化 |
| Real Full-stack Golden Path | not_applicable | 无跨组件运行链变化 |
| Real Provider Probe | not_applicable | 不修改 TikHub/LLM Provider |
| Docs / Governance / Other | required | Runner `32636480935` / job `97186918732`：编号、正文完整性、旧引用、事实源索引、本地 Markdown 链接和现有文档质量门禁全部通过；最终永久 PR CI 继续作为合并条件 |

# Completion Audit

- [x] upstream_re_read：已重新读取本轮用户明确要求、AGENTS、Skill、Roadmap 和当前 docs 树，并以仓库事实纠正 Appendix 的最终顺序。
- [x] change_coverage：已确认所有 `docs/**/*.md` 技术文档都纳入编号或 `README.md` 例外，`docs/assets/` 非 Markdown 资源不适用。
- [x] reverse_audit：已从新文件名反查当前导航、Markdown 本地链接、代码/测试说明字符串和永久 CI path filter；历史 `changes/archive/` 不被改写。
- [x] unresolved_cleared：R1—R6 均已有新鲜证据；不适用的运行时验证层已说明依据。

# 任务

- [x] 调查当前实现和事实源
- [x] 说明测试例外：纯文档/治理重命名不伪造 Red-Green；改用树、链接、diff、质量门禁和 CI 验证
- [x] 建立 Validation Matrix
- [x] 完成 docs 文件名映射与重命名
- [x] 同步当前正式引用和 Skill 规则
- [x] 核对文档正文无语义改动
- [x] 取得新鲜验证证据
- [x] 完成 Requirement Traceability 与 Completion Audit

# 验证

## 计划

- 树检查：所有 `docs/**/*.md`（README 除外）满足 `^[0-9]{2}_`。
- Blueprint 检查：01—08 只发生 `-` → `_` 文件名前缀变化。
- 内容检查：重命名文档正文仅允许路径/链接目标随新文件名变化。
- 引用检查：当前有效文件不存在旧文件名、混合编号或失效本地 Markdown 链接。
- 项目发现：重新生成 `.reliable-vibe-coding/project-context.json` 并检查只记录新路径。
- 文档门禁：`python scripts/quality/check_docs.py`。
- Ready Check：`python .agents/skills/reliable-vibe-coding/scripts/ready_check.py --root . --require-active-ready`，由永久 Change Completion Gate 在最终 HEAD 上执行。
- PR CI：按仓库永久工作流执行，全部通过后才允许合并。

## 新鲜证据

- `ea87400fd5a7cb0c5d4dd4dc62d8a1c6790a47b3`：33 篇文档以原 Blob SHA 建立新路径并删除旧路径，重命名阶段正文保持字节级不变。
- `2f8d9fa50e6339fa2b5b01c306d69fa5ba888d89`：Appendix 02—05 按实际 Stage 开发顺序重新编号，继续复用已有 Blob。
- GitHub Actions run `32636480935` / job `97186918732`（Ubuntu 24.04）：
  - `rvc.py discover --root . --json`：成功，刷新后的事实源索引包含最终编号路径；
  - 一次性完整性校验：成功，覆盖编号集合、Blueprint 精确集合、Appendix 顺序、33 篇正文允许差异、Skill 规则、旧引用、事实源索引、本地 Markdown 链接；
  - `python scripts/quality/check_docs.py`：成功；
  - job conclusion：`success`。
- GitHub Actions run `32636689174` / job `97187424911`：仅在归档 Change 的 Requirement Traceability `| R... |` 行中同步 22 个 `Requirement Source` 路径，8 个归档 Change 受影响；job conclusion：`success`。
- 一次性迁移/校验 workflow 与脚本在进入最终永久 CI 前删除，不作为仓库长期机制保留。

# 文档影响

- `docs/` 文件名和内部路径引用调整；技术正文语义保持不变。
- `AGENTS.md`、根 `README.md`、各文档导航及受影响模块 README 的路径同步。
- 永久 workflow 仅同步文档 path filter；不改变 job、测试或运行语义。
- `SKILL.md` 新增长期文档命名规范。
- `.reliable-vibe-coding/project-context.json` 刷新为当前最终路径事实。

# 交付

- Branch：`docs/numbered-document-filenames`
- Draft PR：#173 `统一 docs 技术文档编号命名`
- 核心重命名 Commit：`ea87400fd5a7cb0c5d4dd4dc62d8a1c6790a47b3`
- Appendix 顺序 Commit：`2f8d9fa50e6339fa2b5b01c306d69fa5ba888d89`
- 项目事实源刷新 Commit：`1159fc914831bb5e1e8b738c293382eb0ab1e0a7`
- 发布：不涉及运行发布、Migration、依赖或部署变更
