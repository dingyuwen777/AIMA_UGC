# System 模块

## 负责什么

- 非敏感、需要 PostgreSQL 作为事实源的系统设置；
- Provider 配置实例的稳定身份、Base URL、Secret 引用和启用状态；
- 关键词与词包父事实，以及词包内关键词的平台、优先级、启用状态和备注关联；
- Provider 中立审计事件；
- 为未来第三方身份接入保留模块边界，但当前不实现认证。

## 不负责什么

- Secret 原始值；`provider_configs` 只保存 `secret_ref`，不保存 API Key/Token/Cookie 明文；
- Provider endpoint、分页、Mapper 或平台 Capability；这些属于 Provider/Collection 边界；
- Plan 对词包的选择、Run 关键词展开/冻结、Scheduler/Worker 执行；这些已经属于当前 Collection Owner，System 只提供 Provider Config、关键词、词包等父事实；
- 登录、本地密码、Session、CSRF、MFA；
- 飞书/OIDC 回调；
- 当前尚未批准的角色/Permission Schema。

## 数据表和写入 Owner

- `system_settings`：`system`；
- `provider_configs`：`system`；
- `keyword_packs`：`system`；
- `keywords`：`system`；
- `keyword_pack_items`：`system`；
- `audit_events`：`system`。

`provider_configs.id` 是 Provider 配置实例的稳定 UUID。同一种 Provider 可以有多个配置实例；配置实例不绑定平台，Collection 的 Plan/平台策略通过 `provider_config_id` 选择它。Provider 类型不允许对同一稳定 UUID 原地改成另一 Provider；切换 Provider 时创建新配置并改引用。

`keywords.normalized_text` 是关键词稳定去重字段，数据库保证唯一；当前 System 父事实不自行猜测 NFKC、casefold、空白折叠等规范化算法，正式写入 API/导入边界后再按批准 Contract 产生该值。`keyword_pack_items` 使用 `(pack_id, keyword_id, platform)` 作为复合身份，`platform='all'` 只表示父事实中的全平台词；Collection 创建 Run 时再按正式 Plan 关系展开并冻结为明确平台关键词列表。

## 外部依赖和 Port

持久化实现位于 `adapters/persistence/postgres/`，业务代码不直接依赖 SQL。Secret 引用由 `platform/security` 校验和解析；实际 Secret 内容继续保留在 Secret 边界，不进入 System 数据表。

## 独立验证

```bash
uv run pytest tests/unit/system/test_keyword_models.py -q
uv run pytest tests/integration/database -q
uv run pytest tests/contracts/test_provider_config_stage7.py -q
uv run python scripts/quality/check_table_ownership.py
uv run python scripts/quality/scan_secrets.py
```
