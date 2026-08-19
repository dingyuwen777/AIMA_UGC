---
schema: rvc-change/v1
id: "CHG-20260819-retry-empty-llm-content"
title: "重试 LLM 空内容响应并恢复离线打标"
level: L2
status: done
owner: "Codex"
branch: "main"
created: 2026-08-19
updated: 2026-08-19
depends_on:
  - "CHG-20260819-deduplicate-non-equivalent-content"
affected_areas:
  - "analysis"
  - "llm"
  - "imports_test"
affected_paths:
  - "backend/src/aima_ugc/adapters/llm/openai_compatible.py"
  - "tests/unit/analysis/test_openai_compatible_llm.py"
  - "tests/unit/analysis/test_llm_transport_retry.py"
  - "backend/src/aima_ugc/adapters/providers/imports_test/README.md"
contracts: []
data_changes: []
---

# 目标

DeepSeek JSON Output 偶发返回空 `message.content` 时，离线内容打标使用既有有界 Transport Retry 恢复，而不是立即终止整个 run；修复验证后从原 run 复用已成功 checkpoint，继续处理剩余记录。

# 成功标准

- [x] HTTP 成功且 `message.content` 为 `null`、空字符串或纯空白时，Adapter 返回稳定错误代码且标记为可重试。
- [x] 既有 `RetryingContentLabelingLLM` 对该错误执行最多 4 次重试；后续响应合法时返回成功，耗尽后仍失败退出。
- [x] 缺少 `choices`、`message` 等其他协议错误继续不可重试，认证、HTTP 状态和 Secret 安全行为不变。
- [x] 目标测试、相关 LLM/离线打标测试及质量门禁通过。
- [x] 从 `20260819T181729.423308+0800` 原 run 恢复时复用 6,024 条成功 checkpoint，不重新请求这些记录。

# 范围

- 调整 OpenAI-compatible Adapter 对空 `message.content` 的错误分类。
- 增加 Adapter 与外层有界重试的回归测试。
- 同步 imports_test 调试说明中的空响应恢复行为。
- 验证后调用现有 `label_sentiment(run_dir=...)` 生产入口恢复原 run。

# 非目标

- 不改变 DeepSeek 模型、Prompt、Taxonomy、Thinking 模式或并发数。
- 不改变默认 Transport Retry 次数和退避算法。
- 不新增依赖、公共 Contract、数据库、Migration 或 CLI。
- 不记录 Provider 原始响应、正文、Secret 或思维链。
- 不把其他结构损坏的 HTTP 200 响应统一改成可重试。

# 必须保持不变

- 保持 `OpenAICompatibleContentLabelingLLM` 构造参数、返回结构、导入路径和错误类型兼容。
- 保持 `invalid_message_content` 错误代码及关键错误信息兼容。
- 保持 401/403、非重试 HTTP 状态和其他协议错误快速失败。
- 保持 checkpoint 身份、run 目录、模型与 Prompt 不变，以便安全恢复既有结果。

# 关键决策

- 用户确认采用最小兼容方案：仅将 Provider 官方确认可能偶发的空 content 视为 transient，并复用既有最多 4 次的 Transport Retry。
- 每次空响应重试可能产生额外付费调用；用户已明确接受该取舍。
- 当前 run 保持 Thinking 模式，避免同一 checkpoint 集合混用未被审计字段区分的推理模式；关闭 Thinking 留作后续独立质量/成本任务。
- 连续空响应超过重试上限仍 fail closed，防止无限调用和费用失控。

# 任务

- [x] 调查当前实现、完整 traceback、运行审计和 DeepSeek 官方 JSON Output 说明
- [x] 建立失败测试并确认因空 content 仍不可重试而失败
- [x] 完成最小实现
- [x] 同步受影响文档
- [x] 取得新鲜验证证据
- [x] 从原 run 恢复剩余打标

# 验证

## 计划

- 目标测试：`uv run pytest tests/unit/analysis/test_openai_compatible_llm.py tests/unit/analysis/test_llm_transport_retry.py -q`
- 相关测试：`uv run pytest tests/unit/analysis/test_offline_labeling_canary.py tests/unit/analysis/test_offline_labeling_recovery.py -q`
- 静态检查/构建：`uv run ruff format --check ...`、`uv run ruff check ...`、`uv run mypy backend/src/aima_ugc/adapters/llm tests/unit/analysis/test_openai_compatible_llm.py tests/unit/analysis/test_llm_transport_retry.py` 及仓库相关质量脚本。
- 运行验证：从原 run 调用 `label_sentiment(run_dir=...)`，确认 checkpoint 从 6,024 条继续增长且未重新请求既有条目。

## 新鲜证据

- Red：`.venv/Scripts/python.exe -m pytest tests/unit/analysis/test_openai_compatible_llm.py -q`，退出码 1；新增 3 个空 content 用例失败、既有 4 个通过，失败原因分别为不可重试或纯空白被当成合法内容。
- Green：`.venv/Scripts/python.exe -m pytest tests/unit/analysis/test_openai_compatible_llm.py tests/unit/analysis/test_llm_transport_retry.py -q`，退出码 0，`10 passed`。
- 相关离线路径：canary、并发、checkpoint/恢复测试退出码 0，`7 passed`；完整 `tests/unit/analysis` 退出码 0，`76 passed`。
- 静态检查：Ruff format/check 退出码 0；`mypy backend/src/aima_ugc/adapters/llm` 退出码 0，3 个生产文件无问题。
- 质量门禁：架构、Secret 扫描、文档入口检查均退出码 0。
- 环境说明：沙箱内 `uv` cache 和 pytest 默认 Temp 返回 WinError 5；目标测试改用锁定 `.venv`，涉及 `tmp_path` 的相关测试按批准在沙箱外运行。一次错误文件名和两次临时目录权限失败均未进入业务断言，不计为回归失败。
- 用户已明确授权将剩余约 19,906 条记录的标题、正文和作者显示名发送到 `api.deepseek.com`，使用 `deepseek-v4-pro`，并接受空 content 时每条最多 4 次额外付费重试。
- 真实恢复：从原 run 调用生产 `label_sentiment(run_dir=...)`；恢复前为 6,024 个 checkpoint / 6,035 次 attempt，首次观测为 6,042 / 6,053，增量严格一致，确认复用了既有 checkpoint，没有在恢复启动时重放已成功记录。
- 五分钟运行观察：以首次新增 checkpoint 的 `2026-08-19 18:58:51.297` 为起点，至 `19:04:06.359` 停止轮询；最终观测为 10,260 个 checkpoint / 10,274 次 attempt，`failed.jsonl` 为 0 字节，未观测到 traceback 或进程退出，且 checkpoint 在最终检查前约 0.3 秒仍在写入。按用户要求停止监控但未终止后台进程；全量完成和最终 Excel 尚未验证。
- 最终运行结果：恢复进程退出码 0；共读取 25,930 条，复用 6,024 条 checkpoint，新成功 19,906 条，最终失败 0 条；发生 19,943 次 LLM attempt、20,015 次 HTTP 请求和 72 次 Transport Retry。`analysis/checkpoints.jsonl` 共 25,930 条，`analysis/failed.jsonl` 为 0 字节。
- Excel 导出完成：`labeled_data.xlsx` 包含 25,930 条内容、0 条评论和 36,600 条标签记录，文件大小 9,897,395 字节；生产导出命令正常退出。
- 提交前最终回归：Analysis 与 imports_test 相关测试退出码 0，`98 passed in 2.13s`；Ruff format/check、mypy、架构检查、表 Owner 检查、Secret 扫描和文档检查均退出码 0。

# 文档影响

- `backend/src/aima_ugc/adapters/providers/imports_test/README.md` 需要说明 JSON Output 空 content 使用有界重试，以及耗尽后如何从同一 run 恢复。

# 交付

- Commit：`c1cd45364d51127a1970088b13ef45922da5829d`（`更新关键词并完善离线去重与AI重试`）。
- PR：未授权，未创建。
- 发布：已按用户明确要求直接快进推送至 `origin/main`，远程引用已核验一致。
