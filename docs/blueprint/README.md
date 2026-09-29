# AIMA_UGC Blueprint 导航

docs/blueprint/ 只维护**长期有效的系统架构、跨模块边界、项目工程基线和已经拍板的技术决策**。

它不承担 Agent_Skills 的通用研发方法、动态 Stage/PR/CI、Production 操作步骤或精确机器事实镜像。

## 当前 Blueprint

1. [docs/blueprint/01_总体架构与技术选型.md](01_总体架构与技术选型.md)：系统形态、进程、模块、持久 Job、前端类型链和技术基线；
2. [docs/blueprint/02_采集系统与数据标准化.md](02_采集系统与数据标准化.md)：Provider、Raw/Input Artifact、Candidate、Mapper、Canonical 与统一入库长期边界；
3. [docs/blueprint/03_数据库与文件存储.md](03_数据库与文件存储.md)：PostgreSQL、表 Owner、Version/Metric、Artifact、Migration 与存储语义；
4. [docs/blueprint/04_后端任务API与前端.md](04_后端任务API与前端.md)：HTTP、持久 Job、前后端 Contract 与长任务交互；
5. [docs/blueprint/05_日志安全部署与运维.md](05_日志安全部署与运维.md)：日志、Secret、安全、持久化、Backup/Restore 与长期运行边界；
6. [docs/blueprint/06_开发约束与分阶段实施.md](06_开发约束与分阶段实施.md)：AIMA 如何把 Agent_Skills 治理映射到本仓库的 Requirement / Change / CI / Docs / Delivery 接线；
7. [docs/blueprint/07_技术决策与实施门禁.md](07_技术决策与实施门禁.md)：普通任务不能静默改变的长期技术决定；
8. [docs/blueprint/08_采集策略与平台能力.md](08_采集策略与平台能力.md)：采集策略、Platform Capability、Operation 与评论补采的长期模型。

## 文档层级

~~~text
为什么采用这个长期边界
→ Blueprint

精确实现是什么
→ Code / Contract / Schema / Migration / Test / CI

某个平台/专题怎样实现和排障
→ Collection / Appendix

现在怎么运行
→ Operations / Guides

下一步已批准但未完成什么
→ Roadmap
~~~

## 读 Blueprint 的正确方式

不要先把 8 篇全部读完。

- 理解全局形态：先读 [docs/blueprint/01_总体架构与技术选型.md](01_总体架构与技术选型.md)；
- 修改某条业务链：只进入承担该边界的对应 Blueprint，再读真实代码和测试；
- 研发交付：项目入口仍是 [AGENTS.md](../../AGENTS.md)，本目录只补 AIMA 的工程接线和长期决定；
- 历史原因：去 [changes/archive/](../../changes/archive/) 与 Git。

## 精确机器事实不在 Blueprint 复制第二份

Blueprint 可以解释为什么需要某种 Contract / Table / Job / Route，但精确集合继续由机器 Owner 持有。已有机器事实时，优先链接和解释，不维护平行清单。
