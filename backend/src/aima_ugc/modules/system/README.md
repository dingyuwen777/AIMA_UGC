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

## Runtime Provider 配置控制面

`provider_configs` 同时承载 Collection 与 LLM 的**非敏感运行配置**。管理员配置中心是人工维护入口；API Key 只写入持久化 Provider Secret Store，数据库、HTTP 响应、审计和日志都不保存 Secret 明文，也不向前端暴露内部 `secret_ref`。

运行时采用“新任务读最新配置、已创建 Run 冻结快照”的规则：

- 新 Analysis Run 每次创建时读取当前启用的默认 LLM Provider，并冻结 Provider revision、Base URL、model、timeout/concurrency/retry 与不可变 Secret 引用；
- 新 Collection Run 冻结计划引用的 Provider 配置与相同运行参数；
- 已创建 Run、运行中任务及同 Run 的自动重试继续使用原快照，不因管理员后续修改或密钥轮换发生漂移；
- 新建/手工重跑重新读取当前数据库配置，不需要重启 API、Worker 或 Docker Compose；
- `.env` / 部署 Secret 仅用于数据库尚无对应配置时的首次 bootstrap。Internal V1 TikHub Provider 一旦存在，后续启动不得再用 `.env` 覆盖数据库事实。

持久化 Secret Store 与内部系统 Secret 分离：Linux 默认位于宿主 `${AIMA_HOST_ROOT}/shared/provider-secrets`；API 以读写方式挂载用于创建不可变 Secret 版本，Worker 只读挂载用于按 Run Snapshot 解析凭据。Windows Docker Desktop 使用独立 Docker-managed `windows_provider_secrets` volume 保持相同语义。

`provider_configs.id` 是 Provider 配置实例的稳定 UUID。同一种 Provider 可以有多个配置实例；配置实例不绑定平台，Collection 的 Plan/平台策略通过 `provider_config_id` 选择它。Provider 类型不允许对同一稳定 UUID 原地改成另一 Provider；切换 Provider 时创建新配置并改引用。

`keywords.normalized_text` 是关键词稳定去重字段，数据库保证唯一。正式 HTTP 写入只接收原始 `text`，
后端先去除首尾空白，再用 Unicode NFKC 与 `casefold` 生成该字段；内部空白和 `-/_/·` 仍参与数据库
身份，因此 `AIMA-500` 与 `AIMA500` 可以是两个父事实。`keyword_pack_items` 使用
`(pack_id, keyword_id, platform)` 作为复合身份，`platform='all'` 只表示父事实中的全平台词；Collection
创建 Run 时再按正式 Plan 关系展开并冻结为明确平台关键词列表。

## Keyword Pack、Brand/Vehicle Filter 与 legacy Rule Relevance

System 负责长期关键词父事实：

```text
keyword_packs / keywords / keyword_pack_items
```

Keyword Pack 为新建 TikHub Discovery 提供 Search Terms。Collection 创建 `collection-run-config.v2` 时把 Search Snapshot 与 Brand/Vehicle Filter Snapshot 分别冻结；Candidate 映射为 Canonical 后，由共享 `BrandVehicleResolver` 决定是否进入 Content Ingestion：

```text
Collection
→ Keyword Pack Search Terms
→ Provider Search / 必要时 Detail
→ BrandVehicleResolver
→ Content Ingestion + Brand/Vehicle Evidence
```

正式 Excel Import 不执行 Search，但使用同一个 Brand/Vehicle Filter：创建 Import/Campaign 时提交 `brand_ids`，由 Brand/Vehicle Catalog 冻结 `BrandVehicleFilterSnapshot`；空集合表示全部 active Brand。Import 与 Campaign 都拒绝旧关键词/车型混合 Snapshot。

Keyword Pack 只负责 TikHub Discovery 的 Search Terms；Brand/Vehicle Filter 由任务创建时冻结的 Brand 范围和目录快照负责。旧 Global Keyword Relevance 配置与 API 已退出当前 Schema 和生产调用链。AI Semantic Relevance 与人工相关性复核仍由 Analysis 与查询层维护，两者不是旧入库过滤配置的延续。

`imports_test` 的离线相关性清洗继续复用现有 Relevance 匹配规则。数据库关键词身份与运行时匹配规范化仍是两个有意不同的概念：`keywords.normalized_text` 负责稳定数据库身份；Relevance 匹配可以进一步忽略空白和 `-/_/·`。同一选择范围内多个数据库关键词若收敛为同一匹配文本，运行时按稳定优先级/顺序保留第一个有效匹配项，数据库与管理 API 仍保留各自词条。

正式关键词目录读写由 Pydantic HTTP Contract 与 `PostgresKeywordCatalogRepository` 维护。Brand/Vehicle Snapshot 由 Brand/Vehicle Owner 提供，并在 Import 与 Collection 创建入口接入 [`backend/src/aima_ugc/modules/ingestion/brand_vehicle_filter.py`](../ingestion/brand_vehicle_filter.py)。精确请求字段和 Snapshot 结构以当前 Contract/代码为准，不在 README 复制第二套 Schema。

Keyword 别名仍通过独立关键词表达；Brand/Vehicle 别名由各自 Catalog 与 Alias 表维护。两类父事实、唯一身份和运行 Snapshot 不互相替代。

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
