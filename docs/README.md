# AIMA_UGC 文档总入口

本页是仓库当前文档体系的总导航。它不复制第二套系统说明，而是回答：某类事实去哪里找，以及哪些文档描述现在、未来或历史。

## 1. 当前状态

- 公司内网 V1：**已完成**；
- 当前产品页面和业务闭环：以代码、前端路由和 Product 文档为准；
- 完整 Production Go-Live：**No-Go，仍有明确未完成门禁**；
- 4000 万历史数据：软件能力已完成，**公司服务器容量门禁、生产写授权、正式执行和全量对账仍未完成**。

已完成阶段不继续留在 `docs/roadmap/`。历史施工过程、当时的 PR/CI/SHA 和完成证据统一由 [`changes/archive/`](../changes/archive/) 与 Git 历史承载。

## 2. 文档分层

| 你要解决的问题 | 文档 Owner | 不承担什么 |
| --- | --- | --- |
| 产品是什么、当前用户能做什么 | [`docs/product/`](product/) | 不复制 API/Schema/Job 内部细节 |
| 我该改哪个代码 | [`docs/01_代码结构与修改导航.md`](01_代码结构与修改导航.md) + 模块 README | 不复制第二套架构说明 |
| 当前怎么运行/部署开发环境 | [`docs/02_环境运行与部署.md`](02_环境运行与部署.md) | 不维护 Production Roadmap |
| API 怎么调用 | [`docs/03_API接口说明.md`](03_API接口说明.md) | 不替代 Pydantic/OpenAPI |
| 怎么测试/调试 | [`docs/04_测试与调试说明.md`](04_测试与调试说明.md) | 不记录单次 PR 流水 |
| 系统长期为什么这样设计 | [`docs/blueprint/`](blueprint/) | 不记录已完成 Stage 施工日志 |
| 当前尚未完成且已经批准什么 | [`docs/roadmap/`](roadmap/) | 不收纳“以后也许做”的愿望清单 |
| 生产部署、Release、迁移怎么操作 | [`docs/operations/`](operations/) | 不把待实现生产门禁伪装成当前能力 |
| TikHub 各平台实现与实测 | [`docs/collection/`](collection/) | 不承担全局架构 |
| 深入专题、真实限制、排障 | [`docs/appendix/`](appendix/) | 不承担 Roadmap/历史归档 |
| Figma、本地 Compose、协作等开发操作 | [`docs/guides/`](guides/) | 不保存动态 Stage/SHA/PR 状态 |
| 某次变更为什么发生 | [`changes/archive/`](../changes/archive/) | 不作为当前实现的事实源 |

## 3. Source of Truth 矩阵

| 事实类型 | 最终机器事实 | 人工说明 Owner |
| --- | --- | --- |
| HTTP Route / 字段 | Pydantic + FastAPI + [`contracts/openapi/openapi.json`](../contracts/openapi/openapi.json) | [`docs/03_API接口说明.md`](03_API接口说明.md) |
| 数据库结构 | SQLAlchemy Table + [`migrations/versions/`](../migrations/versions/) | [`docs/blueprint/03_数据库与文件存储.md`](blueprint/03_数据库与文件存储.md) |
| Worker Job | [`backend/src/aima_ugc/bootstrap/worker.py`](../backend/src/aima_ugc/bootstrap/worker.py) 及注册模块 | [`docs/blueprint/01_总体架构与技术选型.md`](blueprint/01_总体架构与技术选型.md) |
| 前端路由 | [`frontend/src/app/routes.ts`](../frontend/src/app/routes.ts) | [`frontend/README.md`](../frontend/README.md) + Product 文档 |
| 前端 HTTP 类型 | OpenAPI → Orval 生成物 | [`frontend/README.md`](../frontend/README.md) |
| 依赖版本 | lock / version 文件 | 只在必要文档说明基线，不复制完整版本表 |
| Provider 能力 | Operation/Capability/Fixture | [`docs/collection/`](collection/) |
| Analysis Taxonomy | 当前 active Analysis Scheme；空库基线为当前 Prompt | Analysis README + AI Appendix |
| Release 事实 | [`.github/workflows/release.yml`](../.github/workflows/release.yml) + Compose/Dockerfile | [`docs/operations/01_生产部署与离线Release方案.md`](operations/01_生产部署与离线Release方案.md) |
| 当前未完成计划 | 已批准需求 + 当前代码状态 | [`docs/roadmap/`](roadmap/) |

当文档与机器事实冲突时，先判断哪个 Owner 落后，再更新承担该事实的 Owner；不要为了让两份文字一致而复制第三份。

## 4. 当前永久 Workflow

以下小型集合由文档事实门禁与 [`.github/workflows/`](../.github/workflows/) 做 **exact-set** 校验。新增、删除或重命名永久 Workflow 时必须同步此块；旧 Workflow 路径残留同样会失败。

<!-- docs-facts:permanent-workflows:start -->
- [`.github/workflows/change-archive.yml`](../.github/workflows/change-archive.yml)
- [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)
- [`.github/workflows/fullstack.yml`](../.github/workflows/fullstack.yml)
- [`.github/workflows/release.yml`](../.github/workflows/release.yml)
- [`.github/workflows/runtime.yml`](../.github/workflows/runtime.yml)
- [`.github/workflows/tooling.yml`](../.github/workflows/tooling.yml)
<!-- docs-facts:permanent-workflows:end -->

Workflow 的职责、验证层和调试方法见 [`docs/04_测试与调试说明.md`](04_测试与调试说明.md)。本块只维护文件集合，不复制 Workflow 实现。

## 5. 当前只保留两条 Active Roadmap

1. [`docs/roadmap/02_生产上线实施路线.md`](roadmap/02_生产上线实施路线.md)：完整 Production Hardening / Go-Live；
2. [`docs/roadmap/03_4000万历史数据迁移实施方案.md`](roadmap/03_4000万历史数据迁移实施方案.md)：公司服务器容量门禁、生产授权、正式执行和全量对账。

Monitoring/Alert/VOC/Ticket、Web Report Center、Dashboard、Gold Set、双人审批等候选方向只有在被业务明确批准后才进入 Roadmap。此前 Stage 文档提到它们，不等于它们现在是施工计划。

## 6. 文档生命周期

### Current

当前事实、当前实现、当前运维方法。必须随机器事实同步。

### Active Roadmap

只允许同时满足：

- 尚未完成；
- 目标已明确批准；
- 有业务/生产价值；
- 有可观察退出条件；
- 依赖和授权边界清楚。

每篇 live Roadmap 必须在文档前 20 行声明：

```text
- 状态：Active
```

完成后先迁移仍有效知识，再从 `docs/roadmap/` 退出。

### History

施工证据、完成阶段、当时的 PR/CI/SHA 和被替代方案由 `changes/archive/` 与 Git 历史承载，不新增第二套 `docs/archive` / `docs/history`。

## 7. 修改文档时

先读 [`docs/AGENTS.md`](AGENTS.md)。不要机械扫描/改写所有 Markdown；先确定受影响文档域和事实 Owner。涉及移动或删除时必须先完成知识迁移和链接迁移，再删除旧文件。
