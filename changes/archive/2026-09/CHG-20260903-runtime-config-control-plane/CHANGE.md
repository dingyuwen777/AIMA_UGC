# CHG-20260903-runtime-config-control-plane

- Issue: #317
- Risk: L3
- Status: done
- Implementation PR: #318
- Implementation merge: `b9387a731fe682c67c4eb974846a772069c5ba26`

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

## 归档与关闭时序

本 Change 由独立 archive PR 移入 `changes/archive/2026-09/CHG-20260903-runtime-config-control-plane/`。Issue #317 在 archive PR 合并并取得 archive-main fresh evidence 后执行最终 Closure Audit，再关闭；归档 PR 不使用 closing keyword，避免提前关单。

## 回滚

代码回滚时先停止新的配置写入，再回滚应用版本；Migration downgrade 删除新增安全配置列前，必须确认没有依赖新 Runtime Snapshot 的未完成 Run。Secret 文件不在数据库 downgrade 中自动删除，避免破坏历史任务可恢复性。
