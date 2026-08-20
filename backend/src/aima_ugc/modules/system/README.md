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

`keywords.normalized_text` 是关键词稳定去重字段，数据库保证唯一。正式 HTTP 写入只接收原始 `text`，
后端先去除首尾空白，再用 Unicode NFKC 与 `casefold` 生成该字段；内部空白和 `-/_/·` 仍参与数据库
身份，因此 `AIMA-500` 与 `AIMA500` 可以是两个父事实。`keyword_pack_items` 使用
`(pack_id, keyword_id, platform)` 作为复合身份，`platform='all'` 只表示父事实中的全平台词；Collection
创建 Run 时再按正式 Plan 关系展开并冻结为明确平台关键词列表。

## 关键词管理进入 Stage 8 前的产品门禁

`imports_test` 当前有自己的本地相关性清洗词包文件，并在离线清洗时使用 NFKC、casefold、去空白以及
忽略 `-/_/·` 的匹配规范化。Stage 8B 继续保留这套更强的 Relevance 匹配规则；它与数据库身份规则
有意不同。同一词包内若多个数据库关键词收敛为同一匹配文本，运行时按稳定优先级/顺序保留第一个有效
匹配项，数据库和管理 API 仍保留各自词条。

Stage 8B 已批准的业务边界是：Discovery 词包只决定 TikHub 等 Provider 搜索什么；Relevance 是所有
来源在 Mapper 形成 Canonical 后、写入 Content 前执行的统一准入过滤。Relevance 词包是系统全局唯一
配置，Import/Collection 不允许分别覆盖；每个 Job/Run 仍必须冻结 Pack ID、版本和实际关键词快照。
全局配置使用正式外键关系，不能把 Keyword Pack UUID 作为无约束 JSON 设置。

后续正式开发 Alias 关系前仍必须由业务 Owner 明确以下语义，不能由实现者静默选择默认值：

1. 真正业务别名、俗称是否需要“标准词 → 多别名”的正式关系；如果需要，必须再明确别名与 `keywords.normalized_text` 唯一身份、Keyword Pack 成员、Run Snapshot、前端编辑/去重的关系。

Stage 8B 不新增 Alias 表；业务别名先作为独立关键词加入词包。后续决定应在对应 Stage 8 Change 中固化
到 HTTP Contract、正式文档和必要的数据模型，不得提前制造第二套 Keyword/别名数据库结构。

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
