---
schema: coding-change/v1
id: CHG-20260905-192745-env-compose-config-contract
title: 统一本地与生产 env / Compose 配置契约
level: L3
status: done
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
  - tests/unit/test_local_dev_runtime.py
  - .github/workflows/tooling.yml
  - docs/02_环境运行与部署.md
  - docs/guides/03_Windows Docker Desktop Compose运行.md
contracts:
  - AIMA Runtime Environment Configuration Contract
  - AIMA Historical Import Path Contract
data_changes: []
---

# 目标

建立单一、可验证的环境配置边界：本地源码与本地 Docker Compose 共用 `env.local`，服务器/Production Compose 使用 `env.production`；历史导入目录同时具有明确的宿主路径与运行时路径语义，并由配置真正驱动 Compose environment 与 bind target。

# 成功标准

- [x] 本地源码 launcher 继续读取 `env.local`，并把历史导入目录解析为宿主机可访问路径。
- [x] 本地 Linux/WSL/Windows Compose 读取 `env.local`，合法 Docker-only 字段不会被源码 launcher 误报。
- [x] 服务器 Compose 读取 `env.production`，显式暴露 `AIMA_HISTORICAL_IMPORT_ROOT` 且保留旧默认兼容。
- [x] Compose backend environment 与所有历史导入 bind target 使用同一个 runtime root 配置。
- [x] 定向文档、Windows Tooling 与永久配置契约回归同步新的配置职责。

# 范围

- `env.local.example`：扩展为本地源码 + 本地 Compose 的共享模板，并明确 host/runtime 路径语义。
- `env.production.example`：收敛为服务器/Production Compose 模板并补齐历史 runtime root。
- `compose.yaml` / `compose.windows.yaml`：让历史 runtime root 真正可配置。
- `scripts/dev/local_runtime.py`：区分源码消费字段、合法共享字段与真正未知字段，并保持旧 env.local 兼容。
- `tests/unit/test_env_compose_config_contract.py`：锁定 env / Compose / launcher / 文档 / Tooling 契约。
- `tests/unit/test_local_dev_runtime.py`：同步 `LocalDevConfig` 新增宿主历史路径字段，保持原 Ctrl+C/PostgreSQL 清理回归可运行。
- `.github/workflows/tooling.yml`：Windows Compose CLI 使用正式本地 `env.local` 入口。
- 定向同步 `docs/02_环境运行与部署.md` 与直接受影响的 Windows Compose Guide。
- 反向审计发现 `AIMA_ANALYSIS_RUN_SHARD_SIZE` 已无 Settings/Runtime 消费者且 Shard Size 由 Provider 并发自动计算，因此从 env/Compose/launcher 合法键中删除这一同类“假配置”；保留仍真实消费的 `AIMA_ANALYSIS_RUN_MAX_IN_FLIGHT_JOBS`。

# 非目标

- 不改变 HTTP API、Pydantic Contract、Schema/Migration 或业务数据语义。
- 不改变 TikHub/LLM Provider 业务行为、Secret File 分层或正式 Release artifact 结构。
- 不升级 Runtime、依赖、镜像版本或包管理器。
- 不清理与本次 env/Compose 配置契约无关的历史配置项。

# 必须保持不变

- 既有服务器 `env.production` 未设置 `AIMA_HISTORICAL_IMPORT_ROOT` 时仍回退 `/data/aima-historical-input`。
- 既有本地 `env.local` 只设置 `AIMA_HISTORICAL_IMPORT_ROOT=.runtime/historical-input` 时，源码 launcher 仍能工作。
- PostgreSQL 密码、Cursor signing key、TikHub/LLM API Key 的 Secret 存储机制不变。
- API/Worker/Scheduler、数据库、前端业务能力与网络 service-name 通信不变。

# 方案比较与关键决策

1. **继续固定容器 runtime root，只补文档/示例**：改动最小，但配置仍不会真正控制消费者，会保留“假配置”，不满足 #364。
2. **采用 host/runtime 双路径 + 同一环境模板按运行方式消费**：`AIMA_HISTORICAL_IMPORT_HOST_ROOT` 表示宿主 source，`AIMA_HISTORICAL_IMPORT_ROOT` 表示容器/runtime target；Compose 同时用 runtime root 驱动 environment 与 mount target；源码 launcher 优先使用 host root，旧 runtime root 作为兼容回退。该方案满足一份 `env.local` 同时支持源码和本地 Docker，且不改变服务器默认行为。
3. **拆成 env.local.source / env.local.compose / env.production**：语义直观但增加第三套配置事实和同步成本，违反用户已确认的“本地统一 env.local”目标。

选择方案 2。公开配置变化保持向后兼容；无数据库 Migration。回滚只需恢复 env 模板、Compose 插值、launcher 解析、回归、Tooling 和文档。

CI 分层保持成本边界：`env.local.example` 已由 Developer Tooling workflow 的 paths 监听，并由 Windows `docker compose config` + 本配置契约回归验证；不把单纯本地模板变更升级为昂贵的 Runtime Golden Path。`env.production.example`、`compose.yaml`、`compose.windows.yaml` 仍属于 Runtime Acceptance 风险面，本 PR 本身修改 Compose，因此必须取得真实 Runtime current-head 证据后才可合并。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 本地源码使用 env.local，宿主历史路径可访问且合法 Docker 字段不误报 | #364 / AC1 | satisfied | `env.local.example` 同时声明 host/runtime；`LocalDevConfig.source_historical_import_root` 优先 HOST_ROOT，`_KNOWN_LOCAL_KEYS` 区分合法共享键；新增回归覆盖新模板与旧 root-only 兼容。 |
| R2 | 本地 Compose 使用 env.local，host source/runtime target 分离且 environment 与 target 一致 | #364 / AC2 | satisfied | canonical/Windows 8 个历史 bind target 均由 `${AIMA_HISTORICAL_IMPORT_ROOT:-/data/aima-historical-input}` 驱动；backend environment 使用同一变量；Windows Tooling 改为 `env.local` 做真实 Compose CLI config。 |
| R3 | 服务器使用 env.production，模板显式提供 runtime root 且旧默认兼容 | #364 / AC3 | satisfied | `env.production.example` 显式提供 `AIMA_HISTORICAL_IMPORT_ROOT=/data/aima-historical-input`；Compose 插值仍保留同值 fallback，旧服务器 env 无需迁移即可维持现有行为。 |
| R4 | 运行文档明确三种入口并显式使用正确 --env-file | #364 / AC4 | satisfied | `docs/02_环境运行与部署.md` 与 Windows Guide 均明确本地源码/本地 Compose=`env.local`、服务器=`env.production`，Linux/WSL/Windows/服务器命令均显式写对应 `--env-file`。 |
| R5 | 永久回归防止 env/Compose/launcher 再次漂移 | #364 / AC5 | satisfied | `tests/unit/test_env_compose_config_contract.py` 直接锁定共享 env、legacy fallback、host/runtime target、文档/Tooling入口，并系统检查 Compose AIMA 插值同时存在于两份 example env；`tests/unit/test_local_dev_runtime.py` 同步新增字段以保持既有 launcher 生命周期回归。 |
| R6 | API、Schema/Migration、依赖/Runtime 和 Secret 机制保持不变 | #364 / AC6 | satisfied | PR 反向 diff 审计的变更面仅为 env/Compose/launcher/Tooling/测试/运行文档/Change；未改 API、Migration、lockfile、镜像/Runtime version、Provider Secret 实现。Current-head CI/Runtime 仍作为 merge 前执行证据。 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | `test_env_compose_config_contract.py`：launcher env 解析、host/runtime 路径选择、legacy fallback、unknown-key 分类、父进程高级 override 保留；`test_local_dev_runtime.py` 保持既有 launcher 生命周期回归。 |
| 接口 / 契约 | required | env 示例、Compose 插值、Runtime Settings 消费者与 Shard 自动计算代码完成反向审计；不存在 HTTP Contract 变化。 |
| 集成 / 持久化 / 运行依赖 | required | Ready 后由 PR current-head Runtime Acceptance 真实运行 canonical Compose；Windows Tooling 真实执行 merged Compose `config --services`。 |
| 用户 / 工作流验收 | required | 两份长期运行文档中的本地源码、本地 Compose、服务器 Compose 三条操作路径已与机器事实对齐。 |
| 跨组件关键路径 | not_applicable | 不改变产品 API/DB/Worker/前端业务接线；本次风险集中在配置/运行入口。 |
| 外部依赖 / 供应方探测 | not_applicable | 不改变 TikHub/LLM 外部接口，不需要付费或远端 Probe。 |
| 构建 / 打包 / 运行 | required | PR current-head Runtime/CI 与 Compose 解析必须在 merge 前成功；当前 Ready 仅表示实现可进入这些门禁。 |
| 文档 / 治理 / 其他 | required | #364、Change、PR #365 稳定追溯；Ready validator 与 docs/governance checks 由 CI 复核。 |

# 完成审计

- [x] upstream_re_read：2026-09-05 进入 Ready 前重新读取 #364 的目标、范围、兼容条件和 AC1-AC6，并确认没有把“本地 env.local / 服务器 env.production”反向写错。
- [x] change_coverage：逐条将 AC1-AC6 映射到 R1-R6；实现覆盖 env 示例、Compose consumer、source launcher、Windows Tooling、两份直接受影响运行文档和永久回归。
- [x] reverse_audit：从 env 示例反查 Compose、`Settings`、`local_runtime.py`、Analysis Shard 计算、Windows Guide 与 Tooling；发现并修复 Windows Guide/Tooling 的旧 `env.production` 假设、源码父进程高级配置误清理风险，并删除无消费者的 `AIMA_ANALYSIS_RUN_SHARD_SIZE`；后续 Unit 回归暴露的 `LocalDevConfig` 旧构造器也已同步。
- [x] unresolved_cleared：R1-R6 均有当前分支直接实现证据；真实 CI/Runtime 结果尚未冒充完成证据，而被明确保留为 merge 前门禁。

# 任务

- [x] 恢复当前 env、Compose、launcher、Settings、文档和历史提交事实。
- [x] 比较三种方案并确认 host/runtime 双路径方案。
- [x] 创建并写后重读 Requirement Source #364。
- [x] 建立配置契约失败回归并实现 env/Compose/launcher 修复。
- [x] 定向同步运行部署文档和 Windows Compose Guide。
- [x] 反向检查 CI consumer，并让 Windows Tooling 使用 env.local；保留 env.local 本地模板走 Tooling、Production/Compose 走 Runtime 的成本分层。
- [x] 修复 Review 与 CI 新鲜证据暴露的 inherited env 兼容问题、Python 格式/import-order 问题和已有 LocalDevConfig 单测构造器遗漏。
- [ ] PR current-head CI、Runtime Acceptance 与两阶段 Review 通过。
- [ ] guarded merge 后验证 main fresh、自动 Change archive、Issue Closure 与分支清理。

# 验证

## 实现阶段证据

- PR #365 current diff：11 个文件，范围均属于本 Change；`.github/workflows/tooling.yml` patch 仅把 Windows 本地 Compose 从 `env.production` 切换为 `env.local`，没有整文件语义漂移。
- `backend/src/aima_ugc/platform/config/settings.py` 无 `AIMA_ANALYSIS_RUN_SHARD_SIZE` 映射；`backend/src/aima_ugc/modules/analysis/sharding.py` 按 Provider `max_concurrency/max_rps` 计算 Shard；因此已从 env/Compose/launcher 合法键移除该无消费者配置。
- `compose.yaml` 与 `compose.windows.yaml` 的历史 bind target 统一使用 runtime-root 插值；旧默认值仍为 `/data/aima-historical-input`。
- CI #4166 在 HEAD `726d24e11da77618b821bd6e9446e903156339f8` 已证明 Ruff format/lint、mypy、源码前后端 startup smoke、generated Contract 与 docs/governance 通过；Unit 阶段 851 passed / 1 failed，唯一失败为既有测试构造 `LocalDevConfig` 漏传新增 `historical_import_host_root`，已在后续 commit 修复，不能作为最终绿灯。

## merge 前仍必须取得

- 当前最终 HEAD 的 Unit/Contract/API、Developer Tooling、Runtime Acceptance、Release dry-run 与 CI Gate fresh success。
- 两阶段 Review 对最终 HEAD 无阻塞 Finding。

# 文档影响

定向更新 `docs/02_环境运行与部署.md` 与直接面向 Windows 本地 Compose 的 `docs/guides/03_Windows Docker Desktop Compose运行.md`。未机械扫描或重写与本配置入口无关的 Markdown。

# 交付

- Requirement Source：#364
- PR：#365
- merge：本轮用户已授权；仅在 current-head required gate 和 Review 满足后执行。
- 发布/部署：不适用；本次只修改仓库配置契约，不执行生产部署。