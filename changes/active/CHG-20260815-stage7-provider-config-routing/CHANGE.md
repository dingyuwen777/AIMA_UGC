---
schema: rvc-change/v1
id: CHG-20260815-stage7-provider-config-routing
title: 建立 Stage 7 Provider 配置与平台路由基础
level: L3
status: ready_for_review
owner: dingyuwen777
branch: feature/stage7-provider-config-routing
created: 2026-08-15
updated: 2026-08-15
depends_on: [CHG-20260815-stage7-decision-capability]
affected_areas: [system, collection, provider, contracts, database, testing, documentation]
affected_paths: [backend/src/aima_ugc/modules/system/, backend/src/aima_ugc/modules/collection/, backend/src/aima_ugc/platform/security/, backend/src/aima_ugc/adapters/persistence/postgres/system.py, backend/src/aima_ugc/adapters/providers/, backend/src/aima_ugc/contracts/collection/, backend/src/aima_ugc/database_schema.py, contracts/collection/, migrations/versions/20260815_0010_stage7_provider_configs.py, scripts/contracts/, tests/contracts/test_provider_config_stage7.py, tests/unit/collection/test_provider_routing.py, tests/integration/database/test_provider_config_repository.py, .github/workflows/stage7-provider-config-routing.yml, docs/blueprint/README.md, docs/blueprint/02-采集系统与数据标准化.md, docs/blueprint/08-采集策略与平台能力.md, docs/collection/README.md]
contracts: [provider-config.v1, provider-platform-route.v1]
data_changes: [provider_configs]
---

# 目标与当前结果

建立 Stage 7 Provider 配置实例与平台选择的稳定机器边界，使同一种 Provider 可以存在多个独立配置实例；每个平台或采集计划后续选择具体 `provider_config_id`，而不是把 Provider 与平台绑死。未来前端分成“Provider 管理”和“采集 Plan”两层：Provider 实例维护非敏感 URL 与凭据写入，平台再选择具体实例；排序、发布时间范围等业务参数只展示对应 `Provider + Platform + Operation` Capability 真正支持的选项。

当前代码已经建立 Provider Config/Route Contract、System `provider_configs`、PostgreSQL Repository、第十条 Migration、Secret 引用校验和当前只登记 `tikhub + xhs` 的 Provider Registry。原始 API Key/Token 不进入数据库或读取 Contract；当前 TikHub Base URL 仍受显式 allowlist 约束。

本 Change 仍保留在 `changes/active/`，状态为 `ready_for_review`。只有 PR 合并、合并后 main CI 再次成功并重新证明集成状态后，才允许标记 `done` 并归档。

# 成功标准

- [x] `provider_configs` 成为 System Owner 的数据库事实，具有稳定 UUID、Provider 类型、用户可识别名称、Base URL、Secret 引用、启用状态和时间字段；数据库不保存 API Key/Token 明文。
- [x] 同一个 Provider 类型允许存在多个配置实例；PostgreSQL 集成测试实际创建两个相同 `provider=tikhub`、不同 UUID 的 Config。
- [x] Provider Config 本身不绑定平台；平台路由以具体 `provider_config_id` + platform 解析 Capability。
- [x] 建立版本化 `ProviderConfigV1` 与 `ProviderPlatformRouteV1` 机器 Contract；Route 表达平台、具体 Provider Config 和对应 Capability，不暴露 Secret 或第三方分页状态。
- [x] 建立 Provider Registry：按 Provider Config 的 `provider` 选择当前注册项，并按 `provider + platform` 取得机器 Capability；未知 Provider、禁用配置、不允许 Base URL、未实现平台关闭失败。
- [x] 当前仅注册机器事实已存在的 `tikhub + xhs`；没有把抖音、微博、B站、快手设计目标冒充当前实现 Capability。
- [x] Base URL Contract 必须为 HTTPS，拒绝 URL 内嵌凭据、query/fragment；Provider Registration 自身也复用同一 URL 校验，运行时再执行 Provider allowlist。
- [x] Secret 只通过安全相对 `secret_ref` 表达；拒绝绝对路径、`..`、反斜杠等不安全引用。本 Change 不实现未被当前生产调用需要的 Secret 解析/可写 Store。
- [x] Stage 8 管理 UI 的长期边界已冻结：未来可以输入/轮换 API Key，但必须写入后端安全 SecretStore/SecretService；读取 Provider Config 不返回原始 Secret。
- [x] 新 Revision `20260815_0010` 只新增 `provider_configs`，不改写 Stage 1—6 已发布 Revision；专项 CI 验证 `20260814_0009 → head` 与 `base → head` round trip。
- [x] Red 测试先因目标 Provider Registry/Provider Config Contract 不存在而正确失败；Green 后目标实现和相关工作流已有成功证据。
- [x] Blueprint README、Blueprint 02/08、System/Collection README 与采集总览同步为合并后的当前设计。
- [x] `03-数据库与文件存储.md` 与 `07-技术决策与实施门禁.md` 已检查：03 已列 `provider_configs` System 目标表，07 已冻结预算绑定稳定 Provider 配置身份与 Platform/Provider 解耦，没有与本方案相反的规则，因此不为形式制造整篇差异。

# 范围

- Provider 配置实例的稳定 ID、Provider 类型、显示名称、HTTPS Base URL、Secret 引用和启用状态。
- System Owner `provider_configs` Table/Repository 和新增 Alembic Revision。
- Provider Config / Platform Route Pydantic Contract 与生成 JSON Schema。
- Provider Registry/Route 和当前 XHS TikHub Capability 的正式接线。
- Provider Base URL 显式 allowlist 和 Secret 引用输入校验。
- 为后续 Plan/Run Snapshot、Budget Ledger 和 Stage 8 管理页面提供稳定 `provider_config_id` 父事实。

# 非目标

- 不实现 Stage 8 HTTP API 或 Vue 管理页面。
- 不实现浏览器可写 SecretStore/SecretService，也不把 API Key 放数据库明文作为替代。
- 不实现关键词/词包、Collection Plan/Occurrence、最终 Budget Ledger、Scheduler。
- 不实现真实付费 Provider HTTP Transport。
- 不实现抖音、微博、B站、快手 Operation/Mapper/Capability。
- 不改变 Stage 1—6 已发布 Revision、Canonical、Provider Request/Attempt、Job Runtime 或 XHS Operation 行为。

# 必须保持不变

- Platform 与 Provider Config 解耦；一个 Provider 配置实例可以被多个平台选择。
- 同一个 Provider 类型可以存在多个配置实例/账号；具体选择以 `provider_config_id` 为稳定身份。
- 同一稳定 UUID 的 Provider 类型不原地改写；切换 Provider 时新建 Config 并改引用。
- Secret 不进入数据库明文、日志、Raw、Job Payload、Contract 或前端读取响应。
- 前端以后只配置规范化业务参数；`cursor/search_id/pageArea/max_id` 等仍由 Operation 内部维护。
- Capability 只表达当前代码已经实现/验证的能力；第三方官方文档支持不等于 AIMA 当前机器能力。
- Provider 不写业务表；Mapper 不访问数据库或发 HTTP；Router 不绕过 Owner。

# 已确认关键决策

1. 用户批准方案 A：Provider Account/配置实例与 Platform Route 解耦。
2. 用户进一步确认未来前端应能独立配置多个 Provider 实例的 URL/凭据，再让小红书、抖音等平台分别选择具体 Provider，并按 Capability 配置排序、发布时间范围等业务参数。
3. 用户要求该长期方案写入 Blueprint；当前已同步 Blueprint README、02 与 08，并检查 03/07 无冲突。
4. Provider Config 使用 UUID 作为稳定身份；用户可修改显示名称但不改变历史引用。
5. Base URL 是非敏感配置，可持久化，但必须为 HTTPS 且继续受对应 Provider Adapter allowlist；“可配置 URL”不是任意出站目标。
6. 原始 API Key/Token 不进入 `provider_configs`，只保存服务端 `secret_ref`。
7. Plan/Run 后续引用具体 `provider_config_id`；Run 创建时冻结解析后的 Provider/平台业务策略，避免后续修改配置改变历史 Run。
8. Stage 8 如提供凭据编辑页面，写入时必须经后端安全 Secret 边界，读取时只返回“已配置/需更新”等状态或掩码提示，不能回显原始 Secret。

# 方案比较

## 方案 A：Provider Config 与平台选择解耦（采用）

Provider Config 只描述一个可连接的 Provider 实例/账号；平台或 Plan 通过 `provider_config_id` 选择它。可以多个平台共享同一 TikHub Account，也可以各自选择不同 Provider/账号。Budget 后续稳定绑定 Provider Config 身份。

## 方案 B：Provider 只放环境变量（拒绝）

实现最少，但没有稳定数据库身份，无法可靠支撑 Plan Snapshot、Budget、费用审计和多 Provider 实例管理。

## 方案 C：Provider Config 直接绑定平台（拒绝）

会把同一 Provider Account 人为拆成多份，global budget 和费用审计容易重复，也破坏 Platform/Provider 解耦。

# Red → Green 证据

## Red

PR #36 最初只包含 Active Change、失败测试和 `Stage 7 Provider Config Routing` 专项 CI。Red head `2ffaf8256c5f0568092621922f68900ea9dad4a7` 的 run `31854907454` 中，`Stage 7 Provider Config Unit Contract` job `94937704883`：

- 锁定环境安装成功；
- pytest 收集阶段出现 2 个目标错误；
- `ModuleNotFoundError: No module named 'aima_ugc.adapters.providers.registry'`；
- `ImportError: cannot import name 'ProviderConfigV1' from 'aima_ugc.contracts.collection'`；
- `Interrupted: 2 errors during collection`；
- pytest 退出码 2。

失败来自目标机器能力尚未实现，不是锁文件、Python、依赖或旧测试故障。

## Green 与中间验证

实现后的 head `4625b8b1654b397490703e07f2bcdc1878db4ed2` 已取得 8 条成功 workflow：

- `CI` run `31855348487`：success；
- `Stage 4 Job Runtime` run `31855348481`：success；
- `Stage 5A Provider Raw` run `31855348497`：success；
- `Stage 5B Collection Execution` run `31855348490`：success；
- `Stage 5C Provider Persistence` run `31855348493`：success；
- `Stage 5D Provider Dispatch` run `31855348488`：success；
- `Stage 6 XHS Vertical Slice` run `31855348513`：success；
- `Stage 7 Provider Config Routing` run `31855348517`：success。

随后两阶段 Review 又增加 Base URL 安全负例、Registration allowlist 自校验、同 Provider 多实例 PostgreSQL 证据，并删除没有当前生产调用方的 `resolve_secret_ref()` 提前实现。最终 head 需要重新通过同一组新鲜门禁后才允许转 Ready/合并。

# 两阶段 Review

## 第一阶段：需求符合性

- Provider Config 是独立资源，不绑定平台；同 Provider 多实例由 Unit + PostgreSQL 真实行为验证。
- Route 保留具体 `provider_config_id`，当前只接 `tikhub + xhs`。
- 没有提前实现 Plan/Budget/Scheduler、Stage 8 API/UI、四平台 Mapper 或真实付费 HTTP。
- Blueprint 02/08 已描述 Provider 管理与平台/Plan 配置两层模型，且明确 Capability 驱动排序/时间等业务参数。

## 第二阶段：代码质量

- 发现 Provider Registration allowlist 自身缺少 URL 结构校验，已改为复用 `normalize_provider_base_url` 并补不安全/重复 allowlist 测试。
- 发现 `resolve_secret_ref()` 当前无生产调用和独立测试价值，已按最小实现删除，只保留本单元实际使用的 `validate_secret_ref`。
- Base URL 同时有 HTTPS Contract 校验与 Provider Registry allowlist；Secret 引用不携带原始 Secret。
- Repository 保持 caller-owned transaction，不在 Repository 内提交；Provider 类型和稳定 UUID 不提供原地修改入口。
- 新 Migration 单链追加到 `20260814_0009`，无历史 Revision 改写。
- 未新增依赖、锁文件、进程、HTTP API 或前端生成物。

# 实际验证计划

最终 PR head 的 GitHub Actions 必须重新提供以下新鲜证据：

```text
uv lock --check
uv run ruff format --check backend tests scripts
uv run ruff check backend tests scripts
uv run mypy backend/src
uv run pytest tests/unit -q
uv run pytest tests/contracts -q
uv run pytest tests/api -q
uv run pytest tests/integration/database/test_provider_config_repository.py -q
uv run python scripts/contracts/generate.py --check
uv run python scripts/contracts/check_compatibility.py
uv run python scripts/quality/check_architecture.py
uv run python scripts/quality/check_table_ownership.py
uv run python scripts/quality/scan_secrets.py
uv run python scripts/quality/check_docs.py
uv run alembic upgrade head
uv run alembic check
uv run alembic downgrade 20260814_0009
uv run alembic upgrade head
uv run alembic downgrade base
uv run alembic upgrade head
```

当前执行宿主无法解析 `github.com`，不能取得本地 checkout；因此没有伪造本地 `git status`、pytest 或 Alembic 输出。该限制不代表用户本地工作区干净，本地未提交/未推送状态仍无法确认。PR GitHub Actions 是本轮可执行的新鲜验证环境。

# 文档影响

已更新：

- `docs/blueprint/README.md`：Stage 7 当前机器进度和剩余单元；
- `docs/blueprint/02-采集系统与数据标准化.md`：Provider Config、Plan/Run 引用、Secret/SSRF/预算身份；
- `docs/blueprint/08-采集策略与平台能力.md`：多 Provider Config、前端 Provider 管理/平台采集两层模型、Capability 和 Budget 语义；
- `docs/collection/README.md`：开发者采集总览与调试入口；
- System/Collection 模块 README：当前 Owner、机器入口和限制。

已检查但未修改：

- `docs/blueprint/03-数据库与文件存储.md` 已列 `provider_configs` 并要求预算绑定稳定 Provider 配置身份；本 Change 的第十条 Revision是该目标的首个实际落地，不需要重写其余 Schema 设计；
- `docs/blueprint/07-技术决策与实施门禁.md` 已冻结 Platform/Provider 解耦、稳定 Provider 配置预算身份和 Stage 7 Provider/Collection Go；详细多实例与前端选择语义由 02/08 维护，不制造重复第二套字段定义。

# 兼容、Migration、部署和回滚

- 新增独立 Provider Config/Route Contract，不删除或改写现有 Contract 字段。
- 新增 `provider_configs` 和 Revision `20260815_0010`，不改写历史 Revision。
- 当前 Stage 5C `provider_requests.provider` 保持兼容；后续 Plan/Budget Change 再以独立 Migration 引入 `provider_config_id` 外键，不在本 Change 反向改写既有 Request 历史。
- 不新增依赖、不升级锁文件。
- 不改变生产进程数量或部署方式；生产环境未部署。
- 回滚先停止使用新增 Provider Config/Route，再 downgrade `20260815_0010 → 20260814_0009`；本单元无旧数据回填。

# Git

- 基线 main：`ccf5fdfbb74798c036de544b250d464cfe2de855`
- 开发分支：`feature/stage7-provider-config-routing`
- PR：#36，Draft；最终 CI 成功后再转 Ready
- 正确 Red：head `2ffaf8256c5f0568092621922f68900ea9dad4a7`，run `31854907454` / job `94937704883`
- 中间 Green：head `4625b8b1654b397490703e07f2bcdc1878db4ed2`，8 条相关 workflow success
- 最终 PR CI：待最新 head 完成
- 合并：未执行
- 合并后 main 验证：未执行
- Change 归档：未执行；仍在 `changes/active/`
- 生产部署：未执行
