---
schema: coding-change/v1
id: CHG-20260905-192745-env-compose-config-contract
title: 统一本地与生产 env / Compose 配置契约
level: L3
status: in_progress
owner: dingyuwen777
branch: fix/env-compose-config-contract
created: 2026-09-05
updated: 2026-09-05
completion_gate: required
depends_on: []
affected_areas:
  - runtime-config
  - docker-compose
  - local-development
  - deployment-docs
affected_paths:
  - env.local.example
  - env.production.example
  - compose.yaml
  - compose.windows.yaml
  - scripts/dev/local_runtime.py
  - tests/unit/test_env_compose_config_contract.py
  - docs/02_环境运行与部署.md
contracts:
  - AIMA Runtime Environment Configuration Contract
  - AIMA Historical Import Path Contract
data_changes: []
---

# 目标

建立单一、可验证的环境配置边界：本地源码与本地 Docker Compose 共用 `env.local`，服务器/Production Compose 使用 `env.production`；历史导入目录同时具有明确的宿主路径与运行时路径语义，并由配置真正驱动 Compose environment 与 bind target。

# 成功标准

- [ ] 本地源码 launcher 继续读取 `env.local`，并把历史导入目录解析为宿主机可访问路径。
- [ ] 本地 Linux/WSL/Windows Compose 读取 `env.local`，合法 Docker-only 字段不会被源码 launcher 误报。
- [ ] 服务器 Compose 读取 `env.production`，显式暴露 `AIMA_HISTORICAL_IMPORT_ROOT` 且保留旧默认兼容。
- [ ] Compose backend environment 与所有历史导入 bind target 使用同一个 runtime root 配置。
- [ ] 定向文档与永久回归同步新的配置职责。

# 范围

- `env.local.example`：扩展为本地源码 + 本地 Compose 的共享模板，并明确 host/runtime 路径语义。
- `env.production.example`：收敛为服务器/Production Compose 模板并补齐历史 runtime root。
- `compose.yaml` / `compose.windows.yaml`：让历史 runtime root 真正可配置。
- `scripts/dev/local_runtime.py`：区分源码消费字段、合法共享字段与真正未知字段，并保持旧 env.local 兼容。
- 新增最小配置契约单元回归。
- 定向同步 `docs/02_环境运行与部署.md`。

# 非目标

- 不改变 HTTP API、Pydantic Contract、Schema/Migration 或业务数据语义。
- 不改变 TikHub/LLM Provider 业务行为、Secret File 分层或正式 Release artifact 结构。
- 不升级 Runtime、依赖、镜像版本或包管理器。
- 不清理与本次 env/Compose 契约无关的历史配置项。

# 必须保持不变

- 既有服务器 `env.production` 未设置 `AIMA_HISTORICAL_IMPORT_ROOT` 时仍回退 `/data/aima-historical-input`。
- 既有本地 `env.local` 只设置 `AIMA_HISTORICAL_IMPORT_ROOT=.runtime/historical-input` 时，源码 launcher 仍能工作。
- PostgreSQL 密码、Cursor signing key、TikHub/LLM API Key 的 Secret 存储机制不变。
- API/Worker/Scheduler、数据库、前端业务能力与网络 service-name 通信不变。

# 方案比较与关键决策

1. **继续固定容器 runtime root，只补文档/示例**：改动最小，但配置仍不会真正控制消费者，会保留“假配置”，不满足 #364。
2. **推荐：host/runtime 双路径 + 同一环境模板按运行方式消费**：`AIMA_HISTORICAL_IMPORT_HOST_ROOT` 表示宿主 source，`AIMA_HISTORICAL_IMPORT_ROOT` 表示容器/runtime target；Compose 同时用 runtime root 驱动 environment 与 mount target；源码 launcher 优先使用 host root，旧 runtime root 作为兼容回退。该方案满足一份 `env.local` 同时支持源码和本地 Docker，且不改变服务器默认行为。
3. **拆成 env.local.source / env.local.compose / env.production**：语义直观但增加第三套配置事实和同步成本，违反用户已确认的“本地统一 env.local”目标。

选择方案 2。公开配置变化保持向后兼容；无数据库 Migration。回滚只需恢复 env 模板、Compose 插值、launcher 解析、回归和文档。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 本地源码使用 env.local，宿主历史路径可访问且合法 Docker 字段不误报 | #364 / AC1 | not_satisfied | 当前 main 的 env.local 仍只面向源码，launcher 尚未区分共享 Docker 字段。 |
| R2 | 本地 Compose 使用 env.local，host source/runtime target 分离且 environment 与 target 一致 | #364 / AC2 | not_satisfied | 当前 Compose runtime target 仍硬编码 `/data/aima-historical-input`。 |
| R3 | 服务器使用 env.production，模板显式提供 runtime root 且旧默认兼容 | #364 / AC3 | not_satisfied | 当前 `env.production.example` 尚无 `AIMA_HISTORICAL_IMPORT_ROOT`。 |
| R4 | 运行文档明确三种入口并显式使用正确 --env-file | #364 / AC4 | not_satisfied | 当前 `docs/02` 仍写本地 Compose 使用 env.production。 |
| R5 | 永久回归防止 env/Compose/launcher 再次漂移 | #364 / AC5 | not_satisfied | 当前尚无该配置契约专项回归。 |
| R6 | API、Schema/Migration、依赖/Runtime 和 Secret 机制保持不变 | #364 / AC6 | not_satisfied | 待实现 diff 与 current-head CI/Review 证明。 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | launcher env 解析、host/runtime 路径选择、unknown-key 分类。 |
| 接口 / 契约 | required | env 示例、Compose 插值与 runtime Settings 的配置键一致性。 |
| 集成 / 持久化 / 运行依赖 | required | Docker Compose config / Runtime CI 对 canonical 与 Windows override 的真实解析。 |
| 用户 / 工作流验收 | required | 文档中的本地源码、本地 Compose、服务器 Compose 三条操作路径与机器事实一致。 |
| 跨组件关键路径 | not_applicable | 不改变产品 API/DB/Worker/前端业务接线；本次风险集中在配置/运行入口。 |
| 外部依赖 / 供应方探测 | not_applicable | 不改变 TikHub/LLM 外部接口，不需要付费或远端 Probe。 |
| 构建 / 打包 / 运行 | required | PR current-head Runtime/CI 与 Compose 解析必须成功。 |
| 文档 / 治理 / 其他 | required | Issue/Change/PR 追溯、docs check、Change completion gate。 |

# 完成审计

- [ ] upstream_re_read：进入 Ready 前重读 #364 AC1-AC6 与本轮用户确认目标。
- [ ] change_coverage：进入 Ready 前逐条确认 R1-R6 均有实现和直接证据。
- [ ] reverse_audit：进入 Ready 前从 env 示例反查 Compose/launcher/Settings/文档消费者，并核对 host/runtime 路径无反向漂移。
- [ ] unresolved_cleared：进入 Ready 前清零 not_satisfied；未验证内容不得写成已完成。

# 任务

- [x] 恢复当前 env、Compose、launcher、Settings、文档和历史提交事实。
- [x] 比较三种方案并确认 host/runtime 双路径方案。
- [x] 创建并写后重读 Requirement Source #364。
- [ ] 建立配置契约失败回归并实现 env/Compose/launcher 修复。
- [ ] 定向同步运行部署文档。
- [ ] 执行 targeted validation、current-head CI 与两阶段复核。
- [ ] 达到 `ready_for_review` 后 guarded merge，并验证 main fresh、自动 Change archive、Issue Closure 与分支清理。

# 验证

## 计划

- 新增 `tests/unit/test_env_compose_config_contract.py`，直接断言历史 host/runtime 配置、Compose target、共享 env.local 合法字段和生产模板边界。
- 使用仓库当前 Python/pytest/quality 入口运行 targeted/unit/docs/governance checks。
- 使用 PR current-head GitHub Actions 取得 Runtime/Compose 与正式 CI 证据；不以静态测试冒充真实 Docker 运行。

# 文档影响

`docs/02_环境运行与部署.md` 为本次唯一直接承担运行入口的长期文档，使用 targeted 更新；不机械扫描或重写其他 Markdown。

# 交付

- Requirement Source：#364
- PR：待创建
- merge：本轮用户已授权在 required 门禁通过后合并 `main`
- 发布/部署：不适用；本次只修改仓库配置契约，不执行生产部署。