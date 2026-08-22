---
schema: rvc-change/v1
id: CHG-20260822-stage8f-fullstack-acceptance
title: Stage 8F 前后端业务闭环与真实 Excel 验收
level: L2
status: done
owner: chatgpt
branch: feature/stage8f-fullstack-acceptance
created: 2026-08-22
updated: 2026-08-22
depends_on: []
affected_areas:
  - frontend
  - ingestion
  - content
  - ci
  - docs
affected_paths:
  - frontend/src/app/
  - frontend/src/features/import-batches/
  - frontend/src/features/voice-plaza/
  - frontend/tests/
  - frontend/e2e-fullstack/
  - frontend/playwright.fullstack.config.ts
  - frontend/package.json
  - tests/fullstack/
  - .github/workflows/stage8f-fullstack.yml
  - docs/roadmap/
  - docs/appendix/
  - frontend/README.md
contracts: []
data_changes: []
---

# 结果

Stage 8F 已通过 PR #145 合并到 `main`。本单元没有重做 Stage 8，而是基于当前正式 Contract、generated client、PostgreSQL Job Runtime、Excel Import 和 Vue Feature，只修复已确认的前端闭环缺口，并把公司内网 V1 的核心 Excel 链变成永久真实 Full-stack Acceptance。

已完成：

- App Shell 首页从无效入口改为真实 `/` 导航；
- 当前无正式页面的未来菜单项不再以死按钮占位；
- Voice Plaza 平台筛选补齐微博、B站，与当前五平台能力一致；
- Import Batch 详情明确使用“查看入库内容”，继续通过 `source_identifier` 跳转 Voice Plaza；
- 新增首版前后端能力矩阵；
- 新增不 Mock `/api/v1/**` 的真实 Excel Browser Full-stack Acceptance；
- 同步 Frontend README 与两级 Roadmap，下一最小正式单元推进为 Internal V1-A。

# 成功标准

- [x] 首版前后端能力矩阵已建立；
- [x] 首版 App Shell 真实入口可达；
- [x] 未实现未来能力不再显示为无效主导航；
- [x] Voice Plaza 当前五个平台均有筛选入口；
- [x] Batch → Voice Plaza 来源筛选保持后端正式 `source_identifier` 语义；
- [x] Excel Browser → Vue → FastAPI → Import Batch/Job → Worker → PostgreSQL Content → Voice Plaza 真实链通过；
- [x] Full-stack Acceptance 不 Mock `/api/v1/**`；
- [x] 使用隔离 PostgreSQL、生产 Reader/Mapper/Ingestion/Job Worker；
- [x] 不调用真实付费 TikHub/LLM；
- [x] 测试后清理隔离业务数据；
- [x] 原 Mock Playwright E2E 保留；
- [x] 最终 PR HEAD 的全部永久 Workflow success；
- [x] 需求符合性和代码质量 Review 完成，无严重/重要问题；
- [x] PR #145 已合并；
- [x] Roadmap 与当前实现同步。

# 保持不变

本 Change 没有修改：

- Pydantic HTTP Contract；
- OpenAPI；
- `frontend/src/generated/api/`；
- PostgreSQL Schema / Alembic Migration；
- Content 身份与数据保留语义；
- Job Runtime / Fencing / Retry；
- TikHub Provider 行为；
- AI taxonomy；
- 依赖和锁定版本；
- Docker/Compose 或公司服务器部署。

因此没有 Migration、数据回填或兼容切换。

# TDD 与问题修复证据

## 无效 Red

首个测试 HEAD `02e91986269814792cabaa5defa3a4f47ba0b5e0` 因 Vitest Node 环境缺少 `document` 失败。该失败属于测试环境问题，没有冒充产品行为 Red。

## 有效 Red

HEAD：

```text
0cdeb11b40c83df99f731362d40db9e1f4bfd555
```

CI run：

```text
32557735158
```

准确失败于：

- App Shell 缺少首页 `href="/"`；
- 未实现未来菜单仍显示；
- Voice Plaza 缺少 `weibo` / `bilibili`。

随后仅做对应最小 Green。

# 最终验证证据

PR #145 最终 HEAD：

```text
29dfd9e1010ef1b62059c334b31d23e4e0527b8f
```

该 HEAD 的永久 Workflow：

```text
CI #1883                                      success
Stage 6 XHS Vertical Slice #1698             success
Stage 7 Provider Config Routing #1606        success
Stage 7 Keyword Packs #1493                  success
Stage 7 Plan Occurrence Run Snapshot #1491   success
Stage 7 Scheduler Runtime #1833               success
Stage 8F Full-stack Acceptance #10            success
```

其中 CI #1883：

```text
Stage 1              success
Stage 2 Platform     success
Stage 3A Database    success
Windows bootstrap    success
```

Stage 1 覆盖：

- locked Python / frontend environment；
- frontend dependency audit；
- local startup smoke；
- generated Contract/client check；
- backend/repository quality checks；
- Wheel build；
- frontend lint / typecheck / unit / build / Mock Playwright E2E。

Stage 3A 覆盖：

- Schema / table owner；
- 空库 Migration 到 head 与 drift check；
- PostgreSQL repository integration；
- Stage 8B Import HTTP/Worker integration；
- Migration downgrade / re-upgrade。

Stage 8F Full-stack Acceptance #10 覆盖：

```text
PostgreSQL 18.4 隔离实例
→ 空库 Alembic upgrade/current/check
→ 确定性 Excel fixture
→ 真实 FastAPI + 正式 PostgreSQL Job Worker
→ Browser 真实 file input 上传
→ Import Batch + Job
→ 生产 Excel Reader / Mapper / Relevance / Ingestion
→ PostgreSQL Content
→ Runtime succeeded
→ “查看入库内容”
→ /voice-plaza?source_identifier=<batch_id>
→ 本批 Content 浏览器可见
→ 停止 API/Worker
→ 清理隔离数据并核对 Content / Import Batch 为 0
```

普通 CI 没有创建 TikHub Run 或 Analysis Request，因此没有真实付费 TikHub/LLM 调用。

# 两阶段 Review

## 需求符合性

- Stage 8F 核心 Excel 业务链已由真实浏览器自动化证明；
- App Shell、五平台筛选、Batch → Voice Plaza 缺口已修复；
- 采集策略、Analysis、Export 继续复用正式能力和现有测试；
- 没有进入 Docker/Compose、认证、旧数据迁移或其他非目标；
- 能力矩阵、Frontend README、Roadmap 已同步。

## 代码质量

- 没有手改 generated client 或建立第二套 HTTP Contract；
- 没有修改 Schema/Migration/Job Runtime；
- Worker harness 只循环生产 `JobWorker.run_once()`，没有复制 Import 逻辑；
- Full-stack 使用隔离 PostgreSQL 与非生产测试 Secret；
- 测试清理只作用于隔离 CI 环境；
- 没有新增/升级依赖或降低 lint/typecheck/security/docs/CI 门禁；
- 合并前 PR 无外部 review、inline thread 或未解决评论；
- 未发现严重/重要问题。

# 文档结果

新增：

- `docs/appendix/Stage8F前后端能力矩阵与真实验收.md`

同步：

- `frontend/README.md`
- `docs/roadmap/README.md`
- `docs/roadmap/内网V1上线实施计划.md`
- `docs/roadmap/生产上线实施路线.md`

长期 Blueprint、Pydantic Contract、OpenAPI、Schema/Migration 没有变化，因此未制造无关同步。

# Git / PR

```text
开始 main:
b084be777ba0e760d7f826b0241cf6e57bd27f45

实现分支:
feature/stage8f-fullstack-acceptance

PR:
#145 Stage 8F 前后端业务闭环与真实 Excel 验收

最终 PR HEAD:
29dfd9e1010ef1b62059c334b31d23e4e0527b8f

PR 状态:
merged

Merge commit:
8cdbe91c4c1f3a8abb63805f1141147ab0b7248a
```

过期 Draft PR #135 已在本任务开始阶段关闭且未合并；其对应远程分支因当前 GitHub 连接器没有删除分支能力，未执行远程分支删除。

# 部署、回滚与下一步

本 Change 未执行公司服务器部署，也没有 Docker/Compose 变化，因此没有生产部署或数据回滚动作。

Stage 8F 合并后的下一最小正式单元：

```text
Internal V1-A
→ 最小 Docker / Compose / Config
→ PostgreSQL / Artifact / Log 持久目录
→ Secret 只读装配
→ Health / Readiness
→ 空库 Migration
→ 隔离 Compose Smoke
```

只有 Internal V1-A 完成后才进入 Internal V1-B 公司服务器真实部署与业务 Smoke。
