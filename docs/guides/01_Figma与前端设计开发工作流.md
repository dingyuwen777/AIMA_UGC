# AIMA Figma 与前端开发接线

本文只说明 **AIMA 的设计事实怎样映射到当前 Vue 工程**。

通用 Figma 创建、审查、Owner 治理、Design-to-Code、Evidence 和交付方法由 Agent_Skills 通过 [AGENTS.md](../../AGENTS.md) 的项目治理入口提供；本文不维护第二套通用 Figma/MCP 规则。

## 1. 三类事实不要混在一起

| 事实 | AIMA Owner | 说明 |
| --- | --- | --- |
| 页面视觉、布局、交互意图 | 已确认 Figma 文件/Frame/Component/Variable | 设计事实，不定义后端业务 |
| HTTP / Schema / 权限 / 状态机 | 后端 Contract、OpenAPI、代码、测试 | Figma 不能虚构 |
| 当前前端工程结构 | [frontend/README.md](../../frontend/README.md) + Vue 源码 | 设计落地必须复用 |

发生冲突时先判断是哪一类事实落后；不要为了让截图和代码“看起来一致”而修改正确的业务 Contract。

## 2. 当前前端技术边界

当前项目是 Vue + TypeScript + Vite，页面状态使用 Pinia / local state，组件基于 Element Plus，HTTP 类型来自 OpenAPI/Orval 生成链。

精确技术栈和页面入口看 [frontend/README.md](../../frontend/README.md)。

公共 HTTP 类型链：

~~~text
Pydantic / FastAPI
→ contracts/openapi/openapi.json
→ Orval
→ frontend/src/generated/api/
→ Feature api.ts
→ Store / Page
~~~

机器入口：

- [contracts/openapi/openapi.json](../../contracts/openapi/openapi.json)
- [frontend/src/generated/api/](../../frontend/src/generated/api/)

Generated Client 不手改。设计需要新字段时，先确认后端真实能力；如果 Contract 不存在，必须回到正式需求/研发流程，而不是在前端伪造长期字段。

## 3. AIMA 页面 Owner 的落地顺序

设计落地时按当前项目结构定位：

~~~text
App / Layout
→ Shared Component / Token
→ Feature
→ Page
→ Page-private Component
~~~

先复用已有 Owner，再新增。

当前页面和 Feature 入口以 [frontend/src/app/routes.ts](../../frontend/src/app/routes.ts) 和 [frontend/README.md](../../frontend/README.md) 为准。历史目录名不为“看起来更统一”在无关任务中重命名。

## 4. Figma 在 AIMA 负责什么

Figma 应表达：

- 页面信息层级；
- 布局、间距、字号和视觉重点；
- 组件状态与交互；
- Responsive 意图；
- Empty / Loading / Error / Disabled 等用户状态；
- 页面之间可以在演示模式完成的验收交互。

Figma 不负责：

- 定义不存在的 API；
- 发明数据库字段；
- 改写后端权限；
- 把示例数据当生产事实；
- 复制完整 Schema；
- 决定 Release / Migration 行为。

## 5. AIMA 的页面专项事实

页面专项基线不再全部堆进本 Guide：

- 管理员配置 → [docs/guides/02_管理员配置Figma开发基线.md](02_管理员配置Figma开发基线.md)
- 采集运行中心 → [docs/guides/07_采集运行中心Figma开发基线.md](07_采集运行中心Figma开发基线.md)
- 其他页面的当前真实代码入口 → [frontend/README.md](../../frontend/README.md) 与对应 Feature

专项 Guide 只维护 AIMA 的 Figma Node/Owner/页面 Contract，不复制本页的共性边界。

## 6. 设计到代码的 AIMA 接线

通用执行方法由 Agent_Skills 负责；AIMA 项目中需要确保以下项目事实被接上：

1. 从正式 Figma Owner 定位页面/组件，而不是从截图猜；
2. 对照当前 Route 和 Feature Owner；
3. 优先复用现有 App / Shared / Feature 公共组件；
4. 数据只通过当前 Feature API / Generated Client；
5. 需要后端新能力时回到 Contract Owner；
6. 页面交互与当前产品能力保持一致；
7. 视觉、组件和真实用户行为使用 AIMA 当前测试入口验证；
8. 如果 Figma 和正确实现都发生变化，同一任务同步两边承担的事实。

这里不重复 Agent_Skills 的 Review、修复循环、Owner 四层方法或 MCP 调用细则。

## 7. Store、local state 与 API 的项目边界

具体结构由 [frontend/README.md](../../frontend/README.md) 维护。稳定原则只有三条：

- 多组件/跨页面共享且需要生命周期管理的业务状态才进入 Store；
- 页面瞬时 UI 状态优先留在页面/组件；
- Feature API 是页面语义与 Generated Client 的薄边界，不重新定义公共 Contract。

如果一个设计改动要求 Store 开始理解 SQL、Provider 私有字段或 Secret，说明 Owner 已经错位。

## 8. Shared 与 Feature 的边界

适合 Shared：

- 与业务领域弱耦合、多个页面复用的视觉/交互组件；
- 通用日期选择、Shell、基础反馈等已经形成稳定共性能力。

适合 Feature：

- 只服务一个业务域的表格、Drawer、筛选、状态解释和业务交互。

不要因为两个页面“长得像”就提前抽象；也不要在多个页面复制已经稳定存在的 Shared Owner。

## 9. 设计 Token 与组件库

AIMA 当前设计样式必须以真实前端代码和正式 Figma Variables/Components 交叉确认。Element Plus 是实现基础，不代表页面直接接受默认视觉，也不意味着为了设计一致性可以替换当前技术栈。

新增或修改全局视觉规则时，先确认它是否真的属于全局 Owner；只服务一个 Feature 的样式留在 Feature。

## 10. 验证入口

通用测试策略由 Agent_Skills Testing/Coding 负责；AIMA 的现有入口见：

- [docs/04_测试与调试说明.md](../04_测试与调试说明.md)
- [frontend/package.json](../../frontend/package.json)
- [frontend/README.md](../../frontend/README.md)

Figma 改动本身不证明生产页面正确；代码测试通过也不证明视觉与交互意图已经对齐。需要哪种证据由当前任务风险和实际变更边界决定。

## 11. 本文不再保存的内容

为了避免和 Agent_Skills 形成第二套治理，本 Guide 不再维护：

- 通用 Figma MCP 使用规则；
- 通用 Design-to-Code 步骤模板；
- 通用 Owner 分层方法论；
- 通用 Review/修复收敛规则；
- 通用截图比较方法；
- 其它项目也成立的前端最佳实践大全。

这些内容变化时只更新 Agent_Skills；AIMA 只维护自己的事实和接线。
