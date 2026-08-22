---
schema: rvc-change/v1
id: CHG-20260822-reusable-continuation-prompt
title: 固化持续开发与上线通用提示词
level: L2
status: done
owner: dingyuwen777
branch: docs/reusable-continuation-prompt-20260822
created: 2026-08-22
updated: 2026-08-22
depends_on: []
affected_areas:
  - documentation
  - development_workflow
  - roadmap_navigation
affected_paths:
  - docs/guides/AIMA持续开发与内网上线通用提示词.md
  - docs/guides/README.md
  - docs/roadmap/README.md
contracts: []
data_changes: []
---

# 结果

已在仓库中固化一份可以长期复用的持续开发与内网上线提示词：

```text
docs/guides/AIMA持续开发与内网上线通用提示词.md
```

它不是项目状态快照，不保存固定 SHA、PR、分支、CI 或当前 Stage 完成状态；每个新会话都必须从当前 `main`、Active Change、Roadmap、Contract、代码和测试重新恢复事实。

提示词支持持续推进：

```text
Stage 8F 前后端闭环
→ Internal V1-A 最小部署环境
→ Internal V1-B 公司服务器真实部署与 Smoke
→ 公司内网 V1
→ 后续 Production Hardening
```

# 已固化的关键工作流

通用提示词要求每次：

1. 先读 `AGENTS.md` 与 Reliable Vibe Coding Skill；
2. 读取 Blueprint 导航/门禁、Roadmap、代码导航和当前任务机器事实；
3. 检查 `main`、Active Change、开放 PR、CI，未闭环单元优先完成；
4. 默认一次完成一个可独立验收的最小正式单元；
5. Stage 8F 期间按 Route → Contract → OpenAPI/generated → Feature API → Store → Page/Button → 状态 → 跨页面 → Tests 建立能力矩阵并只修真实缺口；
6. 保留 Mock E2E 作为 UI 回归，但公司内网 V1 前必须完成不 Mock `/api/v1/**` 的 Excel Full-stack Acceptance；
7. Stage 8F 真正完成后才进入 Internal V1-A；
8. 真实公司服务器部署不猜服务器地址、凭据或网络事实；
9. 当前最小正式单元最新 HEAD 门禁全绿、PR 可合并且无阻塞 Review 后，可按用户授权通过 PR 合并 `main` 并继续 Change 归档；
10. 每个单元完成后同步 Roadmap，使同一提示词可在下一会话继续使用。

# 首版范围继承

除非未来 `main` 存在更新且已批准的正式决定，提示词继续继承当前公司内网 V1 边界：

```text
首版优先
→ 统一现有前端/后端功能
→ Excel 页面真实导入
→ Job / Worker 真实处理
→ PostgreSQL 保存
→ Voice Plaza 显示
→ 公司服务器
→ 仅公司内部网络访问

首版延期
→ Authentication / 登录
→ Role / Permission / 权限隔离
→ 旧历史数据迁移
```

完整 RPO/RTO、Retention、协调 Backup/Restore、容量/Soak、Release provenance、Monitoring/VOC/Ticket、Web Report Center 等仍保留为后续 Production Hardening。

# 文档结果

新增：

- `docs/guides/AIMA持续开发与内网上线通用提示词.md`

同步导航：

- `docs/guides/README.md`
- `docs/roadmap/README.md`

`AGENTS.md` 不复制整份提示词，仍作为所有 Agent 的统一最高仓库入口；提示词自身强制每次先读取它。

# 验证证据

PR #143 最终 HEAD：

```text
9c613a864a82e84eb89a314bb1fd77a720f5c5b6
```

最终新鲜 Workflow：

```text
CI #1858                                      success
Stage 6 XHS Vertical Slice #1673             success
Stage 7 Keyword Packs #1468                  success
Stage 7 Provider Config Routing #1581        success
Stage 7 Plan Occurrence Run Snapshot #1466   success
Stage 7 Scheduler Runtime #1808               success
```

主 CI 的 Stage 1、Stage 2 Platform、Stage 3A Database、Windows bootstrap 全部成功，覆盖 generated Contract/Client、backend/repository checks、frontend checks、PostgreSQL integration、readiness smoke 和 Migration round-trip。

# 兼容、数据、Migration、部署

本 Change 没有运行时代码、公共 HTTP Contract、Schema、Migration、依赖或生产部署变化。

真实部署仍需后续 Internal V1-A / V1-B 的正式实现和目标服务器真实事实。

# Git / PR

- PR：#143 `固化持续开发与内网上线通用提示词`
- PR 状态：merged
- Merge commit：`c37dc00bcd037861a0ef7769472bf172b68cd70b`
- Change：done，归档至 `changes/archive/2026-08/CHG-20260822-reusable-continuation-prompt/`
