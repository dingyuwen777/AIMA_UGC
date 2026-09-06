# AIMA_UGC 专题附录

`docs/appendix/` 放**需要讲清具体实现、真实限制和调试方法，但不应该塞进核心 Blueprint 的技术专题**。

它不承担：

- 当前 Roadmap；
- 已完成 Stage 施工历史；
- Production 运行手册；
- 产品介绍；
- 第二套完整 Schema/OpenAPI/Taxonomy。

总导航见 [`docs/README.md`](../README.md)。

## 按问题找专题

| 问题 | 文档 | 主要机器事实入口 |
| --- | --- | --- |
| PostgreSQL 查询、Job/Content/Analysis/Export 排障 | [`docs/appendix/01_PostgreSQL查询与调试实战.md`](01_PostgreSQL查询与调试实战.md) | SQLAlchemy Table、Repository、Migration |
| TikHub 五平台真实响应和 Mapper 字段来源 | [`docs/appendix/02_TikHub五平台真实响应与字段映射.md`](02_TikHub五平台真实响应与字段映射.md) | Operation、Mapper、Sanitized Fixture |
| TikHub 多 API family 与备用策略 | [`docs/appendix/03_TikHub多接口验证与备用策略.md`](03_TikHub多接口验证与备用策略.md) | Capability、Operation、Fixture |
| TikHub Probe、接口选型和价格证据 | [`docs/appendix/04_TikHub接口选型与真实验证台账.md`](04_TikHub接口选型与真实验证台账.md) | endpoint ledger、Pricing、Probe |
| Scheduler、Cron、`latest_only`、停机恢复 | [`docs/appendix/05_Scheduler调度执行与停机恢复.md`](05_Scheduler调度执行与停机恢复.md) | Scheduler Domain/Bootstrap/Repository |
| Excel 统一契约、共享 Exporter、离线调试 | [`docs/appendix/06_Excel统一数据导出与离线调试.md`](06_Excel统一数据导出与离线调试.md) | Export Contract、共享 Excel 实现、imports_test |
| AI 打标、Validator、Retry、Analysis 持久化 | [`docs/appendix/07_AI舆情打标与分析实现.md`](07_AI舆情打标与分析实现.md) | Analysis 模块、当前 Scheme/Prompt、Repository |
| TikHub/File Import 如何进入统一 Content | [`docs/appendix/08_数据入口与统一入库实现.md`](08_数据入口与统一入库实现.md) | Reader/Mapper/Canonical/Ingestion/Content Owner |
| Markdown/Word 报告生成与排版 | [`docs/appendix/10_Word舆情报告生成与排版实现.md`](10_Word舆情报告生成与排版实现.md) | Reporting Platform、报告生成入口 |
| Artifact 生命周期、引用与清理 | [`docs/appendix/12_Artifact生命周期与保留策略.md`](12_Artifact生命周期与保留策略.md) | ArtifactService/Store、清理任务 |
| 数千万级 AI 打标成本与吞吐优化 | [`docs/appendix/13_AI大规模打标与成本优化方案.md`](13_AI大规模打标与成本优化方案.md) | Analysis 模块、LLM Adapter、当前 Analysis Identity |

## 已迁出本目录的内容

以下内容不是“删除知识”，而是回到更合适的长期 Owner：

- Production 部署/离线 Release → [`docs/operations/01_生产部署与离线Release方案.md`](../operations/01_生产部署与离线Release方案.md)；
- 4000 万历史迁移/Analysis Run 运行手册 → [`docs/operations/02_4000万历史迁移与Analysis Run运行手册.md`](../operations/02_4000万历史迁移与Analysis%20Run运行手册.md)；
- Stage 8F 已完成前后端验收历史 → `changes/archive/` 与 Git；真实 Full-stack 分层原则由 [`docs/04_测试与调试说明.md`](../04_测试与调试说明.md) 长期维护。

## 当前实现与未来目标必须分开

例如当前已经存在：

```text
Dockerfile / compose.yaml / env.production.example
GitHub 离线 Release 基础
Data Import Campaign
Analysis Run / Planner / Shard
```

因此附录不得继续把这些能力整体写成“尚未实现”。完整 Production 仍未完成的内容属于 [`docs/roadmap/02_生产上线实施路线.md`](../roadmap/02_生产上线实施路线.md)，不能反向把已实现基线改写成未来方案。

## 附录写作标准

一篇专题至少应让开发者知道：

```text
解决什么问题
输入/输出是什么
实际调用链怎样走
关键代码/Contract/表在哪里
为什么这样设计
失败和恢复边界
怎样验证/调试
当前限制
精确机器事实在哪里
```

完整 SQLAlchemy 列表、Alembic DDL、Pydantic 字段、OpenAPI、AI taxonomy 和 generated client 等高频漂移精确数据直接导航到机器事实，不在 Appendix 复制第二套。

历史为什么改过，查 [`changes/archive/`](../../changes/archive/)；未来已批准但未完成什么，查 [`docs/roadmap/`](../roadmap/)。
