---
schema: coding-change/v1
id: CHG-20260903-runtime-config-control-plane
title: 管理员运行时配置中心与动态 Provider 快照
level: L3
status: done
owner: chatgpt
branch: feat/runtime-config-control-plane
created: 2026-09-03
updated: 2026-09-03
completion_gate: required
depends_on: []
affected_areas:
  - system
  - administration
  - analysis
  - collection
  - runtime
  - security
  - api
  - frontend
  - deployment
affected_paths:
  - backend/src/aima_ugc/modules/system/
  - backend/src/aima_ugc/modules/administration/
  - backend/src/aima_ugc/modules/analysis/
  - backend/src/aima_ugc/modules/collection/
  - backend/src/aima_ugc/bootstrap/
  - backend/src/aima_ugc/platform/security/
  - backend/src/aima_ugc/contracts/administration.py
  - frontend/src/features/admin-configuration/
  - migrations/versions/
  - contracts/openapi/openapi.json
  - compose.yaml
  - compose.windows.yaml
  - tests/
  - docs/
contracts:
  - Admin Provider Configuration HTTP API
  - Analysis Runtime Provider Snapshot
  - Collection Provider Runtime Snapshot
data_changes:
  - provider_configs
  - analysis_content_runs
---

# CHG-20260903-runtime-config-control-plane

- Issue: #317
- Risk: L3
- Status: done
- Implementation PR: #318
- Implementation merge: `b9387a731fe682c67c4eb974846a772069c5ba26`

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 管理员可维护 LLM Base URL、Model、API Key、超时、重试和并发参数 | https://github.com/dingyuwen777/AIMA_UGC/issues/317 | satisfied | PR #318 新增管理员 Provider API、AI 模型配置面板与 Provider Config 持久化；OpenAPI/Orval 和前端构建均通过 |
| R2 | 管理员可维护 TikHub Base URL、API Key、超时、RPS 和并发参数 | https://github.com/dingyuwen777/AIMA_UGC/issues/317 | satisfied | PR #318 将 TikHub 作为 collection Provider 接入同一 Provider Config 控制面，并扩展 Collection Run Provider Snapshot |
| R3 | Prompt 继续由 Analysis Scheme 版本化管理，Draft 不影响 Runtime，Active 版本供新任务使用 | https://github.com/dingyuwen777/AIMA_UGC/issues/317 | satisfied | 现有 Analysis Scheme 发布语义保持不变；新 Analysis Run 同时冻结 active Scheme 与 LLM Provider 安全快照 |
| R4 | 车型等现有管理员业务配置继续以数据库为事实源，不新增重复硬编码真相 | https://github.com/dingyuwen777/AIMA_UGC/issues/317 | satisfied | 车型目录与既有车型快照链路未复制为第二套配置；最终 L3 reverse audit 未发现重复 Runtime truth source |
| R5 | 配置激活后无需重启 API、Worker 或容器，之后的新任务使用当前数据库配置 | https://github.com/dingyuwen777/AIMA_UGC/issues/317 | satisfied | Analysis 创建时解析当前默认 LLM Provider，Collection 创建时冻结当前 Provider revision；Runtime Acceptance 与 main-fresh CI 均成功 |
| R6 | 已创建或运行中的 Run 及同 Run 自动 Retry 保持原配置快照，新 Run 或手工重跑读取最新配置 | https://github.com/dingyuwen777/AIMA_UGC/issues/317 | satisfied | `analysis_content_runs.runtime_config_snapshot` 与 Collection Provider Run Snapshot 固化 Provider revision、运行参数和不可变 Secret 引用；Worker 按 Run Snapshot 消费 |
| R7 | Secret 不得明文进入数据库、源码、API、日志、Trace 或审计，只通过批准的 Secret Provider 解析 | https://github.com/dingyuwen777/AIMA_UGC/issues/317 | satisfied | DB 只存 `secret_ref`，管理读取仅返回 `secret_configured`；Secret writer 使用不可变 link-if-absent 发布；Docs/Governance Secret gate 成功 |
| R8 | TikHub 是 collection provider，不与 content platform 混为一个概念 | https://github.com/dingyuwen777/AIMA_UGC/issues/317 | satisfied | Provider Config 与 Collection Run Snapshot 分离 provider/platform；TikHub Provider 可服务对应平台选择而不成为平台标识 |
| R9 | `.env` 只允许作为尚未建立 DB Provider 配置时的 bootstrap 兼容来源，DB 接管后不得重新覆盖或阻断 | https://github.com/dingyuwen777/AIMA_UGC/issues/317 | satisfied | `active_llm_provider` 与 Internal V1 configure 在 DB 有 Provider 配置后停止旧 env fallback、Secret 复制和旧 Secret 校验干扰 |
| R10 | 变更完整覆盖 migration、backend、frontend、runtime consumer、测试和文档，并通过核心无重启验收 | https://github.com/dingyuwen777/AIMA_UGC/issues/317 | satisfied | PR #318 已合并；pre-merge 五类永久门禁全绿；implementation main-fresh CI、Runtime、Tooling、Change Gate 全部 success |

## 目标

把管理员配置中心升级为运行时唯一控制面。LLM、TikHub、Analysis Scheme、车型等管理员配置一旦成功保存并处于生效状态，后续新创建/新启动的运行必须消费数据库中的当前配置，不要求重启 API、Worker 或 Scheduler。

## 运行时语义

1. `provider_configs` 是 LLM / Collection Provider 的非敏感运行时事实源。
2. Secret 值不进入数据库、API 响应、审计、日志或代码；数据库只保存 `secret_ref`。
3. 每次 Secret 轮换创建新的不可变 Secret 引用，历史 Run Snapshot 继续引用旧版本，避免自动重试漂移。
4. Analysis Run 冻结 LLM Provider 安全快照与 Analysis Scheme Version；同 Run 的 Shard/Retry 使用同一快照。
5. Collection Run 继续使用既有 Provider/车型/Relevance Snapshot；创建新 Run 时读取 Provider Config 当前 revision。
6. Analysis Scheme 草稿不影响 Runtime，只有发布/回滚后的 active Version 影响新 Analysis Run。
7. 车型继续以数据库车型目录为唯一事实源；运行时通过已有车型快照保持可复现性。
8. `.env` 中 LLM/TikHub 动态参数仅作为数据库尚未接管对应 Provider 时的首次 bootstrap 兼容来源，不得覆盖或阻断数据库中的运行时事实。

## Schema / API

- 扩展 `provider_configs`：`provider_kind`、`model`、超时、重试、并发/RPS、`extra_config`、`is_default`、`revision`。
- `analysis_content_runs` 增加 `runtime_config_snapshot`，只允许保存非 Secret 值和 `secret_ref`。
- 新增管理员 Provider CRUD/Secret 轮换/配置校验 API；读取响应只暴露 `secret_configured`。

## Secret 边界

管理员提交 API Key 时，服务端把 Secret 原子写入批准的 Secret Root，并生成新的版本化 `secret_ref`。发布使用目标已存在即失败的不可变语义；更新数据库后，旧 Secret 文件继续保留供既有 Run Snapshot 使用。任何读取接口不得返回 Secret 内容或内部 `secret_ref`。

首次部署使用独立的持久化 Provider Secret Store：Linux 默认 `${AIMA_HOST_ROOT}/shared/provider-secrets`，Windows Docker Desktop 使用 `windows_provider_secrets` named volume。`configure` 只在数据库尚未接管对应 Provider 时复制部署 Secret；数据库 Provider 记录存在后不再被 `.env` 启停、Base URL 或旧 Secret 校验干扰。API 以读写方式挂载该 Store 用于密钥轮换，Worker 只读挂载并按 Run Snapshot 解析历史 Secret 引用。

## 验收

- [x] 管理员可配置 LLM URL / Model / API Key / 超时 / 重试 / 并发。
- [x] 管理员可配置 TikHub URL / API Key / 超时 / RPS / 并发。
- [x] 保存后无需重启，新 Analysis Run 使用新 LLM 配置。
- [x] 保存后无需重启，新 Collection Run Snapshot 使用更新后的 TikHub 配置 revision。
- [x] 已有 Run / Retry 保持原 Snapshot。
- [x] Prompt 仅 active Analysis Scheme 对新 Run 生效。
- [x] 车型使用数据库事实与现有 Run Snapshot。
- [x] DB/API/日志/审计不出现 Secret 明文，读取 API 不暴露内部 Secret 引用。
- [x] Migration、Backend、Frontend、测试与文档门禁通过。

## 实现与 Review 证据

2026-09-03 完成 L3 两阶段 Review。Requirement 反查与最终 diff 反查期间发现并修复：

1. Secret 写入从“先检查后 replace”改为目标已存在即原子失败的 link-if-absent 发布，消除并发覆盖历史 Secret 的窗口；
2. `configure` 在 DB 接管 Provider 后停止使用旧 `.env` 覆盖或校验对应动态配置，避免第二事实源重新干扰运行；
3. Analysis `configuration_hash` 纳入冻结 Provider 安全快照，避免 Preview 后管理员轮换 Provider、Create 仍接受旧乐观锁；
4. 旧 Analysis Planner、Compose 与管理员页面设计测试同步到新的 Runtime Snapshot / Provider Secret Store / 配置中心职责。

最终 PR HEAD 已同步当时最新 `main`，无未解决 Review thread，结论为 `NO_UNRESOLVED_FINDINGS_WITHIN_SCOPE`。

## Pre-Merge 永久门禁

PR #318 最终 HEAD `7547f626ac4949ee17f21801f7dbed0071b39623`：

- Change Completion Gate #1760 / run `33731385353`：success；
- CI #3895 / run `33731385521`：success，覆盖 Repository Quality、PostgreSQL Integration、Real Full-stack Golden Path、Docs/Governance；
- Runtime Acceptance #1016 / run `33731385377`：success；
- Developer Tooling Compatibility #386 / run `33731385345`：success；首次 Linux PostgreSQL reset 出现一次 readiness 瞬时竞态，定向重跑同一 job 后所有步骤成功；
- Release dry-run #166 / run `33731385386`：success。

## Implementation Main-Fresh 证据

Implementation squash merge `b9387a731fe682c67c4eb974846a772069c5ba26` 已进入 `main`，随后由 `push` 事件重新验证：

- CI #3896 / run `33731871144`：success；
- Runtime Acceptance #1017 / run `33731870654`：success；
- Developer Tooling Compatibility #387 / run `33731870717`：success；
- Change Completion Gate #1761 / run `33731870636`：success；
- 同一 merge SHA 的 main push 工作流：success=4、failure=0、in_progress=0。

因此实现、真实 PostgreSQL、真实浏览器链路、Compose Runtime、Windows/Linux 开发工具链和治理门禁均在合并后的 `main` 上得到 fresh evidence。

# Completion Audit

- [x] upstream_re_read: 已重新读取 Issue #317、PR #318 最终实现与 Review、最终 pre-merge 门禁，以及 implementation merge 后 main-fresh 工作流事实。
- [x] change_coverage: Runtime Provider、Secret、Analysis/Collection Snapshot、Admin API/UI、Migration、OpenAPI/Orval、Compose/Windows Secret Store、测试与文档均完成并有验证证据。
- [x] reverse_audit: 已从管理员保存配置反查新 Run 创建、运行时快照、Worker Provider 构造和 Secret 解析链路，并确认已有 Run/Retry 不随新配置漂移。
- [x] unresolved_cleared: L3 Review 发现均已修复，PR 无未解决 Review thread，最终 pre-merge 与 implementation-main fresh 永久门禁均无失败。

## 归档与关闭时序

本 Change 由独立 archive PR 移入 `changes/archive/2026-09/CHG-20260903-runtime-config-control-plane/`。Issue #317 在 archive PR 合并并取得 archive-main fresh evidence 后执行最终 Closure Audit，再关闭；归档 PR 不使用 closing keyword，避免提前关单。

## 回滚

代码回滚时先停止新的配置写入，再回滚应用版本；Migration downgrade 删除新增安全配置列前，必须确认没有依赖新 Runtime Snapshot 的未完成 Run。Secret 文件不在数据库 downgrade 中自动删除，避免破坏历史任务可恢复性。
