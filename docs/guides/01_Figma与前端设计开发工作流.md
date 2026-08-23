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

- [`../blueprint/04_后端任务API与前端.md`](../blueprint/04_后端任务API与前端.md)
- [`../blueprint/07_技术决策与实施门禁.md`](../blueprint/07_技术决策与实施门禁.md)
- [`../../frontend/README.md`](../../frontend/README.md)

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

---

## 2. 当前真实前端结构

真实 Router：

```text
frontend/src/app/routes.ts
```

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

---

## 7. 当前 Figma / 图片基线

当前部分正式页面是在完整 Figma 设计系统建立前落地，因此仓库仍保留经批准的一次性视觉参考：

```text
docs/assets/stage8c/collection-runtime-center-prototype.png

docs/assets/stage8d/voice-plaza-list-reference.jpg
docs/assets/stage8d/voice-plaza-detail-reference.jpg

docs/assets/stage8e/tikhub-supplement-centralized-runs-prototype.png
```

这些文件说明当前页面视觉演进来源，但不是长期设计系统。

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

---

## 8. Figma 文件建议怎样组织

长期 Figma 资产建议按职责组织：

```text
Foundations
├─ Color
├─ Typography
├─ Spacing
└─ Radius

Components
→ 稳定公共组件

Patterns
→ List / Detail / Filter / Job Progress / Empty / Error

Screens
→ 正式页面

Flows
→ 关键交互流程
```

规则：

- 重复组件使用 Component/Variant；
- 重复视觉值使用 Variable/Style；
- 布局优先 Auto Layout；
- Layer/Frame 名称表达业务含义；
- 交付开发时必须给明确目标 Frame/Node；
- 页面至少考虑 Normal / Loading / Empty / Error；
- Disabled / Partial / Permission 按实际业务需要设计；
- Figma 不复制完整 API Schema。

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

---

## 10. Element Plus 当前兼容边界

当前依赖事实以 `frontend/package.json` / lock 为准，目前包括：

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
目标 Figma Frame/Node
→ 读取 Frame / Component / Variable / Screenshot / Asset 上下文
→ 读取当前 Vue Feature / Shared / Design Token / generated Client
→ 确认真实 Owner
→ 把设计意图适配成 Vue 3 + TypeScript
→ 接入 Feature api.ts / Store
→ Lint / Typecheck / Unit / Build / E2E
→ 浏览器与 Figma 做视觉核对
```

MCP 输出如果出现：

```text
React
Tailwind
其他 UI Library
手写 fetch
```

只能作为设计结构参考，未经独立技术决策不得直接引入 AIMA。

---

## 12. Figma MCP 使用硬规则

1. 先读仓库当前事实，再读设计上下文；
2. 优先复用当前 Feature/Shared 真实实现；
3. generated API 目录禁止手改；
4. Figma 文字/演示数据不自动成为 HTTP Contract；
5. 资产使用真实导出或当前仓库已有资产；
6. MCP 生成结果必须 Review；
7. 视觉接近不能替代 Type/Test/Build/E2E；
8. 不因为 MCP 示例技术栈改变仓库长期技术选型。

---

## 13. Code Connect

当 AIMA 已经形成稳定的：

```text
Figma Component
↔ Vue Shared/Feature Component
```

映射，并且当前 Figma 工具链支持可靠 Code Connect 时，可以为高复用组件建立 Code Connect/等价映射。

它是增强项，不是开发页面的前置条件。

没有稳定公共组件前，不批量创建占位映射。

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

具体脚本以 `frontend/package.json` 为准。

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

响应式断点只按批准需求实现，不由 Agent 自己猜移动端产品要求。

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

[`../roadmap/02_生产上线实施路线.md`](../roadmap/02_生产上线实施路线.md)

不要从历史 Stage 8 的 Screens 示例自动生成一批新页面。

---

## 20. 最终原则

```text
Figma
→ 已确认视觉和交互目标

Pydantic/OpenAPI
→ HTTP 数据语义

Vue + tests
→ 当前可运行行为

MCP
→ 传递设计上下文并辅助实现

公共的只共享一次
业务的归 Feature
页面私有的留 Page
局部状态不要全局化
先做一个可验证纵切
再复用成熟模式
```
