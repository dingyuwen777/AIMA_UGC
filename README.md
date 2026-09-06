# AIMA_UGC

AIMA_UGC 是爱玛 UGC 舆情采集、数据导入、AI 分析、查询、导出和离线报告的一体化应用仓库。

## 使用者先看什么

- 产品边界与当前能力：[`docs/product/`](docs/product/)
- 当前页面入口：声音广场、采集运行中心、采集策略、管理员配置；精确路由以 [`frontend/src/app/routes.ts`](frontend/src/app/routes.ts) 为准。
- 公司内网 V1：已完成；完整 Production Go-Live 仍有认证、备份恢复、供应链与生产验收等门禁。

## 开发者入口

1. 先读 [`AGENTS.md`](AGENTS.md)。
2. 文档总导航和事实源：[`docs/README.md`](docs/README.md)。
3. 改代码定位：[`docs/01_代码结构与修改导航.md`](docs/01_代码结构与修改导航.md)。
4. 长期架构与技术边界：[`docs/blueprint/README.md`](docs/blueprint/README.md)。
5. 当前尚未完成的正式工作：[`docs/roadmap/README.md`](docs/roadmap/README.md)。

精确机器事实不要从 README 复制：

- HTTP：Pydantic / FastAPI / [`contracts/openapi/openapi.json`](contracts/openapi/openapi.json)
- 数据库：SQLAlchemy Table / [`migrations/versions/`](migrations/versions/)
- 前端路由：[`frontend/src/app/routes.ts`](frontend/src/app/routes.ts)
- Worker Job：[`backend/src/aima_ugc/bootstrap/worker.py`](backend/src/aima_ugc/bootstrap/worker.py)
- 依赖版本：根/前端 Manifest、lock 和 version 文件

## 当前系统主链

```text
TikHub / 文件导入
→ Raw / Source Artifact
→ Operation / Reader / Mapper
→ Canonical
→ Relevance / Decision
→ Content Owner
→ PostgreSQL Current / Version / Metric / Coverage
→ Query / Analysis / Export / Report
→ Vue 产品页面
```

系统采用模块化单体；API、Worker、Scheduler、Migration 分进程；耗时任务统一进入 PostgreSQL Durable Job Runtime。

## 运行与运维

- 开发/本地运行：[`docs/02_环境运行与部署.md`](docs/02_环境运行与部署.md)
- 生产部署与离线 Release：[`docs/operations/01_生产部署与离线Release方案.md`](docs/operations/01_生产部署与离线Release方案.md)
- 4000 万历史迁移运行：[`docs/operations/02_4000万历史迁移与Analysis Run运行手册.md`](docs/operations/02_4000万历史迁移与Analysis%20Run运行手册.md)
- 测试与调试：[`docs/04_测试与调试说明.md`](docs/04_测试与调试说明.md)

## 当前 Active Roadmap

只保留两条已经批准且尚未完成的工作：

1. [`完整 Production Go-Live`](docs/roadmap/02_生产上线实施路线.md)
2. [`4000 万历史数据生产迁移`](docs/roadmap/03_4000万历史数据迁移实施方案.md)

已完成 Stage 的历史设计、PR/CI 和验收证据保留在 [`changes/archive/`](changes/archive/) 与 Git 历史，不继续占用当前 Roadmap。
