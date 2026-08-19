# 前端页面架构与 Figma 设计工作流

> 适用范围：Stage 8 及后续正式业务前端  
> 技术基线：Vue 3 + TypeScript + Vite + Vue Router + Pinia + Element Plus + ECharts  
> 相关文档：[`01-总体架构与技术选型.md`](01-总体架构与技术选型.md)、[`04-后端任务API与前端.md`](04-后端任务API与前端.md)、[`06-开发约束与分阶段实施.md`](06-开发约束与分阶段实施.md)、[`07-技术决策与实施门禁.md`](07-技术决策与实施门禁.md)

## 1. 目标

AIMA_UGC 的前端需要同时满足两件事：

1. 页面需求可以频繁变化，单页改版时尽量只影响该页面和真正需要变化的公共层；
2. 长期维护时不能因为 Vibe Coding、Figma 或代码生成速度快，就复制 API、Store、组件、样式和业务语义。

因此前端固定采用：

```text
单一 Vue SPA
+ App Shell
+ Shared 公共层
+ Feature 业务模块
+ Page 页面级隔离
+ OpenAPI 生成 Client
+ Figma 视觉/交互设计基线
+ Figma MCP 辅助 Design-to-Code
```

“页面独立”指页面的组合、私有组件和局部状态独立，不表示每一页成为独立 npm 工程、微前端或复制一套 API/Store。

## 2. 非目标

首版不做：

- 微前端；
- 一页一个独立 Vue 应用或独立构建工程；
- 同时维护 Vue/React 两套前端；
- 因 Figma/MCP 示例代码而引入 React、Tailwind 或第二套 UI 库；
- 自研 Button、Input、Select、Table 等基础控件库替代 Element Plus；
- 把所有局部 UI 状态都塞进 Pinia；
- Figma 与 Vue 源码的自动双向实时同步；
- 把 Figma 当成 API Contract、数据库 Schema 或业务规则事实源；
- 把 MCP 生成的参考代码未经适配、Review 和验证直接提交生产仓库。

只有出现真实规模、团队边界、独立发布或性能证据时，才重新评估微前端等更复杂方案。

## 3. 三类事实源必须分开

| 事实 | 负责的事实源 | 不负责什么 |
| --- | --- | --- |
| 页面视觉、布局、交互意图、设计状态 | Figma 中已确认的 Frame/Component/Variable | API 字段、数据库表、后端业务规则 |
| HTTP 数据与错误语义 | Pydantic Request/Response → FastAPI OpenAPI → 固定 OpenAPI → Orval Client | 页面视觉和组件布局 |
| 实际运行行为 | 当前 Vue 源码、生成 Client、测试和构建结果 | 替代尚未同步的产品设计决定 |
| Design-to-Code 上下文 | Figma MCP 读取的目标 Frame/Node、组件和变量上下文 | 最终可直接提交的项目源码 |

新页面或正式改版开始编码前，应先有可识别的 Figma 目标 Frame/Node；如果页面只修改业务行为而视觉完全不变，可以直接基于当前页面实现和 Contract 处理，不强制为了形式重新画一张设计稿。

如果 Figma 与当前已发布代码不一致：

- 尚未实现的新设计，以已确认 Figma 作为目标；
- 当前线上/仓库实际行为，以 Vue 源码和测试作为机器事实；
- 不允许长期保留“代码一套、Figma 另一套”而不说明哪一方是下一次修改基线。

## 4. 前端目录与依赖边界

Stage 8 正式业务页面按以下结构落地：

```text
frontend/src/
├─ app/
│  ├─ layouts/
│  ├─ router.ts
│  └─ routes.ts
├─ shared/
│  ├─ components/
│  ├─ styles/
│  ├─ composables/
│  └─ utils/
├─ features/
│  ├─ collection/
│  │  ├─ pages/
│  │  ├─ components/
│  │  ├─ api.ts
│  │  ├─ store.ts
│  │  ├─ models.ts
│  │  └─ tests/
│  ├─ content/
│  ├─ system/
│  └─ ...
├─ generated/
│  └─ api/
├─ App.vue
└─ main.ts
```

当前 Stage 1 的 `frontend/src/views/` 只是最小骨架。Stage 8 实现真实业务页时应逐步把路由目标收口到对应 `features/<feature>/pages/`，不得长期在 `views/` 和 `features/` 维护两份同一业务页面。

### 4.1 App 层

`app/` 只负责应用级结构和装配，例如：

- Router；
- 全站 Layout；
- Sidebar/Header 等 App Shell；
- 全局 Provider/Plugin 装配；
- Feature route 聚合。

App 层不保存某个 Feature 的业务规则。

### 4.2 Shared 层

`shared/` 只放真正跨 Feature 复用、没有单一业务 Owner 的内容：

- 通用展示组件；
- 设计 Token/公共样式；
- 无业务语义的通用 composable；
- 无业务语义的工具函数。

只有“多个 Feature 真实复用”或“明确属于 App Shell/统一设计系统”时才提升到 `shared/`。不要因为预计以后可能复用，就提前把页面私有组件抽成公共组件。

### 4.3 Feature 层

Feature 继续遵守 `04` 已确定的边界：

```text
Page / Component
→ Feature Store / local state
→ Feature API
→ generated client
→ HTTP API
```

- `api.ts` 只能包装生成 Client、统一 Feature 调用方式和必要的展示层适配，不重新定义 HTTP Request/Response Contract；
- `models.ts` 只保存明确需要的前端 View Model/展示类型，不复制生成 Client 已有的接口类型；
- Store 只拥有本 Feature 的共享业务/页面状态；跨 Feature 状态归真正 Owner，不复制 Store；
- 页面组件不直接手写 URL，不直接访问数据库，不理解 Provider 私有 JSON。

### 4.4 Page 层

一个正式页面是最小视觉变化隔离单元。页面有私有组件时采用：

```text
features/content/pages/ContentDetailPage/
├─ ContentDetailPage.vue
├─ components/
└─ ...仅在实际需要时增加的页面私有文件
```

规则：

- 页面私有组件留在页面目录；
- 同一 Feature 多页面真实复用后，提升到 `features/<feature>/components/`；
- 跨 Feature 真正复用后，再评估提升到 `shared/components/`；
- 不为目录对称建立空 `components/`、空 Store、空 composable 或空 README；
- 页面重构不能顺手改无关 Feature。

这样单页频繁改版通常只修改对应 Page；全站导航变化修改 App Shell；跨页面一致组件变化修改其真实共享 Owner。

## 5. UI 组件与 Design Token

### 5.1 Element Plus 是基础控件层

当前技术基线已经选择 Element Plus。业务页面优先复用 Element Plus，再在确有稳定 AIMA 语义时封装应用组件。

允许建立例如：

```text
PageHeader
FilterBar
StatusTag
JobProgress
EmptyState
```

前提是这些组件已经具有稳定的跨页面复用价值。禁止仅为了“设计系统看起来完整”一次性制造大量薄包装组件。

ECharts 继续作为当前图表基础；普通页面不得再引入另一套重复图表库。

### 5.2 Figma Variable 与代码 Token

Figma 中重复使用的颜色、字体、间距、圆角等应通过有语义的 Variable/Style 表达；代码侧使用 CSS Custom Properties 和 Element Plus 可配置变量承载对应语义，不为此新增 Tailwind、CSS-in-JS 或第二套主题运行时。

Stage 8 实现 Design Token 时，代码侧统一入口应放在 `frontend/src/shared/styles/`，具体 Token 名只在真实设计资产开始实现时确定，不在 Blueprint 预造完整 Token 清单。

规则：

- 优先语义名，不在多个页面散落相同 raw hex/spacing；
- Figma Variable 与代码 Token 必须能明确映射；
- 一次性、页面独有的尺寸不强制 Token 化；
- 修改全局 Token 前评估所有消费者，不以单页临时需求破坏全站样式。

## 6. Figma 文件怎样组织

长期 Figma 设计资产建议按职责组织，而不是按“每次需求”复制整套文件：

```text
Foundations
├─ Color / Typography / Spacing / Radius

Components
├─ 基础与公共组件

Patterns
├─ List / Detail / Filter / Job Progress / Empty / Error 等组合模式

Screens
├─ Dashboard
├─ Keyword Packs
├─ Collection Plans
├─ Collection Runs
├─ Content List
├─ Content Detail
└─ ...

Flows
└─ 关键页面交互流程
```

Figma 规则：

- 重复组件优先使用 Component/Variant；
- 重复设计值优先使用 Variable/Style；
- 布局优先使用 Auto Layout，减少无意义绝对定位；
- Layer/Component/Frame 使用能对应业务含义的名称；
- 一个交付给开发的页面必须明确目标 Frame，而不是只给整个 Figma 文件让 Agent 猜；
- 设计重要状态时至少考虑正常、Loading、Empty、Error；是否还需要 Disabled、Partial、权限等状态由具体页面需求决定；
- Figma 只描述用户可见/可交互设计，不复制完整 API Schema。

## 7. Figma MCP → Vue 的固定工作流

Figma MCP 的作用是把设计结构、组件、变量、截图/资产等上下文提供给 Coding Agent，不是项目源码生成器的最终事实源。

固定流程：

```text
目标 Figma Frame/Node
→ 读取设计上下文
→ 读取 AIMA_UGC 当前前端结构、现有组件和 Token
→ 判断应复用 App / Shared / Feature / Page 哪个 Owner
→ 将设计意图适配为 Vue 3 + TypeScript + 当前 Element Plus/ECharts
→ 接入 Feature API / Store / generated client
→ Unit / Type / Lint / Build / E2E
→ 与目标 Figma 状态做视觉核对
```

硬规则：

1. 设计转代码前先读取仓库当前事实，不从 Figma 单独猜项目技术栈；
2. MCP/Agent 输出即使出现 React、Tailwind 或其他参考形式，也只能当设计结构参考，未经独立技术变更不得因此加入项目；
3. 优先复用当前代码中已经存在且语义一致的组件和 Token，不重复生成近似组件；
4. 生成目录 `frontend/src/generated/api/` 继续只由 Orval/OpenAPI 维护，Figma 代码生成不得修改；
5. Figma 中出现的文字、状态和演示数据不自动成为后端 Contract；真实字段必须从已批准业务需求和 Pydantic HTTP Contract 取得；
6. 设计资产进入正式代码时使用真实导出资产或项目已有匹配资产，不用“看起来差不多”的临时占位长期冒充；
7. MCP 生成结果必须经过项目 Review 和验证，不因视觉接近就跳过类型、测试、错误状态和接口边界检查。

### 7.1 Code Connect

如果后续已经形成稳定的 AIMA 公共组件，并且当前 Figma 环境支持组件到代码的可靠映射，可以为高复用组件建立 Code Connect/等价映射，使 Agent 优先复用真实 Vue 组件。

它是增强项，不是 Stage 8 的前置条件。没有稳定组件前不要为了“以后可能有用”批量建立映射。

### 7.2 不做自动双向同步承诺

Figma 与 Vue 源码职责不同，不建立“修改一边自动无损同步另一边”的项目承诺。

如果因为紧急修复先改了代码：

```text
代码先修正
→ 验证真实页面
→ 把已确认的视觉/交互变化同步回 Figma
→ 下一次设计驱动修改继续以更新后的 Frame 为基线
```

可以使用当时可用的代码回流设计能力辅助同步，但最终仍要经过人工/业务确认，不能把自动回流结果当成新的产品决定。

## 8. 高频需求变化时怎样最快落地

### 8.1 只改视觉，不改数据语义

```text
Figma 目标 Frame 更新
→ 判断影响 Page / Feature Component / Shared / App Shell
→ 修改最小 Owner
→ 运行前端验证
→ 视觉核对
```

不改 Pydantic Contract、数据库或后端 Service。

### 8.2 页面需要新字段或新业务行为

```text
页面需求 + Figma 交互
→ 明确字段/行为语义
→ 先冻结 Pydantic HTTP Contract
→ API/Contract Test
→ 固定 OpenAPI
→ 生成 TypeScript Client
→ 前端 Mock/Fixture 与后端 Service 并行开发
→ Feature API / Store
→ Page
→ E2E
```

Figma 不能替代 Contract。页面如果需要一个后端不存在的新字段，不能只在前端 `models.ts` 猜一个同名字段继续开发。

### 8.3 公共视觉规则变化

如果多个页面同时变化，先判断是否实际上是：

- App Layout；
- Shared Component；
- Design Token；
- Feature 级公共组件。

只修改真正 Owner，一次修正所有消费者。不要复制修改到每个 Page。

### 8.4 前后端并行

前后端并行的切分点不是“后端先全部完成”，而是**页面所需 HTTP Contract 已经稳定并能生成 Client**。

Contract 固定后：

- 前端使用生成类型 + Fake/Mock 开发页面；
- 后端实现 Router/Service/Repository；
- 最后用真实 API Test/E2E 合流。

这样既能提高开发速度，也避免前后端分别手写同一个接口语义。

## 9. Store 与页面状态

Pinia 不等于“所有状态全局化”。

页面内只影响当前组件树的状态，例如 Drawer 展开、某个 Tab、本地输入草稿，优先留在 Page/Component/composable。

Feature Store 适合：

- 多组件共享查询条件；
- 当前 Feature 的跨页面状态；
- Job/Run 等需要多个组件共同消费的状态；
- 需要稳定缓存或恢复的页面级查询状态。

Store 不长期缓存服务端业务事实来代替数据库，也不复制后端复杂统计或 AI 规则。

## 10. 视觉与工程验收

每个正式页面至少验证：

### 10.1 工程验证

```text
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test -- --run
npm --prefix frontend run build
```

Stage 8 建立可执行 Playwright E2E 入口后，关键流程再运行对应 E2E。Blueprint 不能把尚未建立的脚本伪装成已经可执行。

### 10.2 页面状态验证

对该页面实际存在的状态检查：

- 正常；
- Loading；
- Empty；
- Error；
- 以及需求明确的 Disabled/Partial/Permission 等状态。

必须检查文本溢出、遮挡、裁切、图片比例、表格超宽、错误信息和交互反馈。

### 10.3 视觉核对

实现后用实际浏览器页面与已确认 Figma Frame 核对：

- Layout；
- 尺寸与间距层级；
- 字体层级；
- 颜色和状态；
- 组件复用是否正确；
- 关键交互。

自动像素级 Snapshot 不作为所有页面首版强制门禁，避免高频设计变化导致无价值快照更新；对稳定的 App Shell、Shared Component 或确实需要严格视觉回归的页面，再增加自动 Visual Regression。

响应式断点只按已批准需求验收。业务尚未确定移动端/平板断点时，不得由 Agent 静默猜一套产品要求。

## 11. Stage 8 实施顺序

Stage 8 开始后，前端按照最小纵切推进，不先一次性生成所有页面：

### 步骤 1：前端公共骨架

→ 修改范围：`app/`、`shared/`、必要的 Design Token、Feature/route 组织  
→ 预期结果：公共 Layout、路由和复用边界稳定，Stage 1 骨架能够承载正式业务页  
→ 验证方式：Lint、Type、Unit、Build、最小路由测试

### 步骤 2：逐个业务纵切

每次选择一个有完整业务价值的页面/流程：

```text
Figma Frame
→ 页面需求
→ HTTP Contract
→ generated client
→ Fake/Mock
→ 后端 Service/API
→ Feature API/Store
→ Vue Page
→ E2E/视觉验收
```

不要先用 Figma 一次性批量生成全部页面，再回头补接口和业务逻辑。

### 步骤 3：稳定后再抽公共资产

只有真实重复出现后，才把页面组件提升为 Feature/Shared Component，并按需要建立 Code Connect/等价设计映射和 Visual Regression。

Stage 8 实现时应建立 `frontend/README.md` 作为开发操作入口，说明新增页面、Figma Frame 交接、生成 Client、Mock、测试和本地运行方式；该 README 描述操作方式，不复制本 Blueprint 的设计原则。

## 12. 修改与文档同步规则

- 前端页面目录、共享边界、Figma/MCP 工作流、Design Token/设计系统规则变化：更新本文；
- HTTP Contract、错误、Cursor、Feature API 调用边界变化：更新 `04`，并按规则同步固定 OpenAPI/生成 Client/`docs/API接口说明.md`；
- Stage 8 阶段顺序或验收门禁变化：更新 `06`；
- Vue/TypeScript/Vite/Pinia/Element Plus/ECharts/Orval 等技术路线或锁定版本变化：按独立技术变更更新 `01/07` 和锁文件；
- 只改一个页面视觉且不改变长期规则时，不修改 Blueprint；
- 不在多个 Blueprint 复制同一套 Figma/页面目录细则，本文是该领域的详细长期事实源。

## 13. 最终固定原则

```text
Figma 决定已确认的视觉与交互目标
Pydantic/OpenAPI 决定 HTTP 数据语义
Vue 源码和测试决定当前可运行实现
MCP 负责传递设计上下文，不负责替代项目架构

公共的只共享一次
业务的归 Feature
页面私有的留在 Page
局部状态不要全局化
页面改版不牵连后端，除非业务语义真的变化

先做一个可验证纵切
再复制成熟模式到下一页
不要一次性生成整个前端
```
