---
schema: rvc-change/v1
id: CHG-20260822-stage8f-fullstack-acceptance
title: Stage 8F 前后端业务闭环与真实 Excel 验收
level: L2
status: in_progress
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
  - .github/workflows/ci.yml
  - docs/roadmap/
  - docs/appendix/
  - frontend/README.md
contracts: []
data_changes: []
---

# 目标

把当前 Stage 8 已有的前后端能力收口为公司内网 V1 上线前可验证的真实业务闭环：修复当前可确认的页面入口/筛选缺口，并建立一条不 Mock `/api/v1/**` 的 Excel 浏览器上传 → FastAPI → PostgreSQL Job → Worker → Content → Voice Plaza 验收链。

# 成功标准

- [ ] 形成基于当前代码、Pydantic Contract、generated client 和测试的首版前后端能力矩阵。
- [ ] App Shell 只呈现当前首版真实可用入口，不再把未实现能力显示成无效按钮。
- [ ] 声音广场当前五个平台的已实现 Content 查询能力都有对应筛选入口。
- [ ] Import Batch 有明确的“查看入库内容”入口，并继续使用 `source_identifier` 跳转到声音广场。
- [ ] 新增真实 Full-stack Excel Acceptance；测试中不拦截/Mock `/api/v1/**`。
- [ ] Full-stack Acceptance 使用隔离 PostgreSQL、真实生产 Import Reader/Mapper/Ingestion/Worker，且不调用真实付费 TikHub/LLM。
- [ ] Full-stack Acceptance 完成后清理隔离业务数据。
- [ ] 现有 Mock Playwright E2E 保留并通过。
- [ ] Frontend lint/typecheck/unit/build/E2E 与受影响 Backend/Integration/质量门禁通过。
- [ ] Roadmap、Frontend README 与实际实现同步。

# 范围

- 对照采集运行中心、采集策略、声音广场和 App Shell 建立能力矩阵。
- 修复当前代码已证明的首版前端入口/筛选不一致。
- 增加独立的 Full-stack Playwright 配置、确定性 Excel fixture 生成器和测试 Worker harness。
- 在永久 CI 中加入 Stage 8F Full-stack Acceptance 门禁。
- 根据最终验证结果同步内网 V1 Roadmap 状态。

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

1. 本轮按 L2 执行。调查未发现需要修改公共 Contract、Schema、Migration 或部署架构的必要性；若后续事实推翻该判断，先升级为 L3 再继续依赖该变化的实现。
2. 采用最小增量方案，不建立第二套 API/Worker/Import 链：真实浏览器验收直接驱动当前 Vue，后端继续使用现有生产 FastAPI、PostgreSQL Job Runtime 和 Import Worker。
3. 未实现的未来 App Shell 入口直接隐藏，而不是保留无法点击的“死按钮”；根 `/` 兼容入口继续存在，但主导航只展示真正独立的首版业务页面，避免与采集运行中心形成重复入口。
4. Full-stack Acceptance 与现有 Mock E2E 分离运行。Mock E2E 继续负责快速 UI 回归；Full-stack 测试单独连接隔离 PostgreSQL 和真实 API/Worker，避免普通页面测试被外部环境污染。
5. Excel Fixture 在测试运行前使用仓库已锁定的 `openpyxl` 确定性生成，不新增二进制 fixture 管理或第三方依赖。

# 任务

- [x] 调查当前实现、Roadmap、Contract、generated client、PostgreSQL 查询和现有测试。
- [ ] Red：为 App Shell 首版导航和声音广场五平台筛选补失败测试，并取得失败证据。
- [ ] Green：做最小前端修复并保持现有 Contract/Store 调用链不变。
- [ ] 建立真实 Excel Full-stack Acceptance harness、Playwright 用例和 CI 门禁。
- [ ] 建立并同步首版前后端能力矩阵。
- [ ] 运行目标测试、相关回归、Frontend 全门禁、Backend 受影响测试和仓库质量检查。
- [ ] 完成需求符合性 Review 与代码质量 Review。
- [ ] 更新 PR，确认最新 HEAD CI 全绿后按授权合并。
- [ ] 合并后归档 Change，并再次走正常 PR/CI 门禁。

# 验证

## 计划

- Red/目标测试：`npm --prefix frontend run test -- --run frontend/tests/app-shell.spec.ts frontend/tests/voice-plaza.spec.ts`
- 前端相关：`npm --prefix frontend run lint`、`npm --prefix frontend run typecheck`、`npm --prefix frontend run test -- --run`、`npm --prefix frontend run build`、`npm --prefix frontend run test:e2e`
- Full-stack：`npm --prefix frontend run test:e2e:fullstack`
- 后端相关：`uv run pytest tests/integration/ingestion -q`、`uv run pytest tests/integration/content/test_stage8d_voice_plaza_runtime.py -q`
- Contract：`uv run python scripts/contracts/generate.py --check`
- 仓库质量：`uv run python scripts/quality/check_architecture.py`、`uv run python scripts/quality/check_table_ownership.py`、`uv run python scripts/quality/scan_secrets.py`、`uv run python scripts/quality/check_docs.py`
- 集成证据：PR 最新 HEAD 的永久 GitHub Actions CI。

## 新鲜证据

- 尚未执行 Red/Green/Full-stack 验证。
- 开始基线：`main=b084be777ba0e760d7f826b0241cf6e57bd27f45`。
- 开始时 `changes/` 仅有 `archive/`，无 Active Change。
- 过期 Draft PR #135 已关闭且未合并；其唯一删除目标在当前 main 已不存在。

# 文档影响

- 新增 Stage 8F 能力矩阵/真实验收 Appendix，记录当前首版动作对应 Route/Contract/Generated Client/Feature/Page/Test 的状态，不复制第二套字段 Schema。
- 完成后同步 `docs/roadmap/内网V1上线实施计划.md`、`docs/roadmap/生产上线实施路线.md` 和 `frontend/README.md`。
- Blueprint 长期架构预计不变；若实现过程中发现长期边界变化再单独处理。

# 交付

- Commit：进行中。
- PR：尚未创建。
- 发布：不涉及公司服务器部署；本轮只完成 Stage 8F，Internal V1-A 为下一正式单元。
