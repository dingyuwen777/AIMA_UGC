---
schema: rvc-change/v1
id: CHG-20260822-internal-v1-stage8f-roadmap
title: 内网 V1 前后端闭环与快速上线实施路线
level: L3
status: done
owner: dingyuwen777
branch: docs/internal-v1-stage8f-roadmap-20260822
created: 2026-08-22
updated: 2026-08-22
depends_on: []
affected_areas:
  - roadmap
  - frontend
  - backend_http
  - ingestion
  - deployment
  - security_scope
affected_paths:
  - docs/roadmap
  - frontend
  - backend/src/aima_ugc/bootstrap
  - backend/src/aima_ugc/contracts
  - tests
  - frontend/e2e
contracts: []
data_changes: []
---

# 结果

本 Change 已完成并合并到 `main`。当前近期开发路线正式调整为：

```text
Stage 8F 前后端业务闭环与上线前验收
→ Internal V1-A 最小 Docker / Compose / Config
→ Internal V1-B 公司服务器部署 + 真实业务 Smoke
→ 公司内网 V1 上线
→ 生产强化 Backlog
→ 完整 Production Go-Live
```

本 Change 只调整 Roadmap 与交付边界，没有修改运行时代码、HTTP Contract、Schema、Migration、依赖或现有前端行为。

# 用户已确认的首版边界

2026-08-22 已确认：

```text
首版优先
→ 统一现有前端与后端功能
→ 修复缺失按钮、错误限制、跨页面断链、前后端能力不匹配
→ Excel 可以真实导入并显示数据
→ 部署到公司服务器
→ 只要求公司内部网络访问

首版延期
→ Authentication / 登录
→ Role / Permission / 权限隔离
→ 旧历史数据迁移

后续待办，不作为当前内网 V1 决策前置
→ 正式 RPO / RTO
→ 完整 Retention
→ 正式容量 / 性能 / Soak
→ Coordinated Backup / Restore 完整闭环
→ Release provenance / SBOM / 签名强化
→ Monitoring / Alert / VOC / Ticket
→ Web Report Center
```

延期认证不改变未来身份边界：仍使用 Provider-neutral `Identity / Authentication Adapter → Principal / AuthContext → Authorization`。

# 关键决定

## Stage 8F 是下一业务开发阶段

当前 Stage 8 已存在真实 Contract、Job、PostgreSQL 和 Vue Feature，不重做 Stage 8；下一阶段只系统检查和修复当前首版业务链中的真实缺口。

必须按以下链逐项核对：

```text
业务动作
→ Route / Pydantic Contract
→ OpenAPI / Generated Client
→ Feature api.ts
→ Pinia Store
→ Page / Button
→ Enabled / Disabled 条件
→ Loading / Error / Success
→ 跨页面结果
→ 自动化测试
```

## Full-stack Acceptance 是 Stage 8F 的关键新增门禁

现有三个 Playwright 业务 E2E 都使用 Route Mock，因此不能代替真实全栈证明。

第一条真实验收固定为：

```text
真实 Excel fixture
→ Browser 上传
→ FastAPI
→ Input Artifact
→ Import Batch + PostgreSQL Job
→ Worker
→ PostgreSQL Content
→ Runtime 页面显示完成
→ 查看入库内容
→ Voice Plaza
→ 显示本批导入数据
```

这条测试不能 Mock `/api/v1/**`。

## Internal V1 最小运行门禁

Stage 8F 完成后才进入部署。内网 V1 至少需要：

```text
Dockerfile / Compose / 配置装配
frontend / api / worker / scheduler / migrate / postgres
PostgreSQL 持久目录
Artifact 持久目录
应用日志持久目录
Secret 文件边界
Health / Readiness
Migration 从空库到 head
容器重启后数据不丢
宿主机 reboot 后可以恢复运行
公司内部网络可访问前端
PostgreSQL 不向普通客户端网络暴露
真实 Excel → Worker → PostgreSQL → Voice Plaza Smoke
```

公司内网 V1 不等于完整 Production Security/DR。

# 文档结果

已合并：

- `docs/roadmap/内网V1上线实施计划.md`
- `docs/roadmap/README.md`
- `docs/roadmap/生产上线实施路线.md`

完整 Production 的认证、Backup/Restore、Release、容量、安全等长期门禁仍保留在 Production Roadmap / Appendix 中。

# 验证证据

PR 最终 HEAD：

```text
870c1ad3f35f601067e1ce660f5c8890ad82597c
```

新鲜 GitHub Actions：

```text
CI #1853                                      success
Stage 6 XHS Vertical Slice #1668             success
Stage 7 Keyword Packs #1463                  success
Stage 7 Provider Config Routing #1576        success
Stage 7 Plan Occurrence Run Snapshot #1461   success
Stage 7 Scheduler Runtime #1803               success
```

主 CI 的 Stage 1、Stage 2 Platform、Stage 3A Database、Windows bootstrap 全部成功。

# Git / PR

- PR：#141 `固化 Stage 8F 前后端闭环与内网 V1 上线路线`
- PR 状态：merged
- Merge commit：`b83c112dffd145886c39f437f9df589cd8e0f3e0`
- Change：done，归档至 `changes/archive/2026-08/CHG-20260822-internal-v1-stage8f-roadmap/`
- 发布：本 Change 没有执行运行环境部署
