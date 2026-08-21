# AIMA_UGC Blueprint 导航

`docs/blueprint/` 只维护**长期架构、领域边界和跨模块技术决定**。

如果第一次接触项目，可以把 Blueprint 理解成“系统说明书的骨架”：它告诉你系统为什么这样拆、数据怎样流、哪些边界不能随便改变；它不负责保存每个 TikHub JSON 路径、每条 SQL、每个页面截图或某次 Stage 的施工流水。

如果你的目标是**马上定位代码并准备修改**，先读：

[`../代码结构与修改导航.md`](../代码结构与修改导航.md)

---

## 1. 文档体系怎么分工

```text
AGENTS.md
→ 所有开发/AI Agent 的统一规则入口

docs/代码结构与修改导航.md
→ 常见开发任务如何定位到真实源码、Contract、表和测试

docs/blueprint/
→ 为什么这样设计、长期边界是什么

模块 README
→ 当前模块具体怎么实现、Owner、主要类/函数、常见修改点

docs/appendix/
→ PostgreSQL、Scheduler、TikHub、Excel、AI、Word 报告等专题实现和调试

docs/guides/
→ Figma 等开发过程指南

docs/collection/
→ 五个平台当前采集能力的人类可读入口

代码 / Contract / Migration / generated / tests / locks
→ 精确机器事实

changes/archive/
→ 历史为什么改过、当时如何验证
```

核心 Blueprint 固定为 `01`—`08`。具体专题不再通过不断新增 `09、10、11...` 扩大核心蓝图。

---

## 2. 第一次进入仓库怎么读

推荐顺序：

1. 根目录 [`../../AGENTS.md`](../../AGENTS.md)；
2. [`.agents/skills/reliable-vibe-coding/SKILL.md`](../../.agents/skills/reliable-vibe-coding/SKILL.md)；
3. [`../代码结构与修改导航.md`](../代码结构与修改导航.md)；
4. 本文；
5. [`07-技术决策与实施门禁.md`](07-技术决策与实施门禁.md)；
6. 再按任务选下面一篇 Blueprint；
7. 最后读取对应模块 README、Contract、Migration、实现和测试。

不要把“一次读完所有文档”当成事实调查。进入具体任务后，只读与当前调用链直接相关的材料。

---

## 3. 八篇核心 Blueprint 分别解决什么

| 文档 | 解决的问题 | 读完后应该知道什么 |
| --- | --- | --- |
| [`01-总体架构与技术选型.md`](01-总体架构与技术选型.md) | 整个系统为什么这样拆？ | 当前真实模块、四个进程、依赖方向、关键代码入口 |
| [`02-采集系统与数据标准化.md`](02-采集系统与数据标准化.md) | TikHub/Excel 为什么能进入同一套业务数据？ | Raw、Mapper、Canonical、Relevance、Ingestion、来源追溯 |
| [`03-数据库与文件存储.md`](03-数据库与文件存储.md) | 什么放 PostgreSQL，什么放文件？ | Current/Version/Metric、表 Owner、Artifact、Job、Migration |
| [`04-后端任务API与前端.md`](04-后端任务API与前端.md) | 页面点按钮后请求怎么走？ | API、Job、Worker、Scheduler、OpenAPI Client、前端边界 |
| [`05-日志安全部署与运维.md`](05-日志安全部署与运维.md) | 出问题去哪看、Secret 怎么保护、怎么部署？ | 日志、安全、Secret、健康检查、部署、当前未闭环恢复能力 |
| [`06-开发约束与分阶段实施.md`](06-开发约束与分阶段实施.md) | 在这个仓库怎么可靠开发？ | Change、TDD、CI、Git、文档同步、验收 |
| [`07-技术决策与实施门禁.md`](07-技术决策与实施门禁.md) | 哪些跨模块决定已经拍板？ | 不能被普通任务偷偷改变的架构/兼容/门禁 |
| [`08-采集策略与平台能力.md`](08-采集策略与平台能力.md) | Plan 怎样选择 Provider/Platform，何时抓详情/评论？ | Capability、Decision、评论、Provider Billing、采集策略 |

---

## 4. 专题问题应该去哪看

### PostgreSQL / SQL

[`../appendix/PostgreSQL查询与调试实战.md`](../appendix/PostgreSQL查询与调试实战.md)

适合：

- 看最近内容、评论、版本和指标历史；
- 查 Job / Run / Batch / Analysis / Export；
- 核对真实表结构；
- `EXPLAIN`；
- Alembic；
- 安全使用事务调试。

### Scheduler

[`../appendix/Scheduler调度执行与停机恢复.md`](../appendix/Scheduler调度执行与停机恢复.md)

适合：

- `latest_only`；
- Occurrence；
- 停机恢复；
- 多 Scheduler 防重；
- Plan → Job → Run 事务；
- Scheduler 与 Worker 恢复区别。

### TikHub

- [`../collection/README.md`](../collection/README.md)：五平台当前能力、代码入口；
- [`../appendix/TikHub五平台真实响应与字段映射.md`](../appendix/TikHub五平台真实响应与字段映射.md)：真实 JSON 路径、Fixture、Operation/Mapper；
- [`../appendix/TikHub多接口验证与备用策略.md`](../appendix/TikHub多接口验证与备用策略.md)：App/Web/V1/V2/V3 如何验证、为什么不自动 fallback；
- [`../appendix/TikHub接口选型与真实验证台账.md`](../appendix/TikHub接口选型与真实验证台账.md)：已经做过的真实 Probe 和接口选型证据。

### Excel / 手工导入 / 统一入库

- [`../appendix/数据入口与统一入库实现.md`](../appendix/数据入口与统一入库实现.md)
- [`../appendix/Excel统一数据导出与离线调试.md`](../appendix/Excel统一数据导出与离线调试.md)

### AI 舆情打标

[`../appendix/AI舆情打标与分析实现.md`](../appendix/AI舆情打标与分析实现.md)

完整 taxonomy / Prompt 唯一业务事实源：

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md
```

### Word 舆情报告

[`../appendix/Word舆情报告生成与排版实现.md`](../appendix/Word舆情报告生成与排版实现.md)

### Figma / Design-to-Code

[`../guides/Figma与前端设计开发工作流.md`](../guides/Figma与前端设计开发工作流.md)

---

## 5. API、测试和部署入口

### HTTP API

[`../API接口说明.md`](../API接口说明.md)

精确机器链：

```text
Pydantic Request/Response
→ FastAPI Route
→ contracts/openapi/openapi.json
→ frontend/src/generated/api/
→ Contract / API Test
```

### 测试与独立调试

[`../测试与调试说明.md`](../测试与调试说明.md)

### 环境与部署

[`../环境运行与部署.md`](../环境运行与部署.md)

---

## 6. 事实冲突怎么处理

优先级不是简单“代码永远比文档高”。正确做法是：

```text
本轮用户明确决定 / 已批准 OpenSpec Change（存在时）
→ 当前代码、Migration、Contract、生成物、锁文件和测试
→ 07 的跨模块已确认决策
→ 01—08 领域 Blueprint
→ 模块 README / collection / appendix / guide
→ 根 README 导航摘要
→ 历史 Change / 旧聊天
```

遇到冲突先判断：

- 实现是否偏离了已批准架构；
- 文档是否只是过期；
- 是否有新决策已经形成但没同步。

确定正确事实后，同一任务把受影响代码/文档收口。

---

## 7. 当前系统实现边界

下面只写当前仓库代码能证明的事实。

### 当前后端业务模块

```text
system
collection
content
ingestion
analysis
reporting
```

当前没有 `monitoring/` 或 `dashboard/` 业务模块。

### 当前持久长任务

真实 Registry：`backend/src/aima_ugc/bootstrap/worker.py`

```text
collection.run.v1
ingestion.import-excel.v1
analysis.content-label.v1
reporting.content-export-excel.v1
```

### 当前前端路由

真实 Router：`frontend/src/app/routes.ts`

```text
/
/voice-plaza
/collection-runtime
/collection-strategy
```

当前正式业务 Feature：

```text
frontend/src/features/voice-plaza/
frontend/src/features/import-batches/
frontend/src/features/collection-strategy/
```

后端 API 已存在不等于一定存在独立 Vue 页面。

### 当前明确未闭环

- 企业登录 / 正式认证授权；
- 完整离线生产 Release；
- PostgreSQL + Artifact 协调 Backup/Restore 写屏障；
- Monitoring 告警、VOC、工单等正式业务模块；
- 独立 Dashboard 业务模块。

历史 Stage 进度只作为变更历史保存在 `changes/archive/`，不能代替当前代码事实。

---

## 8. 文档应该怎么写

正式文档优先回答：

```text
为什么需要
→ 输入是什么
→ 输出是什么
→ 数据/调用怎么走
→ 当前代码在哪里
→ 要修改这个行为应该改哪里
→ 如何验证/调试
→ 限制/未实现
→ 精确事实源在哪里
```

要求：

- 面向基础一般的开发者和需要理解系统方案的人；
- 必要术语第一次出现要用白话解释；
- 能用代码路径、真实表、真实 Fixture 说明就不要写空泛概念；
- Provider JSON 路径、状态机、调试 SQL、恢复边界等理解实现必须知道的内容，可以在 Appendix 直接展开；
- 固定且精确的数据结构可以直接导航到 `tables.py`、Contract、Prompt、Migration，避免复制第二套会漂移的 Schema；
- 不用“企业级、先进、高可用”等词替代具体机制；
- “已实现/未实现/默认行为/限制”必须能从当前仓库事实验证；
- 文档迁移只改变职责和结构，不以“精简”为理由删除仍然有效的技术细节。

---

## 9. 文档变大时放哪里

```text
改变长期系统架构/边界？
→ 更新 01—08 对应 Blueprint

某个模块当前实现细节？
→ 更新模块 README

某个专题的大篇幅实现/调试？
→ docs/appendix/

开发操作流程？
→ docs/guides/

某次变更为什么发生？
→ Change / changes/archive/

精确字段/Schema/类型？
→ 代码 / Contract / Migration / generated / tests
```

这能避免 Blueprint 随每个功能无限增长，同时又不会把真正有用的技术细节删掉。
