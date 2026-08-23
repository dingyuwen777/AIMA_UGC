# AIMA_UGC Blueprint 导航

`docs/blueprint/` 只维护**长期有效的系统架构、边界、关键技术方向和跨模块决定**。

它不是实现手册，也不是 Stage 施工记录。

如果第一次接触仓库，建议先读：

1. [`../../AGENTS.md`](../../AGENTS.md)
2. [`../01_代码结构与修改导航.md`](../01_代码结构与修改导航.md)
3. 本文
4. [`07_技术决策与实施门禁.md`](07_技术决策与实施门禁.md)
5. [`../roadmap/02_生产上线实施路线.md`](../roadmap/02_生产上线实施路线.md)
6. 再按当前任务下钻对应 Appendix、Guide、模块 README、Contract、Migration、代码和测试

---

## 1. Blueprint 和其他文档分别负责什么

```text
Blueprint
→ 系统为什么这样设计
→ 哪些边界长期不能随便改
→ 主要技术方向是什么

Roadmap
→ 当前做到哪里
→ 下一阶段做什么
→ 哪些能力尚未完成
→ 怎样一直做到生产服务器上线

模块 README
→ 当前模块代码怎样实现
→ Owner、入口、调用链、修改位置

Appendix
→ Scheduler、TikHub、Excel、AI、PostgreSQL、Word、Production Release 等大篇幅技术细节和调试

Guide
→ Figma 等开发过程工作流

代码 / Contract / Migration / generated / tests / locks
→ 精确机器事实

changes/archive
→ 某次变更为什么发生、当时怎样验证
```

原则：

> Blueprint 控制“方向和边界”，Appendix/README 解释“具体怎样实现”，Roadmap 保证“后续开发路线不丢”。

---

## 2. 当前核心 Blueprint

当前核心 Blueprint 固定为 `01—08`：

| 文档 | 解决的问题 | 关键结论 |
| --- | --- | --- |
| [`01_总体架构与技术选型.md`](01_总体架构与技术选型.md) | 整个系统怎样拆？ | 模块化单体、API/Worker/Scheduler/Migration 分进程、当前技术栈和依赖方向 |
| [`02_采集系统与数据标准化.md`](02_采集系统与数据标准化.md) | 不同数据来源怎样进入同一体系？ | Provider/File → Raw/Input → Mapper → Canonical → Relevance → Ingestion → PostgreSQL |
| [`03_数据库与文件存储.md`](03_数据库与文件存储.md) | 什么放数据库，什么放文件？ | PostgreSQL 唯一业务事实库、Current/Version/Metric、Artifact、表 Owner、Migration |
| [`04_后端任务API与前端.md`](04_后端任务API与前端.md) | API、Job、Worker、Scheduler、前端怎样协作？ | 长任务 durable Job、OpenAPI generated Client、前后端边界 |
| [`05_日志安全部署与运维.md`](05_日志安全部署与运维.md) | 日志、安全、Secret、生产运行怎么定？ | 日志/Secret/Health/Artifact/部署恢复长期边界 |
| [`06_开发约束与分阶段实施.md`](06_开发约束与分阶段实施.md) | 怎么可靠开发和交付？ | Change、TDD、CI、Git、文档同步、验收方法；阶段进度不在这里维护 |
| [`07_技术决策与实施门禁.md`](07_技术决策与实施门禁.md) | 哪些跨模块决定已经拍板？ | 普通任务不能静默改变的技术决定和门禁 |
| [`08_采集策略与平台能力.md`](08_采集策略与平台能力.md) | Collection Plan 怎样决定抓什么？ | Capability、Decision、Detail/Comment、Provider Billing、采集策略 |

新增一个具体业务场景或某个 Provider 细节时，优先放 Appendix/模块 README；不要继续按 `09、10、11...` 扩张 Blueprint。

只有真正出现**新的长期架构领域**，且无法合理归入现有 01—08 时，才通过新的文档治理 Change 调整核心结构。

---

## 3. 原 Blueprint 09—17 去哪里了

原 `09—17` 主要是在 Stage 7、P1、Stage 8 开发过程中形成的详细实现/验证材料。对应阶段已经完成后，这些内容不再继续占用核心 Blueprint。

当前有效事实已经迁移到：

| 原主题 | 当前正式入口 |
| --- | --- |
| Scheduler 运行、Cron、`latest_only`、并发、防重、停机恢复 | [`../appendix/05_Scheduler调度执行与停机恢复.md`](../appendix/05_Scheduler调度执行与停机恢复.md) + Collection README + 04/07/08 |
| TikHub 五平台真实响应、JSON 路径、Mapper、Fixture | [`../appendix/02_TikHub五平台真实响应与字段映射.md`](../appendix/02_TikHub五平台真实响应与字段映射.md) + [`../collection/README.md`](../collection/README.md) |
| TikHub App/Web/V1/V2/V3 验证和备用接口 | [`../appendix/03_TikHub多接口验证与备用策略.md`](../appendix/03_TikHub多接口验证与备用策略.md) |
| TikHub 真实 Probe/接口选型台账 | [`../appendix/04_TikHub接口选型与真实验证台账.md`](../appendix/04_TikHub接口选型与真实验证台账.md) |
| 统一 Excel 数据导出/离线调试 | [`../appendix/06_Excel统一数据导出与离线调试.md`](../appendix/06_Excel统一数据导出与离线调试.md) |
| AI 打标、相关性、发声类型、Validator、Retry、持久化 | [`../appendix/07_AI舆情打标与分析实现.md`](../appendix/07_AI舆情打标与分析实现.md) + `backend/src/aima_ugc/modules/analysis/README.md` + 当前 Prompt |
| 前端页面结构、Figma/Design-to-Code | [`../guides/01_Figma与前端设计开发工作流.md`](../guides/01_Figma与前端设计开发工作流.md) + `frontend/README.md` |
| Stage 8 Excel/TikHub 统一入库、Import Batch、页面/API/Job | [`../appendix/08_数据入口与统一入库实现.md`](../appendix/08_数据入口与统一入库实现.md) + API/Frontend README + Roadmap |

历史阶段为什么这样拆、当时哪些能力尚未实现、当时的验收证据，继续由：

```text
changes/archive/
```

保存。

---

## 4. 未完成阶段去哪看

[`../roadmap/02_生产上线实施路线.md`](../roadmap/02_生产上线实施路线.md)

这是后续持续开发的正式导航，不因 Blueprint 清理而消失。

它必须持续回答：

```text
已经完成什么
部分完成什么
仍待实现什么
哪些旧方案已被后续决定替代
下一最小正式单元是什么
生产 Go-Live 还差什么
```

当前尤其要保留：

- 企业认证 / 后端 Authorization；
- Stage 9 Monitoring / Alert / VOC / Ticket（按产品目标确认）；
- Stage 10 Word 报告是否正式产品化；
- Stage 11 Docker/Compose/Production Config；
- 离线 Release Bundle、固定 image digest、SBOM、来源验证；
- PostgreSQL + Artifact 协调 Backup/Restore；
- 发布、回滚、重启/reboot、容量、安全真实验收；
- Stage 12 旧数据迁移（如果生产上线需要）。

删除已完成阶段的详细 Blueprint **不能**删除这些未来目标。

---

## 5. 按专题去哪看

### PostgreSQL / SQL

[`../appendix/01_PostgreSQL查询与调试实战.md`](../appendix/01_PostgreSQL查询与调试实战.md)

用于：

- 查 Content/Comment Current；
- 查 Version/Metric/Coverage；
- 查 Run/Scope/Request/Attempt；
- 查 Job/Import Batch/Analysis/Export；
- `EXPLAIN`；
- Alembic；
- 安全事务调试。

### Scheduler

[`../appendix/05_Scheduler调度执行与停机恢复.md`](../appendix/05_Scheduler调度执行与停机恢复.md)

### TikHub

- [`../collection/README.md`](../collection/README.md)
- [`../appendix/02_TikHub五平台真实响应与字段映射.md`](../appendix/02_TikHub五平台真实响应与字段映射.md)
- [`../appendix/03_TikHub多接口验证与备用策略.md`](../appendix/03_TikHub多接口验证与备用策略.md)
- [`../appendix/04_TikHub接口选型与真实验证台账.md`](../appendix/04_TikHub接口选型与真实验证台账.md)

### Excel / 数据入口

- [`../appendix/08_数据入口与统一入库实现.md`](../appendix/08_数据入口与统一入库实现.md)
- [`../appendix/06_Excel统一数据导出与离线调试.md`](../appendix/06_Excel统一数据导出与离线调试.md)

### AI

- [`../appendix/07_AI舆情打标与分析实现.md`](../appendix/07_AI舆情打标与分析实现.md)
- `backend/src/aima_ugc/modules/analysis/README.md`

完整 Prompt / taxonomy 唯一业务事实源：

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md
```

### Word Report

[`../appendix/10_Word舆情报告生成与排版实现.md`](../appendix/10_Word舆情报告生成与排版实现.md)

### Figma / Frontend

- [`../guides/01_Figma与前端设计开发工作流.md`](../guides/01_Figma与前端设计开发工作流.md)
- `frontend/README.md`

### Production Release

- [`../roadmap/02_生产上线实施路线.md`](../roadmap/02_生产上线实施路线.md)
- [`../appendix/11_生产部署与离线Release方案.md`](../appendix/11_生产部署与离线Release方案.md)
- [`../02_环境运行与部署.md`](../02_环境运行与部署.md)
- [`05_日志安全部署与运维.md`](05_日志安全部署与运维.md)

---

## 6. 事实优先级

发生冲突时按内容类型判断，不机械“代码优先”或“文档优先”。

```text
本轮用户明确批准决定 / 正式 Change
→ 当前代码、Contract、Migration、generated、tests、locks
→ Blueprint 07 已确认跨模块决定
→ 对应核心 Blueprint 01—08
→ 模块 README / Appendix / Guide / Roadmap
→ 根 README 摘要
→ 历史 Change / 旧聊天
```

两种事实要分开：

```text
当前已经实现什么
→ 必须由机器事实证明

已批准但尚未实现什么
→ Roadmap/正式设计必须保留，不能因为代码还没有就删除
```

如果旧方案已经被后续正式决定替代，例如 Provider Budget Account / Reservation Ledger，则保留历史原因，但当前开发不得从旧 Change 自动恢复该方案。

---

## 7. 当前系统实现边界

### 后端业务模块

```text
system
collection
content
ingestion
analysis
reporting
```

当前没有正式：

```text
monitoring
alerts
voc
tickets
dashboard
```

### Worker 当前持久 Job

真实 Registry：

```text
backend/src/aima_ugc/bootstrap/worker.py
```

当前：

```text
collection.run.v1
ingestion.import-excel.v1
analysis.content-label.v1
reporting.content-export-excel.v1
```

### 当前前端路由

真实 Router：

```text
frontend/src/app/routes.ts
```

当前：

```text
/
/voice-plaza
/collection-runtime
/collection-strategy
```

### 当前生产 Release

仓库当前根目录已经有：

```text
Dockerfile
compose.yaml
env.production.example
```

它们提供 Internal V1-A 的最小可部署容器栈，并把管理员入口收敛为 `env.production` + 一条 Docker Compose 启动命令；PostgreSQL、Artifact、日志与内部 Secret 使用宿主持久目录，Migration/configure 仍保持独立进程边界。

当前仍没有完整 Stage 11 Production Release 所需的全部能力，例如：

```text
compose.production.yaml / 不可变离线 Release Bundle
固定 image digest
SBOM / 签名 / provenance
协调 PostgreSQL + Artifact Backup / Restore
企业认证 / 授权 / HTTPS 正式入口
真实生产服务器完整验收
```

因此“Internal V1-A 已可部署”不能写成“完整 Production Go-Live 已完成”。

---

## 8. Blueprint 写作规则

Blueprint 只回答长期问题：

```text
为什么这样设计？
模块边界是什么？
谁拥有哪类事实？
哪些跨模块机制不能随便改变？
未来实现必须满足什么不变量？
```

不要在 Blueprint 复制：

- 五个平台完整 Provider JSON；
- 39 个 AI 标签表；
- 完整数据库 DDL；
- 完整 HTTP OpenAPI；
- 某次 Stage 的施工顺序和 PR 过程；
- 某个调试脚本的逐行使用说明。

这些内容应分别进入 Appendix、模块 README、Contract/Migration、Guide 或 `changes/archive/`。

文档结构服务于开发，不以“文件少”为目的；但也不允许 Blueprint 随每个业务功能无限增长。
