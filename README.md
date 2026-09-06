# AIMA_UGC

AIMA_UGC 是面向企业内部 UGC 舆情工作的采集、统一入库、内容查询、AI 分析和数据导出系统。当前产品已经完成公司内网 V1 部署；仓库继续维护两类明确未完成事项：**完整 Production Hardening** 与 **4000 万历史数据的生产容量/授权/执行闭环**。

## 当前产品入口

当前 Vue 路由以 [`frontend/src/app/routes.ts`](frontend/src/app/routes.ts) 为唯一机器事实。面向业务使用者的主要页面是：

- **声音广场**：内容查询、筛选、详情、人工相关性复核、手动 AI Analysis Run、Excel 导出；
- **采集运行中心**：采集运行、统一数据导入、运行状态与详情；
- **采集策略**：词包、全局相关性、周期采集计划；
- **管理员配置**：运行配置、业务目录和管理员专属配置入口；
- **工作台**：当前仍是开发中占位页，不应被描述成已经完成的业务 Dashboard。

产品层说明见 [`docs/product/README.md`](docs/product/README.md)。

## 系统主链

```text
TikHub / 文件导入
→ Raw / Source Artifact
→ Reader / Operation / Mapper
→ Canonical
→ Relevance / Decision
→ Content Owner
→ PostgreSQL Current / Version / Metric / Coverage
→ Query / Analysis / Export / 离线报告
→ Vue
```

采集、数据导入、AI 分析和导出等长任务使用 PostgreSQL Durable Job Runtime，由 API / Worker / Scheduler / Migration 四个正式 Python 进程承担不同职责。架构说明见 [`docs/blueprint/01_总体架构与技术选型.md`](docs/blueprint/01_总体架构与技术选型.md)。

## 文档从哪里开始

- [`docs/README.md`](docs/README.md)：**总入口**。先判断你需要产品、开发、架构、运维、Roadmap 还是专题资料；
- [`docs/01_代码结构与修改导航.md`](docs/01_代码结构与修改导航.md)：准备改代码时按业务问题找真实实现；
- [`docs/03_API接口说明.md`](docs/03_API接口说明.md)：HTTP API 使用与实现导航；
- [`docs/04_测试与调试说明.md`](docs/04_测试与调试说明.md)：测试分层、质量门禁和调试；
- [`docs/blueprint/README.md`](docs/blueprint/README.md)：长期架构与技术决策；
- [`docs/operations/README.md`](docs/operations/README.md)：部署、Release、生产运行和历史迁移操作；
- [`docs/roadmap/README.md`](docs/roadmap/README.md)：**只看当前已批准且尚未完成的工作**。

历史 Stage、已完成 Change、当时的决策和验收证据不继续堆在当前文档树：统一回到 [`changes/archive/`](changes/archive/) 与 Git 历史。

## 当前开发基线

后端是单仓模块化单体，前后端分离但共享同一仓库；精确依赖版本分别看 [`pyproject.toml`](pyproject.toml)、[`uv.lock`](uv.lock)、[`frontend/package.json`](frontend/package.json) 和 [`frontend/package-lock.json`](frontend/package-lock.json)。HTTP 类型链固定为：

```text
Pydantic HTTP Contract
→ FastAPI OpenAPI
→ contracts/openapi/openapi.json
→ Orval generated client
→ Vue Feature
```

生成的前端 Client 禁止手改。数据库结构只通过 Alembic Migration 演进。

源码开发与 Compose 运行命令见 [`docs/02_环境运行与部署.md`](docs/02_环境运行与部署.md)。

## 部署状态

当前已具备 Docker/Compose Internal V1 基线和 GitHub 离线 Release 基础，包括 `images.tar`、manifest、`SHA256SUMS`、`DEPLOY.md` 以及 `--no-build --pull never` 的离线回放链。完整 Production 仍不能宣称 Go-Live，剩余生产门禁见 [`docs/roadmap/02_生产上线实施路线.md`](docs/roadmap/02_生产上线实施路线.md)。

4000 万历史导入的软件能力已经完成；尚未完成的是公司服务器容量门禁、生产写授权、正式 Campaign 和全量对账。执行边界见 [`docs/roadmap/03_4000万历史数据迁移实施方案.md`](docs/roadmap/03_4000万历史数据迁移实施方案.md)。

## 修改项目时

先遵守根目录 [`AGENTS.md`](AGENTS.md) 及目标目录更具体的规则。不要从历史聊天、旧 Stage 文档或截图推断当前机器事实；需要精确字段、路由、表、Job、版本或 Workflow 时，回到当前代码、Contract、Migration、生成物、测试和锁文件。
