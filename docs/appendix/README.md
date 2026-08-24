# AIMA_UGC 专题附录

本目录放**需要讲清具体实现、真实限制和调试方法，但不应该塞进核心 Blueprint 的专题内容**。

如果把整个文档体系看成一张地图：

- [`../blueprint/README.md`](../blueprint/README.md)：核心长期架构、边界和关键技术方向；
- [`../roadmap/README.md`](../roadmap/README.md)：当前做到哪里、还要怎么开发到生产上线；
- [`../01_代码结构与修改导航.md`](../01_代码结构与修改导航.md)：从业务问题快速找到真实代码；
- 模块 README：当前模块实现、Owner、主要类/函数和修改入口；
- 本目录：某个专题的完整实现流程、真实字段、状态机、SQL、排障、修改面；
- Contract、Migration、SQLAlchemy Table、生成 OpenAPI/Client、测试和锁文件：精确机器事实；
- `changes/archive/`：已完成 Stage/Change 为什么这样设计、当时怎样验收。

附录不是“摘要层”。一篇附录如果删掉了开发者理解实现必须知道的 Endpoint、JSON 路径、状态、错误边界、恢复方式、调用链、部署步骤或调试方法，就是失败的文档重构。

原 Blueprint 09—17 是 Stage 7、P1、Stage 8 开发过程中逐渐形成的详细专题/实施文档。对应阶段完成后，其**当前有效技术内容由本目录、Guide、模块 README 和核心 Blueprint 01—08 承接；历史施工过程由 `changes/archive/` 承接**，因此不需要继续占用核心 Blueprint。

---

## 1. 按问题找文档

| 你想解决的问题 | 先看 | 代码事实入口 |
| --- | --- | --- |
| 直接查 PostgreSQL，确认内容/Job/Analysis/Export 到底写了什么 | [`01_PostgreSQL查询与调试实战.md`](01_PostgreSQL查询与调试实战.md) | `backend/src/aima_ugc/**/tables.py`、`adapters/persistence/postgres/`、`migrations/versions/` |
| 理解定时采集、Cron、`latest_only`、停机恢复和并发防重 | [`05_Scheduler调度执行与停机恢复.md`](05_Scheduler调度执行与停机恢复.md) | `modules/collection/scheduler.py`、`bootstrap/scheduler.py`、Collection PostgreSQL Repository |
| 看五个平台 TikHub 真正返回哪些 JSON 字段、Mapper 从哪里取值 | [`02_TikHub五平台真实响应与字段映射.md`](02_TikHub五平台真实响应与字段映射.md) | `adapters/providers/tikhub/operations/`、`mappers/`、`tests/fixtures/providers/tikhub/` |
| 理解 App/Web/V1/V2/V3 为什么不自动切换、备用接口如何验证 | [`03_TikHub多接口验证与备用策略.md`](03_TikHub多接口验证与备用策略.md) | `capabilities.py`、接口比较/备用 Operation、Fixture |
| 查某次真实 Probe、endpoint 价格快照、接口选型证据 | [`04_TikHub接口选型与真实验证台账.md`](04_TikHub接口选型与真实验证台账.md) | `tests/fixtures/providers/tikhub/endpoint_ledger/`、Pricing、Probe 代码 |
| 理解 Excel 与 TikHub 为什么最后进入同一个 Content、来源链怎么保留 | [`08_数据入口与统一入库实现.md`](08_数据入口与统一入库实现.md) | `bootstrap/import_worker.py`、`manual_ingestion.py`、`modules/ingestion/`、`modules/content/ingestion.py` |
| 理解统一 Excel 数据契约、三张 Sheet、离线处理与共享 Exporter | [`06_Excel统一数据导出与离线调试.md`](06_Excel统一数据导出与离线调试.md) | `platform/export/excel.py`、`contracts/export/`、`adapters/providers/imports_test/` |
| 理解 AI relevance / voice_type / sentiment / labels、Validator、Retry、持久化 | [`07_AI舆情打标与分析实现.md`](07_AI舆情打标与分析实现.md) | `modules/analysis/`、当前 Prompt、Analysis PostgreSQL Repository |
| 评估数千万级 AI 打标的成本、吞吐、本地分类器与 LLM fallback 路线 | [`13_AI大规模打标与成本优化方案.md`](13_AI大规模打标与成本优化方案.md) | `modules/analysis/`、`adapters/llm/`、当前 Analysis Identity 与 Prompt/Taxonomy |
| 理解 Markdown/Word 报告的数据流、图表、词云和 DOCX 结构 | [`10_Word舆情报告生成与排版实现.md`](10_Word舆情报告生成与排版实现.md) | `platform/reporting/`、`imports_test/generate_report.py` |
| 从当前代码继续做到生产 Docker/Compose、离线 Release、备份恢复和回滚 | [`11_生产部署与离线Release方案.md`](11_生产部署与离线Release方案.md) | 当前 `entrypoints/`、`PlatformSettings`、Storage/Logging/Health；Docker/Compose 仍待 Stage 11 实现 |

前端页面设计与 Figma 属于开发工作流，见：

- [`../guides/01_Figma与前端设计开发工作流.md`](../guides/01_Figma与前端设计开发工作流.md)

后续阶段和生产上线优先读：

- [`../roadmap/02_生产上线实施路线.md`](../roadmap/02_生产上线实施路线.md)

---

## 2. 从原 Blueprint 09—17 迁下来的主题

当前长期承载关系：

```text
Scheduler 运行/恢复
→ 05_Scheduler调度执行与停机恢复.md

TikHub 真实响应/Mapper/Fixture
→ 02_TikHub五平台真实响应与字段映射.md

TikHub 多 API family / 备用策略
→ 03_TikHub多接口验证与备用策略.md

TikHub Probe / 接口选型台账
→ 04_TikHub接口选型与真实验证台账.md

统一 Excel / 离线调试
→ 06_Excel统一数据导出与离线调试.md

AI 打标 / Relevance / Voice Type / Validator / Retry / Persistence
→ 07_AI舆情打标与分析实现.md
→ backend/src/aima_ugc/modules/analysis/README.md
→ 当前 Prompt

数千万级 AI 打标 / 成本优化 / 本地分类器 / LLM fallback
→ 13_AI大规模打标与成本优化方案.md

Stage 8 数据入口/统一入库
→ 08_数据入口与统一入库实现.md

Frontend/Figma
→ docs/guides/01_Figma与前端设计开发工作流.md
→ frontend/README.md
```

如果需要知道“当时为什么拆成 8A/8B/8C、某个 PR 是怎样验收的”，查对应 `changes/archive/`，而不是在当前技术文档里维持施工日志。

---

## 3. 每篇附录必须达到什么标准

不是为了“有一篇文档”而写，而是要让读者能沿着文档落到代码和实际操作。

至少应该回答：

```text
这个能力解决什么问题？
输入是什么？
输出是什么？
完整调用链怎样走？
核心类/函数/表/Contract 在哪里？
为什么这样设计？
一条真实数据是怎样流过去的？
要改某个行为应该先改哪里？
怎么验证？
怎么调试？
失败时看什么？
哪些东西当前没有实现？
精确机器事实在哪里？
如果是待实现设计，后续应按什么最小单元落地？
```

### 可以直接写进文档的内容

理解实现必须知道、且适合人工阅读的内容应该直接写，例如：

- TikHub Endpoint 和真实 JSON 路径；
- `latest_only` 的状态变化；
- Provider Request/Attempt 的恢复边界；
- Content Current/Version/Metric 的业务语义；
- 一条 Excel 行怎样走到 `ContentIngestionService`；
- AI Validation Retry 与 Transport Retry 的区别；
- 安全的 PostgreSQL 排障 SQL；
- Word 报告的 Markdown → OOXML 流程；
- Production Release 的服务拓扑、目录、发布顺序、Backup/Restore/Rollback 机制。

### 更适合直接导航到代码的内容

精确且容易随实现变化的数据结构，不在文档里复制第二份：

- 完整 SQLAlchemy Table 列表；
- 完整 Alembic DDL；
- 完整 Pydantic HTTP 字段；
- 完整 OpenAPI；
- 完整 AI taxonomy；
- 生成的 TypeScript Client。

对应事实源：

```text
数据库结构
→ backend/src/aima_ugc/**/tables.py
→ migrations/versions/

HTTP
→ backend/src/aima_ugc/contracts/http.py
→ backend/src/aima_ugc/bootstrap/api.py
→ contracts/openapi/openapi.json

Canonical
→ backend/src/aima_ugc/contracts/canonical.py
→ contracts/canonical/

AI taxonomy
→ backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md
```

---

## 4. 当前事实与待实现设计要分开写

这是生产文档最容易出错的地方。

例如当前：

```text
API / Worker / Scheduler / Migration Python 入口
→ 已实现

Dockerfile / compose.yaml / production env / Release Bundle
→ 尚未实现
```

因此附录可以完整写 Production Release 目标设计，但必须明确：

```text
这是待实现目标
```

不能给读者一种“仓库里已经有脚本，照着执行就行”的错觉。

同理：

```text
Analysis
→ 已实现

Monitoring Alert/VOC/Ticket
→ 当前没有正式模块
```

未实现但已批准的后续技术方案不能因清理已完成 Stage 文档被删除；应留在 Roadmap/核心长期设计中，并标注状态。

---

## 5. 文档与代码不一致时怎么办

不要简单把代码抄进文档，也不要因为旧文档写得详细就默认它仍正确。

正确顺序：

```text
先找当前代码 / Contract / Migration / Fixture / Test
→ 看已批准长期决策和 Roadmap
→ 判断旧文档哪一段过期、哪一段仍是未来设计
→ 把当前有效技术事实放到正确的 Appendix/README/Blueprint
→ 把未完成目标保留在 Roadmap
→ 把历史过程留给 Change Archive
```

旧文档是迁移时“不能丢失哪些知识”的检查清单，但不是当前实现的永久事实源。

---

## 6. 什么不放这里

- 单次 PR 的过程流水；
- 历史 SHA 作为长期当前事实；
- 第二套完整数据库 Schema；
- 第二套完整 HTTP Contract；
- 第二套完整 AI taxonomy；
- 把还没实现的能力伪装成现在就能执行的命令。

历史为什么改过，放在：

```text
changes/archive/
```

当前实现是否真的存在，回到代码、Migration、Contract 和测试确认；未来仍需实现什么，回到 `docs/roadmap/`。