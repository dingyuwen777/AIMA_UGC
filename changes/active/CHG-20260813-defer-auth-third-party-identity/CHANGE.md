---
schema: rvc-change/v1
id: CHG-20260813-defer-auth-third-party-identity
title: 延后登录实现并固定第三方身份扩展边界
level: L3
status: approved
owner: dingyuwen777
branch: docs/defer-auth-third-party-identity
created: 2026-08-13
updated: 2026-08-13
depends_on: []
affected_areas: [architecture, auth, security, development-process]
affected_paths: [AGENTS.md, docs/blueprint/README.md, docs/blueprint/04-后端任务API与前端.md, docs/blueprint/05-日志安全部署与运维.md, docs/blueprint/06-开发约束与分阶段实施.md, docs/blueprint/07-技术决策与实施门禁.md, README.md]
contracts: []
data_changes: []
---

# 用户确认的上游决定

第一版暂不设计或实现登录入口、本地用户名/密码、MFA、Session、CSRF 和登录限流。未来身份认证预计与飞书等第三方企业应用/身份源集成，并在认证之后实现权限控制。

当前阶段只固定可替换的身份与授权边界，不绑定飞书 SDK、飞书用户字段或某一种 OAuth/OIDC/Session 细节；具体认证协议、回调、Token、Session 生命周期等在真实第三方接入需求明确后作为独立 L3 Change 决定和实现。

# 目标

1. 消除现有 Blueprint 中“Stage 3 必须立即实现本地账号 + Session 登录”的过期约束。
2. 固定 Authentication 与 Authorization 解耦的长期边界，使未来 Feishu/OIDC/其他企业身份源可以替换而不侵入业务模块。
3. 在编码规范中增加用户决策门禁：遇到无法由仓库确认、且会影响业务语义/Contract/Schema/安全/费用/保留策略等的上游决定时，不得由 Agent 静默拍板继续实现。
4. 明确用户确认的长期决定必须在同一任务写入正式事实文档/Contract/OpenSpec（存在时）或对应 Blueprint，而不是只留在聊天记录。

# 成功标准

- [ ] Blueprint 明确第一版不实现登录入口、本地密码、Session、CSRF、登录限流和 MFA。
- [ ] Blueprint 明确未来第三方身份源通过可替换 Identity/Authentication Adapter 进入统一 Principal/AuthContext，再由授权层判断 Role/Permission/对象权限；业务模块不依赖飞书字段。
- [ ] 未完成真实第三方认证接入前，不宣称对公网的敏感/写 API 已具备生产认证能力。
- [ ] Stage 3 范围调整为 Contract/DB/System/Audit + 身份/授权扩展边界，不把本地登录实现作为当前门禁。
- [ ] AGENTS.md 明确“用户决策门禁”和“用户决定落文档”规则。
- [ ] 文档之间不再同时存在互相冲突的本地登录必做与登录延后描述。

# 方案比较

## A. 现在实现本地账号 + Session，再未来接飞书

不采用。会提前实现用户已明确不需要的登录入口、密码和 Session 生命周期；未来第三方接入时还需维护两套认证路径。

## B. 直接把业务权限绑定飞书 open_id / union_id

不采用。会把业务模块和数据库语义绑定某个 Provider，未来换 OIDC/其他企业身份源需要跨模块迁移。

## C. 身份认证 Provider 可替换，内部只认统一 Principal/AuthContext（采用）

未来链路：

```text
Feishu / OIDC / 其他企业身份源
→ Authentication Adapter
→ Principal / AuthContext
→ Authorization Service / Policy
→ Role / Permission / 对象级授权
→ 业务 Service
```

Provider-specific ID 只存在于身份映射边界，不作为业务模块判断权限的依据。

# 非目标

- 不实现任何登录页面、登录 API、OAuth/OIDC/飞书回调。
- 不新增用户/Session/Auth 表或 Migration。
- 不决定飞书具体 Operation、OAuth/OIDC 模式、Token 生命周期或 Session 策略。
- 不实现 RBAC 代码；只修订长期设计和开发门禁。

# 兼容、Migration、部署与回滚

本 Change 只修改规范与 Blueprint，无代码、Schema、Contract 或运行行为变化，因此无 Migration。生产部署仍为 No-Go。若未来用户改变决定，应创建新的 L3 Change 明确认证方案，而不是改写本归档历史。

# 验证

纯文档/规范变更使用确定性检查替代 TDD：复核受影响文档术语、Stage 3 范围和认证约束无冲突，并运行仓库文档/质量门禁。
