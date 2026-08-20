---
schema: rvc-change/v1
id: "CHG-20260820-configurable-excel-sheet-columns"
title: "imports_test Excel导入展示与报告周期配置"
level: L3
status: done
owner: "codex"
branch: "main"
created: 2026-08-20
updated: 2026-08-20
depends_on: []
affected_areas:
  - "excel-export"
  - "excel-import"
  - "platform-reporting"
  - "imports-test"
affected_paths:
  - "backend/src/aima_ugc/adapters/providers/imports/excel_profile.py"
  - "backend/src/aima_ugc/adapters/providers/imports/excel_reader.py"
  - "backend/src/aima_ugc/adapters/providers/imports/convert.py"
  - "backend/src/aima_ugc/adapters/providers/imports/models.py"
  - "backend/src/aima_ugc/platform/export/excel.py"
  - "backend/src/aima_ugc/adapters/providers/imports_test/test.py"
  - "backend/src/aima_ugc/adapters/providers/imports_test/generate_report.py"
  - "backend/src/aima_ugc/adapters/providers/imports_test/README.md"
  - "backend/src/aima_ugc/platform/reporting/excel_report.py"
  - "backend/src/aima_ugc/platform/reporting/README.md"
  - "docs/blueprint/13-统一数据Excel导出与调试复用.md"
  - "tests/unit/platform/test_excel_export.py"
  - "tests/unit/platform/test_offline_reporting.py"
  - "tests/unit/platform/test_imports_test_reporting.py"
  - "tests/unit/collection/test_imports_test_run_directory.py"
  - "tests/unit/collection/test_imports_test_export.py"
  - "tests/unit/collection/test_p1g_imports_run_all.py"
  - "backend/src/aima_ugc/adapters/providers/imports_test/keyword_pack.txt"
  - "tests/unit/collection/test_imports_keyword_pack.py"
  - "tests/unit/collection/test_imports_excel.py"
contracts: []
data_changes: []
---

# 目标

让 `imports_test` 生成的统一 Excel 中“内容”“标签明细”“评论”三个 Sheet 都能分别通过
有序列名配置决定显示列与顺序，同时保持共享 Exporter、Provider-neutral 数据契约和其他调用方
的既有默认输出不变。

在同一批本地 Excel 导入中，兼容来源工具写错的 Worksheet dimension 元数据；允许自动扫描
工作簿 Sheet，并只按 Canonical 映射实际需要的表头判断候选，不校验字体、字号、颜色等样式。

报告生成阶段支持显式北京时间自然日闭区间。上游转换、关键词、去重、数据库、AI 和最终
Excel 保持全量；仅报告统计、图表和明细按周期筛选，并交叉校验内容与标签明细一致性。

# 成功标准

- [x] `imports_test/test.py` 提供内容、标签明细、评论三个独立的非空列配置。
- [x] 每个配置只显示共享 Exporter 已知列，并严格按配置顺序写出。
- [x] 空配置、重复列、未知列和单个字符串都在发布 Excel 前明确失败。
- [x] `export_unified_data_excel()` 与 `export_unified_content_jsonl_to_excel()` 未传新增参数时，
  三个 Sheet 的表头、顺序、数据、样式和验证保持兼容。
- [x] 隐藏“内容ID”只影响 Excel 展示；`external_content_id` 继续保留在
  `UnifiedDataExcelV1`/归一化记录中，标签行和评论关系语义不变。
- [x] “内容”和“标签明细”展示“二级标签”时，数据行高根据二级标签实际换行/列宽占用
  确定性计算；单行不少于默认行高，并有明确上限。
- [x] raw/labeled 使用同一组三 Sheet 配置；其他平台不新增平行 Exporter。
- [x] 目标、模块、Contract/文档、格式、静态、类型、构建与相关回归取得新鲜证据。
- [x] `read_only=True` 时忽略不可信的 Worksheet dimension，第二个真实文件能读出真实 13 列。
- [x] 自动模式扫描全部 Sheet，优先合法默认 Sheet，否则选择唯一合法 Sheet；多项歧义时拒绝。
- [x] 显式 Sheet 名继续只使用指定 Sheet，不静默切换。
- [x] Sheet 只强制 `媒体名称（中文）`/`标题`/`内文`/`作者`/`出版日期`/`原文链接`
  六个源表头；文章编号、粉丝数和其他无关列可缺失。
- [x] 无关列缺失或重名不阻断导入；必需列重名会明确报错。
- [x] Sheet 资格判断和行读取均不依赖字体、字号、颜色、边框或其他样式。
- [x] `generate_excel_report()` 与 `imports_test.generate_report()` 接受可选报告日期闭区间。
- [x] `test.py` 和独立 `generate_report.py` 均可显式配置报告周期，上游处理保持全量。
- [x] 周期内内容、标签、评论统计分别按发布时间、内容发布时间和评论时间筛选。
- [x] 内容与标签明细的周期内平台、情感、一级/二级标签及标签对不一致时拒绝报告。
- [x] 周期外排除数量进入报告质量说明和返回摘要，不混入统计或图表。

# 范围

- 为共享 Exporter 增加标签明细列和评论列的可选有序投影参数。
- 在 `imports_test` 暴露并传递三个 Sheet 的默认列配置。
- 在共享 Exporter 流式写每行时，仅根据所展示的“二级标签”计算“内容/标签明细”行高。
- 更新共享 Exporter、`imports_test` 单元测试与 Blueprint/README 当前事实。
- 使用小型测试工作簿验证三张表的表头、数据、样式、二级标签行高与重新打开校验。
- 修复生产 Excel Reader 对错误 dimension 元数据的读取，并增加自动 Sheet 发现与最小表头规则。

# 非目标

- 不允许隐藏整个 Sheet；三个 Sheet 继续固定存在。
- 不增加自定义字段、公式列、列别名或运行时从 `.env` 读取展示配置。
- 不改变 Canonical、Analysis、`UnifiedDataExcelV1`、JSON Schema、数据库或去重/打标语义。
- 不修改用户最近提交的 Excel 输入路径和 `run_all()` AI 打标流程勘误。
- 不根据标题、正文或其他列自动行高，不对“评论”Sheet 自动行高，不扫描已写出的工作簿。
- 不模糊匹配或重命名源表头，不扫描第一行以外的位置猜测表头，不校验 Excel 视觉样式。
- 不升级依赖，不修改 `tikhub_test` 默认列。
- 不在报告前过滤 Canonical/filtered/deduplicated，不减少或重跑已有 AI 请求，不改写最终 Excel。
- 不在当前任务定义新的语义相关性模型或自动解决源数据内容冲突。

# 必须保持不变

- 现有只传 `content_columns` 的调用保持合法；新增参数都有 `None` 默认值。
- `None` 继续表示该 Sheet 的完整共享默认列。
- 固定 Sheet 名称和顺序仍为“内容 / 标签明细 / 评论”。
- 行生成、外部 ID 文本格式、超链接、公式注入防护、筛选、宽度和导出后重开校验不变。
- “标签明细”的“内容ID”继续投影自必填 `external_content_id`，不是数据库内部 UUID。
- 每行仍必须能解析平台，并从文章编号或原文链接建立稳定身份；坏行继续阻止发布部分 JSONL。

# 关键决策

- 已确认事实：`deduplicated/contents.jsonl` 包含 `external_content_id`；共享导出器把它展示为
  “内容ID”，用于跨 Sheet 关联。用户要求列可隐藏，不要求删除底层字段。
- 用户已确认采用方案 A：共享入口新增 `label_detail_columns` 和 `comment_columns`，
  `imports_test` 使用 `EXCEL_CONTENT_COLUMNS`、`EXCEL_LABEL_DETAIL_COLUMNS`、
  `EXCEL_COMMENT_COLUMNS` 三个同构元组。优点是与现有入口连续、调用清晰、默认兼容；代价是
  公共函数新增两个可选关键字参数。
- 实施期间用户在同一工作区把 `imports_test` 的标签明细配置改为包含正文、作者、发布时间、
  命中关键词等归一化内容列，把评论配置改为包含父内容标题/正文。实现保留这些用户配置：
  标签明细可选择全部内容共享列，一级/二级标签按当前标签对替换；评论可选择评论列和父内容
  共享列，重名的作者/来源字段保持既有评论语义。这些都是同一归一化记录的既有字段，不新增
  私有数据 Contract。
- 方案 B：新增一个 `sheet_columns` 字典，以中文 Sheet 名映射元组。优点是一个参数；缺点是
  Sheet 名字符串成为调用方配置键、类型和错误定位更弱，并与现有 `content_columns` 形成两种接口。
- 方案 C：新增 `ExcelColumnSelection` 配置对象。优点是集中封装；缺点是当前只有三个元组，
  新类型和构造层增加不必要复杂度。
- 用户同时确认行高策略：保持 `write_only=True`，写行前按二级标签的显式换行数
  及固定 24 字符列宽估算显示行数，使用 `默认行高 × 显示行数`，并限制为 Excel 可读的
  有界高度；若该 Sheet 隐藏“二级标签”则保持默认行高。这样结果不依赖不同 Excel/WPS
  客户端的自动适应行为，也不需要导出后全表二次扫描。
- 版本依据：仓库锁定 openpyxl 3.1.5；官方 3.1 文档确认 write-only 只能顺序 append，
  `RowDimension.height` 是明确行高字段，因此采用流式写入时同步设置行高，而不是保存后回读重写。
- 兼容：新增参数均可选，默认输出不变；`imports_test` 新增配置，不移除现有内容配置。
- 已确认根因：`惠科data(0817-0819).xlsx` 的“文章”Sheet 在元数据中声明 `A1:A1`，
  `read_only` Reader 因而只看到“序号”；调用 `reset_dimensions()` 后可读取真实 13 列和数据。
- 用户确认 Sheet 的业务必需展示字段为平台、标题、正文、作者、发布时间和内容链接，因此精确要求
  对应源表头 `媒体名称（中文）`/`标题`/`内文`/`作者`/`出版日期`/`原文链接`。这只是表头存在性规则，不新增逐单元格
  非空规则。文章编号和粉丝数存在时 Mapper 仍使用，但不是 Sheet 必需表头；序号、监测项名称、版面、媒体类型、
  全文情感不影响 Sheet 资格。
- 自动选择规则：`sheet_name=None` 扫描全部 Sheet；合法默认 Sheet 优先，否则唯一合法候选自动
  选择；没有候选时报告各 Sheet 原因，多个非默认合法候选时拒绝歧义。显式字符串仍严格指定。
- Excel 样式从未进入 Reader/Mapper 数据边界，本次继续不读取或校验字体、字号、颜色和边框。
- 用户确认报告周期只在报告生成时生效，前序阶段继续全量处理。采用单一
  `REPORT_DATE_RANGE=(date, date)` 配置表达包含首尾日的闭区间；`None` 保持全量报告兼容。
- 报告日期 Scope 按三类业务时间分别筛选：内容发布时间、标签对应内容发布时间和评论时间。
  标签明细优先使用其发布时间；旧版默认投影没有发布时间时，通过两页内容ID关联。
- 为避免“内容页已筛选、标签页仍为全量”的静默错误，Reporter 在生成文件前交叉核对周期内
  标签记录数、平台、情感、一级/二级标签及标签对；不一致时 fail closed。
- 用户最终确认 `imports_test` 的真实付费 LLM 在人工执行打标阶段默认开启；仅导入模块和普通
  自动测试不会发送模型请求。只处理导入、去重或导出时可将 `ENABLE_REAL_LLM` 改为 `False`。
- Migration/部署：无数据库或数据 Migration；普通代码部署即可。
- 回滚：回退实现、测试和文档提交即可；既有 Excel/JSONL 无需迁移或重写。

# 任务

- [x] 调查当前实现和事实源
- [x] 建立失败测试或说明测试例外
- [x] 完成最小实现
- [x] 同步受影响文档
- [x] 取得新鲜验证证据
- [x] 建立错误 dimension、必需表头、无关重名列、自动 Sheet 和歧义选择的 Red 测试
- [x] 实现生产 Reader/Converter 最小修复
- [x] 用两个真实源文件验证首行读取、自动选择与完整 Canonical 转换
- [x] 同步源 Excel 要求和排错文档
- [x] 建立报告周期筛选、入口透传和跨 Sheet 漂移的 Red 测试
- [x] 实现共享周期筛选、摘要排除计数和一致性校验
- [x] 修改 `test.py` 与独立 `generate_report.py` 的周期配置和调用
- [x] 用现有全量打标 Excel 实际生成 2026-08-13 至 2026-08-19 报告

# 验证

## 计划

- 目标测试：`uv run pytest tests/unit/platform/test_excel_export.py tests/unit/collection/test_imports_test_export.py tests/unit/collection/test_p1g_imports_run_all.py -q`
- 导入目标测试：`uv run pytest tests/unit/collection/test_imports_excel.py tests/unit/collection/test_p1g_imports_run_all.py -q`
- 相关测试：`uv run pytest tests/unit/platform tests/unit/collection -q`、`uv run pytest tests/unit -q`
- Contract/文档：共享 Excel JSON Schema 生成/漂移检查（若现有命令适用），四项质量脚本。
- 静态检查/构建：`uv run ruff format --check backend tests scripts`、
  `uv run ruff check backend tests scripts`、`uv run mypy backend/src`、`uv build`。

## 新鲜证据

- Red：目标测试首次运行 `11 failed, 17 passed`，失败原因分别为共享入口尚不接受两个新增参数、
  `imports_test` 尚无两个新配置及调用未传参。
- Green：目标测试 `29 passed in 1.33s`，覆盖三页顺序投影、归一化内容列、非法配置、默认兼容、
  二级标签 14.5 倍数行高、409 上限与隐藏列行为。
- 模块回归：`tests/unit/platform` 为 `48 passed, 1 skipped`；`tests/unit/collection` 为
  `270 passed`。后者首次发现用户新增 `AIMA` 后旧断言仍为 103，按当前词包事实更新为
  104 个源词、97 个有效词后通过。
- 完整单元测试：`420 passed, 1 skipped in 8.83s`。
- 格式/静态：`uv run ruff format --check backend tests scripts` 为 349 files already formatted；
  `uv run ruff check backend tests scripts` 为 All checks passed。
- 类型：`uv run mypy backend/src` 检查 183 个源文件，无问题。
- 质量门禁：Architecture、Table Ownership、Secret Scan、Docs 四项脚本均退出 0。
- Contract：生成物漂移检查和兼容性检查均退出 0。
- 构建：`uv build --wheel` 成功生成 `dist/aima_ugc-0.1.0-py3-none-any.whl`。
- 文件与视觉：生产共享 Exporter 生成的小型工作簿由 openpyxl 导出后校验重新打开；再用本地
  Spreadsheet 渲染器渲染三张表，确认表头/列顺序、内容页 3 行标签、标签明细 1/2 行标签和
  评论页默认行高无溢出或遮挡。
- 新需求 Red 前根因实验：第一个真实文件生产 Reader 读取到数据行 2；第二个文件报缺少除
  “序号”外的 12 列。只读检查显示其 dimension 为 `A1:A1`，`reset_dimensions()` 后立即读出
  与第一个文件相同的 13 列表头及真实数据行。
- 导入新需求首次 Red：旧 13 列强制校验、错误 dimension 与缺少自动 Sheet 发现导致
  `7 failed, 14 passed`；继续收紧“只检查需要数据”时，无关重名列放行/必需重名列拒绝测试为
  `2 failed, 27 passed`，失败原因均为旧实现拒绝所有重名表头。
- 导入目标 Green：`tests/unit/collection/test_imports_excel.py` 与
  `tests/unit/collection/test_p1g_imports_run_all.py` 为 `37 passed in 1.79s`，覆盖六个必需列逐列缺失、
  无关/必需重名列、错误 dimension、自动/显式 Sheet 与多文件每文件实际 Sheet 来源。
- 真实文件抽样：两文件各读取前 100 行，均自动选择“文章”、识别 13 个实际表头，
  六个必需表头无缺失。
- 真实文件完整本地 Canonical 转换（不进入关键词或 AI）：共 `131320` 行全部写出、
  `0` 行拒绝；第一份 `75279` 行，第二份 `56041` 行。临时产物已删除。
- 用户确认付费模型默认开启后，入口默认值、回归测试和文档已统一为
  `ENABLE_REAL_LLM=True`；关闭开关时的 fail-closed 测试继续保留。
- 本轮最终静态/类型/门禁：Ruff 格式检查 `349 files already formatted`，Ruff 静态检查通过，
  mypy 检查 `183` 个源文件无问题；四项质量脚本、Contract 生成物漂移/兼容检查、Wheel 构建均退出 `0`。
- 报告周期 Red：共享入口、`imports_test` 透传和配置测试首次为 `4 failed`，原因是尚无
  `report_date_range`/`REPORT_DATE_RANGE`；跨 Sheet 漂移测试同时证明旧实现不会拒绝被篡改标签。
- 报告周期 Green：报告、默认模板、DOCX 包和 `run_all` 相关回归为 `24 passed in 1.82s`，
  覆盖三 Sheet 周期筛选、周期外计数、旧版内容ID回退、跨 Sheet 一致性和入口透传。
- 真实全量 Excel 报告：从既有 `44684` 条全量打标内容生成 `2026-08-13` 至
  `2026-08-19` 报告，纳入 `44232` 条内容和 `62513` 条标签记录，排除 `452` 条周期外内容和
  `609` 条周期外标签；Markdown 没有 `2026-08-07` 至 `2026-08-12` 的趋势/明细。
- 真实 DOCX：ZIP CRC 通过，`14` 个 Office Chart、`14` 个内嵌 XLSX、XML/Relationship 和
  内嵌工作簿由 `verify_docx(..., expected_charts=14)` 重新打开校验通过，大小 `101906` bytes。
- 提交后完整 Unit 为 `440 passed, 1 skipped in 8.28s`，退出码 `0`。
- 当前全仓 Ruff 为 `351 files already formatted` 且静态检查通过；mypy 检查 `185` 个源文件
  无问题；Architecture、Table Ownership、Secret Scan、Docs 四项门禁退出 `0`。
- 当前 Contract 生成物漂移与兼容性检查退出 `0`；`uv build --wheel` 成功生成 Wheel，新增
  `generate_report.py`、共享 Reporter 和默认模板均已进入包。

# 文档影响

- 更新 `docs/blueprint/13-统一数据Excel导出与调试复用.md`，把列投影从仅内容扩展为三个
  Sheet，并记录源 Excel 自动 Sheet/最小表头边界和 Report Scope；更新
  `imports_test/README.md` 的三个配置示例、各 Sheet 可选列、源 Excel 读取规则与报告周期；
  更新 `platform/reporting/README.md` 的共享参数、筛选口径和失败边界。
- 其他 Blueprint、HTTP/OpenAPI、数据库与部署文档不受影响。

# 交付

- Commit：已按职责分批提交到本地 `main`：
  - `815dd39` 修复 Excel 导入工作表识别；
  - `60ea1d2` 支持三张 Excel 表配置展示列；
  - `1a2605e` 补充 AIMA 品牌关键词；
  - `197be81` 支持按指定周期生成报告。
- PR：未授权，不创建。
- Push：未授权，不推送远程；本地 `main` 当前领先 `origin/main`。
- 发布：不在本次范围。
