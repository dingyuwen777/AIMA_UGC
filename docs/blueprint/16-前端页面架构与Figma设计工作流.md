# 前端页面架构与 Figma 设计工作流：当前实现导航

本文保留原 `16-前端页面架构与Figma设计工作流.md` 路径，但以**当前 Vue 代码和当前设计工作流**为准说明长期边界。

Stage 8 当时的完整前端/Figma 设计方案、目录目标和实施顺序没有删除，原样保存在：

[`16-前端Figma设计与Stage8实施记录.md`](16-前端Figma设计与Stage8实施记录.md)

当前实操入口：

- [`../../frontend/README.md`](../../frontend/README.md)：真实路由、Feature、Page/Store/API、测试和修改入口；
- [`../guides/Figma与前端设计开发工作流.md`](../guides/Figma与前端设计开发工作流.md)：Figma → 当前 Vue 项目的实际工作流；
- [`04-后端任务API与前端.md`](04-后端任务API与前端.md)：HTTP/Job/前端边界。

---

## 1. 当前前端不是 Stage 1 骨架

当前真实 Router：

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

当前 Feature：

```text
frontend/src/features/import-batches/
frontend/src/features/collection-strategy/
frontend/src/features/voice-plaza/
```

根 `/` 通过：

```text
frontend/src/views/HomeView.vue
```

复用 `CollectionRuntimePage`；`views/` 现在主要承担这个兼容入口，不再是“真实业务页面尚未开始”的 Stage 1 状态。

旧 Stage 8 文档中的目标目录示例：

```text
features/collection/
features/content/
features/system/
```

是当时用于解释 Feature 分层的**示例结构**，不是当前机器目录。当前代码事实只看 `frontend/src/features/`。

---

## 2. 当前长期前端分层仍然有效

```text
App / Route
→ Page / Component
→ Pinia Store / local state
→ Feature api.ts
→ generated OpenAPI Client
→ HTTP API
```

职责：

### App

```text
frontend/src/app/
```

负责：

- Router；
- App Shell/Layout；
- 全局级装配。

不保存单个业务 Feature 规则。

### Feature

当前业务 Feature 自己拥有：

```text
pages/
api.ts
store.ts
format.ts（需要时）
页面私有组件
```

### Shared

```text
frontend/src/shared/
```

只放已经有真实跨 Feature 复用价值的 Token/组件/工具，不为“未来可能复用”提前抽象。

### Generated Client

```text
frontend/src/generated/api/
```

只由：

```text
Pydantic
→ FastAPI OpenAPI
→ contracts/openapi/openapi.json
→ Orval
```

生成，禁止手工改。

---

## 3. 页面状态放 Store 还是本地

Pinia 不表示所有状态都要全局化。

页面私有状态，例如：

```text
Drawer 是否展开
当前 Tab
尚未提交的输入草稿
一个组件的临时 hover/open 状态
```

优先留在 Page/Component。

Store 更适合：

```text
列表数据和 filter
Cursor
多个组件共享的详情
Job/Run 轮询状态
同一 Feature 跨组件/页面需要的业务交互状态
```

Store 不应该缓存一套服务端业务真相去替代 PostgreSQL，也不应该复制后端 AI/统计规则。

---

## 4. Figma、HTTP Contract、Vue 各自决定什么

必须分开三类事实：

| 事实 | 当前负责者 |
| --- | --- |
| 布局、视觉层级、交互意图、设计状态 | 已确认 Figma Frame/Component/Variable；没有正式 Figma 时仅使用明确批准的一次性视觉参考 |
| HTTP 字段、错误、Cursor、业务请求语义 | Pydantic → OpenAPI → generated Client |
| 当前页面实际运行行为 | Vue 源码 + Store/API + 测试/构建 |

Figma 不能决定：

- 数据库字段；
- 新 API 字段；
- Job 状态机；
- Provider Capability；
- AI taxonomy；
- 权限语义。

如果设计稿需要一个当前 Contract 不存在的数据：

```text
先确认业务需求
→ 修改后端 Contract/实现（如果确实需要）
→ 生成 OpenAPI/Client
→ 再接页面
```

不要长期用前端 Mock 字段冒充后端能力。

---

## 5. 当前 Figma / 一次性视觉基线

Stage 8 期间部分页面是在正式 Figma 文件尚未建立时开发的，因此仓库仍保留经批准的一次性视觉参考：

```text
docs/assets/stage8c/collection-runtime-center-prototype.png

docs/assets/stage8d/voice-plaza-list-reference.jpg
docs/assets/stage8d/voice-plaza-detail-reference.jpg

docs/assets/stage8e/tikhub-supplement-centralized-runs-prototype.png
```

这些资产解释当前页面视觉从哪里来，但不是永久取代 Figma 的设计系统。

未来正式 Figma Frame 建立后，要通过明确 Change 说明：

```text
Figma 接管哪些视觉/交互事实
当前 Vue 哪些业务语义保持
旧 PNG 退化成什么历史参考
```

不能让 Figma、PNG、当前页面三套事实长期互相冲突。

---

## 6. Figma MCP → 当前 Vue 的正确链路

```text
明确目标 Frame/Node
→ 读取设计结构/截图/变量/组件上下文
→ 读取当前 AIMA Vue Feature / shared / token / API
→ 判断应修改 Page / Feature Component / Shared / App 哪个 Owner
→ 把设计意图翻译成 Vue 3 + TypeScript
→ 复用当前 Feature api.ts / Store / generated Client
→ lint / typecheck / unit / build / E2E
→ 用浏览器页面与目标 Figma 做视觉核对
```

MCP 输出如果出现：

```text
React
Tailwind
另一套 UI Library
手写 fetch
```

只能作为视觉/结构参考，不能自动变成 AIMA 技术栈变化。

---

## 7. 页面改动如何判断影响范围

### 只改视觉

```text
Figma / 参考图
→ 目标 Page/Component
→ 必要时 shared token
→ 前端测试/视觉核对
```

不改 Contract/数据库。

### 页面需要新数据

```text
需求
→ 当前 HTTP Contract 是否已有
→ 没有则后端 Pydantic/Service/API Test
→ OpenAPI
→ generated Client
→ Feature api.ts / Store
→ Page
→ E2E
```

### 多页一起改颜色/布局模式

先判断真实 Owner：

```text
App Shell？
Shared Component？
Design Token？
同一个 Feature 的公共组件？
```

不要到每个 Page 复制一遍相同修改。

---

## 8. Element Plus 当前真实边界

当前依赖仍包含：

```text
element-plus = 2.14.4
@typescript/native-preview = 7.0.2
skipLibCheck = false
```

Stage 8C 已验证这组版本下直接使用部分 Element Plus 类型声明会暴露 TypeScript 7 兼容问题，因此现有业务页面在不降低类型门禁、不静默升级依赖的前提下使用了 Vue SFC 原生语义控件完成部分界面。

长期方向仍可以使用 Element Plus，但正确做法是：

```text
需要大量采用 Element Plus
→ 独立技术 Change
→ 核对当时依赖兼容
→ 必要时升级 package + lock
→ typecheck/unit/build/E2E
→ 再扩展页面使用
```

禁止为了页面改版直接：

```text
skipLibCheck=true
或
普通页面 PR 顺手升级整个前端依赖
```

当前完整说明见 `frontend/README.md`。

---

## 9. 当前测试已经存在，不再是“未来 Stage 8 才建立”

当前前端至少已经有：

```text
frontend/tests/
frontend/e2e/
```

常用验证：

```bash
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test -- --run
npm --prefix frontend run build
npm --prefix frontend run test:e2e
```

具体脚本和当前测试文件以 `frontend/package.json` / `frontend/tests/` / `frontend/e2e/` 为准。

页面改完“看起来差不多”不能替代这些工程验证。

---

## 10. 当前新增页面的开发顺序

Stage 8 已经完成主要纵切，但它留下的开发方法继续有效：

```text
业务目标
→ 当前 Capability/Contract 调查
→ 页面信息结构 / Figma
→ 需要变化时先冻结 HTTP Contract
→ API/Contract Test
→ OpenAPI / generated Client
→ Feature api.ts / Store
→ Vue Page
→ Unit/E2E
→ 浏览器视觉验收
```

不是：

```text
一次性画完/生成全部页面
→ 再补后端
```

也不是：

```text
后端把所有未来 API 做完
→ 前端以后再用
```

最小完整 Vertical Slice 仍是当前推荐开发方式。

---

## 11. Code Connect / 双向同步的边界

当真正形成稳定的公共 Figma Component 与 Vue Component 映射后，可以使用 Code Connect/等价机制提高 Design-to-Code 复用率。

但它是增强能力，不是页面开发前置条件。

同样，项目不承诺：

```text
改 Figma 自动无损更新 Vue
或
改 Vue 自动无损更新 Figma
```

如果紧急业务先改了代码：

```text
代码修正并验证
→ 把已确认的视觉/交互变化同步回 Figma
→ 下一次设计继续以同步后的设计稿为目标
```

自动工具可以辅助，最终设计状态仍要明确确认。

---

## 12. 当前修改导航

| 需求 | 先改/先看 |
| --- | --- |
| 路由 | `frontend/src/app/routes.ts` + routes tests |
| 全站 Layout | `frontend/src/app/layouts/` |
| 采集运行中心 | `features/import-batches/` |
| 采集策略 | `features/collection-strategy/` |
| 声音广场 | `features/voice-plaza/` |
| 页面业务状态 | 对应 `store.ts` |
| 后端调用 | 对应 Feature `api.ts` → generated Client |
| HTTP 字段 | 后端 Pydantic Contract → OpenAPI → generated Client |
| 全局 Token | `frontend/src/shared/styles/` |
| Figma 工作流 | `docs/guides/Figma与前端设计开发工作流.md` |
| 前端依赖/兼容 | `frontend/package.json`、lock、tsconfig、独立技术 Change |

---

## 13. 当前明确未实现的前端能力

当前没有：

- 企业登录/认证页面闭环；
- 独立 Analysis 管理中心；
- 独立 Job 管理中心；
- 独立 Word Report 中心；
- Monitoring/Alert/VOC/Ticket/Dashboard 正式页面。

这些是否以及何时实现，按：

[`../roadmap/生产上线实施路线.md`](../roadmap/生产上线实施路线.md)

推进，不从旧 Stage 8 “Screens 示例”自动生成一批新页面。

---

## 14. Stage 8 原详细设计怎样读

完整原文：

[`16-前端Figma设计与Stage8实施记录.md`](16-前端Figma设计与Stage8实施记录.md)

其中仍有效的长期原则包括：

- 单一 Vue SPA；
- App/Shared/Feature/Page 分层；
- OpenAPI generated Client；
- Figma 不替代 Contract；
- 页面私有组件先留 Page；
- 真实复用后再提升 Shared；
- MCP 输出必须适配当前项目而不是改变技术栈。

但以下内容属于当时阶段快照：

```text
“Stage 1 views 只是骨架”
“Stage 8 后再建立 Playwright”
“Stage 8 实现时建立 frontend/README”
```

今天是否实现，以当前 Vue 代码、`frontend/README.md`、测试和本页为准。
