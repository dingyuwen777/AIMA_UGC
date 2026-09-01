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

- [`docs/roadmap/03_4000万历史数据迁移实施方案.md`](03_4000万历史数据迁移实施方案.md)：**当前历史迁移的正式执行计划**。Internal V1-B 已由业务 Owner 于 2026-08-26 确认完成；Stage 12 统一“导入数据”Campaign（本地电脑/服务器批准目录、标准观测/历史补空）、逐行对账与网页手动 AI Run 的软件实现已经合入 `main` 并通过风险相关 CI。下一门禁是公司服务器容量演练，生产 4000 万执行仍需独立授权。
- [`docs/roadmap/01_内网V1上线实施计划.md`](01_内网V1上线实施计划.md)：公司内网 V1 的已完成路线与边界。服务器验收明细属于外部运行证据；仓库只记录业务 Owner 的完成确认，不补造命令或日志。

当前已经确认的首版范围：

```text
已统一当前前端 / 后端首版功能
→ 页面 enabled/disabled 使用现有正式后端事实形成资格快照，服务端仍最终校验
→ Excel 页面真实导入成功链与 Worker 失败链已有永久 Full-stack Acceptance
→ PostgreSQL / Worker / Voice Plaza 真实打通
→ Excel 与 TikHub 的小红书平台身份统一为 xiaohongshu，并有集成回归
→ 最小可部署容器环境已建立
→ 公司服务器部署与真实业务 Smoke 已由业务 Owner 确认完成
→ 仅公司内部网络访问
→ 当前进入 4000 万历史迁移
```

公司内网 V1 阶段曾明确延期：

```text
登录 / Authentication
角色 / Permission / 权限隔离
旧历史数据迁移（2026-08-26 已由业务 Owner 解除延期，转入 Stage 12）
```

### 固定续接提示词

- [`docs/guides/02_AIMA持续开发与内网上线通用提示词.md`](../guides/02_AIMA持续开发与内网上线通用提示词.md)：在新的 ChatGPT / GitHub Coding Agent 会话中直接复制使用。提示词不会保存当前 SHA、PR 或 Stage 完成状态，而是要求每次读取当前 `main`、Active Change、Roadmap、Contract、代码和测试重新判断下一最小正式单元。

这份提示词用于**启动持续开发工作流**，不是新的事实源。阶段状态仍以本 Roadmap 和当前机器事实为准。

### 长期完整生产路线

- [`docs/roadmap/02_生产上线实施路线.md`](02_生产上线实施路线.md)：Stage 0—12 的长期实施路线、完整 Production Go/No-Go、认证、Release、Backup/Restore、回滚和生产强化。
- [`docs/roadmap/03_4000万历史数据迁移实施方案.md`](03_4000万历史数据迁移实施方案.md)：当前 Stage 12 的自包含开发、测试、容量、部署和实际迁移执行门禁。
- [`docs/roadmap/04_业务目录内容查询与AI配置中心实施路线.md`](04_业务目录内容查询与AI配置中心实施路线.md)：近期先依靠当前 Git Prompt/Taxonomy 文件完成声音广场的动态筛选、列表/详情、人工复核、AI Run、导出和正式验收；车型、管理员配置中心、Analysis Scheme、Facet、第三方状态和消息等作为后期升级路线。
- [`docs/02_环境运行与部署.md`](../02_环境运行与部署.md)：当前开发环境能实际执行的命令，以及部署设计与当前实现差距。
- [`docs/blueprint/05_日志安全部署与运维.md`](../blueprint/05_日志安全部署与运维.md)：日志、安全、Secret、Artifact、备份/恢复和生产运行的长期边界。
- [`docs/blueprint/06_开发约束与分阶段实施.md`](../blueprint/06_开发约束与分阶段实施.md)：每个阶段实际开发时必须遵守的工程流程和质量门禁。
- [`docs/blueprint/07_技术决策与实施门禁.md`](../blueprint/07_技术决策与实施门禁.md)：已经拍板、普通任务不能静默改变的技术决定。

## 当前执行顺序

```text
当前 main
↓
Stage 8F：前后端业务闭环与上线前验收
→ 已完成；精确完成证明必须以对应最终 HEAD 的 CI/Full-stack 结果为准
↓
Internal V1-A：最小 Docker / Compose / Config
→ 已完成
↓
Internal V1-B：公司服务器部署与真实业务 Smoke
→ 业务 Owner 于 2026-08-26 确认完成
↓
公司内网 V1 上线
→ 已完成
↓
Stage 12：4000 万历史数据迁移与手动 AI 打标
→ 软件实现与 Git/CI 已完成；公司服务器容量演练和生产执行待独立授权
↓
后续生产强化 Backlog
↓
完整 Production Go-Live
```

Stage 8F 及其后续持续扩展后的永久业务闭环证据入口：

- [`docs/appendix/09_Stage8F前后端能力矩阵与真实验收.md`](../appendix/09_Stage8F前后端能力矩阵与真实验收.md)
- [`.github/workflows/fullstack.yml`](../../.github/workflows/fullstack.yml)
- [`frontend/e2e-fullstack/excel-import.spec.ts`](../../frontend/e2e-fullstack/excel-import.spec.ts)

上述 Full-stack Acceptance Workflow 是当前唯一永久入口；Stage 8F 后新增的人工相关性与 Stage 12 场景也在同一套 Full-stack 入口继续扩展，不再维护独立 `stage8f-fullstack.yml`。

其中真实 Excel Full-stack Acceptance 固定验证两条链：

```text
成功：
Excel fixture
→ 浏览器上传
→ Import Batch + Job
→ Worker
→ PostgreSQL Content
→ 采集运行中心 succeeded
→ 查看入库内容
→ Voice Plaza 显示本批数据

失败：
结构合法但业务字段非法 Excel
→ 浏览器上传 202
→ Import Batch + Job
→ 正式 Worker
→ failed / invalid_import
→ 页面禁用查看入库内容
→ 显示可审计失败终态且不伪造阶段历史
```

这两条链不 Mock `/api/v1/**`。原有 Mock Playwright E2E 继续保留，负责快速前端交互、enabled/disabled、Drawer/Dialog 和常见错误回归，但不替代真实业务链证明。

## “内网 V1”与“完整 Production”有什么区别

公司内网 V1 是经过明确范围收缩、现已由业务 Owner 确认完成的近期交付里程碑：

```text
公司受控服务器
+ 只允许公司内部网络访问
+ 不做登录和权限隔离
+ 上线时不迁旧历史数据；现已在独立 Stage 12 中启动迁移开发
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

**状态不是靠 Stage 名字判断。** 每次继续开发前仍要从当前分支重新读取 [`AGENTS.md`](../../AGENTS.md)、代码、Migration、Contract、测试和相关 Blueprint。

## 最重要的原则

1. **先闭环真实业务，再容器化。** Stage 8F 的严格门禁同时覆盖真实成功链、真实失败终态和页面业务资格；Internal V1-A 只容器化已经证明可工作的业务链，不重新设计前后端业务。
2. **Mock E2E 不替代 Full-stack Acceptance。** Mock 用于快速前端回归；首版核心 Excel 链使用不 Mock API 的永久真实验收。
3. **前端资格不能替代后端守卫。** 页面可以根据现有正式 API 决定按钮是否可用，但并发、陈旧页面和一致性仍由后端再次校验。
4. **延期和解除延期都必须明确写出来。** 登录/权限仍延期；历史迁移已于 2026-08-26 解除延期并进入独立 Stage 12，不反向改写内网 V1 当时的完成边界。
5. **内网 V1 不等于完整 Production。** 长期 Production 门禁继续保留，不因快速上线被删除。
6. **未完成阶段不能因为文档重构被删掉。** 它们是继续开发到完整生产上线的正式导航。
7. **历史方案不能冒充当前方案。** 后续已经明确改变的设计要保留“为什么改”，同时标注已被替代。
8. **Roadmap 不替代代码事实。** 精确类名、字段、表和 API 仍以当前代码/Contract/Migration 为准。
