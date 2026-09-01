# AIMA_UGC 持续开发与内网上线通用提示词

本文提供一份可以在未来 ChatGPT / GitHub Coding Agent 新会话中**反复复制使用**的固定入口提示词。

它解决的问题不是“把今天的项目状态复制到下一次对话”，而是：

> 每次新会话都让 Agent 从 GitHub 当前真实状态重新判断项目做到哪里，然后继续当前下一最小正式单元，直到公司内网 V1 上线，并继续后续 Production Hardening。

因此这份提示词刻意**不保存**：

```text
当前 main SHA
当前 PR 号码
当前工作分支
“现在一定在 Stage 8F”
某一次 CI Run 编号
```

这些都是会变化的运行事实，必须由 GitHub 当前状态重新读取。

长期路线由：

- [`docs/roadmap/01_内网V1上线实施计划.md`](../roadmap/01_内网V1上线实施计划.md)
- [`docs/roadmap/02_生产上线实施路线.md`](../roadmap/02_生产上线实施路线.md)

维护。

---

# 1. 推荐直接复制的通用提示词

下面整段可以在新的网页对话中直接使用。

```text
@GitHub

你现在负责持续开发 GitHub 仓库：

    dingyuwen777/AIMA_UGC

目标不是根据本提示词猜“现在做到 Stage 几”，而是基于仓库当前真实状态，沿仓库正式 Roadmap 持续完成下一最小正式开发单元，逐步实现：

    前后端真实业务闭环
    → 公司内网 V1 可部署
    → 公司服务器真实部署与业务 Smoke
    → 公司内网 V1 上线
    → 后续 Production Hardening

本提示词是固定入口，不是项目事实副本。
不要相信本提示词中的任何历史 SHA、PR、分支、CI、Stage 完成状态；每个新会话必须从当前 GitHub 重新恢复事实。

==================================================
一、开始前必须重新恢复仓库当前事实
==================================================

按顺序执行：

1. 读取当前目标分支根目录 `AGENTS.md`；
2. 使用当前宿主实际可用的 GitHub/仓库读取能力读取 `dingyuwen777/Agent_Skills` 当前默认分支 canonical 源码：先读根 `AGENTS.md`，再按当前源码导航读取 ENTRY、Router、命中的 `SKILL.md` 与 required References；不得把 AIMA 本地 `.agents` 安装副本、Runtime、Release、缓存或历史聊天当作 canonical；
3. 按当前 canonical Skill 判断本轮任务等级和 Change 要求，同时继续遵守 AIMA 自己的项目 Overlay；
4. 读取：
   - `docs/blueprint/README.md`
   - `docs/blueprint/07_技术决策与实施门禁.md`
   - `docs/roadmap/README.md`
   - `docs/roadmap/01_内网V1上线实施计划.md`
   - `docs/roadmap/02_生产上线实施路线.md`
   - `docs/01_代码结构与修改导航.md`
5. 检查当前 `main` 最新 commit；
6. 检查 `changes/active/`；
7. 检查与当前路线直接相关的开放 PR、分支和最新 CI；
8. 按 Roadmap 导航，只读取当前任务直接相关的前端、后端、Contract、Generated Client、Migration、依赖、测试、配置、README、Appendix；
9. 以当前代码、Pydantic Contract、OpenAPI/generated、Migration、tests、locks 为精确机器事实；
10. 不从历史聊天、旧 Change、本提示词或 Roadmap 的一句状态描述猜当前实现。

如果 `AGENTS.md`、Skill 或当前任务关键事实源无法读取，必须明确指出，不能假装已经遵守。

==================================================
二、先判断“现在真正应该继续哪个单元”
==================================================

不要机械从 Stage 编号向后跳。

判断规则：

1. 如果存在与当前路线对应的 Active Change：
   → 先读取并判断它是否仍是当前未闭环工作；
   → 是的话继续这个 Change，不创建平行 Change；

2. 如果上一个最小正式单元已有代码但 PR 未合并、CI 未通过、文档未同步或 Change 未闭环：
   → 先完成它；
   → 不进入后续单元；

3. 如果上一个单元已经真实闭环：
   → 从 `docs/roadmap/01_内网V1上线实施计划.md` 和 `docs/roadmap/02_生产上线实施路线.md` 判断下一最小正式单元；

4. 当前近期路线的业务顺序原则是：

   Stage 8F 前后端业务闭环与上线前验收
   → Internal V1-A 最小 Docker / Compose / Config
   → Internal V1-B 公司服务器部署与真实业务 Smoke
   → 公司内网 V1 上线
   → Stage 12 4000 万历史数据迁移与手动 AI 打标
   → 后续 Production Hardening

   但这只是路线顺序；是否已经完成某一步，必须重新由当前 main 的代码、测试、PR 和 CI 证明。

==================================================
三、当前已批准的公司内网 V1 产品边界
==================================================

除非当前 `main` 中存在更新且已批准的正式决定，否则继承以下边界：

首版优先：

- 统一当前已经存在的前端和后端功能；
- 修复缺失按钮、错误 disabled/限制、跨页面断链、前后端 Contract/功能不匹配；
- Excel 必须可以从真实页面导入；
- Import Job / Worker 必须真正执行；
- 数据必须进入 PostgreSQL；
- 导入的数据必须能在声音广场正确查询和显示；
- 首版部署到公司服务器；
- 只允许公司内部网络访问，不对公网开放。

公司内网 V1 阶段曾明确延期：

- 登录 / Authentication；
- Role / Permission / 权限隔离；
- 旧历史数据迁移（2026-08-26 已解除延期，按独立 Stage 12 实施）。

以下保留为内网 V1 后的 Production Hardening，不因为“Stage 编号靠前”自动阻塞当前内网 V1：

- 正式 RPO / RTO；
- 完整 Retention Policy；
- Coordinated PostgreSQL + Artifact Backup / Restore 完整闭环；
- 正式容量 / 性能 / Soak；
- Release digest / SBOM / 签名 / provenance 强化；
- 完整 Disaster Recovery / rollback；
- Monitoring / Alert / VOC / Ticket；
- Web Report Center；
- 公网或公司网络之外的访问能力。

注意：

“内网 V1 可以延期认证/完整灾备”
不等于
“内网天然安全”或“完整 Production 已经达标”。

扩大访问范围、需要用户权限、具体操作人审计或更高数据风险时，再按正式 Roadmap 进入对应高风险 Change。

==================================================
四、Stage 8F 的执行原则
==================================================

如果当前仍处于 Stage 8F，不重做 Stage 8，也不要一次性重写全部前端。

先基于当前代码建立真实“前后端能力矩阵”，每个首版业务动作逐项核对：

    业务动作
    → FastAPI Route
    → Pydantic Contract
    → OpenAPI
    → Generated Client
    → Feature api.ts
    → Pinia Store / local state
    → Page / Button
    → Enabled / Disabled 条件
    → Loading / Error / Success
    → 跨页面结果
    → 自动化测试

至少分类：

- 已完整闭环；
- 有后端能力但无前端入口；
- 有前端入口但后端不支持；
- 按钮或 disabled 条件错误；
- 状态/轮询/错误反馈不一致；
- 跨页面断链；
- 测试只验证 Mock；
- 明确不属于首版。

重点覆盖当前首版业务面：

1. 采集运行中心
   - Excel Upload；
   - Import Batch / Job；
   - queued/running/succeeded/failed；
   - Batch Detail；
   - Batch → Voice Plaza；
   - TikHub 手工 Run 当前真实 Capability/状态；

2. 采集策略
   - Keyword Pack；
   - Relevance Config；
   - Collection Plan；
   - 启停、配置和 Scheduler 语义；

3. 声音广场
   - Content List / Detail；
   - 搜索、平台、内容类型、时间、来源筛选；
   - Analysis current/stale/pending；
   - AI Analysis Job；
   - Excel Export Job / Artifact / Download；

4. App Shell / Navigation
   - 首版真实路由必须合理可达；
   - 未来能力不能表现成像系统故障一样的死按钮。

发现问题时：

- 后端 Contract 正确 → 修 Feature / Store / Page；
- 后端 Contract 确有缺口 → 按 Pydantic → Route/Service → API/Contract Test → OpenAPI → Generated Client → Frontend 的完整链修改；
- 禁止手改 `frontend/src/generated/api/`；
- 禁止在 Vue 复制第二套后端业务过滤/状态规则来掩盖后端错误；
- 禁止为了页面方便破坏 Canonical、Content Owner、Job Runtime 等既有边界。

==================================================
五、Stage 8F 的真实 Full-stack 验收门禁
==================================================

保留现有 Mock Playwright E2E 做快速 UI 回归，但 Mock E2E 不能证明真实业务闭环。

公司内网 V1 前必须至少有一条真实 Full-stack Acceptance：

    真实 Excel fixture
    → Browser 上传
    → Vue
    → FastAPI
    → Input Artifact
    → Import Batch + PostgreSQL Job
    → Worker
    → Excel Reader / Mapper / Ingestion
    → PostgreSQL Content
    → 采集运行中心显示完成
    → 打开 Batch
    → 查看入库内容
    → Voice Plaza
    → 显示本批导入数据

要求：

- 不 Mock `/api/v1/**`；
- 使用隔离 PostgreSQL；
- 使用真实生产 Import Reader / Mapper / Ingestion；
- 使用测试 Excel Fixture；
- 普通 CI 不调用真实付费 TikHub/LLM；
- TikHub/LLM 状态验证继续使用仓库已有 Fixture/Fake/隔离边界；
- 测试结束清理隔离数据。

Stage 8F 完成必须以当前代码和新鲜测试证据证明，不能只改 Roadmap 状态。

==================================================
六、进入 Internal V1-A 后怎么做
==================================================

只有 Stage 8F 真正闭环后才进入部署实现。

Internal V1-A 是公司内网 V1 的最小可部署闭环，复用长期 Production 设计但不提前实现所有 Hardening。

至少需要验证并实现当前 Roadmap 要求的：

- 根目录 Docker build context；
- Dockerfile；
- Compose；
- frontend / api / worker / scheduler / migrate / postgres；
- PostgreSQL 持久目录；
- Artifact 持久目录；
- 应用日志持久目录；
- Secret 文件只读装配；
- Health / Readiness；
- 空库 Migration 到 head；
- PostgreSQL 不暴露给普通公司客户端网络；
- API / Worker / Scheduler 共享正确配置事实；
- 容器重启后业务数据不丢。

具体文件名、镜像版本、配置字段、目录和命令以实现时当前仓库正式文档、锁文件、Settings 和镜像事实重新确认，不能从历史提示词复制旧值。

==================================================
七、Internal V1-B 完成确认与 Stage 12 续接
==================================================

Internal V1-B 已由业务 Owner 于 2026-08-26 确认完成。新会话不得重做 V1-B；仓库没有服务器命令、日志或截图时，也不得补造详细证据。以下内容保留为 V1-B 验收边界和后续部署复核参考。

目标：

    公司服务器
    + 公司内部网络
    + 不对公网开放

只有在当前工具环境和仓库/受控配置中能够确认目标服务器、部署方式和所需凭据时才实际部署。

不能猜：

- 服务器 IP / hostname；
- SSH 账户；
- 密码 / Key；
- 公司网络 ACL；
- Secret 值。

如果这些外部事实无法从当前可用事实源确认：

- 先完成所有仓库内可完成的代码、部署脚本、文档、Release/Compose 验证；
- 明确列出唯一剩余外部阻塞；
- 不伪造“已经部署成功”。

真实服务器最低 Smoke 以当前 Roadmap 为准，至少应覆盖：

    浏览器访问
    /health/live
    /health/ready
    migrate 到 head
    api / worker / scheduler 运行
    页面导入测试 Excel
    Job queued → running → succeeded
    Batch 统计
    Batch → Voice Plaza
    Content Detail
    容器重启后数据仍存在
    宿主机 reboot 后按设计恢复

当前“AIMA_UGC 公司内网 V1 已上线”的状态来自业务 Owner 完成确认。当前下一正式单元必须读取 `docs/roadmap/03_4000万历史数据迁移实施方案.md` 和对应 Active Change；开发授权不自动包含生产 4000 万写入授权。

==================================================
八、每个会话的工作粒度
==================================================

默认每个新会话只完成一个“当前最小正式开发单元”。

例如：

- Stage 8F 如果正式 Roadmap/Change 已拆成 A/B/C，则一次完成当前一个可独立验收单元；
- 如果没有进一步拆分，则按当前 Change 中可以独立验收的纵切完成，不为了控制对话长度制造没有业务价值的子阶段；
- Internal V1-A 和 V1-B 分开验收；
- Stage 12 依次完成历史只补空值写策略、Campaign/目录/分片、手动 AI Run、容量与恢复门禁；
- 上一个单元没有真正闭环时，不跳下一个。

本轮任务一旦确定：

1. 创建或认领一个适用 Active Change；
2. 明确目标、成功标准、范围、非目标、不变项、验证、部署和回滚；
3. 只读取直接相关实现和事实源；
4. 开发行为变化时按 Skill 执行 Red → Green → Refactor；
5. 完成目标测试、相关回归、类型/静态检查、构建和需要的真实 Integration/Browser 验证；
6. 同步受影响正式文档；
7. 两阶段 Review：需求符合性 + 代码质量；
8. 创建/更新 PR；
9. 以 PR 最新 HEAD 的新鲜 CI 为合并门禁。

==================================================
九、Git / PR / 合并授权
==================================================

使用本提示词时，我明确授权你对“当前最小正式开发单元”执行以下 Git 交付动作：

- 创建工作分支；
- 创建/更新当前 Change；
- Commit；
- Push；
- 创建或更新 PR；
- 修复当前 PR 中发现的问题；
- 等待并检查最新 HEAD 的 CI；
- 在满足仓库质量门禁、PR mergeable、没有未解决严重/重要 Review 问题后，通过 PR 合并到 `main`；
- 合并后按仓库 Change 规则把已完成 Change 移到 `changes/archive/`，并通过正常 PR/CI 合并归档收尾。

不需要在每个单元完成后再次询问“是否可以 merge”。

但不得：

- 直接绕过 PR 写 `main`；
- force push；
- 绕过 Branch Protection；
- 删除/跳过失败测试；
- 降低 lint/typecheck/security/docs 门禁；
- 用临时兼容 hack 伪造成功；
- 因为本提示词授权 merge 就自动授权不可逆生产数据操作。

真实公司服务器上的不可逆数据操作只在对应软件能力、容量和恢复门禁满足，当前工具确实能访问目标环境，并获得本轮显式生产写授权时执行。Stage 12 的代码开发、测试或合并授权不自动授权 4000 万全量迁移。

==================================================
十、用户决策门禁
==================================================

不要重复询问已经被当前 main 正式文档固化的决定。

如果出现新的、仓库无法确认、会实质改变以下内容的上游问题：

- 公共 Contract；
- Schema / Migration；
- 权限/安全语义；
- 隐私/保留/删除；
- Provider/费用；
- 调度；
- SLO / RPO / RTO；
- 不可逆数据行为；
- 公司内网 V1 的产品验收边界；

按 `AGENTS.md` 用户决策门禁：

1. 先把能从代码/仓库/官方事实确认的内容查清；
2. 给明确推荐和必要备选；
3. 只有真正需要业务 Owner 决定时才提问；
4. 决定后同步正式文档/Change/Contract/Schema；
5. 未决定前暂停依赖该决定的高风险实现，但继续完成不依赖它的工作。

==================================================
十一、每个单元完成后必须更新路线事实
==================================================

完成后必须重新检查：

- `docs/roadmap/01_内网V1上线实施计划.md`
- `docs/roadmap/02_生产上线实施路线.md`
- 对应模块 README / Appendix / API / 环境部署说明

如果当前单元已经改变项目“现在做到哪里”，必须在同一交付中同步 Roadmap。

这样下一次使用本提示词时，Agent 能仅依赖当前 main 自动继续，而不需要用户重新解释历史。

==================================================
十二、完成报告格式
==================================================

每个会话结束时至少报告：

1. 本轮开始时确认的 main / Active Change / PR 真实状态；
2. 本轮实际完成的最小正式单元；
3. 修复/新增的主要业务闭环；
4. 修改的关键代码/Contract/Migration/前端/测试/文档；
5. 实际执行的测试和结果；
6. PR 最新 HEAD 与 CI 状态；
7. 是否已合并 main、实际 merge commit；
8. Change 是否已归档；
9. 当前距离公司内网 V1 还差什么；
10. 下一最小正式开发单元是什么。

如果某项没有执行，明确写“未执行”；不要推测成功。

==================================================
十三、最终目标
==================================================

不要以“代码写完”“页面能打开”“Mock E2E 通过”或“Docker 容器启动”作为最终完成标准。

近期最终里程碑是：

    公司内网真实用户可以访问
    + Excel 从页面真实导入
    + Worker 真实处理
    + PostgreSQL 保存数据
    + 声音广场真实显示
    + 基本持久化/Secret/Health/重启恢复成立

达到后才能声明：

    AIMA_UGC 公司内网 V1 已上线

之后继续按 `docs/roadmap/02_生产上线实施路线.md` 的 Production Hardening 路线推进完整 Production Go-Live。
```

---

# 2. 为什么这份提示词可以长期复用

它把信息分成两类。

## 不放进提示词的易变事实

```text
SHA
PR number
branch
CI run
当前某个 Stage 是否已经完成
当前代码文件是否仍存在
```

这些每次从 GitHub 重新查。

## 放进提示词的稳定工作方式

```text
先读 AGENTS
按 Roadmap 判断下一单元
机器事实优先
未闭环不跳阶段
Change → 开发 → 测试 → 文档 → PR → CI → merge → archive
Mock E2E 不冒充真实 Full-stack
部署必须有真实服务器事实
```

所以即使未来 Stage 8F 已完成、Docker 已完成、项目已经进入 Production Hardening，同一份提示词仍然可以继续使用。

---

# 3. 这份提示词给了什么 Git 授权

为了避免每个新会话完成后都停在“PR 已 Ready，等你说 merge”，提示词包含了一项明确授权：

> 当前最小正式单元在最新 HEAD 的仓库门禁全部成功、PR 可合并、Review 无阻塞后，可以直接通过 PR 合并 `main`，并继续完成 Change 归档。

这个授权不等于：

- 可以直接 push `main`；
- 可以 force push；
- 可以跳过 CI；
- 可以删除失败测试；
- 可以自动执行任意生产数据破坏操作；
- 可以猜公司服务器凭据。

---

# 4. 到真实部署阶段仍可能需要什么外部事实

通用提示词可以驱动仓库一直开发到可部署，但真实公司服务器部署最终仍依赖当时可获得的外部事实，例如：

```text
目标服务器地址
SSH / 受控部署入口
公司网络访问方式
实际 Secret
```

如果这些信息已经在当时可用的受控配置/连接中，Agent 应按正式部署流程继续；如果当前工具不可访问，则不能假装完成真实部署。

关键原则是：

> 能由仓库完成的全部先完成；只有真正的外部环境事实才成为最后阻塞。

---

# 5. 维护规则

这份提示词本身应保持稳定。

以下变化通常只需要更新 Roadmap，不需要修改通用提示词：

- Stage 8F 完成；
- 进入 Internal V1-A；
- Docker/Compose 文件已存在；
- 内网 V1 已上线；
- 进入 Production Hardening；
- 新增具体 Feature。

只有以下情况才需要改这份提示词：

- 仓库统一开发流程发生变化；
- `AGENTS.md` / Reliable Vibe Coding 的核心门禁改变；
- Roadmap 事实源路径改变；
- 用户改变“一次完成一个最小正式单元”的工作方式；
- Git 合并授权边界改变。

这样可以避免“提示词版本”和“代码版本”长期同步的额外维护负担。
