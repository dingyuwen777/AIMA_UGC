# CHG-20260903-runtime-config-control-plane

- Issue: #317
- Risk: L3
- Status: active

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
8. `.env` 中 LLM 动态参数仅作为首次迁移/未配置时的兼容启动来源，不得覆盖数据库中已经存在的活动 Provider Config。

## Schema / API

- 扩展 `provider_configs`：`provider_kind`、`model`、超时、重试、并发/RPS、`extra_config`、`is_default`、`revision`。
- `analysis_content_runs` 增加 `runtime_config_snapshot`，只允许保存非 Secret 值和 `secret_ref`。
- 新增管理员 Provider CRUD/Secret 轮换/配置校验 API；响应只暴露 `secret_configured`。

## Secret 边界

管理员提交 API Key 时，服务端把 Secret 原子写入批准的 Secret Root，并生成新的版本化 `secret_ref`。更新数据库后，旧 Secret 文件继续保留供既有 Run Snapshot 使用。任何读取接口不得返回 Secret 内容。

首次部署使用独立的持久化 Provider Secret Store：Linux 默认 `${AIMA_HOST_ROOT}/shared/provider-secrets`，Windows Docker Desktop 使用 `windows_provider_secrets` named volume。`configure` 只在数据库尚未接管对应 Provider 时复制部署 Secret；数据库 Provider 记录存在后不再被 `.env` 启停、Base URL 或旧 Secret 校验干扰。API 以读写方式挂载该 Store 用于密钥轮换，Worker 只读挂载并按 Run Snapshot 解析历史 Secret 引用。

## 验收

- [ ] 管理员可配置 LLM URL / Model / API Key / 超时 / 重试 / 并发。
- [ ] 管理员可配置 TikHub URL / API Key / 超时 / RPS / 并发。
- [ ] 保存后无需重启，新 Analysis Run 使用新 LLM 配置。
- [ ] 保存后无需重启，新 Collection Run Snapshot 使用更新后的 TikHub 配置 revision。
- [ ] 已有 Run / Retry 保持原 Snapshot。
- [ ] Prompt 仅 active Analysis Scheme 对新 Run 生效。
- [ ] 车型使用数据库事实与现有 Run Snapshot。
- [ ] DB/API/日志/审计不出现 Secret 明文。
- [ ] Migration、Backend、Frontend、测试与文档门禁通过。

## 实现验证证据

2026-09-03 在仓库 GitHub Runner 的收尾验证中已通过：

- `scripts/contracts/generate.py` 生成后再次 `--check` 无漂移；
- Orval 前端 API Client 重新生成成功；
- 前端 TypeScript/Vue typecheck、ESLint、生产构建全部通过；
- `tests/unit/system/test_runtime_provider_config.py`：6 项回归覆盖 LLM Provider 身份兼容、Collection Provider 约束、不可变 Secret、Collection Run Provider Snapshot、DB 默认 LLM 覆盖 env、DB 已接管但无活动默认时禁止 env 回退；
- `tests/unit/content/test_analysis_runtime_configuration_hash.py`：2 项通过，确认 Provider `revision` / `secret_ref` 变化会改变 Analysis 乐观锁哈希，同时历史空 Runtime Snapshot 保持旧哈希兼容；
- `uv run mypy backend/src`：287 个源码文件无类型错误；
- `docker compose config` 与 Windows overlay `docker compose -f compose.yaml -f compose.windows.yaml config` 均通过。

## L3 Review 记录

两阶段 Review 已按 Requirement 反查并修复以下重要 Finding：

1. Secret 写入从“先检查后 replace”改为目标已存在即原子失败的 link-if-absent 发布，消除极窄并发窗口下覆盖历史 Secret 的可能性；
2. `configure` 在 DB 接管 Provider 后停止使用旧 `.env` 覆盖或校验对应动态配置，避免重启时第二事实源重新干扰运行；
3. Analysis `configuration_hash` 纳入冻结 Provider 安全快照，避免 Preview 后管理员轮换 Provider、Create 却仍接受旧乐观锁的竞态；
4. PR 当前无未解决 Review thread；最终完成仍以最新 HEAD 的永久 CI、Runtime Acceptance 与 Release dry-run 全绿为准。

## 回滚

代码回滚时先停止新的配置写入，再回滚应用版本；Migration downgrade 删除新增安全配置列前，必须确认没有依赖新 Runtime Snapshot 的未完成 Run。Secret 文件不在数据库 downgrade 中自动删除，避免破坏历史任务可恢复性。
