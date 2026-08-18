---
schema: rvc-change/v1
id: CHG-20260815-stage7-provider-config-routing
title: 建立 Stage 7 Provider 配置与平台路由基础
level: L3
status: done
owner: dingyuwen777
branch: feature/stage7-provider-config-routing
created: 2026-08-15
updated: 2026-08-15
depends_on: [CHG-20260815-stage7-decision-capability]
affected_areas: [system, collection, provider, contracts, database, testing, documentation]
affected_paths: [backend/src/aima_ugc/modules/system/, backend/src/aima_ugc/modules/collection/, backend/src/aima_ugc/operations/security/, backend/src/aima_ugc/adapters/persistence/postgres/system.py, backend/src/aima_ugc/adapters/providers/, backend/src/aima_ugc/contracts/collection/, backend/src/aima_ugc/database_schema.py, contracts/collection/, migrations/versions/20260815_0010_stage7_provider_configs.py, scripts/contracts/, tests/contracts/test_provider_config_stage7.py, tests/unit/collection/test_provider_routing.py, tests/integration/database/test_provider_config_repository.py, .github/workflows/stage7-provider-config-routing.yml, docs/blueprint/README.md, docs/blueprint/02-采集系统与数据标准化.md, docs/blueprint/08-采集策略与平台能力.md, docs/collection/README.md]
contracts: [provider-config.v1, provider-operations-route.v1]
data_changes: [provider_configs]
---

# 目标与结果

建立 Stage 7 Provider 配置实例与平台选择的稳定机器边界：同一种 Provider 可以存在多个独立配置实例；Provider Config 不绑定平台；平台或后续 Collection Plan 通过稳定 `provider_config_id` 选择具体实例。未来前端分成“Provider 管理”和“采集 Plan”两层，排序、发布时间等业务参数只展示对应 `Provider + Platform + Operation` Capability 实际支持的选项。

已建立 `ProviderConfigV1` / `ProviderPlatformRouteV1`、System Owner `provider_configs`、PostgreSQL Repository、第十条 Revision、Secret 引用校验和 Provider Registry。当前 Registry 只登记已有机器实现的 `tikhub + xhs`；其余四个平台仍按各自 Stage 7 Operation/Fixture/Mapper 门禁推进。

# 成功标准

- [x] `provider_configs` 使用稳定 UUID，并保存 Provider 类型、显示名称、HTTPS Base URL、`secret_ref`、启用状态和时间；不存在 API Key/Token/Cookie 明文列。
- [x] PostgreSQL 集成测试实际创建两个 `provider=tikhub`、不同 UUID 的配置实例，证明同 Provider 多实例成立。
- [x] Provider Config 不绑定平台；`ProviderPlatformRouteV1` 保留具体 `provider_config_id` 并绑定规范化 Platform Capability。
- [x] 禁用 Config、未知 Provider、不允许 Base URL、未实现平台均关闭失败。
- [x] Base URL 必须为 HTTPS，拒绝内嵌用户名/密码、query、fragment；Provider Registration 也复用同一规范化校验并执行 allowlist。
- [x] `secret_ref` 拒绝绝对路径、`..`、反斜杠和非法路径段；原始 Secret 不进入 Contract、数据库、日志、Raw、Job Payload 或读取响应。
- [x] 新 Revision `20260815_0010` 只新增 `provider_configs`，不改写 Stage 1—6 Revision；验证 `20260814_0009 → head` 和 `base → head`。
- [x] Red→Green 证据成立；最终 PR head 与合并后 main 的相关 CI 全部成功。
- [x] Blueprint README、Blueprint 02/08、Collection 总览和 System/Collection README 已同步。
- [x] Blueprint 03/07 已检查：已有稳定 Provider 配置身份和 Platform/Provider 解耦规则，无需为形式制造重复字段定义。

# 范围与非目标

范围：Provider Config 稳定身份、非敏感连接配置、Secret 引用、System 表/Repository、Provider Config/Route Contract、当前 Provider Registry/Capability 接线、Migration、自动化测试与长期文档。

非目标：Stage 8 HTTP API/Vue 页面、可写 SecretStore/SecretService、关键词/词包、Collection Plan/Occurrence、最终 Budget Ledger、Scheduler、真实付费 Provider HTTP Transport、抖音/微博/B站/快手 Operation/Mapper/Capability。

# 必须保持不变

- Platform 与 Provider Config 解耦；同一 Config 可被多个平台复用，同一种 Provider 也可有多个 Config。
- 同一稳定 UUID 的 Provider 类型不原地改写；切换 Provider 时创建新 Config 并显式改引用。
- Secret 不保存或回显明文。
- Provider 私有分页状态不成为业务/前端 Contract。
- Capability 只登记当前代码已经实现并验证的能力。
- Provider 不写业务表，Mapper 不发 HTTP/读数据库，Repository 保持 caller-owned transaction。

# 已确认关键决策

1. 采用方案 A：Provider 配置实例与 Platform Route 解耦。
2. Provider Config 使用稳定 UUID；显示名称可改但不作为外键。
3. Base URL 可配置但必须 HTTPS，并继续受 Provider Adapter 出站 allowlist；当前 TikHub 只允许 `https://api.tikhub.io`。
4. 原始 API Key/Token 不进入 `provider_configs`，只保存服务端 `secret_ref`。
5. 后续 Plan/Run 使用 `provider_config_id`，Run 创建时冻结解析后的 Provider/平台业务策略。
6. Stage 8 如提供凭据编辑页面，必须通过后端安全 SecretStore/SecretService 写入；读取只暴露配置状态或掩码提示，不返回原始 Secret。
7. 前端的平台排序、时间范围、内容类型等选项由当前 `Provider + Platform + Operation` Capability 驱动，不维护第三方参数静态表。

# 方案比较

- **方案 A：Provider Config 与平台选择解耦（采用）**：支持多账号、多平台共享、逐平台替换 Provider，并为后续 Budget 提供稳定身份。
- **方案 B：只用环境变量（拒绝）**：没有稳定数据库身份，无法可靠支撑 Plan Snapshot、Budget 和费用审计。
- **方案 C：Config 直接绑定平台（拒绝）**：会把同一 Provider Account 人为拆成多份，破坏 global budget 与 Platform/Provider 解耦。

# Red → Green

## Red

PR #36 Red head `2ffaf8256c5f0568092621922f68900ea9dad4a7`，Stage 7 run `31854907454` / job `94937704883`：锁定环境安装成功，pytest 在收集阶段因目标能力尚不存在产生 2 个错误：

- `ModuleNotFoundError: No module named 'aima_ugc.adapters.providers.registry'`
- `ImportError: cannot import name 'ProviderConfigV1' from 'aima_ugc.contracts.collection'`

`Interrupted: 2 errors during collection`，退出码 2。失败原因是目标实现缺失，不是依赖或旧测试故障。

## Green 与最终 PR 验证

最终 PR head：`ad8cb849c6cb50417bd5c7919ea32cb7ba0d25fc`。

Stage 7 Unit/Contract：18 passed，0 failed，退出码 0。Stage 7 Quality 中 Ruff format/check、mypy、Contract 生成/兼容、架构、Table Owner、Secret 扫描和文档门禁全部成功。Stage 7 PostgreSQL 在 PostgreSQL 18.4 上完成 `alembic upgrade head`、`alembic check`、Provider Config Repository 集成测试，以及 `20260814_0009 → head`、`base → head` round trip。

最终 PR head 的 8 条相关 workflow 全部 success：CI、Stage 4、Stage 5A、Stage 5B、Stage 5C、Stage 5D、Stage 6、Stage 7 Provider Config Routing。PR 无 review thread、review submission 或讨论阻塞，随后由 Draft 转 Ready 并正常 merge。

# 两阶段 Review

## 需求符合性

- 多 Provider 实例、平台独立选择、Capability 驱动业务参数均有机器事实和测试；没有把 Stage 8 UI 或后续 Plan/Budget/Scheduler 偷跑进本 Change。
- 当前只注册 `tikhub + xhs`，未把其余四平台目标设计冒充当前机器能力。
- Blueprint 02/08 已固化 Provider 管理与平台/Plan 配置的两层模型。

## 代码质量

- Review 发现 Registration allowlist 自身缺少 URL 结构校验，已复用 `normalize_provider_base_url` 并补 HTTP/重复/非 allowlist 等负例。
- Review 发现未使用的 `resolve_secret_ref()` 属提前实现，已删除，只保留当前需求实际使用的 `validate_secret_ref`。
- PostgreSQL 测试补充同 Provider 两个配置实例的真实行为证明。
- Repository 不提交事务；Migration 单链追加；无依赖/锁文件/公共 HTTP API/前端生成物变化。

# 文档同步

已更新：

- `docs/blueprint/README.md`
- `docs/blueprint/02-采集系统与数据标准化.md`
- `docs/blueprint/08-采集策略与平台能力.md`
- `docs/collection/README.md`
- `backend/src/aima_ugc/modules/system/README.md`
- `backend/src/aima_ugc/modules/collection/README.md`

已检查但无需修改：`docs/blueprint/03-数据库与文件存储.md`、`docs/blueprint/07-技术决策与实施门禁.md`，其现有规则与本方案一致。

# 兼容、Migration、部署和回滚

- 新增独立 Provider Config/Route Contract，不删除或改写现有 Contract 字段。
- 新增 `provider_configs` 和 `20260815_0010`，不改写历史 Revision。
- Stage 5C `provider_requests.provider` 暂保持兼容；后续 Plan/Budget Change 再以独立 Migration 引入具体 Provider Config 外键。
- 未新增或升级依赖，未改变生产进程或部署方式，未执行生产部署。
- 回滚：先停止使用新 Provider Config/Route，再执行 `20260815_0010 → 20260814_0009` downgrade；无旧数据回填。

# Git 与集成证据

- 基线 main：`ccf5fdfbb74798c036de544b250d464cfe2de855`
- 开发分支：`feature/stage7-provider-config-routing`（PR 合并后由仓库自动删除）
- PR：#36
- 最终 PR head：`ad8cb849c6cb50417bd5c7919ea32cb7ba0d25fc`
- 合并 commit：`86bcafb84005858af865e506ed4885dbceb2ffb0`
- 合并后 main HEAD：`86bcafb84005858af865e506ed4885dbceb2ffb0`
- 合并后 main：8 条相关 push workflow 全部 `success`；其中 CI run `31856087304`、Stage 6 run `31856087344`，Stage 7 Provider Config Routing 的 Unit/Contract、Quality、PostgreSQL jobs 均 `success`。
- Change：完成后由独立归档 PR 移入 `changes/archive/2026-08/`。
- 生产部署：未执行。

当前执行宿主无法取得用户本地 AIMA_UGC 工作树，因此没有伪造本地 `git status`、本地未推送提交或本地测试证据；上述验证来自本轮 GitHub Actions。