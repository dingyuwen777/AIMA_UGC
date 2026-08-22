---
schema: rvc-change/v1
id: CHG-20260822-internal-v1-stage8f-roadmap
title: 内网 V1 前后端闭环与快速上线实施路线
level: L3
status: in_progress
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

基于当前 `main` 的 Stage 8、前端页面、HTTP Contract、Generated Client、Worker、PostgreSQL 和测试事实，重新确定 AIMA_UGC 的近期交付目标：

1. 先把已经实现的前端和后端功能真正闭环，而不是继续增加新业务模块；
2. 以“Excel 可以从页面导入、后台真实处理、数据进入 PostgreSQL、最终可以在声音广场正确显示”为首版最重要的端到端验收链；
3. 前后端闭环后，再把当前系统部署到公司服务器，仅允许公司内部网络访问；
4. 登录/权限隔离、旧历史数据迁移和完整生产强化能力明确延期，不让它们阻塞第一版内网上线；
5. 保留完整 Production Go-Live 的长期门禁，不把“内网 V1 可用”误写成“完整生产安全闭环”。

本 Change 只固化实施路线和产品/部署边界，不在本 Change 中修改运行时代码、公共 HTTP Contract、Schema、Migration 或依赖。

# 用户已确认的上游决策

2026-08-22 用户明确确认：

```text
第一版优先目标
→ 统一前端与后端已经存在的功能
→ 修复缺失按钮、错误限制、跨页面不通、前后端能力不匹配
→ Excel 可以真实导入并显示数据
→ 部署到公司服务器
→ 只要求公司内部网络访问

第一版明确延期
→ 登录 / Authentication
→ 用户角色 / Permission / 权限隔离
→ 旧历史数据迁移

后续待办，不作为第一版内网上线的当前决策前置
→ 正式 RPO / RTO
→ 完整数据保留策略
→ 正式容量 / 性能 / Soak 目标
→ 协调 Backup / Restore 完整闭环
→ 完整 Release provenance / SBOM / 签名
→ Monitoring / Alert / VOC / Ticket
→ Web Report Center
```

延期认证不改变长期身份边界：未来仍使用 Provider-neutral `Identity / Authentication Adapter → Principal / AuthContext → Authorization`，业务模块不绑定飞书或其他 Provider 私有身份。

# 当前仓库事实

## Stage 8 已有业务能力

当前路由：

```text
/
/voice-plaza
/collection-runtime
/collection-strategy
```

当前主要页面能力：

```text
采集运行中心
→ Excel Import
→ TikHub Run
→ 运行列表 / 摘要 / 详情

采集策略
→ Keyword Pack
→ Relevance Config
→ Collection Plan

声音广场
→ Content 查询 / 详情 / 筛选
→ AI Analysis
→ Excel Export
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

现有前端 Playwright E2E 主要通过 `page.route('**/api/v1/**')` Mock HTTP，因此可以验证页面交互，但不能证明：

```text
真实 Vue
→ 真实 FastAPI
→ 真实 PostgreSQL Job
→ 真实 Worker
→ 真实 PostgreSQL
→ 再由 Vue 查询显示
```

已经发现的具体一致性例子：

```text
routes.ts 中 `/` 首页真实存在
HomeView 复用 CollectionRuntimePage
但 AppShell 的“首页”导航被 disabled
```

这说明当前需要的是系统性的前后端闭环审计，而不是零散补一个按钮后直接容器化。

# 方案比较

## 方案 A：直接进入 Stage 11A 容器化

优点：最快看到服务器页面。

缺点：

- 会把现有前后端缺口原样封装进容器；
- Mock E2E 仍不能证明 Excel → Worker → PostgreSQL → Voice Plaza；
- 上线后才发现按钮、状态、Contract 或跨页面问题，排障成本更高。

不推荐。

## 方案 B：重新做一遍 Stage 8

优点：可以全面返工。

缺点：

- 当前后端 Contract、Job、页面和大部分 Feature 已经存在；
- 会重复已经验证的架构基础；
- 容易扩大范围、拖慢内网上线。

不推荐。

## 方案 C：新增 Stage 8F“前后端业务闭环与上线前验收”，然后进入内网 V1 部署

优点：

- 保留 Stage 8 已完成的机器事实；
- 只针对真实不闭环点修复；
- 以可观察业务链而不是“页面能打开”作为验收；
- 完成后再容器化，能显著降低部署后返工。

**采用方案 C。**

# 当前实施路线

```text
当前 main
↓
Stage 8F：前后端业务闭环与上线前验收
↓
Internal V1-A：最小可部署 Docker / Compose / Config
↓
Internal V1-B：公司服务器部署与真实业务 Smoke
↓
公司内网 V1 上线
↓
后续生产强化 Backlog
↓
完整 Production Go-Live
```

# Stage 8F：前后端业务闭环与上线前验收

这是下一最小正式开发阶段。

## 目标

把“后端已经有能力”和“前端已经有页面”转换成真正可用的业务产品闭环。

## 必须审计的能力矩阵

每一项都检查：

```text
业务动作
→ 后端 Route / Contract
→ Generated Client
→ Feature api.ts
→ Store / state
→ 页面入口 / 按钮
→ 可用条件 / disabled 条件
→ loading / success / error
→ 跨页面结果
→ 自动化测试
→ 是否属于首版
```

## 采集运行中心

至少验证：

- Excel 上传入口真实可用；
- 上传后创建 Import Batch + Job；
- Worker 状态能反映到页面；
- 成功/失败/处理中状态与后端一致；
- Batch 详情可读；
- “查看入库内容”正确跳到声音广场并按 Import Batch 过滤；
- TikHub 手工 Run 的按钮、Capability 限制、详情和状态与后端一致；
- 不允许页面发起后端 Contract 不支持的动作。

## 采集策略

至少验证：

- Keyword Pack 新建、查看、启停、加关键词；
- Relevance Config 查看与保存；
- Collection Plan 新建、查看、启停；
- 页面约束与后端 Domain/Contract 一致；
- 保存配置不被误写成“立即执行采集”。

## 声音广场

至少验证：

- Excel/TikHub 入库的数据都能查询；
- Batch/Run 来源筛选真实有效；
- Content 详情与来源链可读；
- 搜索、平台、内容类型、时间、Analysis 等筛选与后端语义一致；
- AI 打标按钮只在可提交时可用，Job 状态正确；
- Excel Export 创建、状态、下载闭环；
- 不在 Vue 复制后端过滤/权限/业务规则来掩盖 Contract 问题。

## App Shell / 导航

- 所有首版真实路由都有合理导航入口；
- 未来能力不以“看起来可以点但实际上没实现”的方式展示；
- disabled/hidden 必须代表真实产品决定；
- `/` 与 `/collection-runtime` 的关系明确，避免首页存在但导航不可达。

## Stage 8F 测试门禁

保留现有 Mock E2E 作为快速 UI 回归，但新增真实 Full-stack Acceptance。

第一条必须闭环：

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
→ 能看到本次导入的数据
```

这个测试不能 Mock `/api/v1/**`。

普通 CI 不调用真实付费 TikHub/LLM；TikHub 和 AI 使用仓库已有 Fixture/Fake/隔离边界验证前端状态和 Contract。

# Internal V1：公司内网上线最小门禁

Stage 8F 完成后再进入部署。

第一版至少需要：

```text
Dockerfile / Compose / 生产配置装配
frontend / api / worker / scheduler / migrate / postgres 服务拓扑
PostgreSQL 持久目录
Artifact 持久目录
应用日志持久目录
Secret 文件边界
Health / Readiness
Migration 从空库到 head
容器重启后数据不丢
宿主机 reboot 后关键数据仍在
公司内部网络可以访问前端
PostgreSQL 不暴露给普通客户端网络
真实 Excel → Worker → PostgreSQL → Voice Plaza Smoke
```

这组要求不是为了“完整生产合规”，而是避免第一版一重启就丢数据、只启动 API 没启动 Worker、页面能打开但 Excel 永远不处理等基础故障。

# 明确延期的能力

以下项目不阻塞“公司内网 V1”，但继续保留为后续正式 Roadmap：

```text
Authentication / Authorization
角色与对象级权限
旧历史数据迁移
正式 RPO / RTO
完整 Retention Policy
Coordinated PostgreSQL + Artifact Backup / Restore
完整 Rollback / Disaster Recovery 演练
正式容量 / 性能 / Soak 验收
Release SBOM / 签名 / Provenance 强化
Monitoring / Alert / VOC / Ticket
Web Report Center
公网或公司网络边界之外的访问
```

这里的“延期”不等于这些能力没有价值，也不等于内网天然安全。第一版接受的残余风险只适用于：

```text
公司受控服务器
+ 公司内部网络访问
+ 不对公网暴露
+ 不把内网 V1 宣称为完整 Production Security Go-Live
```

一旦要扩大访问范围、接入更多用户或承载更高业务风险，必须重新进入认证/授权、Backup/Restore、RPO/RTO、容量和安全门禁。

# 成功标准

- [x] 基于当前代码确认 Stage 8 的真实前端、后端、Job、Excel 和 Voice Plaza 主链。
- [x] 确认现有前端 E2E 的 Mock 边界，不能把它当真实 Full-stack 证明。
- [x] 确认至少一个真实前端一致性缺口：`/` 存在但 AppShell 首页 disabled。
- [x] 固化下一阶段为 Stage 8F，而不是直接 Stage 11A。
- [x] 固化第一版认证/权限延期、旧历史迁移延期、公司内网访问边界。
- [x] 区分“内网 V1 上线”和“完整 Production Go-Live”。
- [ ] Roadmap 正式文档已同步并通过仓库文档/CI 门禁。
- [ ] PR 合并后再将本 Change 归档。

# 兼容、数据和 Migration

本 Change 不修改运行时代码、公共 Contract、数据库 Schema 或 Migration。

未来 Stage 8F 修复遵循：

- 后端 Contract 正确时修 Feature/Store/Page；
- Contract 确有缺口时走 Pydantic → Route → OpenAPI → Generated Client → Frontend 的完整链；
- 不手改 Generated Client；
- 不为了 UI 方便复制后端业务规则；
- 数据身份、Canonical、Content Owner、Job Runtime 不因页面修复改变。

# 部署与回滚

本 Change 本身只改文档，无运行时部署。

Internal V1 部署实现必须单独创建 L3 Change；完整 Production Release 仍继续遵循现有 Stage 11 长期设计。第一版部署失败时不得通过绕过 Migration、关闭 Secret 检查、把 PostgreSQL 暴露公网或删除失败 CI 来“快速上线”。

# 文档影响

本 Change 需要同步：

- `docs/roadmap/README.md`：明确当前优先入口；
- `docs/roadmap/内网V1上线实施计划.md`：保存当前短期实施计划；
- `docs/roadmap/生产上线实施路线.md`：把 Stage 8F 和 Internal V1 放到完整 Production 之前，并保留长期生产强化门禁。

Blueprint/Production Appendix 的完整生产安全设计继续有效；因为本次定义的是范围更窄的“公司内网 V1”，不把完整 Production 门禁降级为内网默认安全。

# Git / PR

- 基线 main：`085344729ff8cee32ca38a09c18ae4635a6ff636`
- 分支：`docs/internal-v1-stage8f-roadmap-20260822`
- PR：待创建
- Merge：未经用户明确授权不直接合并
- 发布：本 Change 不部署