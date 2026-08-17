# 统一数据 Excel 导出与调试复用

## 1. 定位

本设计负责的是**采集基础数据明细 Excel 导出**，不是舆情分析报告、汇报材料或 Report Renderer。

这里的“原始数据 Excel”含义是：

```text
各平台 Provider Raw
→ 各平台正式 Mapper
→ CanonicalContentV1 / CanonicalCommentV1
→ CanonicalContentAggregateV1 或等价的 Provider-neutral 导出 Read Model
→ 统一 Excel 数据导出
```

Excel 中展示的是帖子/笔记/视频、作者、指标、一级评论、二级评论及其关系等**未经过舆情分析加工的基础采集数据**。TikHub/其他 Provider 的完整原始响应 JSON 仍由 Raw Artifact/调试 Raw 文件保存，不能为了 Excel 展示把 Provider 私有 JSON 变成第二套公共数据结构。

分析报告是另一条能力：

```text
Canonical / Query Read Model
→ Analysis
→ Report Context
→ Report Renderer
```

数据 Excel 导出与报告 Renderer 不得共用含混的“导出/报告”实现，也不得把分析结论写进基础数据导出模块。

## 2. 统一数据结构

小红书、抖音、微博、B站、快手等平台的 Provider 响应结构可以不同，但进入系统公共边界前必须由各自正式 Mapper 转为统一 Canonical。

长期事实源：

- 原子内容：`CanonicalContentV1`；
- 原子评论：`CanonicalCommentV1`；
- 查询、页面、AI 和正式数据导出的完整帖子视图：`CanonicalContentAggregateV1`；
- Provider Raw 只负责保留外部原始证据，不作为 Excel 公共列定义。

因此正式 Excel 导出不能按 TikHub、小红书、抖音分别维护一套字段映射。平台差异在 Mapper 之前解决；Excel 只消费 Provider-neutral 数据。

如果未来正式导出确实需要一个专用 Export Read Model，只允许从 Canonical/Aggregate 确定性派生，并在对应 Change 中明确 Owner、输入输出和测试；不得重新读取 Provider 私有字段补列。

## 3. 当前 `tikhub_test` 的阶段性实现

在正式系统级数据 Excel 导出尚未开发完成前，`backend/src/aima_ugc/adapters/providers/tikhub_test/` 允许保留一个**阶段性原始数据 Excel 实现**，用于真实 Provider 调试闭环。

当前边界：

```text
TikHub 正式 Operation / Transport / Mapper
→ CanonicalContentV1 / CanonicalCommentV1
→ tikhub_test 临时 RawDataContent / RawDataCommentRow
→ tikhub_test/excel.py
→ <platform>_raw_data.xlsx
```

它的存在只为当前调试工具在系统级导出能力缺失时提供可读结果，不代表已经形成第二套长期 Export Contract。

必须保持：

- Excel 数据来自正式 Canonical，不直接解析 Provider Raw；
- 完整 Provider Raw 继续独立保存；
- 外部 ID 按文本写入；
- 一级/二级评论保留 `external_comment_id`、`root_comment_id`、`parent_comment_id`；
- `comment_coverage`/等价覆盖状态可追溯；
- 外部文本防 Excel 公式注入；
- 原始数据 Excel 展示格式不能反向成为 Canonical Schema。

## 4. 正式系统级数据导出的复用门禁

未来开发正式“导出 Excel”功能时，**开始编码前必须读取本文和 `tikhub_test/README.md` / `tikhub_test/excel.py` / 对应测试**，并把“收敛两套 Excel 实现”列为该 Change 的验收项。

正式导出能力只有满足以下闭环，才允许宣称完成：

1. 明确统一数据导出的业务范围、筛选条件、权限、最大数据量、同步/Job 边界、文件生命周期和验收样例；
2. 导出核心只消费 `CanonicalContentAggregateV1` 或经批准的 Provider-neutral Export Read Model，不读取 TikHub/平台私有 JSON；
3. 建立唯一共享原始数据 Excel Exporter（具体模块路径由未来 Change 基于当时仓库结构确定，本文不提前冻结目录）；
4. 共享实现覆盖内容区块、一级/二级评论关系、文本 ID、时间、URL、长文本、覆盖状态、公式注入防护和可打开性验证；
5. 系统业务导出和 `tikhub_test` 都调用同一个共享 Excel 导出实现；
6. **删除 `tikhub_test/excel.py` 中已经重复的导出实现，以及只为该重复实现存在的 `RawDataContent` / `RawDataCommentRow` / `RawDataBlock` 等临时显示模型；**如果某个类型仍有独立用途，必须说明用途并避免复制共享 Export Model；
7. 把通用 Excel 单元测试迁移到共享导出模块；`tikhub_test` 只保留“真实/Fixture Canonical 能进入共享 Exporter 并成功生成文件”的集成级回归；
8. 更新 `tikhub_test/README.md`、根 README、测试说明和受影响 Blueprint，明确当前已无第二套 Excel 实现；
9. PR Review 必须搜索仓库中的 `.xlsx`/`openpyxl`/Excel exporter 相关实现，确认没有两个独立的内容+评论数据导出器继续并存。

这是一项**硬迁移门禁**，不是可选清理。正式系统数据导出完成但仍保留 `tikhub_test` 的平行 Excel 生成逻辑，视为功能未完全收口。

## 5. 依赖规则

当前 `tikhub_test` 因阶段性实现可使用锁定的 `openpyxl`。未来共享导出模块落地后：

- 如果共享 Exporter 继续使用 `openpyxl`，依赖由共享能力拥有，`tikhub_test` 只调用共享代码；
- 如果未来经独立 Change 决定更换 Excel 技术实现，必须先比较兼容性、样式、可编辑性、性能和维护成本，再迁移共享 Exporter；
- 不允许 `tikhub_test` 因共享模块改技术而继续私自保留旧 `openpyxl` 路线。

## 6. 与报告能力的边界

基础数据 Excel 导出回答的是：

> “系统当前采集到了哪些帖子、指标和评论？”

报告回答的是：

> “这些数据说明了什么、风险/趋势/结论是什么？”

两者可以读取同一 Canonical/Query 事实，但业务语义、Job、权限、模板和验收标准不同。后续任何 Change 不得因为都能生成 `.xlsx` 或文件，就把数据导出与报告渲染合成一个万能模块。
