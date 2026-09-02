# Figma 与前端设计开发工作流

这篇 Guide 说明 AIMA_UGC 后续怎样把 Figma 设计稳定地转成当前 Vue 代码，同时避免页面改版破坏后端 Contract、复制 Store/API，或因为 MCP 示例代码改变项目技术栈。

当前技术基线：

```text
Vue 3
TypeScript
Vite
Vue Router
Pinia
Element Plus
ECharts
OpenAPI / Orval generated client
```

长期前后端边界见：

- [`docs/blueprint/04_后端任务API与前端.md`](../blueprint/04_后端任务API与前端.md)
- [`docs/blueprint/07_技术决策与实施门禁.md`](../blueprint/07_技术决策与实施门禁.md)
- [`frontend/README.md`](../../frontend/README.md)

---

## 1. 先区分三种事实源

| 事实 | 当前事实源 | 不负责什么 |
| --- | --- | --- |
| 页面视觉、布局、交互意图 | 已确认 Figma Frame/Component/Variable；没有正式 Figma 时使用明确批准的一次性视觉参考 | API 字段、数据库表、后端业务规则 |
| HTTP 数据和错误语义 | Pydantic Request/Response → OpenAPI → Orval generated client | 页面布局/视觉 |
| 当前实际运行行为 | Vue 源码、Store/API、generated client、测试和 build | 自动替代尚未实现的产品设计 |

所以：

```text
Figma 有字段
≠ 后端已经有字段

后端有 API
≠ 前端已经有独立页面

MCP 生成了代码
≠ 代码可以直接提交
```

还要区分一个容易混淆的边界：

```text
Figma 目标信息架构（Target IA）
≠
当前已经实现的 Vue Route
```

Figma 可以先表达已经确认的长期产品方向，例如公共 Sidebar 中可以先出现未来页面入口；但 Design-to-Code 时只能为 [`frontend/src/app/routes.ts`](../../frontend/src/app/routes.ts) 当前真实存在的页面接通可点击导航。未来入口在代码中不得被实现成死链、伪路由、空白假页面或仅为了“和设计一致”而增加的无效菜单动作。真正新增页面时再按：

```text
Feature
→ Page
→ Route
→ App Shell
→ Test
```

同步接通。

---

## 2. 当前真实前端结构

真实 Router：

- [`frontend/src/app/routes.ts`](../../frontend/src/app/routes.ts)

当前路由：

```text
/
/collection-runtime
/collection-strategy
/voice-plaza
```

当前业务 Feature：

```text
frontend/src/features/import-batches/
frontend/src/features/collection-strategy/
frontend/src/features/voice-plaza/
```

当前通用分层：

```text
App / Router / Layout
→ Page / 页面私有组件
→ Pinia Store / local state
→ Feature api.ts
→ frontend/src/generated/api/
→ FastAPI
```

不要从早期 Stage 的目录示例猜现在存在 `features/content`、`features/system` 等目录；当前目录只以仓库实际内容为准。

---

## 3. 页面独立不等于复制工程

AIMA_UGC 使用一个 Vue SPA。

“页面独立”指：

```text
页面组合独立
页面私有组件独立
局部交互状态独立
修改页面时尽量只影响真实 Owner
```

不表示：

- 一页一个 npm 工程；
- 微前端；
- 每页复制一套 API；
- 每页复制一套 Store；
- 同时维护 Vue/React 两套前端。

只有真实团队/发布/性能边界证明有必要时，才重新评估微前端。

---

## 4. App / Shared / Feature / Page 怎样分

### App

```text
frontend/src/app/
```

负责：

- Router；
- App Shell；
- 全局 Layout；
- 应用级 Plugin 装配。

不保存某个 Feature 的业务规则。

### Shared

```text
frontend/src/shared/
```

只放真实跨 Feature 复用的内容：

- Design Token；
- 无单一业务 Owner 的组件；
- 无业务语义的工具/composable。

不要因为“以后可能复用”提前抽象。

### Feature

一个 Feature 典型拥有：

```text
api.ts
store.ts
format.ts（需要时）
pages/
Feature 级公共组件（真实复用后）
```

### Page

页面私有组件优先留在 Page 目录。

只有：

```text
同 Feature 多页面真实复用
→ 提升到 Feature component

跨 Feature 真实复用
→ 再考虑 shared
```

不要先做一套“看起来完整”的组件库再找使用场景。

Figma 组件也使用同样边界：

```text
AIMA/顶部栏
AIMA/侧边栏
AIMA/页面标题区
AIMA/按钮
AIMA/输入框
AIMA/下拉选择
AIMA/页签项
AIMA/反馈横幅
AIMA/空状态
AIMA/模态框外壳
→ 适合作为跨页面公共组件

采集策略 KPI
Keyword Pack Workspace
Global Relevance Config
Collection Plan Table / Form
→ 保持 Feature 级组件或 Pattern
```

设计系统和代码组件不要求机械 1:1；目标是同一种稳定模式只有一种实现方式，而不是把所有业务块都提升成全局万能组件。

---

## 5. Store 和 local state 怎样选

页面局部状态优先 local：

```text
Drawer 展开
Tab
表单草稿
一次 hover/open
```

Pinia Store 更适合：

```text
列表数据和筛选
Cursor
详情状态
多个组件共享的 Job/Run 状态
页面轮询
同 Feature 的共享业务交互状态
```

Store 不缓存一套服务端业务事实来替代 PostgreSQL，也不复制后端 Analysis/统计规则。

---

## 6. Generated Client 是硬边界

目录：

```text
frontend/src/generated/api/
```

唯一生成链：

```text
后端 Pydantic Contract
→ FastAPI OpenAPI
→ contracts/openapi/openapi.json
→ Orval
→ generated client
```

禁止：

- Figma MCP 修改 generated 文件；
- Page 手写长期 `/api/v1/...` URL；
- Feature 自己复制 Request/Response interface；
- 前端 Mock 字段长期脱离后端 Contract。

如果页面需要当前 API 没有的新数据：

```text
确认业务语义
→ 后端 Pydantic Contract
→ API/Contract Test
→ OpenAPI
→ generated Client
→ Feature api.ts / Store
→ Page
```

### 6.1 Figma 示例数据不是服务器事实

Figma 为了让 Normal/Data 状态可设计、可演示、可被 Codex读取，可以放代表性示例值，例如：

```text
词包数量
Plan 数量
Plan ID
Provider 显示名
Cron
下次运行时间
词包版本
相关性配置版本
有效关键词
分页页码
状态
```

这些示例只说明：

```text
这个字段在什么位置
怎样排版
长短文本怎样处理
Data / Empty / Loading / Error 怎样表现
```

它们不说明服务器当前一定存在这些记录，也不能成为前端常量。正式代码必须按当前调用链读取：

```text
Page
→ Store
→ Feature api.ts
→ generated client
→ FastAPI
```

Provider Config、平台可执行能力和 Search 参数尤其不能从 Figma 示例反推。当前 Collection 页面仍必须使用：

```text
GET /api/v1/collection-capabilities
→ generated client
→ CollectionSearchConfigFields
```

动态决定 Provider 和合法参数，不在 Vue 中维护第二套五平台 `if/else` 参数表。

---

## 7. 当前 Figma / 图片基线

当前部分正式页面是在完整 Figma 设计系统建立前落地。早期经批准的一次性视觉参考及其尺寸、哈希和采用原因仍由对应的归档 Change 保存；这些二进制图片已于 2026-08-27 经用户授权从当前仓库删除，不再作为可访问的现行资产。当前可运行的 Vue 页面是实际视觉实现，但仍不能冒充正式 Figma 设计系统。

以后建立正式 Figma Frame 后应明确：

```text
Figma 接管哪些视觉/交互事实
当前 Vue 哪些业务语义必须保持
旧 PNG 是否只保留历史参考意义
```

不要让：

```text
PNG
Figma
当前 Vue
```

长期成为三套没有优先级的设计事实。

### 7.1 采集策略正式 Figma 基线

“采集策略”已经形成正式 Figma 基线，并已由当前 Vue 页面落地；这套基线继续用于后续维护和 targeted re-review，覆盖：

```text
采集策略 / 关键词包
采集策略 / 全局相关性
采集策略 / 采集计划
关键词包 / 新建弹窗
采集计划 / 新建抽屉
采集计划 / 详情抽屉
采集策略开发状态规格
```

这套 Figma 接管：

- App Shell 在该页面中的视觉表现；
- 页面标题、KPI、Tab、筛选、表格、Modal、Drawer 的布局与视觉；
- Normal / Data / Loading / Empty / Error / Disabled 等状态表达；
- 公共组件的视觉 API 和设计 Token；
- 关键 Prototype 交互意图。

它不接管：

- Keyword Pack / Plan / Relevance 的 HTTP Schema；
- Provider Capability；
- Scheduler、Plan 启停、冻结 Relevance 等后端状态机；
- 当前服务器里到底有多少条 Plan、哪个 Provider Config 可用；
- 当前真实 Route 列表。

当前实现位于 `frontend/src/features/collection-strategy/`，真实 Route 仍是 `/collection-strategy`。页面通过 Pinia Store、Feature API 和 generated client 读取动态数据；关键词包分页、完整引用目录、Capability 表单、计划资格和历史配置摘要都由现有 Owner 维护，没有把 Figma 示例值写成生产事实。公共页面头、按钮、图标和反馈样式位于 `frontend/src/shared/ui/`，Feature KPI、表格、Modal、Drawer 和业务表单保持独立边界。

实现或维护该页面时必须继续执行：

```text
当前 AGENTS.md / Coding 规则
→ 当前 Contract / Service / Store / API / Route
→ 目标 Figma Design Context
→ 公共组件与 Feature 组件映射
→ Vue 实现 / 当前实现差异
→ 测试 / Build / Browser / 视觉验收
```

不能只看截图或只复制 Figma MCP 返回的 React/Tailwind 参考代码。每次涉及视觉或交互的变更，都要重新取得目标画板的 Fresh Screenshot，并用真实浏览器页面做 targeted 对照；浏览器 Mock 用于覆盖状态空间，真实 Full-stack Golden Path 只证明关键 Frontend/API/PostgreSQL 接线，两者不能互相冒充。

### 7.2 声音广场正式 Figma 基线

“声音广场”的正式设计文件为 `EAPm8KVarUe7BFTSnzvOpT`。Design-to-Code 和后续 targeted re-review 使用以下正式节点：

```text
Normal / Data              3924:556
AI Runtime 未配置          3924:782
Loading                    3925:697
Empty                      3925:4440
Error                      3925:4709
内容详情 Drawer / Loaded   3925:4978
内容详情 Drawer / Loading  3925:5068
内容详情 Drawer / Error    3925:5212
AI Analysis Preview        3926:978
Excel Export / Empty       3927:1051
Excel Export / Running     3929:1133
```

这套 Figma 接管 `/voice-plaza` 的页面布局、视觉层级、状态表达和 Overlay 几何关系；当前 HTTP Contract、Pinia Store、Cursor、Analysis Run、人工相关性复核、Detail supplement、Export Job/Artifact 和错误语义仍以当前代码、generated client 与后端事实为准。Figma 中的帖子、Run 状态、选择数量、模型名、互动数和分页示例只用于说明布局，不得写成生产常量。

当前代码 Owner 保持：

```text
App Shell
→ frontend/src/app/layouts/AppShell.vue

跨页面视觉 Owner
→ frontend/src/shared/ui/
→ frontend/src/shared/styles/

声音广场业务 Owner
→ frontend/src/features/voice-plaza/
→ 页面私有 Filter / Table / Drawer / Dialog 留在 Voice Plaza Page
```

正式桌面视觉复核使用 `1440×900` 作为参考 Viewport，但生产代码不得因此写死页面宽高。浏览器原生控件（例如 `input[type=date]`）的系统 Chrome 可以随浏览器/平台变化；验收关注其语义、尺寸、布局和可操作性，不用 Figma 静态占位符替代真实原生行为。

声音广场视觉或交互变更至少按以下证据分层验证：

```text
Fresh Figma Design Context / Screenshot
→ Browser Mock：Normal / Loading / Empty / Error / Runtime unavailable / Overlay
→ Lint / Typecheck / Unit / Build / Contract / generated drift gate
→ Real Full-stack Golden Path：只证明真实 Frontend/API/Worker/PostgreSQL 接线
```

Browser Mock 可以覆盖广泛的用户可见状态和请求语义，但不能冒充真实后端、PostgreSQL 或 Worker；Real Full-stack 也不需要机械复制全部视觉状态。

### 7.3 管理员配置正式 Figma 基线

管理员配置继续使用同一个正式设计文件 `EAPm8KVarUe7BFTSnzvOpT`，但作为独立页面，不放进声音广场 Canvas：

```text
车型 / 关键词资源        3964:2
Analysis Scheme          3967:86
配置状态板               3971:2
```

代码 Owner 是 [`frontend/src/features/admin-configuration/`](../../frontend/src/features/admin-configuration/)；Provider-neutral Principal 和管理员路由守卫分别由 [`frontend/src/features/identity/`](../../frontend/src/features/identity/) 与 [`frontend/src/app/router.ts`](../../frontend/src/app/router.ts) 负责。车型多选跨 Collection、Import、声音广场和管理员页复用 [`frontend/src/shared/VehicleMultiSelect.vue`](../../frontend/src/shared/VehicleMultiSelect.vue)。

这组 Figma 只定义信息架构、布局、状态和组件复用。角色固定为管理员/普通用户，发布/回滚审计、车型删除限制、Scheme 版本冲突、动态目录和错误语义以当前 Contract/代码为准；示例车型、Prompt、Hash 和审计记录不构成生产事实。当前三个节点共复用 37 个共享组件实例，正文统一使用 Noto Sans SC，并分别保留实现注释；程序化 QA 未发现可见越界、非规范字体或本地重复组件。精确 QA 账本见 [`changes/archive/2026-09/CHG-20260902-u3-admin-identity-config/figma-state.json`](../../changes/archive/2026-09/CHG-20260902-u3-admin-identity-config/figma-state.json)。

---

## 8. Figma 文件建议怎样组织

AIMA 当前设计系统页面使用中文职责名：

```text
00 AIMA 设计系统使用说明
01 设计规范
02 公共组件
03 页面模板
```

设计资产内部长期按职责组织：

```text
设计规范
├─ 颜色
├─ 字体
├─ 间距
└─ 圆角

公共组件
→ 稳定跨页面组件

页面模板 / Pattern
→ 列表 / 详情 / 筛选 / 任务进度 / 空状态 / 错误状态

业务页面
→ 正式 Screen

关键流程
→ Prototype / Flow
```

规则：

- 重复组件使用 Component/Variant；
- 组件可变文字优先使用 Component Property，不在实例上叠加额外 Text 模拟值；
- 重复视觉值使用 Variable/Style；
- 布局优先 Auto Layout；
- Layer/Frame 名称表达业务含义；
- 交付开发时必须给明确目标 Frame/Node；
- 页面至少考虑 Normal / Loading / Empty / Error；
- Disabled / Partial / Permission 按实际业务需要设计；
- Figma 不复制完整 API Schema；
- Prototype Variable 只服务演示，不成为 Vue 状态模型或后端 Contract。

---

## 9. Design Token

Figma 中稳定重复的：

```text
Color
Typography
Spacing
Radius
```

应使用有语义的 Variable/Style。

代码侧统一放真正公共 Token，例如：

```text
frontend/src/shared/styles/
```

代码侧优先：

- CSS Custom Properties；
- 当前 UI Library 可配置变量。

当前没有必要为 Token 引入：

- Tailwind；
- CSS-in-JS；
- 第二套主题 Runtime。

一次性页面尺寸不需要机械 Token 化。

Figma 已经存在对应 AIMA Design Token 时，页面和公共组件应优先绑定现有变量，不继续散落语义相同的 Raw Hex。不能确定语义是否相同的颜色不要为了“Token 覆盖率”强行合并。

---

## 10. Element Plus 当前兼容边界

当前依赖事实以 [`frontend/package.json`](../../frontend/package.json) / lock 为准，目前包括：

```text
element-plus = 2.14.4
@typescript/native = TypeScript 7.0.2
```

当前：

```text
skipLibCheck = false
```

Stage 8C 实现时已发现：当前锁定组合下直接使用部分 Element Plus 类型声明会暴露 TypeScript 7 兼容问题。

当时的处理原则今天仍有效：

```text
不能为了页面开发：
→ 静默升级依赖
→ skipLibCheck=true
→ 降低 typecheck
```

这不表示永久禁止 Element Plus。

如果未来 Figma 改版确实需要系统性使用 Element Plus：

```text
独立技术 Change
→ 核对当时 Element Plus / TypeScript 兼容性
→ 必要时升级 package + lock
→ typecheck / unit / build / E2E
→ 再扩展业务页面
```

不要在普通页面 PR 顺手改变全局类型基线。

---

## 11. Figma MCP → Vue 的固定流程

```text
AGENTS.md / Coding Skill
→ 当前 Route / Feature / Store / API / Contract / Capability
→ 目标 Figma Frame 的 Design Context
→ 当前 Shared / App Shell / Design Token
→ 区分全局公共组件、Feature 组件、页面私有组合
→ 把设计意图适配成 Vue 3 + TypeScript
→ 接入既有 Feature api.ts / Store / generated client
→ Lint / Typecheck / Unit / Build / E2E
→ 浏览器与 Figma 做视觉核对
```

顺序不能反过来。尤其不能先让 MCP 生成一套组件/数据模型，再要求仓库迁就生成结果。

MCP 输出如果出现：

```text
React
Tailwind
其他 UI Library
手写 fetch
```

只能作为设计结构参考，未经独立技术决策不得直接引入 AIMA。

对于 Figma 公共 Sidebar：

```text
设计中存在未来入口
→ 保留目标 IA 视觉

当前 routes.ts 没有该 Route
→ 不接 clickable route
→ 不创建 placeholder Page
→ 不制造 disabled 假功能

未来页面真实完成
→ 再同步 Route + App Shell
```

---

## 12. Figma MCP 使用硬规则

1. 先读仓库当前事实，再读设计上下文；
2. Design-to-Code 优先调用目标 Frame 的 Design Context，不用截图替代结构上下文；
3. 优先复用当前 Feature/Shared 真实实现；
4. generated API 目录禁止手改；
5. Figma 文字、Prototype Variable 和演示数据不自动成为 HTTP Contract；
6. Figma 中的 Provider、Capability、时间、状态、数量等示例值不得硬编码为生产事实；
7. Figma 完整 Sidebar 可以表达目标 IA，但当前代码只接通真实 Route；
8. Component Property 应表达可变文本/状态，业务页不要用额外覆盖文字伪装公共组件内容；
9. 资产使用真实导出或当前仓库已有资产；Unicode 图标不能因为出现在设计示例中就成为生产 Icon 实现；
10. MCP 生成结果必须 Review；
11. 视觉接近不能替代 Type/Test/Build/E2E；
12. 不因为 MCP 示例技术栈改变仓库长期技术选型。

---

## 13. Code Connect

当 AIMA 已经形成稳定的：

```text
Figma Component
↔ Vue Shared/Feature Component
```

映射，并且当前 Figma 工具链支持可靠 Code Connect 时，可以为高复用组件建立 Code Connect/等价映射。

它是增强项，不是开发页面的前置条件。

没有稳定公共组件前，不批量创建占位映射；当前 Figma 席位/计划如果不支持 Code Connect，也不能为了获得映射能力阻塞正常的 Design Context → Vue 工作流。

---

## 14. 不承诺自动双向同步

项目不承诺：

```text
改 Figma
→ 自动无损改 Vue

改 Vue
→ 自动无损回写 Figma
```

如果紧急修复先改代码：

```text
代码修正
→ 测试/浏览器验证
→ 把确认的视觉/交互变化同步回 Figma
→ 下一次设计继续以更新后的 Frame 为目标
```

自动工具可以辅助，但不能代替业务/设计确认。

---

## 15. 三类常见改动

### 15.1 只改视觉

```text
Figma Frame
→ 判断 Page / Feature Component / Shared / App Shell
→ 修改最小 Owner
→ 前端验证
→ 视觉核对
```

不改数据库、Pydantic Contract 或 Service。

### 15.2 页面需要新字段/新行为

```text
页面需求
→ 当前 Capability / Contract 调查
→ 明确业务语义
→ Pydantic Contract
→ API/Contract Test
→ OpenAPI
→ generated Client
→ Feature API / Store
→ Page
→ E2E
```

### 15.3 多页面一起变化

先找真实公共 Owner：

```text
App Layout？
Shared Component？
Design Token？
Feature 级组件？
```

只改 Owner，不到每个 Page 复制修复。

---

## 16. 前后端怎样并行

切分点不是“后端所有 API 都做完”，而是：

> 页面需要的 HTTP Contract 已经稳定，并能生成 TypeScript Client。

之后：

```text
前端
→ generated type + Fake/Mock
→ Page/Store

后端
→ Router/Service/Repository

合流
→ Real API / E2E
```

这样可以并行，又不会两边分别手写接口语义。

---

## 17. 当前测试和视觉验收

提交正式页面前至少：

```bash
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test -- --run
npm --prefix frontend run build
npm --prefix frontend run test:e2e
```

具体脚本以 [`frontend/package.json`](../../frontend/package.json) 为准。

页面状态按实际需要检查：

- Normal；
- Loading；
- Empty；
- Error；
- Disabled / Partial / Permission（需求存在时）。

视觉核对：

- 布局；
- 字号层级；
- 间距；
- 颜色/状态；
- 文本溢出；
- 表格超宽；
- 图片比例；
- 错误反馈；
- 关键交互。

自动像素 Snapshot 不作为所有高频页面强制门禁；稳定 App Shell/Shared Component 或明确需要严格回归时再建立 Visual Regression。

响应式断点只按批准需求实现，不由 Agent 自己猜移动端产品要求。Figma 1440×900 等桌面 Frame 是设计参考 Viewport，不等于生产代码必须写死 `width: 1440px; height: 900px`；生产布局仍按当前 App Shell 与真实响应式需求实现。

---

## 18. 新页面的推荐 Vertical Slice

Stage 8 已经完成主要业务纵切，但其开发方法继续作为长期规则：

```text
业务目标
→ 当前 Capability 调查
→ 信息结构 / Figma
→ HTTP Contract（需要变化时）
→ API/Contract Test
→ OpenAPI / generated Client
→ 后端实现与前端并行
→ Feature API / Store
→ Vue Page
→ Unit / E2E
→ 视觉验收
```

不采用：

```text
Figma 一次生成全部未来页面
→ 再追着补后端
```

也不采用：

```text
后端提前实现全部未来 API
→ 页面以后再决定怎么用
```

每次完成一个可以独立验收的纵切。

---

## 19. 当前前端仍未实现的能力

当前没有正式：

- 企业登录/认证页面闭环；
- 独立 Analysis 管理中心；
- 独立 Job 管理中心；
- 独立 Word Report 中心；
- Monitoring/Alert/VOC/Ticket/Dashboard 页面。

是否以及何时实现看：

[`docs/roadmap/02_生产上线实施路线.md`](../roadmap/02_生产上线实施路线.md)

不要从历史 Stage 8 的 Screens 示例自动生成一批新页面。

同样，不要因为 Figma 公共 Sidebar 已经展示某个未来入口，就把它写成“当前已实现”。Figma 可以先保存长期产品 IA；代码事实仍以当前 Route / Feature / Test 为准。

---

## 20. 最终原则

```text
Figma
→ 已确认视觉、交互目标和目标信息架构

Pydantic/OpenAPI
→ HTTP 数据语义

Vue + tests
→ 当前可运行行为

MCP
→ 传递设计上下文并辅助实现

公共的只共享一次
业务的归 Feature
页面私有的留 Page
动态服务器事实不写死在设计实现里
未来 IA 不冒充当前 Route
局部状态不要全局化
先做一个可验证纵切
再复用成熟模式
```
