## Requirement Source

Requirement-Source: #<Issue>

- 填写真实、稳定且可追溯的 Requirement Source。GitHub Issue 可使用 `Requirement-Source: #123`；仓库正式文件可使用仓库内真实存在的路径，例如 `Requirement-Source: docs/spec.md` 或 `Requirement-Source: docs/architecture.md`。
- 一个 PR 确实对应多个独立来源时，每个来源单独填写一行 `Requirement-Source:`；不要把多个来源挤在同一行。
- `#<Issue>`、空值、`TBD`、`TODO`、`待确认`、`无` 等占位值不能作为正式来源。
- machine gate 只负责可机械确认的来源形状、存在性或可解析性；它不替代 Requirement 自然语言完整性、Completion Audit 或独立 Review。
- 仓库外 ID / URL 只有在当前项目已经建立明确、稳定的机器解析规则时才能作为 machine source；通用模板不自创外部 URI 规则。
- `Requirement-Source` 说明 PR 为什么存在；`Closes` / `Fixes` / `Resolves` 说明 merge 后是否应自动关闭整个 Issue，两者职责不同。不要用关闭关键字替代 `Requirement-Source:`。
- Requirement Source 需要 post-merge evidence（例如 main-fresh CI、迁移/部署后验证或 Change archive）时，merge 前不得使用 `Closes` / `Fixes` / `Resolves` 抢先自动关闭；由 Post-Merge Finalization / Closure Audit 取得充分直接 Evidence、回写 Acceptance 并重读后再关闭。

## 背景与现状

说明当前可验证事实、约束和本 PR 要解决的问题。不要把未验证推断写成事实。

## 目标

描述合并后用户、调用方或维护者能够观察到的结果。

## 范围

- 列出本 PR 实际修改的模块、Contract、数据、治理资产或工具链。

## 非目标

- 明确本 PR 不处理什么，防止范围静默扩大。

## 必须保持不变

- 列出需要兼容的公共接口、配置、数据语义、权限、安全边界、合法行为与既有门禁。

## 变更摘要

- 按文件、模块或能力说明实际变化及原因；不要只罗列 diff。

## Contract / 数据 / Schema / Migration / Runtime / Release

- 分别说明适用的 Contract、数据、Schema、Migration、Runtime、Release 影响。
- 无变化的维度明确写“无 / 不适用”并给出事实依据。
- 有变化时说明兼容、迁移、部署、失败语义与回滚边界。

## 验证

列出本轮实际执行的完整命令或机器检查、exit code、通过/失败数量，以及与当前 head 绑定的 CI / GitHub Actions Evidence。未执行的验证不得写成已通过。

## 文档与治理

说明同步了哪些长期事实、Requirement / Change / Review 治理；未更新的相关文档说明为什么不受影响。

## 风险与未验证内容

明确剩余风险、环境限制、未执行验证和它们是否阻塞当前交付结论。

## Git / 发布

说明分支、提交、PR、reviewed head、CI、merge、main-fresh、Change Archive、Issue Closure、cleanup 与 Release/Deploy 状态；不适用或未授权的阶段明确说明。
