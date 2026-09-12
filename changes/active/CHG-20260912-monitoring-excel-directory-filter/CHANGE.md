---
schema: coding-change/v1
id: CHG-20260912-monitoring-excel-directory-filter
title: 增加监测 Excel 目录批量过滤脚本
level: L2
status: in_progress
owner: dingyuwen777
branch: feat/451-monitoring-excel-directory-filter
created: 2026-09-12
updated: 2026-09-12
completion_gate: required
depends_on: []
affected_areas:
  - imports-test
  - excel
  - offline-analysis
  - documentation
affected_paths:
  - backend/src/aima_ugc/adapters/providers/imports_test/monitoring_excel_filter/
  - tests/unit/ingestion/test_monitoring_excel_filter.py
contracts: []
data_changes: []
---

# 背景与现状

当前 `imports_test/test.py` 支持单个 Excel 或人工列出的 `Path` 元组，但没有“指定一个目录并递归处理所有 Excel”的一次性离线入口。正式 Excel 批量转换会把任何 `ExcelImportRowError` 记为 rejected row，并在存在 rejected row 时拒绝发布 Canonical；而本次监测 Excel 明确包含微信、今日头条等 AIMA 五个平台以外的来源，这些来源会由现有 Profile 产生 `platform_unmapped`。

Issue #451 已确认本工具只服务一次性离线筛选：复用现有 Reader、Mapper、Canonical、关键词过滤和去重，只把目录发现与 `platform_unmapped` 的人工 skip 作为入口差异，不改变正式 Import、Platform Contract、Canonical、数据库或外部 Provider 语义。

# 目标

- 用户只配置一个 `INPUT_DIR`，工具递归发现根目录和子目录中的全部 `.xlsx`；
- 五平台行继续使用现有 `map_excel_row()` 形成 `CanonicalContentV1`；
- 非五平台 `platform_unmapped` 明确跳过并计数，其他数据错误 fail closed；
- 品牌词和车型词共用一个本地词包，标题/正文命中任意词即保留；
- 所有文件的过滤结果统一按现有稳定身份去重；
- 输出 Canonical、Filtered、Deduplicated JSONL、冲突审计和可对账运行摘要；
- README 给出配置、执行、输出和失败边界。

# 范围

Included：`imports_test` 下新增独立目录批量过滤工具、词包示例、targeted tests 和该工具 README。

Excluded：PostgreSQL、TikHub、LLM、AI 标签、API/Worker/Scheduler、正式 Historical Import、正式 Excel Export/Report、平台扩展、Schema/Migration、依赖升级、修改生产 Import fail-closed 行为。

# 必须保持不变

- AIMA 平台机器身份仍只有 `xiaohongshu/douyin/weibo/bilibili/kuaishou`；
- 正式 `convert_excel_to_canonical_jsonl()` / `convert_excel_files_to_canonical_jsonl()` 继续对 rejected row fail closed；
- Reader、Mapper、Identity、Canonical、Relevance、Filter、Dedup 的业务语义由现有 Owner 维护，本工具不复制第二套实现；
- 不访问数据库或外部 Provider，不修改源 Excel；
- 不新增第三方依赖。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 递归发现目录及子目录 `.xlsx`，忽略临时/非目标文件并保持确定性顺序 | https://github.com/dingyuwen777/AIMA_UGC/issues/451 | in_progress | `test_discover_input_files_*` 已定义目标回归，生产入口待实现 |
| R2 | 五平台复用 Mapper；仅 `platform_unmapped` skip，其他错误失败 | https://github.com/dingyuwen777/AIMA_UGC/issues/451 | in_progress | Mapper/错误边界回归已定义，生产入口待实现 |
| R3 | 同名文件使用相对输入路径保留唯一来源追溯 | https://github.com/dingyuwen777/AIMA_UGC/issues/451 | in_progress | 同 basename 跨子目录回归已定义，生产入口待实现 |
| R4 | 品牌/车型同一词包 OR，复用现有 Canonical Filter | https://github.com/dingyuwen777/AIMA_UGC/issues/451 | in_progress | 完整入口回归已定义，生产入口待实现 |
| R5 | 所有文件统一复用现有 `(platform, external_content_id)` 去重 | https://github.com/dingyuwen777/AIMA_UGC/issues/451 | in_progress | 跨 Excel 重复回归已定义，生产入口待实现 |
| R6 | 生成逐文件与全局可对账 `run_summary.json` | https://github.com/dingyuwen777/AIMA_UGC/issues/451 | in_progress | Summary 对账回归已定义，生产入口待实现 |
| R7 | README 说明用途、输入、平台/关键词边界、命令与输出 | https://github.com/dingyuwen777/AIMA_UGC/issues/451 | in_progress | targeted README 待实现 |
| R8 | targeted tests / Ruff / PR CI 证明实现且不改变正式 Contract/依赖 | https://github.com/dingyuwen777/AIMA_UGC/issues/451 | in_progress | current-head Evidence 待形成 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit | required | 目录发现、Mapper skip/fail、来源追溯、关键词 OR、跨文件去重、summary 对账 |
| Contract / Generated | not_applicable | 不修改 Platform/Canonical/API Contract 或生成物 |
| Backend/API/PostgreSQL | not_applicable | 不访问数据库，不修改 API/Worker |
| Browser / Full-stack | not_applicable | 无前端或跨进程产品链变化 |
| External Provider Probe | not_applicable | 不调用 TikHub/LLM 或其他外部 Provider |
| Build / Runtime | required | Python import/compile、targeted pytest、Ruff、PR CI |
| Docs | required | 新工具 README 与当前代码事实一致 |

# 实施步骤

- [x] 建立 Requirement Source：Issue #451。
- [x] 恢复当前 Reader/Mapper/Filter/Dedup/Platform/Imports Test 机器事实。
- [x] 定义目录发现、非五平台 skip、OR 过滤、跨文件去重和 summary 的 targeted tests。
- [ ] 形成 Red Evidence，证明当前仓库尚无目标工具入口。
- [ ] 实现 `monitoring_excel_filter/process_directory.py`，只新增薄编排层。
- [ ] 增加 `keyword_pack.txt` 与 README。
- [ ] 运行 targeted tests、静态检查和相关治理门禁。
- [ ] 重新读取 Issue #451 与当前实现，完成 Completion Audit。
- [ ] 完成独立 Review、PR current-head CI、Ready 与合并门禁。
- [ ] 合并后验证 main fresh CI 和 repository-native Change 归档。

# 当前新鲜证据

- 2026-09-12 重新读取当前 `main`：`147dc43f82624fe201a979e73d9d2f5c21190534`。
- 当前 `imports_test/test.py` 只接受单个 `Path` 或人工 tuple，没有目录递归发现。
- 当前正式批量转换存在任意 rejected row 时拒绝发布 Canonical；`platform_unmapped` 因此不能直接复用该高层入口。
- 当前 `filter_canonical_content_jsonl()` 只传 `keywords=` 时，同一维度内为 OR，满足品牌词/车型词任意命中需求。
- 当前 `deduplicate_content_jsonl()` 按 `(platform, external_content_id)` 去重，可直接处理跨 Excel 过滤结果。
- Draft PR 的正式 CI 会直接 skipped，因此 PR 已切为普通状态但仍保持“逻辑未就绪”；下一次同步提交只用于触发 tests-only Red。

# Completion Audit

- [x] upstream_re_read：已重新读取 Issue #451、当前 `main` 的项目规则、Blueprint、数据入口文档和直接相关生产实现。
- [ ] change_coverage：R1–R8 待实现与 current-head 验证后收敛。
- [ ] reverse_audit：待从最终 diff 反查生产 Owner 是否保持未修改、README/测试是否与真实入口一致。
- [ ] unresolved_cleared：当前仍缺 Red/Green、PR current-head CI、独立 Review、合并后 main fresh Evidence。

# 兼容、部署与回滚

本任务不改变生产 Contract、Schema、Migration、依赖、部署或数据库。工具是 `imports_test` 下独立人工入口；回滚时删除新增目录和 targeted test 即可，正式产品运行链不受影响。
