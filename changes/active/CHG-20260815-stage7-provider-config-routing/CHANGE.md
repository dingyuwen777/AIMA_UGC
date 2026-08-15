---
schema: rvc-change/v1
id: CHG-20260815-stage7-provider-config-routing
title: 建立 Stage 7 Provider 配置与平台路由基础
level: L3
status: in_progress
owner: dingyuwen777
branch: feature/stage7-provider-config-routing
created: 2026-08-15
updated: 2026-08-15
depends_on: [CHG-20260815-stage7-decision-capability]
affected_areas: [system, collection, provider, contracts, database, testing, documentation]
affected_paths: [backend/src/aima_ugc/modules/system/, backend/src/aima_ugc/modules/collection/, backend/src/aima_ugc/adapters/persistence/postgres/, backend/src/aima_ugc/adapters/providers/, backend/src/aima_ugc/database_schema.py, migrations/versions/, tests/, docs/blueprint/02-采集系统与数据标准化.md, docs/blueprint/03-数据库与文件存储.md, docs/blueprint/08-采集策略与平台能力.md, docs/collection/README.md]
contracts: [provider-config.v1, provider-platform-route.v1]
data_changes: [provider_configs]
---

# 目标

建立 Stage 7 Provider 配置实例与平台选择的稳定机器边界，使同一种 Provider 可以存在多个独立配置实例；每个平台或采集计划选择具体 `provider_config_id`，而不是把 Provider 与平台绑死。后续前端可以独立维护 Provider 名称、Base URL 和凭据，并按平台选择 Provider；Provider 私有分页状态和 Secret 不进入业务配置。

# 成功标准

- [ ] `provider_configs` 成为 System Owner 的数据库事实，具有稳定 UUID、Provider 类型、用户可识别名称、Base URL、Secret 引用、启用状态和时间字段；数据库不保存 API Key/Token 明文。
- [ ] 同一个 Provider 类型允许存在多个配置实例；平台选择具体 `provider_config_id`，配置实例本身不绑定某个平台。
- [ ] 建立版本化 `ProviderConfigV1` 与 `ProviderPlatformRouteV1` 机器 Contract；Route 同时表达平台、具体 Provider Config 和对应 Capability，不暴露 Secret 或第三方分页状态。
- [ ] 建立 Provider Registry/Router：按 Provider Config 的 `provider` 选择已注册 Provider 实现，并按 `provider + platform` 取得当前机器 Capability；未知 Provider、禁用配置、Provider/Capability 不匹配时关闭失败。
- [ ] 当前仅注册机器事实已存在的 `tikhub + xiaohongshu`；不得把抖音、微博、B站、快手设计目标冒充当前实现 Capability。
- [ ] Secret 继续通过 `secret_ref` 进入服务端 Secret 边界；本 Change 不把原始凭据写入源码、数据库、日志、Raw、Contract、Job Payload 或测试快照。
- [ ] 后续 Stage 8 管理 UI 可以在后端安全 Secret 写入能力建立后提供 API Key 输入；读取 Provider Config 时不返回原始 Secret。
- [ ] 新 Migration 必须从当前正式 Revision `20260814_0009` 升级到 head，并继续验证 base→head、上一正式 Revision→head、downgrade/re-upgrade 和 drift。
- [ ] Red 测试先因目标 Provider Config/Route 机器事实不存在而正确失败；Green 后相关 Unit/Contract/PostgreSQL/架构/Secret/文档门禁成功。
- [ ] 受影响 Blueprint/Collection README 同步为合并后的当前事实，不写变更流水账。

# 范围

- Provider 配置实例的稳定 ID、Provider 类型、显示名称、Base URL、Secret 引用和启用状态。
- System Owner `provider_configs` Table/Repository 和新增 Alembic Revision。
- Provider Config / Platform Route Pydantic Contract 与生成 JSON Schema。
- Provider Registry/Router 和当前 XHS TikHub Capability 的正式接线。
- 为后续 Plan/Run Snapshot、Budget Ledger 和 Stage 8 管理页面提供稳定 `provider_config_id` 父事实。

# 非目标

- 不实现 Stage 8 HTTP API 或 Vue 管理页面。
- 不在本 Change 中实现可从浏览器写入 Secret 的持久 SecretStore；当前只建立不泄露 Secret 的 `secret_ref` 边界。
- 不实现关键词/词包、Collection Plan/Occurrence、最终 Budget Ledger、Scheduler。
- 不实现抖音、微博、B站、快手 Operation/Mapper/Capability。
- 不改变 Stage 1—6 已发布 Revision、Canonical、Provider Request/Attempt、Job Runtime 或 XHS Operation 行为。

# 必须保持不变

- Platform 与 Provider 解耦；一个 Provider 配置实例可以被多个平台选择。
- 同一个 Provider 类型可以存在多个配置实例/账号；具体选择以 `provider_config_id` 为稳定身份。
- Secret 不进入数据库明文、日志、Raw、Job Payload、Contract 或前端读取响应。
- 前端以后只配置规范化业务参数；`cursor/search_id/pageArea/max_id` 等仍由 Operation 内部维护。
- Capability 只表达当前代码已经实现/验证的能力；第三方官方文档支持不等于 AIMA 当前机器能力。
- Provider 不写业务表；Mapper 不访问数据库或发 HTTP；Router 不绕过 Owner。

# 已确认关键决策

1. 用户批准方案 A：Provider Account/配置实例与 Platform Route 解耦。
2. 用户进一步确认未来前端应能独立配置多个 Provider 实例的 URL/凭据，再让小红书、抖音等平台分别选择具体 Provider，并按 Capability 配置排序、发布时间范围等业务参数。
3. Provider Config 使用 UUID 作为稳定身份；用户可修改显示名称但不改变历史引用。
4. Base URL 是非敏感配置，可持久化；原始 API Key/Token 不进入 `provider_configs`，只保存服务端 `secret_ref`。
5. Plan/Run 后续引用具体 `provider_config_id`；Run 创建时冻结解析后的 Provider/平台业务策略，避免后续修改配置改变历史 Run。
6. Stage 8 如提供凭据编辑页面，写入时必须经后端安全 Secret 边界，读取时只返回“已配置/掩码状态”，不能回显原始 Secret；具体可写 SecretStore 属于后续安全能力，不在本 Change 静默实现。

# 方案比较

## 方案 A：Provider Config 与平台选择解耦（采用）

Provider Config 只描述一个可连接的 Provider 实例/账号；平台或 Plan 通过 `provider_config_id` 选择它。可以多个平台共享同一 TikHub Account，也可以各自选择不同 Provider/账号。Budget 后续可稳定绑定 Provider Config 身份。

## 方案 B：Provider 只放环境变量（拒绝）

实现最少，但没有稳定数据库身份，无法可靠支撑 Plan Snapshot、Budget、费用审计和多 Provider 实例管理。

## 方案 C：Provider Config 直接绑定平台（拒绝）

会把同一 Provider Account 人为拆成多份，global budget 和费用审计容易重复，也破坏 Platform/Provider 解耦。

# 实施步骤

[步骤 1：建立 Red 测试]
→ 修改范围：System/Collection Unit、Contract、PostgreSQL Integration Test。
→ 预期结果：测试明确要求 Provider Config/Route/Registry 和新表行为，并因目标实现尚不存在而失败。
→ 验证方式：PR GitHub Actions 中相关 pytest/质量 Job 出现目标模块或表缺失导致的正确 Red。

[步骤 2：建立 Provider Config 数据与 Contract]
→ 修改范围：`modules/system`、`contracts/collection`、Schema 生成脚本、`database_schema.py`。
→ 预期结果：Provider Config/Route 成为版本化机器事实；Secret 只保存引用。
→ 验证方式：Unit/Contract/Schema drift/Secret 扫描。

[步骤 3：建立 PostgreSQL Repository 与 Migration]
→ 修改范围：System PostgreSQL Repository、Alembic 新 Revision。
→ 预期结果：多个 Provider 实例可创建/读取/更新非 Secret 配置，稳定 UUID 不变化，API Key 不存在数据库列。
→ 验证方式：PostgreSQL 18.4 Repository Test、base→head、`20260814_0009→head`、downgrade/re-upgrade、`alembic check`。

[步骤 4：建立 Provider Registry/Route]
→ 修改范围：Collection/Provider routing 与 TikHub Capability 接线。
→ 预期结果：`provider_config_id + platform` 能解析到唯一已注册 Provider/Capability；禁用/未知/不支持组合关闭失败。
→ 验证方式：Unit Test + 架构/Secret 门禁。

[步骤 5：同步正式文档并两阶段 Review]
→ 修改范围：Blueprint 02/03/08、Collection README、System/Collection README（如职责变化）。
→ 预期结果：文档描述合并后的真实 Provider 实例与平台选择模型，Stage 8 UI 能直接据此消费后端 Contract，而不是维护平台私有参数表。
→ 验证方式：`check_docs`、diff Review、相关 CI。

# 验证计划

目标验证包括：

```text
uv lock --check
uv run ruff format --check backend tests scripts
uv run ruff check backend tests scripts
uv run mypy backend/src
uv run pytest tests/unit -q
uv run pytest tests/contracts -q
uv run pytest tests/integration/database -q
uv run python scripts/contracts/generate.py --check
uv run python scripts/contracts/check_compatibility.py
uv run python scripts/quality/check_architecture.py
uv run python scripts/quality/check_table_ownership.py
uv run python scripts/quality/scan_secrets.py
uv run python scripts/quality/check_docs.py
uv run alembic upgrade head
uv run alembic check
```

本执行宿主当前无法解析 `github.com`，不能取得本地 checkout；因此本 Change 的 Red/Green 和集成证据使用 PR GitHub Actions。该限制不代表用户本地工作区干净，本地未提交/未推送状态仍无法确认。

# 文档影响

Provider Config/平台路由会改变 Stage 7 当前系统事实，因此需同步 Blueprint 02/03/08 和采集总览；不修改与本 Change 无关的 Stage 8 页面细节或生产部署文档。

# 兼容、Migration、部署和回滚

- 新增独立 Provider Config/Route Contract，不删除或改写现有 Contract 字段。
- 新增 `provider_configs` Migration，不改写历史 Revision。
- 当前 Stage 5C `provider_requests.provider` 仍保持兼容；后续 Plan/Budget Change 再以独立 Migration 引入 `provider_config_id` 外键，不在本 Change 反向改写既有 Request 历史。
- 不新增依赖、不升级锁文件。
- 不改变生产进程数量或部署方式。
- 回滚先停止使用新增 Provider Config/Route，再 downgrade 本 Revision；没有业务数据回填。

# Git

- 基线 main：`ccf5fdfbb74798c036de544b250d464cfe2de855`
- 分支：`feature/stage7-provider-config-routing`
- PR：待创建
- CI：待本轮实际运行
- 合并：未执行
- Change：in_progress
