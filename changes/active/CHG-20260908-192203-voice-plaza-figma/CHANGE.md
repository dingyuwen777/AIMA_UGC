---
schema: coding-change/v1
id: CHG-20260908-192203-voice-plaza-figma
title: 声音广场 Figma 实施与全量排序
level: L3
status: ready_for_review
owner: codex
branch: feat/voice-plaza-figma-20260908
created: 2026-09-08
updated: 2026-09-08
completion_gate: required
depends_on: []
affected_areas:
  - content
  - vehicles
  - frontend
affected_paths:
  - backend/src/aima_ugc/modules/content/
  - backend/src/aima_ugc/modules/vehicles/
  - backend/src/aima_ugc/contracts/
  - backend/src/aima_ugc/bootstrap/
  - backend/src/aima_ugc/adapters/persistence/postgres/
  - frontend/
  - migrations/
  - contracts/
  - tests/
  - docs/
contracts:
  - ContentListQuery
  - ContentListItemResponse
  - VehicleModelResponse
data_changes:
  - vehicle_models
---

# 目标与边界

上游需求为 Issue #389 和用户 2026-09-08 的按 Figma 直接实施决定。保留现有 Vue/Pinia/生成 Client/Service/Job 架构及锁定版本，增量实现后端排序、车型分组、声音广场界面和公共外壳。不得用示例数据或只对当前页排序代替真实能力；不部署、不合并。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 粉丝数和发布时间全量排序、空值置后、Cursor 绑定并兼容旧调用 | https://github.com/dingyuwen777/AIMA_UGC/issues/389 / AC1 | satisfied | PostgreSQL 双字段、双方向、同值及空值分页集成通过；旧 v1 Cursor 回归通过；真实浏览器排序请求成功 |
| R2 | 复用管理员车型目录并补 Figma 系列分组 | https://github.com/dingyuwen777/AIMA_UGC/issues/389 / AC2 | satisfied | 可空系列/类别 Migration、目录创建/缺省保留/显式清空集成通过；管理页面保存、内容列表读取和系列/别名选择全栈通过 |
| R3 | 声音广场与无顶栏公共布局符合 Figma，保留现有业务与错误恢复 | https://github.com/dingyuwen777/AIMA_UGC/issues/389 / AC3 | satisfied | 122 项前端单元与 71 项 Browser Mock 通过；详情、人工纠正、AI、导出、任务/消息中心可达；Figma 正常页及详情/导出文案同步并截图核对 |
| R4 | 有数据页面跨 1180 至 2560 宽度无异常留白、裁切，操作可达 | https://github.com/dingyuwen777/AIMA_UGC/issues/389 / AC5 | satisfied | 五平台、长标题、三个标签和三个车型在六种宽度逐列几何及溢出检查通过；1180/1440/2560 实际截图复核；窄屏表格局部滚动与固定操作列保留 |
| R5 | 公共 AppShell 无顶栏、180px 侧栏及底部任务/消息/身份入口，其他路由与权限回归 | https://github.com/dingyuwen777/AIMA_UGC/issues/389 / AC4 | satisfied | AppShell/任务消息测试与全路由六种尺寸 Browser Mock 通过，其他页面几何随公共顶栏移除而验证 |
| R6 | 分层验证、生成物、正式构建及真实结果报告 | https://github.com/dingyuwen777/AIMA_UGC/issues/389 / AC6 | satisfied | 下方 Validation Matrix 列明实际通过证据、Windows 三条既有 Linux 专属失败及待执行的正式 CI，不夸大模型 Fake 或本地证据 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 前端 122 passed；后端目标 Cursor/车型及集成组合 18 passed；扩展 Python 结果和 Windows 限制见下文 |
| 接口 / Contract | required | generate.py --check、check_compatibility.py 通过；Orval 再生成前后 Client SHA256 一致 |
| Backend/API/PostgreSQL | required | PostgreSQL 18 隔离库执行排序与目录持久化测试；Alembic upgrade head/check 通过，无额外升级差异 |
| Browser Mock Acceptance | required | 71 passed；五平台文字徽标、六种尺寸的补充检查复用相同页面与几何用例 |
| Real Full-stack Golden Path | required | 管理能力 5 passed；AI streaming 和人工相关性 3 passed；真实 Browser/API/Worker/PostgreSQL，模型为本地 Fake |
| External Provider Probe | not_applicable | 复用落库数据和既有业务；不需要付费外部调用 |
| Build / Runtime | required | npm run build、TS7/Vue 类型检查通过；mypy 317 文件通过；Ruff 全仓约定范围和前端全量 lint 通过 |
| Docs / Governance / Other | required | 产品、API Blueprint、Content README 定向同步；文档、事实、Secret、架构/表 Owner、项目治理检查通过 |

# 实施计划

1. Contract/查询/Cursor → 全量排序 → 单元与 PostgreSQL 边界验证。
2. 车型目录/Migration/管理入口 → 真实系列数据 → 目录和内容消费集成验证。
3. AppShell/声音广场组件与 Store → Figma 运行效果 → 目标浏览器行为和截图。
4. 生成物/文档/构建 → 兼容与完成复核 → 汇总新鲜证据。

# 兼容、部署与回滚

旧调用不传排序保留 coalesce(published_at,last_seen_at) 降序；新页面显式发布时间排序。新 Cursor 绑定排序，旧 Cursor 在原查询和有效期内继续可读。车型增量可空字段不要求修改既有 ID；先执行 Migration 后部署新代码，回滚先回旧代码，保留新字段数据。

# Completion Audit

- [x] upstream_re_read：重新读取 Issue #389、Figma 正常页/三种浮层和用户关于整体页面、铃铛、列宽及多平台标识的决定；最新 origin/main 仍为 e93839959b7a57fd29b5344d6b7e39562a2671e8。
- [x] change_coverage：逐项核对全量排序、旧调用兼容、真实车型目录、页面状态、多尺寸及文档，覆盖 R1–R6，无自行延期的需求。
- [x] reverse_audit：生成 Client → API → Owner 查询/写入接线一致；现有相关性/标签/车型纠正与撤销、锁定/解锁、任务取消、导出下载入口保留；用户可见异步状态及错误由现有服务返回。未知粉丝数不伪造为零。
- [x] unresolved_cleared：本次实现未发现未解决的阻塞缺陷。Windows 上既有 Linux 权限测试无法执行，保留真实失败并交由正式 Linux CI 验证；不据此宣称 CI 通过、合并或部署。

# 验证记录

- 初始 Red：tests/unit/content/test_content_cursor.py，4 failed / 1 passed。新增字段与排序身份尚不支持，失败符合预期；原签名防篡改用例通过。
- 后端目标：`python -m pytest tests/unit/content/test_content_cursor.py tests/unit/content/test_vehicle_display_classification.py tests/integration/content/test_stage8d_voice_plaza_runtime.py tests/integration/database/test_u1_u5_administration.py -q`：18 passed。数据库只使用本任务隔离 PostgreSQL，不修改用户数据库。
- 前端：`npm run test -- --run`：23 文件、122 passed；`npm run test:e2e`：71 passed；`npm run lint`、`npm run build`：exit 0。新增 AI 预检竞争回归经历失败后修复通过。
- 独立审查补充：复用六种宽度用例加入五平台、长标题、三个标签和三个车型，`npm run test:e2e -- e2e/voice-plaza-design.spec.ts -g 'column geometry'`：6 passed（10.8s）；补充后 `npm run typecheck` 与 `npm run lint`：exit 0。截图已实际复核。
- 正式 CI `a64b81f4`：Linux Python Unit/Contract/API 分别 909/104/53 passed，前端 122 单元及 71 Browser Mock 通过；PostgreSQL 集成各组共 228 passed，Compose 和 Linux/Windows Tooling 通过。真实全栈 11 passed / 1 failed：历史导入用例仍在新版列表中断言正文。依据正式列表/详情分工，将同一正文断言移入对应内容详情；保留标题冲突、历史补空及 selected/all Run 的业务断言。同时按独立复核改用数量菜单的完整刷新，并用真实活动任务区域替换已失效的旧文案负断言。修正后须以最终 head CI 为准。
- 历史导入适配最终复跑：新的任务隔离 PostgreSQL 执行 `npm run test:e2e:fullstack -- e2e-fullstack/stage12-historical-analysis.spec.ts`，1 passed（27.7s）；正文补空、冲突、连续 selected/all 分析及撤销均通过。曾复现菜单未关闭导致后续刷新不可达，已补充关闭；失败用例遗留来源造成的后续冲突数量差异通过新隔离库恢复 CI 初始条件，不改原预期。独立增量复核无新增发现，Typecheck 与目标 ESLint 通过，无新增生产代码差异。
- 全栈：现有 `admin-product-capabilities.spec.ts` 5 passed；`analysis-streaming.spec.ts` 与 `manual-relevance-review.spec.ts` 合计 3 passed。覆盖管理目录保存→列表/详情消费，以及真实 Worker 的分析和人工纠正。未调用真实付费模型或 TikHub。
- 扩展 Python：`python -m pytest tests/unit tests/contracts tests/api -q` 在 Windows 得到 1055 passed、8 skipped、3 failed；三条失败均在未修改的 `test_prepare_host.py` 调用 Windows 不存在的 `os.geteuid/chown` 时发生。沙箱首次运行还出现临时目录 PermissionError，已在正常主机权限下复跑消除；没有删除、跳过或修改失败测试。
- `python -m mypy backend/src/aima_ugc`：317 文件通过。与 CI 相同范围的 Ruff format/check：641 文件已格式化、检查通过。
- `scripts/contracts/generate.py --check`、`scripts/contracts/check_compatibility.py`、`scripts/quality/check_architecture.py`、`scripts/quality/check_table_ownership.py`、`scripts/quality/check_docs.py`、`scripts/quality/check_docs_facts.py`、`scripts/quality/scan_secrets.py`、`scripts/quality/check_agent_governance.py` 均 exit 0。
- 生成 Client 再生成前后 SHA256：`D7B2DBA3D5258740F277924F3C712A6171ADB204F96F5DEBE1BC138F1D25C6AF`；没有手改生成物或升级依赖。

# 作者复核与独立审查状态

- 独立审查：用户明确授权一个只读审查 Agent。审查者重新读取 Issue #389 六项 AC，对照 `e938399 → 979f4e9` 及补充后的 AC5 测试完成需求和实现两阶段复核，结论为 `NO_FINDINGS_WITHIN_SCOPE`。原长标题/多标签/多车型的证据缺口经补充测试及截图复核关闭。审查者未重新运行全量测试；最终提交 head 的正式 CI 仍须通过，此结论不等于可合并。
- 正式 CI：实现提交的 Compose Golden Path、Linux/Windows Developer Tooling 已通过；首次 CI 因 PR `Requirement-Source` 使用完整 URL 而非项目要求的 `#389` 失败，已修正 PR 字段。元数据编辑运行因同 SHA 尚无全绿基线失败，后续实际测试补充提交触发完整 CI；最终结果以 PR 当前 head 为准。

- 需求复核：从用户决定、Issue 和正式 Figma 重建范围，再核对实现和证据。1440 基准侧栏 180、页面左右间距 24；表格复用 Figma 固定列宽，标题列承接剩余宽度。无顶栏布局也验证了采集策略、运行中心、管理及任务/通知入口。
- 代码复核：检查 SQL 双向 NULLS LAST 和 ID 续页、作者一对一关联、旧摘要/旧 Cursor、车型省略与显式 null、合并后分类投影、请求迟到竞争、模态焦点/Escape、日期北京时间边界、导出字段初始化及旧任务行为。复核未发现需阻断本次提交的问题；这不替代托管平台 Review 和 CI。
- 视觉：已实际检查正常页、1440/2560 截图及详情/AI/导出尺寸。平台标识保持 Figma 的书/抖/快/微/B 文字徽标，配合颜色和平台名称，不声称已使用官方品牌 Logo。实际数量、车型、标签和任务数据保持来自 API。
- Figma 同步仅修改正常页及详情/导出的十处可用性文案：二级标签前置提示、人工复核明确措辞和导出已选范围；不改变整体页面结构、尺寸或示例数据。

# 文件变更与交付边界

- Content Contract、查询、Cursor、HTTP 投影：后端全量排序及作者粉丝数；车型 Contract、Owner、表及 Migration：可空系列/类别的管理与消费。对应 OpenAPI/TypeScript Client 由正式生成器同步。
- AppShell、NotificationInbox：无顶栏布局与底部公共入口、Figma 铃铛资产。VoicePlazaPage、Filters、Table、Detail、Analysis、Export、Store：基准版式、真实状态和既有业务保留。
- 新增 AimaDateRange/AimaDialog，扩展已有 VehicleMultiSelect 的 compact 模式；其他消费者保留原模式。新增 bell/calendar/sort 三个 SVG 均来自当前 Figma。
- 前后端测试按行为及公共布局更新；产品说明、API Blueprint、Content README 只同步当前变化。预先存在的 Figma 工作流指南修改排除在本次提交外。
- 分支 `feat/voice-plaza-figma-20260908`，PR #390 → main；用户授权到提交/推送/PR，不合并、不部署、不删除分支。正式 CI 结果以本 PR 当前 head 的 GitHub Actions 为准。
