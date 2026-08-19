---
schema: rvc-change/v1
id: CHG-20260819-simplify-llm-config
title: 精简离线 AI 打标 LLM 配置
level: L2
status: ready_for_review
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
  - tests/unit/analysis/test_openai_compatible_llm.py
  - tests/unit/collection/test_p1g_imports_run_all.py
contracts: []
data_changes: none
---

# 目标

让离线 AI 打标人工配置只保留真正需要环境/用户决定的 LLM 参数：`AIMA_LLM_BASE_URL`、`AIMA_LLM_API_KEY`、`AIMA_LLM_MODEL`；`AIMA_LLM_TIMEOUT_SECONDS` 保持可选且默认 60 秒。OpenAI-compatible Adapter、JSON mode 和模型服务身份由程序负责，不再要求人工重复配置。

# 成功标准

- [x] `.env` 仅要求 `AIMA_LLM_BASE_URL`、`AIMA_LLM_API_KEY`、`AIMA_LLM_MODEL` 三项，缺少任一项仍由 `_require_env` fail-closed。
- [x] `AIMA_LLM_TIMEOUT_SECONDS` 可省略并复用 Adapter 默认 60 秒，也可显式覆盖为合法正数。
- [x] `AIMA_LLM_PROVIDER` 与 `AIMA_LLM_JSON_MODE` 不再由 `imports_test` `.env` 读取或要求配置。
- [x] `OpenAICompatibleContentLabelingLLM` 继续默认发送 JSON mode 请求，一次 `complete()` 恰好一次 HTTP 请求且不隐藏网络重试。
- [x] Adapter 在未显式提供 `provider_name` 时，从实际请求 `base_url` 的非 Secret endpoint host 自动生成稳定 `provider_name`；显式非默认端口进入身份，继续参与 Analysis 审计和 checkpoint 模型身份匹配。
- [x] 既有显式 `provider_name` 和程序级 `use_json_mode=False` 调用保持兼容；`ContentLabelAnalysisV1` 字段、checkpoint schema、Prompt/Taxonomy、数据库和 Stage 8 均未改变。
- [x] `.env.example`、人工入口 README 与 Analysis README 已同步实际实现；Blueprint 15 的高层 `model_provider + model` 身份语义没有变化，因此不写入人工 `.env` 实现细节。

# 范围

- 精简 `imports_test` 的真实 LLM `.env` 配置面。
- 为 OpenAI-compatible Adapter 增加安全、稳定的默认 Provider 身份派生。
- 增加 Adapter 与人工入口回归测试并同步直接受影响文档。

# 非目标

- 不新增第二种 LLM Adapter。
- 不改为 OpenAI SDK；继续复用现有 `httpx`。
- 不删除 Adapter 的 `use_json_mode` 程序级能力，只是不再把它暴露给 `imports_test` `.env`。
- 不修改 Analysis Contract 字段或 checkpoint schema。
- 不处理用户此前遇到的具体 HTTP 401 API Key/账号问题；该错误与本次配置精简是独立问题。
- 不启动 Stage 8。

# 必须保持不变

- `ContentLabelingService` 继续只依赖统一 LLM Port，不感知具体 HTTP Provider。
- `model_provider + model + prompt_sha256 + taxonomy_sha256 + input_hash` 仍参与 checkpoint 恢复身份。
- API Key 不写入日志、错误、README、Change 或持久化审计文件。
- OpenAI-compatible Adapter 仍使用 `POST <base_url>/chat/completions`、Bearer Authorization、本地 Validator 和显式 Validation Retry 语义。
- 旧调用如果已经显式传入 `provider_name`，其行为不被破坏；显式空白/非法值仍按既有规则拒绝。

# 关键决策

用户已确认从第一性原理只手工配置真正不可由程序获知的 Base URL、API Key、Model，并保留 timeout 作为可选覆盖。Adapter 类型当前只有 OpenAI-compatible 一种，因此不建立 Adapter 配置项；JSON mode 是当前结构化打标的默认行为，也不要求人工重复声明。

为了不削弱现有 Analysis/Checkpoint 审计，`model_provider` 字段继续保留。Adapter 在没有显式 `provider_name` 时根据**实际请求 Base URL**的 hostname（显式非默认端口时包含端口）生成稳定、非 Secret 的服务身份；显式 `provider_name` 继续作为程序级兼容覆盖。这样人工配置减少，但模型服务 endpoint 或模型变化仍可使旧 checkpoint 安全失效。

Blueprint 15 已核对：其长期约束只要求 `model_provider + model` 等身份参与分析追溯/checkpoint 恢复，并未规定该身份必须来自人工环境变量。本次没有改变这一高层语义，因此不修改 Blueprint 15；具体 `.env`/Adapter 默认行为由实现、Analysis README 和 `imports_test` README 维护，避免把运行入口细节写成第二套架构契约。

# 任务

- [x] 调查当前实现、文档、Contract 与相关测试
- [x] 建立失败测试并确认目标行为当前未实现
- [x] 完成最小实现
- [x] 同步 `.env.example` 与直接受影响 README
- [x] 取得目标 Green、静态检查、Contract/架构/Secret/Docs 与主 CI 新鲜证据

# 验证

## 计划

- 目标测试：`tests/unit/analysis/test_openai_compatible_llm.py`、`tests/unit/collection/test_p1g_imports_run_all.py`
- 相关测试：P1 Excel/Analysis/Export 测试集合与仓库完整 `tests/unit`
- 静态检查/构建：仓库既有 Ruff format/check、mypy、Contract/API/Architecture/Secret/Docs 检查及适用 PR workflows

## 新鲜证据

Red（PR #78 head `ec6c5a88129a6ed6382896133f5bfb4bd2322a9e`）：Stage 5A Provider Raw run `32218128738` 的 P1/Analysis 测试得到 `2 failed, 73 passed`；两处失败均为 `OpenAICompatibleContentLabelingLLM.__init__()` 仍强制要求 `provider_name`，证明目标行为尚未实现，而非环境失败。Secret 与 Docs gates 同轮仍成功。

Green（实现 head `86effe3675f9d99156dd113ff14cc385adaca5ce`）：Stage 5A Provider Raw run `32218415273` success：

- P1 Excel/Analysis/Export 测试：`76 passed in 2.77s`；
- P1 Ruff format/check：通过；
- P1 mypy：`Success: no issues found in 24 source files`；
- Analysis/Export Contract drift：通过；
- 架构、Secret、Docs gates：通过；
- Provider/Raw 相关测试：`24 passed in 0.38s`；
- Stage 5A 全仓 Ruff format/check、mypy、架构、table ownership、Secret、Docs 质量门禁全部通过，其中全仓 mypy 为 `Success: no issues found in 168 source files`。

同一实现 head 的主 `CI` run `32218415327` 已 success；Stage 1-7 Audit、Stage 5A/5C/5D、Stage 6、Stage 7 Keyword Packs/Plan Occurrence/Provider Config/Scheduler 共 10 个已完成 workflow 均 success。最后一次记录时 Stage 5B 仍处于 GitHub Runner 排队状态；本 Change 元数据收口提交后仍需以最终 PR head 的新鲜 workflow 结果作为合并门禁。

# 文档影响

- `imports_test/.env.example` 与 `imports_test/README.md`：人工配置只保留 3 个必填项 + 可选 timeout，并说明 Adapter/JSON mode/审计身份由程序负责。
- `modules/analysis/README.md`：固化唯一当前真实 Adapter、默认 JSON mode、默认 timeout、自动 endpoint host 身份及 checkpoint 语义。
- Blueprint 15：无需修改；高层 Analysis/checkpoint 身份契约未改变。

# 交付

- Change 初始化 Commit：`5a04d4d702baae0cff977da79930e520a47f1827`
- Red 测试 Commit：`ec6c5a88129a6ed6382896133f5bfb4bd2322a9e`
- 实现与文档 Commit：`6295be8a659a1cd8c737a3ef66e8fdb8427dcaa1` 至 `86effe3675f9d99156dd113ff14cc385adaca5ce`
- PR：#78，Draft；待最终 head workflow 全绿后转 Ready 并按仓库正常门禁合并。
- 发布：不涉及独立部署；随正常 PR 集成。
