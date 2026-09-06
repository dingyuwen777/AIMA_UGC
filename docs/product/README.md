# AIMA_UGC 产品文档

本目录从**业务使用者和产品维护者**视角描述 AIMA_UGC。这里回答“产品现在能做什么、用户怎样完成任务、哪些能力尚未完成”，不把 Job type、数据库表、Provider 私有字段或内部 ID 当成产品语言。

当前入口：

- [`docs/product/01_产品概述与边界.md`](01_产品概述与边界.md)：产品目标、当前范围、明确不属于当前产品的内容；
- [`docs/product/02_当前产品能力与用户流程.md`](02_当前产品能力与用户流程.md)：按页面和用户任务描述当前已实现能力；
- [`docs/product/03_角色权限与产品状态.md`](03_角色权限与产品状态.md)：管理员/普通用户边界、当前身份实现状态和 Production 前置门禁。

精确页面 Route 以 [`frontend/src/app/routes.ts`](../../frontend/src/app/routes.ts) 为机器事实；精确 API/Schema 不在本目录复制，分别回到 OpenAPI、Contract、Migration 和模块 README。

## 产品文档原则

1. **先说用户任务，再说系统概念。** 正常使用者不需要理解 Batch ID、Run ID、Shard、Provider Attempt 等工程细节才能完成操作。
2. **只写已经存在的产品能力。** 工作台当前是占位页，就明确写占位；候选 Dashboard 不写成待开发承诺。
3. **管理员能力与普通业务能力分开。** Secret、模型 URL/API Key、运行配置等只在管理员边界内出现。
4. **Figma 不能发明后端能力。** 设计稿中的数据源、筛选、状态和权限必须落回当前 Contract/代码；开发流程见 [`docs/guides/01_Figma与前端设计开发工作流.md`](../guides/01_Figma与前端设计开发工作流.md)。
5. **产品 Roadmap 不是愿望清单。** 只有已经批准、尚未完成且有退出条件的事项才进入 [`docs/roadmap/`](../roadmap/)。
