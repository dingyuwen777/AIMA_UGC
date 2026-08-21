# AIMA_UGC 专题附录

这里放**需要讲得比较细，但不应该塞进核心 Blueprint 的内容**。

如果把整个文档体系看成一张地图：

- [`../blueprint/README.md`](../blueprint/README.md) 负责回答“系统长期为什么这样设计”；
- 模块 README 负责回答“当前代码具体在哪里、怎么实现”；
- 本目录负责回答“某个专题具体怎么运行、怎么调试、有哪些真实限制”；
- Contract、Migration、SQLAlchemy Table、生成 OpenAPI/Client、测试和锁文件继续是精确机器事实，文档不复制第二套 Schema。

## 先从哪个文档看

| 你想解决的问题 | 先看 |
| --- | --- |
| 想直接查 PostgreSQL，确认内容、任务、分析结果是否写进去 | [`PostgreSQL调试与常用SQL.md`](PostgreSQL调试与常用SQL.md) |
| 想理解定时采集为什么只补最新一次、服务重启后怎么恢复 | [`Scheduler运行与恢复.md`](Scheduler运行与恢复.md) |
| Mapper 对不上字段，想知道 TikHub 真实响应大概长什么样 | [`TikHub真实响应结构.md`](TikHub真实响应结构.md) |
| 想确认为什么选某个 TikHub endpoint，备用接口怎么启用 | [`TikHub接口验证与选型台账.md`](TikHub接口验证与选型台账.md) |
| 想理解 Excel、TikHub 手工入口如何最终写进同一个数据库 | [`数据入口与统一入库.md`](数据入口与统一入库.md) |
| 想运行 Excel 导入、去重、标签、统一 Excel 导出 | [`Excel导入导出与离线处理.md`](Excel导入导出与离线处理.md) |
| 想理解相关性、发声类型、情感、一级/二级标签如何一次完成 | [`AI舆情分析与打标.md`](AI舆情分析与打标.md) |
| 想从统一 Excel 生成 Markdown 与横向 A4 Word 舆情报告 | [`Word舆情报告.md`](Word舆情报告.md) |

前端页面设计与 Figma 属于开发工作流，不属于系统架构附录，见 [`../guides/README.md`](../guides/README.md)。

## 本目录的写法

每篇附录尽量按下面顺序写：

```text
为什么需要
→ 输入是什么
→ 实际流程
→ 当前代码位置
→ 最小例子
→ 常见问题/限制
→ 去哪里看精确机器事实
```

第一次出现的术语要用白话说明。能用一条真实数据或一条命令说明的问题，不用抽象名词绕一圈。

## 什么不放这里

以下内容不在附录里维护第二份：

- 完整数据库 DDL；
- 完整 HTTP 字段表；
- 完整 AI taxonomy；
- 每个 Migration 的 SQL 副本；
- 每个 Provider 私有响应的长期手工 Schema；
- 阶段开发流水和 PR 验证历史。

对应事实源分别是：

- 数据库：`backend/src/aima_ugc/**/tables.py` + `migrations/versions/`；
- HTTP：Pydantic Request/Response + `contracts/openapi/openapi.json`；
- AI taxonomy：`backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md`；
- TikHub：生产 Operation/Mapper + 脱敏 Fixture + `docs/collection/`；
- 阶段历史：`changes/archive/`。
