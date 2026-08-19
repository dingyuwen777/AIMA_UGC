---
schema: rvc-change/v1
id: CHG-20260819-imports-excel-view-config
title: imports_test Excel 可配置列与统一样式
level: L3
status: ready_for_review
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

让 `imports_test` 最终导出的 Excel 默认只展示用户当前需要的 10 列，并允许在 `test.py` 中通过一个有序配置项自由增删已支持列、调整列顺序；同时把共享 Excel 的视觉格式统一调整为用户上传参考文件 `文章` Sheet 的可复现样式。`imports_test/README.md` 改为面向使用者的配置、运行、输出和排错说明，不再以临时阶段实施过程为主线。

默认内容列顺序：

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

# 成功标准

- [x] `imports_test` 的 raw/labeled Excel 默认内容 Sheet 都只展示上述 10 列，顺序完全一致。
- [x] `test.py` 顶部有 `EXCEL_CONTENT_COLUMNS` 有序配置；用户增删/重排配置即可改变导出列，不需要改 Exporter 代码。
- [x] 列配置只能引用共享 Exporter 已定义的内容列；空配置、未知列、重复列 fail-closed，不静默猜测。
- [x] `UnifiedDataExcelV1` Pydantic 数据契约、字段语义和生成 JSON Schema 不改变；TikHub/其他调用方不传列配置时仍得到现有完整内容列，保持向后兼容。
- [x] raw/labeled 在同一次调用配置下保持相同 Sheet、列名、列顺序；仅 Analysis 值是否填充不同。
- [x] 共享 Excel 样式复用用户附件 `文章` Sheet 的稳定格式事实：首行冻结、首行筛选、表头 `#FFC000`、11pt 粗体、正文 11pt、表头行高 16.5、正文默认行高 14.5、显示网格线、无合并单元格、链接可点击、页面方向与页边距按模板；长字段使用有界固定宽度。
- [x] 大文件仍使用 write-only 流式写出，不扫描全表做自动列宽，不增加 pandas 或第二套 Workbook 实现。
- [x] `imports_test/README.md` 已重写成人工使用说明，明确输入、配置、运行、输出、列配置、所有可选列、模型配置和常见失败，并移除“P1 边界/临时阶段”式使用说明主线。
- [x] Blueprint 13 已更新为长期当前事实：一个数据契约 + 一个共享 Exporter；允许对既有列做受控展示投影，但禁止调用方新增私有字段或复制 Workbook 实现。

# 范围

- 共享 Excel Exporter 增加可选的内容列投影/排序参数，默认完整列。
- `imports_test` 设置默认 10 列并把同一配置用于 raw/labeled 导出。
- 共享 Excel 样式按附件 `文章` Sheet 调整。
- 更新相关测试、README 与 Blueprint 13。

# 非目标

- 不改变 `UnifiedDataExcelV1` / Canonical / Analysis 的业务字段和 Schema。
- 不允许任意自定义列名、公式列或调用方传 Python 回调生成私有列。
- 不新增第二个 Excel Exporter，也不在 `imports_test` 里后处理/重写 `.xlsx`。
- 不配置评论列；`imports_test` 当前没有评论，评论 Sheet 保持共享 Exporter 的既有完整字段。
- 不从源 Excel 样式文件运行时读取模板；附件只用于冻结可维护的样式事实，避免生产依赖本地模板文件。
- 不启动 Stage 8。

# 必须保持不变

- Provider-neutral 数据继续先投影为 `UnifiedDataExcelV1`，再由唯一 `platform/export/excel.py` 写出。
- TikHub/未来正式导出不传新参数时，内容列仍为当前完整顺序。
- 外部 ID 文本格式、Formula Injection 防护、合法 HTTP(S) 超链接、北京时间显示、原子发布与重新打开验证继续有效。
- 约 90k 行场景继续使用 `write_only=True`，不得为了样式或列配置把所有 Cell 常驻内存。
- `export_raw_excel()` 和 `export_labeled_excel()` 都只消费同一 deduplicated JSONL，不回读源 Excel。

# 方案比较

## 方案 A：`imports_test` 导出后再二次修改 Excel

先调用共享 Exporter 生成完整 Workbook，再在 `imports_test` 删除列、调样式。

不采用。它会让 `imports_test` 成为第二个 Workbook Owner，重复列/样式/校验逻辑；约 9 万行还需要再次打开和重写大文件，增加时间和内存成本。

## 方案 B：把共享 Exporter 的全局默认列直接改成 10 列

所有调用方都只输出用户当前 10 列。

不采用。会破坏 TikHub/正式导出的既有完整字段，丢失 ID、指标、来源和分析版本等审阅信息，是不必要的破坏性变化。

## 方案 C：共享 Exporter 支持“已知列的受控有序投影”，默认仍为完整视图

`UnifiedDataExcelV1` 数据结构不变；Exporter 接受可选 `content_columns`，只允许从当前共享列集合中选择，顺序即输出顺序；不传参数仍输出完整列。`imports_test` 在 `test.py` 顶部传入用户确认的 10 列。公共样式继续只在共享 Exporter 维护。

采用。它满足可配置、单一实现、向后兼容、低维护成本和大文件流式写出的约束；新增机制只有“列名校验 + 索引投影”，没有引入第二个 Contract 或插件系统。

# 已确认关键决策

用户已明确确认：

1. `imports_test` 最终默认只展示 10 列：平台、标题、正文、作者、发布时间、内容链接、命中关键词、情感标签、一级标签、二级标签；
2. 通过配置项决定显示哪些列以及列顺序；
3. README 应让使用者直接知道如何配置和运行脚本，不需要“与 P1 边界”等实施过程描述；
4. Excel 样式参考本次上传文件 `文章` Sheet 的字体、字号、颜色、冻结首行等可复现格式。

附件实际格式调查结果：首行冻结 `A2`；AutoFilter 覆盖整个数据区；表头填充 `#FFC000`、粗体 11pt；正文 11pt；表头行高 16.5，正文默认 14.5；显示网格线；无合并；模板主要列宽 B=20、C=34、D/E=50、F=15、G=20、H=12，其余默认；页面为 portrait，页边距 left/right=0.7、top/bottom=0.75、header/footer=0.3。模板个别单元格存在字体差异，不复制为列级例外，统一使用一致 11pt 字体。

# 公共接口与兼容策略

- `export_unified_data_excel()` 与 `export_unified_content_jsonl_to_excel()` 新增可选 keyword-only `content_columns`；默认 `None` 表示完整既有列。
- 只新增可选参数，不删除/改名既有参数，现有调用继续可运行。
- `UnifiedDataExcelV1` Pydantic Contract 与生成 Schema 不变。
- 列选择仅是最终展示投影，不改变底层数据存在性与字段语义。
- 导出后校验不再无条件依赖 `内容ID` 必须可见；只有实际选择该列时才校验首个内容 ID，Sheet/表头/行数始终校验。

# Migration / 部署 / 回滚

- 数据库 Migration：不适用。
- 依赖升级：不适用，继续使用已锁定 openpyxl。
- 部署：随正常代码 Release；不需要数据迁移。
- 回滚：回退本 Change 的 Exporter/入口/文档提交即可；底层 JSONL、Contract、数据库均未改变，不需要数据回滚。

# 风险

- 列投影配置错误：通过非空、合法列、无重复的 fail-closed 校验处理。
- 隐藏 `内容ID` 后不能用该列做 reopen 验证：仍强制校验 Sheet、实际表头和行数；只有该列可见时再校验首个内容 ID。
- 样式对大文件性能影响：只使用固定字体/填充/列宽/行高/冻结/筛选，不做 autofit、复杂条件格式或全表扫描。
- 共享样式变化会影响 TikHub/正式默认 Excel 外观，但不改变字段和值；这是本次用户明确要求的统一视觉调整。

# 任务

- [x] 读取仓库规则、Blueprint、共享 Exporter/Contract/测试和附件真实格式
- [x] 建立列投影、默认 imports_test 10 列和附件样式的失败测试并确认 Red
- [x] 实现共享 Exporter 最小列投影与统一样式
- [x] 接线 `imports_test` 默认列配置
- [x] 重写 `imports_test/README.md` 为使用说明
- [x] 更新 Blueprint 13 长期规则
- [x] 运行目标/相关测试、Ruff、mypy、Contract/架构/Secret/Docs 并取得 Green
- [ ] 最终 PR head 适用 workflows 全部成功
- [ ] 两阶段 Review、正常 PR 合并、Change 归档

# 验证

## 计划

- 目标测试：`tests/unit/platform/test_excel_export.py`、`tests/unit/collection/test_imports_test_export.py`、`tests/unit/collection/test_p1g_imports_run_all.py`
- 相关测试：P1/Analysis/Export 测试集合与完整 `tests/unit`
- 静态/契约：Ruff format/check、mypy、contract generation/check、architecture、secret、docs
- 格式：自动测试检查冻结首行、AutoFilter、表头填充/字体、行高、网格线、列宽、页边距/方向、超链接与重新打开可用性。
- CI：PR 最终 head 的适用 workflows 全部成功后才合并。

## 新鲜证据

Red（PR #80 head `fb1d619f6d8481b7055e40c8c1a01808ef89a82e`）：Stage 5A Provider Raw run `32220675358` 的 P1 Excel/Analysis/Export 测试得到 `6 failed, 74 passed in 3.27s`。失败均为目标行为尚未实现：`EXCEL_CONTENT_COLUMNS` 不存在、`export_labeled_excel()` 未传列配置、共享 Exporter 不接受 `content_columns`；Secret 与 Docs gates 同轮成功。

Green（实现/文档 head `cdea0b685951e3c1d610ffa411b1f237d5f60c41`）：Stage 5A Provider Raw run `32221143932` success：

- P1 Excel/Analysis/Export 测试：`80 passed in 3.27s`；
- P1 Ruff format/check：通过，40 files already formatted / All checks passed；
- P1 mypy：`Success: no issues found in 24 source files`；
- Analysis/Export Contract 生成与 drift：通过，确认 `UnifiedDataExcelV1` Schema 未变化；
- Architecture、Secret、Docs gates：通过；
- Provider/Raw 相关测试：`24 passed in 0.46s`；
- Stage 5A 全仓 Ruff format/check、mypy、架构、table ownership、Secret、Docs 质量门禁全部通过，其中全仓 mypy 为 `Success: no issues found in 168 source files`。

本 Change 元数据收口后仍以新的最终 PR head workflows 作为合并门禁。

# 文档影响

- `imports_test/README.md`：整体重写为人工使用指南，包含默认 10 列、全部可选内容列、配置示例、运行步骤、输出目录、模型配置与排错。
- Blueprint 13：从“固定完整列且调用方不可选”调整为“完整数据契约 + 共享 Exporter 的受控展示投影”，并固化统一样式规则。

# 交付

- Change 初始化 Commit：`2f87db73acc0686b840b4df91daaf1fe00bfc24b`
- Red 测试 Commit：`234f62e5542a22eaa6596fc22b09f29a7d309824` 至 `fb1d619f6d8481b7055e40c8c1a01808ef89a82e`
- 共享 Exporter 实现 Commit：`c21373b78bf5823eefd6cfbe0e21984eff968694`
- imports_test 接线 Commit：`d4d93ab92e23fe770aaf5dd43f92afbeb8088d6c`
- 文档 Commit：`3816a9e84b1097580fa5e348c98efac6756f531e`、`d972c8371631516056241553006393e8706521d4`、`cdea0b685951e3c1d610ffa411b1f237d5f60c41`
- PR：#80，当前 Draft；最终 head workflows 全绿后转 Ready 并正常合并。
- 发布：不独立部署，随正常 PR 集成。
