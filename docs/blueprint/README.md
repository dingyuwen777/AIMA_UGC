# AIMA_UGC Blueprint 导航

`docs/blueprint/` 保存系统长期架构、关键技术设计、跨模块决定，以及仍会影响后续开发的详细设计材料。

文档治理的目标不是把 Blueprint 变短，而是让读者知道：

```text
为什么这样设计
→ 当前代码在哪里
→ 详细实现去哪里看
→ 原阶段设计怎样追溯
→ 后续还要开发什么
→ 怎样一直做到生产上线
```

如果第一次接触仓库，建议先读：

1. [`../../AGENTS.md`](../../AGENTS.md)
2. [`../代码结构与修改导航.md`](../代码结构与修改导航.md)
3. 本文
4. [`07-技术决策与实施门禁.md`](07-技术决策与实施门禁.md)
5. [`../roadmap/生产上线实施路线.md`](../roadmap/生产上线实施路线.md)
6. 再按当前任务下钻 Blueprint、Appendix、模块 README、代码和测试

---

## 1. 文档体系怎么分工

```text
AGENTS.md
→ 所有开发/AI Agent 的统一规则入口

docs/代码结构与修改导航.md
→ 常见开发任务怎样定位真实源码、Contract、表和测试

docs/blueprint/
→ 长期架构 + 关键详细设计 + 当前实现导航 + 原阶段设计/验收记录

docs/roadmap/
→ 当前做到哪里、还缺什么、如何继续开发到生产上线

模块 README
→ 当前模块代码怎样实现、Owner、主调用链、常见修改入口

docs/appendix/
→ PostgreSQL、Scheduler、TikHub、Excel、AI、Word、生产部署等专题实现/调试

docs/guides/
→ Figma 等开发过程指南

docs/collection/
→ 五个平台当前采集能力的人类可读入口

代码 / Contract / Migration / generated / tests / locks
→ 精确机器事实

changes/archive/
→ 某次变更为什么发生、当时怎样验证
```

### 为什么原 Blueprint 09—17 的内容仍然保留

本轮不会为了目录更整齐而删除原 `09—17` 的有效技术内容。

原因很直接：其中仍有大量：

- Scheduler 恢复细节和 Stage 7 验收证据；
- TikHub 真实字段/接口验证证据；
- Excel 统一导出设计；
- AI taxonomy、Validator、Retry、离线运行等设计演进；
- Figma/前端设计原则和 Stage 8 工作流；
- Stage 8 数据入口、页面和实施顺序的完整方案。

但“内容保留”不等于“过去写的当前状态继续冒充今天事实”。因此本轮采用两种方式：

```text
仍然直接符合当前实现的详细文档
→ 保持原编号文件，做当前事实勘误/补充

包含大量历史阶段状态的详细文档
→ 原编号路径升级为当前实现导航
→ 原正文用原 Blob 原样保存在同编号“设计/阶段记录”文件
```

当前采用第二种方式的文件：

```text
09 Scheduler
15 AI Analysis
16 Frontend/Figma
17 Stage 8
```

也就是说：**原文没有丢，只是把“今天怎么做”和“当时为什么这样设计”分开了。**

---

## 2. 核心 Blueprint 01—08

| 文档 | 解决的问题 | 读完后应该知道什么 |
| --- | --- | --- |
| [`01-总体架构与技术选型.md`](01-总体架构与技术选型.md) | 整个系统为什么这样拆？ | 当前真实模块、四个进程、依赖方向、关键代码入口 |
| [`02-采集系统与数据标准化.md`](02-采集系统与数据标准化.md) | TikHub/Excel 为什么能进入同一套业务数据？ | Raw、Mapper、Canonical、Relevance、Ingestion、来源追溯 |
| [`03-数据库与文件存储.md`](03-数据库与文件存储.md) | 什么放 PostgreSQL，什么放文件？ | Current/Version/Metric、表 Owner、Artifact、Job、Migration |
| [`04-后端任务API与前端.md`](04-后端任务API与前端.md) | 页面点按钮后请求怎么走？ | API、Job、Worker、Scheduler、OpenAPI Client、前端边界 |
| [`05-日志安全部署与运维.md`](05-日志安全部署与运维.md) | 出问题去哪看、Secret 怎么保护、怎样进入生产？ | 日志、安全、Secret、健康、部署与恢复长期边界 |
| [`06-开发约束与分阶段实施.md`](06-开发约束与分阶段实施.md) | 在这个仓库怎么可靠开发？ | Change、TDD、CI、Git、文档同步、验收；阶段状态转到 Roadmap |
| [`07-技术决策与实施门禁.md`](07-技术决策与实施门禁.md) | 哪些跨模块决定已经拍板？ | 不能被普通任务偷偷改变的架构/兼容/门禁 |
| [`08-采集策略与平台能力.md`](08-采集策略与平台能力.md) | Plan 怎样选择 Provider/Platform，何时抓详情/评论？ | Capability、Decision、评论、Billing、采集策略 |

---

## 3. Blueprint 09—17：当前导航与详细设计保留区

### 3.1 Scheduler

当前实现入口：

- [`09-Scheduler运行与恢复策略.md`](09-Scheduler运行与恢复策略.md)
- [`../appendix/Scheduler调度执行与停机恢复.md`](../appendix/Scheduler调度执行与停机恢复.md)

Stage 7 完整设计/验收原文：

- [`09-Scheduler设计与Stage7验收记录.md`](09-Scheduler设计与Stage7验收记录.md)

### 3.2 TikHub 真实响应和接口选型

这些文件本身仍是详细证据文档，并与增强 Appendix 配合使用：

- [`10-TikHub真实响应结构附录.md`](10-TikHub真实响应结构附录.md) ↔ [`../appendix/TikHub五平台真实响应与字段映射.md`](../appendix/TikHub五平台真实响应与字段映射.md)
- [`11-TikHub多接口验证与备用策略.md`](11-TikHub多接口验证与备用策略.md) ↔ [`../appendix/TikHub多接口验证与备用策略.md`](../appendix/TikHub多接口验证与备用策略.md)
- [`12-TikHub真实请求响应与接口选型台账.md`](12-TikHub真实请求响应与接口选型台账.md) ↔ [`../appendix/TikHub接口选型与真实验证台账.md`](../appendix/TikHub接口选型与真实验证台账.md)

### 3.3 Excel

- [`13-统一数据Excel导出与调试复用.md`](13-统一数据Excel导出与调试复用.md)：原完整设计；
- [`../appendix/Excel统一数据导出与离线调试.md`](../appendix/Excel统一数据导出与离线调试.md)：当前实现/代码/调试入口。

### 3.4 AI Analysis

当前实现入口：

- [`15-舆情AI打标与统一分析契约.md`](15-舆情AI打标与统一分析契约.md)
- [`../appendix/AI舆情打标与分析实现.md`](../appendix/AI舆情打标与分析实现.md)
- `backend/src/aima_ugc/modules/analysis/README.md`
- `backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md`

P1/Stage 8 完整设计演进原文：

- [`15-舆情AI打标与统一分析设计演进记录.md`](15-舆情AI打标与统一分析设计演进记录.md)

### 3.5 Frontend / Figma

当前实现入口：

- [`16-前端页面架构与Figma设计工作流.md`](16-前端页面架构与Figma设计工作流.md)
- [`../guides/Figma与前端设计开发工作流.md`](../guides/Figma与前端设计开发工作流.md)
- `frontend/README.md`

Stage 8 完整设计原文：

- [`16-前端Figma设计与Stage8实施记录.md`](16-前端Figma设计与Stage8实施记录.md)

### 3.6 Stage 8

当前实现入口：

- [`17-Stage8数据入口统一入库与业务前端实施.md`](17-Stage8数据入口统一入库与业务前端实施.md)
- [`../appendix/数据入口与统一入库实现.md`](../appendix/数据入口与统一入库实现.md)
- [`../roadmap/生产上线实施路线.md`](../roadmap/生产上线实施路线.md)

Stage 8 A—F 完整实施设计/阶段快照原文：

- [`17-Stage8实施设计与阶段快照.md`](17-Stage8实施设计与阶段快照.md)

这些“设计/阶段记录”文件用于保留技术理由和演进证据；判断今天是否已实现，必须回到当前编号入口、代码、Contract、Migration 和测试。

---

## 4. 生产上线和未完成阶段去哪看

[`../roadmap/生产上线实施路线.md`](../roadmap/生产上线实施路线.md)

这篇必须长期保留：

```text
Stage 0—12 原设计目标
+ 当前代码状态
+ 已完成/部分完成/待实现/已被替代
+ 下一阶段开发顺序
+ Stage 11 Production Release
+ Stage 12 旧数据迁移
+ Go-Live 验收清单
```

重要原则：

> 未完成阶段不能因为“当前代码没有实现”就从文档里删除。

如果设计仍被批准且是生产目标的一部分，它必须继续留在 Roadmap/Blueprint 中，并明确写“待实现”。

---

## 5. 专题问题应该去哪看

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

### TikHub

- [`../collection/README.md`](../collection/README.md)：五平台当前能力、代码入口；
- [`../appendix/TikHub五平台真实响应与字段映射.md`](../appendix/TikHub五平台真实响应与字段映射.md)：真实 JSON 路径、Fixture、Operation/Mapper；
- [`../appendix/TikHub多接口验证与备用策略.md`](../appendix/TikHub多接口验证与备用策略.md)：App/Web/V1/V2/V3 如何验证；
- [`../appendix/TikHub接口选型与真实验证台账.md`](../appendix/TikHub接口选型与真实验证台账.md)：真实 Probe 与选型证据。

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

### 生产 Release / 上线

- [`../roadmap/生产上线实施路线.md`](../roadmap/生产上线实施路线.md)
- [`../appendix/生产部署与离线Release方案.md`](../appendix/生产部署与离线Release方案.md)
- [`../环境运行与部署.md`](../环境运行与部署.md)
- [`05-日志安全部署与运维.md`](05-日志安全部署与运维.md)

---

## 6. API、测试和部署入口

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

## 7. 事实冲突怎么处理

正确优先级：

```text
本轮用户明确批准的决定 / 正式 Change
→ 当前代码、Migration、Contract、generated、tests、locks
→ 07 的跨模块已确认决策
→ 01—08 核心 Blueprint
→ 当前实现导航 / Roadmap
→ 详细设计与阶段记录（用于解释设计理由，不覆盖今天机器事实）
→ 模块 README / collection / appendix / guide
→ 根 README 摘要
→ 历史 Change / 旧聊天
```

但要注意两类不同内容：

```text
“当前已经实现什么”
→ 必须服从当前机器事实

“已批准但尚未实现什么”
→ 不能因为代码不存在就删除；要保留并标待实现
```

如果旧设计被后续正式决策替代，例如旧 Provider Budget Ledger，则保留演进说明，同时明确禁止继续按旧方案开发。

---

## 8. 当前系统实现边界

### 当前后端业务模块

```text
system
collection
content
ingestion
analysis
reporting
```

当前没有正式 `monitoring/`、`alerts/`、`voc/`、`tickets/` 或 `dashboard/` 业务模块。

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

### 当前生产 Release 状态

仓库当前根目录没有：

```text
Dockerfile
compose.yaml
compose.production.yaml
env.production.example
```

因此完整离线生产 Release 仍是 Roadmap 中的待实现阶段，不能写成当前已经可以执行的命令。

---

## 9. 文档应该怎么写

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

- 面向开发者，也面向需要理解整个系统技术方案的人；
- 必要术语第一次出现用白话解释；
- 能用代码路径、真实表、真实 Fixture 说明就不要写空泛概念；
- Provider JSON 路径、状态机、SQL、恢复边界等理解实现必须知道的内容应直接展开；
- 固定且容易漂移的完整 Schema/Contract 可以导航到代码，不手工复制第二套；
- 已批准但未实现的设计必须明确标注“待实现”，不能删除；
- 文档迁移只改变职责和结构，不以“精简”为理由删除仍然有效的技术细节。

---

## 10. 文档变大时放哪里

```text
改变长期系统架构/边界？
→ 更新核心 Blueprint

某个详细技术设计仍影响多个阶段？
→ 保留详细设计/阶段记录，同时提供当前实现入口

某个模块当前实现细节？
→ 模块 README

某个专题的大篇幅实现/调试？
→ docs/appendix/

下一阶段/生产上线顺序？
→ docs/roadmap/

开发操作流程？
→ docs/guides/

某次变更为什么发生？
→ Change / changes/archive/

精确字段/Schema/类型？
→ 代码 / Contract / Migration / generated / tests
```

目录职责服务于开发，不为目录整洁牺牲可用信息。