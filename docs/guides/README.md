# AIMA_UGC 开发指南

`docs/guides/` 只放**开发或协作过程中怎么操作**的说明，不承担当前 Stage、数据库 Schema、API 字段或业务状态的事实源职责。

## 当前指南

- [`docs/guides/01_Figma与前端设计开发工作流.md`](01_Figma与前端设计开发工作流.md)：Figma/原型如何与当前 Vue、真实后端 Contract、公共组件和设计系统协作；
- [`docs/guides/03_Windows Docker Desktop Compose运行.md`](03_Windows%20Docker%20Desktop%20Compose运行.md)：Windows Docker Desktop 如何运行 canonical Compose + storage-only override；
- [`docs/guides/04_Docker国内构建源与本地重置.md`](04_Docker国内构建源与本地重置.md)：网络受限环境的构建源和开发机重置边界；
- [`docs/guides/05_多人协作与Change自动归档.md`](05_多人协作与Change自动归档.md)：多人协作、Requirement/Change、PR、Review、合并和自动归档的仓库工作流。

## 不再维护“固定持续开发提示词”

公司内网 V1 已完成，继续保存一份写死“Stage 8F → V1-A → V1-B → 上线”的通用提示词会把历史路线重新带回新会话。

新的开发任务统一从当前事实恢复：

```text
根 AGENTS.md
→ Agent_Skills 当前 canonical Source Mode
→ docs/README.md
→ 当前代码 / Contract / Migration / tests / locks
→ 仅在任务确实涉及未完成目标时读取 docs/roadmap/
```

因此新的 Agent 会话不需要复制一份仓库内固定大提示词。全局/团队使用方式由 Agent_Skills 与项目 [`AGENTS.md`](../../AGENTS.md) 治理，项目文档只维护当前项目事实和开发导航。

## 文档分工

```text
产品当前能做什么       → docs/product/
为什么系统这样设计       → docs/blueprint/
当前模块具体怎么实现       → 模块 README
专题实现、排障和深挖       → docs/appendix/
开发过程中怎么操作         → docs/guides/
生产部署/运行/迁移          → docs/operations/
已批准且未完成目标          → docs/roadmap/
历史为什么改过             → changes/archive/
精确字段/Schema/接口        → 代码、Migration、Contract、生成物、测试
```

如果目标是“我应该改哪个代码文件”，先读 [`docs/01_代码结构与修改导航.md`](../01_代码结构与修改导航.md)；总文档导航见 [`docs/README.md`](../README.md)。
