# 采集运行中心 Figma 开发基线

本文维护 `/collection-runtime` 的正式 Figma 与当前 Vue 实现之间的长期映射。目标是让设计先在正确 Owner 上收敛，再由正式页面实例和代码消费；它不复制 API Schema，也不把 Figma 示例数据变成生产事实。

## 1. 正式事实源

- Figma 文件：`qmZEFvPrB8u9JX5fyqc93S`
- 页面：`3500:2023`（采集运行中心）
- 正式主页面：`3500:2025`
- 设计与开发规范：`7099:27523`
- 四层 Owner Governance：`7840:9761`
- 当前 Route：`/collection-runtime`
- 当前页面 Owner：[`frontend/src/features/import-batches/pages/CollectionRuntimePage/`](../../frontend/src/features/import-batches/pages/CollectionRuntimePage/)

Figma 负责布局、视觉层级、组件复用、用户可见状态和交互意图。HTTP 字段、Capability、Cursor、Job/Run/Campaign 状态、资格条件和错误语义继续以当前 Contract、generated client、Store/API 与服务端实现为准。

## 2. 四层 Owner 链路

| 层级 | Figma Owner | 职责 | 代码 Owner |
| --- | --- | --- | --- |
| L1 | `01 设计规范`、`02 公共组件` | 颜色、字体、间距、圆角，以及 Button、PageHeader、DateRange、Tabs、Feedback、Empty、Modal/Drawer Shell 等跨页面视觉 API | `frontend/src/shared/styles/`、`frontend/src/shared/ui/` |
| L2 | `03 页面模板` | PageShell、列表/筛选/详情/任务进度等稳定组合方式，不保存采集运行业务状态 | `frontend/src/app/layouts/AppShell.vue` 与共享页面组合规则 |
| L3 | `4798:10640` 页面公共组件区 | 采集运行 KPI、筛选、七列表格、状态进度、Cursor、导入 Modal 内容、补采与详情 Drawer 内容 | `CollectionRuntimePage/components/`；跨组件数据由 `features/import-batches/store.ts` 持有 |
| L4 | `3500:2023` 下正式页面实例 | 主页面、Tab、流程状态、详情、撤销、Compact/Wide 等可验收 Screen；只组合上游 Owner | `CollectionRuntimePage.vue` 及真实 Route 实例 |

同步顺序固定为：

```text
L1 设计规范 / 公共组件
→ L2 页面模板
→ L3 页面公共组件 / Feature Owner
→ L4 正式页面实例
→ Vue 现有实现 Delta
→ Browser / CI 验收
```

稳定的公共视觉变化应先修改 L1 或 L2；采集运行业务块修改 L3；L4 只组合并展示状态。不要在多个正式 Frame 上分别复制同一修复。

## 3. 正式页面与状态节点

### 主页面与响应式

| 场景 | Node | 验收重点 |
| --- | --- | --- |
| 全部运行 / 1440 基准 | `3500:2025` | 标题操作、三 KPI、三 Tab、五项筛选、七列表格、Cursor |
| 数据导入 Tab | `3500:2311` | 只投影真实导入类型，不建立第二套列表 |
| 辅助补采 Tab | `3500:2588` | 只投影真实补采类型，Capability 仍来自服务端 |
| Compact 1180 | `4742:2404` | 固定 180px 侧栏；工作区弹性；表格局部横向滚动 |
| Wide 1920 | `4742:2603` | 主要信息列吸收宽度；状态与操作列保持可读 |
| 状态规格 | `3500:5609` | Loading、Empty、Error/Retry、导入与 Provider 不可用状态 |

### 导入、补采与详情

| 场景 | Node | 代码 Owner |
| --- | --- | --- |
| 导入数据 / 本地电脑 | `3500:2875` | `DataImportDialog.vue` |
| 导入数据 / 服务器目录 | `3500:3029` | `DataImportDialog.vue` |
| 预检就绪 / 运行 / 完成 | `3500:3348`、`3500:3648`、`3500:3951` | `DataImportDialog.vue` + Store/服务端 Campaign 状态 |
| 辅助补采 / 主动发现 | `3500:4257` | `TikHubSupplementDrawer.vue` |
| 辅助补采 / 基于批次 | `3500:4408` | `TikHubSupplementDrawer.vue` |
| 数据导入详情 | `3500:4557` | `ImportBatchDetailDrawer.vue` |
| 辅助补采详情 | `3500:5216` | `CollectionRunDetailDrawer.vue` |
| 撤销影响 / 不可撤销 / 已撤销 | `5140:7670`、`5143:7905`、`5143:8216` | `DataImportDialog.vue` + 服务端撤销资格与结果 |

Prototype 只表达用户如何从创建进入状态、从列表进入详情；Vue 必须继续根据真实返回结果驱动 Modal/Drawer 和状态，不能用固定延时或假成功替代后端事实。

## 4. 页面结构 Contract

正式主页面保持以下用户层结构：

1. 页面标题“采集运行中心”和刷新、导入、新建辅助补采三个操作。
2. “处理中 / 今日完成 / 今日入库内容”三张 KPI，值来自 Summary API。
3. “全部运行 / 数据导入 / 辅助补采”三个 Tab。
4. 搜索、北京时间日期范围、状态、类型五项筛选与查询/重置动作；不在默认层暴露内部 Stage。
5. 任务、类型、状态与进度、处理环节、处理结果、创建时间、操作七列表格。
6. Cursor 分页、Loading、Empty、Error/Retry，以及导入/补采详情入口。

内部 UUID、Job 身份和原始错误信息只进入技术详情或诊断层。Figma 中的任务名、数量、进度和时间只用于表达布局。

## 5. 响应式 Contract

- 1440×900 是桌面视觉参考，不是生产固定宽高。
- 侧栏保持 180px，右侧工作区使用剩余空间；页面内容保留 24px 水平内边距。
- 视口大于 1120px 时，筛选控件单行优先并允许自然收缩。
- 视口不大于 1120px 时，筛选控件稳定为两列；不大于 720px 时单列兜底。
- 运行表最小可读宽度为 1212px；空间不足时只有表格区域使用原生 `overflow-x: auto`，页面本身不整体横滚或缩放。
- 1180/1200/1280 验证紧凑窗口，1440 验证基准，1920 验证宽屏；1100/1120 专门验证筛选断点。
- 所有宽度下都必须能到达表格操作列，不删除列或隐藏真实动作来“适配”。

## 6. 真实数据与交互边界

以下事实不由 Figma 接管：

- `GET /api/v1/collection-runtime/runs` 的 cursor + limit 和 `next_cursor + has_more`；
- `GET /api/v1/collection-runtime/summary` 的 `Asia/Shanghai` 今日口径；
- Data Import Campaign、兼容 Excel Import、TikHub discovery/batch supplement 的状态与资格；
- Provider/Platform/Search Config 和补采能力；
- 只有活跃任务且页面可见时约每 5 秒静默刷新；
- Campaign 开始、取消、重试、撤销、冲突详情和任务中心深链；
- Error Contract、request ID、技术错误码与恢复语义。

修改视觉时从页面动作反查 Store、Feature API 和 generated client。没有后端字段或能力时，应保留诚实的禁用/不可用状态，不能为了演示补假数据或平行接口。

## 7. Design-to-Code 验收

每次视觉或交互变化至少完成：

```text
Fresh Figma Design Context / Screenshot
→ Visual / Interaction / State 对照
→ Responsive / Component-Owner 对照
→ Data-Contract 反向审计
→ Unit / Browser Mock / Lint / Typecheck / Build
→ current-head CI
```

对照结论必须明确记录为：代码跟随既有 Figma、Figma 已同步长期设计变化，或仍有待人工确认的设计差异。Browser Mock 可覆盖视觉状态和请求语义，但不能冒充真实后端、PostgreSQL、Worker 或外部 Provider 证据。

## 8. 修改入口

- 页面编排：`CollectionRuntimePage.vue`
- KPI：`components/CollectionRuntimeKpiCards.vue`
- 筛选：`components/CollectionRuntimeFilters.vue`
- 七列表格：`components/CollectionRuntimeTable.vue`
- 状态进度：`components/CollectionRuntimeStatusProgress.vue`
- 导入 Modal：`components/DataImportDialog.vue`
- 补采 Drawer：`components/TikHubSupplementDrawer.vue`
- 详情 Drawer：`components/ImportBatchDetailDrawer.vue`、`components/CollectionRunDetailDrawer.vue`
- 页面共享状态：`frontend/src/features/import-batches/store.ts`
- Feature API：`frontend/src/features/import-batches/api.ts`
- 机器接口：`frontend/src/generated/api/`（只生成，不手改）

公共视觉变化先检查 `frontend/src/shared/ui/` 与 `frontend/src/shared/styles/`；只有真实跨 Feature 复用时才提升 Owner，页面私有业务组件继续留在 Feature 内。
