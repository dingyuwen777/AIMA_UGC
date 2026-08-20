---
schema: rvc-change/v1
id: CHG-20260820-llm-cost-and-multi-excel
title: AI 打标可复算计费与多 Excel 合并导入
level: L3
status: done
owner: codex
branch: main
created: 2026-08-20
updated: 2026-08-20
depends_on: []
affected_areas:
  - analysis
  - llm-adapter
  - excel-import
  - manual-ingestion
  - documentation
affected_paths:
  - backend/src/aima_ugc/adapters/llm/
  - backend/src/aima_ugc/modules/analysis/
  - backend/src/aima_ugc/adapters/providers/imports/
  - backend/src/aima_ugc/adapters/providers/imports_test/
  - backend/src/aima_ugc/bootstrap/manual_ingestion.py
  - tests/unit/analysis/
  - tests/unit/collection/
  - tests/integration/collection/test_stage8a_cross_source_idempotency.py
  - docs/blueprint/
contracts:
  - ContentLabelingLLMResponse
  - ContentLabelingAttempt
  - content-label-attempt.v2
  - p1-run-summary.v2
data_changes:
  - analysis/llm_requests.jsonl
  - analysis/attempts.jsonl
  - canonical/conversion_summary.json
  - run_summary.json
---

# 目标

在不改变既有单文件打标行为、Canonical/Analysis/Excel 业务契约和默认 file-only 安全边界的前提下：

1. 用模型响应的真实 token 分类和冻结单价快照计算每次 HTTP 响应及整次 AI 打标 run 的费用；
2. 允许 `imports_test` 在一个 run 中按显式顺序合并多个 Excel，统一过滤、去重、打标和导出；
3. 数据库 opt-in 模式仍为每个源 Excel 建立独立 Artifact 与 Import Batch。

# 成功标准

- [ ] `.env` 只保留模型调用所需地址、密钥、模型和可选超时，不增加价格生效时间等计费元数据。
- [ ] 价格目录按 provider/model 匹配，支持普通输入/输出与缓存命中/未命中/输出两类文本 token 计价，并用内容哈希自动标识价格快照。
- [ ] 每个收到 usage 的 LLM HTTP 响应（含空 content/协议错误后重试）都有 token、单价快照和费用审计；无法精确计算时明确记录原因。
- [ ] `attempts.jsonl` 保留 Validation Attempt 事实，`llm_requests.jsonl` 保留物理 HTTP 请求费用事实，run summary 汇总全部可计费请求且报告未计费请求数。
- [ ] 可以从历史 HTTP 请求审计生成不覆盖原始审计的费用复算报告；旧数据缺少必要 token 分类时拒绝伪造精确值。
- [ ] 原 `INPUT_XLSX` 单文件配置和生产 `convert_excel_to_canonical_jsonl()` 行为保持兼容。
- [ ] 多文件按配置顺序合并到同一 Canonical JSONL，再复用既有过滤、去重、打标和导出实现。
- [ ] 数据库 opt-in 时按源文件分区全局去重后的结果，每个源文件独立入库并保持来源 Artifact/Batch 可追溯。
- [ ] 相关单元测试、类型检查、静态检查和质量门禁获得本轮新鲜通过证据。

# 范围

- 增加最小通用文本 LLM 价格目录、加载校验、精确 Decimal 计算和快照哈希。
- 增加逐 HTTP 请求费用审计、run 汇总和非覆盖式复算函数。
- 共享计费能力归属平台无关的 `adapters/llm`；`imports_test` 只选择人工 run 的配置和审计路径。
- 增加生产级多 Excel 转换编排，继续复用既有 Reader、Mapper 和单文件转换逻辑边界。
- 扩展 `imports_test` 配置、run summary 与数据库 opt-in 编排。
- 同步 Analysis、Import 测试入口、Blueprint 和配置示例文档。

# 非目标

- 不接入供应商余额/账单 API，不把本地计算值声明为供应商最终账单。
- 不增加预算阈值、费用停止策略、Budget Account 或 Reservation Ledger。
- 不支持图片、音频、按请求、阶梯折扣或其他未配置计费维度。
- 不改变既有关键词、去重键、标签 Prompt/Taxonomy、Excel 输出列或数据库 Schema。
- 不升级依赖，不新增命令行入口，不创建 PR，不强制推送或重写历史。

# 必须保持不变

- 单个 Excel 仍可通过 `INPUT_XLSX` 和 `convert_excel_to_canonical_jsonl()` 原样运行。
- `WRITE_TO_DATABASE=False`、`ENABLE_REAL_LLM=False` 的默认安全边界不变。
- 一条内容一次逻辑 Validation Attempt、显式有界 Transport Retry 和 checkpoint 恢复语义不变。
- Canonical、UnifiedContentRecordV1、ContentLabelAnalysisV2 和最终 Excel Contract 不变。
- 多文件去重继续复用既有稳定身份规则，不引入模糊正文或标题去重。

# 关键决策

## 用户确认

- 采用版本化官方价格快照思路，但配置从第一性原理精简：价格不放 `.env`，不手工维护生效时间或价格版本。
- 价格项只保存计算与核验所需 provider、model、币种、token 单价和官方来源；代码以规范化内容 SHA-256 自动生成快照身份。
- 现阶段内置价格目录只保存实际使用的 `deepseek-v4-pro`；其他文本模型由同一通用目录结构按需新增，不预配未使用模型。
- 多个 Excel 合并为一个 run，统一过滤、去重、打标和导出；数据库按源文件分别溯源。

## 方案比较

1. 推荐并采用：通用文本价格目录 + 物理 HTTP 请求审计 + 多文件合并编排。能覆盖重试费用、历史复算和跨文件去重，不改变业务 Contract。
2. 仅在 `.env` 配单价：配置少但易误填、历史复算弱，且 Secret/运行参数与可审计价格事实混杂，不采用。
3. 只汇总成功 Validation Attempt：实现最小但遗漏空 content 等已付费响应，不满足准确计费，不采用。

## 兼容、迁移、部署与回滚

- 数据库 Schema/Migration：无变化。
- 文件审计新增 `llm_requests.jsonl`；`attempts.jsonl` 升级 schema 但仅增加字段，旧 checkpoint 读取不变。
- 单文件生产 API 保持；多文件使用新增编排函数和 `INPUT_XLSX_FILES`，原配置继续作为兼容回退。
- 部署只随代码和包内价格 TOML 发布，不新增依赖或服务。
- 回滚可恢复旧入口；新增审计文件是附加事实，不参与标签恢复和业务读取。

## 风险

- Provider 已处理但客户端未收到响应时，本地无法取得 usage，必须报告计费未知，不承诺与供应商账单完全一致。
- 供应商价格变化后必须更新价格目录；历史 run 使用当次冻结快照，不被后续价格覆盖。
- 多文件同名会使现有 `source_value=文件名` 无法唯一分区，因此多文件入口必须在付费/入库前拒绝重复文件名。

# 任务

- [x] 调查当前实现和事实源
- [x] 建立失败测试或说明测试例外
- [x] 完成最小实现
- [x] 同步受影响文档
- [x] 取得新鲜验证证据

# 验证

## 计划

- 目标测试：`uv run pytest tests/unit/analysis/test_llm_pricing.py tests/unit/analysis/test_openai_compatible_llm.py tests/unit/analysis/test_offline_content_labeling.py tests/unit/collection/test_imports_excel.py tests/unit/collection/test_p1g_imports_run_all.py tests/unit/collection/test_stage8a_debug_database_opt_in.py -q`
- 相关测试：`uv run pytest tests/unit/analysis tests/unit/collection -q`
- 静态检查/构建：`uv run ruff check backend tests scripts`、`uv run mypy backend/src`，以及四项仓库质量脚本。

## 新鲜证据

- Red：新增价格/请求审计/多 Excel 测试在实现前因缺少对应 API 于 collection 阶段失败，失败原因与预期一致。
- 目标测试：`uv run pytest tests/unit/analysis/test_llm_pricing.py tests/unit/analysis/test_llm_request_audit.py tests/unit/analysis/test_openai_compatible_llm.py tests/unit/analysis/test_offline_content_labeling.py tests/unit/collection/test_imports_excel.py tests/unit/collection/test_p1g_imports_run_all.py tests/unit/collection/test_manual_ingestion_multi.py tests/unit/collection/test_stage8a_debug_database_opt_in.py --basetemp .test-tmp-final-target -q`，退出码 0，`47 passed`。
- 全量单元测试：`uv run pytest tests/unit --basetemp .test-tmp-final-unit -q`，退出码 0，`400 passed, 1 skipped`。
- PostgreSQL 专项收集：`uv run pytest tests/integration/collection/test_stage8a_cross_source_idempotency.py --collect-only -q`，退出码 0，4 项均可收集，包含新增多源 Artifact/Batch 用例。
- 静态检查：`uv run ruff check backend tests scripts`，退出码 0；`uv run mypy backend/src`，退出码 0，178 个源码文件无问题。
- 质量门禁：`check_docs.py`、`check_architecture.py`、`check_table_ownership.py`、`scan_secrets.py` 均退出码 0。
- 打包：`uv build`，退出码 0，成功生成 sdist 与 wheel；包内包含 `pricing.toml`。
- 完整 `uv run pytest -q` 的环境验收未通过：`447 passed, 1 skipped, 8 failed, 98 errors`，失败/错误共同前置原因是本机缺少 `.runtime/secrets/postgres_password`，不是本次目标或单元测试失败。未伪造 PostgreSQL 集成通过；新增集成测试留给具备隔离 PostgreSQL 18 与 Secret 的 CI/开发环境执行。

# 文档影响

- 更新 `imports_test/.env.example` 与 `imports_test/README.md`，逐项解释配置意义和官方取值来源。
- 新增 `adapters/llm/README.md`，明确全平台共享 Owner、调用边界、换模型步骤和准确性边界。
- 更新 Analysis README 和 Blueprint 15，说明物理请求计费、价格快照、复算和准确性边界。
- 更新 Excel Import/Stage 8 文档，说明多文件顺序、全局去重和按源文件入库语义。
- Blueprint 13 已复核：本次不改变 Excel 输出 Workbook/列 Contract，因此无需制造无关文档差异。

# 交付

- Commit：用户已授权本 Change 与实现直接提交并推送到远程 `main`；具体哈希以 Git 提交结果为准。
- PR：用户要求直接推送主分支，不创建 PR。
- 发布：不在本任务范围。
