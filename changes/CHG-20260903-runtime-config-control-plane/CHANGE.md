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

首次部署使用独立的持久化 Provider Secret Store：Linux 默认 `${AIMA_HOST_ROOT}/shared/provider-secrets`，Windows Docker Desktop 使用 `windows_provider_secrets` named volume。`configure` 只在首次缺失时把部署 Secret 复制进去；数据库 Provider 记录存在后不再被 `.env` 启停/Base URL 覆盖。API 以读写方式挂载该 Store 用于密钥轮换，Worker 只读挂载并按 Run Snapshot 解析历史 Secret 引用。

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

2026-09-03 在仓库 GitHub Runner 的一次性收尾验证中已通过：

- `scripts/contracts/generate.py` 生成后再次 `--check` 无漂移；
- Orval 前端 API Client 重新生成成功；
- 前端 TypeScript/Vue typecheck、ESLint、生产构建全部通过；
- `tests/unit/system/test_runtime_provider_config.py`：4 项通过，覆盖 LLM dotted Provider 身份兼容、Collection Provider 约束、不可变 Secret 写入和 Collection Provider Run Snapshot；
- `docker compose config` 与 Windows overlay `docker compose -f compose.yaml -f compose.windows.yaml config` 均通过。

正式 PR 全量 CI、Runtime Acceptance 与 L3 Review 仍以 GitHub 门禁结果为最终完成证据。

## 回滚

代码回滚时先停止新的配置写入，再回滚应用版本；Migration downgrade 删除新增安全配置列前，必须确认没有依赖新 Runtime Snapshot 的未完成 Run。Secret 文件不在数据库 downgrade 中自动删除，避免破坏历史任务可恢复性。