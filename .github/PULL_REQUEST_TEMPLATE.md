## Requirement Source

Requirement-Source: #<Issue>

- 机器门禁当前接受两类稳定来源：本仓 Issue（例如 `Requirement-Source: #123`，且必须是真实 Issue 而不是 PR）或当前仓库内真实存在的正式文件相对路径（例如 `Requirement-Source: docs/blueprint/07_技术决策与实施门禁.md`）。
- 一个 PR 确实对应多个来源时，重复填写多行 `Requirement-Source:`；不要把多个来源挤在同一行。
- `#<Issue>`、空值、`TBD` / `TODO` / `待确认` / `无` 等占位值、已不存在的 Issue/路径或自由文本 ID 会被 `Requirement Traceability and Completion Audit` 拒绝。
- 机器门禁只确认来源“存在、可解析、可访问”，不判断需求自然语言是否完整，也不替代 Completion Audit / Agent_Skills Review 的需求符合性审查。
- 如果项目已有更强的正式需求源，可填写当前仓库内对应正式路径；仓库外 ID/URL 只有在项目后续为其建立明确机器解析规则后才可作为机器来源。
- `Closes` / `Fixes` / `Resolves` 只在本 PR 合并后确实完成整个 Issue 时使用；不要用关闭关键字替代 `Requirement-Source:`。

## 背景与现状

说明当前可验证事实和本 PR 解决的问题。

## 目标

描述合并后可观察的结果。

## 范围

- 列出本 PR 修改的模块、Contract、数据或工具链。

## 非目标

- 明确本 PR 不处理什么。

## 必须保持不变

- 列出需要兼容的公共接口、配置、数据和合法行为。

## 变更摘要

- 按文件或能力说明实际变化及原因。

## Contract / 数据 / Migration

- 无变化时明确写“无”。
- 有变化时说明兼容、迁移、部署和回滚。

## 验证

列出本轮实际执行的完整命令、退出码、通过/失败数量，以及 GitHub Actions Run。

## 文档

说明同步了哪些长期事实；未更新的相关文档说明为什么不受影响。

## 风险与未验证内容

明确剩余风险、环境限制和未执行的验证。

## Git / 发布

说明分支、提交、CI、合并和发布/回滚状态。
