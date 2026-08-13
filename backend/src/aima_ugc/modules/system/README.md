# System 模块

## 负责什么

- 非敏感、需要 PostgreSQL 作为事实源的系统设置；
- Provider 中立审计事件；
- 为未来第三方身份接入保留模块边界，但当前不实现认证。

## 不负责什么

- Secret；
- 登录、本地密码、Session、CSRF、MFA；
- 飞书/OIDC 回调；
- 当前尚未批准的角色/Permission Schema。

## 数据表和写入 Owner

- `system_settings`：`system`；
- `audit_events`：`system`。

## 外部依赖和 Port

持久化实现位于 `adapters/persistence/postgres/`，业务代码不直接依赖 SQL。

## 独立验证

```bash
uv run pytest tests/integration/database -q
uv run python scripts/quality/check_table_ownership.py
```
