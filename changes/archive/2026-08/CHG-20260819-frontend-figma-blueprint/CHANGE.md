---
id: CHG-20260819-frontend-figma-blueprint
title: 固化前端页面架构与 Figma 设计工作流
level: L3
status: done
owner: AI coding agent
branch: main
base_branch: main
created_at: 2026-08-19
updated_at: 2026-08-19
affected_paths:
  - docs/blueprint/README.md
  - docs/blueprint/16-前端页面架构与Figma设计工作流.md
rollback:
  strategy: revert
  note: 本变更只修改长期设计文档；如需撤回，使用普通 Git revert 回退本提交，不修改代码、Contract、Migration 或锁文件。
---

# 固化前端页面架构与 Figma 设计工作流

## 1. 背景与现状

Stage 1 已锁定 Vue 3 + TypeScript + Vite + Vue Router + Pinia + Element Plus + ECharts，并已建立 OpenAPI → Orval Client 基础；`04-后端任务API与前端.md` 已有 Feature/API/Store 高层边界，但正式 Stage 8 尚缺少以下长期规则：

- 页面级变化怎样隔离；
- App/Shared/Feature/Page 的 Owner 怎样划分；
- Figma 在系统中的事实边界；
- Figma MCP Design-to-Code 怎样适配现有 Vue 技术栈；
- Design Token、公共组件和 Element Plus 怎样协作；
- 高频需求变化时怎样保持前后端并行且不复制 Contract；
- 实现后怎样做工程与视觉验收。

当前 Stage 8 仍是下一正式阶段。本 Change 只固化设计基线，不开始正式业务 API 或页面实现。

## 2. 已确认方案

新增 `docs/blueprint/16-前端页面架构与Figma设计工作流.md` 作为前端页面组织与 Figma 工作流的唯一详细长期事实源，并更新 Blueprint README 导航。

固定方案：

```text
单一 Vue SPA
+ App Shell
+ Shared 公共层
+ Feature 业务模块
+ Page 页面级隔离
+ Pydantic/OpenAPI/Orval Contract 链
+ Figma 视觉/交互设计基线
+ Figma MCP 辅助 Design-to-Code
```

主要边界：

- 页面私有组件留在 Page；同 Feature 真正复用后提升到 Feature Component；跨 Feature 真正复用后再提升到 Shared；
- 不采用一页一个独立工程或微前端；
- Figma 负责已确认视觉/交互目标，不负责 API、数据库和后端业务规则；
- MCP 输出是设计上下文/参考实现，不是可直接提交的最终项目源码；
- 不因 MCP 示例引入 React、Tailwind 或第二套 UI/图表库；
- Element Plus 继续作为基础控件层，ECharts 继续作为当前图表基础；
- Figma Variable 与代码 CSS Custom Properties/Element Plus 变量建立语义映射；
- Code Connect/等价组件映射只在稳定公共组件形成后按需建立，不作为 Stage 8 前置条件；
- 不承诺 Figma 与 Vue 源码自动双向实时同步；代码先变更时需要把已确认视觉/交互同步回设计基线；
- 页面新增字段或业务行为时仍必须先冻结 Pydantic HTTP Contract，再生成 Client，前后端以生成类型/Fake/Mock 并行实现；
- Stage 8 先做公共骨架和一个完整页面纵切，再复制成熟模式，不一次性生成全部页面。

## 3. 文档组织决定

没有把同一套规则机械复制到 `04/06/07`：

- `04` 继续负责 API、Feature API/Store 和前后端数据方向；
- `06` 继续负责通用开发流程、测试和正式阶段顺序；
- `07` 继续负责跨文档技术路线、版本和 Go/No-Go；
- `16` 负责前端页面架构、Figma/MCP、Design Token、高频改版和视觉验收细则；
- Blueprint README 负责导航和 Stage 8 读取顺序。

这样后续规则只维护一份，降低 Blueprint 自身漂移风险。

## 4. 范围

本 Change 仅包含：

- 新增 Blueprint 16；
- 更新 Blueprint README 导航、索引、Stage 8 读取顺序和文档同步规则；
- 明确该设计固化不等于 Stage 8 业务实现已经开始。

## 5. 非目标与兼容性

本 Change 不：

- 修改 `frontend/` 代码；
- 修改 Vue/TypeScript/Vite/Pinia/Element Plus/ECharts/Orval 版本；
- 新增 npm 依赖；
- 修改 Pydantic/OpenAPI/生成 Client；
- 修改后端 API、数据库、Migration、Provider 或 Job；
- 建立真实 Figma 文件、Code Connect 映射或页面；
- 提前决定 Stage 8 具体页面字段、业务行为、权限或响应式断点。

因此无数据 Migration、部署或运行时兼容影响。

## 6. 验证与验收

交付前必须核对：

- Git 变更只包含本 Change、Blueprint README 和 Blueprint 16；
- README 对 Blueprint 16 的相对链接与文件名一致；
- Blueprint 16 对 `01/04/06/07` 的相对链接与现有文件名一致；
- Stage 8 仍明确为下一正式阶段，且文档说明本 Change 不等于业务页面实现开始；
- 文档没有改变当前技术版本、Contract、Migration 或运行代码事实；
- 提交后重新从 `main` 读取目标文件与提交 diff，确认内容和路径正确。

本任务是纯文档设计固化，不伪造 Red-Green 或运行时测试结论。
