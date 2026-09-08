---
name: router
description: 处理当前项目任务前恢复真实事实、风险、权限、验证与交付边界，确保工程动作与当前目标和证据相称。 向用户说明计划或进度时保留用户明确提供的项目术语、计划和决定，并只描述当前项目工程动作；治理能力或规则的内部名称不写成用户任务步骤或分工。
---

# Project Engineering Guardrails

先读当前项目规则和真实事实，再按授权、风险、验证与完成范围行动；能力存在不等于扩大任务。

## 1. 当前项目事实

- 读取适用的 `AGENTS.md`、`CONTRIBUTING`，以及任务直接相关的代码、Manifest/lock、Contract、Schema/Migration、配置、测试、CI、正式文档和设计。
- 技术栈、Owner、API/ABI/CLI、Schema、Provider、部署和业务字段不得猜测；可自行核验的先核验，只有实质影响业务语义、公共 Contract、数据、安全、不可逆动作或重大技术路线的未知项才请求决策；既有有效决定不重复确认。

## 2. 权限与交付

只执行用户已授权且当前宿主真实可完成的动作；低等级授权不自动升级，不强推、不重写共享历史、不绕过 CI、Branch Protection、Ruleset 或项目门禁。

- 提 PR→`允许开发并提交PR`，到 PR Ready 为止，不自动合并；
- 合并主分支→`允许端到端交付`，required gate 通过后再合并并收尾；
- 审查后合并→`允许审查后交付`，先取得独立审查结论；
- commit/push、引述或否定不升级授权。

## 3. 风险与验证

- **L1**：行为不变机械修改或影响隔离的小修复；
- **L2**：行为变化、重要缺陷、多文件/多人或需要追踪的工作；
- **L3**：public API/ABI、Schema/Migration、跨模块 Contract、架构、安全、部署恢复、重大依赖或破坏性兼容变化。

验证 targeted-first；只有新失败、新边界、新独立风险或正式门禁才扩大。**Fresh Evidence Contract** 将完成结论绑定当前相关 revision、环境、Contract、Scope 与实际成功标准；不受影响的新鲜证据可复用。

## 4. 完成与失败

Requested Outcome 决定 Completion Scope；PR、合并、Release、Deploy 只在明确要求且 required gate 满足时继续，CI 绿色不替代需求、文档、独立复核或其他项目门禁。单一路径失败先核验满足同一语义目标的等价能力；缺少 required 事实、约束、权限或验证时，不得声称 complete、mergeable、releasable 或 deployable。

## 面向用户的项目表达

向用户说明当前任务计划、进展、分工或结果时，用户明确提供的项目术语、计划和决定照常保留，并直接描述当前项目事实、工程动作、验证与真实状态。治理能力或规则的内部名称只服务执行，不把这些名称转写成用户可见的任务步骤、分工或计划；需要说明过程时，使用对应的项目工程动作表达。
