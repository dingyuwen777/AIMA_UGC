---
schema: rvc-change/v1
id: CHG-20260814-stage7-real-provider-probe
title: 固化 Stage 7 真实 Provider Probe 与人工审阅边界
level: L2
status: ready_for_review
owner: dingyuwen777
branch: docs/stage7-real-provider-probe
created: 2026-08-14
updated: 2026-08-14
depends_on: [CHG-20260814-stage6-xhs-vertical-slice]
affected_areas: [collection, provider, testing, documentation, blueprint]
affected_paths: [docs/blueprint/02-采集系统与数据标准化.md, docs/blueprint/06-开发约束与分阶段实施.md, docs/blueprint/07-技术决策与实施门禁.md, docs/测试与调试说明.md]
contracts: []
data_changes: []
---

# 目标

把已经确认的真实 Provider 独立调试和人工审阅要求固化为 Stage 7 长期事实：五个平台正式 Operation 都必须能够通过复用生产实现的人工 Real Probe 独立验证，完整保存 Raw，并生成便于人工检查的帖子/评论 XLSX 派生视图。

# 成功标准

- [x] Blueprint 02 明确 Real Probe 的输入、生产调用链、Secret、Raw、Canonical 与 XLSX 派生物边界。
- [x] Blueprint 06 把五个平台独立 Real Probe 纳入 Stage 7 的正式范围和验收。
- [x] Blueprint 07 固化 Real Probe 的跨模块安全、费用、CI 和生产数据边界，同时保留尚未批准的四平台具体 Operation 与 Scheduler 策略门禁。
- [x] `docs/测试与调试说明.md` 说明人工 Probe 的配置能力、输出结构和 XLSX 人工审阅布局。
- [x] XLSX 以人工阅读为目标：帖子公共字段跨评论行纵向合并、评论一条一行、一级/二级关系清晰、无粗黑边框；机器事实仍由 Raw/Canonical 维护。
- [x] 不新增代码、Contract、Schema、Migration、依赖或具体 Provider Operation 选择。
- [ ] PR CI 成功，合并后 main 相关 CI 再次成功后才归档 Change。

# 范围

- 固化真实 URL + Secret + 平台/Operation/业务参数的人工 Real Probe 能力边界。
- 固化 Probe 必须复用正式 Provider Client、Operation、分页和 Mapper。
- 固化逐请求 Raw JSON/GZIP 保存、Canonical 校验和 XLSX 人工审阅派生物。
- 固化真实 Probe 不进入普通 CI、不写生产业务数据库、显式限制请求/分页预算、不泄露 Secret。
- 固化人工审阅 Excel 的最小长期布局和可读性要求。

# 非目标

- 不选择抖音、微博、B站、快手的具体正式 Operation。
- 不决定 Scheduler `misfire_policy`、`max_catch_up_runs` 或费用/容量保护值。
- 不实现 Probe 脚本、Excel Exporter、Provider Client 或任何 Stage 7 代码。
- 不新增 Excel 依赖，也不预先决定 `openpyxl`/`xlsxwriter` 等实现。
- 不改变 Stage 1—6 已建立的 Contract、Schema、Migration、Job/Raw/Ingestion 边界。

# 必须保持不变

- Raw 是外部 Provider 原始证据，XLSX 只是可重新生成的人工审阅派生物。
- Probe、测试和脚本必须复用生产 Client/Operation/Mapper，不复制 endpoint、分页或字段映射。
- API Key/Cookie/Token 等 Secret 不进入源码、Git、日志、Raw、Canonical、Excel、Job Payload 或数据库明文。
- 真实付费 Provider Probe 默认关闭且不进入普通 CI。
- Stage 7 仍受其余四平台能力矩阵/脱敏 Fixture 和 Scheduler misfire/catch-up 决策门禁约束。

# 已确认关键决策

1. 后续必须保留可人工运行的真实 Provider Probe，能够配置真实 Provider URL、通过 Secret 边界取得 API Key，并配置平台、Operation、关键词、内容/评论 ID、分页、排序、时间范围等该 Operation 明确支持的参数。
2. Real Probe 调用正式 Provider Client → 正式 Operation/分页 → Raw → 正式 Mapper → Canonical；调试脚本不得再造平行实现。
3. 每个真实请求的完整原始响应必须单独保存为 Raw JSON/GZIP；Canonical 是机器可验证的业务转换结果。
4. Probe 可以生成 XLSX 供人工审阅，但 XLSX 不作为原始证据、Canonical Contract、数据库导入事实源或业务持久化格式。
5. 人工审阅 Workbook 以少量 Sheet 为原则，核心 `内容与评论` Sheet 以一条帖子/笔记/视频为纵向区块，帖子公共字段跨其评论行合并，每条评论独占一行，并保留真实 comment/root/parent ID；空评论必须区分 complete/partial/not_requested/unavailable。
6. XLSX 采用轻量可读布局：浅色表头、白色主体、必要的浅分隔和留白、正文自动换行、ID 文本格式、URL 可点击；不使用粗黑边框包围帖子区块。
7. 其余四平台的具体 Operation 选型和 Scheduler misfire/catch-up 策略仍未批准，本 Change 不代替用户决策。

# 任务

[步骤 1：固化采集与 Probe 边界]
→ 修改范围：`docs/blueprint/02-采集系统与数据标准化.md`
→ 预期结果：Real Probe 的生产调用链、配置、Secret、Raw/Canonical/XLSX 角色清晰。
→ 验证方式：文档冲突检查 + 仓库 `check_docs`/Secret 门禁。

[步骤 2：固化 Stage 7 验收]
→ 修改范围：`docs/blueprint/06-开发约束与分阶段实施.md`
→ 预期结果：五个平台 Fixture/Fake 自动验证之外，明确保留人工 Real Probe 与 Raw/XLSX 人工审阅能力。
→ 验证方式：检查 Stage 7 范围未越界到具体 Operation/Scheduler 决策 + CI。

[步骤 3：固化跨模块硬边界]
→ 修改范围：`docs/blueprint/07-技术决策与实施门禁.md`
→ 预期结果：安全、费用、CI、生产数据边界成为跨文档事实，同时尚未决策项仍保持 No-Go。
→ 验证方式：术语/门禁冲突检查 + CI。

[步骤 4：固化人工使用与 Excel 布局]
→ 修改范围：`docs/测试与调试说明.md`
→ 预期结果：开发者能理解未来 Probe 的配置维度、输出目录、Raw/Canonical/XLSX 分工和人工审阅样式。
→ 验证方式：Markdown/链接/术语检查 + CI。

# 验证计划与当前证据

纯文档任务不伪造 Red/Green。使用仓库已有确定性文档、Secret、架构和完整 PR CI 作为替代验证；合并后再次检查 main CI。当前宿主没有本地仓库/终端，因此本轮无法在本地执行 `uv run ...` 命令，最终以 GitHub Actions 对目标提交的实际结果为准。

提交前人工复核已确认：

- 分支相对基线 `main` 只修改本 Change 和四个已声明文档；
- Blueprint 02 只扩展 Real Probe 与采集验收边界；
- Blueprint 06 只扩展 Stage 7 范围/验收，不改变阶段树；
- Blueprint 07 版本从 1.14 更新到 1.15，仅新增 Real Probe 跨模块决策和 Stage 7 No-Go；
- `docs/测试与调试说明.md` 只增加未来 Stage 7 Probe/XLSX 人工审阅说明和通用 Probe 安全要求；
- 抖音、微博、B站、快手具体 Operation 与 Scheduler misfire/catch-up 仍明确保持未决；
- 无代码、Contract、Schema、Migration、依赖和锁文件变化。

# 文档影响

只修改上述四个长期事实文档。`docs/blueprint/README.md` 当前关于 Stage 7 尚受其余平台矩阵、Scheduler 和最终预算门禁约束的摘要仍然成立，不因本 Change 修改。

# 兼容、依赖、Migration、部署和回滚

- 公共 Contract/Schema：无变化。
- Migration/数据库：无变化。
- 依赖/锁文件：无变化。
- 生产部署：无变化；本 Change 只冻结未来开发/人工调试要求。
- 回滚：如需撤销，只回滚本 Change 的文档提交，不涉及数据或运行时迁移。

# Git

- 基线 main：`7029f19e6cea8a219e1fc0b135ea53f3115da301`
- 分支：`docs/stage7-real-provider-probe`
- 当前分支 HEAD：`629f09754ad79cf4f7a613de058e67f7766cdbbe`
- Commit：文档与 Change 已提交；待 PR 集成
- PR：待创建
- CI：待 PR 运行
- 合并：未执行
- 归档：未执行
