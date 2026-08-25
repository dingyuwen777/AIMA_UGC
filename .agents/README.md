# `.agents` 使用说明

`.agents/` 用来保存**仓库内 AI / Coding Agent 的辅助能力和导航信息**。它不是产品代码目录，也不是另一套项目架构文档。

如果在 AIMA_UGC 中处理分析、设计、开发、Review、文档、PR、CI 或交付任务，统一入口仍然是仓库根目录的 [`AGENTS.md`](../AGENTS.md)。本 README 只帮助人快速判断“这里有哪些能力、什么时候用哪个 Skill”，**不能替代 `AGENTS.md` 或各 Skill 的 `SKILL.md` 正式规则**。

## 1. 这个目录为什么存在

项目里的 AI Agent 需要两类东西：

1. **可执行的工作规则**：例如怎样可靠开发、怎样检查文档；
2. **可失效的导航信息**：例如当前仓库有哪些事实入口，帮助 Agent 少走弯路。

把它们放在 `.agents/` 下，可以和产品代码、正式架构文档分开，避免把 Agent 工作流混入业务实现。

当前结构：

```text
.agents/
├── README.md
├── project-context.json
└── skills/
    ├── coding/
    │   ├── README.md
    │   ├── SKILL.md
    │   ├── agents/
    │   ├── assets/
    │   ├── references/
    │   ├── scripts/
    │   └── tests/
    └── docs/
        ├── README.md
        ├── SKILL.md
        ├── agents/
        └── references/
```

### `project-context.json`

这是 Coding Skill 生成或刷新的**项目发现缓存**，主要用于快速定位规则、Manifest、锁文件、文档和其他事实入口。

它只是导航缓存，不是当前实现的事实源。缓存可能过期；真正的事实仍然要回到当前代码、Contract、Migration、测试、锁文件和项目正式文档确认。

从仓库根目录刷新：

```bash
python .agents/skills/coding/scripts/coding.py discover --root .
```

不要因为缓存里写了某个结论，就跳过当前仓库事实检查。

## 2. `coding` 和 `docs` 分别解决什么问题

| Skill | 主要解决的问题 | 常见任务 |
| --- | --- | --- |
| [`coding`](skills/coding/README.md) | 怎样可靠完成软件研发、验证和交付 | 仓库分析、方案设计、功能开发、Bug 修复、重构、Code Review、PR、CI、Release |
| [`docs`](skills/docs/README.md) | 怎样保证技术文档与正确事实同步，并让人真正看懂 | 文档 Review、文档修复、README/架构/API/运维文档编写与更新、代码与文档一致性检查 |

最简单的判断方式：

```text
主要任务是在改或检查软件实现？
→ 用 Coding

主要任务是在检查、编写或更新技术文档？
→ 用 Docs

代码变化可能影响文档？
→ Coding 先做 Docs Impact
→ 有影响时再加载 Docs

Docs 检查时发现其实是代码错了？
→ Docs 输出 code_issue_detected
→ 返回 Coding 修实现
→ Docs 做 targeted re-review
```

## 3. 在 AIMA_UGC 中怎样进入这两个 Skill

### 普通研发任务

```text
AGENTS.md
→ Coding
→ 按任务读取最少充分代码 / Contract / Migration / 测试 / 文档
→ 实现与验证
→ Docs Impact
→ Review / PR / CI / 交付
```

### 单独做文档任务

Docs 可以独立承担文档工作，但 AIMA_UGC 的仓库规则要求所有仓库任务先经过统一入口：

```text
AGENTS.md
→ Coding 完成仓库级事实恢复、风险和 Git/权限路由
→ Docs 成为本任务的主要工作流
→ Review Only / Review + Fix / Write / Update
```

这不表示“用 Docs 还要由 Coding 来写文档”。Coding 在这里负责项目门禁；真正的文档判断和写作由 Docs 负责。

## 4. 最常用的请求方式

不需要记复杂命令。在支持仓库访问的 Agent 中，直接把目标和授权写清楚即可。

### 用 Coding 开发

```text
使用 coding，基于当前仓库真实实现完成这个功能。
先恢复事实和判断风险等级，再按适用规则开发、测试、Review，并完成 PR/CI 交付。
```

### 用 Coding 只做 Review

```text
使用 coding 审查当前实现，只 Review，不修改代码。
基于当前仓库事实给出问题、证据和风险。
```

### 用 Docs 只检查文档

```text
使用 docs 检查当前技术文档是否和实际代码、Contract、Migration、配置、测试一致。
只 Review，不修改文件。
```

### 用 Docs 检查并修正文档

```text
使用 docs 检查并修正受影响文档。
从为什么存在、解决什么问题、数据/调用怎么流、代码在哪实现开始解释；术语用白话，必要时给最小例子。
如果发现是代码问题，不要让文档迎合 Bug，按 Docs → Coding 路由处理。
```

### 用 Docs 新写 README

```text
使用 docs 为这个模块补 README。
面向第一次接手项目的人，说明为什么存在、负责什么、不负责什么、主要调用/数据流、真实实现入口、怎么使用和排障。
不要复制完整 Schema 或代码形成第二套事实。
```

## 5. 哪些文件才是正式规则

请区分“使用说明”和“执行规则”：

```text
仓库级规则
→ ../AGENTS.md

Coding 正式规则
→ skills/coding/SKILL.md
→ skills/coding/references/

Docs 正式规则
→ skills/docs/SKILL.md
→ skills/docs/references/

人类快速使用说明
→ 本 README
→ skills/coding/README.md
→ skills/docs/README.md

可失效导航缓存
→ project-context.json
```

README 可以解释“怎么用”，但不应复制所有详细规则。README 与 `SKILL.md` 冲突时，以当前适用的上位项目规则和 `SKILL.md` 为准。

## 6. 进一步阅读

- [Coding Skill 使用说明](skills/coding/README.md)
- [Coding 正式规则](skills/coding/SKILL.md)
- [Docs Skill 使用说明](skills/docs/README.md)
- [Docs 正式规则](skills/docs/SKILL.md)
- [AIMA_UGC Agent 统一入口](../AGENTS.md)
