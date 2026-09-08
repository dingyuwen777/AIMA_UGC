---
schema: coding-change/v1
id: CHG-20260909-admin-configuration-figma
title: 管理员配置 Figma 与代码增量同步
level: L2
status: ready_for_review
owner: codex
branch: feature/admin-configuration-figma-20260909
created: 2026-09-09
updated: 2026-09-09
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - administration
affected_paths:
  - frontend/src/features/admin-configuration/
  - frontend/src/shared/styles/responsive.css
  - frontend/e2e/
  - frontend/e2e-fullstack/
  - frontend/tests/
  - tests/fullstack/fake_openai_llm.py
  - frontend/README.md
  - docs/product/
contracts: []
data_changes: []
---

# 背景、目标与不变项

依据Issue #395与用户逐页完整交付授权。采集策略PR #394已合并并归档，本页从main 28d3c1c601c94e9e9d38522c828b3cbd0e37ddb5开始。正式Figma Page3957:2有六个标签页、宽窄规格和行为说明；当前Vue页面已有所有管理能力，AI模型/TikHub测试连接也已接入后端，但Figma主画板缺入口。目标是增量对齐布局、状态和交互，保留总体页面及公共复用。

范围为六个标签页、Provider测试连接与草稿状态、表格滚动及相应Figma状态。优先复用现有AdminConfigurationPage、ProviderConfigurationPanel、AnalysisLabelsEditor、VehicleMultiSelect、Aima公共UI与生成Client。不得新增平行API/Store或业务规则，不新增认证、全库审计搜索、付费Probe、依赖、Schema/Migration或生产部署。原有docs/guides/01_Figma与前端设计开发工作流.md修改不属于本次提交。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 六个标签页对照与公共组件复用 | https://github.com/dingyuwen777/AIMA_UGC/issues/395 / AC1 | satisfied | 六个标签保留公共UI和生成Client；Browser核验1180/1440布局及1180/1281/1440/1920表格；正式Figma六个Owner和30条跨页导航已核对 |
| R2 | 已保存配置测试连接及完整结果状态 | https://github.com/dingyuwen777/AIMA_UGC/issues/395 / AC2 | satisfied | 两类Provider的已保存配置、未保存提示、在途身份和迟到成功/失败回归通过；Figma正式测试按钮与5249:3452状态示例已查看 |
| R3 | Provider生命周期、Secret与草稿保护 | https://github.com/dingyuwen777/AIMA_UGC/issues/395 / AC3 | satisfied | 保存时锁定表单、失败保留输入；真实LLM服务配置创建/修改/连接/归档/恢复/删除闭环通过，密钥不回显 |
| R4 | 车型、关联、操作记录和长表格可达 | https://github.com/dingyuwen777/AIMA_UGC/issues/395 / AC4 | satisfied | 车型与操作记录使用独立滚动区，末列可达且标题/分页不随表滚动；分类、引用、合并和动态目录沿用正式Owner，PG与Browser证据通过 |
| R5 | 分析规则完整能力与历史语义 | https://github.com/dingyuwen777/AIMA_UGC/issues/395 / AC5 | satisfied | 发布前保存、保存后服务端新版本规范化回填、冲突保留输入和复制名称清空回归通过；正式API生命周期与历史Run冻结保持 |
| R6 | 状态、宽窄布局、设计同步及真实能力边界 | https://github.com/dingyuwen777/AIMA_UGC/issues/395 / AC6 | satisfied | 六个正式Owner同步业务文案，Provider复用公共目录/编辑器；高级参数/反馈状态、规则输入容器、六列表格及行为说明均经结构和截图核验；不显示未实现审计搜索 |
| R7 | 分层验收、独立Review、完成审查 | https://github.com/dingyuwen777/AIMA_UGC/issues/395 / AC7 | satisfied | 本地Frontend Unit131、Browser101、Backend连接4、PostgreSQL9、真实Full-stack6通过；两阶段代码Review、完成定义及文档独立复核无阻断。正式CI独立由R8控制，仍待执行 |
| R8 | 当前提交正式CI | https://github.com/dingyuwen777/AIMA_UGC/issues/395 / AC7 | explicitly_deferred | 仅按AGENTS提交→push→CI顺序后置，合并前必须通过，不豁免 |
| R9 | main合并后验证、归档和清理 | https://github.com/dingyuwen777/AIMA_UGC/issues/395 / AC8 | explicitly_deferred | 用户已授权完整交付；合并后执行，最终交付前必须完成，不延期至其他迭代 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Unit / Component | required | 管理页面、Provider参数与结构化标签既有单元回归 |
| Browser Mock Acceptance | required | 六个标签、长数据、宽窄、旧响应、测试连接、草稿及失败恢复 |
| Backend/API/PostgreSQL Integration | required | 复用既有Provider/车型/规则生命周期测试，不以Mock代替服务器边界 |
| Real Full-stack Golden Path | required | 复用真实管理员产品能力路径；连接测试采用本地Fake或服务器受控失败验证，不调用真实计费服务 |
| External Provider Probe | not_applicable | 不修改Provider协议，无需真实账户或计费调用 |
| Build / Runtime | required | lint、类型检查、正式构建、实际浏览器截图 |
| Docs / Governance / Design | required | 产品文档定向同步、Figma结构/截图/原型、两阶段独立Review、Ready与CI |

# 实施计划

1. 正式Figma、当前页面与公共样式 → 逐标签核对真实差异 → Browser实际几何、状态和API请求验收，先复现缺陷。
2. AdminConfigurationPage、ProviderConfigurationPanel及必要私有组件 → 最小布局/状态修正 → 测试连接和保存草稿/并发返回回归，保持Contract与后端业务限制。
3. 对应正式Figma Owner与状态画板 → 同步已有能力及合理体验修正 → 小范围结构读取、截图和原型验证，不用截图冒充可编辑结构。
4. 测试、产品文档、Change与PR → 分层验收和独立审查 → 当前head CI、受SHA保护合并、main复验、自动归档、Issue及分支清理。

# 兼容、部署与回滚

保持Route、生成Client、Provider连接测试Contract、数据库、身份/授权、Secret处理、Scheme发布和历史冻结语义。前端静态资源按现有方式发布；回滚本次前端代码与静态资源即可。无数据迁移、配置或依赖变化。Figma示例不是生产事实，开发测试不代表生产已部署。

# Completion Audit

- [x] upstream_re_read：重新读取GitHub Issue #395的AC1–AC8、用户逐页交付授权、正式Figma、产品事实和实际调用链。
- [x] change_coverage：六个标签、Provider草稿/连接/生命周期、车型关联、规则版本和操作记录均有实现、测试、文档依据；CI及main交付依R8/R9继续执行。
- [x] reverse_audit：独立复核AC1–AC5及后端能力→页面入口、页面动作→正式API，无遗漏或虚构能力；真实Full-stack确认历史Run冻结。复制/归档部分依据调用链及既有生命周期测试，不声称每项均新增Browser用例。
- [x] unresolved_cleared：实现、文档、设计及独立Review无剩余阻断。当前提交CI和main集成尚未执行，R8/R9继续阻止最终完成和合并。

# 当前状态

进入待审仅表示实现、本地验证、文档和独立Review完成，不表示CI通过、可合并或任务完成。当前提交正式CI、main合并后验证、归档和分支清理仍未完成，须按R8/R9取得实际结果。


# 已取得的本地验证证据与待执行门禁

- 初始Browser实际复现未保存仍可测试、迟到结果串到其他配置、保存可继续编辑、发布未锁定及表格无独立滚动区；对应回归修复后通过。
- `npm run lint`与`npm run build`（TS7、Vue类型检查、Vite）退出0；前端23个Unit文件/131项通过；完整Browser101项通过，包含新增管理员14项。实际查看六标签1180/1440截图，表格专项额外覆盖1281/1920与末列操作。
- 后端`test_provider_connectivity.py`4项通过：TikHub当前用户接口、Origin拒绝、LLM模型目录接口、上游错误及Secret不回显。
- 隔离PostgreSQL中，`test_u1_u5_administration.py`及`test_provider_config_repository.py`4项、`test_product_resource_lifecycle.py`5项通过；组合命令重复运行的连接Unit不计作额外独立覆盖。
- 真实`admin-product-capabilities.spec.ts`6项通过：车型/词包/导入/筛选，导出Worker/通知，规则原子发布/新旧Run冻结，审计第二页，词包生命周期，以及新增LLM服务配置完整生命周期。使用全新隔离库和本地Fake；没有真实TikHub账户/付费Provider Probe。TikHub由上述Backend Unit和两类Provider Browser覆盖。
- Fake仅新增GET /v1/models元数据响应，保存、授权、Secret、版本、归档和删除均走正式实现。
- Ruff check/format、文档链接、机器事实一致性、架构边界、表写Owner和项目治理接线检查退出0。Pydantic既有弃用警告未触发依赖升级。
- 两阶段独立代码Review最终NO_BLOCKERS；独立完成定义反查AC1–AC5无遗漏；两份文档复核NO_DOC_BLOCKERS。Reviewer未重跑本轮全部测试，不能用其结论替代实际测试或CI。
- 正式Figma Page3957:2已核对六个Owner与全部30条跨页签目标，Provider公共目录/编辑器、车型字段、关联入口、六列表格及标题/分页同步。规则两个多行输入容器改为纵向HUG，截图确认不再裁切。
- 高级状态5246:3408、连接/保存状态5249:3452、行为说明4908:25400及其入口/返回原型已核对；最终Provider、TikHub、车型、关联、规则、操作记录、反馈和高级参数PNG已实际下载查看。失败的大调用未计为成功，重复临时参考已清理。
- 本次无公共Contract、Schema/Migration、依赖、认证、预算、付费Probe或生产部署变化。
- 尚未取得：当前实现提交的正式CI；main合并及合并后CI；Change自动归档；Issue关闭与本任务分支清理。以上必须在最终交付前逐项执行，不由本记录豁免。
