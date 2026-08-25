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
  - docs/blueprint/README.md
  - docs/blueprint/06_开发约束与分阶段实施.md
  - changes/archive/2026-08/CHG-20260824-ci-validation-layers/CHANGE.md
  - changes/archive/2026-08/CHG-20260825-ci-long-term-risk-layers/CHANGE.md
  - tests/unit/test_reliable_vibe_coding_portability.py
  - tests/unit/test_reliable_vibe_coding_global_language_rules.py
contracts: []
data_changes: []
---

# 背景与当前事实

当前仓库只有一套 `.agents/skills/reliable-vibe-coding/` Skill。原 Skill 已经包含项目发现、L1-L3 分级、Change 管理、Requirement Traceability、Completion Audit、Red-Green-Refactor、根因调试、分层验证、多人协作、Review、Git、安全、文档同步和交付证据等机制，但原主 `SKILL.md` 同时承担入口、路由、流程正文、AIMA/Web 技术形态示例和交付门禁，容易让“跨项目通用规则”和“AIMA 当前项目选择”混在一起。

本 Change 的目标从始至终不是把 Skill 写短，而是把规则重新组织成更清晰、可路由、可执行的规范体系。用户在开发过程中连续补充了四组要求，每一次新增要求都使此前的 Ready/Green 结论失效并重新走门禁：

1. **跨项目、跨研发阶段、跨编程语言通用化。** Agent 必须先按项目形态、研发阶段/任务类型、语言/工具链、L1-L3 风险四个维度恢复事实并路由，再读取命中的规则。
2. **文档结构不能写死。** 通用 Skill 不能把某个项目的 `Blueprint 01—08`、固定文件数量、固定文件名或固定编号上限当成全球规则；`references/` 则应使用 `01_、02_……` 两位数字表达研发流程阅读顺序，方便人工阅读，但编号不能反向成为固定配额。
3. **内容守恒优先，禁止过度总结。** 用户明确要求“不丢失任何细节和有价值内容，不要删除内容，只做合理组织，并确保大模型严格按 Skill 流程工作”。因此“通用化/精简”不能把多条带触发条件、例外、失败处理、停止条件、验证责任、安全/兼容边界的规则压成一句抽象原则；只有逐项证明完全等价时才允许消除重复，无法证明等价时保留原细节。
4. **中文提交、中文注释、内部函数注释必须是通用原则。** 用户在 2026-08-25 再次明确：所有 Git 提交信息使用中文；代码注释使用中文；内部/private/helper 函数也必须写函数级注释；这三类要求要写进 Skill 通用原则，不能依赖 AIMA 或任何项目 Overlay。该决定明确覆盖前一轮“为了跨项目可移植而把中文提交/注释暂归 AIMA Overlay”的分类，但不删除那段真实历史。

第一轮通用化曾在旧候选 HEAD `bfa382b13ae711e6ca1200e4f4ed9ccd4154aa99` 取得完整 CI/Runtime/Full-stack/Completion Green；用户新增动态文档/编号要求后该结论主动失效。第二轮编号/动态 Blueprint 候选 `6bc3093164a325e4ef95ef33abf9cff7e94f576c` 又取得完整 Green；用户再次提出“不要过度总结/不要丢细节”后该结论再次主动失效。第三轮内容守恒候选 `9049a6b4368cd2217a12dd31942a30f7036d1ee3` 曾取得 Change Completion Gate、CI、Runtime、Full-stack 同 HEAD 全绿；用户随后把中文提交/注释/内部函数注释提升为通用原则，因此该 Ready 结论再次失效。本 Change 没有用旧绿灯冒充新完成定义。

现有 Web/API/PostgreSQL/Provider 专项测试策略的规则内容完整保留；当前规范路径从原 `testing-strategy.md` 迁移为编号后的 `08_testing-strategy.md`。对仍被 Ready Check 当作实时仓库路径解析的历史 Requirement Source，只迁移 Source 路径，不改写历史 Change 的 Evidence、状态、Review 或结论。

本 Change 只修改 Skill、Agent 默认提示、项目治理文档、回归测试和 `rvc.py` 的只读项目发现能力；不改变 AIMA 产品 API、Canonical/HTTP Contract、数据库 Schema/Migration、业务数据、前端产品行为、运行时部署语义或依赖锁。

# Git / main 同步事实

开发期间 `main` 多次前进，每次都重新比较真实差异后再决定是否同步，没有从旧聊天或旧 SHA 猜当前状态：

1. 第一轮同步到 `9b6457d3549dea57f85d52bf664227b47791b9b4`。
2. PR #223 的 Actions 历史清理使 `main` 前进到 `3591c1fbdbf50a65c6da3e773fe6e12b1246d5`，确认未触碰 Skill 后通过双父 merge `5eafde1c09c10a0f54ae007c3d93ccc27d616223` 正常同步。
3. PR #224 完成 Actions 清理收尾后 `main` 前进到 `73027fe300e86d29b5864a0b90d1b7ec82669961`，再次确认无 Skill 冲突后通过双父 merge `230be2f9202acf94c4e6d90fa26b5eaca1e1c072` 同步。
4. Actions 清理 Change 归档后 `main` 前进到 `ae5635bc6a1f0112fc1c7446155cf42e0b8a71a2`，差异仅为另一个 Change 从 active 移到 archive，通过双父 merge `e1e86992c8da3150f0245dc95ad33a96c3bd93bd` 同步。
5. 第三轮内容守恒 Ready 前 compare 为 `behind_by: 0`，base 仍为 `ae5635bc6a1f0112fc1c7446155cf42e0b8a71a2`。
6. R10 开始时发现 `main` 又前进到 `dfe2491afe91b59864609e9eaf830d8661643e91`。检查该提交确认它只有一个 0 字节 `README_DO_NOT_USE`，且提交信息为空，是前序工具操作遗留的无关污染，不属于用户代码。没有把它混入 Skill 语义：在 `main` 用中文提交 `移除误创建的空文件` 删除该文件，得到 `99d830fb3b9d78ec019ff68198b976bf83475a57`；随后通过正常双父 merge `a698b46220d5499b59d705f6ffff79ed323d3115` 把最新 `main` 同步到当前分支，提交信息为 `同步主分支误文件清理提交`。同步后 compare 为 `behind_by: 0`。

最终 Ready 前还必须重新 compare 最新 `main`；如果主分支再次前进，必须根据真实差异判断是否同步，不能复用本段旧结论。

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

R10 加入后，通用 Skill 还必须无条件包含下面三类语言/注释门禁：

```text
所有 Git 提交信息使用中文
代码注释统一使用中文
新增或修改的 public/exported 与 internal/private/helper 函数都必须有函数级中文注释或文档注释
```

专有名词、标识符、协议、库、标准名和必须原样保留的外部文本可以保持原语言；项目可以增加提交格式、前缀、工单号，以及选择 docstring/Javadoc/XML docs 等文档注释语法，但不能取消中文语言和内部函数级说明要求。

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
- [x] 前一轮为了保证 AIMA 行为不丢失，曾把中文提交、中文注释和 PEP 257 正式写入根 `AGENTS.md`。该历史继续保留；R10 现在把中文提交、中文注释、内部函数级说明进一步提升为通用 Skill 硬原则，AIMA 本地规则变成重复强化而不是生效前提。
- [x] `SKILL.md` 现已明确 `所有 Git 提交信息使用中文`、`代码注释统一使用中文`、`内部/private/helper 函数也必须写函数级中文注释或文档注释`。
- [x] `05_development-workflows.md` 已展开中文提交、中文注释、public/exported 与 internal/private/helper 函数级说明、简单函数一句话说明、复杂规则 why/invariant/risk/compatibility，以及保留专有名词/标识符/协议等原文的边界。
- [x] `11_verification-review.md` 已把中文函数级说明与 `Commit message 必须使用中文` 纳入 Code Quality/Git Review；旧 `非显然内部/private/helper` 具体复核语义继续保留。
- [x] `agents/openai.yaml` 默认提示明确要求 `write Git commit messages in Chinese`、`write code comments in Chinese`、`document internal/private/helper functions`。
- [x] `12_rule-preservation-map.md` 保留“前一轮曾把中文规则分类为 Overlay”的真实历史，同时明确 R10 覆盖该旧归属；当前 `应留在通用 Skill` 包含中文提交、中文注释、内部函数级说明，`应由项目 Overlay 决定` 只保留提交格式/注释语法等附加细节。
- [x] 为 R10 新增独立 Unit 回归，且已经取得因三条通用规则缺失而失败的有效 Red。
- [ ] R10 实现后的最终候选需要完成重新执行的 Completion Audit、A1/A2/Code Quality Review，并在最终 Change HEAD 上取得 Change Completion Gate、CI、Runtime、Full-stack 全部成功后才能重新转 PR Ready。

# 范围

- 重组 `.agents/skills/reliable-vibe-coding/SKILL.md` 的入口、路由和统一工作流组织。
- 将 `.agents/skills/reliable-vibe-coding/references/*.md` 迁移为两位数字前缀的研发流程阅读顺序，完成所有实时引用迁移后删除旧无编号副本。
- 新增/维护 `02_task-routing.md`、`03_language-and-toolchain-profiles.md`、`07_validation-strategy.md`、`12_rule-preservation-map.md`。
- 调整 `04_change-management.md`、`05_development-workflows.md`、`10_completion-gate.md`、`11_verification-review.md` 和 `CHANGE.template.md` 的通用表达，但不降低原职责。
- 保留 Web/API/PostgreSQL/Provider 专项策略全部有效语义，将 canonical 路径迁为 `08_testing-strategy.md`。
- 扩展 `rvc.py` 常见多语言 Manifest/Workspace 的只读发现，不改变缓存/Change schema、parser、conflict detection 或 CLI 协议。
- 更新 `agents/openai.yaml`，要求默认 Agent 四维路由、读取所有命中 reference、保留所有已有有价值细节、中文提交、中文注释、内部函数级说明，并完成 fresh-evidence gate。
- 更新 AIMA 根/嵌套 `AGENTS.md`、Blueprint README、Blueprint 06 的当前 Skill 路径、动态文档治理和项目 Overlay。
- 对旧 `testing-strategy.md` 的实时历史 Requirement Source 做路径迁移，不重写历史证据。
- 增加仓库级回归测试验证上述结构、语义、内容守恒、中文提交/注释/内部函数级说明和项目 Overlay 边界。

# 非目标

当前非目标：

- 不修改 AIMA 产品代码、HTTP/Canonical Contract、数据库 Schema/Migration、产品数据、前端业务功能或运行时部署语义。
- 不修改长期 CI 风险层架构，不新增平行 Workflow。
- 不删除原 reference 中仍有效的规则细节，不把硬规则压成抽象口号。
- 不以“文档更短”“层级更少”“术语更统一”为理由删除例外、失败处理、停止条件或验证责任。
- 不为所有语言强制一种测试框架、目录、包管理器或版本。
- 不自动升级语言、Runtime、依赖、Action、镜像或锁文件。
- 不把 AIMA 的 PostgreSQL、Vue/FastAPI、当前 Blueprint 集合等项目技术选择提升为全球默认。
- 不把当前 `01_...12_` reference 数量变成永久上限。
- 不把真实 Provider Probe 偷塞进普通 CI，也不因本次治理变更发起 TikHub/LLM 付费调用。

被 R10 明确替代、仅作为历史保留的旧非目标：

```text
不为所有语言强制注释语言或提交语言
不把 AIMA 的中文提交/注释提升为全球默认
```

这两条在前一轮是为了避免项目偏好污染通用 Skill；用户随后明确要求相反的当前规则，因此它们不再是现行非目标，但必须保留在 Change 历史中解释设计演进。

# 必须保持不变

- 系统、开发者、用户和目标路径 `AGENTS.md`/同等规则优先于通用 Skill。
- 当前仓库文件、锁、真实命令、实际运行结果和用户明确决定优先；缓存/聊天不能作为事实副本。
- L1/L2/L3、L2/L3 Change、Requirement Traceability、Completion Audit、两阶段 Review、Red-Green-Refactor、根因调试、最小兼容实现、并行冲突检查、文档同步和 Git 安全边界不降低。
- Web/API/PostgreSQL/Provider 的 Browser Mock、Backend/API/PostgreSQL、Contract/Generated Client、Real Full-stack、Real Provider Probe 详细语义完整保留。
- 原规则中的触发条件、例外、失败行为、停止条件、验证责任、安全边界、兼容要求和操作顺序都属于必须保留的语义；组织变化不能把它们变成只能“凭经验推断”的隐含知识。
- 项目有更具体日志规范时服从项目；没有更具体规则且日志体系支持这些语义时，DEBUG/INFO/WARNING/ERROR 的默认严重性仍是规范 fallback，跨生态只允许等价严重性映射，不能降成“可参考”。
- **所有 Git 提交信息使用中文是通用 Skill 规则。** 项目只能附加格式/前缀/工单号等要求，不能把语言改成非中文。
- **代码注释统一使用中文是通用 Skill 规则。** 专有名词、标识符、协议、库、标准名和必须原样保留的外部文本可保留原文。
- **新增或修改的 public/exported 与 internal/private/helper 函数都必须有函数级中文说明。** 简单函数可用一句简短职责说明；非显然内部逻辑还必须继续解释业务规则、不变量、状态转换、算法取舍、兼容原因或重要副作用。
- AIMA 根 `AGENTS.md` 继续保留中文提交、中文注释和 Python PEP 257，与通用规则兼容并增加 Python 项目细节；但通用规则不依赖这些项目条款才能成立。
- `.reliable-vibe-coding/project-context.json`、`rvc-project-context/v1`、`rvc-change/v1` 协议不做破坏性迁移。
- AIMA 项目本地技术/文档规则继续由根/嵌套 `AGENTS.md`、Blueprint/Roadmap/Appendix/Guide、Contract、Migration、locks、tests、CI 承载。
- Archive 的状态、Evidence、Review、结论不因当前文件改名而改写；只有 Ready Check 作为实时仓库路径校验的 Source 随 canonical 文件移动。

# 关键决策

1. 采用“核心流程 + 条件式 profiles/reference”而不是为每种语言复制完整 Skill，防止 TDD/Git/Review/Change 多份规则长期漂移。
2. Web/API/PostgreSQL/Provider 测试策略保留为完整专项 profile；通用层只负责判断何时加载，不以 generic matrix 替代专项职责。
3. `rvc.py` 保持 `rvc-project-context/v1` 与 `rvc-change/v1` 协议不变，仅扩展静态 Manifest/Workspace 分类。
4. 规则只允许移动、分类、条件化或消除**逐项证明完全等价**的重复；无法证明等价时保留原细节。
5. 历史决策：第一轮通用化曾把 AIMA PostgreSQL、中文提交/注释、docs 编号等一起分类为项目 Overlay，以免项目事实污染通用 Skill；当时 AIMA 的中文提交/注释被完整迁回根 `AGENTS.md`，没有删除。
6. 当前决策：R10 明确覆盖第 5 条中“中文提交/注释属于 Overlay”的部分。PostgreSQL、框架、docs 编号等仍是项目 Overlay；**中文提交、中文注释、internal/private/helper 函数级说明现在属于通用 Skill。** 旧分类继续作为历史记录，不是当前规范。
7. Reference 改名采用真正 canonical rename：实时引用迁移后删除无编号副本，不维护第二套当前规范；旧名称只作为历史映射标签存在。
8. Reference 编号只表示当前阅读顺序，不是文档配额；未来按依赖位置增删。
9. Blueprint/Design/Roadmap 等项目文档集合从目标项目实际规则和当前文件发现，不在通用 Skill 写死。
10. `内容守恒优先于篇幅精简` 是未来 Skill 重组的元门禁，但它**不能替代**各 reference 的原规则正文；preservation map 必须能从旧规则追到新规范承载。
11. 自动化测试只能防结构/关键词和已知语义回归，不能单独证明内容完全等价；大规模重组还必须人工逐项检查“必须→建议、默认→参考、停止条件消失、项目规则无承载”等语义退化。
12. R10 的实现不能通过删除旧 self-test 或修改旧断言来“制造通过”；旧 `内部/private/helper 函数包含非显然业务规则` 与 `非显然内部/private/helper` 具体措辞已在新规则中保留，同时新增更强的“所有内部函数均有函数级中文说明”基线。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Skill 适用于不同项目、不同研发阶段、不同编程语言 | user:2026-08-25-portable-skill | satisfied | `02_task-routing.md` 建立四维路由；`03_language-and-toolchain-profiles.md` 覆盖主要生态并有未列语言回退；`07_validation-strategy.md` 使用通用风险维度；`rvc.py` 多语言 Manifest 回归经历独立 Red/Green |
| R2 | 重新组织 Skill，使大模型严格按规定流程工作 | user:2026-08-25-portable-skill | satisfied | `SKILL.md` 明确先路由、命中 reference 必须读取、Change/TDD/验证/Review/Git/fresh-evidence 门禁；`agents/openai.yaml` 同步要求 four-dimensional routing、read every triggered reference、preserve details、fresh-evidence gate；RVC self-tests 持续验证 |
| R3 | 不丢失现有内容和有价值细节，不做过度总结 | user:2026-08-25-preserve-skill-details | satisfied | `12_rule-preservation-map.md` 逐项映射原 13 条不变量、工作流 1—11 和专项规则；旧 Skill self-test 曾发现 private/helper 措辞收缩并修复；后续人工 Review 又发现日志 fallback 与 AIMA 中文注释承载问题并通过独立 Red 修复 |
| R4 | 不从历史聊天猜实现，按当前 AGENTS 和 GitHub 事实工作 | AGENTS.md | satisfied | 全程从当前分支/主分支 GitHub 文件、PR diff 和 Actions 恢复事实；main 前进均 compare 后正常同步；R10 开始时还识别并清理一个 0 字节误文件提交，再以正常双父 merge 同步最新 main |
| R5 | L2 Change 维护 Traceability、Validation Matrix、Completion Audit、两阶段 Review 和新鲜证据 | .agents/skills/reliable-vibe-coding/references/04_change-management.md | not_satisfied | R10 是新的上游完成定义，因此上一轮 `ready_for_review` 与 Audit/Review 结论已失效；本文件已重新置 `in_progress`，R10 已进入 Traceability，仍需对 R1-R10 重新做 Completion Audit、A1/A2/Code Quality，并取得最终同 HEAD 机器 Gate |
| R6 | 专项 testing 改名后历史实时 Requirement Source 仍可解析 | changes/archive/2026-08/CHG-20260825-ci-long-term-risk-layers/CHANGE.md | satisfied | Ready Gate 实际先后暴露两个归档 CI Change 的旧 Source；两者均只把实时 Source 迁到 `.agents/skills/reliable-vibe-coding/references/08_testing-strategy.md`，历史 Evidence/状态/结论不变 |
| R7 | 通用 Skill 不写死 Blueprint 数量、固定文档名或编号上限 | user:2026-08-25-dynamic-project-docs | satisfied | `SKILL.md`、根/嵌套 `AGENTS.md`、Blueprint 06、Blueprint README 均改为项目实际集合；portability test 对 `固定 01—08` 建负断言，同时确认当前 AIMA 01—08 导航仍保留 |
| R8 | Skill reference 使用 `01_、02_……` 按研发阶段/依赖顺序，便于阅读；编号不是固定配额 | user:2026-08-25-numbered-skill-references | satisfied | `references/` 只保留 `01_...12_` canonical 文件；旧无编号文件删除；Skill/template/内部 links/自测/AIMA 导航/实时 Source 全迁移；目录唯一性由 Unit 直接断言 |
| R9 | Skill 重组不得过度总结或丢失任何现有/有价值细节；只合理组织，并让默认 Agent 主动执行内容守恒 | user:2026-08-25-preserve-all-details | satisfied | preservation Red `fe2f7a4103de8edb240680541252cd0bf38c6060`：Unit `639 passed / 1 failed`；logging Red `a9e91fac058f5cbf6fa1bc8e2a6882441ba39e5d`：`640 passed / 1 failed`；AIMA comment Overlay Red `53edf9bad63e9eb8f9e28b61ee72521f7938ee1e`：`640 passed / 1 failed`；人工 Review 实际发现并修复自动绿灯没有覆盖的语义问题，旧专项 testing 内容保持 |
| R10 | Git 提交信息中文、代码注释中文、内部/private/helper 函数也必须写函数级注释；这些是 Skill 通用原则，不能依赖项目 Overlay | user:2026-08-25-global-chinese-commit-comments | not_satisfied | 新增 `tests/unit/test_reliable_vibe_coding_global_language_rules.py`。两次格式问题未进入目标断言，不计需求 Red；有效 Red commit `193e40bda3dc15fa78a64b24dd11c9114e30df38` / CI `32805896442` / Repository Quality `97675878991`：Ruff format `492 files already formatted`、Ruff success、mypy 242 success、Unit `641 passed / 3 failed / 1 warning`，三个失败分别对应中文提交、中文注释/内部函数说明、规则不应委托 Overlay；Secret/Docs success。当前实现已更新 `SKILL.md`、`05_development-workflows.md`、`11_verification-review.md`、`12_rule-preservation-map.md`、`agents/openai.yaml` 和 portability tests；实现候选 `55aae9a0b534e47a910b064c4017c5db39f5045c` 的 CI/Runtime/Full-stack 已成功且 Unit `644 passed`，但 R10 完成定义尚未重新 Audit，所以仍保持 `not_satisfied` 直到最终 Change HEAD 门禁闭环 |

# Validation Matrix

本 Change 的主风险是 Skill/治理语义漂移。产品 Web/API/PostgreSQL 层没有独立产品行为变化；这些层的现有 CI 只作为“没有产品回归”的辅助证据，不能代替内容守恒和 R10 语义审计。

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改前端产品行为/路由/请求；实现候选的 Playwright `22 passed` 只证明没有现有浏览器回归 |
| Backend/API/PostgreSQL Integration | not_applicable | 不修改后端业务、Schema/Migration、Job/Worker；PostgreSQL Integration success 仅作无回归辅助 |
| Contract / Generated Client | not_applicable | 不修改 Pydantic/OpenAPI/generated client/Canonical/Job Contract；Contract `75 passed`、API `34 passed`、generated drift success 仅作无回归辅助 |
| Real Full-stack Golden Path | not_applicable | 不改变跨组件产品接线；Full-stack Acceptance success 只证明现有 Golden Path 未被治理变更破坏 |
| Real Provider Probe | not_applicable | 不改 Provider endpoint/shape/pagination/capability/pricing；没有执行真实付费 Probe |
| Docs / Governance / Other | required | 前三轮完整 Red/Green 历史继续保留。R10 有效 Red 为 `193e40bda3dc15fa78a64b24dd11c9114e30df38`：Ruff/format/mypy 成功，Unit `641 passed / 3 failed`，仅三条新通用语言规则失败。实现候选 `55aae9a0b534e47a910b064c4017c5db39f5045c` 的 CI `32806772123`、Runtime `32806772073`、Full-stack `32806772091`、结构性 Change Completion Gate `32806772097` 均 success；Repository Quality 完整日志：Ruff format `492 files already formatted`、Ruff success、mypy 242、Unit `644 passed / 1 warning`、Contract 75、API 34、Frontend Unit 39、Playwright 22、Architecture/Ownership/Secret/Docs/Wheel 全 success。该 Completion Gate 发生在 Change 尚未纳入 R10 语义前，只能证明结构/旧 Traceability，不作为 R10 Completion Audit 证据；当前 Change 已重新 `in_progress`，最终必须在更新后的 Change HEAD 重跑 Gate |

# Completion Audit

- [ ] upstream_re_read：需要基于用户四轮要求重新读取当前 `SKILL.md`、05/11/12 reference、Agent prompt、R10 tests、根 `AGENTS.md`、Active Change 和最新 main，独立重建最终完成定义；不能复用 R1-R9 的旧 Audit 当成 R10 审计。
- [ ] change_coverage：需要确认 R1-R10 全部进入当前 Change，尤其 R10 三条规则都位于通用 Skill/Review/Agent prompt，而不是只靠 AIMA `AGENTS.md`；同时检查被 R10 覆盖的旧“Overlay”分类只作为历史保留，不再出现在当前规范段落。
- [ ] reverse_audit：需要从旧规则与 R10 新规则双向审计：旧 private/helper 非显然规则具体语义、日志 fallback、Web/API/PostgreSQL 专项、动态 docs、编号 reference 都不能回归；新增中文提交/中文注释/全部内部函数级说明也必须从主 Skill → workflow → review → Agent prompt → regression 全链可达。
- [ ] unresolved_cleared：R5/R10 当前为 `not_satisfied`；只有新的 Completion Audit、A1/A2/Code Quality、最新 main compare 和最终同 HEAD Actions 成功后才能清零。

# 两阶段 Review

## Review A1：上游要求 → Change

前三轮 A1 结论保留为开发历史，但 R10 出现后不再是最终结论。重新 Review 必须覆盖：

1. 跨项目/阶段/语言四维路由。
2. 大模型必须读命中 reference 并严格执行 Change/TDD/验证/Review/Git/fresh-evidence。
3. 内容守恒优先，不把可执行细节压成抽象口号。
4. Blueprint/文档数量不写死；reference 采用两位数字阅读顺序但没有固定配额。
5. Web/API/PostgreSQL/Provider 原专项策略继续完整保留。
6. **所有 Git 提交信息使用中文。**
7. **代码注释统一使用中文。**
8. **新增或修改的 public/exported、internal/private/helper 函数都必须有函数级中文说明；internal/private/helper 不能因为可见性低或简单就完全省略。**
9. 项目 Overlay 只能附加提交格式、注释语法、PEP 257 等更具体约束，不能取消 R10 通用规则。
10. 旧“中文规则属于 Overlay”的历史必须保留但明确被 R10 覆盖，不能让历史文字重新成为当前规范。

当前状态：**重新打开，待最终复核。**

## Review A2：Change → 实现 / 测试 / 文档

前三轮 A2 结论保留为历史。R10 最终 A2 还要逐项核对：

- `SKILL.md` 是否在通用不变量和 Git/注释工作流中直接写中文提交、中文注释、内部函数级说明。
- `05_development-workflows.md` 是否保留旧 `内部/private/helper 函数包含非显然业务规则` 具体语义，同时增加所有内部函数至少一句中文函数级职责说明。
- `11_verification-review.md` 是否同时检查 `新增或修改的 public/exported 与内部/private/helper 函数是否都有必要的中文函数级说明`、旧 `非显然内部/private/helper` 复杂规则，以及 `Commit message 必须使用中文`。
- `12_rule-preservation-map.md` 是否保留旧 Overlay 迁移历史并清楚标记 R10 为当前覆盖决定；`应由项目 Overlay 决定` 不得再含 `commit message 语言` 或 `代码注释与 docstring/comment language`。
- `agents/openai.yaml` 是否让默认 Agent 直接执行三条通用规则。
- 新增 R10 tests 是否经历正确 Red/Green，没有通过删除旧 self-test、降低断言或硬编码测试数据制造通过。
- AIMA 根 `AGENTS.md` 的中文提交/注释/PEP 257 仍然保留，与通用规则兼容。

当前状态：**重新打开，待最终复核。**

## Code Quality Review

前三轮未发现未解决严重/重要问题。R10 仍需重新检查：

- 只改治理/测试/Agent prompt，不触及产品 API、数据、Migration、Runtime、lock。
- 规则文字不自相矛盾；通用中文规则与项目附加约束边界明确。
- 不因“内部函数都要注释”制造要求逐行翻译或大段模板化注释；简单函数一句话即可，复杂函数说明原因/约束。
- 不删除原 self-tests；本轮 self-tests 曾实际发现旧具体措辞丢失，并通过恢复具体语义解决。
- 所有本轮 Git 提交信息使用中文；R10 有效 Red 之前的历史空提交属于已识别并修复的工具污染，不把它当正常规则执行结果。
- Secret/Docs/架构/Owner 等质量门禁继续保持。

当前状态：**重新打开，待最终复核。**

# 任务

## 前三轮已完成并保留的任务

- [x] 调查原 Skill、references、template、scripts、tests 和 AIMA 上游规则。
- [x] 检查 Active Change / main 并在主分支前进时重新比较和正常同步。
- [x] 建立第一轮跨项目通用化 Red：`628 passed / 5 failed`。
- [x] 新增四维 task routing、multi-language profile、generic validation、preservation map。
- [x] 为 `rvc.py` 多语言 Manifest 发现建立独立 Red：`633 passed / 1 failed`，随后最小 Green。
- [x] 原 Skill self-tests 发现 private/helper 措辞收缩并修复，14/14 恢复。
- [x] 第一轮 Completion Audit 发现 AIMA docs 项目规则承载不足并新增 `docs/AGENTS.md`。
- [x] 第一轮旧 Ready HEAD 曾完整 Green；用户新增要求后主动撤销完成结论。
- [x] 建立动态 Blueprint + 编号 reference 回归；首次因 Ruff format 未进入目标断言，不计需求 Red。
- [x] 修正测试格式后取得有效 Red：`628 passed / 11 failed`，11 个失败均命中编号/动态文档目标。
- [x] 建立 `01_...12_` canonical reference，迁移 Skill/template/AIMA 导航/self-test/live Source，并删除无编号副本。
- [x] 修改 Blueprint README：保留当前 01—08 实际导航，取消固定数量/编号上限。
- [x] Ready Gate 实际暴露两个归档 CI Change 旧 Requirement Source，均仅迁移实时 Source，不改历史 Evidence/结论。
- [x] 编号/动态文档候选完整 Green；用户新增“不要过度总结”后再次撤销 Ready。
- [x] 新增 preservation hard-gate 回归并取得 Red `639 passed / 1 failed`。
- [x] `SKILL.md`、preservation map、Agent prompt 明确内容守恒规则，恢复 Green。
- [x] 人工内容守恒 Review 发现日志 fallback 从“默认语义”弱化成“可参考”。
- [x] 建立 logging fallback 回归并取得独立 Red `640 passed / 1 failed`。
- [x] 恢复日志级别规范 fallback，并允许跨生态等价严重性映射。
- [x] 人工内容守恒 Review 发现 AIMA 原中文注释默认缺少项目 Overlay 承载。
- [x] 建立 AIMA comment Overlay 回归并取得独立 Red `640 passed / 1 failed`。
- [x] 根 `AGENTS.md` 恢复 AIMA 中文注释 + Python PEP 257；preservation map 登记当时的中文提交/注释迁移。
- [x] 第三轮实现 HEAD `e52c345e691117e30ab6bb4587adbb27e0848eb6` 完整 Green：Unit 641、Contract 75、API 34、Frontend Unit 39、Playwright 22、CI/PG/Runtime/Full-stack 全成功。
- [x] 第三轮重新执行 R1-R9 Completion Audit 与 A1/A2/Code Quality Review。
- [x] 第三轮最终 Ready candidate `9049a6b4368cd2217a12dd31942a30f7036d1ee3` 取得 Change Completion Gate、CI、Runtime、Full-stack 同 HEAD success；R10 出现后该 Ready 结论失效但证据保留。

## R10 当前任务

- [x] 重新读取当前根 `AGENTS.md`、Skill、05/11/12 reference、Agent prompt、Active Change、PR 和最新 main。
- [x] 发现并修复 `main` 的 0 字节 `README_DO_NOT_USE` 工具污染；用中文提交清理并正常同步最新 main 到当前分支。
- [x] 新增 `tests/unit/test_reliable_vibe_coding_global_language_rules.py`。
- [x] 第一次 Red 尝试只因 Ruff format 失败，没有把它计为需求 Red。
- [x] 第二次 Red 尝试只因 Ruff import-order/blank-line 失败，没有把它计为需求 Red。
- [x] 取得有效 R10 Red：`641 passed / 3 failed`，三个失败分别对应中文 Git 提交、中文代码注释/内部函数说明、中文规则不能委托项目 Overlay。
- [x] 更新 `SKILL.md`：把中文提交、中文注释、内部/private/helper 函数级中文说明写入通用不变量、计划、实现和 Git 章节。
- [x] 更新 `05_development-workflows.md`：统一中文提交/注释，所有 public/internal 函数有函数级说明，复杂内部规则继续解释 why/invariant/risk/compatibility。
- [x] 更新 `11_verification-review.md`：Code Quality 检查所有 public/internal 函数级中文说明，Git Review 检查中文 Commit message。
- [x] 更新 `agents/openai.yaml`：默认 Agent 直接执行三条通用规则。
- [x] 更新 portability regression：AIMA docs governance 仍是 Overlay，而中文提交/注释变为通用规则。
- [x] 更新 `12_rule-preservation-map.md`：保留旧 Overlay 历史、记录 R10 覆盖关系、把中文规则移入通用核心。
- [x] 旧 Skill self-tests 在实现过程中抓到 `内部/private/helper 函数包含非显然业务规则` / `非显然内部/private/helper` 具体措辞丢失；没有删测试，而是恢复具体旧语义并保留更强的新基线。
- [x] 实现候选 `55aae9a0b534e47a910b064c4017c5db39f5045c` 取得 CI/Runtime/Full-stack success，Repository Quality Unit `644 passed`；该候选仍使用 R1-R9 旧 Change 结构，因此只作实现 Green，不作最终 R10 Ready 证据。
- [ ] 重新执行 R1-R10 Completion Audit 与 A1/A2/Code Quality Review。
- [ ] 最终 Ready 前重新 compare 最新 main；必要时正常同步并重跑门禁。
- [ ] 将 R5/R10 清零、Completion Audit 四项完成，并把 Change 重新置 `ready_for_review`。
- [ ] 最终 Change HEAD 必须取得 Change Completion Gate、CI、Runtime、Full-stack 全 success。
- [ ] 机器门禁全部成功后把 PR #222 从 Draft 转 Ready；不自动合并。

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

原通用前身 `development-workflows.md` 还包含“无项目注释语言约定时默认中文”的项目倾向。为了跨项目可移植，新通用 Skill 当时改为“服从目标项目/生态”，但人工 Review 发现：AIMA 根 `AGENTS.md` 已有 `提交信息使用中文`，却没有正式承载原来的中文注释偏好；这会造成 AIMA 行为丢失。

先在旧 portability 回归中增加：

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

`12_rule-preservation-map.md` 同时登记当时的归属迁移。**该迁移历史继续有效，但 R10 后续改变了当前归属：中文规则现在同时存在于通用 Skill 与 AIMA 项目规则中。**

### 第三轮实现 Green 与最终同 HEAD Gate

实现 HEAD `e52c345e691117e30ab6bb4587adbb27e0848eb6` 的 CI `32804091561`：Repository Quality、PostgreSQL Integration、CI Gate 全部 success；Repository Quality 中 Unit `641 passed`、Contract 75、API 34、Frontend Unit 39、Playwright 22、Architecture/Ownership/Secret/Docs/Wheel 全 success。Runtime `32804091564`、Full-stack `32804091579` 也 success。

随后 Change Ready 结构修正后，最终候选 `9049a6b4368cd2217a12dd31942a30f7036d1ee3` 取得：

```text
Change Completion Gate 32804867801 → success
CI 32804867796 → success
Runtime Acceptance 32804867814 → success
Full-stack Acceptance 32804867821 → success
```

该结果曾足以支撑 R1-R9 Ready，但 R10 出现后自动失效为“最终完成证据”，仍保留为前三轮历史。

## 第四轮：中文提交 / 中文注释 / 内部函数注释通用化（R10）

### 两次无效 Red 尝试

第一次新增 `tests/unit/test_reliable_vibe_coding_global_language_rules.py` 后，commit `56334b54098274f3303e72694a1ea0b143960832` 的 CI 在 Unit 前被 Ruff format 拦住，因此目标断言没有运行，不计需求 Red。

修正后第二次尝试在 Unit 前又被 Ruff I001（import 与模块常量之间额外空行）拦住；仍不计需求 Red。两次都只修测试格式，没有提前修改 Skill 实现。

### 有效 R10 Red

commit：

```text
193e40bda3dc15fa78a64b24dd11c9114e30df38
```

CI：

```text
run 32805896442
Repository Quality job 97675878991
```

完整结果：

```text
ruff format --check → 492 files already formatted
ruff check → All checks passed
mypy backend/src → Success: no issues found in 242 source files
uv run pytest tests/unit -q → 641 passed / 3 failed / 1 warning
Secret Scan → success
Docs link check → success
```

三个失败分别是：

1. `SKILL.md` 不包含 `所有 Git 提交信息使用中文`；
2. `SKILL.md` 不包含 `代码注释统一使用中文` / internal helper 函数级中文说明；
3. `12_rule-preservation-map.md` 仍把中文提交/注释归到项目 Overlay，而没有作为通用 Skill 当前规则。

这证明 Red 因 R10 尚未实现而失败，不是格式、类型、环境或无关产品回归。

### R10 实现

实现保持“新要求叠加旧细节”，没有通过删旧规则完成：

- `SKILL.md`：新增通用不变量“中文注释与函数级说明”和“Git 提交信息统一中文”；在计划、实施、Git 部分重复强化；允许专有名词/标识符/协议/库/标准名保留原文；public/exported 与 internal/private/helper 新增/修改函数均需函数级中文说明。
- `05_development-workflows.md`：Git 提交信息统一中文；代码注释统一中文；所有新增/修改 public/internal 函数都有函数级说明；简单函数允许一句话；复杂函数继续解释 why/invariant/risk/compatibility、状态转换和副作用。旧 `内部/private/helper 函数包含非显然业务规则` 具体措辞继续保留。
- `11_verification-review.md`：检查所有新增/修改 public/exported 与 internal/private/helper 的中文函数级说明；另保留 `非显然内部/private/helper` 复杂规则复核；Git Review 明确 `Commit message 必须使用中文`。
- `agents/openai.yaml`：默认 Agent 直接要求 `write Git commit messages in Chinese`、`write code comments in Chinese`、`document internal/private/helper functions`。
- `12_rule-preservation-map.md`：保留第一轮“迁到 Overlay”的历史；新增“R10 后续覆盖旧分类”的现行规则；`应留在通用 Skill` 包含中文提交、中文注释、内部函数级说明；Overlay 仅决定提交格式/注释语法等附加细节。
- `tests/unit/test_reliable_vibe_coding_portability.py`：把原“中文规则应仅属于 AIMA Overlay”的断言改为“AIMA docs governance 仍是 Overlay，而中文规则是 global”；AIMA 根 `AGENTS.md` 仍需保留中文和 PEP 257。
- `tests/unit/test_reliable_vibe_coding_global_language_rules.py`：独立守护通用中文规则及“不委托 Overlay”的边界。

在第一次实现后，Skill 自身 14 个 self-tests 发现两处具体旧措辞被改写：

```text
内部/private/helper 函数包含非显然业务规则
非显然内部/private/helper
```

没有删除或修改旧 self-test；而是在更强的新规则中恢复这两条具体表达，形成：

```text
所有内部/private/helper 函数 → 至少函数级中文职责说明
其中包含非显然业务规则的内部/private/helper → 继续额外解释具体 why/invariant/state/compatibility/side-effect
```

### R10 实现 Green 候选

候选 HEAD：

```text
55aae9a0b534e47a910b064c4017c5db39f5045c
```

同一候选的 Actions：

```text
CI run 32806772123 → success
Runtime Acceptance 32806772073 → success
Full-stack Acceptance 32806772091 → success
Change Completion Gate 32806772097 → success（仅证明当时旧 Change 结构；R10 尚未写入 Traceability，因此不能作为最终 R10 Completion 证据）
```

Repository Quality job `97678368521` 完整日志：

```text
ruff format --check → 492 files already formatted
ruff check → All checks passed
mypy backend/src → Success: no issues found in 242 source files
Unit → 644 passed / 1 warning
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
PostgreSQL Integration → success
```

该 Green 证明实现与旧回归兼容，但本文件此时刚重新把 R10 纳入上游完成定义，因此最终 Ready 仍需新的 Completion Audit、Review 和 Change HEAD 同 HEAD Gate。

# 文档影响

- `references/` 当前规范统一使用 `01_...` 两位数字阅读顺序，但数量不是固定配额。
- `docs/AGENTS.md` 保留 AIMA 两位数字 docs 导航、README 不编号、实时引用迁移和 archive 历史边界，同时明确不预设固定文档数量、文件名、编号上限。
- 根 `AGENTS.md`、Blueprint 06、Blueprint README 按当前实际 `docs/blueprint/` 集合理解核心架构；当前 01—08 继续存在，但不是永久数量制度。
- 根 `AGENTS.md` 继续保留 AIMA 中文提交、中文注释 + Python PEP 257。R10 后，这些条款不再是通用中文规则的唯一承载，而是与通用 Skill 一致的项目强化和 Python 具体规范。
- `SKILL.md`、`05_development-workflows.md`、`11_verification-review.md`、`agents/openai.yaml`、`12_rule-preservation-map.md` 现在共同构成中文提交、中文注释、内部函数级说明的通用规则链。
- `12_rule-preservation-map.md` 明确保留“早期曾归 Overlay”的历史及“R10 覆盖旧分类”的新事实，避免通过删除历史制造看似一致。
- 两个归档 CI Change 仍只迁移实时 Requirement Source 到 `08_testing-strategy.md`，历史 Evidence/Review/结论保持。
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
- **行为约束变化（Skill 用户侧）**：复制/使用本 Skill 的项目现在会受到中文 Git commit message、中文代码注释、所有新增/修改 internal/private/helper 函数级中文说明的通用约束。这是用户明确要求的规则变化，不是隐式兼容副作用。
- 项目可以继续要求 PEP 257、Javadoc、XML docs、特定提交前缀等更具体格式；这些与通用中文规则叠加。
- 前一轮“中文规则只在 AIMA Overlay”不再是当前兼容承诺；其历史被完整保留在 preservation map 和本 Change。
- 回滚：如 Skill 重组出现问题，可整体 revert 本 PR 的 Skill/docs/test/tooling diff；不涉及产品数据回滚、Migration downgrade 或外部 Provider 状态恢复。

# 交付

- Branch：`refactor/reliable-vibe-coding-portable-routing`
- PR：`#222`，仍保持 Draft；R10 新 Completion Audit/Review/final Gate 完成前不得转 Ready
- Current confirmed main after pollution cleanup：`99d830fb3b9d78ec019ff68198b976bf83475a57`
- Latest R10 main sync merge：`a698b46220d5499b59d705f6ffff79ed323d3115`
- Dynamic docs / numbered reference historical Green：`6bc3093164a325e4ef95ef33abf9cff7e94f576c`
- R9 initial Red：`fe2f7a4103de8edb240680541252cd0bf38c6060`
- Logging preservation Red：`a9e91fac058f5cbf6fa1bc8e2a6882441ba39e5d`
- AIMA comment Overlay Red：`53edf9bad63e9eb8f9e28b61ee72521f7938ee1e`
- R1-R9 final historical Ready：`9049a6b4368cd2217a12dd31942a30f7036d1ee3`
- R10 valid Red：`193e40bda3dc15fa78a64b24dd11c9114e30df38`
- R10 implementation Green candidate：`55aae9a0b534e47a910b064c4017c5db39f5045c`
- Final R10 Ready candidate：尚未形成；必须由 Completion Audit/Review 完成后的 Change 更新提交产生
- Merge：未执行，也不在本 Change 中自动执行
- Release / Deploy：不适用
