# Coding Skill 使用说明

`coding` 用来解决一个核心问题：**怎样把一个软件研发请求，变成可追溯、可验证、能够正常交付的结果。**

它不是某个语言、框架或数据库的固定模板，也不是“自动写代码脚本”。它负责先恢复当前仓库事实，再根据项目形态、任务类型、工具链和风险选择本次真正需要的研发流程。

> 本 README 只说明怎么使用 Coding。正式规则以 [`SKILL.md`](SKILL.md) 和命中的 [`references/`](references/) 为准；不要用 README 替代正式规则。

## 1. 什么时候应该用 Coding

以下任务都适合直接使用 Coding：

- 第一次接手仓库，先恢复当前事实；
- 需求分析和技术方案；
- 功能开发；
- Bug / 故障定位和修复；
- 重构、性能和可维护性修改；
- Code Review / 代码质量审计的仓库事实、风险和权限入口；
- API、数据库、前后端、Worker、CLI 等跨边界集成；
- PR、CI、合并和交付；
- Release、部署、回滚等在当前项目授权范围内的研发工作。

如果仓库存在 [`review`](../review/README.md)，显式 Code Review / Audit 在 Coding 完成事实恢复和四维路由后会进入 Review；普通实现任务在完成前 Review 阶段也会进入 Review。Review 不维护第二套开发规范，而是复用 Coding 规则做独立审查和测试充分性验证。

如果任务主要是**检查、编写或更新技术文档**，应使用 [`docs`](../docs/README.md) 作为文档专业工作流；在 AIMA_UGC 中仍先遵守根 [`AGENTS.md`](../../../AGENTS.md) 的统一仓库入口。

## 2. 为什么不能直接开始改代码

一个仓库里的同一句需求，可能对应完全不同的风险。

例如“改一个字段”：

```text
内部临时变量改名
→ 可能只是低风险 L1

公开 API 字段改名
→ 会影响调用者和兼容性

数据库列改名
→ 还会影响 Migration、历史数据和回滚
```

所以 Coding 的第一步不是猜技术栈，也不是直接生成代码，而是先判断：

```text
当前项目真实是什么形态？
现在要做什么类型的任务？
实际语言、Runtime、Manifest、锁文件和测试工具是什么？
风险是 L1、L2 还是 L3？
哪些接口、数据、配置、用户行为和运行边界会受影响？
```

这就是 Coding 的“四维任务路由”。它的目的不是增加流程，而是避免在错误的项目模型上工作。

## 3. 在 AIMA_UGC 中怎么使用

AIMA_UGC 的统一入口是仓库根目录的 [`AGENTS.md`](../../../AGENTS.md)。正常顺序：

```text
AGENTS.md
→ .agents/skills/coding/SKILL.md
→ 按任务读取命中的 references
→ 读取最少充分的代码 / Contract / Migration / 配置 / 测试 / 文档
→ 开发或完成 Review 前事实恢复
→ 新鲜验证
→ Docs Impact
→ 完成前 Review
→ .agents/skills/review/SKILL.md（仓库存在时）
→ PR / CI / 交付
```

显式 Code Review / Audit 不需要先走一遍“开发”：Coding 完成事实恢复、四维路由、工具链/风险/权限确认后，直接切入 Review。

不要因为已经读过以前的聊天、Change 或旧文档，就跳过当前仓库事实恢复。

## 4. 最常用的请求方式

不需要把 Coding 的内部规则全部写进提示词。只要明确目标、授权和边界即可。

### 4.1 开发一个功能

```text
使用 coding，基于当前 main 的真实代码完成这个功能。
先读取仓库规则和相关事实，判断 L1-L3 风险；按适用规则完成实现、测试、文档影响检查，并在完成前进入 review，最后完成 PR/CI。
```

### 4.2 修 Bug

```text
使用 coding 修复这个问题。
先稳定复现并定位根因，不要先猜修复；保留失败证据，修复后重新验证原始症状和相关回归，并在完成前执行 review。
```

### 4.3 只做 Code Review

```text
使用 coding 审查当前代码，只 Review，不修改。
先恢复当前仓库事实、需求、工具链、风险和权限；如果仓库存在 review Skill，按 Coding 的硬路由进入 review，从正确性、边界条件、错误处理、安全、兼容、并发、测试充分性、维护性和当前项目规则检查，并给出证据。
```

这里仍然从 Coding 进入，是为了保留 AIMA_UGC 的统一仓库门禁；真正的独立审查方法由 Review Skill 负责。

### 4.4 做方案但暂时不改代码

```text
使用 coding 基于当前仓库实现给出落地方案，只做分析和设计，不修改代码、分支或 PR。
先确认真实模块边界、Contract、Schema、依赖和现有测试，再提出方案。
```

### 4.5 完成开发并交付 PR

```text
使用 coding 完成这个任务，并按仓库现有 Git/CI 门禁创建 PR。
完成前按当前仓库规则进入 review；只有当前 HEAD 的适用验证、Review 和 CI 真正通过后，才能声明可合并。
```

## 5. L1、L2、L3 可以怎么理解

这里给的是快速理解，不替代 [`SKILL.md`](SKILL.md) 的正式判定。

### L1：小而隔离

通常是：

- 纯机械文案或路径修正；
- 行为不变的极小改动；
- 影响范围很小、没有公共 Contract / Schema / 安全 / 部署风险的简单修复。

L1 不一定需要 Change，但仍然需要适用验证。

### L2：需要正式追踪的重要修改

常见包括：

- 新功能；
- 行为变化；
- 多文件重要修复；
- 需要追踪的文档/架构治理；
- 明显的并行协作影响。

通常需要 `changes/active/<CHANGE_ID>/CHANGE.md`。

### L3：公共边界或高风险修改

常见包括：

- 公共 API / Contract；
- Schema / Migration；
- 认证授权和安全；
- 破坏性兼容；
- 部署、恢复、数据迁移；
- 重大依赖或跨模块长期边界。

L3 不能因为“只改几行”就降低风险等级。

## 6. Coding 和 Review / Docs 怎么协作

### 6.1 Coding → Review

Coding 继续负责研发规范、需求/TDD/调试/兼容/Contract/Schema/Git/验证/交付。Review 不复制这些规则。

仓库存在 `../review/SKILL.md` 时：

```text
显式 Code Review / Audit
→ Coding 恢复仓库事实和任务边界
→ Review 独立审查

普通实现任务
→ Coding 实现与验证
→ Docs Impact（适用时）
→ 完成前 Review
→ Review 独立审查
```

Review 从测试专家视角独立重建风险和应有证据，不把“测试绿色”自动等同“测试充分”。它会按项目真实边界区分 Browser Mock、Backend/API/Persistence、Contract、Real Full-stack、外部 Probe 等不同证据。

如果 Review 发现实现缺陷且当前任务已经授权修复：

```text
Review Finding
→ 返回 Coding
→ Coding 按完整研发流程修复并取得新鲜验证
→ Review re-review
```

Review Skill 不存在时，Coding 仍保留原有两阶段 Review；Review 文件存在但无法读取时，不能假装 Review 已完成。

详细说明见 [`../review/README.md`](../review/README.md) 和正式 [`../review/SKILL.md`](../review/SKILL.md)。

### 6.2 Coding → Docs

Coding 不自己复制一套 Docs 写作规则，而是在代码或行为变化后做一个轻量判断：

```text
这次变化是否改变了人类需要理解、使用、维护、部署或排障的事实？
```

#### 没有文档影响

记录具体依据：

```text
Docs Impact: not_applicable
Reason: <为什么没有影响>
```

然后结束文档分支，不加载无关文档，也不为了“有文档 diff”而改 Markdown。

#### 有文档影响

```text
Coding
→ 读取 ../docs/SKILL.md
→ Docs 默认做 targeted Review / Update
```

Docs 自己决定哪些文档真正相关，不是 Coding 猜到的候选文档都必须修改。

如果 Docs 发现当前实现违反正确事实：

```text
Docs
→ code_issue_detected
→ 返回 Coding
→ Coding 按完整研发流程修复并验证
→ Docs targeted re-review
```

详细协作规则见 [`../docs/references/04_与Coding协作.md`](../docs/references/04_与Coding协作.md)。

## 7. Coding 自带哪些辅助 CLI

这些脚本是**工作流辅助工具**，不是 Coding Skill 本身，也不会自动替你完成研发判断。

从仓库根目录运行。

### 7.1 发现或刷新项目导航缓存

```bash
python .agents/skills/coding/scripts/coding.py discover --root .
```

作用：创建或刷新 `.agents/project-context.json`。

这个文件只是可失效导航缓存，不是事实副本。

### 7.2 查看进行中的 Change 和冲突

```bash
python .agents/skills/coding/scripts/coding.py status --root .
```

### 7.3 单独检查 Active Change 重叠

```bash
python .agents/skills/coding/scripts/coding.py conflicts --root .
```

它会根据当前 Change 声明的路径、Contract、数据等显式边界检查并行重叠，但不能替代人工理解真实调用链。

### 7.4 创建 L2 / L3 Change

先看参数：

```bash
python .agents/skills/coding/scripts/coding.py new-change --help
```

`new-change` 会实际写入 `changes/active/`，只有任务确实需要 Change 且当前 Git/任务授权允许时才使用。

### 7.5 Ready 前机器结构检查

```bash
python .agents/skills/coding/scripts/ready_check.py --root . --require-active-ready
```

这个脚本检查可机器判断的 Change 结构和完成状态。它**不能证明业务需求完整，也不能替代 Requirement Traceability、Completion Audit、语义 Review 和真实测试**。

## 8. 目录怎么读

```text
coding/
├── README.md      # 人类使用说明
├── SKILL.md       # Coding 正式主规则
├── agents/        # Agent metadata / 默认提示
├── assets/        # Change 等模板
├── references/    # 按触发条件加载的详细规则
├── scripts/       # 项目发现、Change 和 Ready Check 辅助工具
└── tests/         # Coding / Review / Docs 路由与规则回归
```

不是每个任务都要把 `references/` 全部读一遍。应先按 `SKILL.md` 路由，只读取本次命中的最少充分 reference。

## 9. 常见误区

### “用了 Coding 就应该直接改代码”

不对。只读分析、Review、方案任务不会因为用了 Coding 就自动获得修改、提交、PR 或合并权限。

### “CI 绿了就代表功能一定完成”

不对。CI 只能证明它实际检查的内容。L2/L3 还要核对上游需求、Change、Validation Matrix、Completion Audit 和适用 Review。

### “项目发现缓存写了什么就是什么”

不对。`.agents/project-context.json` 只是导航，当前仓库真实文件和本轮验证结果优先。

### “所有项目都要 Browser、PostgreSQL、Full-stack”

不对。验证层由当前项目真实边界和任务风险决定，不为了套模板制造测试层。

### “Coding 已经会自检，所以不需要 Review Skill”

不对。Coding 保留基础两阶段 Review，但仓库安装 Review Skill 后，Coding 会把显式 Review/Audit 和实现完成前 Review 路由到独立 Review 方法，由 Review 重新检查测试充分性和 Findings，减少作者自检确认偏差。

### “Coding 已经包含 Docs，所以不用再加载 Docs”

不对。Coding 只负责 Docs Impact 和路由；真正的文档事实、写作和审查方法由 Docs Skill 负责。

## 10. 进一步阅读

- [Coding 正式主规则](SKILL.md)
- [跨项目研发任务路由](references/02_跨项目研发任务路由.md)
- [通用验证与证据策略](references/07_通用验证与证据策略.md)
- [两阶段复核与完成前验证](references/11_两阶段复核与完成前验证.md)
- [Review Skill 使用说明](../review/README.md)
- [Review 正式规则](../review/SKILL.md)
- [Docs Skill 使用说明](../docs/README.md)
- [`.agents` 总说明](../../README.md)
- [AIMA_UGC Agent 统一入口](../../../AGENTS.md)

## 11. 网络源与 Workflow 治理怎么用

当任务会下载安装 Runtime、编译器、系统包、语言依赖，或者会修改启动/初始化脚本、Docker/OCI 镜像构建、CI bootstrap、部署环境准备等网络下载行为时，Coding 会先判断**目标执行环境**，而不是按 Agent 自己所在网络选择镜像。

如果目标是**中国大陆网络**，应对当前可用的国内镜像做**实时核验**，再选择适合该生态和项目的下载源；阿里云、清华 TUNA、中科大 USTC、npmmirror 等只能作为候选，不代表永久可用。海外服务器或 GitHub Hosted Runner 也不会因为项目在中国使用就机械切到国内源。正式细则见 [`references/03_编程语言与工具链适配规则.md`](references/03_编程语言与工具链适配规则.md)。

镜像加速的目标只是改善下载链路，不应该顺手改变锁定版本、包/镜像 canonical 身份、checksum/hash/digest、签名或锁文件事实。当前镜像不可验证或明显落后时，应回到项目既有源、官方上游或另一个已验证候选，而不是关闭 TLS、校验或安全门禁换取速度。

当任务新增/修改永久 CI、Workflow、测试门禁、构建/发布流水线，或者当前调查已经发现 Workflow 明显存在无关触发、重复环境准备、重复证明同一风险或昂贵层被滥用时，Coding 会先做 **Workflow Responsibility Audit**：明确每个 Job/Step 证明什么，再建立原证明责任到新位置的映射。

所谓 **证据守恒**，不是要求 YAML 行数不变，而是要求所有仍然存在的独立失败边界都有不弱于原来的验证层。之后才可以通过 path/event 过滤、changed-scope/risk detection、fast path、安全缓存、artifact 复用、并行化、PR/main/release 分层或收敛 Real Full-stack Golden Path 等方式降低成本。正式方法见 [`references/07_通用验证与证据策略.md`](references/07_通用验证与证据策略.md)；Web/API/PostgreSQL/Provider 项目还要同时遵守 [`references/08_分层测试与验收策略.md`](references/08_分层测试与验收策略.md)。

这套规则不会要求每次普通代码修改都扫描全部 Workflow；只有 CI/Workflow 本身被修改，用户明确要求精简，或当前任务已经暴露明显长期成本问题时才触发专项审计。