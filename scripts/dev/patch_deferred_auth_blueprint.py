"""一次性同步第三方身份接入与用户决策门禁到长期设计文档。"""

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old[:100]!r}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_section(path: str, start: str, end: str, replacement: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    if text.count(start) != 1 or text.count(end) != 1:
        raise RuntimeError(f"{path}: section markers are not unique: {start!r} / {end!r}")
    before, tail = text.split(start, 1)
    _, after = tail.split(end, 1)
    file_path.write_text(before + replacement + end + after, encoding="utf-8")


def main() -> None:
    # Coding standard: decisions that belong to the user/business owner must stop dependent work,
    # but the agent must first give a concrete recommendation in the conversation.
    replace_once(
        "AGENTS.md",
        "能从仓库确认的事实不反问。发现错误前提先指出。",
        """能从仓库确认的事实不反问。发现错误前提先指出。

### 用户决策门禁

如果某个未决事项会实质影响业务语义、页面/验收、公共 Contract、Schema、权限/安全、隐私与保留/删除、外部 Provider/Operation、费用/预算、调度策略、SLO/RPO/RTO、兼容性或不可逆数据行为，并且仓库没有已经批准的事实：

1. 不得由 Agent 静默选一个默认值后继续实现依赖该决定的代码；
2. 先完成能够由仓库、官方资料、Fixture 或测试自行确认的事实调查，再只提出最小必要的上游问题；
3. **必须在对话中先给出明确推荐方案**；存在有意义的取舍时再给 2–3 个实质不同的备选，并说明影响，不能只把一个没有建议的开放问题丢给用户；
4. 由用户/业务 Owner 作最终决定；在得到决定前，暂停依赖该决定的 Contract、Schema、业务语义、安全策略或不可逆实现，与该决定无依赖的工作可以继续；
5. 用户明确“暂不决定/以后再做”时，把延期本身记录为正式设计边界，不得继续偷偷实现该能力；
6. 用户给出决定后，在同一任务同步到对应长期事实源：Blueprint/需求文档、OpenSpec（存在时）、Contract/Schema（形成机器事实时）以及当前 Change；聊天记录不能作为后续开发唯一事实源；
7. 后续任务再次遇到已经固化的决定时直接读取事实源执行，不重复询问；只有新需求与已批准决定冲突时才重新提请用户决策。""",
    )
    replace_once(
        "AGENTS.md",
        """- 本地账号密码使用 Argon2id，服务端 Session Cookie 使用 `HttpOnly`、`Secure` 和 `SameSite`；
- Session、登录限流、RBAC 和 API 幂等必须有数据库表和生命周期，不使用纯进程内状态充当生产事实；
- 修改请求按会话模型执行 CSRF 防护；""",
        """- 当前第一版不实现本地账号密码、登录入口、MFA、Session、CSRF 或登录限流；真实第三方身份接入需求明确后再通过独立 L3 Change 实现认证；
- 未来飞书、OIDC 或其他企业身份源必须通过可替换 Identity/Authentication Adapter 进入统一 `Principal/AuthContext`；业务模块不得直接依赖飞书 SDK、`open_id`、`union_id` 或其他 Provider 私有字段；
- Authentication 与 Authorization 解耦：后端权限判断面向统一 Principal、稳定 Permission 和对象级策略，不因更换身份 Provider 改写业务 Service；
- 如果未来选定服务端 Session，再按实际方案实现 Session 哈希、Cookie、CSRF、撤销与过期；如果采用 OAuth/OIDC/飞书授权流程，则按协议验证 `state`、`nonce`，支持时使用 PKCE；
- API 幂等必须有数据库事实源；认证/授权实现进入生产范围后同样不得使用纯进程内状态充当生产事实；""",
    )
    replace_once(
        "AGENTS.md",
        "- 不得关闭认证、证书、输入校验或安全检查。",
        "- 已实现并批准的认证、证书、输入校验或安全检查不得为方便调试而关闭；第三方认证尚未接入时，敏感/写 API 不得宣称具备公网生产认证能力。",
    )
    replace_once(
        "AGENTS.md",
        "- Session fixation、CSRF、撤销/过期、RBAC、IDOR、SSRF 重定向/DNS、路径/Zip/日志注入；",
        "- 认证接入阶段按实际协议验证身份边界与授权；采用 Session 时覆盖 fixation、CSRF、撤销/过期，采用 OAuth/OIDC/飞书授权流程时覆盖 state/nonce/PKCE/回调绑定；通用授权覆盖 Permission/对象级权限/IDOR，其他安全专项继续覆盖 SSRF 重定向/DNS、路径/Zip/日志注入；",
    )
    replace_once(
        "AGENTS.md",
        "受影响就同任务更新，不受影响不制造文档差异。长期文档描述合并后的当前系统，不写成变更日志。文档用普通中文、真实路径、真实命令和明确例子。",
        "受影响就同任务更新，不受影响不制造文档差异。长期文档描述合并后的当前系统，不写成变更日志。文档用普通中文、真实路径、真实命令和明确例子。用户确认的长期业务/技术决定或明确延期决定必须在同一任务落到正式事实源，不能只存在于聊天或 Change 历史中。",
    )

    # DB blueprint: local-password/session schema is no longer a current Stage 3 commitment.
    replace_once(
        "docs/blueprint/03-数据库与文件存储.md",
        """### 4.1 System

```text
users
roles
permissions
user_roles
role_permissions
sessions
auth_login_attempts
api_idempotency_records
provider_configs
keyword_packs
keywords
keyword_pack_items
tracked_accounts
audit_events
```""",
        """### 4.1 System

当前 Stage 3 共享基础：

```text
system_settings
provider_configs
keyword_packs
keywords
keyword_pack_items
tracked_accounts
audit_events
```

本地用户名/密码、`sessions`、`auth_login_attempts` 不属于当前第一版 Schema。未来接入飞书/OIDC/其他企业身份源时，再通过独立 L3 Change 冻结身份映射、Principal、Role/Permission 与必要的会话/Token 表；不得提前把业务表绑定某个 Provider 私有用户 ID。`api_idempotency_records` 需要稳定 actor/Principal 作用域，因此跟随实际认证/授权边界一起冻结，不在当前 Stage 3A 猜测 actor 语义。""",
    )
    replace_section(
        "docs/blueprint/03-数据库与文件存储.md",
        "### 5.19 `System/Auth` 与 API 幂等表\n",
        "## 6. `jsonb` 使用边界",
        """### 5.19 System、审计与未来身份扩展

当前 Stage 3 不实现本地用户名/密码、Session、CSRF、登录限流，也不建立 `users.password_hash`、`sessions` 或 `auth_login_attempts` 等本地登录 Schema。

`system_settings` 只保存非敏感、需要数据库事实源的系统设置；Secret 继续留在 Secret 文件/未来 Secret Provider 中。

`audit_events` 必须保持身份 Provider 中立。当前最小语义：

```text
audit_events
  id                  uuid primary key
  actor_kind          text not null
  actor_ref           text
  event_type          text not null
  object_type         text
  object_id           text
  request_id          text
  safe_detail         jsonb not null default '{}'
  created_at          timestamptz not null
```

`actor_kind` 至少能够表达 `system` 和未来的 `principal`；`actor_ref` 只保存内部稳定引用或安全摘要，不把飞书 `open_id`、`union_id`、OAuth Token 等 Provider 私有/敏感值直接传播成业务主键。未来建立正式 Principal 表后，可通过独立 Migration 把适用引用升级为受约束外键。

未来认证/授权的长期方向固定为：

```text
Feishu / OIDC / 其他企业身份源
→ identity/authentication adapter
→ Principal / AuthContext
→ authorization
→ stable Permission / object policy
→ business service
```

可能需要 `principals`、`identity_links`、`roles`、`permissions`、Principal-Role/Role-Permission 等关系，但**这些表名、字段和生命周期现在不冻结**；等真实第三方接入协议、租户边界和权限需求确认后再创建对应 L3 Change 与 Migration。若未来方案需要服务端 Session，再独立增加 Session 表和过期/撤销语义；不因为旧蓝图曾出现本地登录模型而默认继续实现。

HTTP API 幂等仍是长期要求，但现有设计以 actor 作为作用域。当前认证/Principal 语义尚未冻结，因此 `api_idempotency_records` 的 actor 外键/作用域字段也延后到实际认证/写 API 阶段决定，避免先绑定不存在的 `users` 表。

""",
    )
    replace_once(
        "docs/blueprint/03-数据库与文件存储.md",
        """sessions(user_id, revoked_at)
sessions(idle_expires_at)
auth_login_attempts(account_identifier_hash, attempted_at desc)
auth_login_attempts(client_ip_hash, attempted_at desc)
""",
        "",
    )

    # API blueprint: provider-neutral identity boundary only; no login implementation now.
    replace_section(
        "docs/blueprint/04-后端任务API与前端.md",
        "### 4.7 认证、会话和授权\n",
        "## 5. 长任务",
        """### 4.7 身份认证扩展边界与授权

当前第一版**不设计或实现登录入口、本地用户名/密码、MFA、Session、CSRF 和登录限流**。这些不是当前 Stage 3 成功标准。未来预计接入飞书等第三方企业应用/身份源；具体采用飞书 OAuth、OIDC、企业自建登录还是服务端 Session，由真实接入场景明确后通过独立 L3 Change 决定。

长期依赖方向固定为：

```text
Feishu / OIDC / 其他企业身份源
→ Identity / Authentication Adapter
→ Principal / AuthContext
→ Authorization Service / Policy
→ Role / Permission / 对象级授权
→ 业务 Service
```

业务 Router/Service 只消费统一 `Principal/AuthContext` 和授权结果，不读取飞书 `open_id`、`union_id`、租户字段或 SDK 对象做权限判断。Provider-specific 身份只存在于身份映射/Adapter 边界，因此未来替换身份源不需要改写业务模块。

角色名称和操作边界仍属于阶段 0 业务决定；长期只固定“后端授权不能依赖前端隐藏按钮”。未来权限控制应尽量面向稳定 Permission 和对象级策略。Artifact/Raw/敏感导出下载必须先查元数据和所属业务对象，再执行权限判断，不能把存储路径或可猜 URL 直接暴露给浏览器。

如果未来选定服务端 Session，必须再明确 Session 生命周期、Token 哈希、Cookie、CSRF、撤销/过期和限流；如果选择 OAuth/OIDC/飞书授权流程，则必须按实际协议验证回调绑定、`state`、`nonce`，支持时使用 PKCE。Provider Token/Secret 只保存在服务端 Secret 边界，不进入浏览器长期存储、日志或业务表明文。

第三方认证尚未实现和验收前，系统可以继续本地/受控环境开发，但**不得把敏感或写 API 宣称为具备公网生产认证能力**。

""",
    )

    # Security blueprint: same decision and actor-neutral audit.
    replace_once(
        "docs/blueprint/05-日志安全部署与运维.md",
        """审计记录包含：

```text
actor
action""",
        """审计中的 `actor` 使用统一 Principal 或明确的 system actor，不把审计模型硬绑定为“本地用户表 ID”；未来第三方身份源先映射到内部 Principal，再写审计。

审计记录包含：

```text
actor
action""",
    )
    replace_once(
        "docs/blueprint/05-日志安全部署与运维.md",
        "└─ session_secret",
        "└─ <identity_provider_secret>  # 未来接入第三方身份源时按实际 Provider 增加",
    )
    replace_section(
        "docs/blueprint/05-日志安全部署与运维.md",
        "### 13.2 登录与会话\n",
        "### 13.3 权限",
        """### 13.2 身份认证与第三方接入

当前第一版不实现本地用户名/密码、登录页面、MFA、Session、CSRF 或登录限流，也不预建 `sessions`、`auth_login_attempts`、密码 Hash 等本地登录 Schema。

未来飞书、OIDC 或其他企业身份源统一通过可替换 Adapter 接入：

```text
External Identity Provider
→ Authentication Adapter
→ Principal / AuthContext
→ Authorization
→ 业务能力
```

第三方 Provider 的用户 ID、租户字段、Token 和 SDK 对象不能成为业务模块公共身份结构。业务权限只依赖内部 Principal/AuthContext；身份映射层负责把 Provider-specific subject 映射到内部身份。Provider Secret/Token 只保存在服务端 Secret 边界，禁止进入日志、Raw、Job Payload、浏览器 `localStorage` 或业务表明文。

具体认证协议和会话策略在真实第三方接入时单独评审。如果采用 OAuth/OIDC/飞书授权流程，必须验证 `state`、`nonce`，支持时使用 PKCE，且不能只相信前端传回的用户信息；如果实际方案需要服务端 Session，再追加 Session fixation、Cookie、CSRF、撤销/过期等专项测试。

认证尚未实现时，生产状态继续 No-Go：敏感和写 API 不能仅靠前端隐藏、Nginx 路径或“部署在内网”的假设来宣称已完成权限保护。

""",
    )
    replace_once(
        "docs/blueprint/05-日志安全部署与运维.md",
        """第一版最小角色：

```text
admin
operator
analyst
viewer
```

后端每个写接口必须声明权限；隐藏按钮不能代替后端授权。查询 Raw、下载导出、修改 Provider、删除数据和恢复备份使用单独权限，不因拥有普通写权限自动获得。""",
        """角色名称和操作边界仍属于阶段 0 业务决定。以下只作为候选角色套餐示例，**不是已批准的第一版角色 Contract**：

```text
admin
operator
analyst
viewer
```

未来角色如何命名可以变化，但权限判断必须后端执行并尽量面向稳定 Permission；隐藏按钮不能代替后端授权。查询 Raw、下载敏感导出、修改 Provider、删除数据和恢复备份应使用独立权限，不因拥有普通写权限自动获得。""",
    )

    # Development blueprint: explicit user-decision flow and adjusted Stage 3/8.
    replace_once(
        "docs/blueprint/06-开发约束与分阶段实施.md",
        "- 用户和基础权限；",
        "- 身份/权限采用可替换边界；具体第三方认证与角色操作边界按阶段 0/后续独立 Change 决定；",
    )
    replace_once(
        "docs/blueprint/06-开发约束与分阶段实施.md",
        "重大方案有多个可行选项时，先列 2—3 个方案和取舍，确认后实现。用户已经明确授权按本技术基线从零实施的事项，不重复要求无价值确认。",
        """重大方案有多个可行选项时，先列 2—3 个方案和取舍，确认后实现。用户已经明确授权按本技术基线从零实施的事项，不重复要求无价值确认。

### 5.3 必须由用户/业务 Owner 决定的事项

无法从仓库或真实事实源确认、且会改变业务语义、Contract、Schema、安全/权限、隐私/保留/删除、Provider Operation、费用、调度或 SLO/RPO/RTO 的上游决定，Agent 不得代替用户拍板。

流程固定为：

```text
先调查可确认事实
→ 在对话中给出推荐方案
→ 必要时列 2—3 个实质不同的备选和影响
→ 用户/业务 Owner 决定
→ 把决定或“明确延期”同步到正式事实文档/OpenSpec/Change
→ 再继续依赖该决定的实现
```

等待决定期间，只暂停真正依赖该决定的部分；无依赖工作可以继续。不得只问“你想怎么做”而不给推荐，也不得把聊天中的决定当成后续唯一事实源。""",
    )
    replace_once(
        "docs/blueprint/06-开发约束与分阶段实施.md",
        "18. Worker/Scheduler 崩溃恢复、API 幂等与 Auth 安全专项；",
        "18. Worker/Scheduler 崩溃恢复、API 幂等，以及达到实际认证接入阶段后对应协议/Auth 安全专项；",
    )
    replace_once(
        "docs/blueprint/06-开发约束与分阶段实施.md",
        """### 阶段 3：Contract、数据库与 System/Auth

→ 修改范围：Canonical Pydantic、JSON Schema 生成、核心表、API 幂等、用户/角色/权限/Session/登录限流/审计、Alembic  
→ 预期结果：空库可升级，示例可校验，表 Owner 明确，认证与授权有数据库事实源  
→ 验证：Migration 集成、Contract 生成/兼容、Session 固定/撤销/过期、CSRF、RBAC、登录限流和审计测试""",
        """### 阶段 3：Contract、数据库与 System/Audit

→ 修改范围：Canonical Pydantic、JSON Schema 生成、核心表、Artifact 元数据 Repository/Table、System Settings、Provider 中立审计、Alembic，以及未来第三方身份接入所需的 `Principal/AuthContext` Port 边界  
→ 预期结果：空库可升级，示例可校验，表 Owner 明确；认证 Provider 可以未来接入而不污染业务模块；当前不实现登录入口、本地密码、Session、CSRF、登录限流或 MFA  
→ 验证：Migration 升降级、Contract 生成/兼容、Artifact Repository、审计 actor Provider 中立性和依赖方向；真实飞书/OIDC/Session 安全专项留到认证接入 Change""",
    )
    replace_once(
        "docs/blueprint/06-开发约束与分阶段实施.md",
        "→ 验证：API、统一错误、API 幂等、Session/CSRF/RBAC/对象级授权、Cursor、Type、Unit、E2E",
        "→ 验证：API、统一错误、Cursor、Type、Unit、E2E；如果届时已接入第三方认证/授权，再按实际协议增加 Principal/Permission/对象级授权和对应安全 E2E，未接入时不得用 Mock 登录冒充生产认证成立",
    )

    # Decision gate: record the new approved decision, remove local-login assumptions from Stage 0/3 gate.
    replace_once(
        "docs/blueprint/07-技术决策与实施门禁.md",
        "> 蓝图版本：1.6  ",
        "> 蓝图版本：1.7  ",
    )
    replace_once(
        "docs/blueprint/07-技术决策与实施门禁.md",
        "## 3. 版本选择与冻结政策",
        """### 2.8 身份认证延期、第三方扩展边界与用户决策规则

用户已确认：当前第一版不设计或实现登录入口、本地用户名/密码、MFA、Session、CSRF 或登录限流。未来预计与飞书等第三方企业应用/身份源结合后实现身份认证与权限控制；具体认证协议、回调、Token/Session 生命周期在真实接入需求明确后作为独立 L3 Change 冻结。

当前只冻结以下长期边界：

```text
Feishu / OIDC / 其他企业身份源
→ Identity / Authentication Adapter
→ Principal / AuthContext
→ Authorization
→ stable Permission / object policy
→ business service
```

- 业务模块不得直接依赖飞书 SDK、`open_id`、`union_id`、租户字段或其他 Provider 私有身份；
- Authentication 与 Authorization 解耦，替换身份 Provider 不应要求改写业务 Service；
- 角色名称/操作边界仍由阶段 0 业务决定，`admin/operator/analyst/viewer` 目前只是候选示例；
- 未完成真实认证接入前，敏感/写 API 不得宣称具备公网生产认证能力；
- 用户明确延期的能力不得由后续 Agent 因旧模板或“最佳实践”偷偷恢复实现。

需要用户/业务 Owner 决定的事项采用固定门禁：Agent 先调查可自行确认的事实，**在对话中给出推荐方案**，必要时附 2–3 个实质不同备选和影响，再由用户作最终决定。决定前暂停依赖该语义的 Contract/Schema/安全或不可逆实现；用户决定或明确延期后，同一任务必须写入对应领域 Blueprint/需求、OpenSpec（存在时）和当前 Change，形成机器 Contract/Schema 时再同步机器事实。聊天记录不能成为后续实现唯一依据。

## 3. 版本选择与冻结政策""",
    )
    replace_once(
        "docs/blueprint/07-技术决策与实施门禁.md",
        "1. 第一版页面、角色操作边界、字段和验收流程；",
        "1. 第一版页面、字段和验收流程，以及未来第三方认证接入后需要的角色/Permission 操作边界；当前登录入口已明确延期，不再作为第一版待设计项；",
    )
    replace_once(
        "docs/blueprint/07-技术决策与实施门禁.md",
        "| 3 Contract/DB/Auth | 表、Owner、API/Canonical/Job 契约和 Session 模型已评审 | 先做写 API，后补认证表 |",
        "| 3 Contract/DB/System | **可推进共享基础**：Canonical/表 Owner/Alembic/Artifact 元数据/System/Audit 边界已设计；本地登录/Session 已明确延期，当前只预留 Provider 中立 Principal/AuthContext 边界 | 因旧蓝图自行创建本地密码/Session 表、把业务身份绑定飞书私有字段、在无认证时宣称敏感写 API 可公网生产 |",
    )
    replace_once(
        "docs/blueprint/07-技术决策与实施门禁.md",
        "- 阶段 0 未决项解决后，把确定值写入对应领域文档和 OpenSpec，不在本文长期保留模糊占位；",
        "- 阶段 0 或其他用户决策门禁解决后，把用户确认值或明确延期写入对应领域文档和 OpenSpec（存在时），并同步当前 Change；不得只保留聊天结论，也不得在本文长期保留已解决的模糊占位；",
    )

    # Navigation and README: current next stage wording.
    replace_once(
        "docs/blueprint/README.md",
        "### 阶段 3：Contract、数据库与 System/Auth",
        "### 阶段 3：Contract、数据库与 System/Audit",
    )
    replace_once(
        "docs/blueprint/README.md",
        "- System Settings、User、Role、Permission、Session、登录限流、审计；\n- API 幂等基础；",
        "- System Settings、Provider 中立审计，以及未来第三方身份接入所需的 `Principal/AuthContext` 扩展边界；\n- 当前不实现登录入口、本地密码、Session、CSRF、登录限流或 MFA；API 幂等的 actor 作用域跟随未来 Principal/认证语义冻结；",
    )
    replace_once(
        "README.md",
        "→ 阶段 3：Canonical Contract、核心数据库 Schema/Alembic、System/Auth",
        "→ 阶段 3：Canonical Contract、核心数据库 Schema/Alembic、System/Audit + 第三方身份扩展边界（不实现登录）",
    )


if __name__ == "__main__":
    main()
