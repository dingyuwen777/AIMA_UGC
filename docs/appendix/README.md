# AIMA_UGC 专题附录

docs/appendix/ 放**需要讲清具体实现、真实限制和调试方法，但不应该塞进核心 Blueprint 的技术专题**。

它不承担 Agent_Skills 通用治理、当前 Roadmap、已完成 Stage、Production 操作手册、产品介绍或第二套完整 Schema/OpenAPI/Taxonomy。

总导航见 [docs/README.md](../README.md)。

## 按问题找专题

| 问题 | 专题 | 主要事实入口 |
| --- | --- | --- |
| PostgreSQL 查询与排障 | [docs/appendix/01_PostgreSQL查询与调试实战.md](01_PostgreSQL查询与调试实战.md) | SQLAlchemy / Repository / Migration |
| TikHub 真实响应与 Mapper 字段 | [docs/appendix/02_TikHub五平台真实响应与字段映射.md](02_TikHub五平台真实响应与字段映射.md) | Operation / Mapper / Fixture |
| TikHub 多 API family 怎样验证 | [docs/appendix/03_TikHub多接口验证与备用策略.md](03_TikHub多接口验证与备用策略.md) | 验证方法 / 切换门禁 |
| TikHub 当前主链与历史验证证据 | [docs/appendix/04_TikHub接口选型与真实验证台账.md](04_TikHub接口选型与真实验证台账.md) | endpoint ledger / Pricing / Probe |
| Scheduler、Cron、停机恢复 | [docs/appendix/05_Scheduler调度执行与停机恢复.md](05_Scheduler调度执行与停机恢复.md) | Scheduler Domain / Repository |
| Excel 导出与离线调试 | [docs/appendix/06_Excel统一数据导出与离线调试.md](06_Excel统一数据导出与离线调试.md) | Export Contract / Excel 实现 |
| AI 打标实现与排障 | [docs/appendix/07_AI舆情打标与分析实现.md](07_AI舆情打标与分析实现.md) | Analysis 模块 / active Scheme |
| 数据入口、Replay/撤销实现与排障 | [docs/appendix/08_数据入口与统一入库实现.md](08_数据入口与统一入库实现.md) | Reader / Mapper / Ingestion / Lineage |
| Word 报告生成与排版 | [docs/appendix/10_Word舆情报告生成与排版实现.md](10_Word舆情报告生成与排版实现.md) | Reporting Platform |
| 资源生命周期与撤销 | [docs/appendix/11_业务资源生命周期与数据撤销实现.md](11_业务资源生命周期与数据撤销实现.md) | Lifecycle / HTTP / Migration |
| Artifact 生命周期 | [docs/appendix/12_Artifact生命周期与保留策略.md](12_Artifact生命周期与保留策略.md) | ArtifactService / Store |
| AI 大规模容量、成本与候选优化评估 | [docs/appendix/13_AI大规模打标与成本优化方案.md](13_AI大规模打标与成本优化方案.md) | 当前机器事实 + 明确标记候选 |

## Appendix 和 Blueprint 的分界

Blueprint 回答“为什么系统必须有这条长期边界”；Appendix 回答“当前具体实现怎样落地、哪里容易出错、怎么查”。

例如统一 Canonical / Content Owner 的必要性由 [docs/blueprint/02_采集系统与数据标准化.md](../blueprint/02_采集系统与数据标准化.md) 解释；Excel、TikHub、Replay 怎样接入和排障由 [docs/appendix/08_数据入口与统一入库实现.md](08_数据入口与统一入库实现.md) 解释。

## TikHub：方法与证据分开

- [docs/appendix/03_TikHub多接口验证与备用策略.md](03_TikHub多接口验证与备用策略.md) 只维护方法、状态含义、切换门禁和禁止事项；
- [docs/appendix/04_TikHub接口选型与真实验证台账.md](04_TikHub接口选型与真实验证台账.md) 维护已取得的 Endpoint、价格和 A/B 证据。

同一 Endpoint / Probe 事实不在两篇重复维护。

## 当前事实与候选方案分开

Appendix 可以保存长期有价值的技术评估，但必须明确“已实现事实 / 外部已核验事实（带日期） / 未批准候选”。未批准候选不是当前能力，也不是 Roadmap；只有正式批准后才进入 [docs/roadmap/](../roadmap/) 或独立 Requirement/Change。

历史施工过程仍去 [changes/archive/](../../changes/archive/)。
