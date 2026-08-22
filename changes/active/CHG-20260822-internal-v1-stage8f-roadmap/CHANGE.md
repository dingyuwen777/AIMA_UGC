---
schema: rvc-change/v1
id: CHG-20260822-internal-v1-stage8f-roadmap
title: 内网 V1 前后端闭环与快速上线实施路线
level: L3
status: ready_for_review
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

# 目标

基于当前 `main` 的 Stage 8、Vue 页面、HTTP Contract、Generated Client、Worker、PostgreSQL 和测试事实，重新确定近期开发路线：

1. 先把当前已经存在的前端和后端功能真正闭环；
2. 首版最关键端到端验收固定为“Excel 页面导入 → Worker → PostgreSQL → 声音广场显示”；
3. 前后端闭环后，再部署到公司服务器，仅允许公司内部网络访问；
4. 登录/权限隔离、旧历史数据迁移和完整生产强化能力明确延期；
5. 区分“公司内网 V1 上线”和“完整 Production Go-Live”，不删除长期生产门禁。

本 Change 只修改 Roadmap/Change，不修改运行时代码、HTTP Contract、Schema、Migration、依赖或现有前端行为。

# 用户已确认的上游决策

2026-08-22 用户明确确认：

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

可列入后续待办，不作为当前内网 V1 决策前置
→ 正式 RPO / RTO
→ 完整 Retention
→ 正式容量 / 性能 / Soak
→ Coordinated Backup / Restore 完整闭环
→ Release provenance / SBOM / 签名强化
→ Monitoring / Alert / VOC / Ticket
→ Web Report Center
```

延期认证不改变长期身份边界：未来仍使用 Provider-neutral `Identity / Authentication Adapter → Principal / AuthContext → Authorization`，业务模块不绑定飞书或其他 Provider 私有身份。

# 当前机器事实与问题证据

## Stage 8 已存在的业务入口

当前路由：

```text
/
/voice-plaza
/collection-runtime
/collection-strategy
```

当前页面已经承接：

```text
采集运行中心
→ Excel Import / TikHub Run / 运行列表 / 摘要 / 详情

采集策略
→ Keyword Pack / Relevance Config / Collection Plan

声音广场
→ Content 查询 / 详情 / 筛选 / AI Analysis / Excel Export
```

正式 Excel 主链已经存在：

```text
Vue
→ POST /api/v1/import-batches
→ Input Artifact
→ processing_import_batches
→ ingestion.import-excel.v1 Job
→ Worker
→ Excel Reader / Mapper
→ Canonical
→ Relevance
→ ContentIngestionService
→ PostgreSQL
→ GET /api/v1/contents
→ Voice Plaza
```

## 当前测试缺口

三个当前前端 Playwright 业务 E2E 都使用 HTTP Route Mock：

```text
collection-runtime.spec.ts
collection-strategy.spec.ts
voice-plaza.spec.ts
```

其中采集运行中心和采集策略直接 `page.route('**/api/v1/**')`；声音广场也对 `/api/v1/contents**` 等真实业务接口进行 Route Mock。

所以当前 E2E 可以证明页面交互，但不能证明：

```text
真实 Vue
→ FastAPI
→ PostgreSQL Job
→ Worker
→ PostgreSQL
→ Vue
```

完整闭环。

## 已确认的具体前端一致性缺口

当前：

```text
routes.ts
→ `/` 首页真实存在

HomeView.vue
→ 复用 CollectionRuntimePage

AppShell.vue
→ “首页”却是 disabled
```

这证明当前正确工作单元应是系统性前后端闭环，而不是直接容器化或零散补按钮。

# 方案比较与决定

## A. 直接进入 Stage 11A

优点：最快看到服务器页面。

问题：会把当前前后端缺口一起封装进容器；Mock E2E 仍无法证明核心 Excel 真实业务链。

不采用。

## B. 重做 Stage 8

优点：可以全面返工。

问题：当前 Contract、Job、PostgreSQL 和三套 Vue Feature 已有大量真实实现，会重复已完成基础并扩大范围。

不采用。

## C. 新增 Stage 8F，再做内网 V1 部署

```text
Stage 8F 前后端业务闭环与上线前验收
→ Internal V1-A 最小 Docker / Compose / Config
→ Internal V1-B 公司服务器部署 + 真实业务 Smoke
→ 公司内网 V1 上线
→ 生产强化 Backlog
→ 完整 Production Go-Live
```

**采用方案 C。**

# Stage 8F：下一最小正式开发阶段

Stage 8F 不是重做 Stage 8，而是建立当前能力矩阵并只修真实缺口。

每个首版业务动作都按以下链核对：

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

## 采集运行中心

至少闭环：Excel 上传、Import Batch + Job、状态、Batch 详情、TikHub Run Capability/创建/详情，以及 Batch → Voice Plaza 来源过滤。

## 采集策略

至少闭环：Keyword Pack 新建/查看/关键词维护/启停、Relevance Config、Collection Plan 新建/查看/启停，并保证页面语义与后端一致。

## 声音广场

至少闭环：Content 列表/详情/筛选、Batch/Run 来源、AI Analysis 创建与 Job 状态、Excel Export 创建/状态/下载。

## App Shell

首版真实路由要可达；未来能力不做成像故障一样的死按钮。`/` 与 `/collection-runtime` 的产品关系需要在 Stage 8F 明确并修正导航。

# Stage 8F 测试门禁

保留现有 Mock Browser E2E 作为快速 UI 回归，同时新增真实 Full-stack Acceptance。

第一条必须固定为：

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

普通 CI 不调用真实付费 TikHub/LLM；继续使用已有 Fixture/Fake/隔离边界。

# 公司内网 V1 最小门禁

Stage 8F 完成后才进入部署。

至少需要：

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

公司内网 V1 不等于“内网天然安全”，也不等于完整 Production Security/DR 已完成。当前延期只适用于公司受控服务器、公司内部网络、不对公网开放的范围。

# 后续生产强化 Backlog

当前不阻塞公司内网 V1：

```text
Authentication / Authorization
角色与对象级权限
Legacy Migration
正式 RPO / RTO
完整 Retention
Coordinated PostgreSQL + Artifact Backup / Restore
完整 Rollback / Disaster Recovery 演练
正式容量 / 性能 / Soak
Release digest / SBOM / 签名 / Provenance
Monitoring / Alert / VOC / Ticket
Web Report Center
公网或公司网络之外访问
```

完整 Production Roadmap 中继续保留这些长期门禁。

# 成功标准

- [x] 基于当前代码确认 Stage 8 的真实前端、后端、Job、Excel 和 Voice Plaza 主链。
- [x] 重新检查三个前端 Playwright E2E 的 Mock 边界，确认它们不能代替真实 Full-stack 证明。
- [x] 确认具体一致性缺口：`/` 存在但 AppShell 首页 disabled。
- [x] 固化下一阶段为 Stage 8F，而不是直接 Stage 11A。
- [x] 固化认证/权限延期、旧历史迁移延期、公司内网访问范围。
- [x] 区分“内网 V1”和“完整 Production Go-Live”。
- [x] 新增 `docs/roadmap/内网V1上线实施计划.md`。
- [x] 更新 `docs/roadmap/README.md` 与 `docs/roadmap/生产上线实施路线.md`。
- [x] 实质 Roadmap HEAD `4cfd1ef0e527cdabf938650c6ddd23389ac68796` 的全部本轮 Workflow 成功。
- [ ] 本次 Change 状态收口产生的新 PR HEAD 仍需新鲜 Workflow 全绿后才能合并。
- [ ] PR 实际合并后再归档本 Change。

# 验证证据

实质 Roadmap HEAD：

```text
4cfd1ef0e527cdabf938650c6ddd23389ac68796
```

新鲜 GitHub Actions：

```text
CI #1852                                      success
Stage 6 XHS Vertical Slice #1667             success
Stage 7 Keyword Packs #1462                  success
Stage 7 Provider Config Routing #1575        success
Stage 7 Plan Occurrence Run Snapshot #1460   success
Stage 7 Scheduler Runtime #1802               success
```

主 CI 包含并通过：

- Stage 1：runtime version、locked env、frontend dependency audit、local startup smoke、generated contracts/client、backend/repository checks、Wheel、Frontend checks；
- Stage 2 Platform：Platform unit + PostgreSQL integration + real readiness HTTP smoke；
- Stage 3A Database：Schema/Owner、空库 migration、PostgreSQL repositories、Stage 8B import HTTP/Worker integration、previous revision/base round-trip；
- Windows bootstrap。

本 Change 更新状态后会产生新的 PR HEAD，因此最终 Merge 门禁仍以最新 HEAD 的新鲜 Workflow 为准。

# 兼容、数据、Migration

本 Change 没有运行时代码、公共 Contract、Schema、Migration 或依赖变化。

未来 Stage 8F 修复继续遵循：

- Contract 正确时修 Feature/Store/Page；
- Contract 缺口时走 Pydantic → Route → OpenAPI → Generated Client → Frontend；
- 不手改 Generated Client；
- 不在 Vue 复制后端业务规则掩盖后端错误；
- Canonical、Content Owner、Job Runtime 不因页面修复改变。

# 部署、回滚和安全

本 Change 不部署运行环境。

Internal V1 部署实现必须单独创建 L3 Change。快速内网上线也不能通过以下方式缩短工期：

```text
绕过 Migration
关闭 Secret 检查
把 PostgreSQL 暴露到普通客户端网络
把业务数据放容器临时层
删除或跳过失败 CI
```

完整 Production Release / Backup / Restore / Authorization 的长期设计继续有效，只是明确排在公司内网 V1 之后。

# 文档影响

已同步：

- `docs/roadmap/README.md`
- `docs/roadmap/内网V1上线实施计划.md`
- `docs/roadmap/生产上线实施路线.md`

Blueprint/Production Appendix 的完整生产安全设计继续有效，因为本次定义的是更窄的公司内网 V1，而不是降低完整 Production 的安全和灾备标准。

# Git / PR

- 基线 main：`085344729ff8cee32ca38a09c18ae4635a6ff636`
- 分支：`docs/internal-v1-stage8f-roadmap-20260822`
- PR：#141 `固化 Stage 8F 前后端闭环与内网 V1 上线路线`
- PR 当前：Draft；本 Change 已进入 `ready_for_review`
- Merge：仅在 PR 最新 HEAD 新鲜门禁全部成功且用户明确授权后执行
- 归档：仅在 PR 实际合并后进行
- 发布：本 Change 不执行部署