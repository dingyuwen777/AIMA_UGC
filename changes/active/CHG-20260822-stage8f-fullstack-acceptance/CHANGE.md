---
schema: rvc-change/v1
id: CHG-20260822-stage8f-fullstack-acceptance
title: Stage 8F 前后端业务闭环与真实 Excel 验收
level: L2
status: ready_for_review
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

# 目标

把当前 Stage 8 已有的前后端能力收口为公司内网 V1 上线前可验证的真实业务闭环：修复当前可确认的页面入口/筛选缺口，并建立一条不 Mock `/api/v1/**` 的 Excel 浏览器上传 → FastAPI → PostgreSQL Job → Worker → Content → Voice Plaza 验收链。

# 成功标准

- [x] 形成基于当前代码、Pydantic Contract、generated client 和测试的首版前后端能力矩阵。
- [x] App Shell 只呈现当前首版真实可用入口，不再把未实现能力显示成无效按钮。
- [x] 声音广场当前五个平台的已实现 Content 查询能力都有对应筛选入口。
- [x] Import Batch 有明确的“查看入库内容”入口，并继续使用 `source_identifier` 跳转到声音广场。
- [x] 新增真实 Full-stack Excel Acceptance；测试中不拦截/Mock `/api/v1/**`。
- [x] Full-stack Acceptance 使用隔离 PostgreSQL、真实生产 Import Reader/Mapper/Ingestion/Worker，且不调用真实付费 TikHub/LLM。
- [x] Full-stack Acceptance 完成后清理隔离业务数据。
- [x] 现有 Mock Playwright E2E 保留。
- [ ] 合并前最终 PR HEAD 的 Frontend lint/typecheck/unit/build/E2E、Backend/Integration、质量门禁与 Stage 8F Full-stack CI 全部通过；该事实以 GitHub 最新 HEAD CI 为准，并在归档 Change 记录最终 SHA/Run，避免为“记录最终 CI”再次改变待合并 HEAD。
- [x] Roadmap、Frontend README 与实际实现同步。

# 范围

- 对照采集运行中心、采集策略、声音广场和 App Shell 建立能力矩阵。
- 修复当前代码已证明的首版前端入口/筛选不一致。
- 增加独立的 Full-stack Playwright 配置、确定性 Excel fixture 生成器和测试 Worker harness。
- 增加永久 Stage 8F Full-stack Acceptance workflow。
- 同步内网 V1 Roadmap，使下一最小正式单元推进为 Internal V1-A。

# 非目标

- 不实现登录、Authentication、Role/Permission 或权限隔离。
- 不实现 Docker/Compose；Internal V1-A 仍是 Stage 8F 完成后的下一正式单元。
- 不迁移旧历史数据。
- 不修改 AI taxonomy、TikHub Provider 语义或付费调用策略。
- 不新增独立 Analysis/Export/Report Center 页面。
- 不重做现有前端视觉设计，不做无关重构或目录改名。

# 必须保持不变

- Pydantic HTTP Contract → OpenAPI → Orval generated client 的单一事实链；`frontend/src/generated/api/` 禁止手改。
- Excel Import 继续使用 `Input Artifact → Import Batch + PostgreSQL Job → Worker → Reader/Mapper → Canonical → Relevance → ContentIngestionService → PostgreSQL`。
- Content 来源筛选继续由后端正式 `source_identifier` 查询实现，Vue 不增加第二套过滤规则。
- 当前 PostgreSQL Schema、Migration、Content 身份、Job Runtime、表 Owner 和公共 API 保持兼容。
- 普通 CI 不调用真实付费 TikHub/LLM。
- 当前依赖及锁定版本不升级、不新增依赖。

# 关键决策

1. 本轮按 L2 执行。实际实现没有修改公共 Contract、Schema、Migration 或部署架构，因此没有升级为 L3。
2. 采用最小增量方案，不建立第二套 API/Worker/Import 链：真实浏览器验收直接驱动当前 Vue，后端继续使用现有生产 FastAPI、PostgreSQL Job Runtime 和 Import Worker。
3. 未实现的未来 App Shell 入口直接隐藏，而不是保留无法点击的“死按钮”；根 `/` 兼容入口继续存在并可导航。
4. Full-stack Acceptance 与现有 Mock E2E 分离运行。Mock E2E 继续负责快速 UI 回归；Full-stack 测试单独连接隔离 PostgreSQL 和真实 API/Worker。
5. Excel Fixture 在测试运行前使用仓库已锁定的 `openpyxl` 确定性生成，不新增二进制 fixture 管理或第三方依赖。
6. Full-stack Worker harness 只循环调用生产 `JobWorker.run_once()`；不复制 Reader、Mapper、Relevance、Ingestion 或 Job 状态机。

# 任务

- [x] 调查当前实现、Roadmap、Contract、generated client、PostgreSQL 查询和现有测试。
- [x] Red：为 App Shell 首版导航和声音广场五平台筛选补失败测试，并取得正确失败证据。
- [x] Green：做最小前端修复并保持现有 Contract/Store 调用链不变。
- [x] 建立真实 Excel Full-stack Acceptance harness、Playwright 用例和永久 CI 门禁。
- [x] 建立并同步首版前后端能力矩阵。
- [x] 完成需求符合性 Review 与代码质量 Review；未发现严重/重要问题。
- [ ] 等待本次 `ready_for_review` 元数据提交后的最终 PR HEAD 完整回归与所有永久 CI。
- [ ] 将 PR 从 Draft 转为可合并状态，确认最终 HEAD 全部门禁通过后按授权合并。
- [ ] 合并后归档 Change，并再次走正常 PR/CI 门禁。

# 验证

## 计划

- 前端：永久 `CI / Stage 1` 执行 lint、typecheck、unit、build、Mock Playwright E2E。
- Full-stack：永久 `Stage 8F Full-stack Acceptance / Excel Browser Full-stack`。
- 后端/数据库：永久 `CI / Stage 3A Database`，包含 Stage 8B Import HTTP/Worker 集成。
- Contract：永久 `CI / Stage 1 / Verify generated contracts and client`。
- 仓库质量：永久 `CI / Stage 1 / Backend and repository checks`。
- 集成证据：PR 最新 HEAD 的全部 GitHub Actions workflow。

## Red / Green 新鲜证据

### 无效 Red（不计入 TDD 证据）

首个测试 HEAD `02e91986269814792cabaa5defa3a4f47ba0b5e0` 使用 Vue Test Utils `mount()`，Vitest 当前 Node 环境缺少 `document`，因此失败属于测试环境错误。该结果明确不作为产品行为 Red。

### 有效 Red

HEAD `0cdeb11b40c83df99f731362d40db9e1f4bfd555`，CI run `32557735158`：

- App Shell SSR 输出没有 `href="/"` 的首页入口；
- 未实现的未来菜单仍出现在 App Shell；
- Voice Plaza 平台筛选缺少 `weibo` / `bilibili`；
- 同一轮后端与 PostgreSQL 集成门禁未显示由这些测试引入的业务失败。

这些失败准确对应目标缺陷。

### Green / Full-stack

HEAD `41218a990311e9daad0c611f7f6a2200597ca5e3`：

- `Stage 8F Full-stack Acceptance` run `32558201453` → `Excel Browser Full-stack` 全步骤 success；
- PostgreSQL 18.4 service healthy；
- 空库 `alembic upgrade head`、`current`、`check` success；
- 确定性 Excel fixture 生成 success；
- 真实 FastAPI + 正式 Job Worker 启动和 `/health/ready` success；
- 浏览器真实 Excel 上传 → Batch + Job → Worker → PostgreSQL Content → Runtime succeeded → “查看入库内容” → Voice Plaza 内容可见 success；
- 测试后停止进程、TRUNCATE 隔离数据并核对 Content / Import Batch 为 0 success；
- 该链没有创建 TikHub Run 或 Analysis Request，不调用真实付费 TikHub/LLM。

HEAD `94b0dfccc3597094ef383350e9061cfa9cc41deb`：

- 永久 `CI` run `32558443240` 全部 success：Stage 1、Stage 2 Platform、Stage 3A Database、Windows bootstrap；
- Stage 1 包含 locked environment、generated contracts/client、仓库质量检查、Wheel build、Frontend lint/typecheck/unit/build/Mock Playwright E2E；
- Stage 3A 包含 PostgreSQL repository integration 与 Stage 8B Import HTTP/Worker integration；
- `Stage 8F Full-stack Acceptance` run `32558443223` success；
- 同一 HEAD 的 Stage 6 与四条 Stage 7 永久 workflow 也全部 success。

本文件切换为 `ready_for_review` 会产生一个仅 Change 元数据变化的新 HEAD。合并前必须再次确认该最终 HEAD 的全部永久 workflow success；最终 SHA/Run 在归档 Change 中记录，避免再次修改待合并 HEAD 形成自引用循环。

## 两阶段 Review

### 需求符合性

- Stage 8F 核心 Excel 浏览器链已由不 Mock API 的真实测试覆盖；
- App Shell、五平台筛选、Batch → Voice Plaza 缺口已修复；
- 采集策略、Analysis、Export 继续复用当前正式能力和既有自动化测试；
- 没有进入 Docker/Compose、认证、历史迁移或其他非目标；
- Roadmap、能力矩阵和 Frontend README 已同步。

### 代码质量

- 没有手改 `frontend/src/generated/api/`，没有新增第二套 HTTP Contract；
- 没有修改 Schema/Migration/Content 身份/Job Runtime；
- Full-stack Worker harness 复用生产 Worker Registry 与 `JobWorker.run_once()`，不复制 Import 业务逻辑；
- Full-stack 测试使用隔离 PostgreSQL，测试 Secret 为非生产固定值，普通 CI 不调用付费 Provider/LLM；
- 测试清理只作用于隔离 CI PostgreSQL；
- 没有新增或升级依赖，没有降低 lint/typecheck/security/docs/CI 门禁；
- PR 变更范围与 Change 一致，未发现严重/重要 Review 问题；当前 PR 无外部 review、inline thread 或未解决评论。

## 开始事实

- 开始基线：`main=b084be777ba0e760d7f826b0241cf6e57bd27f45`。
- 开始时 `changes/` 仅有 `archive/`，无 Active Change。
- 过期 Draft PR #135 已关闭且未合并；其唯一删除目标在开始时 current main 已不存在。

# 文档影响

已同步：

- `docs/appendix/Stage8F前后端能力矩阵与真实验收.md`；
- `frontend/README.md`；
- `docs/roadmap/README.md`；
- `docs/roadmap/内网V1上线实施计划.md`；
- `docs/roadmap/生产上线实施路线.md`。

Blueprint 长期架构、Pydantic Contract、OpenAPI、Schema/Migration 未改变，因此没有制造对应无关差异。

# 交付

- 分支：`feature/stage8f-fullstack-acceptance`。
- PR：#145 `Stage 8F 前后端业务闭环与真实 Excel 验收`，当前 Draft，未合并。
- 发布：未执行；本轮不部署公司服务器。
- 下一最小正式单元：PR #145 合并且 Change 归档后为 Internal V1-A。
