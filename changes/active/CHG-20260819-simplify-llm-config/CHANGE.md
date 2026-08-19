---
schema: rvc-change/v1
id: CHG-20260819-simplify-llm-config
title: 精简离线 AI 打标 LLM 配置
level: L2
status: in_progress
owner: ChatGPT
branch: fix/simplify-llm-config
created: 2026-08-19
updated: 2026-08-19
depends_on: []
affected_areas:
  - analysis
  - imports_test
affected_paths:
  - backend/src/aima_ugc/adapters/llm/openai_compatible.py
  - backend/src/aima_ugc/adapters/providers/imports_test/test.py
  - backend/src/aima_ugc/adapters/providers/imports_test/.env.example
  - backend/src/aima_ugc/adapters/providers/imports_test/README.md
  - backend/src/aima_ugc/modules/analysis/README.md
  - docs/blueprint/15-舆情AI打标与统一分析契约.md
  - tests/unit/analysis/test_openai_compatible_llm.py
contracts: []
data_changes: none
---

# 目标

让离线 AI 打标人工配置只保留真正需要环境/用户决定的 LLM 参数：`AIMA_LLM_BASE_URL`、`AIMA_LLM_API_KEY`、`AIMA_LLM_MODEL`；`AIMA_LLM_TIMEOUT_SECONDS` 保持可选且默认 60 秒。OpenAI-compatible Adapter、JSON mode 和模型服务身份由程序负责，不再要求人工重复配置。

# 成功标准

- [ ] `.env` 仅要求 `AIMA_LLM_BASE_URL`、`AIMA_LLM_API_KEY`、`AIMA_LLM_MODEL` 三项，缺少任一项仍 fail-closed。
- [ ] `AIMA_LLM_TIMEOUT_SECONDS` 可省略并默认 60 秒，也可显式覆盖为合法正数。
- [ ] `AIMA_LLM_PROVIDER` 与 `AIMA_LLM_JSON_MODE` 不再由 `imports_test` `.env` 读取或要求配置。
- [ ] `OpenAICompatibleContentLabelingLLM` 继续默认发送 JSON mode 请求，一次 `complete()` 恰好一次 HTTP 请求且不隐藏网络重试。
- [ ] Adapter 在未显式提供 `provider_name` 时，从实际 `base_url` 的非 Secret endpoint host 自动生成稳定 `provider_name`，继续参与 Analysis 审计和 checkpoint 模型身份匹配。
- [ ] 既有显式 `provider_name` 调用保持兼容，`ContentLabelAnalysisV1` 字段、checkpoint schema、Prompt/Taxonomy、数据库和 Stage 8 均不改变。
- [ ] `.env.example`、人工入口 README、Analysis README 与 Blueprint 15 描述和实际实现一致。

# 范围

- 精简 `imports_test` 的真实 LLM `.env` 配置面。
- 为 OpenAI-compatible Adapter 增加安全、稳定的默认 Provider 身份派生。
- 增加 Adapter 回归测试并同步直接受影响文档。

# 非目标

- 不新增第二种 LLM Adapter。
- 不改为 OpenAI SDK；继续复用现有 `httpx`。
- 不删除 Adapter 的 `use_json_mode` 程序级能力，只是不再把它暴露给 `imports_test` `.env`。
- 不修改 Analysis Contract 字段或 checkpoint schema。
- 不处理本次用户遇到的具体 401 API Key/账号问题。
- 不启动 Stage 8。

# 必须保持不变

- `ContentLabelingService` 继续只依赖统一 LLM Port，不感知具体 HTTP Provider。
- `model_provider + model + prompt_sha256 + taxonomy_sha256 + input_hash` 仍参与 checkpoint 恢复身份。
- API Key 不写入日志、错误、README、Change 或持久化审计文件。
- OpenAI-compatible Adapter 仍使用 `POST <base_url>/chat/completions`、Bearer Authorization、本地 Validator 和显式 Validation Retry 语义。
- 旧调用如果已经显式传入 `provider_name`，其行为不被破坏。

# 关键决策

用户已确认从第一性原理只手工配置真正不可由程序获知的 Base URL、API Key、Model，并保留 timeout 作为可选覆盖。Adapter 类型当前只有 OpenAI-compatible 一种，因此不建立 Adapter 配置项；JSON mode 是当前结构化打标的默认行为，也不要求人工重复声明。

为了不削弱现有 Analysis/Checkpoint 审计，`model_provider` 字段继续保留。Adapter 在没有显式 `provider_name` 时根据实际请求 `base_url` 的 hostname（显式非默认端口时包含端口）生成稳定、非 Secret 的服务身份；显式 `provider_name` 仍作为兼容覆盖。这样人工配置减少，但模型身份变化仍可使旧 checkpoint 安全失效。

# 任务

- [x] 调查当前实现、文档、Contract 与相关测试
- [ ] 建立失败测试并确认目标行为当前未实现
- [ ] 完成最小实现
- [ ] 同步 `.env.example`、README 与 Blueprint 15
- [ ] 取得新鲜验证和 CI 证据

# 验证

## 计划

- 目标测试：`tests/unit/analysis/test_openai_compatible_llm.py`
- 相关测试：`tests/unit/analysis/` 与仓库完整 `tests/unit`
- 静态检查/构建：仓库既有 Ruff format/check、mypy、Contract/API/Architecture/Secret/Docs 检查及适用 PR workflows

## 新鲜证据

- Red：待建立并执行。

# 文档影响

- 更新 `imports_test/.env.example` 与 `imports_test/README.md`，使人工配置只保留 3 个必填项 + 可选 timeout。
- 更新 Analysis README 与 Blueprint 15，固化 Adapter 选择、默认 JSON mode、自动模型服务身份与 checkpoint 语义。

# 交付

- Commit：待完成。
- PR：待创建。
- 发布：不涉及独立部署；随正常 PR 集成。