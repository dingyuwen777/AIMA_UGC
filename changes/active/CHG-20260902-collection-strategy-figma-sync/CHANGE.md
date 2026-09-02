---
schema: coding-change/v1
id: CHG-20260902-collection-strategy-figma-sync
title: 同步采集策略 Figma 与真实车型和词包后端契约
level: L2
status: ready_for_review
owner: dingyuwen777
branch: fix/306-collection-strategy-figma-sync
created: 2026-09-02
updated: 2026-09-02
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - figma-sync
  - tests
affected_paths:
  - frontend/src/features/collection-strategy/
  - frontend/src/shared/VehicleMultiSelect.vue
  - frontend/tests/collection-strategy.spec.ts
  - frontend/tests/collection-strategy-design.spec.ts
  - frontend/e2e/collection-strategy.spec.ts
  - frontend/e2e/collection-strategy-figma-geometry.spec.ts
  - changes/active/CHG-20260902-collection-strategy-figma-sync/CHANGE.md
contracts: []
data_changes: []
---

# 目标

让 `/collection-strategy` 当前生产前端与正式 Figma `release` 中采集策略页面保持一致，同时严格服从现有后端 Contract：页面头部操作、关键词包创建入口、采集计划的词包/车型发现范围、计划详情车型展示均使用真实运行时数据，不猜测或新增 API。

# 成功标准

- [x] 页面头部仅显示“刷新数据”和“新建采集计划”，关键词包卡片头部提供唯一“新建词包”入口。
- [x] 采集计划列表第三列与 Figma 一致为“词包 / 车型”，能组合展示 API 返回的词包与车型范围。
- [x] 计划详情显示真实词包与车型；车型使用 `display_name · code`，历史 deprecated/merged 车型仍可解析，目录缺失时保留原始 ID。
- [x] 新建计划继续只从 active 车型目录选择，并保持“词包或车型至少一个”的现有资格约束。
- [x] 前端通过 generated Orval client 完整分页读取车型目录，不改后端 Contract、generated client、依赖或数据库。
- [x] 正式 1440×900 Figma 关键几何、Vitest、Playwright Browser Mock、lint、typecheck、build 和 Runtime Acceptance 已取得新鲜 GREEN 证据；合并、归档与 Issue 关闭属于通过评审后的交付阶段，不作为 `ready_for_review` 前置条件。

# 范围

- 调整 Collection Strategy Feature 的 API wrapper、Store、页面组合、关键词包面板、计划列表、计划详情、全局相关性工作区和 Figma 对应的创建抽屉展示。
- 补充 Store/单元测试、SSR 设计基线、功能 Browser Mock 和独立 Figma 1440×900 几何回归。
- 仅使用现有 AIMA UI 组件、Token、generated client 与共享 `VehicleMultiSelect`。

# 非目标

- 不新增或修改后端 endpoint、OpenAPI Contract、数据库 Schema/Migration。
- 不修改 generated API client。
- 不增加依赖或升级工具链。
- 不实现 Figma 旧注释中与真实后端不一致的词包编辑、删除、复制能力。
- 不改变采集调度、Provider、Capability、全局相关性或 Eligibility 业务规则。

# 必须保持不变

- `CollectionPlanCreateRequest` / `CollectionPlanResponse` 既有字段及五个平台机器值保持不变。
- 新建计划车型选择仍使用 `VehicleMultiSelect` 的 active-only 目录；历史展示目录与可创建目录语义不得混用。
- `Asia/Shanghai`、现有 Cron 机器值、Provider Capability/Search Config、全局相关性、词包分页和启停资格保持不变。
- 车型展示失败不得伪造业务名；未解析 ID 必须保留可追溯原始值。

# 关键决策

- 车型目录展示数据由 Collection Strategy Store 统一加载，详情和列表共享，不让组件各自猜测或重复请求。
- 历史展示读取 `/api/v1/vehicle-models` 时不传 `status`，按 `limit=200` + `offset` 直到覆盖 `total`，因此 active/deprecated/merged 均可解析；创建选择器继续 active-only，并同样完整分页。
- 列表发现范围按 Figma 三行密度展示：同时存在词包和车型时优先各展示一项，剩余项用“另有 N 项范围”汇总；车型项加“车型：”前缀，详情用 `display_name · code`。
- Figma 当前正式文案使用“执行频率”“目标平台与采集渠道”“系统固定规则”和批准的频率标签；仅调整用户可见文案，不改变 Cron 机器值。
- 关键视觉位置不是凭目测验收：新增 1440×900 Playwright 几何测试，覆盖页面头部、KPI、页签、筛选区、计划表、词包工作区、关键词弹窗、新建计划抽屉、全局相关性和计划详情抽屉。
- Figma 可见“开发状态规格”已经按当前后端 Contract / generated client 更新，并明确覆盖同页历史 Dev Mode 注释中的失效描述；当前 Plugin API 无法可靠重写部分历史注释元数据，因此不把失效注释作为实现事实源。
- 采用 connector-only 降级 Git 交付是本轮已获用户明确授权的宿主能力例外；仍保留 Issue、Change、PR、CI、Review、归档和 main 新鲜校验，不绕过门禁。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 页头只保留刷新与新建计划，新建词包移动到关键词包卡片头部 | https://github.com/dingyuwen777/AIMA_UGC/issues/306 | satisfied | `CollectionStrategyPage.vue` 删除页头新建词包；`KeywordPackPanel.vue` 提供卡片内唯一入口；Browser Mock 与 1440 几何回归均通过 |
| R2 | 计划列表同时展示真实关键词包与车型范围，并与 Figma 六列表格一致 | https://github.com/dingyuwen777/AIMA_UGC/issues/306 | satisfied | `PlanPanel.vue` 六列表头为“词包 / 车型”，真实 pack/vehicle 目录解析并保留 ID 回退；SSR、Browser Mock 和几何回归通过 |
| R3 | 计划详情展示真实车型名与 code，历史状态可解析，缺失目录回退原始 ID | https://github.com/dingyuwen777/AIMA_UGC/issues/306 | satisfied | `PlanDetailDrawer.vue` 展示独立车型区；Store 无 status 拉取历史目录；Browser Mock 验证 deprecated 车型 `display_name · code` |
| R4 | 新建计划保持 active-only 车型选择与词包/车型至少一个的资格规则 | https://github.com/dingyuwen777/AIMA_UGC/issues/306 | satisfied | `VehicleMultiSelect.vue` 默认 `status=active`；`PlanCreateDrawer.vue` 继续复用 `planExecutionReason`；Browser Mock 验证 active-only 请求与选择器 |
| R5 | 车型目录必须走 Orval generated client，并按 offset/limit 完整分页 | https://github.com/dingyuwen777/AIMA_UGC/issues/306 | satisfied | `api.ts` 只包装 generated `listVehicleModels`；Store 历史目录和共享选择器都按 `limit=200`/offset 迭代；单元与 Browser Mock 覆盖多页 |
| R6 | 平台、Provider、Cron、北京时间、Capability/Eligibility、相关性与分页既有行为保持 | https://github.com/dingyuwen777/AIMA_UGC/issues/306 | satisfied | generated 五平台枚举与 Cron 机器值未改；Capability/Eligibility Owner 保持；北京时间显示到 Figma 约定分钟粒度；完整前端 CI 通过 |
| R7 | 不修改后端 Contract、generated client、依赖和数据库 | https://github.com/dingyuwen777/AIMA_UGC/issues/306 | satisfied | `main@c246d504...` 到 `082b3533...` 新鲜 compare 仅含前端源码/测试/Change，无 backend、generated、manifest/lock、migration 或数据库路径 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | CI #3699：Vitest 16 files / 72 tests 全绿；其中采集策略 Store 8 项、设计 SSR 4 项，覆盖历史车型目录全量分页和 Figma 文案/范围 |
| 接口 / 契约 | required | 新鲜读取 generated client 确认五个平台、Plan `vehicle_model_ids`、`Asia/Shanghai`；新鲜读取车型 Contract 确认 active/deprecated/merged 与 limit≤200；PR diff 不改 Contract/generated |
| 集成 / 持久化 / 运行依赖 | not_applicable | 本次不修改持久化、数据库或真实外部服务语义；前端接线通过正式 HTTP 形状 Browser Mock 验证，无需 TikHub 实探 |
| 用户 / 工作流验收 | required | CI #3699：Playwright 46/46 全绿；覆盖页头/词包入口、范围、历史车型详情、active-only 创建以及正式 Figma 关键几何 |
| 跨组件关键路径 | required | Store → Page → PlanPanel/PlanDetailDrawer 使用同一历史车型目录；PlanCreateDrawer → VehicleMultiSelect 保持独立 active-only 创建路径；相关回归全绿 |
| 外部依赖 / 供应方探测 | not_applicable | 本次不改变供应方 API；Figma 正式节点已作为设计事实源重新读取并截图复核，TikHub 实探没有新增证明价值 |
| 构建 / 打包 / 运行 | required | GitHub Actions 锁定 Node 24.19.0 / npm 11.17.0；lint、typecheck、Vitest、Vite build、Playwright 全绿；Runtime Acceptance #820 成功 |
| 文档 / 治理 / 其他 | required | Issue #306、PR #307 `Requirement-Source: #306`、本 Active Change 均存在；Change Ready 提交后由 Completion Gate 再次机器验证 |

# 完成审计

- [x] upstream_re_read：已在最终 GREEN 后重新读取 Issue #306、Figma `3620:782` 与开发状态规格、车型后端 Contract、generated client，以及当前 `api.ts`、`store.ts`、页面组合、展示 Owner、`VehicleMultiSelect`、`presentation.ts`。
- [x] change_coverage：逐条从 Issue #306 与正式 Figma 重建完成定义，功能数据流、主要显示文案与 1440×900 关键布局均有对应实现和测试，没有用本 Change 反推需求。
- [x] reverse_audit：后端车型目录/Plan/Capability → generated client → API wrapper/Store → 页面展示与创建选择器链路成立；反向检查前端动作未发现虚构 API、额外机器枚举或前端私有 Contract。
- [x] unresolved_cleared：R1–R7 均有新鲜实现或验证证据；未发现 blocker、未经批准延期、依赖升级、Schema/Migration 或生产数据变更。

# 任务

- [x] 调查当前实现和事实源；新建项目则确认现有资料、目标和硬约束
- [x] 建立四维任务路由：现有前后端项目 / feature 修复 / Vue3+TS+Python Contract / L2
- [x] 建立失败测试或说明测试例外
- [x] 建立并维护验证矩阵
- [x] 完成最小实现
- [x] 同步受影响文档：产品/架构事实未变化；更新 Figma 开发规格与本 Change/Issue 追溯
- [x] 取得新鲜验证证据
- [x] 完成需求追溯与完成审计

# 验证

## 计划

- Store/单元：`frontend/tests/collection-strategy.spec.ts`
- 设计 SSR 基线：`frontend/tests/collection-strategy-design.spec.ts`
- 功能 Browser Mock：`frontend/e2e/collection-strategy.spec.ts`
- Figma 1440×900 几何：`frontend/e2e/collection-strategy-figma-geometry.spec.ts`
- 静态检查或构建：frontend lint、typecheck、Vitest、Vite build
- 就绪检查：`python .agents/skills/coding/scripts/ready_check.py --root . --require-active-ready`
- 正式证据以 GitHub Actions 使用仓库锁定工具链执行的结果为准；当前宿主不冒充锁定本地工具链。

## 新鲜证据

- RED：PR #307 首提交锁定车型目录与 Figma 数据流后，CI #3691 按预期失败；后续几何测试提交也先观察到可复现的布局差异，再进行最小修复。
- GREEN：最终实现头 `082b35332af0ed912c78d6f57b985d0abbd43176` 的 CI #3699 成功；Repository Quality 使用 Node 24.19.0 / npm 11.17.0 执行 lint、typecheck、Vitest、build 与 Playwright 全绿。
- Vitest：16 个测试文件、72 个测试通过。
- Browser Mock：46 个 Playwright 测试通过，其中采集策略 3 个正式几何用例覆盖主工作区、关键词弹窗/新建计划抽屉、全局相关性/详情抽屉。
- Runtime Acceptance #820 成功。
- Dependency audit：生产与完整 npm audit 均为 0 vulnerabilities；本变更未修改依赖。
- `main` 新鲜基线仍为 `c246d504679b60708eaeb698a4cce38b1702ea1a`，PR head 相对该基线 ahead 9 / behind 0，当前 mergeable=true。

# 文档影响

- 产品/架构文档不需要修改：公共 Contract、路由、数据模型、部署方式均不变化。
- Figma “开发状态规格”的可见前端实现契约已同步当前真实数据源、字体与车型规则；历史 Dev Mode 注释中无法由当前 Plugin API 稳定改写的旧描述由该正式规格显式覆盖，不作为代码生成事实源。
- Change 与 Issue 作为本次治理和需求追溯文档；合并 `main` 且 main 新鲜 CI 通过后再单独归档 Change 并关闭 Issue。

# 交付

- 提交：实现与验证头 `082b35332af0ed912c78d6f57b985d0abbd43176`；本提交将 Change 切换为 `ready_for_review`
- 拉取请求：#307（当前 Draft；Change Completion Gate 通过后再转 Ready）
- 合并：未执行；等待明确合并授权
- 发布：不适用；合并 main 后由现有发布流程按需处理
