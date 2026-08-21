# AIMA_UGC 专题附录

本目录放**需要讲清具体实现、真实限制和调试方法，但不应该塞进核心 Blueprint 的专题内容**。

如果把整个文档体系看成一张地图：

- [`../blueprint/README.md`](../blueprint/README.md)：长期架构和边界；
- [`../代码结构与修改导航.md`](../代码结构与修改导航.md)：从业务问题快速找到真实代码；
- 模块 README：当前模块实现、Owner、主要类/函数和修改入口；
- 本目录：某个专题的完整实现流程、真实字段、状态机、SQL、排障、修改面；
- Contract、Migration、SQLAlchemy Table、生成 OpenAPI/Client、测试和锁文件：精确机器事实。

附录不是“摘要层”。一篇附录如果删掉了开发者理解实现必须知道的 Endpoint、JSON 路径、状态、错误边界、恢复方式、调用链或调试步骤，就是失败的文档重构。

---

## 1. 按问题找文档

| 你想解决的问题 | 先看 | 代码事实入口 |
| --- | --- | --- |
| 直接查 PostgreSQL，确认内容/Job/Analysis/Export 到底写了什么 | [`PostgreSQL查询与调试实战.md`](PostgreSQL查询与调试实战.md) | `backend/src/aima_ugc/**/tables.py`、`adapters/persistence/postgres/`、`migrations/versions/` |
| 理解定时采集、Cron、`latest_only`、停机恢复和并发防重 | [`Scheduler调度执行与停机恢复.md`](Scheduler调度执行与停机恢复.md) | `modules/collection/scheduler.py`、`bootstrap/scheduler.py`、`collection_planning.py` |
| 看五个平台 TikHub 真正返回哪些 JSON 字段、Mapper 从哪里取值 | [`TikHub五平台真实响应与字段映射.md`](TikHub五平台真实响应与字段映射.md) | `adapters/providers/tikhub/operations/`、`mappers/`、`tests/fixtures/providers/tikhub/` |
| 理解 App/Web/V1/V2/V3 为什么不自动切换、备用接口如何验证 | [`TikHub多接口验证与备用策略.md`](TikHub多接口验证与备用策略.md) | `capabilities.py`、`api_family_compare.py`、`operations/backup.py` |
| 查某次真实 Probe、endpoint 价格快照、接口选型证据 | [`TikHub接口选型与真实验证台账.md`](TikHub接口选型与真实验证台账.md) | `tests/fixtures/providers/tikhub/endpoint_ledger/`、Pricing、Probe 代码 |
| 理解 Excel 与 TikHub 为什么最后进入同一个 Content、来源链怎么保留 | [`数据入口与统一入库实现.md`](数据入口与统一入库实现.md) | `bootstrap/import_worker.py`、`manual_ingestion.py`、`modules/ingestion/`、`modules/content/ingestion.py` |
| 理解统一 Excel 数据契约、三张 Sheet、离线处理与共享 Exporter | [`Excel统一数据导出与离线调试.md`](Excel统一数据导出与离线调试.md) | `platform/export/excel.py`、`adapters/providers/imports_test/` |
| 理解 AI relevance / voice_type / sentiment / labels、Validator、Retry、持久化 | [`AI舆情打标与分析实现.md`](AI舆情打标与分析实现.md) | `modules/analysis/`、当前 Prompt、`adapters/persistence/postgres/analysis.py` |
| 理解 Markdown/Word 报告的数据流、图表、词云和 DOCX 结构 | [`Word舆情报告生成与排版实现.md`](Word舆情报告生成与排版实现.md) | `platform/reporting/`、`imports_test/generate_report.py` |

前端页面设计与 Figma 属于开发工作流，见：

- [`../guides/Figma与前端设计开发工作流.md`](../guides/Figma与前端设计开发工作流.md)

---

## 2. 每篇附录必须达到什么标准

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
- Word 报告的 Markdown → OOXML 流程。

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

## 3. 文档与代码不一致时怎么办

不要简单把代码抄进文档，也不要因为旧文档写得详细就默认它仍正确。

正确顺序：

```text
先找当前代码 / Contract / Migration / Fixture / Test
→ 看已批准长期决策
→ 判断旧文档哪一段过期
→ 保留仍有效的技术细节
→ 修正过期事实
→ 补缺失的代码入口和验证方法
```

旧文档可以作为“不能丢失哪些知识”的清单，但不能作为当前实现的最终事实源。

---

## 4. 什么不放这里

- 阶段施工日志和某次 PR 的完整过程；
- 历史 SHA 作为长期事实；
- 第二套完整数据库 Schema；
- 第二套完整 HTTP Contract；
- 第二套完整 AI taxonomy；
- 还没实现的能力写成当前正式说明。

历史为什么改过，放在：

```text
changes/archive/
```

当前实现是否真的存在，回到代码、Migration、Contract 和测试确认。
