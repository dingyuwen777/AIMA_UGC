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
  - docs/AGENTS.md
  - tests/unit/test_reliable_vibe_coding_portability.py
contracts: []
data_changes: []
---

# 背景与当前事实

当前仓库只有一套 `.agents/skills/reliable-vibe-coding/` Skill。原 Skill 已经包含项目发现、L1-L3 分级、Change 管理、Requirement Traceability、Completion Audit、Red-Green-Refactor、根因调试、分层验证、多人协作、Review、Git 和交付证据等完整机制，但主 `SKILL.md` 同时承担入口、路由、流程正文、AIMA/Web 技术形态示例和交付门禁，容易让可移植规则与当前项目专项规则混在一起。

现有 `testing-strategy.md` 中 Browser Mock、Backend/API/PostgreSQL、Real Full-stack、Real Provider Probe 等内容对 Web/API/数据库/外部 Provider 项目有直接价值，因此本次没有删除、改名或压缩该专项策略；通用层只负责判断这些专项规则什么时候适用。CLI、Library、Mobile、Embedded、Data、Infra 等项目则根据真实边界选择对应验证，而不是为了满足模板制造 Browser/PostgreSQL/Provider 层。

本次只重组 Skill 和其开发工具，不改变 AIMA 产品 API、Schema、Migration、运行时、业务行为或 CI 风险层。

任务开始基线为 `main` 的 `e8f974b6679a6e2ef8382324196d70311ec12b3a`。开发过程中 `main` 前进并归档了已完成的 `CHG-20260825-ci-long-term-risk-layers`；当前分支已正常同步最新主分支基线 `9b6457d3549dea57f85d52bf664227b47791b9b4`，同步后重新检查了本 Change 的上游 Source 与最终 diff，没有把旧 HEAD 的验证直接套用到新 HEAD。Ready 收尾前再次比较 `main...refactor/reliable-vibe-coding-portable-routing`，结果为 `behind_by: 0`。

# 目标

把 Reliable Vibe Coding 重组为一个可以复制到不同项目使用的通用研发 Skill，并让 Agent 在执行前先按四个互相独立的维度路由：

```text
项目形态
× 研发阶段 / 任务类型
× 编程语言 / 工具链
× 风险等级 L1-L3
→ 选择最少但充分的规则、验证和交付门禁
```

核心流程保持稳定；项目、阶段、语言和验证细节按真实仓库事实条件式加载。现有有价值规则和专项细节全部保留，不因“精简”而删除。

# 成功标准

- [x] `SKILL.md` 形成清晰的强制入口与四维任务路由，明确先识别项目事实，再选择阶段、工具链、风险规则和验证，而不是默认 Web/Python/PostgreSQL。
- [x] 新增项目/研发阶段路由参考，覆盖首次接入、需求/设计、实现、Bug/调试、重构、Review、发布/运维、维护/迁移、安全/不可逆操作等阶段，并明确各阶段应加载哪些现有规则。
- [x] 新增编程语言与工具链适配参考，覆盖 Python、JavaScript/TypeScript、Go、Rust、Java/Kotlin、.NET、C/C++、Swift、Dart/Flutter、PHP、Ruby、Elixir，以及多语言/Monorepo、Container/IaC，并提供未列语言的统一发现算法；没有硬编码版本或擅自更换包管理器。
- [x] 新增通用 Validation Matrix，把验证抽象为行为、接口、真实依赖集成、用户/调用者工作流、跨组件 Golden Path、外部依赖 Probe、Build/Package/Runtime、Docs/Governance 等风险维度；现有 Browser/PostgreSQL/Provider 细节保留为条件式专项 profile。
- [x] `CHANGE.template.md` 不再要求所有项目机械使用 Browser/PostgreSQL/Provider 行名，同时保留这些专项层的语义映射和适用条件。
- [x] 建立 `rule-preservation-map.md`，逐项登记原主 Skill 的 13 条不变量、统一工作流 1—11、8 个旧 reference、TDD、根因调试、Git/依赖/安全、注释、可观测性、文档同步和专项测试职责，明确通用核心、条件式专项和项目本地 Overlay 的归属。
- [x] 保持 `project-discovery.md`、`repository-constraints.md`、`collaboration.md`、`testing-strategy.md` 原路径和原内容；对必须通用化改写的 `change-management.md`、`completion-gate.md`、`development-workflows.md`、`verification-review.md` 按 preservation map 逐项保留原职责和硬门禁。
- [x] 原主 Skill 中属于 AIMA 项目的文档编号规则没有因通用化丢失：已迁入 `docs/AGENTS.md` 项目 Overlay，并由 portability regression 直接验证编号、README、Blueprint 01—08、重命名实时引用和历史归档边界。
- [x] 新增自动化回归测试，验证四维路由、Agent 默认执行提示、多语言 profile/Manifest 发现、通用验证层、关键旧规则可达、AIMA 项目 Overlay 与旧 Web/PostgreSQL/Provider 专项策略仍存在。
- [x] 已取得正确 Red、实现后的完整 Repository Quality/CI Green、旧 Skill 自测 Green 和内容守恒人工 Review；最终 `ready_for_review` HEAD 继续由 Change Completion Gate/Ready Check 和 CI 验证，若机器门禁失败则不进入合并。

# 范围

- 重组 `.agents/skills/reliable-vibe-coding/SKILL.md` 的入口、任务路由和统一流程组织。
- 新增跨项目/阶段/语言/通用验证参考文件及规则保留映射。
- 调整 `change-management.md`、`completion-gate.md`、`development-workflows.md`、`verification-review.md` 和 `CHANGE.template.md`，使通用流程不绑定单一技术栈，同时保留原有细节。
- 保留 `testing-strategy.md` 作为 Web/API/PostgreSQL/Provider 边界的高价值专项策略，并从通用验证策略明确路由到它。
- 增加仓库级 Unit 回归测试验证 Skill 结构和关键规则可达性。
- 扩充 `rvc.py` 对常见多语言 Manifest/Workspace 的只读发现能力，但不改变缓存/Change schema、Change 解析、冲突检测或 CLI 协议。
- 更新 `agents/openai.yaml`，要求 Agent 先完成四维路由并读取所有命中的 reference 后再执行任务。
- 新增 `docs/AGENTS.md`，承载从通用 Skill 移出的 AIMA 文档树项目本地规则，避免“通用化”变成项目知识删除。

# 非目标

- 不修改 AIMA 产品代码、HTTP/Canonical Contract、数据库 Schema/Migration、前端功能或运行时。
- 不修改当前 CI Workflow 架构，不新增平行 CI Workflow。
- 不删除现有 references 中仍有效的细节，不把硬规则压缩成抽象口号。
- 不为所有语言制定一套固定测试框架、目录结构、包管理器、格式化工具或版本。
- 不自动升级任何语言、运行时、依赖、Action、镜像或锁文件。
- 不把 AIMA 的 PostgreSQL、Vue/FastAPI、Blueprint 编号、中文 Git 提交等当前项目选择提升为所有项目的全球默认。

# 必须保持不变

- 系统/开发者/用户/仓库 `AGENTS.md` 等高优先级规则始终高于通用 Skill。
- 仓库事实、锁文件、真实命令、当前实现和本轮新鲜验证证据优先，不从聊天或缓存猜实现。
- L1/L2/L3 分级、L2/L3 Change、Requirement Traceability、Completion Audit、两阶段 Review、Red-Green-Refactor、根因调试、最小兼容实现、并行冲突检查、文档同步和 Git 安全边界不降低。
- `testing-strategy.md` 路径与 Browser Mock / Backend/API/PostgreSQL / Contract / Real Full-stack / Real Provider Probe 的详细语义保留，避免破坏归档 Change 的 Requirement Source 和现有专项测试治理。
- `.reliable-vibe-coding/project-context.json`、`rvc-project-context/v1`、`rvc-change/v1` 和 `rvc.py` 既有缓存/Change 协议不做破坏性格式迁移。
- AIMA 项目本地规则继续由根/嵌套 `AGENTS.md`、Blueprint、Contract、Migration、locks、tests 和 CI 承载；通用 Skill 只负责发现并服从这些 Overlay。

# 关键决策

1. 采用“核心流程 + 条件式 profiles/路由”而不是为每种语言复制一套 Skill，避免多份 TDD/Git/Review/Change 规则长期漂移。
2. 现有 Web/API/PostgreSQL/Provider 测试策略保留为专项 profile；通用层只抽象风险与证据职责，不弱化原有测试边界。
3. 本次不迁移 `rvc.py` 的缓存协议；只扩展 Manifest/Workspace 发现表面，保持 `rvc-project-context/v1` 与 `rvc-change/v1` 不变。
4. 原规则只允许移动、分类或消除完全等价重复；不能因缩短主 `SKILL.md` 删除约束。`rule-preservation-map.md` 与 portability regression 共同作为后续重组的内容守恒门禁。
5. AIMA 自身 PostgreSQL、Blueprint 编号、中文 Git 提交等项目约束继续由项目 Overlay 承载；通用 Skill 明确项目 Overlay 优先级，不把这些专项事实强加给其他仓库。
6. `testing-strategy.md`、`project-discovery.md`、`repository-constraints.md`、`collaboration.md` 不做无必要改写；对通用化必须触及的 reference 才做语义迁移。
7. 对原 Skill 中嵌入的 AIMA `docs/` 编号细节，不采用“只在 preservation map 记住”的弱承载；新增 `docs/AGENTS.md` 让目标路径上的 Agent 自动读取并强制执行完整项目规则。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Skill 必须适用于不同项目、不同研发阶段、不同编程语言 | user:2026-08-25-portable-skill | satisfied | `task-routing.md` 建立项目形态 × 研发阶段 × 编程语言/工具链 × L1-L3 四维路由；`language-and-toolchain-profiles.md` 覆盖主要生态并给未列语言回退算法；`validation-strategy.md` 使用技术栈无关证据维度；`rvc.py` 多语言 Manifest 回归经历正确 Red/Green；当前 CI Unit 637 项全部通过 |
| R2 | 重新组织现有 Skill，使大模型能严格按 Skill 中规定流程工作 | user:2026-08-25-portable-skill | satisfied | 主 `SKILL.md` 将“先四维路由、命中 reference 必须读取、再工作”设为强制入口，保留 L1-L3、Change、Traceability、TDD、根因调试、Review、Ready、Git 和新鲜证据硬门禁；`agents/openai.yaml` 默认提示同时要求四维路由、读取所有命中 reference 和完成 fresh-evidence gate，portability tests 对这些执行入口做自动断言 |
| R3 | 不丢失任何现有内容和有价值细节，不做过度总结 | user:2026-08-25-preserve-skill-details | satisfied | `rule-preservation-map.md` 逐项映射原 13 条不变量、工作流 1—11 和 8 个旧 reference；`testing-strategy.md`、`project-discovery.md`、`repository-constraints.md`、`collaboration.md` 保持原 SHA/原路径；旧 Skill 自测曾实际发现“内部/private/helper 函数”措辞收缩并修复；内容守恒 Review 又发现 AIMA docs 编号细节承载不足，随后补 `docs/AGENTS.md` 并将完整规则纳入自动回归，没有把项目专项知识只留在审计清单中 |
| R4 | 不从仓库历史或聊天猜实现，按当前 AGENTS 与真实仓库事实工作 | AGENTS.md | satisfied | 任务从当前 `AGENTS.md`、Skill/references/测试和真实 GitHub HEAD 恢复事实；main 前进后重新检查来源并同步 `9b6457d3549dea57f85d52bf664227b47791b9b4`；Ready 收尾前再次比较当前分支与 main 为 `behind_by: 0`，没有复用失效 HEAD 结论 |
| R5 | L2 变更维护 Change、Validation Matrix、Completion Audit 和新鲜证据 | .agents/skills/reliable-vibe-coding/references/change-management.md | satisfied | 本 Change 从 `in_progress` 持续维护到 `ready_for_review`；Validation Matrix 的产品层均有明确不适用依据；Docs/Governance/Other 有正确 Red、当前完整 CI Green、旧 Skill self-tests、差异审计和内容守恒 Review；Completion Audit 与两阶段 Review 已完成，最终 HEAD 继续接受机器 Ready Check/CI，机器失败则不得合并 |
| R6 | 已完成 CI Change 对 `testing-strategy.md` 的 Requirement Source 不得因本次重组失效 | changes/archive/2026-08/CHG-20260825-ci-long-term-risk-layers/CHANGE.md | satisfied | `testing-strategy.md` 路径和专项语义完整保留，当前 SHA 仍为 `242ebc1e0f255e4427fe87ed1f6bbc6cc9a025e6`；归档 CI Change 的 Source 路径继续存在且可解析 |

# Validation Matrix

本 Change 运行在 AIMA 仓库，沿用该 Change 创建时的专项 testing profile 记录；新 `CHANGE.template.md` 已改为技术栈无关的八个语义维度，Web/API/PostgreSQL/Provider 仅在真实存在时再映射到原专项层。

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 本次不改变前端产品行为、路由、请求或用户页面，Browser 层没有独立产品风险需要证明；AIMA 现有 Playwright 22 项在当前 CI 中仍全部通过，只作为无回归辅助证据 |
| Backend/API/PostgreSQL Integration | not_applicable | 本次不改变后端业务模块、数据库、Migration、Job/Worker 或持久化行为；`rvc.py` 只扩展仓库文件分类，不访问产品数据库/runtime；当前 PostgreSQL Integration job 全部成功作为无回归辅助证据 |
| Contract / Generated Client | not_applicable | 不修改产品 Pydantic/OpenAPI/generated client、Canonical、Job Payload 或其他产品 Contract；当前 Contract 75 项和 generated drift 检查仍成功作为无回归辅助证据 |
| Real Full-stack Golden Path | not_applicable | 不改变跨前后端真实产品接线；Full-stack Acceptance run `32796805631` 成功，只作为无回归辅助证据，不替代本 Change 主验证 |
| Real Provider Probe | not_applicable | 不修改 Provider endpoint、参数、字段、分页、capability 或 pricing，不需要真实付费/外部 Probe |
| Docs / Governance / Other | required | 当前实现 HEAD `bd39ea362b4df32f71182c0ba82ea2dbbc83e2e1`：CI run `32796805697` 的 Repository Quality、PostgreSQL Integration、CI Gate 均 success；Ruff/format 全通过，mypy 242 source files 无问题，Unit `637 passed`，Contract `75 passed`，API `34 passed`，Architecture/Ownership/Secret/Docs/Wheel 全通过，Frontend Unit `39 passed`、Playwright `22 passed`；Runtime Acceptance run `32796805652`、Full-stack run `32796805631`、Change Completion Gate run `32796805658` 均 success；旧 Skill self-tests 14/14 通过；最终 Change-only HEAD 再取得新的 Ready/CI 机器证据后才可把 PR 转 Ready |

# Completion Audit

- [x] upstream_re_read：已在同步最新 main 后重新读取用户两轮要求、根 `AGENTS.md`、当前 `SKILL.md`、四个新增通用 reference、被修改的 Change/Completion/Workflow/Review、原专项 `testing-strategy.md`、模板和相关测试；发现 docs 项目 Overlay 新增后又读取 `docs/AGENTS.md`，独立重建“跨项目/阶段/语言且不丢规则”的完成定义。
- [x] change_coverage：已从用户要求和原 Skill 反向逐项检查；四维通用化、严格执行入口、内容守恒、专项策略保留、项目 Overlay、Change/验证/Review 均进入当前 Change；AIMA docs 编号细节最初承载不足的问题已在 Audit 中发现并补齐，没有遗留 requirement omission。
- [x] reverse_audit：从 Library、CLI、Service、Frontend/Full-stack、Mobile/Desktop、Data/ML、Embedded、Infra/IaC、Monorepo 等项目形态以及 Onboarding、Design、Feature、Bug、Refactor、Review、Release、Maintenance/Security 等阶段反查路由；再从原 Browser/PostgreSQL/Provider 专项规则反查仍能由 generic profile 条件式进入；从 AIMA 反查中文提交、Blueprint 01—08、PostgreSQL 和 docs 编号/重命名/历史归档规则均由根或嵌套项目 Overlay 承载。
- [x] unresolved_cleared：R1-R6 均已有实现/证据；所有 Validation Matrix 不适用项都有当前 diff/产品边界依据，没有通过缩小测试范围规避独立风险。

# 两阶段 Review

## Review A1：上游要求 → Change

- 用户要求的三条核心完成定义已经独立重建并覆盖：跨项目/阶段/语言、严格按流程执行、不丢失细节。
- 根 `AGENTS.md` 对 AIMA 当前事实优先、L2/Change/Completion Gate、项目本地技术边界和 Git/CI 的要求均未被通用化覆盖掉。
- 原 Skill 13 条不变量、统一工作流、TDD/根因调试、Git/依赖/安全、注释/日志、文档同步、Validation、Review/交付规则均能从新入口或 preservation map 导航到规范承载。
- 对原 Skill 中混入的 AIMA docs 命名细节进行了单独内容守恒审计；最终由 `docs/AGENTS.md` 正式承载，而不是把它们删除或强加给其他项目。
- 没有以当前 Change checklist、CI 绿色或历史聊天代替上游需求全集。

## Review A2：Change → 实现 / 测试 / 文档

- 四维路由由 `SKILL.md` + `task-routing.md` 实现；语言工具链由 `language-and-toolchain-profiles.md` 实现；验证抽象由 `validation-strategy.md` 实现；规则迁移审计由 `rule-preservation-map.md` 实现。
- Change/Completion/Workflow/Review/template 已切换到通用语义，同时 `testing-strategy.md` 原专项事实保持不变。
- `rvc.py` 最终差异只增加 Manifest 名称/后缀分类，早期一次过大的整文件 rewrite 已在差异审查中发现并恢复；缓存 schema、Change schema、Change parser、冲突检测和 CLI 行为没有被本次通用化顺手重写。
- `docs/AGENTS.md` 只承载 AIMA docs 树项目规则，并通过 root portability tests 逐条验证；它没有把 AIMA 规则反向写回通用 Skill。
- 产品 API/Schema/Migration/前端/依赖锁没有变化，因此对应产品测试层不适用；治理/工具变更由 portability tests、旧 Skill self-tests 和 Repository Quality 覆盖。

## Code Quality Review

- 没有引入新的依赖、Runtime、包管理器或锁文件变化。
- 多语言 profile 中的命令明确只是候选导航，不会把示例命令冒充仓库真实命令。
- 未列语言有统一回退算法，不需要为每个未来语言复制 Skill。
- generic Validation Matrix 以“风险 → 证据”而不是固定测试配额组织，避免把 Browser/PostgreSQL 强加给无关项目，同时没有降低原专项验证责任。
- `rvc.py` 的多语言扩展是静态 Manifest 分类，没有网络、Secret、生产 I/O 或新的安全边界。
- `docs/AGENTS.md` 通过嵌套规则作用域承载项目文档治理，职责明确；并显式说明自身是规则文件、不属于两位数字技术文档编号对象，避免规则自冲突。
- 当前完整 CI 在同步后的实际分支上通过，未发现严重/重要的正确性、安全、兼容或维护性问题；本轮没有无关产品代码重构。

# 任务

- [x] 调查当前 Skill、references、模板、脚本、测试和 AIMA 上游规则
- [x] 检查 Active Change 冲突并确定保留 `testing-strategy.md` 路径
- [x] 建立 Skill 通用性/规则保留回归测试并取得正确结构 Red：`628 passed / 5 failed`，5 个失败均对应缺少本 Change 目标
- [x] 新增四维任务路由与编程语言/工具链 profile
- [x] 新增通用 Validation Matrix 规则
- [x] 重组主 `SKILL.md`，保持关键硬门禁在入口层可见
- [x] 调整 Change/Completion/template/Review/Workflow 的技术栈中立表达
- [x] 建立原规则完整 preservation map
- [x] 为 `rvc.py` 多语言 Manifest 发现建立独立 Red：`633 passed / 1 failed`，唯一失败为 `CMakeLists.txt` 尚未识别为 manifest；随后最小实现分类扩展
- [x] 修复历史 Skill 自测发现的规则措辞收缩并确认当前旧 Skill 自测 14/14 通过
- [x] 内容守恒 Review 发现 AIMA docs 编号细节正式承载不足后，新增 `docs/AGENTS.md` 并加强项目 Overlay 回归
- [x] 在同步最新 main 后重新执行完整 CI；当前实现 HEAD 的 Repository Quality、PostgreSQL Integration、CI Gate、Runtime、Full-stack、Change Completion Gate 均成功
- [x] 完成 Requirement Traceability、Completion Audit 和两阶段 Review
- [x] 将本 Change 置为 `ready_for_review`；最终 Change-only HEAD 继续由新的 Change Completion Gate/CI 作最后机器验证，机器失败则保持 PR Draft 并继续修正

# 验证

## Red 证据

### 结构通用化 Red

提交 `b82004c6871ca9b92801f9c89605585cec83f851`：

```text
Ruff / format / mypy
→ 通过

uv run pytest tests/unit -q
→ 628 passed / 5 failed
```

5 个失败均落到本 Change 目标：主 Skill 缺少四维路由、语言 profile 不存在、通用 Validation Matrix 不存在、rule preservation map 不存在、Change 模板仍绑定旧专项层。旧 `testing-strategy.md` 的专项规则保留断言在该 Red 中已经通过。

### 多语言项目发现 Red

提交 `1c282d4667415d6e581325bbfc8f4c115b23f131`，CI run `32795417184`，Repository Quality job `97645641780`：

```text
Ruff / format / mypy
→ 通过

uv run pytest tests/unit -q
→ 633 passed / 1 failed
```

唯一失败为 `CMakeLists.txt` 被 `_classify_path()` 判为 `None` 而不是 `manifest`。随后只扩展 Manifest 精确名称/项目后缀分类，没有改缓存或 Change 协议。

## Green / 回归证据

### 当前实现 HEAD 完整 CI

实现与内容守恒修正后的 HEAD `bd39ea362b4df32f71182c0ba82ea2dbbc83e2e1`：

```text
CI run: 32796805697
Repository Quality job: 97649687460 → success
PostgreSQL Integration job: 97649687638 → success
CI Gate → success
Runtime Acceptance run: 32796805652 → success
Full-stack Acceptance run: 32796805631 → success
Change Completion Gate run: 32796805658 → success
```

Repository Quality 新鲜结果：

```text
ruff format --check
→ 491 files already formatted

ruff check
→ All checks passed

mypy backend/src
→ Success: no issues found in 242 source files

uv run pytest tests/unit -q
→ 637 passed, 1 warning

uv run pytest tests/contracts -q
→ 75 passed

uv run pytest tests/api -q
→ 34 passed, 1 warning

Architecture / Table Ownership / Secret / Docs
→ success

Wheel build + isolated install/import
→ success, version 0.1.0

Frontend Unit
→ 39 passed

Playwright Browser Mock Acceptance
→ 22 passed
```

PostgreSQL Integration 中 Migration compatibility、Platform、Readiness、Database、Job Runtime、Collection、Content、Ingestion 全部 success。本次没有产品数据库变更，因此这些只作为无回归辅助证据，不把它们错误描述为通用 Skill 语义的主证明。

### 原 Skill 历史自测

当前分支执行：

```text
python -m unittest discover .agents/skills/reliable-vibe-coding/tests -v
```

结果为：

```text
14/14 passed
```

这组旧测试在重组过程中曾真实发现主 `SKILL.md` 把原“内部/private/helper 函数”收缩成“内部/private/helper”的内容守恒问题；修复后重新 14/14 通过，不能把该细节损失静默解释为“等价总结”。

### 内容守恒证据

以下高价值专项 reference 当前保持原路径和原 SHA：

```text
project-discovery.md
07deaa3c8a610017a08c35728bc58fe3da8acd75

repository-constraints.md
095833d9cede1b595aa2e8087a27e94f969b35be

collaboration.md
90f3797f5bc77af32adb642526b6560f46e4cadc

testing-strategy.md
242ebc1e0f255e4427fe87ed1f6bbc6cc9a025e6
```

被通用化改写的 Change/Completion/Workflow/Review 不以“文件仍存在”作为内容守恒证明，而由 `rule-preservation-map.md` 分章节追溯原规则，新 portability tests 再检查关键旧门禁仍在规范运行路径可达。

原主 Skill 中属于 AIMA 的 docs 文件命名规则经过人工反向审计后，最终正式承载在 `docs/AGENTS.md`；portability test 直接检查每个 docs 子目录独立编号、两位数字下划线、README 不编号、按上游依赖排序、Blueprint 01—08 不静默重排、改名同步实时引用、Archive 不改写、Requirement Source 同步和资源/模块 README 例外，避免 preservation map 成为唯一知识载体。

### `rvc.py` 差异控制

曾出现一次 Contents API 整文件替换导致 `rvc.py` diff 远大于目标范围。差异复核发现后，立即恢复 `main` 原实现，只重新叠加最小 Manifest/后缀分类；恢复后的比较中 `rvc.py` 仅保留多语言发现相关差异，没有顺带修改 cache/Change/parser/conflict/CLI 逻辑。

## Final Ready 机器门禁

本文件更新只同步已经取得的完成事实，不再改变 Skill 实现。该更新会产生新的最终 `ready_for_review` HEAD；必须在同一 HEAD 上重新取得：

```text
python .agents/skills/reliable-vibe-coding/scripts/ready_check.py --root . --require-active-ready
```

对应的 Changed Change Completion Gate，以及仓库实际触发的最终 CI。只有这些最终机器门禁成功后，PR #222 才从 Draft 转 Ready；若失败，按原始错误继续修正，不修改/降低门禁。

## 本地验证限制

尝试在本地容器获取仓库用于额外运行 Skill 自测时，环境无法解析 `github.com`，因此没有把本地容器执行虚构成验证证据。当前可执行验证以 GitHub Runner 的本轮当前 HEAD 证据为准。

# 文档影响

- 本次主要交付物就是 Skill 的规范文档、Change 模板、Agent 默认执行提示和规则保留映射。
- 新增 `docs/AGENTS.md` 只承载 AIMA `docs/` 树的项目本地规则：编号、README、Blueprint 01—08、实时引用迁移和历史归档边界；这是把原 Skill 中的项目专项细节迁到正确事实源，不是新增一套与通用 Skill 冲突的规则。
- AIMA 产品 Blueprint、模块 README、HTTP/Canonical Contract、数据库文档不受产品行为影响，因此不制造这些文档的无关差异。
- 原主 Skill 中属于 AIMA 项目的中文 Git 提交、PostgreSQL 等约束没有被删除；它们继续由根 `AGENTS.md`、Blueprint/locks/Contract 等正式项目事实承载，`rule-preservation-map.md` 明确记录归属。
- `testing-strategy.md` 继续作为 AIMA Web/API/PostgreSQL/Provider 的专项验证事实源，不因新增 generic validation 而变成历史文件。

# 兼容性、依赖、Migration、部署与回滚

- Public product API / Contract：无变化。
- Database Schema / Migration：无变化。
- 产品数据：无变化。
- 依赖 / Lock：无变化。
- Runtime / Deployment：无变化。
- Skill cache schema：`rvc-project-context/v1` 不变。
- Change schema：`rvc-change/v1` 不变。
- 回滚：如果通用化入口出现问题，可以按本 PR 的 Skill/测试/tooling/docs Overlay diff 整体回滚；不涉及产品数据回滚或 Migration downgrade。

# 交付

- Branch：`refactor/reliable-vibe-coding-portable-routing`
- Draft PR：`#222`；最终 `ready_for_review` HEAD 的机器门禁成功后转为 Ready，不在本 Change 中提前声称已经合并
- Main sync：当前比较 `behind_by: 0`，base `9b6457d3549dea57f85d52bf664227b47791b9b4`
- Implementation Green HEAD：`bd39ea362b4df32f71182c0ba82ea2dbbc83e2e1`，CI/Runtime/Full-stack/Completion 全绿
- Final Ready HEAD：由本次 Change 事实同步提交产生；必须取得该 HEAD 的最终机器证据
- Merge：未执行
- Release / Deploy：不适用
