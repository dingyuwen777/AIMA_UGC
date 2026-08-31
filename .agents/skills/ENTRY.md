# Agent Skills Entry

本文件是 Agent_Skills 的稳定薄入口，不保存 Skill Catalog、路由矩阵或专业规则。

使用 Agent_Skills 处理任何任务时：

1. 先读取当前目标项目及上级适用的 `AGENTS.md`、`CONTRIBUTING` 或同等项目规则；
2. 再按任务需要从当前代码、Manifest/lock、Contract、Schema/Migration、配置、测试、CI、正式文档和设计事实恢复最少充分的项目上下文；
3. 然后无条件读取 [`.agents/skills/router/SKILL.md`](router/SKILL.md)，由 Router 选择本次真正命中的专业 Skill 与 References；
4. 目标项目事实和上位指令优先于 Agent_Skills 通用示例，不从历史聊天、缓存或其他业务仓库猜当前实现。

如果 [`.agents/skills/router/SKILL.md`](router/SKILL.md)、必需 Skill 或必需 Reference 无法读取或验证，必须说明缺失事实，并停止依赖相应规则的动作；不得用旧记忆、摘要或自拟替代规则声称已经按 Agent_Skills 执行。
