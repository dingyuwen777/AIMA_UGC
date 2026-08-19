---
schema: rvc-change/v1
id: CHG-20260819-deduplicate-non-equivalent-content
title: 同一内容非等价记录统一去重
level: L2
status: done
owner: Codex
branch: main
created: 2026-08-19
updated: 2026-08-19
depends_on: []
affected_areas:
  - analysis
  - imports_test
affected_paths:
  - .reliable-vibe-coding/project-context.json
  - backend/src/aima_ugc/modules/analysis/offline_content.py
  - backend/src/aima_ugc/adapters/providers/imports_test/README.md
  - tests/unit/analysis/test_offline_content_processing.py
  - docs/测试与调试说明.md
contracts: []
data_changes: []
---

# 目标

文件导入结果按 `(platform, external_content_id)` 统一去重；同一身份的记录即使业务字段存在差异，也只保留源文件中首次出现的记录，不再中止整个离线处理任务。

# 成功标准

- [x] 五个平台的同一稳定身份均最多输出一条记录。
- [x] 完全等价和非等价的后续记录都计入 `duplicates_removed`。
- [x] 非等价重复继续写入 `deduplication_conflicts.jsonl`，记录首次行、丢弃行和差异字段，但不再阻止发布去重 JSONL。
- [x] 现有等价重复的首次记录保留顺序、流式处理方式和公开函数签名保持不变。
- [x] 现有真实 filtered JSONL 可以在不调用 LLM 的情况下完成去重，输出中不存在重复稳定身份。

# 范围

- 调整 Provider-neutral JSONL 去重的非等价重复处理。
- 更新对应单元测试、人工入口说明和统一测试说明。
- 使用现有真实 filtered JSONL 做离线去重验证。

# 非目标

- 不合并不同记录的字段，不按发布时间、文本长度或平台私有规则选择代表记录。
- 不修改 Canonical、Analysis 或 Excel Contract。
- 不修改 Excel 身份解析规则、关键词规则、LLM 调用、并发或重试行为。
- 不运行真实 LLM，不修改用户输入 Excel，不升级依赖。

# 必须保持不变

- 稳定身份仍为 `(platform, external_content_id)`。
- 首次出现的记录保持原始内容和源定位，输出顺序保持首次出现顺序。
- 输入仍逐行解析和校验，输出仍使用临时文件、`fsync` 和原子替换。
- 等价重复仍不写差异审计；非等价重复的审计不包含正文等敏感原文。
- 用户对 `test.py`、`keyword_pack.txt` 和 `tikhub_test/test.py` 的未提交配置修改不得被覆盖。

# 关键决策

- 用户确认所有平台的同一内容只需要一条记录，字段差异也属于去重范围。
- 代表记录统一保留首次出现项，复用现有等价重复语义，并避免根据不可靠字段猜测“最佳”记录。
- 非等价重复从致命冲突改为可审计的数据质量信号；`conflicts` 继续统计此类记录以保持摘要字段兼容。

# 任务

- [x] 调查当前实现、失败产物、真实冲突记录和相关事实源
- [x] 建立五平台非等价重复的失败测试
- [x] 完成保留首条、审计差异且继续发布的最小实现
- [x] 同步受影响文档
- [x] 取得目标、相关、静态和真实数据验证证据

# 验证

## 计划

- 目标测试：`uv run pytest tests/unit/analysis/test_offline_content_processing.py -q`
- 相关测试：`uv run pytest tests/unit/analysis tests/unit/collection/test_imports_test_run_directory.py tests/unit/collection/test_p1g_imports_run_all.py -q`
- 静态检查：`uv run ruff format --check <changed Python files>`、`uv run ruff check <changed Python files>`、`uv run mypy backend/src/aima_ugc/modules/analysis tests/unit/analysis/test_offline_content_processing.py`
- 文档与边界：`uv run python scripts/quality/check_architecture.py`、`uv run python scripts/quality/scan_secrets.py`、`uv run python scripts/quality/check_docs.py`
- 真实数据：对 `20260819T174913.984515+0800/filtered/contents.jsonl` 运行生产去重入口并扫描输出稳定身份唯一性，不进入 Analysis/LLM 阶段。

## 新鲜证据

- Red：`uv --cache-dir .uv-cache run pytest tests/unit/analysis/test_offline_content_processing.py -q -p no:cacheprovider`，退出码 1；5 个平台新用例均因旧实现抛出 `ContentDeduplicationConflictError` 失败，5 个既有用例通过。
- Green：同一目标命令退出码 0，`10 passed in 0.45s`。
- 相关回归：`uv --cache-dir .uv-cache run pytest tests/unit/analysis tests/unit/collection/test_imports_excel.py tests/unit/collection/test_imports_test_run_directory.py tests/unit/collection/test_imports_test_export.py tests/unit/collection/test_p1g_imports_run_all.py -q -p no:cacheprovider`，退出码 0，`92 passed in 2.46s`。
- 真实数据：生产 `deduplicate_content_jsonl` 处理现有 49 MB filtered JSONL，退出码 0；`rows_seen=25931`、`rows_written=25930`、`duplicates_removed=1`、`conflicts=1`。
- 真实输出逐行通过 `UnifiedContentRecordV1` 校验；`rows=25930`、`unique=25930`、`duplicate_identities=0`，目标小红书 ID 仅保留 `sheet=文章;row=13709`。
- `deduplication_conflicts.jsonl` 保留原冲突的首次行 `5176`、丢弃行 `16027` 和 3 个差异字段。
- `ruff format --check` 退出码 0，2 个变更 Python 文件已格式化；`ruff check` 退出码 0；mypy 退出码 0，7 个 source files 无问题。
- `check_architecture.py`、`scan_secrets.py`、`check_docs.py` 均退出码 0。
- 扩大回归曾包含 `test_imports_keyword_pack.py`，结果为 `94 passed, 1 failed`；唯一失败来自任务开始前用户已把词包 `凌志26-M` 改成 `凌志26M`，与本次去重实现无关，未覆盖或修改该用户配置。
- 用户随后明确要求将词包修改一并提交；同步该词包的测试断言后，最终相关回归退出码 0，`98 passed in 2.13s`。Ruff format/check、mypy、架构检查、表 Owner 检查、Secret 扫描和文档检查均退出码 0。

# 文档影响

- 更新 `imports_test/README.md` 和 `docs/测试与调试说明.md`，明确首次记录优先、非等价重复只审计不中止。
- Blueprint 13 的统一 Excel/JSONL 边界、Blueprint 15 的 Analysis Contract 均不变化，无需修改。

# 交付

- Commit：`c1cd45364d51127a1970088b13ef45922da5829d`（`更新关键词并完善离线去重与AI重试`）。
- PR：未授权，未创建。
- 发布：已按用户明确要求直接快进推送至 `origin/main`，远程引用已核验一致。
