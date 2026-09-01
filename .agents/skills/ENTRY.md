# Agent Skills Entry

本文件是 Agent_Skills 的稳定薄入口，不保存 Skill Catalog、路由矩阵或专业规则。

使用 Agent_Skills 处理任何任务时：

1. 先读取当前目标项目及上级适用的 `AGENTS.md`、`CONTRIBUTING` 或同等项目规则；
2. 再按任务需要从当前代码、Manifest/lock、Contract、Schema/Migration、配置、测试、CI、正式文档和设计事实恢复最少充分的项目上下文；
3. 然后无条件读取 [`.agents/skills/router/SKILL.md`](router/SKILL.md)，由 Router 选择本次真正命中的专业 Skill 与 References；
4. 目标项目事实和上位指令优先于 Agent_Skills 通用示例，不从历史聊天、缓存或其他业务仓库猜当前实现。

**Runtime Mode 下，从进入本 Entry 起内部控制面动作保持静默。** Skill 发现、选择、加载、Router 判断、Reference / required Context 取得和 Handoff 都只服务内部执行，不得播报加载了哪个 Skill、选择了哪些内部能力或怎样取得内部规则；后续任何规则中出现“输出”“选择”“加载”“Handoff”等表述时，在 Runtime Mode 也只表示内部控制面结果，不得转写成用户可见进度。用户可见进度只描述目标项目的调查、修改、测试、文档、复核、Git/CI 和交付事实。Source Mode 维护者直接使用明文仓库时不应用这项隐藏策略，可以正常讨论内部导航和路由事实。

这里的静默边界只约束 Agent / Prompt / Skill / Runtime 能控制的文本。**宿主 UI** 自身自动生成的 Skill/Tool activity label、调用事件或 trace **不受 Prompt / Skill / Runtime 文本规则直接控制**，因此不能宣称可以隐藏；如果宿主产品提供单独的可见性设置，应以宿主能力为准。

如果 [`.agents/skills/router/SKILL.md`](router/SKILL.md)、必需 Skill 或必需 Reference 无法读取或验证，必须说明缺失事实，并停止依赖相应规则的动作；Runtime Mode 的用户可见错误说明只报告“必需治理约束不可用或不完整”及其对工程动作的影响，不枚举缺失的内部 Skill、Reference、路径或加载步骤；不得用旧记忆、摘要或自拟替代规则声称已经按 Agent_Skills 执行。
