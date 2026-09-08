---
schema: coding-change/v1
id: CHG-20260909-collection-strategy-figma
title: 采集策略 Figma 与代码增量同步
level: L2
status: ready_for_review
owner: codex
branch: feature/collection-strategy-figma-20260909
created: 2026-09-09
updated: 2026-09-09
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - collection
affected_paths:
  - backend/src/aima_ugc/contracts/
  - backend/src/aima_ugc/bootstrap/
  - backend/src/aima_ugc/adapters/persistence/postgres/keyword_lifecycle.py
  - contracts/openapi/openapi.json
  - tests/integration/database/test_keyword_pack_atomic_update.py
  - frontend/src/features/collection-strategy/
  - frontend/src/shared/
  - frontend/e2e/
  - frontend/e2e-fullstack/keyword-pack-editor.spec.ts
  - frontend/src/generated/api/client.ts
  - frontend/tests/
  - frontend/README.md
  - docs/product/
contracts:
  - KeywordPackUpdateRequest
  - KeywordPackKeywordCreateRequest
data_changes: []
---

# 目标、范围和不变项

依据 Issue #393 和用户逐页完整交付授权，先核对采集策略正式 Figma，再在现有页面/子组件内增量实现，保持总体布局和业务能力，复用已有公共组件，合理可用性修正同步回设计。基线 main：3a2d578ea300a30520b473ae42de5b8939b2ae2e。

范围包括词包、全局相关性、采集计划、创建/编辑/详情、状态与响应式。保留 Route、Vue/Pinia、生成 Client、现有 Contract、Scheduler 和历史配置语义。无依赖升级、Schema/Migration、生产部署或真实付费 Provider 调用。用户原有 docs/guides/01_Figma与前端设计开发工作流.md 修改不属于本次提交。管理员配置是下一独立页面任务，本 Change 不混入。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Figma 完整状态与真实能力核对 | https://github.com/dingyuwen777/AIMA_UGC/issues/393 / AC1 | satisfied | 正式 Page 4627:13214 主画板、状态和新增编辑/资源详情结构与截图完成核对 |
| R2 | 代码增量对齐并复用公共组件 | https://github.com/dingyuwen777/AIMA_UGC/issues/393 / AC2 | satisfied | 保留 PageShell、AimaDialog/Drawer/Button、表格、反馈及现有 Feature Owner；设计公共实例和代码公共组件继续复用 |
| R3 | 词包与全局相关性完整操作保留 | https://github.com/dingyuwen777/AIMA_UGC/issues/393 / AC3 | satisfied | Store、Browser、生命周期 API/PostgreSQL 与真实跨层验收，详见验证记录 |
| R4 | 计划完整操作、车型、Capability和历史配置保留 | https://github.com/dingyuwen777/AIMA_UGC/issues/393 / AC4 | satisfied | PlanCreateDrawer 继续复用车型/逐平台搜索参数；周期计划真实跨层验收；当前资源与历史冻结配置文案同步 |
| R5 | 响应式、长数据、异步、错误和产品文案 | https://github.com/dingyuwen777/AIMA_UGC/issues/393 / AC5 | satisfied | 1100至1920宽度横向滚动操作可达、长列表末项、旧请求隔离、错误重试和焦点返回验收通过 |
| R6 | 本地分层验收、设计对照和两阶段复核 | https://github.com/dingyuwen777/AIMA_UGC/issues/393 / AC6 | satisfied | 下方各适用层取得证据；Windows三项Linux专用失败明确保留，由R7正式Linux CI闭环 |
| R7 | 当前提交正式 CI | https://github.com/dingyuwen777/AIMA_UGC/issues/393 / AC6 | explicitly_deferred | 仅按 AGENTS 提交→push→CI 的顺序延至实现提交后，合并前必须通过，不豁免 |
| R8 | 合并 main 后验证、归档和清理 | https://github.com/dingyuwen777/AIMA_UGC/issues/393 / AC7 | explicitly_deferred | 仅按用户及 AGENTS 授权流程在CI通过后执行；最终交付前必须完成，不延期到其他迭代 |
| R9 | 新建/编辑共用完整词包表单并原子保存 | https://github.com/dingyuwen777/AIMA_UGC/issues/393 / AC8 | satisfied | 同一KeywordPackCreateDialog完整草稿和单次更新；PostgreSQL 9项、Browser及真实跨层通过；Figma5198:31577同步成员平台/优先级/启停/备注 |
| R10 | 计划资源点击查看全部当前配置并同步Figma | https://github.com/dingyuwen777/AIMA_UGC/issues/393 / AC9 | satisfied | 既有GET返回完整成员与车型字段；Browser长列表、错误重试、焦点返回通过；Figma5189:31271/5203:3257及点击/返回原型同步 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 策略Store、资格和表单状态 |
| 接口 / Contract | required | 生成消费者无漂移，合法创建/更新请求保留 |
| Backend/API/PostgreSQL | required | 既有词包/全局相关性/周期计划服务器边界 |
| Browser Mock Acceptance | required | 词包、相关性、计划流程，响应式、异步和失败 |
| Real Full-stack Golden Path | required | 复用现有真实策略/管理接线用例，隔离PostgreSQL，无付费调用 |
| External Provider Probe | not_applicable | 不修改Adapter或外部协议，不需要真实计费请求 |
| Build / Runtime | required | lint、TS7/Vue类型检查、正式build与实际截图 |
| Docs / Governance / Other | required | 定向文档、Figma状态、需求/完成审查、Ready及CI |

# 实施计划

用户补充决定：新建/编辑必须共用同一词包表单和一次保存；计划详情点击词包或车型可查看完整当前内容，代码与正式Figma同步。原先只复用弹窗壳、成员分别保存的实现不作为最终交付。

补充范围与取舍：现有词包更新请求增加可选完整成员列表，旧请求省略时保持原元数据更新行为；创建/追加成员请求增加默认all的平台范围，复用当前已有平台范围语义。继续由同一System Owner在同一事务校验版本、归档及启用限制并提交，失败不保留部分更新。无需Schema/Migration，不放宽在用配置规则。计划资源详情复用既有GET及AimaDialog，不新增历史版本查询或用当前内容回填历史。

5. `contracts/http.py`、`contracts/resource_lifecycle.py`、`bootstrap/import_http.py`、`bootstrap/resource_lifecycle_http.py`、`postgres/keyword_lifecycle.py` → 同一事务完整保存词包 → 共享关键词隔离、允许追加/禁止在用修改、版本冲突、原子回滚及旧请求兼容测试。
6. 生成OpenAPI/Schema/Client与前端统一表单、计划资源详情 → 用户看到一致表单和完整内容 → Browser成功/失败/完整长列表、真实API/PostgreSQL、生成一致性、正式Figma结构与截图验收。

1. 正式Figma/公共组件与现有Contract→确定差异并补齐必要画板→结构、状态、原型及截图核对。
2. Page/私有组件/Store→增量修复和复用→先复现缺陷，再执行目标回归。
3. 真实跨层接线和正式构建→确认保留业务能力→使用现有隔离测试，不创建平行实现。
4. 产品文档/审查/CI→完成当前页面交付→受SHA保护合并、main复验、自动归档、Issue同步和分支清理。

# 兼容、部署与回滚

现有词包更新 Contract 增加可选 keywords，省略时保持元数据更新兼容；创建/追加成员的 platform_scope 默认 all，保留原请求行为。前后端应一起部署；回滚本次代码及对应生成物即可恢复原接口消费者。不变更数据库、Migration、依赖、配置、调度、权限或费用边界。开发环境和Figma示例不代表生产已部署。

# Completion Audit

- [x] upstream_re_read：Ready前通过GitHub重新读取Issue #393全部AC1–AC9，与用户统一表单/完整当前资源决定及正式Figma交叉核对。
- [x] change_coverage：按上游逐项重建主页面、业务操作、响应式、原子保存、资源详情与交付定义；实现要求均有证据，CI和合并仅按时序后置。
- [x] reverse_audit：后端词包/相关性/计划操作均有前端入口；前端详情只调用既有GET，统一保存走Owner事务；不虚构立即执行/预算/历史版本查询，不改写历史冻结配置。
- [x] unresolved_cleared：实现与独立复核无未关闭阻断；R7/R8仍是实际交付门禁，必须在最终完成报告前执行。

# 当前状态

实现、分层验收、两阶段独立代码复核与Figma结构/截图核对已完成，准备提交当前实现并执行正式CI。最终交付仍待当前提交CI、main合并后验证、归档与分支清理。

# 验证与复核记录

- Red → Green：较旧详情和分页响应覆盖刷新结果的两项 Store 回归先失败后通过；统一更新的成员 Contract/事务测试先失败后通过。
- 独立复核发现累计501成员保存受限和原备注空白丢失；隔离 PostgreSQL 分别复现后修复，保留创建上限和既有累计成员，完整回传不裁剪备注。
- 两个统一更新请求反序追加相同新词已在两个真实 PostgreSQL 事务中复现 DeadlockDetected；按 normalized_text 唯一键顺序调用既有 Repository 后转绿。该结论不扩展为所有既有写入口的统一并发保证。依据匹配版本 PostgreSQL 18 官方锁文档：https://www.postgresql.org/docs/18/explicit-locking.html 。
- `tests/integration/database/test_keyword_pack_atomic_update.py`：9 passed；独立 Reviewer 也实际重跑9 passed。覆盖原子保存、失败回滚、并发版本、重复成员、启用限制、共享隔离、旧请求、501成员、原备注和反序并发。参数化项导致测试函数数与用例数不同。
- 既有词包/资源生命周期/周期计划 API 与 PostgreSQL 目标组合：20 passed。
- 前端 Unit：23 files / 131 tests passed；完整 Browser Mock：87 passed；补充详情错误重试及横向滚动操作可达性后，策略几何目标13 passed。
- 隔离真实 Full-stack：周期计划逐平台 Search Config、词包创建与完整编辑、未引用词包归档/恢复/条件删除各1 passed。均使用真实 API/PostgreSQL，未调用付费 Provider。
- 前端 lint、TS7/Vue 类型检查、正式 Vite build通过；后端 mypy 317 files、Ruff check和642 files格式检查通过。
- 后端完整 Unit/Contract/API 在 Windows：1055 passed、8 skipped、3 failed。失败均为既有 `tests/unit/test_prepare_host.py` 对 Linux `os.geteuid/chown` 的要求；未修改/跳过失败用例，以当前提交的正式 Linux CI 作为合并门禁。
- 文档入口与链接检查、机器事实一致性、架构边界和表写 Owner检查通过。生成 OpenAPI/Client 已同步，最终生成差异与 Ready检查在提交前执行。
- 两阶段独立 Review：业务/规格及实现质量均 NO_BLOCKERS；两项 P2 和重复成员错误断言建议均关闭。并发修复已独立复验。最终 Figma 与当前 SHA CI 仍单独验收，不能由代码 Review 代替。
- Figma最终验收：新增统一编辑5198:31577、词包详情5189:31271、车型详情5203:3257，复用公共Modal实例；三个正文均为582×362、clipsContent=true、VERTICAL滚动。查看入口与关闭/返回原型已读取并补齐；当前配置/历史冻结行为标注已同步。实际下载并查看最终PNG，确认成员属性、详情字段和按钮无横向溢出；未用截图冒充结构证据。
- 最终增量复验：前端lint、check_agent_governance.py、scripts/contracts/generate.py --check及check_compatibility.py均退出0。Figma服务部分大调用失败后拆分为小调用，失败未作为验收成功。
