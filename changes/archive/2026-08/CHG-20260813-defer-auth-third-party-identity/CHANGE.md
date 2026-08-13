---
schema: rvc-change/v1
id: CHG-20260813-defer-auth-third-party-identity
title: 延后登录实现并固定第三方身份扩展边界
level: L3
status: done
owner: dingyuwen777
branch: docs/defer-auth-third-party-identity
created: 2026-08-13
updated: 2026-08-13
depends_on: []
affected_areas: [architecture, auth, security, development-process]
affected_paths: [AGENTS.md, README.md, docs/blueprint/README.md, docs/blueprint/01-总体架构与技术选型.md, docs/blueprint/03-数据库与文件存储.md, docs/blueprint/04-后端任务API与前端.md, docs/blueprint/05-日志安全部署与运维.md, docs/blueprint/06-开发约束与分阶段实施.md, docs/blueprint/07-技术决策与实施门禁.md]
contracts: []
data_changes: []
---

# 结果

用户确认的认证延期和用户决策门禁已经写入长期设计并合并到 `main`：

1. 第一版不设计或实现登录入口、本地用户名/密码、MFA、Session、CSRF 和登录限流。
2. 未来飞书、OIDC 或其他企业身份源通过可替换 `Identity / Authentication Adapter` 接入统一 `Principal / AuthContext`，再由授权层执行 Permission / 对象级权限；业务模块不依赖飞书私有字段或 SDK 对象。
3. 具体第三方认证协议、租户映射、Token/Session 生命周期、角色和 Permission 操作边界在真实需求明确后通过新的 L3 Change 冻结。
4. API 幂等的 actor/Principal 数据库作用域同步延期，不为了当前幂等设计反向创建本地 `users`。
5. 审计 actor 保持 Provider 中立，当前可表达 system actor，未来外部身份先映射内部 Principal 再写审计。
6. 遇到必须由用户/业务 Owner 决定的上游问题时，Agent 必须先调查可确认事实，并在对话中给出明确推荐方案；存在实质取舍时再给 2–3 个备选及影响，由用户最终决定。决定前只暂停依赖该决定的工作；决定或明确延期必须同步正式 Blueprint/需求/OpenSpec（存在时）/Change，形成 Contract/Schema 时同步机器事实，聊天不能作为唯一事实源。

# 最终身份边界

```text
Feishu / OIDC / 其他企业身份源
→ Identity / Authentication Adapter
→ Principal / AuthContext
→ Authorization Service / Policy
→ stable Permission / object policy
→ 业务 Service
```

Authentication 与 Authorization 解耦；Provider-specific 身份只存在于 Adapter/身份映射边界。

# 设计范围调整

- Stage 3 调整为 `Contract、数据库与 System/Audit` 共享基础；当前不实现本地登录。
- 当前 Stage 3 System Schema 不再包含本地 `users`、`sessions`、`auth_login_attempts`。
- `admin/operator/analyst/viewer` 只作为候选角色示例，不是已批准第一版角色 Contract。
- Stage 8 若尚未接入真实第三方认证，只允许受控环境开发，不得用 Mock 登录或前端隐藏按钮宣称公网生产认证成立。
- 未来真实认证接入时，再按实际协议补 Session 或 OAuth/OIDC/飞书对应安全测试。

# 成功标准

- [x] 登录、本地密码、Session、CSRF、登录限流和 MFA 明确延期。
- [x] 第三方身份采用 Provider 可替换 Adapter → Principal/AuthContext 边界。
- [x] 业务模块不依赖飞书 `open_id`、`union_id` 或 SDK 私有对象。
- [x] 本地 Auth Schema 和 actor-bound API 幂等从当前 Stage 3 基线移出。
- [x] 角色示例不再冒充已批准业务 Contract。
- [x] `AGENTS.md`、Blueprint 06/07 已形成“对话先推荐 → 用户决定 → 正式落文档 → 继续依赖实现”的硬门禁。
- [x] 01/03/04/05/06/07 不再存在“第一版服务端 Session 必做”与登录延期的冲突。

# 文档同步

- `AGENTS.md`：新增用户决策硬门禁和认证延期安全边界。
- Blueprint 01：API/system 改为第三方身份可替换边界。
- Blueprint 03：当前 System Schema 移除本地登录表，审计 actor Provider 中立，未来身份表延期。
- Blueprint 04：身份/授权链改为 Adapter → Principal/AuthContext；API 幂等 actor 语义延期。
- Blueprint 05：第三方身份安全边界、Provider 中立审计，角色改为候选示例。
- Blueprint 06：新增用户决策流程；Stage 3/8 验收同步调整。
- Blueprint 07：1.6 → 1.7，记录认证延期、第三方身份边界和用户决策门禁，更新 Stage 0/3/8 Go/No-Go。
- Blueprint README / 根 README：下一阶段描述同步。

# 验证与 Review

本 Change 是纯设计/规范变更，TDD 不适用。一次性文档迁移工具使用严格唯一匹配和冲突断言，并在最终 PR 前全部删除。

PR #7：`延后登录实现并固定第三方身份扩展边界`。

- PR 最终 head `7a253e35906a8a8e337b28291b249904ebeba7c4`。
- PR CI Run `31697663875`：`Stage 1`、`Stage 2 Platform`、`Windows bootstrap` 全部 success。
- 两阶段 Review：最终差异只有规范/Blueprint/Change；没有代码、Schema、Migration、HTTP Contract、依赖或 Branch Protection 变化；未发现严重或重要问题。
- PR #7 已 squash merge，合并提交：`c0739cd675896d01bd4e8811ee7c2a093c1c9c09`。
- 合并后 `main` CI Run `31697926363`：`Stage 1`、`Stage 2 Platform`、`Windows bootstrap` 全部 success。

# 兼容、Migration、部署与回滚

无运行行为、Contract、Schema/Data、依赖或 Migration 变化。生产仍 No-Go。未来用户改变认证方向时创建新的 L3 Change，不改写本归档历史。
