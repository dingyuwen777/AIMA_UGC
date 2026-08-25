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
  - tests/unit/test_reliable_vibe_coding_portability.py
contracts: []
data_changes: []
---

# 背景与当前事实

当前仓库只有一套 `.agents/skills/reliable-vibe-coding/` Skill。原 Skill 已经包含项目发现、L1-L3 分级、Change 管理、Requirement Traceability、Completion Audit、Red-Green-Refactor、根因调试、分层验证、多人协作、Review、Git 和交付证据等完整机制，但主 `SKILL.md` 同时承担入口、路由、流程正文、AIMA/Web 技术形态示例和交付门禁，容易让可移植规则与当前项目专项规则混在一起。

现有 `testing-strategy.md` 中 Browser Mock、Backend/API/PostgreSQL、Real Full-stack、Real Provider Probe 等内容对 Web/API/数据库/外部 Provider 项目有直接价值，因此本次没有删除、改名或压缩该专项策略；通用层只负责判断这些专项规则什么时候适用。CLI、Library、Mobile、Embedded、Data、Infra 等项目则根据真实边界选择对应验证，而不是为了满足模板制造 Browser/PostgreSQL/Provider 层。

本次只重组 Skill 和其开发工具，不改变 AIMA 产品 API、Schema、Migration、运行时、业务行为或 CI 风险层。

任务开始基线为 `main` 的 `e8f974b6679a6e2ef8382324196d70311ec12b3a`。开发过程中 `main` 前进并归档了已完成的 `CHG-20260825-ci-long-term-risk-layers`；当前分支已正常同步最新主分支基线 `9b6457d3549dea57f85d52bf664227b47791b9b4`，同步后重新检查了本 Change 的上游 Source 与最终 diff，没有把旧 HEAD 的验证直接套用到新 HEAD。

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
- [x] 新增自动化回归测试，验证四维路由、Agent 默认执行提示、多语言 profile/Manifest 发现、通用验证层、关键旧规则可达、AIMA 项目 Overlay 与旧 Web/PostgreSQL/Provider 专项策略仍存在。
- [x] 已取得正确 Red、实现后的 Repository Quality Green、旧 Skill 自测 Green 和内容守恒人工 Review；本 `ready_for_review` 候选提交继续由 Change Completion Gate/Ready Check 验证，若机器门禁失败则不进入合并。

# 范围

- 重组 `.agents/skills/reliable-vibe-coding/SKILL.md` 的入口、任务路由和统一流程组织。
- 新增跨项目/阶段/语言/通用验证参考文件及规则保留映射。
- 调整 `change-management.md`、`completion-gate.md`、`development-workflows.md`、`verification-review.md` 和 `CHANGE.template.md`，使通用流程不绑定单一技术栈，同时保留原有细节。
- 保留 `testing-strategy.md` 作为 Web/API/PostgreSQL/Provider 边界的高价值专项策略，并从通用验证策略明确路由到它。
- 增加仓库级 Unit 回归测试验证 Skill 结构和关键规则可达性。
- 扩充 `rvc.py` 对常见多语言 Manifest/Workspace 的只读发现能力，但不改变缓存/Change schema、Change 解析、冲突检测或 CLI 协议。
- 更新 `agents/openai.yaml`，要求 Agent 先完成四维路由并读取所有命中的 reference 后再执行任务。

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
- AIMA 项目本地规则继续由 `AGENTS.md`、Blueprint、Contract、Migration、locks、tests 和 CI 承载；通用 Skill 只负责发现并服从这些 Overlay。

# 关键决策

1. 采用“核心流程 + 条件式 profiles/路由”而不是为每种语言复制一套 Skill，避免多份 TDD/Git/Review/Change 规则长期漂移。
2. 现有 Web/API/PostgreSQL/Provider 测试策略保留为专项 profile；通用层只抽象风险与证据职责，不弱化原有测试边界。
3. 本次不迁移 `rvc.py` 的缓存协议；只扩展 Manifest/Workspace 发现表面，保持 `rvc-project-context/v1` 与 `rvc-change/v1` 不变。
4. 原规则只允许移动、分类或消除完全等价重复；不能因缩短主 `SKILL.md` 删除约束。`rule-preservation-map.md` 与 portability regression 共同作为后续重组的内容守恒门禁。
5. AIMA 自身 PostgreSQL、Blueprint 编号、中文 Git 提交等项目约束继续由 `AGENTS.md` / Blueprint 承载；通用 Skill 明确项目 Overlay 优先级，不把这些专项事实强加给其他仓库。
6. `testing-strategy.md`、`project-discovery.md`、`repository-constraints.md`、`collaboration.md` 不做无必要改写；对通用化必须触及的 reference 才做语义迁移。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Skill 必须适用于不同项目、不同研发阶段、不同编程语言 | user:2026-08-25-portable-skill | satisfied | `task-routing.md` 建立项目形态 × 研发阶段 × 编程语言/工具链 × L1-L3 四维路由；`language-and-toolchain-profiles.md` 覆盖主要生态并给未列语言回退算法；`validation-strategy.md` 使用技术栈无关证据维度；`rvc.py` 多语言 Manifest 回归已经经历正确 Red/Green |
| R2 | 重新组织现有 Skill，使大模型能严格按 Skill 中规定流程工作 | user:2026-08-25-portable-skill | satisfied | 主 `SKILL.md` 将“先四维路由、命中 reference 必须读取、再工作”设为强制入口，保留 L1-L3、Change、Traceability、TDD、根因调试、Review、Ready、Git 和新鲜证据硬门禁；`agents/openai.yaml` 默认提示同时要求四维路由、读取所有命中 reference 和完成 fresh-evidence gate，portability tests 对这些执行入口做自动断言 |
| R3 | 不丢失任何现有内容和有价值细节，不做过度总结 | user:2026-08-25-preserve-skill-details | satisfied | `rule-preservation-map.md` 逐项映射原 13 条不变量、工作流 1—11 和 8 个旧 reference；`testing-strategy.md`、`project-discovery.md`、`repository-constraints.md`、`collaboration.md` 保持原 SHA/原路径；旧 Skill 自测曾实际发现“内部/private/helper 函数”措辞收缩，修正后当前旧 Skill 自测 14/14 通过，证明回归门禁能捕获此类内容损失；AIMA 文档编号/中文提交等专项规则明确留在项目 Overlay |
| R4 | 不从仓库历史或聊天猜实现，按当前 AGENTS 与真实仓库事实工作 | AGENTS.md | satisfied | 任务从当前 `AGENTS.md`、Skill/references/测试和真实 GitHub HEAD 恢复事实；main 前进后重新检查来源、同步最新 `9b6457d3549dea57f85d52bf664227b47791b9b4` 并在同步后的 `8b898d4656495cbc83775f6a750f6be852fcdcb9` 重新运行 Repository Quality，没有复用失效 HEAD 结论 |
| R5 | L2 变更维护 Change、Validation Matrix、Completion Audit 和新鲜证据 | .agents/skills/reliable-vibe-coding/references/change-management.md | satisfied | 本 Change 从 `in_progress` 持续维护到本轮 `ready_for_review`；Validation Matrix 的产品层均有明确不适用依据，Docs/Governance/Other 有 Red、Repository Quality、旧 Skill self-tests、差异审计和内容守恒 Review 证据；Completion Audit 与两阶段 Review 已完成，本候选提交继续接受机器 Ready Check/CI，机器失败则不得合并 |
| R6 | 已完成 CI Change 对 `testing-strategy.md` 的 Requirement Source 不得因本次重组失效 | changes/archive/2026-08/CHG-20260825-ci-long-term-risk-layers/CHANGE.md | satisfied | `testing-strategy.md` 路径和专项语义完整保留，当前 SHA 仍为 `242ebc1e0f255e4427fe87ed1f6bbc6cc9a025e6`；归档 CI Change 的 Source 路径继续存在且可解析 |

# Validation Matrix

本 Change 运行在 AIMA 仓库，沿用该 Change 创建时的专项 testing profile 记录；新 `CHANGE.template.md` 已改为技术栈无关的八个语义维度，Web/API/PostgreSQL/Provider 仅在真实存在时再映射到原专项层。

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 本次不改变前端产品行为、路由、请求或用户页面，Browser 层没有独立风险需要证明 |
| Backend/API/PostgreSQL Integration | not_applicable | 本次不改变后端业务模块、数据库、Migration、Job/Worker 或持久化行为；`rvc.py` 只扩展仓库文件分类，不访问产品数据库/runtime |
| Contract / Generated Client | not_applicable | 不修改产品 Pydantic/OpenAPI/generated client、Canonical、Job Payload 或其他产品 Contract |
| Real Full-stack Golden Path | not_applicable | 不改变跨前后端真实产品接线；仓库 Full-stack CI 即使运行也只作为无回归辅助，不作为本 Change 主证据 |
| Real Provider Probe | not_applicable | 不修改 Provider endpoint、参数、字段、分页、capability 或 pricing，不需要真实付费/外部 Probe |
| Docs / Governance / Other | required | `tests/unit/test_reliable_vibe_coding_portability.py` 覆盖四维路由、Agent 执行提示、语言 profile、Manifest 分类、通用验证、旧规则可达和 AIMA Overlay；旧 Skill self-tests 14/14 通过；实现 HEAD `8b898d4656495cbc83775f6a750f6be852fcdcb9` 的 Repository Quality job `97648417603` 成功，Ruff、format、Secret、Schema/OpenAPI、Architecture、Error Contracts、Table Ownership、Logging Boundaries、Docs、Frontend API Usage、mypy、Unit Tests 全部成功；最终 candidate Ready commit 再由 Change Completion Gate 验证 |

# Completion Audit

- [x] upstream_re_read：已在同步最新 main 后重新读取用户两轮要求、`AGENTS.md`、当前 `SKILL.md`、四个新增通用 reference、被修改的 Change/Completion/Workflow/Review、原专项 `testing-strategy.md`、模板和相关测试，独立重建“跨项目/阶段/语言且不丢规则”的完成定义。
- [x] change_coverage：已从用户要求和原 Skill 反向逐项检查；四维通用化、严格执行入口、内容守恒、专项策略保留、项目 Overlay、Change/验证/Review 均进入当前 Change，没有发现新的 requirement omission。
- [x] reverse_audit：从 Library、CLI、Service、Frontend/Full-stack、Mobile/Desktop、Data/ML、Embedded、Infra/IaC、Monorepo 等项目形态以及 Onboarding、Design、Feature、Bug、Refactor、Review、Release、Maintenance/Security 等阶段反查路由；再从原 Browser/PostgreSQL/Provider 专项规则反查仍能由 generic profile 条件式进入；从 AIMA 反查中文提交、Blueprint 编号、PostgreSQL 等项目约束仍由项目 Overlay 承载。
- [x] unresolved_cleared：R1-R6 均已有实现/证据；所有 Validation Matrix 不适用项都有当前 diff/产品边界依据，没有通过缩小测试范围规避独立风险。

# 两阶段 Review

## Review A1：上游要求 → Change

- 用户要求的三条核心完成定义已经独立重建并覆盖：跨项目/阶段/语言、严格按流程执行、不丢失细节。
- `AGENTS.md` 对 AIMA 当前事实优先、L2/Change/Completion Gate、项目本地技术边界和 Git/CI 的要求均未被通用化覆盖掉。
- 原 Skill 13 条不变量、统一工作流、TDD/根因调试、Git/依赖/安全、注释/日志、文档同步、Validation、Review/交付规则均能从新入口或 preservation map 导航到规范承载。
- 没有以当前 Change checklist、CI 绿色或历史聊天代替上游需求全集。

## Review A2：Change → 实现 / 测试 / 文档

- 四维路由由 `SKILL.md` + `task-routing.md` 实现；语言工具链由 `language-and-toolchain-profiles.md` 实现；验证抽象由 `validation-strategy.md` 实现；规则迁移审计由 `rule-preservation-map.md` 实现。
- Change/Completion/Workflow/Review/template 已切换到通用语义，同时 `testing-strategy.md` 原专项事实保持不变。
- `rvc.py` 最终差异只增加 Manifest 名称/后缀分类，早期一次过大的整文件 rewrite 已在差异审查中发现并恢复；缓存 schema、Change schema、Change parser、冲突检测和 CLI 行为没有被本次通用化顺手重写。
- 产品 API/Schema/Migration/前端/依赖锁没有变化，因此对应产品测试层不适用；治理/工具变更由 root portability tests、旧 Skill self-tests 和 Repository Quality 覆盖。

## Code Quality Review

- 没有引入新的依赖、Runtime、包管理器或锁文件变化。
- 多语言 profile 中的命令明确只是候选导航，不会把示例命令冒充仓库真实命令。
- 未列语言有统一回退算法，不需要为每个未来语言复制 Skill。
- generic Validation Matrix 以“风险 → 证据”而不是固定测试配额组织，避免把 Browser/PostgreSQL 强加给无关项目，同时没有降低原专项验证责任。
- `rvc.py` 的多语言扩展是静态 Manifest 分类，没有网络、Secret、生产 I/O 或新的安全边界。
- 没有发现严重/重要的正确性、安全、兼容或维护性问题；本轮没有无关产品代码重构。

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
- [x] 在同步最新 main 后重新执行 Repository Quality，job `97648417603` 成功
- [x] 完成 Requirement Traceability、Completion Audit 和两阶段 Review
- [x] 将本 Change 置为候选 `ready_for_review`，由当前提交的 Change Completion Gate/Ready Check 作最后机器验证；机器失败则保持 PR 不可合并并继续修正

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

### 当前实现 HEAD Repository Quality

在同步最新 main 后的实现 HEAD `8b898d4656495cbc83775f6a750f6be852fcdcb9`，CI run `32796364979`，Repository Quality job `97648417603` 为 success。以下步骤全部成功：

```text
Ruff
Ruff format
Secret Scan
Canonical JSON Schema
Job JSON Schema
OpenAPI
Data Entity Names
Architecture
Error Contracts
Table Ownership
Logging Boundaries
Docs
Frontend API Usage
mypy
Unit Tests
```

这里不虚构 Unit 的精确通过数量；GitHub 当前高层 job 结果只足以确认 Unit Tests step 成功。

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

### `rvc.py` 差异控制

曾出现一次 Contents API 整文件替换导致 `rvc.py` diff 远大于目标范围。差异复核发现后，立即恢复 `main` 原实现，只重新叠加最小 Manifest/后缀分类；恢复后的比较中 `rvc.py` 仅保留多语言发现相关差异，没有顺带修改 cache/Change/parser/conflict/CLI 逻辑。

## Candidate Ready 机器门禁

本次文件更新把 Change 从 `in_progress` 置为 `ready_for_review`，目的就是让当前提交实际执行：

```text
python .agents/skills/reliable-vibe-coding/scripts/ready_check.py --root . --require-active-ready
```

以及 PR 的 Changed Change Completion Gate。只有该候选提交的机器门禁成功后，PR 才能被描述为满足 Ready 门禁；若失败，按原始错误继续修正，不修改/降低门禁。

## 本地验证限制

尝试在本地容器获取仓库用于额外运行 Skill 自测时，环境无法解析 `github.com`，因此没有把本地容器执行虚构成验证证据。当前可执行验证以 GitHub Runner 的本轮当前 HEAD 证据为准。

# 文档影响

- 本次主要交付物就是 Skill 的规范文档、Change 模板、Agent 默认执行提示和规则保留映射。
- AIMA 产品 Blueprint、模块 README、HTTP/Canonical Contract、数据库文档不受产品行为影响，因此不制造这些文档的无关差异。
- 原主 Skill 中属于 AIMA 项目自己的文档编号、Blueprint 01—08、中文 Git 提交、PostgreSQL 等约束没有被删除；它们由 `AGENTS.md`、`docs/blueprint/06_开发约束与分阶段实施.md`、Blueprint/locks/Contract 等正式项目事实继续承载，`rule-preservation-map.md` 明确记录迁移归属。
- `testing-strategy.md` 继续作为 AIMA Web/API/PostgreSQL/Provider 的专项验证事实源，不因新增 generic validation 而变成历史文件。

# 兼容性、依赖、Migration、部署与回滚

- Public product API / Contract：无变化。
- Database Schema / Migration：无变化。
- 产品数据：无变化。
- 依赖 / Lock：无变化。
- Runtime / Deployment：无变化。
- Skill cache schema：`rvc-project-context/v1` 不变。
- Change schema：`rvc-change/v1` 不变。
- 回滚：如果通用化入口出现问题，可以按本 PR 的 Skill/测试/tooling diff 整体回滚；不涉及产品数据回滚或 Migration downgrade。

# 交付

- Branch：`refactor/reliable-vibe-coding-portable-routing`
- Draft PR：`#222`，在最终机器门禁成功前保持 Draft/不可声称可合并
- Implementation HEAD evidence：`8b898d4656495cbc83775f6a750f6be852fcdcb9` Repository Quality success
- Candidate Ready commit：由本次 Change 更新产生，等待同一提交的新鲜 Change Completion Gate/CI 结果
- Merge：未执行
- Release / Deploy：不适用
