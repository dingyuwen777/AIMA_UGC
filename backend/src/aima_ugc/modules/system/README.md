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
- `global_relevance_config`：`system`；
- `audit_events`：`system`。

`provider_configs.id` 是 Provider 配置实例的稳定 UUID。同一种 Provider 可以有多个配置实例；配置实例不绑定平台，Collection 的 Plan/平台策略通过 `provider_config_id` 选择它。Provider 类型不允许对同一稳定 UUID 原地改成另一 Provider；切换 Provider 时创建新配置并改引用。

`keywords.normalized_text` 是关键词稳定去重字段，数据库保证唯一。正式 HTTP 写入只接收原始 `text`，
后端先去除首尾空白，再用 Unicode NFKC 与 `casefold` 生成该字段；内部空白和 `-/_/·` 仍参与数据库
身份，因此 `AIMA-500` 与 `AIMA500` 可以是两个父事实。`keyword_pack_items` 使用
`(pack_id, keyword_id, platform)` 作为复合身份，`platform='all'` 只表示父事实中的全平台词；Collection
创建 Run 时再按正式 Plan 关系展开并冻结为明确平台关键词列表。

## Keyword Pack 与 Rule Relevance

System 负责长期关键词父事实：

```text
keyword_packs / keywords / keyword_pack_items
```

确定性 Rule Relevance 发生在 Canonical 之后、Content Ingestion 之前，但不同入口的**选择方式不同**：

```text
Collection
→ global_relevance_config
→ 当前全局 Relevance Keyword Pack
→ 创建 Run 时冻结 Relevance Snapshot

Excel Import
→ 用户创建 Import 时显式选择 1—20 个 Keyword Pack
→ 合并启用关键词并按现有 Relevance 匹配规则归一/去重
→ 冻结 ImportKeywordSelectionSnapshot 到 Batch + Job
```

所以 `global_relevance_config` 仍是 System Owner 的正式父事实，但它当前服务 Collection 的全局入口选择；Excel Import 不读取它来决定本次筛选词包。Import 和 Collection 都使用同一关键词目录与确定性 Relevance 语义，并把本次实际 Pack/版本/有效关键词冻结后再异步执行，避免管理员后续修改词包改变已经排队的任务。

`imports_test` 的离线相关性清洗继续复用现有 Relevance 匹配规则。数据库关键词身份与运行时匹配规范化仍是两个有意不同的概念：`keywords.normalized_text` 负责稳定数据库身份；Relevance 匹配可以进一步忽略空白和 `-/_/·`。同一选择范围内多个数据库关键词若收敛为同一匹配文本，运行时按稳定优先级/顺序保留第一个有效匹配项，数据库与管理 API 仍保留各自词条。

正式关键词目录读写由 Pydantic HTTP Contract 与 `PostgresKeywordCatalogRepository` 维护；Collection 全局 Relevance 由 `PostgresGlobalRelevanceRepository` 维护；Import 的多词包冻结在 `bootstrap/import_http.py` 与 `modules/ingestion/import_job.py`。精确请求字段和 Snapshot 结构以当前 Contract/代码为准，不在 README 复制第二套 Schema。

当前没有独立 Alias 表。业务别名先作为独立关键词加入词包；如果未来建立“标准词 → 多别名”正式关系，必须先明确它与 `keywords.normalized_text` 唯一身份、Keyword Pack 成员、Collection Run Snapshot、Import Keyword Selection 和前端编辑/去重的关系，再通过正式 Change 落到 Contract/Schema。

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
