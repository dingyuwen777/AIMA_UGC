---
schema: rvc-change/v1
id: CHG-20260825-portable-reliable-vibe-coding
title: Reliable Vibe Coding 跨项目跨阶段跨语言通用化重组
level: L2
status: in_progress
owner: aima
branch: refactor/reliable-vibe-coding-portable-routing
created: 2026-08-25
updated: 2026-08-25
completion_gate: required
depends_on: []
affected_areas:
  - developer-tooling
  - agent-workflow
  - testing-governance
affected_paths:
  - .agents/skills/reliable-vibe-coding/
  - AGENTS.md
  - docs/AGENTS.md
  - docs/blueprint/06_开发约束与分阶段实施.md
  - changes/archive/2026-08/CHG-20260825-ci-long-term-risk-layers/CHANGE.md
  - tests/unit/test_reliable_vibe_coding_portability.py
contracts: []
data_changes: []
---

# 背景与当前事实

当前仓库只有一套 `.agents/skills/reliable-vibe-coding/` Skill。原 Skill 已经包含项目发现、L1-L3 分级、Change 管理、Requirement Traceability、Completion Audit、Red-Green-Refactor、根因调试、分层验证、多人协作、Review、Git 和交付证据等完整机制，但主 `SKILL.md` 同时承担入口、路由、流程正文、AIMA/Web 技术形态示例和交付门禁，容易让可移植规则与当前项目专项规则混在一起。

第一轮通用化已经完成四维任务路由、多语言工具链 profile、技术栈无关 Validation Matrix、规则保留映射和 `rvc.py` 多语言 Manifest 发现，并在 PR #222 的前一候选 HEAD 上取得完整 CI/Completion/Runtime/Full-stack Green。用户随后明确补充两个要求，因此本 Change 重新从 `ready_for_review` 回到 `in_progress`，PR #222 也已重新转为 Draft：

1. 通用 Skill 不能把 `Blueprint 01—08`、固定文档数量、固定文件名或固定编号上限写死；不同项目应以自己的实际文档集合和本地规则为准。
2. `references/` 中按研发阶段拆分的规范文件应使用 `01_、02_……` 的两位数字前缀，并按研发流程阅读顺序排列，方便人工阅读；编号只是当前导航，不得反向变成“永远只能有 N 份 reference”的新硬编码。

现有 Web/API/PostgreSQL/Provider 专项测试策略的**规则内容**仍必须完整保留。由于本轮要把全部 reference 统一为编号文件，原 `testing-strategy.md` 的当前规范路径会迁移为 `08_testing-strategy.md`；所有仍被机器当作实时路径解析的引用必须同步迁移，历史 Change 的 Evidence/结论不得因此改写。

本次仍只重组 Skill、治理文档和只读项目发现能力，不改变 AIMA 产品 API、Schema、Migration、运行时、业务行为或依赖锁。

## Git / main 同步事实

任务最初基线为 `main` 的 `e8f974b6679a6e2ef8382324196d70311ec12b3a`。开发过程中 `main` 多次前进：

- 已归档 CI 长期风险层 Change 后同步到 `9b6457d3549dea57f85d52bf664227b47791b9b4`；
- 本轮编号迁移期间，PR #223 合并了 Actions 历史清理，`main` 前进到 `3591c1fbdbfdb50a65c6da3e773fe6e12b1246d5`；
- 比较确认新 main 只新增 `.github/workflows/change-completion-gate.yml`、Actions 历史清理 Change 和维护脚本，没有触碰 Skill；当前分支随后通过双父 merge commit `5eafde1c09c10a0f54ae007c3d93ccc27d616223` 正常同步，没有 force/rebase。

后续所有 Green/Ready 证据必须基于同步该 main 之后的新 HEAD，旧 HEAD Green 只能作为历史开发证据，不能冒充最终结论。

# 目标

把 Reliable Vibe Coding 重组为一个可以复制到不同项目使用的通用研发 Skill，并让 Agent 在执行前先按四个互相独立的维度路由：

```text
项目形态
× 研发阶段 / 任务类型
× 编程语言 / 工具链
× 风险等级 L1-L3
→ 选择最少但充分的规则、验证和交付门禁
```

同时把 Skill 的规范文档按研发流程形成清晰的人类阅读顺序：

```text
01 项目事实发现
→ 02 任务路由
→ 03 语言 / 工具链
→ 04 Change 管理
→ 05 设计 / 实施 / 根因调试
→ 06 仓库边界
→ 07 通用验证
→ 08 Web/API/PostgreSQL/Provider 专项测试
→ 09 多人 / 多 Agent 协作
→ 10 Completion Gate
→ 11 Review / 交付
→ 12 规则保留审计
```

这个列表描述**当前 reference 集合的阅读顺序**，不是固定配额。以后新增、拆分或合并 reference 时必须按真实依赖关系和阅读顺序调整，不能因为现在是 12 份就把 12 写成永久上限。

# 成功标准

- [x] `SKILL.md` 形成清晰的强制入口与四维任务路由，明确先识别项目事实，再选择阶段、工具链、风险规则和验证，而不是默认 Web/Python/PostgreSQL。
- [x] 项目/研发阶段路由覆盖首次接入、需求/设计、实现、Bug/调试、重构、Review、发布/运维、维护/迁移、安全/不可逆操作等阶段。
- [x] 编程语言与工具链适配覆盖 Python、JavaScript/TypeScript、Go、Rust、Java/Kotlin、.NET、C/C++、Swift、Dart/Flutter、PHP、Ruby、Elixir，以及多语言/Monorepo、Container/IaC，并提供未列语言的统一发现算法；不硬编码版本或擅自更换包管理器。
- [x] 通用 Validation Matrix 抽象为行为、接口、真实依赖集成、用户/调用者工作流、跨组件 Golden Path、外部依赖 Probe、Build/Package/Runtime、Docs/Governance 等风险维度；原 Browser/PostgreSQL/Provider 细节继续作为条件式专项 profile。
- [x] `CHANGE.template.md` 不要求所有项目机械使用 Browser/PostgreSQL/Provider 行名，同时保留专项层映射和适用条件。
- [x] `rule-preservation-map` 逐项登记原主 Skill 13 条不变量、统一工作流 1—11、旧 reference、TDD、根因调试、Git/依赖/安全、注释、可观测性、文档同步和专项测试职责。
- [x] 原主 Skill 中属于 AIMA 项目的 docs 编号/重命名/历史归档知识已由 `docs/AGENTS.md` 正式承载，而不是只留在审计清单。
- [ ] 通用 Skill 不出现把任一项目的 Blueprint 数量、固定文件名或固定编号上限写死为全球规则；AIMA 自己也通过 `docs/AGENTS.md`、当前实际文档集合和 `docs/blueprint/README.md` 动态确定现有 Blueprint，而不是把“当前碰巧是 01—08”变成永久约束。
- [ ] `references/` 当前规范文件全部使用两位数字前缀，并且目录只保留一套编号文件，不保留一套无编号平行规范造成阅读歧义。
- [ ] 所有当前 Skill 内链、AIMA 当前文档导航和仍被 Ready Check 解析的 Requirement Source 已迁移到编号路径；历史 Evidence/结论没有因文件改名而被重写。
- [ ] 自动化回归验证 reference 顺序、编号路径、动态 Blueprint 边界、主要语言覆盖、通用验证层、关键旧规则可达以及 AIMA 专项策略仍完整存在。
- [ ] 本轮新增要求有正确 Red、Green、Completion Audit、两阶段 Review 和最终新鲜 CI/Ready 证据。

# 范围

- 重组 `.agents/skills/reliable-vibe-coding/SKILL.md` 的入口、任务路由和统一流程组织。
- 将 `.agents/skills/reliable-vibe-coding/references/*.md` 当前规范文件迁移为两位数字前缀的研发流程阅读顺序；完成所有实时引用迁移后删除无编号旧副本。
- 维护多语言/工具链 profile、generic Validation Matrix 和 rule preservation map。
- 调整 `change-management`、`completion-gate`、`development-workflows`、`verification-review` 和 `CHANGE.template.md` 的技术栈中立表达与编号路径。
- 保留 Web/API/PostgreSQL/Provider 专项策略的全部有效语义，将当前规范路径迁移到 `08_testing-strategy.md`。
- 增加仓库级 Unit 回归测试验证 Skill 结构、编号顺序、动态文档边界和关键规则可达性。
- 扩充 `rvc.py` 对常见多语言 Manifest/Workspace 的只读发现能力，但不改变缓存/Change schema、Change 解析、冲突检测或 CLI 协议。
- 更新 `agents/openai.yaml`，要求 Agent 先完成四维路由并读取所有命中的 reference 后再执行任务。
- 更新 AIMA 根/嵌套 `AGENTS.md` 和 Blueprint 06 的当前 Skill 路径与动态文档治理说明。
- 对仍使用旧 `testing-strategy.md` 作为实时 Requirement Source 的归档 Change，只迁移 Source 路径，不重写历史 Evidence/结论。

# 非目标

- 不修改 AIMA 产品代码、HTTP/Canonical Contract、数据库 Schema/Migration、前端功能或运行时。
- 不修改当前 CI 风险层架构，不新增平行 CI Workflow。
- 不删除原 reference 中仍有效的规则细节，不把硬规则压缩成抽象口号。
- 不为所有语言规定固定测试框架、目录结构、包管理器、格式化工具或版本。
- 不自动升级任何语言、运行时、依赖、Action、镜像或锁文件。
- 不把 AIMA 的 PostgreSQL、Vue/FastAPI、当前 Blueprint 文件集合、中文 Git 提交等项目选择提升为所有项目的全球默认。
- 不把 `01_…12_` 当前 reference 数量变成永久文档数量约束。

# 必须保持不变

- 系统/开发者/用户/目标路径 `AGENTS.md` 等高优先级规则始终高于通用 Skill。
- 仓库事实、锁文件、真实命令、当前实现和本轮新鲜验证证据优先，不从聊天或缓存猜实现。
- L1/L2/L3、L2/L3 Change、Requirement Traceability、Completion Audit、两阶段 Review、Red-Green-Refactor、根因调试、最小兼容实现、并行冲突检查、文档同步和 Git 安全边界不降低。
- Web/API/PostgreSQL/Provider 专项策略的 Browser Mock / Backend/API/PostgreSQL / Contract / Real Full-stack / Real Provider Probe 详细语义完整保留；只允许当前规范路径从无编号名称迁移到 `08_testing-strategy.md`。
- `.reliable-vibe-coding/project-context.json`、`rvc-project-context/v1`、`rvc-change/v1` 和 `rvc.py` 既有缓存/Change 协议不做破坏性格式迁移。
- AIMA 项目本地规则继续由根/嵌套 `AGENTS.md`、当前 Blueprint/Roadmap/Appendix/Guide、Contract、Migration、locks、tests 和 CI 承载；通用 Skill 只负责发现并服从这些 Overlay。
- 历史 Archive 的状态、Evidence 和结论不因当前文件改名而改写；仅被 Ready Check 当作实时路径校验的 Source 随当前文件路径同步。

# 关键决策

1. 采用“核心流程 + 条件式 profiles/路由”而不是为每种语言复制一套 Skill，避免多份 TDD/Git/Review/Change 规则漂移。
2. Web/API/PostgreSQL/Provider 测试策略保留为专项 profile；通用层只抽象风险与证据职责，不弱化原测试边界。
3. 不迁移 `rvc.py` 的缓存协议；只扩展 Manifest/Workspace 发现表面，保持 `rvc-project-context/v1` 与 `rvc-change/v1` 不变。
4. 原规则只允许移动、分类或消除完全等价重复；不能因缩短主 `SKILL.md` 删除约束。`12_rule-preservation-map.md` 与 portability regression 共同作为后续重组内容守恒门禁。
5. AIMA 自身 PostgreSQL、当前文档集合、中文 Git 提交等项目约束由项目 Overlay 承载；通用 Skill 明确 Overlay 优先级，不把这些专项事实强加给其他仓库。
6. 本轮 reference 改名采用**真正的 canonical rename**：所有实时引用迁完后删除旧无编号文件，不保留第二套 `.md` 兼容副本，以免目录阅读仍然混乱。历史旧名称只可在 preservation map 中作为“原 reference”标签出现。
7. 编号只表达当前研发流程阅读顺序；未来新增 reference 时按依赖位置调整，不把 12 当固定数量。
8. Blueprint/Design/Architecture/Roadmap 等项目文档集合以目标项目当前真实文件和项目规则发现；通用 Skill 不允许出现固定 Blueprint 数量/文件名/编号上限。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Skill 必须适用于不同项目、不同研发阶段、不同编程语言 | user:2026-08-25-portable-skill | satisfied | `02_task-routing.md`、`03_language-and-toolchain-profiles.md`、`07_validation-strategy.md` 和 `rvc.py` 已形成跨项目/阶段/语言的事实发现与验证路由；第一轮 Green 已证明其结构可运行，最终仍需本轮新 HEAD 回归 |
| R2 | 重新组织现有 Skill，使大模型严格按 Skill 流程工作 | user:2026-08-25-portable-skill | satisfied | 主 `SKILL.md` 将四维路由、命中 reference 必须读取和 fresh-evidence gate 设为强制入口；`agents/openai.yaml` 有对应默认提示 |
| R3 | 不丢失任何现有内容和有价值细节，不做过度总结 | user:2026-08-25-preserve-skill-details | satisfied | `12_rule-preservation-map.md` 逐项映射原不变量/工作流/专项策略；旧 Skill 自测曾抓到 private/helper 措辞收缩；Completion Audit 又抓到 AIMA docs 规则承载不足并迁入 `docs/AGENTS.md`，说明内容守恒不是只靠口头声明 |
| R4 | 不从历史聊天猜实现，按当前 AGENTS 与 GitHub 事实工作 | AGENTS.md | satisfied | 本任务持续从当前 GitHub 读取 AGENTS、Skill、references、Change、Blueprint 和 CI；main 前进后重新比较并同步最新 `3591c1fbdbfdb50a65c6da3e773fe6e12b1246d5`，没有沿用失效基线 |
| R5 | L2 变更维护 Change、Validation Matrix、Completion Audit 和新鲜证据 | .agents/skills/reliable-vibe-coding/references/04_change-management.md | not_satisfied | Change 已因新需求回退 `in_progress`；新增要求完成 Green、Audit 和最终 Ready 证据后才能重新 satisfied |
| R6 | 已归档 CI Change 对专项测试策略的实时 Requirement Source 在改名后仍可解析 | changes/archive/2026-08/CHG-20260825-ci-long-term-risk-layers/CHANGE.md | satisfied | 归档 Change R5 Source 已迁移为 `.agents/skills/reliable-vibe-coding/references/08_testing-strategy.md`，历史 Evidence/结论保持不变 |
| R7 | 通用 Skill 不得写死 Blueprint 数量、固定文档名或编号上限；项目文档集合按当前真实项目事实发现 | user:2026-08-25-dynamic-project-docs | not_satisfied | `SKILL.md`、`docs/AGENTS.md`、根 `AGENTS.md`、Blueprint 06 和 preservation map 已改为动态原则；待删除旧副本并完成 Green/Review 后确认 |
| R8 | 按研发阶段拆分的 Skill reference 使用 `01_、02_……` 两位数字顺序，便于阅读；编号不是固定文档数量 | user:2026-08-25-numbered-skill-references | not_satisfied | 01—12 编号 canonical 文件与主要内链已建立；旧无编号副本尚待删除并执行完整 Green |

# Validation Matrix

本 Change 是开发治理/Skill 文档与项目发现工具变更。产品 Web/API/PostgreSQL 等专项层没有独立产品行为风险；仓库现有产品 CI 仍会作为无回归辅助证据，但不能替代本 Change 的治理验证。

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不改变前端产品行为、路由或请求；后续若 CI 运行仅作为无回归辅助 |
| Backend/API/PostgreSQL Integration | not_applicable | 不改变后端业务、数据库、Migration、Job/Worker；`rvc.py` 只做静态文件分类 |
| Contract / Generated Client | not_applicable | 不修改产品 Pydantic/OpenAPI/generated client/Canonical/Job Contract |
| Real Full-stack Golden Path | not_applicable | 不改变产品跨组件接线；若 CI 运行仅作为无回归辅助 |
| Real Provider Probe | not_applicable | 不修改 Provider endpoint/字段/分页/capability/pricing，不需要真实外部调用 |
| Docs / Governance / Other | required | portability unit、旧 Skill self-tests、编号目录唯一性、Markdown/link/docs check、Ready Check、Repository Quality/CI、Completion Audit、内容守恒 Review；当前只已有新 Red，Green 尚待取得 |

# Completion Audit

- [ ] upstream_re_read：完成本轮编号/动态文档迁移后，重新读取用户三轮要求、当前根/嵌套 AGENTS、主 Skill、全部编号 reference、模板、Blueprint 06、相关 Change 和测试，独立重建完成定义。
- [ ] change_coverage：确认 R1-R8 全部由当前规范/实现覆盖，没有把“编号方便阅读”错误实现成固定文档数量，也没有因改名丢失旧细节。
- [ ] reverse_audit：从当前 `references/` 目录按 01→12 阅读顺序反查上下游链接；再从旧 reference 名称、AIMA 当前导航、Archive Requirement Source 反查没有失效实时路径；从其他项目反查不受 AIMA Blueprint 数量约束。
- [ ] unresolved_cleared：R5/R7/R8 清零；所有 required 证据基于最终同步 main 后的当前 HEAD。

# 两阶段 Review

## Review A1：上游要求 → Change

第一轮 A1 已确认跨项目/阶段/语言、严格执行和内容守恒三条要求。本轮新增后必须重新执行 A1，重点检查：

- “不写死 Blueprint 数量/名称”是否进入通用 Skill 和 AIMA 项目 Overlay，而不是只改一句说明；
- “01_、02_……”是否落实为真实文件名和全部实时引用，而不是目录里同时保留两套文件；
- 编号是否只表达阅读顺序，没有创建“必须永久 12 份”的新硬编码。

当前因 R7/R8 尚未完成 Green，A1 最终结论暂不标记通过。

## Review A2：Change → 实现 / 测试 / 文档

待 Green 后重新检查：主 Skill、02/04/05/07/10/11/12 内链、模板、根/嵌套 AGENTS、Blueprint 06、归档 Source、目录唯一性和 portability tests 是否一致。

## Code Quality Review

第一轮已确认：无依赖/Runtime/产品 Contract 变化，`rvc.py` 只做静态 Manifest 分类。第二轮需要特别检查文档 rename 是否存在断链、重复 canonical 文件、历史 Source 漂移或无关内容改写。

# 任务

- [x] 调查原 Skill、references、模板、脚本、测试和 AIMA 上游规则
- [x] 建立第一轮通用性/内容守恒 Red，并完成四维路由、多语言 profile、generic Validation、preservation map
- [x] 为 `rvc.py` 多语言 Manifest 发现建立独立 Red/Green
- [x] 旧 Skill self-tests 抓到并修正规则措辞收缩
- [x] 第一轮 Completion Audit 发现 AIMA docs 项目规则承载不足并新增 `docs/AGENTS.md`
- [x] 第一轮实现曾在最终 Ready HEAD 取得 CI、PostgreSQL、Runtime、Full-stack、Change Completion Gate 全绿
- [x] 用户新增“动态 Blueprint + reference 编号”要求后，PR #222 转回 Draft
- [x] 新增本轮回归测试；第一次因 Ruff format 失败未计为有效 Red
- [x] 修正测试格式后取得有效 Red：Ruff/format/mypy 全过，Unit `628 passed / 11 failed`，11 个失败全部对应编号文件/旧路径/动态文档目标
- [x] 新建 01—12 编号 reference，并迁移主 Skill、02/04/05/07/10/11/12、模板、根/嵌套 AGENTS、Blueprint 06 和归档 CI Change 的主要实时引用
- [x] 本轮期间 main 前进到 `3591c1fb...`，比较无 Skill 冲突后通过双父 merge 同步最新 main
- [ ] 删除 12 个无编号旧 reference，确保目录只有一套 canonical 规范文件
- [ ] 运行目标 Unit、旧 Skill self-tests、Docs/Ready/CI，取得 Green
- [ ] 重新完成 R1-R8 Requirement Traceability、Completion Audit 和两阶段 Review
- [ ] 将 Change 重新置为 `ready_for_review`，在最终 HEAD 取得 Change Completion Gate 和 CI，再把 PR #222 从 Draft 转 Ready

# 验证

## 第一轮历史 Red / Green（仅作开发历史，不替代本轮最终证据）

### 结构通用化 Red

提交 `b82004c6871ca9b92801f9c89605585cec83f851`：

```text
Ruff / format / mypy → 通过
uv run pytest tests/unit -q → 628 passed / 5 failed
```

失败分别对应缺四维路由、语言 profile、generic Validation Matrix、preservation map 和通用 Change template。

### 多语言项目发现 Red

提交 `1c282d4667415d6e581325bbfc8f4c115b23f131`，CI `32795417184`：

```text
Ruff / format / mypy → 通过
uv run pytest tests/unit -q → 633 passed / 1 failed
```

唯一失败是 `CMakeLists.txt` 未被识别为 manifest；随后只扩展 Manifest 名称/后缀分类。

### 第一轮 Green

在此前候选 HEAD 上曾取得：Unit 637、Contract 75、API 34、Frontend Unit 39、Playwright 22、Ruff/mypy/Architecture/Ownership/Secret/Docs/Wheel/PostgreSQL/Runtime/Full-stack/Completion 全绿。由于用户随后新增要求且 main 又前进，这些结果只证明旧候选，不作为本轮最终“完成”证据。

## 本轮有效 Red：动态 Blueprint + 编号 reference

### 非有效尝试

提交 `6ea36cdd2564cfc525c6022aeb317d762a601413` 首次新增回归时，Repository Quality 先因 Ruff format 失败，目标断言没有运行到，因此**不计入需求 Red**。

### 有效 Red

提交：

```text
fe3af58415f09c5d3b1d1be0e6a7be122a51e519
```

CI：

```text
run 32798934825
Repository Quality job 97655864851
```

实际结果：

```text
ruff format --check → 491 files already formatted
ruff check → All checks passed
mypy backend/src → Success: no issues found in 242 source files
uv run pytest tests/unit -q → 628 passed / 11 failed / 1 warning
Secret Scan → success
Docs link check → success
```

11 个失败均命中本轮目标：编号 canonical reference 尚不存在/目录仍包含旧无编号文件、`SKILL.md`/template 仍引用旧名称、动态 Blueprint 文档规则尚未落地。没有环境错误或错误断言混入，因此这是有效 Red。

## 本轮 Green 计划

完成旧 reference 删除和全部实时引用迁移后，以同步最新 main 的当前 HEAD 执行：

```text
uv run ruff format --check backend tests scripts ...
uv run ruff check backend tests scripts ...
uv run mypy backend/src
uv run pytest tests/unit -q
python -m unittest discover .agents/skills/reliable-vibe-coding/tests -v
uv run python scripts/quality/scan_secrets.py
uv run python scripts/quality/check_docs.py
python .agents/skills/reliable-vibe-coding/scripts/ready_check.py --root . --require-active-ready（仅在重新 Ready 后）
```

并读取 PR 当前 HEAD 的 Repository Quality、Change Completion Gate 及仓库实际触发的其他长期门禁。失败则修根因，不降低断言或恢复无编号副本绕过测试。

# 文档影响

- Skill reference 当前规范将统一为 `01_…` 两位数字前缀，按研发流程表达阅读顺序；编号不是固定文档配额。
- `docs/AGENTS.md` 保留 AIMA 的两位数字文档导航规则，但 Blueprint/Design/Architecture/Roadmap 集合以目标项目当前实际文档和项目规则为准：不预设固定数量、固定文件名或固定编号上限。
- 根 `AGENTS.md` 和 Blueprint 06 已改为按当前 `docs/blueprint/` 实际集合理解核心长期架构，不再把“当前 01—08”描述成永久规则；导航表中具体 01—08 文件仍可作为 AIMA 当前真实文件路径出现，这与全球固定政策不同。
- 归档 CI Change 仅把仍需实时解析的专项测试 Requirement Source 迁到 `08_testing-strategy.md`，历史 Evidence/结论保持不变。
- AIMA 产品 HTTP/Canonical/数据库文档不受产品行为影响，不制造无关差异。

# 兼容性、依赖、Migration、部署与回滚

- Public product API / Contract：无变化。
- Database Schema / Migration：无变化。
- 产品数据：无变化。
- 依赖 / Lock：无变化。
- Runtime / Deployment：无变化。
- Skill cache schema：`rvc-project-context/v1` 不变。
- Change schema：`rvc-change/v1` 不变。
- 文档路径兼容：Skill reference 当前 canonical 路径会从无编号名称迁为两位数字名称；仓库内当前实时引用在同一 Change 迁移。历史自然语言中提及旧文件名可以保留，但不能作为当前机器 Source。
- 回滚：如编号迁移出现问题，可 revert 本 PR 的 Skill/docs/test 路径迁移；不涉及产品数据回滚或 Migration downgrade。

# 交付

- Branch：`refactor/reliable-vibe-coding-portable-routing`
- PR：`#222`，当前 Draft
- Main synchronized through：`3591c1fbdbfdb50a65c6da3e773fe6e12b1246d5`
- Latest main sync merge commit：`5eafde1c09c10a0f54ae007c3d93ccc27d616223`
- Current Change status：`in_progress`
- Final Green / Ready HEAD：尚未产生
- Merge：未执行
- Release / Deploy：不适用
