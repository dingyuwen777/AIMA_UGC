---
schema: rvc-change/v1
id: CHG-20260825-portable-reliable-vibe-coding
title: Reliable Vibe Coding 跨项目跨阶段跨语言通用化重组
level: L2
status: ready_for_review
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
  - docs/blueprint/README.md
  - docs/blueprint/06_开发约束与分阶段实施.md
  - changes/archive/2026-08/CHG-20260825-ci-long-term-risk-layers/CHANGE.md
  - tests/unit/test_reliable_vibe_coding_portability.py
contracts: []
data_changes: []
---

# 背景与当前事实

当前仓库只有一套 `.agents/skills/reliable-vibe-coding/` Skill。原 Skill 已经包含项目发现、L1-L3 分级、Change 管理、Requirement Traceability、Completion Audit、Red-Green-Refactor、根因调试、分层验证、多人协作、Review、Git 和交付证据等完整机制，但原主 `SKILL.md` 同时承担入口、路由、流程正文、AIMA/Web 技术形态示例和交付门禁，容易让可移植规则与当前项目专项规则混在一起。

第一轮通用化已经完成：

- 项目形态 × 研发阶段 × 编程语言/工具链 × L1-L3 风险四维任务路由；
- 多语言工具链 profile；
- 技术栈无关 Validation Matrix；
- 原规则内容守恒映射；
- `rvc.py` 多语言 Manifest/Workspace 发现；
- AIMA 项目 Overlay 与通用 Skill 的边界分离。

第一轮曾在 PR #222 的候选 HEAD `bfa382b13ae711e6ca1200e4f4ed9ccd4154aa99` 上取得 CI、Runtime、Full-stack、Change Completion Gate 全部成功。但用户随后明确补充两项要求，因此不能继续把旧候选当作最终完成状态：

1. 通用 Skill 不能把 `Blueprint 01—08`、固定文档数量、固定文件名或固定编号上限写死；不同项目必须以自己的实际文档集合和本地规则为准。
2. `references/` 中按研发阶段拆分的规范文档应使用 `01_、02_……` 两位数字前缀，并按研发流程阅读顺序排列，方便人工阅读；编号只是导航，不得反向变成“永远只能有 N 份 reference”的新硬编码。

因此本 Change 曾从 `ready_for_review` 重新回到 `in_progress`，PR #222 也重新转为 Draft，并重新执行 Red → Green → Completion Audit。

现有 Web/API/PostgreSQL/Provider 专项测试策略的**规则内容**仍完整保留；仅当前规范路径从原 `testing-strategy.md` 迁移为编号后的 `08_testing-strategy.md`。所有仍被机器作为实时路径解析的引用已同步迁移；历史 Change 的 Evidence/结论没有因当前文件改名而改写。

本次只重组 Skill、治理文档和只读项目发现能力，不改变 AIMA 产品 API、Schema、Migration、运行时、业务行为或依赖锁。

# Git / main 同步事实

开发期间 `main` 多次前进，每次都重新比较实际差异后再同步，没有从历史聊天或旧 SHA 猜测：

1. 第一轮同步到 `9b6457d3549dea57f85d52bf664227b47791b9b4`；
2. 本轮编号迁移期间，Actions 历史清理 PR #223 使 `main` 前进到 `3591c1fbdbfdb50a65c6da3e773fe6e12b1246d5`，比较确认未触碰 Skill 后通过双父 merge `5eafde1c09c10a0f54ae007c3d93ccc27d616223` 同步；
3. PR #224 进一步完成 Actions 清理收尾，`main` 前进到 `73027fe300e86d29b5864a0b90d1b7ec82669961`，再次确认无 Skill 冲突后通过双父 merge `230be2f9202acf94c4e6d90fa26b5eaca1e1c072` 同步；
4. Actions 清理 Change 最终归档后，`main` 前进到 `ae5635bc6a1f0112fc1c7446155cf42e0b8a71a2`；该变化只把另一个 Change 从 `active` 移到 `archive`，通过双父 merge `e1e86992c8da3150f0245dc95ad33a96c3bd93bd` 同步到当前分支。

当前 Ready 候选建立在上述最新主分支事实之上。旧 HEAD 的 Green 只作为开发历史；最终完成结论必须由本次 `ready_for_review` 提交之后的新鲜门禁证明。

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

这个列表描述**当前 reference 集合的阅读顺序**，不是固定配额。以后新增、拆分或合并 reference 时按真实依赖关系和阅读顺序调整，不能因为现在是 12 份就把 12 写成永久上限。

# 成功标准

- [x] `SKILL.md` 形成清晰的强制入口与四维任务路由，明确先识别项目事实，再选择阶段、工具链、风险规则和验证，而不是默认 Web/Python/PostgreSQL。
- [x] 项目/研发阶段路由覆盖首次接入、需求/设计、实现、Bug/调试、重构、Review、发布/运维、维护/迁移、安全/不可逆操作等阶段。
- [x] 编程语言与工具链适配覆盖 Python、JavaScript/TypeScript、Go、Rust、Java/Kotlin、.NET、C/C++、Swift、Dart/Flutter、PHP、Ruby、Elixir、多语言/Monorepo、Container/IaC，并提供未列语言的统一发现算法；不硬编码版本或擅自更换包管理器。
- [x] 通用 Validation Matrix 抽象为行为、接口、真实依赖集成、用户/调用者工作流、跨组件 Golden Path、外部依赖 Probe、Build/Package/Runtime、Docs/Governance 等风险维度；原 Browser/PostgreSQL/Provider 细节继续作为条件式专项 profile。
- [x] `CHANGE.template.md` 不要求所有项目机械使用 Browser/PostgreSQL/Provider 行名，同时保留专项层映射和适用条件。
- [x] `12_rule-preservation-map.md` 逐项登记原主 Skill 13 条不变量、统一工作流 1—11、旧 reference、TDD、根因调试、Git/依赖/安全、注释、可观测性、文档同步和专项测试职责。
- [x] 原主 Skill 中属于 AIMA 项目的 docs 编号/重命名/历史归档知识由 `docs/AGENTS.md` 正式承载，而不是只留在审计清单。
- [x] 通用 Skill 不把任一项目的 Blueprint 数量、固定文件名或固定编号上限写成全球规则；AIMA 通过 `docs/AGENTS.md`、`docs/blueprint/README.md` 和当前实际文档集合动态确定现有 Blueprint。
- [x] `docs/blueprint/README.md` 保留当前 01—08 的实际导航和职责，但不再宣称“固定为 01—08”，也不禁止未来真正需要的 `09_` 或更大编号。
- [x] `references/` 当前规范文件全部使用两位数字前缀，目录只保留一套编号 canonical 文件，不保留无编号平行规范。
- [x] 所有当前 Skill 内链、AIMA 当前文档导航和仍被 Ready Check 解析的 Requirement Source 已迁移到编号路径；历史 Evidence/结论没有因文件改名而改写。
- [x] 自动化回归验证 reference 顺序、编号路径、动态 Blueprint 边界、主要语言覆盖、通用验证层、关键旧规则可达以及 AIMA 专项策略仍完整存在。
- [x] 本轮新增要求取得正确 Red 和同步最新 main 后的实现 Green；Completion Audit 与两阶段 Review 已重新完成，当前提交进入最终 Ready 机器门禁。

# 范围

- 重组 `.agents/skills/reliable-vibe-coding/SKILL.md` 的入口、任务路由和统一流程组织。
- 将 `.agents/skills/reliable-vibe-coding/references/*.md` 当前规范文件迁移为两位数字前缀的研发流程阅读顺序；完成所有实时引用迁移后删除无编号旧副本。
- 维护多语言/工具链 profile、generic Validation Matrix 和 rule preservation map。
- 调整 Change/Completion/Workflow/Review/template 的技术栈中立表达与编号路径。
- 保留 Web/API/PostgreSQL/Provider 专项策略全部有效语义，将当前规范路径迁移为 `08_testing-strategy.md`。
- 增加仓库级 Unit 回归测试验证 Skill 结构、编号顺序、动态文档边界和关键规则可达性。
- 扩充 `rvc.py` 对常见多语言 Manifest/Workspace 的只读发现能力，但不改变缓存/Change schema、Change 解析、冲突检测或 CLI 协议。
- 更新 `agents/openai.yaml`，要求 Agent 先完成四维路由并读取所有命中的 reference 后再执行任务。
- 更新 AIMA 根/嵌套 `AGENTS.md`、Blueprint README 和 Blueprint 06 的当前 Skill 路径与动态文档治理说明。
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
- Web/API/PostgreSQL/Provider 专项策略的 Browser Mock / Backend/API/PostgreSQL / Contract / Real Full-stack / Real Provider Probe 详细语义完整保留；当前规范路径迁移为 `08_testing-strategy.md`。
- `.reliable-vibe-coding/project-context.json`、`rvc-project-context/v1`、`rvc-change/v1` 和 `rvc.py` 既有缓存/Change 协议不做破坏性格式迁移。
- AIMA 项目本地规则继续由根/嵌套 `AGENTS.md`、当前 Blueprint/Roadmap/Appendix/Guide、Contract、Migration、locks、tests 和 CI 承载；通用 Skill 只负责发现并服从这些 Overlay。
- 历史 Archive 的状态、Evidence 和结论不因当前文件改名而改写；仅被 Ready Check 当作实时路径校验的 Source 随当前文件路径同步。

# 关键决策

1. 采用“核心流程 + 条件式 profiles/路由”而不是为每种语言复制一套 Skill，避免多份 TDD/Git/Review/Change 规则漂移。
2. Web/API/PostgreSQL/Provider 测试策略保留为专项 profile；通用层只抽象风险与证据职责，不弱化原测试边界。
3. 不迁移 `rvc.py` 的缓存协议；只扩展 Manifest/Workspace 发现表面，保持 `rvc-project-context/v1` 与 `rvc-change/v1` 不变。
4. 原规则只允许移动、分类或消除完全等价重复；不能因缩短主 `SKILL.md` 删除约束。`12_rule-preservation-map.md` 与 portability regression 共同作为后续重组内容守恒门禁。
5. AIMA 自身 PostgreSQL、当前文档集合、中文 Git 提交等项目约束由项目 Overlay 承载；通用 Skill 明确 Overlay 优先级，不把这些专项事实强加给其他仓库。
6. reference 改名采用真正的 canonical rename：所有实时引用迁完后删除旧无编号文件，不保留第二套 `.md` 兼容副本。历史旧名称只在 preservation map 中作为“原 reference”标签出现。
7. 编号只表达当前研发流程阅读顺序；未来新增 reference 时按依赖位置调整，不把 12 当固定数量。
8. Blueprint/Design/Architecture/Roadmap 等项目文档集合以目标项目当前真实文件和项目规则发现；通用 Skill 不允许出现固定 Blueprint 数量/文件名/编号上限。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Skill 必须适用于不同项目、不同研发阶段、不同编程语言 | user:2026-08-25-portable-skill | satisfied | `02_task-routing.md`、`03_language-and-toolchain-profiles.md`、`07_validation-strategy.md` 和 `rvc.py` 已形成跨项目/阶段/语言的事实发现与验证路由；portability Unit 在本轮实现 HEAD 重新通过 |
| R2 | 重新组织现有 Skill，使大模型严格按 Skill 流程工作 | user:2026-08-25-portable-skill | satisfied | 主 `SKILL.md` 将四维路由、命中 reference 必须读取和 fresh-evidence gate 设为强制入口；`agents/openai.yaml` 有对应默认提示；RVC completion-gate self-tests 在编号迁移后成功 |
| R3 | 不丢失任何现有内容和有价值细节，不做过度总结 | user:2026-08-25-preserve-skill-details | satisfied | `12_rule-preservation-map.md` 逐项映射原不变量/工作流/专项策略；旧 Skill 自测曾抓到 private/helper 措辞收缩；Completion Audit 又抓到 AIMA docs 规则承载不足，均在 Ready 前修正；`08_testing-strategy.md` 保持原专项语义 |
| R4 | 不从历史聊天猜实现，按当前 AGENTS 与 GitHub 事实工作 | AGENTS.md | satisfied | 全程从当前 GitHub 读取 AGENTS、Skill、references、Change、Blueprint 和 CI；main 每次前进都重新 compare 后用正常双父 merge 同步，最终同步到 `ae5635bc6a1f0112fc1c7446155cf42e0b8a71a2` |
| R5 | L2 变更维护 Change、Validation Matrix、Completion Audit 和新鲜证据 | .agents/skills/reliable-vibe-coding/references/04_change-management.md | satisfied | Change 因新需求从 Ready 回退 in_progress，重新取得有效 Red、Green、Traceability、Audit 和两阶段 Review；当前再次置 `ready_for_review`，由本提交的新鲜 Ready Check/CI 作最终机器验证 |
| R6 | 已归档 CI Change 对专项测试策略的实时 Requirement Source 在改名后仍可解析 | changes/archive/2026-08/CHG-20260825-ci-long-term-risk-layers/CHANGE.md | satisfied | 归档 Change R5 Source 已迁移为 `.agents/skills/reliable-vibe-coding/references/08_testing-strategy.md`；历史 Evidence/结论未改写，Docs/Ready 相关检查在实现 Green 中成功 |
| R7 | 通用 Skill 不得写死 Blueprint 数量、固定文档名或编号上限；项目文档集合按当前真实项目事实发现 | user:2026-08-25-dynamic-project-docs | satisfied | `SKILL.md` 明确“不预设项目 Blueprint 数量/文件名/编号上限”；`docs/AGENTS.md` 明确动态集合；根 `AGENTS.md`、Blueprint 06 与 `docs/blueprint/README.md` 均改为以当前实际文档集合为准；portability test 对“固定 01—08”回归建立负断言 |
| R8 | 按研发阶段拆分的 Skill reference 使用 `01_、02_……` 两位数字顺序，便于阅读；编号不是固定文档数量 | user:2026-08-25-numbered-skill-references | satisfied | `references/` 当前只保留 `01_...12_` 一套 canonical `.md`；旧无编号 12 文件已原子删除；主 Skill、内部内链、模板、AIMA 导航、自测和实时 Requirement Source 已迁移；portability test 精确断言目录顺序与唯一性 |

# Validation Matrix

本 Change 是开发治理/Skill 文档与项目发现工具变更。产品 Web/API/PostgreSQL 等专项层没有独立产品行为风险；仓库现有产品 CI 作为无回归辅助证据，但不替代本 Change 的治理验证。

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不改变前端产品行为、路由或请求；CI 中前端/Playwright 成功仅作为无回归辅助 |
| Backend/API/PostgreSQL Integration | not_applicable | 不改变后端业务、数据库、Migration、Job/Worker；CI PostgreSQL Integration 成功仅作为无回归辅助 |
| Contract / Generated Client | not_applicable | 不修改产品 Pydantic/OpenAPI/generated client/Canonical/Job Contract；生成漂移检查成功仅作为无回归辅助 |
| Real Full-stack Golden Path | not_applicable | 不改变产品跨组件接线；不以 Full-stack 结果作为本 Change 主证据 |
| Real Provider Probe | not_applicable | 不修改 Provider endpoint/字段/分页/capability/pricing，不需要真实外部调用 |
| Docs / Governance / Other | required | 有效 Red `fe3af584...`：Ruff/format/mypy 通过、Unit `628 passed / 11 failed` 且 11 个失败全部命中本轮目标；实现 Green HEAD `f9138a89...` 的 CI `32800997716`：Ruff/format/mypy success，Unit `641 passed`、Contract `75 passed`、API `34 passed`、Architecture/Ownership/Secret/Docs/Wheel success、Frontend Unit `39 passed`、Playwright `22 passed`，PostgreSQL Integration 与 CI Gate success；编号迁移后的 RVC completion-gate self-tests success；当前 Ready 提交继续执行最终机器门禁 |

# Completion Audit

- [x] upstream_re_read：已在最新 main 同步后重新读取用户三轮要求、根 `AGENTS.md`、`docs/AGENTS.md`、主 `SKILL.md`、编号 reference 集合、模板、Blueprint README/06、当前 Change、归档 CI Change 和 portability/self-tests，独立重建“跨项目/阶段/语言 + 不丢规则 + 动态项目文档 + 编号阅读导航”的完成定义。
- [x] change_coverage：R1-R8 全部进入当前 Change；没有把“编号方便阅读”错误实现成固定 reference 数量，也没有把“当前 AIMA 01—08”继续写成永久 Blueprint 制度。
- [x] reverse_audit：从 `references/` 目录按 01→12 反查，只存在一套 canonical `.md`；从主 Skill、02/04/05/07/10/11/12、template、根/嵌套 AGENTS、Blueprint 06、归档 Requirement Source 反查均使用编号实时路径；从 Blueprint README 反查当前 01—08 仍可导航但未来数量/文件名/编号上限不锁死；从其他项目角度反查不受 AIMA 当前文档集合强制。
- [x] unresolved_cleared：R1-R8 均为 `satisfied`；Validation Matrix 唯一 required 的 Docs/Governance 有正确 Red、实现 Green 和即将运行的最终 Ready 机器门禁，所有不适用产品层都有当前 diff/边界依据。

# 两阶段 Review

## Review A1：上游要求 → Change

通过。独立从用户三轮要求重建完成定义，确认覆盖：

- 不同项目、不同研发阶段、不同编程语言通用；
- 大模型先路由并严格读取命中 reference，再执行 Change/TDD/验证/Review/Git 门禁；
- 原规则和有价值细节不因“精简/通用化”丢失；
- 通用 Skill 不固定任何项目的 Blueprint 数量、文件名、编号上限；
- reference 以两位数字按研发流程提供人工阅读顺序；
- 当前 01—12 只是现状导航，不变成永久文档配额。

没有把当前 Change checklist、旧 Ready Green 或 CI 成功冒充上游需求全集。

## Review A2：Change → 实现 / 测试 / 文档

通过：

- `SKILL.md`：四维路由、编号目录说明、动态文档边界和全部编号链接；
- `01_...12_`：当前 canonical reference 集合，旧无编号副本已删除；
- `02/04/05/07/10/11/12`：内部链接全部迁到编号路径；未需要内容变化的 reference 保持原规则语义；
- `CHANGE.template.md`：通用 Validation 与专项 testing 路径迁到编号文件；
- `AGENTS.md` / `docs/AGENTS.md`：AIMA 当前导航与动态文档集合边界一致；
- `docs/blueprint/README.md`：保留当前 01—08 实际列表，删除“永久固定 01—08 / 禁止未来 09+”政策；
- Blueprint 06：专项测试链接和文档分层说明同步；
- 归档 CI Change：只迁移机器仍需解析的 Requirement Source，历史 Evidence/结论不改写；
- `tests/unit/test_reliable_vibe_coding_portability.py`：验证编号目录唯一性、主要生态、专项策略保留、旧硬门禁可达、动态 Blueprint 边界；
- 旧 Skill `test_development_guidance.py`：只迁移到编号 reference 路径，原断言没有降低。

## Code Quality Review

通过，未发现未解决的严重/重要问题：

- 无产品代码、Schema、Migration、依赖、Runtime 或锁文件变化；
- `rvc.py` 多语言改动仍仅为静态 Manifest 分类；
- reference rename 没有保留第二套兼容文档，避免双事实源；
- 编号规则明确区分“当前顺序”与“永久数量”，没有从一个硬编码修成另一个硬编码；
- AIMA 当前 01—08 文件名继续可用于项目导航，但不再作为全球/永久限制；
- Markdown/Docs 检查已在实现 Green 通过；
- Secret 扫描通过；
- main 前进均先 compare 再正常 merge，无 force/rebase/历史重写。

# 任务

- [x] 调查原 Skill、references、模板、脚本、测试和 AIMA 上游规则
- [x] 建立第一轮通用性/内容守恒 Red，并完成四维路由、多语言 profile、generic Validation、preservation map
- [x] 为 `rvc.py` 多语言 Manifest 发现建立独立 Red/Green
- [x] 旧 Skill self-tests 抓到并修正规则措辞收缩
- [x] 第一轮 Completion Audit 发现 AIMA docs 项目规则承载不足并新增 `docs/AGENTS.md`
- [x] 第一轮实现曾在旧 Ready HEAD 取得完整门禁 Green；用户新增要求后主动撤回 Ready
- [x] 新增“动态 Blueprint + 编号 reference”回归；第一次因 Ruff format 失败未计为有效 Red
- [x] 修正测试格式后取得有效 Red：Ruff/format/mypy 全过，Unit `628 passed / 11 failed`，11 个失败全部对应本轮目标
- [x] 新建 01—12 编号 reference，迁移主 Skill、内部链接、模板、AIMA 导航、自测和实时 Requirement Source
- [x] 删除 12 个无编号旧 reference，确保目录只有一套 canonical 规范文件
- [x] 修改 `docs/blueprint/README.md`，保留当前 01—08 列表但取消固定数量/编号上限
- [x] 多次同步任务期间最新 main，最终基线为 `ae5635bc6a1f0112fc1c7446155cf42e0b8a71a2`
- [x] 实现 Green：CI `32800997716`，Unit 641 / Contract 75 / API 34，Docs/Secret/Architecture/Ownership/Wheel/PostgreSQL/Frontend/Playwright/CI Gate 全部成功
- [x] 完成 R1-R8 Requirement Traceability、Completion Audit 和两阶段 Review
- [x] 将本 Change 重新置为 `ready_for_review`；当前提交进入最终 Change Completion Gate/CI
- [ ] 最终 Ready HEAD 全部门禁成功后，把 PR #222 从 Draft 转 Ready；不自动合并

# 验证

## 第一轮历史 Red / Green

这些证据只说明第一轮通用化过程，不替代本轮最终状态。

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

### 第一轮旧 Ready Green

旧候选 `bfa382b13ae711e6ca1200e4f4ed9ccd4154aa99` 曾取得 CI、Runtime、Full-stack、Change Completion Gate 全绿。用户新增要求后该结论主动失效，PR 转回 Draft，不用旧结果冒充当前完成。

## 本轮有效 Red：动态 Blueprint + 编号 reference

### 非有效尝试

提交 `6ea36cdd2564cfc525c6022aeb317d762a601413` 首次新增回归时，Repository Quality 先因 Ruff format 失败，目标断言未运行，因此不计入需求 Red。

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

11 个失败全部命中本轮目标：编号 canonical reference 尚不存在/目录仍包含旧无编号文件、`SKILL.md`/template 仍引用旧名称、动态 Blueprint 文档规则尚未落地。没有环境错误或错误断言混入。

## 本轮实现 Green

实现 HEAD：

```text
f9138a89b3c0832ae2af0a041de0dbdbe499b6f3
```

CI：

```text
run 32800997716
Repository Quality job 97661668077
```

完整日志：

```text
ruff format --check → 491 files already formatted
ruff check → All checks passed
mypy backend/src → Success: no issues found in 242 source files
Unit → 641 passed / 1 warning
Contract → 75 passed
API → 34 passed / 1 warning
Architecture / Table Ownership → success
Secret Scan / Docs links → success
Wheel build + clean venv install/import → success
Frontend Unit → 39 passed
Frontend build → success
Playwright Browser Mock Acceptance → 22 passed
```

同一 CI 的 PostgreSQL Integration 与 `CI Gate` 也为 success。

编号迁移后的 RVC completion-gate/self-tests 在 Change Completion Gate 中成功；当时 `Enforce changed PR Change readiness` 失败是因为 Change 有意保持 `in_progress`，不是路径/测试断裂。

随后 `main` 仅发生另一个 Change 的归档移动并同步到当前分支；该同步不触碰 Skill/测试/Blueprint。当前 `ready_for_review` 提交必须再次执行新鲜 Ready Check 和 CI，只有最终 HEAD 成功后才允许将 PR 转 Ready。

# 文档影响

- Skill reference 当前规范统一为 `01_…` 两位数字前缀，按研发流程表达阅读顺序；编号不是固定文档配额。
- `docs/AGENTS.md` 保留 AIMA 的两位数字文档导航规则，但 Blueprint/Design/Architecture/Roadmap 集合以目标项目当前实际文档和项目规则为准：不预设固定数量、固定文件名或固定编号上限。
- 根 `AGENTS.md`、Blueprint 06 和 Blueprint README 都已改为按当前 `docs/blueprint/` 实际集合理解核心长期架构。
- 当前 01—08 文件仍作为 AIMA 当前真实导航保留；这是“当前仓库有什么”，不是“所有项目/未来永远只能有什么”。
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
- Skill 文档路径：当前 canonical reference 从无编号名称迁移为两位数字名称；仓库内所有实时引用在同一 Change 迁移。历史自然语言可保留旧名称，但不能作为当前机器 Source。
- 回滚：如编号迁移出现问题，可 revert 本 PR 的 Skill/docs/test 路径迁移；不涉及产品数据回滚或 Migration downgrade。

# 交付

- Branch：`refactor/reliable-vibe-coding-portable-routing`
- PR：`#222`，当前仍保持 Draft，直到本 Ready 提交全部机器门禁成功
- Latest main synchronized：`ae5635bc6a1f0112fc1c7446155cf42e0b8a71a2`
- Latest main sync merge：`e1e86992c8da3150f0245dc95ad33a96c3bd93bd`
- Implementation Green HEAD：`f9138a89b3c0832ae2af0a041de0dbdbe499b6f3`
- Candidate Ready commit：由本次 Change 更新产生，等待同一提交的新鲜 Change Completion Gate/CI
- Merge：未执行
- Release / Deploy：不适用
