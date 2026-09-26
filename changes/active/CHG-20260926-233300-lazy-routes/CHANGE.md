---
schema: coding-change/v1
id: CHG-20260926-233300-lazy-routes
title: 按需加载重页面路由
level: L2
status: ready_for_review
owner: codex
branch: fix/618-lazy-routes
created: 2026-09-26
updated: 2026-09-26
completion_gate: required
depends_on: []
affected_areas:
  - frontend
affected_paths:
  - frontend/src/app/routes.ts
  - frontend/README.md
contracts: []
data_changes: []
---

# 变更摘要

Issue #618 / AC4、AC5 的工作包。将声音广场、采集运行中心、采集策略和管理员配置路由改为 Vue Router 异步组件，降低登录/首页首包脚本体积。

# 背景、现状与问题

当前 `routes.ts` 顶层同步导入全部页面，Vite 生产构建把这些页面依赖放进初始 `index` JS。浏览器打开登录或工作台时也需下载解析未访问的重页面代码。这是静态依赖图造成的首包放大。

# 事实与证据

| 编号 | 已确认事实 | 来源 | 支撑决策 |
| --- | --- | --- | --- |
| E1 | `routes.ts` 顶层同步导入全部七个页面 | 当前路由源码 | 重页面可在路由边界拆包 |
| E2 | 基线 Vite 构建仅一个 `index` JS，480.12 kB、gzip 141.53 kB | 当前 main、`npm run build` 输出 | 衡量首包改善 |
| E3 | 登录、无权限和首页是独立轻页面；其余四个是业务重页面 | 当前组件与路由 | 保留轻页面初始可用 |

推断与待确认：生产网络下载和浏览器解析收益待实机验证；构建产物可直接验证依赖拆分。

# 目标、成功标准与非目标

目标：登录、无权限与工作台仍直接可用，四个业务页面在进入对应路由时加载，URL、守卫和功能不变。

- [x] 构建产生独立业务页 chunk，初始 JS 小于 480.12 kB 基线。
- [x] 路由、身份守卫、现有页面测试和真实浏览器关键路径通过。

范围：路由导入与前端开发说明。非目标：页面内部拆分、CSS 结构、依赖升级、路由 URL 或权限调整。必须保持现有组件和守卫的加载结果。

# 约束与意图决策

只在 Vue Router 的 `component` 边界使用动态 import；路由名称、路径、meta 和轻页面同步导入保持。无公共 API、Schema、数据或部署流程变化；前端构建输出 chunk 名会自然变化。

# 修改方案与决策依据

把四个业务页静态 import 移入对应 route 的 `component: () => import(...)`。使用现有测试与 `npm run build` 验证页面可达和首包；不引入预加载抽象或新的模块边界。

## 备选方案与取舍

手工拆分 Vite vendor chunk 或改页面内部组件会扩大范围，且无法直接切断所有重页面的首包依赖；优先路由边界。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 重页面按需加载，轻页面和路由功能保持 | #618 / AC4 | satisfied | Vite 产出四个业务页 JS/CSS chunk；138 个浏览器旅程覆盖各页面与守卫 |
| R2 | 构建和回归给出对照 | #618 / AC5 | satisfied | 初始 JS 480.12→160.34 kB，gzip 141.53→54.54 kB；235 个组件测试、138 个浏览器测试通过 |

# 计划改动

| 文件 | 修改 | 原因 | 对应 |
| --- | --- | --- | --- |
| `frontend/src/app/routes.ts` | 四个重页面动态 import | 切断首包依赖 | R1 / E1 |
| `frontend/README.md` | 当前路由加载方式 | 与实现同步 | R1 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 路由与页面现有测试 |
| 接口 / 契约 | not_applicable | 路由 URL、API 与消费者结构不变 |
| 集成 / 持久化 / 运行依赖 | not_applicable | 无数据库或系统依赖变化 |
| 用户 / 工作流验收 | required | 登录/首页及业务页可导航 |
| 跨组件关键路径 | required | 路由、身份守卫与页面加载 |
| 外部依赖 / 供应方探测 | not_applicable | 无供应方行为变化 |
| 构建 / 打包 / 运行 | required | 生产构建 chunk 与首包对照 |
| 文档 / 治理 / 其他 | required | 前端 README、Change 和 CI |

# 风险、兼容性、迁移与回滚

风险是动态 chunk 加载失败导致单页不可达，使用构建与浏览器导航验证。无数据库 Migration；回滚前端构建恢复静态导入。路由 URL、名称和守卫逻辑均不变。

# 文档、依赖、部署与发布影响

同步前端 README 的加载说明。依赖、Runtime、配置、Secret、后端和公共 API 均不变；发布仍使用既有前端构建流程。

# 完成审计

- [x] upstream_re_read：重读 #618 / AC4、AC5、当前路由与身份守卫。
- [x] change_coverage：构建、路由、守卫和四个业务页面均由现有测试或浏览器旅程覆盖。
- [x] reverse_audit：每个导航入口对应仍存在的 route；四个动态 route 在浏览器测试中加载真实组件。
- [x] unresolved_cleared：`not_satisfied` 清零，生产网络收益留待用户实测。

# 完成证据与状态

基线 `main@90143b4e` 的 `npm run build` 通过：初始 JS 480.12 kB、gzip 141.53 kB；CSS 180.09 kB、gzip 27.84 kB。当前改动的 `npm run build`（包含 TypeScript 检查）通过：初始 JS 160.34 kB、gzip 54.54 kB；CSS 31.27 kB、gzip 6.40 kB，并生成四个页面各自的 JS/CSS chunk。初始 JS 原始大小降低约 66.6%，gzip 降低约 61.5%；这是构建证据，不代表真实网络时延。

`npm run lint` 通过；`npm run test -- --run` 为 32 文件、235 测试通过；`npm run test:e2e -- --workers=2` 为 138 个浏览器旅程通过，包括四个业务路由。原有测试已直接覆盖加载和操作，无需写与动态 import 代码逐行对应的低价值测试。当前 PR HEAD CI 待验证。无公共 Contract、依赖、Migration、配置或部署方式变化；前端回滚可恢复同步加载，但首包体积恢复旧值。
