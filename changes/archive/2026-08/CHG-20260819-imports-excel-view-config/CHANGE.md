---
schema: rvc-change/v1
id: CHG-20260819-imports-excel-view-config
title: imports_test Excel 可配置列与统一样式
level: L3
status: done
owner: ChatGPT
branch: feature/imports-excel-view-config
created: 2026-08-19
updated: 2026-08-19
depends_on: []
affected_areas:
  - platform_export
  - imports_test
  - blueprint
  - tests
affected_paths:
  - backend/src/aima_ugc/platform/export/excel.py
  - backend/src/aima_ugc/adapters/providers/imports_test/test.py
  - backend/src/aima_ugc/adapters/providers/imports_test/README.md
  - docs/blueprint/13-统一数据Excel导出与调试复用.md
  - tests/unit/platform/test_excel_export.py
  - tests/unit/collection/test_imports_test_export.py
  - tests/unit/collection/test_p1g_imports_run_all.py
contracts: []
data_changes: none
---

# 目标

让 `imports_test` 最终 Excel 默认只展示以下 10 列，并允许通过 `test.py` 的有序配置自由选择共享内容列及调整顺序：

```text
平台
标题
正文
作者
发布时间
内容链接
命中关键词
情感标签
一级标签
二级标签
```

同时统一共享 Excel 的人工审阅样式，参考用户上传 Excel 的 `文章` Sheet，并把 `imports_test/README.md` 改为直接可执行的使用说明。

# 成功标准

- [x] raw/labeled 的 `内容` Sheet 默认都只展示上述 10 列，顺序一致。
- [x] `EXCEL_CONTENT_COLUMNS` 决定显示列和顺序，不需要改 Exporter。
- [x] 空、重复、未知列 fail-closed。
- [x] 不传 `content_columns` 的既有调用仍得到原完整内容列。
- [x] `UnifiedDataExcelV1`、生成 Schema、Canonical、Analysis、数据库均未变化。
- [x] raw/labeled 共用同一展示配置，仅 Analysis 是否填值不同。
- [x] 共享样式包含冻结首行、筛选、`#FFC000` 表头、11pt 字体、表头/正文行高、网格线、固定列宽、纵向页面、参考页边距和可点击 HTTP(S) 链接。
- [x] 继续使用 openpyxl write-only 流式写出，不新增 pandas 或第二套 Workbook。
- [x] README 已按“配置 → 运行 → 输出 → 可选列 → 排错”重写，不再以临时阶段边界为主线。
- [x] Blueprint 13 已同步“完整数据契约 + 共享 Exporter 受控展示投影”的长期规则。

# 范围

- 共享 Excel Exporter 增加可选 `content_columns`。
- `imports_test` 默认配置 10 列，raw/labeled 共用。
- 共享 Excel 样式按参考 Sheet 固化。
- 更新直接相关测试、README 与 Blueprint 13。

# 非目标

- 不修改 `UnifiedDataExcelV1` / Canonical / Analysis 字段与 Schema。
- 不允许任意自定义列名、公式列或调用方私有字段。
- 不新增第二个 Excel Exporter，也不在 `imports_test` 中二次重写 Workbook。
- 不增加评论列配置；评论 Sheet 保持共享完整字段。
- 不把用户附件作为运行时模板依赖。
- 不启动 Stage 8。

# 必须保持不变

- Provider-neutral 数据继续通过 `UnifiedDataExcelV1` 进入唯一共享 Exporter。
- TikHub/正式导出不传 `content_columns` 时完整列行为保持兼容。
- 外部 ID 文本格式、Formula Injection 防护、合法 HTTP(S) 超链接、北京时间显示、原子发布与重新打开校验继续有效。
- 大文件继续 `write_only=True`，不扫描全表 autofit。
- raw/labeled 都只消费同一 `deduplicated/contents.jsonl`。

# 方案比较

## 方案 A：`imports_test` 导出后再删除列/修改样式

不采用。会形成第二个 Workbook Owner，并让约 9 万行文件产生一次无必要的二次打开和重写。

## 方案 B：把共享 Exporter 全局默认直接改成 10 列

不采用。会破坏 TikHub/正式导出的完整默认视图。

## 方案 C：共享 Exporter 支持已知列的受控有序投影

采用。`UnifiedDataExcelV1` 不变；`content_columns=None` 保持完整默认视图；传入列配置时只允许从共享已知列中选择并按配置顺序投影。`imports_test` 只维护默认 10 列配置，样式仍由共享 Exporter 唯一维护。

# 已确认关键决策

用户确认：

1. `imports_test` 默认展示 10 个指定业务列；
2. 用户可配置显示哪些列以及列顺序；
3. README 应直接告诉使用者怎么配置、运行、查看结果和排错；
4. Excel 样式参考上传文件 `文章` Sheet 的可复现格式。

附件格式事实：冻结 `A2`；AutoFilter 覆盖数据区；表头 `#FFC000`、11pt 粗体；正文 11pt；表头行高 16.5、默认正文行高 14.5；显示网格线；无合并；主要列宽 B=20、C=34、D/E=50、F=15、G=20、H=12；portrait；页边距 left/right=0.7、top/bottom=0.75、header/footer=0.3。模板局部字体差异不复制为异常规则，公共样式统一使用 Calibri 11pt。

# 公共接口与兼容策略

- `export_unified_data_excel()` 与 `export_unified_content_jsonl_to_excel()` 增加可选 keyword-only `content_columns`。
- `None` 保持现有完整内容列。
- 配置只做最终展示投影，不改变底层数据。
- 只新增可选参数，不删除或改名既有参数。
- `UnifiedDataExcelV1` Contract/Schema 不变。
- 内容 ID 不显示时，reopen 校验仍强制 Sheet、实际表头和行数；只有 `内容ID` 可见时才额外校验首个 ID。

# Migration / 部署 / 回滚

- 数据库 Migration：不适用。
- 依赖升级：不适用。
- 部署：随正常代码 Release，无数据迁移。
- 回滚：回退本 Change 的 Exporter、入口、文档和测试即可；不需要数据回滚。

# 风险与处理

- 列配置错误：非空、无重复、必须为已知列的严格校验。
- 样式影响大文件：只使用固定样式和有界列宽，不做全表 autofit 或复杂条件格式。
- 共享样式影响其他默认 Excel 外观：字段和值不变，且统一样式属于本次已批准目标。

# 任务

- [x] 读取仓库规则、相关 Blueprint、Contract、共享 Exporter/测试与附件格式
- [x] 建立失败测试并确认 Red
- [x] 实现共享 Exporter 列投影和样式
- [x] 接线 `imports_test` 10 列默认配置
- [x] 重写 `imports_test/README.md`
- [x] 更新 Blueprint 13
- [x] 取得目标测试、Ruff、mypy、Contract、架构、Secret/Docs Green
- [x] 最终 PR head 11/11 workflows 成功
- [x] 两阶段 Review，无未解决的重要问题
- [x] PR #80 正常 merge 并重新读取 `main` 确认集成

# 验证

## Red

PR #80 head `fb1d619f6d8481b7055e40c8c1a01808ef89a82e`，Stage 5A Provider Raw run `32220675358`：

```text
6 failed, 74 passed
```

失败均来自目标行为尚未实现：`EXCEL_CONTENT_COLUMNS` 不存在、最终导出未传列配置、共享 Exporter 不接受 `content_columns`。Secret/Docs 同轮仍成功。

## Green

实现/文档 head `cdea0b685951e3c1d610ffa411b1f237d5f60c41`，Stage 5A run `32221143932`：

- P1 Excel/Analysis/Export：`80 passed in 3.27s`；
- Provider/Raw：`24 passed in 0.46s`；
- Ruff format/check：通过；
- P1 mypy：24 source files 无问题；
- 全仓 mypy：168 source files 无问题；
- Analysis/Export Contract drift、Architecture、Table Ownership、Secret、Docs：全部通过。

最终 PR head `bafd7aea2ac5b8993428d688a27213f5371904da` 的 11 个 workflows 全部 completed/success：

- CI `32221259125`；
- Stage 1-7 Audit Correctness `32221259143`；
- Stage 5A Provider Raw `32221259179`；
- Stage 5B Collection Execution `32221259169`；
- Stage 5C Provider Persistence `32221259183`；
- Stage 5D Provider Dispatch `32221259135`；
- Stage 6 XHS Vertical Slice `32221259159`；
- Stage 7 Keyword Packs `32221259148`；
- Stage 7 Plan Occurrence Run Snapshot `32221259226`；
- Stage 7 Provider Config Routing `32221259181`；
- Stage 7 Scheduler Runtime `32221259085`。

主 CI 的 Stage 1、Stage 2 Platform、Stage 3A Database、Windows bootstrap 均 success；Stage 1 的 contracts/client、backend/repository checks、Wheel build 和 frontend checks 均 success。

# 文档影响

- `imports_test/README.md`：已重写为人工使用指南，包含默认 10 列、全部可选内容列、配置示例、运行步骤、输出目录、模型配置和排错。
- Blueprint 13：已固化完整数据契约与受控展示投影的长期规则，以及统一 Excel 样式。

# 交付

- Change 初始化 Commit：`2f87db73acc0686b840b4df91daaf1fe00bfc24b`
- Red 测试 Commit：`234f62e5542a22eaa6596fc22b09f29a7d309824` 至 `fb1d619f6d8481b7055e40c8c1a01808ef89a82e`
- 共享 Exporter 实现 Commit：`c21373b78bf5823eefd6cfbe0e21984eff968694`
- imports_test 接线 Commit：`d4d93ab92e23fe770aaf5dd43f92afbeb8088d6c`
- 文档/收口 Commit：`3816a9e84b1097580fa5e348c98efac6756f531e` 至 `bafd7aea2ac5b8993428d688a27213f5371904da`
- PR：#80，已正常 merge。
- main merge commit：`961c837393b5eb451839236e275a14107088e0f2`。
- 发布：不涉及独立部署；随 `main` 正常集成。
