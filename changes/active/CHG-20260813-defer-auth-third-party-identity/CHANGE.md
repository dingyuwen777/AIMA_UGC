---
schema: rvc-change/v1
id: CHG-20260813-defer-auth-third-party-identity
title: 延后登录实现并固定第三方身份扩展边界
level: L3
status: ready_for_review
owner: dingyuwen777
branch: docs/defer-auth-third-party-identity
created: 2026-08-13
updated: 2026-08-13
depends_on: []
affected_areas: [architecture, auth, security, development-process]
affected_paths: [AGENTS.md, README.md, docs/blueprint/README.md, docs/blueprint/01-总体架构与技术选型.md, docs/blueprint/03-数据库与文件存储.md, docs/blueprint/04-后端任务API与前端.md, docs/blueprint/05-日志安全部署与运维.md, docs/blueprint/06-开发约束与分阶段实施.md, docs/blueprint/07-技术决策与实施门禁.md, changes/active/CHG-20260813-defer-auth-third-party-identity/CHANGE.md]
contracts: []
data_changes: []
---

# 用户确认的上游决定

1. 第一版暂不设计或实现登录入口、本地用户名/密码、MFA、Session、CSRF 和登录限流。
2. 未来身份认证预计与飞书等第三方企业应用/身份源集成，再实现权限控制。
3. 当前只预留可替换的身份/授权边界，不绑定飞书 SDK、`open_id`、`union_id` 或某一种 OAuth/OIDC/Session 细节。
4. 遇到必须由用户/业务 Owner 决定的上游事项时，Agent 必须先在对话中给出明确推荐方案；存在实质取舍时再列 2–3 个备选及影响，由用户最终决定后继续依赖该决定的工作。
5. 用户决定或明确延期必须在同一任务写入正式 Blueprint/需求/OpenSpec（存在时）/Change，形成 Contract/Schema 时再同步机器事实；不能只留在聊天里。

# 最终设计

未来身份链路固定为：

```text
Feishu / OIDC / 其他企业身份源
→ Identity / Authentication Adapter
→ Principal / AuthContext
→ Authorization Service / Policy
→ stable Permission / object policy
→ 业务 Service
```

Authentication 与 Authorization 解耦。业务模块只消费统一 Principal/AuthContext 和授权结果，Provider 私有身份只停留在 Adapter/身份映射边界。

当前不冻结 `principals`、`identity_links`、Role/Permission、Session/Token 等具体表结构；等真实第三方协议、租户和权限需求明确后再创建独立 L3 Change/Migration。`api_idempotency_records` 现有设计依赖 actor，因此 actor/Principal 数据库语义也跟随真实认证/写 API 阶段冻结，不反向创建本地 `users`。

审计保持 Provider 中立：actor 使用 system actor 或未来内部 Principal，不把飞书私有 ID/Token 当业务主键。

# 成功标准

- [x] Blueprint 明确第一版不实现登录入口、本地密码、Session、CSRF、登录限流和 MFA。
- [x] Blueprint 明确未来第三方身份源通过可替换 Adapter 进入统一 Principal/AuthContext，再由授权层判断 Permission/对象权限；业务模块不依赖飞书字段。
- [x] 未完成真实第三方认证接入前，不宣称对公网的敏感/写 API 已具备生产认证能力。
- [x] Stage 3 调整为 Contract/DB/System/Audit + 身份/授权扩展边界，不把本地登录实现作为当前门禁。
- [x] 本地用户/Session/Auth 登录表从当前 Stage 3 Schema 基线移出；API 幂等 actor 作用域不再绑定不存在的 `users`。
- [x] `admin/operator/analyst/viewer` 改为候选角色示例，不再冒充已批准第一版角色 Contract。
- [x] AGENTS.md 和 Blueprint 06/07 明确用户决策门禁：先调查、对话中给推荐/备选、用户决定、正式落文档、再继续依赖实现。
- [x] 文档之间不再同时存在“第一版服务端 Session 必做”和“登录延期”的冲突。

# 方案比较

## A. 现在实现本地账号 + Session，再未来接飞书

不采用。会提前实现用户明确不需要的登录入口、密码和 Session 生命周期，未来还需维护/迁移两套认证路径。

## B. 直接把业务权限绑定飞书 open_id / union_id

不采用。会把业务模块和数据语义绑定某个 Provider，未来替换 OIDC/其他企业身份源需要跨模块改造。

## C. Provider 可替换，内部只认 Principal/AuthContext（采用）

满足当前“延后登录、保留扩展能力”的目标，同时不过度预建具体协议和 Schema。

# 非目标

- 不实现登录页面、登录 API、OAuth/OIDC/飞书回调。
- 不新增用户/Session/Auth 表或 Migration。
- 不决定飞书具体协议、Token 生命周期或 Session 策略。
- 不实现 RBAC/Permission 代码。
- 不修改运行代码、HTTP Contract、数据库或依赖。

# 文档同步

- `AGENTS.md`：新增用户决策硬门禁，并同步认证延期安全边界。
- Blueprint 01：API/system 模块改为第三方身份可替换边界。
- Blueprint 03：移除当前本地 users/session/login-attempt Schema，审计 actor Provider 中立，身份具体表延后。
- Blueprint 04：身份/授权链改为 Adapter → Principal/AuthContext；API 幂等 actor 语义延期。
- Blueprint 05：第三方身份安全边界、Provider 中立审计；角色列表改为候选示例。
- Blueprint 06：新增“必须由用户决定”流程；Stage 3/8 验收同步调整。
- Blueprint 07：1.6 → 1.7，记录已确认延期决定和用户决策门禁，更新 Stage 0/3/8 Go-No-Go。
- Blueprint README / 根 README：下一阶段描述同步。

# 验证与 Review

本 Change 为纯设计/规范变更，TDD 不适用。一次性迁移工具使用唯一文本匹配和显式冲突断言，正式分支最终已删除全部临时 workflow/脚本。

PR #7 Run `31697484373`：

- `Stage 1` success；
- `Stage 2 Platform` success；
- `Windows bootstrap` success。

需求符合性 Review：最终 diff 只修改规范/Blueprint/Change，不包含代码、Schema、Migration、Contract、依赖或 Branch Protection；用户确认的“登录延期 + 第三方身份扩展 + 对话推荐后用户决策”均有正式事实落点。

质量 Review：复核 01/03/04/05/06/07 的身份、Session、API 幂等、审计和 Stage 门禁，已消除本地登录必做冲突；没有把飞书私有字段冻结成业务结构，也没有提前冻结未确认身份表/协议。未发现严重或重要问题。

# 兼容、Migration、部署与回滚

无运行行为、Contract、Schema/Data、依赖或 Migration 变化。生产仍 No-Go。若未来用户改变认证决定，创建新的 L3 Change 覆盖当前设计，不改写本归档历史。

# Git

- 分支：`docs/defer-auth-third-party-identity`
- PR：#7 `延后登录实现并固定第三方身份扩展边界`
- 合并前要求：PR 最终 head CI 全绿且 Review 无严重/重要问题。
- 合并后要求：`main` CI 全绿后归档本 Change。
