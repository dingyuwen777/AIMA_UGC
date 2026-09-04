---
schema: coding-change/v1
id: CHG-20260904-173308-docker-network-ipam
title: 统一 Compose 内部网络 IPAM
level: L3
status: in_progress
owner: dingyuwen777
branch: infra/349-docker-network-ipam
created: 2026-09-04
updated: 2026-09-04
completion_gate: required
depends_on: []
affected_areas:
  - deployment
  - runtime
  - documentation
affected_paths:
  - compose.yaml
  - env.production.example
  - docs/02_环境运行与部署.md
  - docs/blueprint/05_日志安全部署与运维.md
  - changes/active/CHG-20260904-173308-docker-network-ipam/CHANGE.md
contracts: []
data_changes: []
---

# 背景与现状

Requirement Source 为 Issue #349。当前 canonical `compose.yaml` 的 `networks.app` 只有 `driver: bridge`，没有显式 IPAM；因此完整 Compose Runtime 的应用内部网段由 Docker 动态分配。业务 Owner 已明确要求默认使用 `10.1.1.0/24`，并以 `10.1.1.1` 为网关。

当前服务通过 Compose service DNS 通信；`bootstrap` 使用 `network_mode: none`；`compose.windows.yaml` 只覆盖 Windows Docker Desktop 的持久化 storage，不拥有第二套网络定义。现有 Runtime Acceptance 对 `compose.yaml`、`env.production.example` 等 Runtime 风险路径运行 `Compose Golden Path`。

# 目标

- canonical `app` bridge 默认 `subnet=10.1.1.0/24`、`gateway=10.1.1.1`；
- subnet/gateway 可由 `env.production` 覆盖，避免与具体宿主 LAN、VPN 或其他 Docker network 冲突时必须改源码；
- Windows storage-only override 继续继承 canonical network；
- service DNS、宿主端口、Secret、持久化、出站访问与 `bootstrap network_mode: none` 保持不变；
- 不给各服务固定容器 IP，不把 `app` 设为 `internal: true`。

# 范围

Included：`compose.yaml` 的 `app` IPAM、`env.production.example` 的网络配置入口，以及直接承担完整 Compose 日常运行/部署边界的定向文档同步。

Excluded：业务 API/Contract/Schema、数据库 Migration、业务逻辑、依赖/Runtime 版本、永久 CI Workflow 重构、真实生产服务器部署、各服务静态 `ipv4_address`。

# 必须保持不变

- `AIMA_DB_HOST=postgres` 等 service-DNS 通信方式不变；
- `compose.windows.yaml` 继续只承担 storage override，不复制 network；
- `bootstrap` 继续 `network_mode: none`；
- Frontend 宿主端口映射、Secret 分类和持久目录语义不变；
- Worker/API 等仍可访问外部 TikHub/LLM，不引入 `internal: true`；
- 不升级 Docker、Compose、基础镜像或任何依赖。

# 方案比较

- 方案 A（采用）：在 canonical `compose.yaml` 使用可配置 IPAM，默认 `10.1.1.0/24` + `10.1.1.1`，并由 `AIMA_DOCKER_SUBNET` / `AIMA_DOCKER_GATEWAY` 覆盖。满足目标，同时保留不同宿主处理网段冲突的能力，不产生第二套 Runtime。
- 方案 B（不采用）：直接在 Compose 硬编码 subnet/gateway。实现最少，但目标宿主一旦与 LAN/VPN/其他 Docker network 重叠就必须修改源码，不利于同一 Runtime 跨环境运行。
- 方案 C（不采用）：把 `app` 改为预创建的 external Docker network。会增加部署前置步骤和运维状态，削弱当前 canonical Compose 自包含编排，不符合本次最小变化目标。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 默认 canonical app network 为 `10.1.1.0/24`，gateway 为 `10.1.1.1` | https://github.com/dingyuwen777/AIMA_UGC/issues/349 | not_satisfied | 待实现并渲染 canonical Compose 验证 |
| R2 | subnet/gateway 可通过环境覆盖，Windows override 继续继承 canonical network | https://github.com/dingyuwen777/AIMA_UGC/issues/349 | not_satisfied | 待实现 default/override/Windows merge 配置验证 |
| R3 | service DNS、端口、bootstrap 隔离、出站能力、持久化与 Secret 边界保持不变，不引入静态服务 IP | https://github.com/dingyuwen777/AIMA_UGC/issues/349 | not_satisfied | 待 diff 审计与 Compose Golden Path 证明 |
| R4 | 配置与直接相关部署文档同步；PR required checks 与 merge 后 main fresh CI 通过 | https://github.com/dingyuwen777/AIMA_UGC/issues/349 | not_satisfied | 待 Docs targeted review、PR/main fresh CI |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | not_applicable | 本次是 declarative Compose/runtime 配置，不存在独立函数行为；以配置解析、Runtime 与 Golden Path 证据替代形式化 Red/Green |
| 接口 / Contract | required | `env.production` 新增 subnet/gateway 配置入口及默认/override 解析语义 |
| 集成 / Persistence / Runtime Dependency | required | Docker Compose 合并后的 `app` IPAM、服务拓扑与网络创建/启动边界 |
| 用户 / Workflow Acceptance | not_applicable | 不修改业务用户或 API 调用方工作流；部署操作者配置行为由 Build/Runtime + 文档直接验证 |
| 跨组件 Golden Path | required | 现有 `Compose Golden Path` 对 canonical stack startup/health/persistence/recovery 的 current-head 证明 |
| External Dependency / Provider Probe | not_applicable | 不修改 TikHub/LLM 接口或 Provider 当前事实 |
| Build / Package / Runtime | required | canonical/default/override/Windows merged `docker compose config`，以及 Runtime Acceptance |
| Docs / Governance / Other | required | Issue #349、Change Completion、targeted Docs、Deep Review、required checks、main fresh CI |

# 实施步骤

- [x] 搜索未完成同范围 Issue/Active Change，并建立、回读 Requirement Source #349。
- [x] 恢复当前 main、Ruleset、Compose、Runtime Acceptance 与相关部署文档事实。
- [ ] 建立首个治理提交和任务分支，创建早期 PR。
- [ ] 实现 canonical network IPAM 与 env 配置入口。
- [ ] 同步直接相关部署文档，不扩大到无关 Roadmap/业务文档。
- [ ] 执行 default/override/Windows merge 配置验证和必要静态检查。
- [ ] 完成 Requirement Traceability、Completion Audit 与 Deep Review。
- [ ] 取得 PR required checks/current-head 证据并 guarded merge。
- [ ] 取得 main fresh CI，归档 Change，完成 Issue Acceptance/Closure Audit 与分支清理。

# 当前新鲜证据

- 2026-09-04：main HEAD `efa1b7819d561fa355eb0078e110ab9361362ac2`；Ruleset 21909651 要求 PR、`CI Gate`、`Requirement Traceability and Completion Audit`、`Compose Golden Path`。
- open Issue 搜索未发现与 Docker network/IPAM/`10.1.1.0/24` 同范围未完成事项；`changes/active` 当前不存在，`changes/` 只有 archive。
- Issue #349 已创建并写后重读；标题、正文、AC1–AC4 task list、验证要求和上游事实源均存在。
- 当前 `compose.yaml` 的 `app` network 仅有 `driver: bridge`；`env.production.example` 无 Docker subnet/gateway；Windows override 不定义 network。
- 当前 `.github/workflows/runtime.yml` 会把 `compose.yaml` / `env.production.example` 判为 Runtime risk，并运行 `Compose Golden Path` 的 `docker compose config` 与真实 stack startup/health/persistence/recovery。

# Completion Audit

- [ ] upstream_re_read：Ready 前重新读取 Issue #349、当前 main、Ruleset、Compose/Env、Runtime Acceptance 与目标文档。
- [ ] change_coverage：逐条比较 AC1–AC4 与 R1–R4、实现、验证和文档，确认无 requirement omission。
- [ ] reverse_audit：从 env/config → Compose render → app network → service DNS/runtime → Golden Path → operator docs 反查完整链路，并复核 Validation Matrix 证据等级。
- [ ] unresolved_cleared：Ready 前清零 `not_satisfied`，所有 N/A/未执行生产部署都有明确依据。

# 兼容、部署与回滚

API、Contract、Schema、Migration、业务数据和依赖无变化。既有 `env.production` 即使没有新增两项，也会使用 Compose 默认值。新 IPAM 在 Compose network 被重新创建时生效；目标宿主应先检查 `ip route` 和现有 Docker networks，若 `10.1.1.0/24` 冲突则通过 env 覆盖为批准网段。

回滚可恢复原 Compose 网络配置或回退本次提交并重新创建 `app` network；不需要数据库 Migration，不删除 bind mount / named volume 持久数据。