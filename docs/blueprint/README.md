# AIMA_UGC Blueprint 导航

`docs/blueprint/` 只维护**长期架构和稳定技术决定**。

如果你第一次接触项目，可以把 Blueprint 理解成“系统说明书的骨架”：它告诉你为什么系统这样拆、数据怎样流、哪些边界不能随便改变；它不负责保存每个 SQL、TikHub 字段、调试命令、页面截图或历史 Stage 施工记录。

## 1. 先看懂整个文档体系

```text
AGENTS.md
→ 所有开发/AI Agent 的统一规则入口

docs/blueprint/
→ 为什么这样设计、长期边界是什么

模块 README
→ 当前代码具体怎么实现、入口在哪里

docs/appendix/
→ PostgreSQL、Scheduler、TikHub、Excel、AI、报告等专题细节和调试

docs/guides/
→ Figma 等开发过程指南

docs/collection/
→ 五个平台当前采集实现的人类可读入口

代码 / Contract / Migration / 生成物 / 测试 / 锁文件
→ 精确机器事实

changes/archive/
→ 历史为什么改过、当时怎么验证
```

核心 Blueprint 固定为 `01`—`08`。具体专题不再通过不断新增 `09、10、11...` 扩大核心蓝图。

## 2. 第一次进仓库怎么读

固定顺序：

1. 根目录 [`AGENTS.md`](../../AGENTS.md)；
2. [`.agents/skills/reliable-vibe-coding/SKILL.md`](../../.agents/skills/reliable-vibe-coding/SKILL.md)；
3. 本文；
4. [`07-技术决策与实施门禁.md`](07-技术决策与实施门禁.md)；
5. 再按任务选择下面一篇 Blueprint；
6. 然后读取对应模块 README、Contract、Migration、实现、测试和配置。

不要把“一次性读完所有文档”当成事实调查。进入具体任务后，只读与当前调用链直接相关的材料。

## 3. 八篇核心 Blueprint 分别解决什么

| 文档 | 白话问题 | 什么时候读 |
| --- | --- | --- |
| [`01-总体架构与技术选型.md`](01-总体架构与技术选型.md) | 整个系统为什么这样拆？有哪些当前真实模块和运行进程？ | 总体架构、目录、跨模块边界、技术路线 |
| [`02-采集系统与数据标准化.md`](02-采集系统与数据标准化.md) | TikHub/Excel 等不同数据为什么最后能进入同一套业务数据？ | Provider、Raw、Mapper、Canonical、Relevance、Ingestion、来源追溯 |
| [`03-数据库与文件存储.md`](03-数据库与文件存储.md) | 什么放 PostgreSQL，什么放文件？为什么有 Current/Version/Metric？ | Schema、Migration、Repository、Artifact、数据历史、Job |
| [`04-后端任务API与前端.md`](04-后端任务API与前端.md) | 页面点按钮后请求怎么走？长任务为什么走 Job？ | API、Job、Worker、Scheduler、前端 Client、认证边界 |
| [`05-日志安全部署与运维.md`](05-日志安全部署与运维.md) | 出问题去哪看？Secret 怎么保护？哪些部署/备份能力已实现？ | 日志、安全、Secret、健康检查、部署、Release、备份 |
| [`06-开发约束与分阶段实施.md`](06-开发约束与分阶段实施.md) | 在这个仓库怎么可靠开发、测试、Review 和交付？ | 计划、Change、TDD、CI、Git、文档同步、Stage 判断 |
| [`07-技术决策与实施门禁.md`](07-技术决策与实施门禁.md) | 哪些跨模块决定已经拍板，不能被一个任务偷偷改掉？ | **每个任务都读**；重大决策、兼容、阶段门禁 |
| [`08-采集策略与平台能力.md`](08-采集策略与平台能力.md) | Plan 怎样选择 Provider/Platform，何时抓详情/评论，能力差异怎么处理？ | Collection Plan、Capability、Decision、评论、Provider Billing |

## 4. 具体问题去哪里看

### PostgreSQL / SQL

[`../appendix/PostgreSQL调试与常用SQL.md`](../appendix/PostgreSQL调试与常用SQL.md)

适合：

- 直接看最近内容；
- 查 Job/Run/Batch；
- 看 Analysis/Export；
- `EXPLAIN`；
- Alembic 命令；
- 安全事务练习。

### Scheduler

[`../appendix/Scheduler运行与恢复.md`](../appendix/Scheduler运行与恢复.md)

适合：

- `latest_only`；
- Occurrence；
- 停机恢复；
- 多 Scheduler 防重；
- Scheduler 和 Worker 恢复区别。

### TikHub

- [`../collection/README.md`](../collection/README.md)：五平台当前实现入口；
- [`../appendix/TikHub真实响应结构.md`](../appendix/TikHub真实响应结构.md)：Raw/Mapper 字段排障；
- [`../appendix/TikHub接口验证与选型台账.md`](../appendix/TikHub接口验证与选型台账.md)：API family、备用接口、真实 Probe。

### Excel / 手工导入 / 统一入库

- [`../appendix/数据入口与统一入库.md`](../appendix/数据入口与统一入库.md)
- [`../appendix/Excel导入导出与离线处理.md`](../appendix/Excel导入导出与离线处理.md)

### AI 舆情打标

[`../appendix/AI舆情分析与打标.md`](../appendix/AI舆情分析与打标.md)

完整 taxonomy / Prompt 唯一事实源仍是：

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md
```

### Word 舆情报告

[`../appendix/Word舆情报告.md`](../appendix/Word舆情报告.md)

### Figma / Design-to-Code

[`../guides/前端与Figma工作流.md`](../guides/前端与Figma工作流.md)

## 5. API、测试和部署入口

### HTTP API

[`../API接口说明.md`](../API接口说明.md)

它帮助人理解接口用途；精确机器事实仍是：

```text
Pydantic Request/Response
→ FastAPI Route
→ contracts/openapi/openapi.json
→ frontend/src/generated/api/
→ Contract/API tests
```

### 测试与独立调试

[`../测试与调试说明.md`](../测试与调试说明.md)

### 环境与部署

[`../环境运行与部署.md`](../环境运行与部署.md)

## 6. 事实冲突怎么处理

发生冲突时：

```text
本轮用户明确决定 / 已批准 OpenSpec Change（存在时）
→ 当前代码、Migration、Contract、生成物、锁文件和测试
→ 07 的跨模块已确认决策
→ 01—08 领域 Blueprint
→ 模块 README / collection / appendix / guide
→ 根 README 导航摘要
→ 历史 Change / 旧聊天
```

但是不能看到“代码比文档新”就无条件认为代码一定正确。要先判断：

- 实现是否偏离了已经批准的架构；
- 文档是否只是过期；
- 是否有新的正式决策尚未同步。

确定正确事实后，在同一任务把受影响代码/文档收口。

## 7. 当前系统状态

当前机器事实已经包含：

### 数据入口

- TikHub 五平台正式 Collection；
- Excel File Import；
- `tikhub_test` / `imports_test` 独立调试入口；
- Canonical → Relevance → Ingestion → PostgreSQL 统一业务入库。

### 数据与任务

- PostgreSQL Current/Version/Metric；
- Raw/Artifact 来源追溯；
- PostgreSQL 持久 Job；
- Scheduler `latest_only`；
- Processing Import Batch。

### 业务能力

- Import Batch/运行中心；
- Keyword Pack / Relevance Config / Collection Plan；
- 声音广场；
- Analysis；
- 正式 Excel Export；
- 离线 Markdown/Word 舆情报告。

### 当前明确未闭环

- 企业登录/正式认证授权；
- 完整离线生产 Release；
- 数据库 + Artifact 协调 Backup/Restore 写屏障；
- Stage 9 的 Monitoring 具体业务（告警、VOC/工单等尚需后续正式 Change）。

Stage 1—7、临时 P1、Stage 8A—8F 已闭环；下一正式方向是 **Stage 9 Analysis and Monitoring**。

Stage 名称只用于导航，不能替代代码/Schema 事实。

## 8. 文档怎么写

所有正式文档都按实际问题出发，优先回答：

```text
为什么需要
→ 输入是什么
→ 输出是什么
→ 数据/调用怎么走
→ 当前代码在哪里
→ 最小例子
→ 限制/未实现
→ 精确事实源在哪里
```

要求：

- 假设读者基础一般；
- 必要术语第一次出现用白话解释；
- 能不用术语就不要为了显得专业而堆术语；
- 代码、表名、命令只在帮助理解/调试时出现；
- 可以给短、真实、可验证的例子；
- 不复制第二套完整 Schema、OpenAPI、Prompt taxonomy、Migration SQL；
- 不用“企业级、先进、高可用”等空泛词替代具体机制；
- “已实现/未实现/默认行为/限制”必须能从当前仓库事实验证。

## 9. 文档变大时应该放哪

判断规则：

```text
改变了长期系统架构/边界？
→ 更新 01—08 对应 Blueprint

只是某个模块当前实现细节？
→ 更新模块 README

是某个专题的大篇幅运行/调试说明？
→ docs/appendix/

是开发操作流程？
→ docs/guides/

是某次变更为什么发生？
→ Change / changes/archive/

是精确字段/Schema/类型？
→ 代码 / Contract / Migration / generated / tests
```

这能避免 Blueprint 随每个功能无限增长。
