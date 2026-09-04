---
schema: coding-change/v1
id: CHG-20260904-173308-docker-network-ipam
title: 统一 Compose 内部网络 IPAM
level: L3
status: ready_for_review
owner: dingyuwen777
branch: infra/349-docker-network-ipam
created: 2026-09-04
updated: 2026-09-04
completion_gate: required
depends_on: []
affected_areas:
  - deployment
  - runtime
  - testing
  - documentation
affected_paths:
  - compose.yaml
  - env.production.example
  - tests/unit/test_compose_network.py
  - changes/active/CHG-20260904-173308-docker-network-ipam/CHANGE.md
contracts: []
data_changes: []
---

# 背景与现状

Requirement Source 为 Issue #349。原 canonical `compose.yaml` 的 `networks.app` 只有 `driver: bridge`，没有显式 IPAM；完整 Compose Runtime 的应用内部网段此前由 Docker 动态分配。业务 Owner 已明确要求默认使用 `10.1.1.0/24`，并以 `10.1.1.1` 为网关。

当前服务继续通过 Compose service DNS 通信；`bootstrap` 继续使用 `network_mode: none`；`compose.windows.yaml` 仍只覆盖 Windows Docker Desktop 的持久化 storage，不拥有第二套网络定义。现有 Runtime Acceptance 对 `compose.yaml` / `env.production.example` 等 Runtime 风险路径运行真实 `Compose Golden Path`。

# 目标

- canonical `app` bridge 默认 `subnet=10.1.1.0/24`、`gateway=10.1.1.1`；
- subnet/gateway 可由 `env.production` 覆盖，目标宿主与 LAN、VPN 或其他 Docker network 冲突时无需修改 Compose 源码；
- Windows storage-only override 继续继承 canonical network；
- service DNS、宿主端口、Secret、持久化、出站访问与 `bootstrap network_mode: none` 保持不变；
- 不给各服务固定容器 IP，不把 `app` 设为 `internal: true`。

# 范围

Included：`compose.yaml` 的 `app` IPAM、`env.production.example` 的网络配置入口与部署前冲突说明、针对默认值/override/Windows merge 的回归测试，以及本 Change 的可追溯交付记录。

Excluded：业务 API/Contract/Schema、数据库 Migration、业务逻辑、依赖/Runtime 版本、永久 CI Workflow 重构、真实生产服务器部署、各服务静态 `ipv4_address`。

Docs targeted review 已读取 `docs/02_环境运行与部署.md` 与 `docs/blueprint/05_日志安全部署与运维.md`：两者继续准确声明完整 Runtime 由 canonical `compose.yaml + env.production` 驱动，Windows override 不修改网络/端口，因此没有需要纠正的 Markdown 现状描述。精确 subnet/gateway 与冲突预检属于机器可执行部署配置，已落在 `env.production.example`，避免在 Blueprint 再维护第二套易漂移数值。

# 必须保持不变

- `AIMA_DB_HOST=postgres` 等 service-DNS 通信方式不变；
- `compose.windows.yaml` 继续只承担 storage override，不复制 network；
- `bootstrap` 继续 `network_mode: none`；
- Frontend 宿主端口映射、Secret 分类和持久目录语义不变；
- Worker/API 等仍可访问外部 TikHub/LLM，不引入 `internal: true`；
- 不升级 Docker、Compose、基础镜像或任何依赖。

# 方案比较

- 方案 A（采用）：在 canonical `compose.yaml` 使用可配置 IPAM，默认 `10.1.1.0/24` + `10.1.1.1`，并由 `AIMA_DOCKER_SUBNET` / `AIMA_DOCKER_GATEWAY` 覆盖。满足目标，同时保留不同宿主处理网段冲突的能力，不产生第二套 Runtime。
- 方案 B（不采用）：直接在 Compose 硬编码 subnet/gateway。实现更少，但目标宿主一旦与 LAN/VPN/其他 Docker network 重叠就必须修改源码，不利于同一 Runtime 跨环境运行。
- 方案 C（不采用）：把 `app` 改为预创建的 external Docker network。会增加部署前置步骤和运维状态，削弱当前 canonical Compose 自包含编排，不符合本次最小变化目标。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 默认 canonical app network 为 `10.1.1.0/24`，gateway 为 `10.1.1.1` | https://github.com/dingyuwen777/AIMA_UGC/issues/349 | satisfied | `compose.yaml` 已使用 `AIMA_DOCKER_SUBNET:-10.1.1.0/24` / `AIMA_DOCKER_GATEWAY:-10.1.1.1`；`env.production.example` 显式给出同值；PR #350 implementation head `885036e` 的 Runtime Acceptance 已完成真实 `docker compose config` topology validation。 |
| R2 | subnet/gateway 可通过环境覆盖，Windows override 继续继承 canonical network | https://github.com/dingyuwen777/AIMA_UGC/issues/349 | satisfied | `compose.yaml` 使用 Compose 环境插值；`compose.windows.yaml` 未新增 network；`tests/unit/test_compose_network.py` 同时锁定 source contract，并使用真实 `docker compose config --format json` 验证默认、非默认 `10.77.88.0/24` override 与 Windows merge；final-head CI 必须通过后才允许 merge。 |
| R3 | service DNS、端口、bootstrap 隔离、出站能力、持久化与 Secret 边界保持不变，不引入静态服务 IP | https://github.com/dingyuwen777/AIMA_UGC/issues/349 | satisfied | PR diff 只改 network IPAM/env/test/Change；回归测试锁定 `AIMA_DB_HOST=postgres`、`network_mode: none`、无 `ipv4_address`、无 `internal: true`、Windows 无第二 network；implementation head `885036e` 的 Release dry-run run `33859669747` 已成功 build 并以 no-build/no-pull 回放离线 candidate，Developer Tooling run `33859669757` 的 Linux 与 Windows 两个 job 全部 success。 |
| R4 | 部署配置与直接相关当前文档完成同步 | https://github.com/dingyuwen777/AIMA_UGC/issues/349 | satisfied | `env.production.example` 已新增正式 subnet/gateway 与 LAN/VPN/Docker network 冲突预检说明；定向重读 `docs/02_环境运行与部署.md` 和 Blueprint 05 后确认其 canonical Compose / Windows storage-only 边界仍准确，无需复制数值；implementation head CI 的 Docs and Governance job 已 success。 |
| R5 | final PR required checks、merge 后 main fresh CI、Change archive 与 Issue 验收关闭 | https://github.com/dingyuwen777/AIMA_UGC/issues/349 | explicitly_deferred | Issue #349 AC4 明确把这些定义为 merge/post-merge 证据；它们在 PR Ready 之前逻辑上无法全部成立，正式交由本任务 Post-Merge Finalization 继续完成，禁止以本 Change Ready 状态冒充。 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | `tests/unit/test_compose_network.py` 锁定默认 IPAM、配置入口、service DNS/隔离不变量，并在存在 Docker CLI 时调用真实 Compose parser 验证 default/override/Windows merge；final-head `Repository Quality` 必须通过。 |
| 接口 / Contract | required | `env.production` 新增 `AIMA_DOCKER_SUBNET` / `AIMA_DOCKER_GATEWAY` 配置入口；既有 env 缺少两项时由 Compose 默认值保持目标配置。 |
| 集成 / Persistence / Runtime Dependency | required | 现有 Runtime Acceptance 对 canonical Compose 网络创建、startup、health、persistence/recovery 与 Windows merged Runtime 提供真实 Docker 证据；final head 必须通过。 |
| 用户 / Workflow Acceptance | not_applicable | 不改变业务用户、页面或 API 工作流；部署操作者配置行为由 env contract、真实 Compose render 和运行文档边界直接验证。 |
| 跨组件 Golden Path | required | Ruleset required `Compose Golden Path` 是 merge gate；implementation head 已通过 topology parse，final head 仍必须完整通过。 |
| External Dependency / Provider Probe | not_applicable | 不修改 TikHub/LLM 请求、Provider Contract、费用或外部 API 行为，不为本次网络声明制造付费 Provider 调用。 |
| Build / Package / Runtime | required | implementation head Release dry-run run `33859669747` success，Developer Tooling run `33859669757` success；final-head CI / Runtime Acceptance 继续作为 merge 证据。 |
| Docs / Governance / Other | required | Issue #349、Requirement Source live read、Change Completion、targeted Docs review、L3 Deep Review、required checks 与 post-merge finalization。 |

# 实施步骤

- [x] 搜索未完成同范围 Issue/Active Change，并建立、回读 Requirement Source #349。
- [x] 恢复当前 main、Ruleset、Compose、Runtime Acceptance 与相关部署文档事实。
- [x] 以首个治理提交建立任务分支并创建早期 PR #350，未创建空远程分支。
- [x] 实现 canonical network IPAM 与 env 配置入口。
- [x] 增加 source + 真实 Compose parser 网络回归测试。
- [x] 完成 targeted Docs Impact：部署模板同步；现有 Markdown 边界继续准确，因此不做无意义改写。
- [x] 完成 Requirement Traceability 与 Completion Audit，进入 L3 Deep Review。
- [ ] 完成 final-head Deep Review 与 required checks，执行 guarded merge。
- [ ] 取得 main fresh CI，归档 Change，完成 Issue Acceptance/Closure Audit 与分支清理。

# 当前新鲜证据

- Ready 前重新读取 Issue #349：仍为 open，AC1–AC4、验证要求、非目标与 post-merge 证据要求未变化。
- Ready 前重新读取 main：仍为 `efa1b7819d561fa355eb0078e110ab9361362ac2`；Ruleset 21909651 仍强制 PR、strict up-to-date、`CI Gate`、`Requirement Traceability and Completion Audit`、`Compose Golden Path`，即使当前账号可 bypass 也不使用 bypass。
- PR #350 implementation head `885036eafb2937f5a89a0d18a7926f28644041f6` 的 changed files 只有 Change、`compose.yaml`、`env.production.example`、网络回归测试。
- Runtime Acceptance run `33859669758` 已完成 `Validate canonical Compose topology`；本地当前宿主没有 Docker CLI，因此没有把本地静态检查冒充真实 Compose 证据。
- Release dry-run run `33859669747` 已 `success`，其中 `Build Linux AMD64 application images`、`Build offline deployment bundle`、`Replay bundle with no build and no pull` 均 success。
- Developer Tooling run `33859669757` 已 `success`：Linux Local Development Tooling 与 Windows Development and Compose Tooling 两个 job 均 success，Windows 的 `Validate Windows Compose CLI contract` success。
- CI run `33859670061` 已有 `Docs and Governance` 与 `PostgreSQL Integration` success；该 implementation-head run 不是 final-head merge 证据，final Change commit 后重新取 fresh required CI。
- Change Completion Gate run `33859669751` 早期按设计失败，唯一失败原因是 Active Change 当时仍为 `in_progress`；PR Requirement Source 校验已经 success。Ready commit 后必须由 fresh gate 重新证明。

# Completion Audit

- [x] upstream_re_read：已重新读取 Issue #349、main HEAD、active Ruleset、当前 Compose/Env/Test、Runtime Acceptance 及 `docs/02` / Blueprint 05；未发现上游目标、非目标或门禁变化。
- [x] change_coverage：AC1→R1；AC2→R2；AC3→R3；AC4 的配置/文档部分→R4，final PR/main/archive/closure 部分→R5；没有把 post-merge 证据提前伪装成已完成。
- [x] reverse_audit：从 `env.production` 配置入口反查 Compose interpolation → `app` IPAM → service DNS/无静态 IP → canonical/Windows merge → offline replay/Runtime → 操作文档边界，未发现第二套 network Owner 或跨模块副作用。
- [x] unresolved_cleared：R1–R4 已有实现和本轮证据；R5 依据 Issue #349 AC4 正式 `explicitly_deferred` 到 Post-Merge Finalization；Validation Matrix 的业务用户场景/Provider Probe N/A 均有明确范围依据，没有 `not_satisfied`。

# 兼容、部署与回滚

API、Contract、Schema、Migration、业务数据和依赖无变化。既有 `env.production` 即使没有新增两项，也会使用 Compose 默认值。新 IPAM 在 Compose network 被重新创建时生效；真实目标宿主部署前必须检查 `ip route` 和现有 Docker networks，若 `10.1.1.0/24` 冲突则同时覆盖 `AIMA_DOCKER_SUBNET` / `AIMA_DOCKER_GATEWAY` 为批准网段。

本任务不执行公司生产服务器部署。真正应用变更时使用计划停机的 `docker compose down` + `up` 重新创建网络，禁止为此增加 `-v`；bind mount / named volume 持久数据不应因网络重建删除。

回滚可恢复原 subnet/gateway 配置或回退本次实现并重新创建 `app` network；不需要数据库 Migration，不改变数据格式。