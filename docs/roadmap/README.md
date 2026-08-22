# AIMA_UGC 开发与上线 Roadmap

这个目录回答两个不同层级的问题：

> **当前代码下一步应该继续开发什么，怎样先形成公司内网可用的 V1？**
>
> **内网 V1 之后，还要补哪些能力才能达到完整 Production Go-Live？**

这两个里程碑现在必须明确区分，不能再把“公司内部先用起来”和“完整生产安全/灾备闭环”混成同一套门禁。

它与 Blueprint 的区别：

```text
Blueprint
→ 系统应该怎样设计、边界为什么这样定

Roadmap
→ 按什么顺序把尚未完成的设计继续实现、验收到内网 V1 和完整 Production

Appendix / Module README
→ 某个专题或模块当前具体怎样实现、怎样调试

Change / changes/archive
→ 某次变更为什么发生、当时怎么验证
```

## 当前执行入口

### 近期第一优先级

- [`内网V1上线实施计划.md`](内网V1上线实施计划.md)：**当前近期开发的正式执行计划**。先完成 Stage 8F 前后端业务闭环，再做公司服务器最小部署与真实 Excel Smoke。

当前已经确认的首版范围：

```text
先统一当前前端 / 后端功能
→ Excel 页面导入必须真实闭环
→ PostgreSQL / Worker / Voice Plaza 必须真实打通
→ 部署到公司服务器
→ 仅公司内部网络访问
```

首版明确延期：

```text
登录 / Authentication
角色 / Permission / 权限隔离
旧历史数据迁移
```

### 长期完整生产路线

- [`生产上线实施路线.md`](生产上线实施路线.md)：Stage 0—12 的长期实施路线、完整 Production Go/No-Go、认证、Release、Backup/Restore、回滚和生产强化。
- [`../环境运行与部署.md`](../环境运行与部署.md)：当前开发环境能实际执行的命令，以及部署设计与当前实现差距。
- [`../blueprint/05-日志安全部署与运维.md`](../blueprint/05-日志安全部署与运维.md)：日志、安全、Secret、Artifact、备份/恢复和生产运行的长期边界。
- [`../blueprint/06-开发约束与分阶段实施.md`](../blueprint/06-开发约束与分阶段实施.md)：每个阶段实际开发时必须遵守的工程流程和质量门禁。
- [`../blueprint/07-技术决策与实施门禁.md`](../blueprint/07-技术决策与实施门禁.md)：已经拍板、普通任务不能静默改变的技术决定。

## 当前执行顺序

```text
当前 main
↓
Stage 8F：前后端业务闭环与上线前验收
↓
Internal V1-A：最小 Docker / Compose / Config
↓
Internal V1-B：公司服务器部署与真实业务 Smoke
↓
公司内网 V1 上线
↓
后续生产强化 Backlog
↓
完整 Production Go-Live
```

Stage 8F 完成前，不应该因为“后端已有 API、前端已有页面”就直接进入部署。

当前前端 Playwright 测试中存在 Mock API E2E，因此页面自动化通过本身不能证明真实：

```text
Vue
→ FastAPI
→ PostgreSQL Job
→ Worker
→ PostgreSQL
→ Vue
```

已经闭环。当前最重要的 Full-stack Acceptance 固定为：

```text
Excel fixture
→ 浏览器上传
→ Import Batch + Job
→ Worker
→ PostgreSQL Content
→ 采集运行中心显示结果
→ 查看入库内容
→ Voice Plaza 显示本批数据
```

## “内网 V1”与“完整 Production”有什么区别

公司内网 V1 是经过明确范围收缩的近期交付里程碑：

```text
公司受控服务器
+ 只允许公司内部网络访问
+ 不做登录和权限隔离
+ 不迁旧历史数据
+ 先保证业务链、持久化、Health、Secret、重启恢复和 Excel Smoke
```

这不代表：

```text
内网天然安全
认证已经不需要
Backup/Restore 已完成
完整灾备/容量/安全已经验收
```

完整 Production 仍需要按长期路线补齐认证授权、正式 RPO/RTO、协调 Backup/Restore、完整 Release/rollback、安全与容量验收等能力。

## 状态怎么读

Roadmap 使用四种状态：

```text
已完成
→ 当前代码、Contract/Migration/测试可以证明主要目标已经闭环

部分完成
→ 原阶段的一部分已经正式实现，但仍有明确剩余工作

待实现
→ 设计仍有效，但当前代码尚未落地

已被后续决策替代
→ 历史方案保留用于理解演进，但不能照旧继续开发
```

**状态不是靠 Stage 名字判断。** 每次继续开发前仍要从当前分支重新读取 `AGENTS.md`、代码、Migration、Contract、测试和相关 Blueprint。

## 最重要的原则

1. **先闭环真实业务，再容器化。** 页面、按钮、Contract、Generated Client、Worker、PostgreSQL 和跨页面结果必须真实一致。
2. **Mock E2E 不替代 Full-stack Acceptance。** Mock 用于快速前端回归；首版核心业务必须至少有一条不 Mock API 的真实链。
3. **允许延期必须明确写出来。** 当前登录/权限和历史迁移延期是已确认产品决定，不由后续 Agent 擅自恢复为内网 V1 阻塞项。
4. **内网 V1 不等于完整 Production。** 长期 Production 门禁继续保留，不因快速上线被删除。
5. **未完成阶段不能因为文档重构被删掉。** 它们是继续开发到完整生产上线的正式导航。
6. **历史方案不能冒充当前方案。** 后续已经明确改变的设计要保留“为什么改”，同时标注已被替代。
7. **Roadmap 不替代代码事实。** 精确类名、字段、表和 API 仍以当前代码/Contract/Migration 为准。
