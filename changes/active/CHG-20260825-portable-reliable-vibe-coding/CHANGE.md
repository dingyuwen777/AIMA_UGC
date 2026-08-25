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
  - changes/archive/2026-08/CHG-20260824-ci-validation-layers/CHANGE.md
  - changes/archive/2026-08/CHG-20260825-ci-long-term-risk-layers/CHANGE.md
  - tests/unit/test_reliable_vibe_coding_portability.py
contracts: []
data_changes: []
---

# 背景与当前事实

当前仓库只有一套 `.agents/skills/reliable-vibe-coding/` Skill。原 Skill 已经包含项目发现、L1-L3 分级、Change 管理、Requirement Traceability、Completion Audit、Red-Green-Refactor、根因调试、分层验证、多人协作、Review、Git、安全、文档同步和交付证据等机制，但原主 `SKILL.md` 同时承担入口、路由、流程正文、AIMA/Web 技术形态示例和交付门禁，容易让“跨项目通用规则”和“AIMA 当前项目选择”混在一起。

本 Change 的目标从始至终不是把 Skill 写短，而是把规则重新组织成更清晰、可路由、可执行的规范体系。用户在开发过程中连续补充了三组要求，每一次新增要求都使此前的 Ready/Green 结论失效并重新走门禁：

1. **跨项目、跨研发阶段、跨编程语言通用化。** Agent 必须先按项目形态、研发阶段/任务类型、语言/工具链、L1-L3 风险四个维度恢复事实并路由，再读取命中的规则。
2. **文档结构不能写死。** 通用 Skill 不能把某个项目的 `Blueprint 01—08`、固定文件数量、固定文件名或固定编号上限当成全球规则；`references/` 则应使用 `01_、02_……` 两位数字表达研发流程阅读顺序，方便人工阅读，但编号不能反向成为固定配额。
3. **内容守恒优先，禁止过度总结。** 用户明确要求“不丢失任何细节和有价值内容，不要删除内容，只做合理组织，并确保大模型严格按 Skill 流程工作”。因此“通用化/精简”不能把多条带触发条件、例外、失败处理、停止条件、验证责任、安全/兼容边界的规则压成一句抽象原则；只有逐项证明完全等价时才允许消除重复，无法证明等价时保留原细节。

第一轮通用化曾在旧候选 HEAD `bfa382b13ae711e6ca1200e4f4ed9ccd4154aa99` 取得完整 CI/Runtime/Full-stack/Completion Green；用户新增动态文档/编号要求后该结论主动失效。第二轮编号/动态 Blueprint 候选 `6bc3093164a325e4ef95ef33abf9cff7e94f576c` 又取得完整 Green；用户再次提出“不要过度总结/不要丢细节”后该结论再次主动失效。本 Change 没有用旧绿灯冒充新完成定义。

现有 Web/API/PostgreSQL/Provider 专项测试策略的规则内容完整保留；当前规范路径从原 `testing-strategy.md` 迁移为编号后的 `08_testing-strategy.md`。对仍被 Ready Check 当作实时仓库路径解析的历史 Requirement Source，只迁移 Source 路径，不改写历史 Change 的 Evidence、状态、Review 或结论。

本 Change 只修改 Skill、Agent 默认提示、项目治理文档、回归测试和 `rvc.py` 的只读项目发现能力；不改变 AIMA 产品 API、Canonical/HTTP Contract、数据库 Schema/Migration、业务数据、前端产品行为、运行时部署语义或依赖锁。

# Git / main 同步事实

开发期间 `main` 多次前进，每次都重新比较真实差异后再决定是否同步，没有从旧聊天或旧 SHA 猜当前状态：

1. 第一轮同步到 `9b6457d3549dea57f85d52bf664227b47791b9b4`；
2. PR #223 的 Actions 历史清理使 `main` 前进到 `3591c1fbdbf50a65c6da3e773fe6e12b1246d5`，确认未触碰 Skill 后通过双父 merge `5eafde1c09c10a0f54ae007c3d93ccc27d616223` 正常同步；
3. PR #224 完成 Actions 清理收尾后 `main` 前进到 `73027fe300e86d29b5864a0b90d1b7ec82669961`，再次确认无 Skill 冲突后通过双父 merge `230be2f9202acf94c4e6d90fa26b5eaca1e1c072` 同步；
4. Actions 清理 Change 归档后 `main` 前进到 `ae5635bc6a1f0112fc1c7446155cf42e0b8a71a2`，差异仅为另一个 Change 从 active 移到 archive，通过双父 merge `e1e86992c8da3150f0245dc95ad33a96c3bd93bd` 同步；
5. 内容守恒人工 Review 收尾前重新比较 `main...refactor/reliable-vibe-coding-portable-routing`，结果 `behind_by: 0`，当前基线仍为 `ae5635bc6a1f0112fc1c7446155cf42e0b8a71a2`。

如果本 Ready 候选之后 `main` 再次前进，合并前仍需按真实差异重新判断，不允许把本段结论当成永久事实。

# 目标

把 Reliable Vibe Coding 重组为一个可以复制到不同项目使用的通用研发 Skill，并让 Agent 在执行前先按四个互相独立的维度路由：

```text
项目形态
× 研发阶段 / 任务类型
× 编程语言 / 工具链
× 风险等级 L1-L3
→ 本次必须读取的 references
→ 本次 Validation Matrix
→ 本次 Change / Review / Git / Delivery 门禁
```

同时把当前 Skill reference 按真实研发流程形成清晰阅读顺序：

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

这个顺序描述当前 reference 集合，不是固定配额。未来新增、拆分或合并 reference 时按真实依赖关系调整；每个任务仍只读取命中的最少充分规则，不要求机械通读所有编号文件。

重组的首要约束是：**内容守恒优先于篇幅精简。** 文件数量、篇幅、层级、术语一致性都不能成为删除触发条件、例外、失败行为、停止条件、验证责任、安全边界、兼容要求或项目本地规则的理由。

# 成功标准

- [x] `SKILL.md` 建立强制四维任务路由，要求先恢复真实项目事实，再选择阶段、工具链、风险规则和验证，不默认 Web/Python/PostgreSQL。
- [x] 研发阶段覆盖 Repository Onboarding、Requirement/Design、Feature、Bug/Incident、Refactor/Performance、Review/Audit、Integration/PR/Release、Maintenance/Migration、Security/Irreversible Operation 等真实阶段。
- [x] 语言/工具链 profile 覆盖 Python、JavaScript/TypeScript、Go、Rust、Java/Kotlin、.NET、C/C++、Swift、Dart/Flutter、PHP、Ruby、Elixir、Monorepo、Container/IaC，并提供未列语言统一发现算法；不硬编码版本、不擅自切换包管理器。
- [x] 通用 Validation Matrix 使用行为、接口、真实依赖集成、用户/调用者工作流、跨组件 Golden Path、外部依赖 Probe、Build/Package/Runtime、Docs/Governance 等技术栈无关维度；Web/API/PostgreSQL/Provider 仍条件式进入完整专项 profile。
- [x] `CHANGE.template.md` 使用通用 Validation Matrix，同时保留 Browser Mock、Backend/API/PostgreSQL、Contract/Generated Client、Real Full-stack、Real Provider Probe 的明确映射与“不互相冒充”边界。
- [x] `12_rule-preservation-map.md` 逐项登记原主 Skill 的 13 条不变量、统一工作流 1—11、原 reference、TDD、根因调试、Git/依赖/安全、注释、可观测性、文档同步、测试分层和项目 Overlay 迁移。
- [x] AIMA 项目本地 docs 编号、README、实时引用迁移和 archive 历史不可改写规则由 `docs/AGENTS.md` 正式承载，而不是只留在 preservation map。
- [x] 通用 Skill 不把任一项目的 Blueprint 数量、具体文件名或编号上限写成全球规则；AIMA 由 `docs/AGENTS.md`、`docs/blueprint/README.md` 和当前实际文件集合确定现状。
- [x] `docs/blueprint/README.md` 继续保留当前 AIMA 01—08 的实际导航与职责，但取消“永久固定 01—08”和“禁止未来 09+”的制度性表述。
- [x] `references/` 当前规范文件全部使用 `01_...12_` 两位数字前缀，目录只保留一套 canonical `.md`，不保留无编号平行规范。
- [x] Skill 内链、模板、AIMA 当前导航、Skill self-tests 和 Ready Check 实时 Requirement Source 均迁移到编号路径；历史 Evidence/结论没有因改名被重写。
- [x] `SKILL.md`、`12_rule-preservation-map.md` 和 `agents/openai.yaml` 明确“内容守恒优先于篇幅精简”，禁止用抽象口号替代可执行细节；无法证明完全等价时保留原细节。
- [x] 人工内容守恒 Review 不只检查关键词：实际发现“日志 fallback 从规范默认降成可参考”和“AIMA 中文注释规则缺少项目承载”两个语义问题，分别建立正确 Red 后修复；证明审计能发现自动检查之外的语义退化。
- [x] AIMA 原有中文提交与中文注释项目行为没有因通用化消失：提交规则继续由根 `AGENTS.md` 承载；中文注释 + Python PEP 257 已迁回根 `AGENTS.md`；通用 Skill 不把中文强加给其他项目。
- [x] 自动化回归覆盖四维路由、编号 reference 唯一顺序、动态 Blueprint、主要语言、generic validation、专项 testing、旧硬门禁、内容守恒元规则、日志默认严重性和 AIMA 项目 Overlay。
- [x] 本轮各新增要求均有正确 Red、修复后 Green、重新执行的 Completion Audit、A1/A2/Code Quality Review 和实现级新鲜 CI 证据；本文件产生的最终 Ready 候选 HEAD 还必须由同一 HEAD 的 Change Completion Gate/CI/Runtime/Full-stack 机器门禁确认，失败则不得转 PR Ready。

# 范围

- 重组 `.agents/skills/reliable-vibe-coding/SKILL.md` 的入口、路由和统一工作流组织。
- 将 `.agents/skills/reliable-vibe-coding/references/*.md` 迁移为两位数字前缀的研发流程阅读顺序，完成所有实时引用迁移后删除旧无编号副本。
- 新增/维护 `02_task-routing.md`、`03_language-and-toolchain-profiles.md`、`07_validation-strategy.md`、`12_rule-preservation-map.md`。
- 调整 `04_change-management.md`、`05_development-workflows.md`、`10_completion-gate.md`、`11_verification-review.md` 和 `CHANGE.template.md` 的通用表达，但不降低原职责。
- 保留 Web/API/PostgreSQL/Provider 专项策略全部有效语义，将 canonical 路径迁为 `08_testing-strategy.md`。
- 扩展 `rvc.py` 常见多语言 Manifest/Workspace 的只读发现，不改变缓存/Change schema、parser、conflict detection 或 CLI 协议。
- 更新 `agents/openai.yaml`，要求默认 Agent 四维路由、读取所有命中 reference、保留所有已有有价值细节并完成 fresh-evidence gate。
- 更新 AIMA 根/嵌套 `AGENTS.md`、Blueprint README、Blueprint 06 的当前 Skill 路径、动态文档治理和项目 Overlay。
- 对旧 `testing-strategy.md` 的实时历史 Requirement Source 做路径迁移，不重写历史证据。
- 增加仓库级回归测试验证上述结构、语义和项目 Overlay。

# 非目标

- 不修改 AIMA 产品代码、HTTP/Canonical Contract、数据库 Schema/Migration、产品数据、前端业务功能或运行时部署语义。
- 不修改长期 CI 风险层架构，不新增平行 Workflow。
- 不删除原 reference 中仍有效的规则细节，不把硬规则压成抽象口号。
- 不以“文档更短”“层级更少”“术语更统一”为理由删除例外、失败处理、停止条件或验证责任。
- 不为所有语言强制一种测试框架、目录、包管理器、注释语言、提交语言或版本。
- 不自动升级语言、Runtime、依赖、Action、镜像或锁文件。
- 不把 AIMA 的 PostgreSQL、Vue/FastAPI、当前 Blueprint 集合、中文提交/注释等项目选择提升为全球默认。
- 不把当前 `01_...12_` reference 数量变成永久上限。
- 不把真实 Provider Probe 偷塞进普通 CI，也不因本次治理变更发起 TikHub/LLM 付费调用。

# 必须保持不变

- 系统、开发者、用户和目标路径 `AGENTS.md`/同等规则优先于通用 Skill。
- 当前仓库文件、锁、真实命令、实际运行结果和用户明确决定优先；缓存/聊天不能作为事实副本。
- L1/L2/L3、L2/L3 Change、Requirement Traceability、Completion Audit、两阶段 Review、Red-Green-Refactor、根因调试、最小兼容实现、并行冲突检查、文档同步和 Git 安全边界不降低。
- Web/API/PostgreSQL/Provider 的 Browser Mock、Backend/API/PostgreSQL、Contract/Generated Client、Real Full-stack、Real Provider Probe 详细语义完整保留。
- 原规则中的触发条件、例外、失败行为、停止条件、验证责任、安全边界、兼容要求和操作顺序都属于必须保留的语义；组织变化不能把它们变成只能“凭经验推断”的隐含知识。
- 项目有更具体日志规范时服从项目；没有更具体规则且日志体系支持这些语义时，DEBUG/INFO/WARNING/ERROR 的默认严重性仍是规范 fallback，跨生态只允许等价严重性映射，不能降成“可参考”。
- AIMA 的中文提交、中文注释和 Python PEP 257 等项目规则必须在项目 Overlay 中继续存在；通用 Skill 本身不强迫其他仓库使用中文。
- `.reliable-vibe-coding/project-context.json`、`rvc-project-context/v1`、`rvc-change/v1` 协议不做破坏性迁移。
- AIMA 项目本地技术/文档规则继续由根/嵌套 `AGENTS.md`、Blueprint/Roadmap/Appendix/Guide、Contract、Migration、locks、tests、CI 承载。
- Archive 的状态、Evidence、Review、结论不因当前文件改名而改写；只有 Ready Check 作为实时仓库路径校验的 Source 随 canonical 文件移动。

# 关键决策

1. 采用“核心流程 + 条件式 profiles/reference”而不是为每种语言复制完整 Skill，防止 TDD/Git/Review/Change 多份规则长期漂移。
2. Web/API/PostgreSQL/Provider 测试策略保留为完整专项 profile；通用层只负责判断何时加载，不以 generic matrix 替代专项职责。
3. `rvc.py` 保持 `rvc-project-context/v1` 与 `rvc-change/v1` 协议不变，仅扩展静态 Manifest/Workspace 分类。
4. 规则只允许移动、分类、条件化或消除**逐项证明完全等价**的重复；无法证明等价时保留原细节。
5. AIMA PostgreSQL、中文提交/注释、docs 编号等项目选择迁回项目 Overlay；不把项目规则删除，也不把它们强加给其他仓库。
6. Reference 改名采用真正 canonical rename：实时引用迁移后删除无编号副本，不维护第二套当前规范；旧名称只作为历史映射标签存在。
7. Reference 编号只表示当前阅读顺序，不是文档配额；未来按依赖位置增删。
8. Blueprint/Design/Roadmap 等项目文档集合从目标项目实际规则和当前文件发现，不在通用 Skill 写死。
9. `内容守恒优先于篇幅精简` 是未来 Skill 重组的元门禁，但它**不能替代**各 reference 的原规则正文；preservation map 必须能从旧规则追到新规范承载。
10. 自动化测试只能防结构/关键词和已知语义回归，不能单独证明内容完全等价；大规模重组还必须人工逐项检查“必须→建议、默认→参考、停止条件消失、项目规则无承载”等语义退化。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Skill 适用于不同项目、不同研发阶段、不同编程语言 | user:2026-08-25-portable-skill | satisfied | `02_task-routing.md` 建立四维路由；`03_language-and-toolchain-profiles.md` 覆盖主要生态并有未列语言回退；`07_validation-strategy.md` 使用通用风险维度；`rvc.py` 多语言 Manifest 回归经历独立 Red/Green |
| R2 | 重新组织 Skill，使大模型严格按规定流程工作 | user:2026-08-25-portable-skill | satisfied | `SKILL.md` 明确先路由、命中 reference 必须读取、Change/TDD/验证/Review/Git/fresh-evidence 门禁；`agents/openai.yaml` 同步要求 four-dimensional routing、read every triggered reference、preserve details、fresh-evidence gate；RVC self-tests 持续通过 |
| R3 | 不丢失现有内容和有价值细节，不做过度总结 | user:2026-08-25-preserve-skill-details | satisfied | `12_rule-preservation-map.md` 逐项映射原 13 条不变量、工作流 1—11 和专项规则；旧 Skill self-test 曾发现 private/helper 措辞收缩并修复；后续人工 Review 又发现日志 fallback 与 AIMA 中文注释承载问题并通过独立 Red 修复 |
| R4 | 不从历史聊天猜实现，按当前 AGENTS 和 GitHub 事实工作 | AGENTS.md | satisfied | 全程从当前分支/主分支 GitHub 文件、PR diff 和 Actions 恢复事实；main 每次前进均 compare 后正常双父 merge；最终人工 Review 前 compare 为 `behind_by: 0`，base `ae5635bc6a1f0112fc1c7446155cf42e0b8a71a2` |
| R5 | L2 Change 维护 Traceability、Validation Matrix、Completion Audit、两阶段 Review 和新鲜证据 | .agents/skills/reliable-vibe-coding/references/04_change-management.md | satisfied | 用户每次新增完成定义都主动把 Change 从 Ready 回退 `in_progress`；R1-R9 全部覆盖；本轮 Audit/A1/A2/Code Quality 已重新执行；实现 HEAD `e52c345e691117e30ab6bb4587adbb27e0848eb6` 取得完整新鲜 Green，本文件产生最终 Ready candidate 后继续由机器 Gate 验证 |
| R6 | 专项 testing 改名后历史实时 Requirement Source 仍可解析 | changes/archive/2026-08/CHG-20260825-ci-long-term-risk-layers/CHANGE.md | satisfied | Ready Gate 实际先后暴露两个归档 CI Change 的旧 Source；两者均只把实时 Source 迁到 `.agents/skills/reliable-vibe-coding/references/08_testing-strategy.md`，历史 Evidence/状态/结论不变；随后候选 Gate 成功 |
| R7 | 通用 Skill 不写死 Blueprint 数量、固定文档名或编号上限 | user:2026-08-25-dynamic-project-docs | satisfied | `SKILL.md`、根/嵌套 `AGENTS.md`、Blueprint 06、Blueprint README 均改为项目实际集合；portability test 对 `固定 01—08` 建负断言，同时确认当前 AIMA 01—08 导航仍保留 |
| R8 | Skill reference 使用 `01_、02_……` 按研发阶段/依赖顺序，便于阅读；编号不是固定配额 | user:2026-08-25-numbered-skill-references | satisfied | `references/` 只保留 `01_...12_` canonical 文件；旧无编号文件删除；Skill/template/内部 links/自测/AIMA 导航/实时 Source 全迁移；目录唯一性由 Unit 直接断言 |
| R9 | Skill 重组不得过度总结或丢失任何现有/有价值细节；只合理组织，并让默认 Agent 主动执行内容守恒 | user:2026-08-25-preserve-all-details | satisfied | 初始 preservation Red `fe2f7a4103de8edb240680541252cd0bf38c6060`：Ruff/format/mypy 绿、Unit `639 passed / 1 failed`；人工 Review 又用 logging Red `a9e91fac058f5cbf6fa1bc8e2a6882441ba39e5d`（`640 passed / 1 failed`）和 AIMA comment Overlay Red `53edf9bad63e9eb8f9e28b61ee72521f7938ee1e`（`640 passed / 1 failed`）证明并修复两个自动绿灯未发现的语义问题；最终实现 HEAD `e52c345e691117e30ab6bb4587adbb27e0848eb6` Unit `641 passed` 且完整 CI/Runtime/Full-stack Green |

# Validation Matrix

本 Change 的主风险是 Skill/治理语义漂移。产品 Web/API/PostgreSQL 层没有独立产品行为变化；这些层的现有 CI 只作为“没有产品回归”的辅助证据，不能代替内容守恒审计。

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改前端产品行为/路由/请求；实现 Green 的 Playwright `22 passed` 仅证明没有现有浏览器回归 |
| Backend/API/PostgreSQL Integration | not_applicable | 不修改后端业务、Schema/Migration、Job/Worker；实现 Green 的 PostgreSQL Integration 全部 success 仅作无回归辅助 |
| Contract / Generated Client | not_applicable | 不修改 Pydantic/OpenAPI/generated client/Canonical/Job Contract；Contract `75 passed`、API `34 passed` 和 generated drift success 仅作无回归辅助 |
| Real Full-stack Golden Path | not_applicable | 不改变跨组件产品接线；Full-stack Acceptance success 只证明原 Golden Path 未被治理变更破坏 |
| Real Provider Probe | not_applicable | 不改 Provider endpoint/shape/pagination/capability/pricing；未发真实付费 Probe |
| Docs / Governance / Other | required | 三轮需求均有正确 Red；最新实现 HEAD `e52c345e691117e30ab6bb4587adbb27e0848eb6`：CI `32804091561` success，Repository Quality `97670678288` success，PostgreSQL Integration `97670678489` success，CI Gate `97671071702` success，Runtime `32804091564` success，Full-stack `32804091579` success；Ruff format `491 files already formatted`、Ruff success、mypy 242 source files、Unit `641 passed`、Contract 75、API 34、Frontend Unit 39、Playwright 22、Architecture/Ownership/Secret/Docs/Wheel 全 success。Change Completion Gate `32804091575` 的 RVC self-tests success，而 changed-PR readiness 因 Change 当时仍为 `in_progress` 按设计 fail closed；本 Ready candidate 将重新触发最终 Gate |

# Completion Audit

- [x] upstream_re_read：重新读取用户三轮核心要求，尤其最新“不要过度总结、不要丢任何细节”；重新读取当前根 `AGENTS.md`、`docs/AGENTS.md`、主 `SKILL.md`、编号 references、Agent prompt、Change/template、Blueprint README/06；并对照 `main` 原主 Skill、原 `development-workflows.md`、原 `testing-strategy.md` 以及 PR 中被改写的 04/05/10/11/reference/template diff。没有从当前 Change checklist 反推完成定义。
- [x] change_coverage：R1-R9 全部进入 Requirement Traceability。动态 Blueprint、编号 reference、内容守恒都不是只写一句说明：对应主入口、preservation map、Agent prompt、项目 Overlay 和自动回归均有正式承载。
- [x] reverse_audit：从原规则反向逐项检查当前承载。`01_project-discovery.md`、`06_repository-constraints.md`、`08_testing-strategy.md`、`09_collaboration.md` 为纯改名/内容不变；其中 `08_testing-strategy.md` 与旧文件 blob SHA 同为 `242ebc1e0f255e4427fe87ed1f6bbc6cc9a025e6`。`04_change-management.md`、`10_completion-gate.md`、`11_verification-review.md` 的改动是把原 Web/HTTP 示例扩展为 public API/ABI/CLI/Library/Data/Package 等通用边界，原 L2/L3、Traceability、Ready、Browser/API/PostgreSQL/Full-stack/Provider 证据责任仍在。`CHANGE.template.md` 使用 generic matrix，但明确映射回 `08_testing-strategy.md`，保留 Browser Mock ≠ Backend/DB、一条 Full-stack ≠ 全部状态、Provider Probe 有界且默认不进普通 CI。人工继续审计 `05_development-workflows.md` 时发现日志 fallback 曾从规范默认改成“可参考”，另发现原 AIMA 中文注释默认在通用化后缺少项目承载；两项均先建立独立失败回归再修复。中文提交原规则一直由根 `AGENTS.md` 承载，中文注释 + PEP 257 现也由根 `AGENTS.md` 正式承载；preservation map 记录旧通用 fallback → AIMA Overlay 的迁移关系。
- [x] unresolved_cleared：R1-R9 均为 satisfied，没有 `not_satisfied`、无未批准 deferred；所有 required 治理层都有 Red/Green 和人工审计证据。最终 Ready candidate 机器 Gate 若失败，则本结论自动失效并需重新进入 `in_progress`，不得降低门禁。

# 两阶段 Review

## Review A1：上游要求 → Change

结论：**通过。**

逐项从用户要求重建完成定义：

1. Skill 必须跨项目、跨阶段、跨语言，而不是默认 AIMA/Web/Python/PostgreSQL；R1/R2 覆盖。
2. 规则必须能让大模型严格执行：先路由、读命中 reference、Change/Traceability/TDD/验证/Review/Git/fresh evidence 不能被说明文字替代；R2/R5 覆盖。
3. 原有内容和有价值细节不得因通用化、重排、改名或“精简”丢失；R3/R9 覆盖，并有 preservation map + Agent prompt + regression + 人工逐项 Review，而不是只写一个“请保留细节”口号。
4. Blueprint/文档数量、名字不能写死；R7 覆盖。原 AIMA 当前 01—08 仍作为现状导航保留，但“固定 01—08”是用户新要求明确推翻的旧制度，不属于应继续强行保留的全球约束。
5. Reference 应按 `01_、02_……` 顺序便于阅读，同时不能写死数量；R8 覆盖。
6. AIMA 项目本地规则不能因为通用 Skill 去项目化而丢失：docs 编号迁到 `docs/AGENTS.md`，中文提交/中文注释/PEP 257 留在根 `AGENTS.md`；R3/R9 的人工审计明确验证。
7. 历史 Change 不能因当前文件 rename 被重写：仅机器实时 Source 做路径迁移，历史 Evidence/结论保留；R6 覆盖。

没有把当前 Change、自身 checklist、CI 绿色或 preservation map 当成上游需求全集。

## Review A2：Change → 实现 / 测试 / 文档

结论：**通过。**

- 四维入口：`SKILL.md` + `02_task-routing.md`；
- 多语言事实发现：`03_language-and-toolchain-profiles.md` + `rvc.py`；
- 通用风险到证据：`07_validation-strategy.md`；
- Web/API/PostgreSQL/Provider 详细专项：`08_testing-strategy.md`，内容与原文件保持；
- L2/L3/Traceability：`04_change-management.md`；
- Feature/Bug/Refactor/TDD/根因调试/兼容/Git/注释/日志：`05_development-workflows.md`；
- 仓库真实边界：`06_repository-constraints.md`；
- 协作：`09_collaboration.md`；
- Completion：`10_completion-gate.md`；
- Review/交付证据：`11_verification-review.md`；
- 内容守恒审计：`12_rule-preservation-map.md`；
- Agent 默认行为：`agents/openai.yaml`；
- AIMA docs Overlay：`docs/AGENTS.md`；
- AIMA 中文提交/注释 Overlay：根 `AGENTS.md`；
- 当前 Blueprint 动态集合说明：`docs/blueprint/README.md` 和 Blueprint 06；
- 自动回归：`tests/unit/test_reliable_vibe_coding_portability.py` + Skill 原 14 个 self-tests。

人工 Review 发现的两个语义问题都经过“先加失败回归 → 实际确认 Red → 最小修复 → Green”，没有静默直接改文档，也没有降低断言。

## Code Quality Review

结论：**通过，未发现未解决的严重/重要问题。**

- 没有新增依赖、Runtime、包管理器或 lock 变化；
- 没有修改产品 API、Canonical、Schema/Migration、业务数据或产品行为；
- `rvc.py` 只增加静态 Manifest/Workspace 分类，没有网络、Secret、生产写入或新的缓存/Change schema；
- `08_testing-strategy.md` 保持原专项内容，未以 generic validation 替代；
- `04/10/11` 通用化扩大适用边界，不把原 MUST/Ready/证据责任降为建议；
- `05` 的日志 fallback 语义弱化已被人工 Review + 回归修复；
- AIMA 中文注释规则已迁回正确 Overlay，避免“通用化 = 项目规则删除”；
- Secret scan 与 docs link gate 在最新实现 HEAD 成功；
- 没有为通过测试删除/skip/降低断言，没有关闭 Ready Gate；Change 保持 `in_progress` 时 Completion Gate 按设计失败，证明 fail-closed 状态生效；
- 没有混入无关产品重构。

# 任务

- [x] 调查原 Skill、references、template、scripts、tests 和 AIMA 上游规则
- [x] 检查 Active Change / main 并在主分支前进时重新比较和正常同步
- [x] 建立第一轮跨项目通用化 Red：`628 passed / 5 failed`
- [x] 新增四维 task routing、multi-language profile、generic validation、preservation map
- [x] 为 `rvc.py` 多语言 Manifest 发现建立独立 Red：`633 passed / 1 failed`，随后最小 Green
- [x] 原 Skill self-tests 发现 private/helper 措辞收缩并修复，14/14 恢复
- [x] 第一轮 Completion Audit 发现 AIMA docs 项目规则承载不足并新增 `docs/AGENTS.md`
- [x] 第一轮旧 Ready HEAD 曾完整 Green；用户新增要求后主动撤销完成结论
- [x] 建立动态 Blueprint + 编号 reference 回归；首次因 Ruff format 未进入目标断言，不计需求 Red
- [x] 修正测试格式后取得有效 Red：`628 passed / 11 failed`，11 个失败均命中编号/动态文档目标
- [x] 建立 `01_...12_` canonical reference，迁移 Skill/template/AIMA 导航/self-test/live Source，并删除无编号副本
- [x] 修改 Blueprint README：保留当前 01—08 实际导航，取消固定数量/编号上限
- [x] Ready Gate 实际暴露两个归档 CI Change 旧 Requirement Source，均仅迁移实时 Source，不改历史 Evidence/结论
- [x] 编号/动态文档候选完整 Green；用户新增“不要过度总结”后再次撤销 Ready
- [x] 新增 preservation hard-gate 回归并取得 Red `639 passed / 1 failed`
- [x] `SKILL.md`、preservation map、Agent prompt 明确内容守恒规则，恢复 Green
- [x] 人工内容守恒 Review 发现日志 fallback 从“默认语义”弱化成“可参考”
- [x] 建立 logging fallback 回归并取得独立 Red `640 passed / 1 failed`
- [x] 恢复日志级别规范 fallback，并允许跨生态等价严重性映射
- [x] 人工内容守恒 Review 发现 AIMA 原中文注释默认缺少项目 Overlay 承载
- [x] 建立 AIMA comment Overlay 回归并取得独立 Red `640 passed / 1 failed`
- [x] 根 `AGENTS.md` 恢复 AIMA 中文注释 + Python PEP 257；preservation map 登记中文提交/注释迁移
- [x] 最新实现 HEAD `e52c345e691117e30ab6bb4587adbb27e0848eb6` 完整 Green：Unit 641、Contract 75、API 34、Frontend Unit 39、Playwright 22、CI/PG/Runtime/Full-stack 全成功
- [x] 重新执行 R1-R9 Completion Audit 与 A1/A2/Code Quality Review
- [x] 最终 Ready 前 compare main，`behind_by: 0`
- [x] 清零 R5/R9 `not_satisfied` 并将本 Change 置 `ready_for_review` 候选
- [ ] 本文件提交产生的新最终 Ready HEAD 必须取得 Change Completion Gate、CI、Runtime、Full-stack 同 HEAD 机器成功；这是外部 Actions 证据，不通过修改本文件反复记录 run id 形成无限新 HEAD
- [ ] 机器门禁全部成功后把 PR #222 从 Draft 转 Ready；本 Change 不授权自动合并

# 验证

## 第一轮：跨项目/阶段/语言通用化

### 结构通用化 Red

提交 `b82004c6871ca9b92801f9c89605585cec83f851`：

```text
Ruff / format / mypy → 通过
uv run pytest tests/unit -q → 628 passed / 5 failed
```

5 个失败分别对应缺少四维路由、语言 profile、generic Validation Matrix、preservation map、通用 Change template。旧专项 testing 关键断言在该 Red 已通过。

### 多语言项目发现 Red

提交 `1c282d4667415d6e581325bbfc8f4c115b23f131`，CI run `32795417184`：

```text
Ruff / format / mypy → 通过
uv run pytest tests/unit -q → 633 passed / 1 failed
```

唯一失败为 `CMakeLists.txt` 未识别成 Manifest；随后只扩展静态 Manifest/项目后缀分类，不改 cache/change/parser/conflict/CLI 协议。

### 第一轮旧 Green

旧候选 `bfa382b13ae711e6ca1200e4f4ed9ccd4154aa99` 曾取得 CI、Runtime、Full-stack、Change Completion Gate 全部成功。后续用户新增完成定义后该证据只保留为开发历史，不支持最终 Ready。

## 第二轮：动态 Blueprint + 编号 reference

### 首次 Red 尝试不计入

提交 `6ea36cdd2564cfc525c6022aeb317d762a601413` 首次新增回归时，Repository Quality 先被 Ruff format 挡住，目标断言没有运行，因此没有把它伪称为需求 Red。

### 有效 Red

提交 `fe3af58415f09c5d3b1d1be0e6a7be122a51e519`，CI `32798934825` / Repository Quality `97655864851`：

```text
ruff format --check → 491 files already formatted
ruff check → All checks passed
mypy backend/src → Success: no issues found in 242 source files
uv run pytest tests/unit -q → 628 passed / 11 failed / 1 warning
Secret Scan → success
Docs link check → success
```

11 个失败均命中编号 canonical reference 尚不存在/旧无编号路径仍存在、Skill/template 旧路径、动态 Blueprint 尚未落地，没有环境错误混入。

### 实现 Green 与 Ready Source 修正

实现 HEAD `f9138a89b3c0832ae2af0a041de0dbdbe499b6f3` 的 CI `32800997716` 已确认 Ruff/format/mypy、Unit/Contract/API、Architecture/Ownership、Secret/Docs、Wheel、Frontend Unit/Build/Playwright、PostgreSQL Integration、CI Gate 成功。

随后 Ready Gate 实际暴露两份 gated 归档 Change 仍把旧 `testing-strategy.md` 当实时 Requirement Source：

- `CHG-20260825-ci-long-term-risk-layers`
- `CHG-20260824-ci-validation-layers`

两处只把 Source 迁移到 `08_testing-strategy.md`，历史 Evidence/Review/结论不变。候选 `6bc3093164a325e4ef95ef33abf9cff7e94f576c` 随后取得 CI、Runtime、Full-stack、Change Completion Gate 全绿。R9 新要求出现后，该结果不再作为最终 Ready 证据。

## 第三轮：禁止过度总结 / 内容守恒

### R9 元规则 Red

提交 `fe2f7a4103de8edb240680541252cd0bf38c6060`，CI `32802414173` / Repository Quality `97665754214`：

```text
ruff format --check → 491 files already formatted
ruff check → All checks passed
mypy backend/src → Success: no issues found in 242 source files
uv run pytest tests/unit -q → 639 passed / 1 failed / 1 warning
Secret Scan → success
Docs link check → success
```

唯一失败为 `test_reorganization_preserves_executable_detail_instead_of_over_summarizing`，第一个失败断言是 `SKILL.md` 尚未包含 `内容守恒优先于篇幅精简`。随后：

- `agents/openai.yaml` 增加 `preserve all existing valuable details and never replace executable rules with over-summarized abstractions`；
- `SKILL.md` 主入口与“规则完整性维护”增加内容守恒硬门禁；
- `12_rule-preservation-map.md` 增加逐项语义映射、禁止抽象替代可执行细节、无法证明等价时保留原细节；
- portability regression 对这些入口建立机器断言。

实现后 Unit 恢复到 640 通过，但人工 Review 继续执行，没有以该绿灯结束审计。

### 人工审计缺陷 1：日志默认严重性被弱化

对照 `main` 原 `development-workflows.md` 时发现：原文“没有更具体规则时”给出 DEBUG/INFO/WARNING/ERROR **默认语义**；通用化版本曾改成“没有更具体规则时可参考”，把 normative fallback 弱化成建议。

先增加 `test_logging_fallback_severity_semantics_remain_normative`，提交 `a9e91fac058f5cbf6fa1bc8e2a6882441ba39e5d`；CI `32803347189` / Repository Quality `97668507719`：

```text
Ruff / format / mypy → success
Unit → 640 passed / 1 failed
Secret / Docs → success
```

唯一失败为日志 fallback 规范断言。随后 `05_development-workflows.md` 恢复：

```text
项目已有更具体日志规则 → 遵守项目规则
没有更具体规则且现有级别支持这些语义 → 使用原 DEBUG/INFO/WARNING/ERROR 默认严重性
生态名称不同 → 只允许等价严重性映射
```

没有把原默认语义继续写成“参考”。

### 人工审计缺陷 2：AIMA 中文注释缺少 Overlay 承载

原通用前身 `development-workflows.md` 还包含“无项目注释语言约定时默认中文”的项目倾向。为了跨项目可移植，新通用 Skill 正确改为“服从目标项目/生态”，但人工 Review 发现：AIMA 根 `AGENTS.md` 已有 `提交信息使用中文`，却没有正式承载原来的中文注释偏好；这会造成 AIMA 行为丢失。

先在 `test_aima_specific_rules_remain_project_overlay_instead_of_becoming_global` 增加：

```text
除专有名词、标识符、协议、库和标准名外，代码注释使用中文
Python 文档字符串遵循 PEP 257
```

提交 `53edf9bad63e9eb8f9e28b61ee72521f7938ee1e`，CI `32803709259` / Repository Quality `97669570167`：

```text
Ruff / format / mypy → success
Unit → 640 passed / 1 failed / 1 warning
Secret / Docs → success
```

唯一失败为 AIMA comment Overlay 缺失；日志 fallback 回归此时已经通过。

随后根 `AGENTS.md` 新增“注释语言”小节：

- 除专有名词、标识符、协议、库和标准名外，代码注释使用中文；
- Python 文档字符串遵循 PEP 257，其他语言沿用项目文档注释规范；
- 注释解释 why/约束/风险/非直观规则，public 与承载非显然规则的 private/helper 按实际需要说明。

`12_rule-preservation-map.md` 同时登记原中文提交/中文注释 fallback 的归属迁移：通用 Skill 不强迫其他项目中文；AIMA 继续由根 `AGENTS.md` 承载中文提交和中文注释/PEP 257。

## 最新实现 Green

实现 HEAD：

```text
e52c345e691117e30ab6bb4587adbb27e0848eb6
```

CI run `32804091561`：

```text
Repository Quality job 97670678288 → success
PostgreSQL Integration job 97670678489 → success
CI Gate 97671071702 → success
```

Repository Quality 完整输出：

```text
ruff format --check → 491 files already formatted
ruff check → All checks passed
mypy backend/src → Success: no issues found in 242 source files
Unit → 641 passed / 1 warning
Contract → 75 passed
API → 34 passed / 1 warning
Architecture → success
Table Ownership → success
Secret Scan → success
Docs link check → success
Wheel build + isolated install/import → success, version 0.1.0
Frontend lint/typecheck/build → success
Frontend Unit → 39 passed
Playwright Browser Mock Acceptance → 22 passed
```

同一实现 HEAD 的：

```text
Runtime Acceptance 32804091564 → success
Full-stack Acceptance 32804091579 → success
Change Completion Gate 32804091575：
  RVC completion-gate self-tests → success
  changed-PR readiness → failure
```

最后一项 failure 是当时 Change 明确仍为 `in_progress` 的预期 fail-closed 结果，不是 Skill self-test 或实现失败。现在本文件已完成 R1-R9 Audit 并进入 `ready_for_review`；由本次更新产生的新 HEAD 必须重新执行并通过 changed-PR readiness。

# 文档影响

- `references/` 当前规范统一使用 `01_...` 两位数字阅读顺序，但数量不是固定配额。
- `docs/AGENTS.md` 保留 AIMA 两位数字 docs 导航、README 不编号、实时引用迁移和 archive 历史边界，同时明确不预设固定文档数量、文件名、编号上限。
- 根 `AGENTS.md`、Blueprint 06、Blueprint README 按当前实际 `docs/blueprint/` 集合理解核心架构；当前 01—08 继续存在，但不是永久数量制度。
- 根 `AGENTS.md` 新增 AIMA 注释语言 Overlay，恢复中文注释 + Python PEP 257，不把这条项目规则写回通用 Skill。
- `12_rule-preservation-map.md` 记录 AIMA docs、中文提交/注释、日志 fallback 等具体迁移和守恒结论，不只列关键词。
- 两个归档 CI Change 仅迁移实时 Requirement Source 到 `08_testing-strategy.md`，历史 Evidence/Review/结论保持。
- AIMA 产品 HTTP/Canonical/数据库/前端功能文档没有产品行为变化，不制造无关差异。

# 兼容性、依赖、Migration、部署与回滚

- Public product API / Contract：无变化。
- Database Schema / Migration：无变化。
- 产品数据：无变化。
- 依赖 / Lock：无变化。
- Runtime / Deployment：无变化。
- Skill cache schema：`rvc-project-context/v1` 不变。
- Change schema：`rvc-change/v1` 不变。
- Skill canonical reference 路径：从无编号名称迁移为两位数字名称；仓库实时引用同 Change 迁移。历史自然语言可以保留旧名称作为历史标签，但不能作为当前机器 Source。
- AIMA 中文提交/注释行为：继续存在，只是从旧通用 fallback 迁到项目根 `AGENTS.md`，避免污染其他项目。
- 回滚：可整体 revert 本 PR 的 Skill/docs/test/tooling diff；不涉及产品数据回滚、Migration downgrade 或外部 Provider 状态恢复。

# 交付

- Branch：`refactor/reliable-vibe-coding-portable-routing`
- PR：`#222`，当前仍保持 Draft；本文件更新产生的最终 Ready candidate HEAD 的机器门禁全部成功后才转 Ready
- Current main base：`ae5635bc6a1f0112fc1c7446155cf42e0b8a71a2`，最后 compare `behind_by: 0`
- Latest main sync merge：`e1e86992c8da3150f0245dc95ad33a96c3bd93bd`
- Dynamic docs / numbered reference historical Green：`6bc3093164a325e4ef95ef33abf9cff7e94f576c`
- R9 initial Red：`fe2f7a4103de8edb240680541252cd0bf38c6060`
- Logging preservation Red：`a9e91fac058f5cbf6fa1bc8e2a6882441ba39e5d`
- AIMA comment Overlay Red：`53edf9bad63e9eb8f9e28b61ee72521f7938ee1e`
- Latest implementation Green：`e52c345e691117e30ab6bb4587adbb27e0848eb6`
- Final Ready candidate：由本文件更新提交产生；以该 HEAD 的 Actions 为最终机器证据，不在本文件里反复写回 run id 形成无限新 HEAD
- Merge：未执行，也不在本 Change 中自动执行
- Release / Deploy：不适用
