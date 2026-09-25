# AIMA_UGC 文档总入口

本页只回答两个问题：**某类事实由谁负责？为了完成当前任务应该从哪里开始看？**

AIMA_UGC 继续使用 Agent_Skills 作为通用研发治理能力。AIMA 自己的文档树不复制第二套通用 Analysis / Coding / Testing / Review / Docs / Figma / Git / Delivery 方法；进入项目时先遵守 [AGENTS.md](../AGENTS.md)，再按当前任务恢复 AIMA 的项目事实。

## 1. 先区分四类信息

### 当前机器事实

精确、易变化、可以由仓库直接验证的事实，由机器 Owner 持有，例如：

- HTTP Route / Request / Response → Pydantic + FastAPI + [contracts/openapi/openapi.json](../contracts/openapi/openapi.json)
- 数据库结构 → SQLAlchemy + [migrations/versions/](../migrations/versions/)
- Worker Job 注册 → [backend/src/aima_ugc/bootstrap/worker.py](../backend/src/aima_ugc/bootstrap/worker.py)
- 前端 Route → [frontend/src/app/routes.ts](../frontend/src/app/routes.ts)
- 依赖与 Runtime 版本 → lock / version 文件
- CI / Release 行为 → [.github/workflows/](../.github/workflows/)

Markdown 解释这些事实的目的、边界、用法和定位方式，**不手抄一份完整机器定义**。

### 当前长期说明

回答“现在为什么这样设计、用户现在能做什么、当前怎样操作”，分别由 Product、Blueprint、Operations、Guides、Collection、Appendix 承担。

### 已批准但尚未完成

只进入 [docs/roadmap/](roadmap/)。Roadmap 不保存“以后也许做”的候选方向。

### 历史

施工过程、当时的 PR / CI / SHA、已完成 Stage 和被替代方案进入 [changes/archive/](../changes/archive/) 与 Git 历史，不继续占用 live docs。

## 2. 文档 Owner

| 读者要解决的问题 | 唯一长期 Owner | 不承担什么 |
| --- | --- | --- |
| 产品是什么、当前用户能做什么 | [docs/product/](product/) | 不复制 API/表/Job 内部实现 |
| 我应该从哪个代码入口开始改 | [docs/01_代码结构与修改导航.md](01_代码结构与修改导航.md) + 模块 README | 不维护第二套架构说明 |
| 日常源码开发怎样启动和排障 | [docs/02_环境运行与部署.md](02_环境运行与部署.md) | 不复制 Windows / Release / Production 专项手册 |
| HTTP API 怎样理解和调用 | [docs/03_API接口说明.md](03_API接口说明.md) | 不镜像完整 OpenAPI Route / 字段集合 |
| 当前项目怎样选择测试和调试入口 | [docs/04_测试与调试说明.md](04_测试与调试说明.md) | 不复制 Agent_Skills 通用测试方法 |
| 系统长期为什么这样设计 | [docs/blueprint/](blueprint/) | 不记录单次施工、PR、CI 流水 |
| 当前已经批准但尚未完成什么 | [docs/roadmap/](roadmap/) | 不收纳未批准候选 |
| 已经存在的生产/迁移能力怎样操作 | [docs/operations/](operations/) | 不把未完成 Production 门禁写成当前能力 |
| 五个平台的 TikHub 当前实现差异 | [docs/collection/](collection/) | 不承担全局采集架构 |
| 某个实现专题、真实限制和调试方法 | [docs/appendix/](appendix/) | 不承担 Roadmap 或通用治理 |
| Figma、Compose、本地 Release、团队协作等开发操作 | [docs/guides/](guides/) | 不维护业务状态、Schema 或动态 Stage |
| 某次变更为什么发生、当时怎样验证 | [changes/archive/](../changes/archive/) | 不作为当前实现说明 |

### 单一解释 Owner

同一个长期事实只允许一个文档 Owner 完整解释。其他文档如果需要它，只保留必要上下文并链接唯一 Owner，不再复制完整规则、完整 Route、完整 Schema、完整状态表或完整流程。

## 3. Agent_Skills 与 AIMA 的边界

~~~text
Agent_Skills
→ 通用研发治理：怎样分析、编码、测试、Review、写文档、做设计和交付

AIMA_UGC/AGENTS.md
→ 项目治理入口 + AIMA Overlay + 当前项目导航

AIMA docs / code / Contract / Schema / CI
→ AIMA 自己的产品、架构、运行和机器事实
~~~

因此：

- AIMA **继续完整使用** Agent_Skills；
- AIMA 文档可以说明“本项目怎样接入通用治理”，但不复制 Agent_Skills 的通用方法正文；
- AIMA 特有的 Change carrier、质量脚本、Workflow、GitHub App、目录、Contract 和运行事实必须继续留在 AIMA；
- 通用规则变化时，不要求人工同步一套 AIMA 文档副本。

## 4. Source of Truth 矩阵

| 事实类型 | 最终机器事实 | 人工说明 Owner |
| --- | --- | --- |
| HTTP Route / 字段 | Pydantic + FastAPI + [contracts/openapi/openapi.json](../contracts/openapi/openapi.json) | [docs/03_API接口说明.md](03_API接口说明.md) 只解释调用语义 |
| 数据库结构 | SQLAlchemy + [migrations/versions/](../migrations/versions/) | [docs/blueprint/03_数据库与文件存储.md](blueprint/03_数据库与文件存储.md) |
| Worker Job | [backend/src/aima_ugc/bootstrap/worker.py](../backend/src/aima_ugc/bootstrap/worker.py) | [docs/blueprint/01_总体架构与技术选型.md](blueprint/01_总体架构与技术选型.md) |
| 前端 Route | [frontend/src/app/routes.ts](../frontend/src/app/routes.ts) | [frontend/README.md](../frontend/README.md) + Product |
| 前端 HTTP 类型 | OpenAPI → Generated Client | [frontend/README.md](../frontend/README.md) |
| Provider 能力 | Operation / Capability / Fixture / Test | [docs/collection/](collection/) |
| Analysis Taxonomy | 当前 active Analysis Scheme；空库基线为当前 Prompt | Analysis README + [docs/appendix/07_AI舆情打标与分析实现.md](appendix/07_AI舆情打标与分析实现.md) |
| Release | Workflow + Dockerfile + Compose | [docs/operations/01_生产部署与离线Release方案.md](operations/01_生产部署与离线Release方案.md) |
| 未完成计划 | 已批准 Requirement + 当前实现状态 | [docs/roadmap/](roadmap/) |

文档与机器事实冲突时，先判断“实现缺陷 / 文档漂移 / 已批准未来设计 / 新决策”，再修正确的一方；不要为了表面一致制造第三份事实。

## 5. 当前永久 Workflow

以下小型集合由文档事实门禁做 exact-set 校验；这里只维护文件集合，不复制 Workflow 实现。

<!-- docs-facts:permanent-workflows:start -->
- [`.github/workflows/change-archive.yml`](../.github/workflows/change-archive.yml)
- [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)
- [`.github/workflows/fullstack.yml`](../.github/workflows/fullstack.yml)
- [`.github/workflows/release.yml`](../.github/workflows/release.yml)
- [`.github/workflows/runtime.yml`](../.github/workflows/runtime.yml)
- [`.github/workflows/tooling.yml`](../.github/workflows/tooling.yml)
<!-- docs-facts:permanent-workflows:end -->

职责和测试层见 [docs/04_测试与调试说明.md](04_测试与调试说明.md)。

## 6. 当前 Active Roadmap

当前只保留两条：

1. [docs/roadmap/02_生产上线实施路线.md](roadmap/02_生产上线实施路线.md)：完整 Production Hardening / Go-Live；
2. [docs/roadmap/03_4000万历史数据迁移实施方案.md](roadmap/03_4000万历史数据迁移实施方案.md)：容量门禁、生产授权、正式执行和全量对账。

未批准的 AI 降本、本地分类器、Monitoring、Dashboard、Gold Set 等候选方向**不因为在研究文档里出现就自动成为 Roadmap**。

## 7. 文档生命周期

### Current

当前产品、架构、使用、运行、调试说明。承担当前事实的文档必须随正确事实同步。

### Active Roadmap

必须同时满足：已明确批准、尚未完成、有可观察退出条件、依赖和授权边界明确。每篇 live Roadmap 前 20 行必须包含“- 状态：Active”。

### Temporary Operations / Migration Guide

只服务某次尚未完全退出的部署、Migration、回填或迁移窗口。最后一个需要该手册的目标环境完成后，把长期知识并入正式 Owner，把执行证据留在 [changes/archive/](../changes/archive/) 与 Git，然后删除临时 live 文档。

### History

统一由 [changes/archive/](../changes/archive/) 与 Git 承担，不新增第二套 docs/archive 或 docs/history。

## 8. 修改文档时

先读 [docs/AGENTS.md](AGENTS.md)，再回答：

1. 谁会读？
2. 他要完成什么任务？
3. 哪个 Owner 应该解释这个事实？
4. 精确机器事实在哪里？
5. 现有文档能否通过修改/链接解决，还是确实需要新文档？
6. 删除或合并前，仍有效知识迁到哪里？
7. 这篇文档有没有明确退出条件？

**文档数量不是目标；单一 Owner、最小充分解释和可验证事实才是目标。**
