# AIMA_UGC Blueprint 导航

`docs/blueprint/` 只维护**长期有效的系统架构、跨模块边界和已经拍板的技术决策**。它不维护动态 Stage、单次 PR/CI、已完成施工历史，也不承担 Production 操作手册。

## 当前 Blueprint

1. [`docs/blueprint/01_总体架构与技术选型.md`](01_总体架构与技术选型.md)：总体架构、进程、模块、Job、前端类型链和技术基线；
2. [`docs/blueprint/02_采集系统与数据标准化.md`](02_采集系统与数据标准化.md)：Provider、Raw、Candidate、Mapper、Canonical 和统一入库边界；
3. [`docs/blueprint/03_数据库与文件存储.md`](03_数据库与文件存储.md)：PostgreSQL、表 Owner、Artifact、Migration 与存储语义；
4. [`docs/blueprint/04_后端任务API与前端.md`](04_后端任务API与前端.md)：HTTP、持久 Job、前后端 Contract 和长任务交互；
5. [`docs/blueprint/05_日志安全部署与运维.md`](05_日志安全部署与运维.md)：日志、Secret、安全、持久化、Backup/Restore 和 Production 长期边界；
6. [`docs/blueprint/06_开发约束与分阶段实施.md`](06_开发约束与分阶段实施.md)：长期开发/验证/Change/CI 约束，不维护 Stage 完成状态；
7. [`docs/blueprint/07_技术决策与实施门禁.md`](07_技术决策与实施门禁.md)：普通任务不能静默改变的长期决定；
8. [`docs/blueprint/08_采集策略与平台能力.md`](08_采集策略与平台能力.md)：词包、Plan、Capability、Scheduler 和平台采集能力边界。

核心 Blueprint 固定 01—08。Scheduler/TikHub/Excel/AI/Word 等具体实现细节继续放模块 README 或 [`docs/appendix/`](../appendix/)；生产操作放 [`docs/operations/`](../operations/)；不会继续用 Blueprint 09、10、11……记录施工阶段。

## 文档层级

```text
Product
→ 用户现在能做什么

Blueprint
→ 系统为什么这样设计、长期边界是什么

代码结构导航 / 模块 README
→ 当前改代码从哪里开始

Appendix / Collection
→ 专题实现和 Provider 细节

Operations
→ 当前能力怎样部署、运行、恢复、迁移

Roadmap
→ 已批准且尚未完成的目标

Change / Git
→ 历史施工和验收证据
```

完整分层和事实源矩阵见 [`docs/README.md`](../README.md)。

## 读 Blueprint 的正确方式

### 准备修改业务代码

先读根 [`AGENTS.md`](../../AGENTS.md) 和 [`docs/01_代码结构与修改导航.md`](../01_代码结构与修改导航.md)，再按影响面读对应 Blueprint/模块 README。不要从 Blueprint 猜精确 API/表字段。

### 准备修改架构边界

先读 [`docs/blueprint/07_技术决策与实施门禁.md`](07_技术决策与实施门禁.md)。如果任务会改变模块拆分、Canonical、Content 身份、表 Owner、Job Runtime、Scheduler、认证、Backup/Restore 等长期决定，必须按高风险 Change 处理。

### 准备部署或生产迁移

- 当前操作：[`docs/operations/`](../operations/)；
- 尚未完成的 Production 门禁：[`docs/roadmap/02_生产上线实施路线.md`](../roadmap/02_生产上线实施路线.md)；
- 尚未完成的 4000 万生产执行：[`docs/roadmap/03_4000万历史数据迁移实施方案.md`](../roadmap/03_4000万历史数据迁移实施方案.md)。

## 精确机器事实不在 Blueprint 复制第二份

以下内容直接回到机器事实：

- 精确依赖版本 → lock/version 文件；
- HTTP 字段和路径 → Pydantic/FastAPI/OpenAPI；
- 数据库列/约束 → SQLAlchemy/Migration；
- 前端 Route → [`frontend/src/app/routes.ts`](../../frontend/src/app/routes.ts)；
- generated Client → OpenAPI/Orval 生成链；
- Worker Registry → [`backend/src/aima_ugc/bootstrap/worker.py`](../../backend/src/aima_ugc/bootstrap/worker.py)；
- Provider JSON → Sanitized Fixture/Operation/Mapper。

Blueprint 负责解释**边界和原因**，机器事实负责精确值。
