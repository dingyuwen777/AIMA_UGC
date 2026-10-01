---
schema: coding-change/v1
id: CHG-20261001-195441-report-delivery
title: 数据库报告功能远程交付与持续回归
level: L3
status: ready_for_review
owner: Codex
branch: feature/report-delivery
created: 2026-10-01
updated: 2026-10-01
completion_gate: required
depends_on: []
affected_areas:
  - reporting
  - administration
  - storage
  - analysis
  - quality
affected_paths:
  - backend/src/aima_ugc
  - frontend
  - migrations
  - tests
  - scripts/quality
  - .github/workflows/ci.yml
  - contracts/openapi
  - docs
  - AGENTS.md
contracts:
  - reports HTTP API
  - reporting generation/publication Job v1
data_changes:
  - report_runs
  - report_items
  - report_artifacts
---

# 变更摘要

交付已经完成本地验收的数据库报告功能，并让报告 PostgreSQL 工作流在正式 CI 中持续执行。报告和品牌车型识别两批均已完成本地验证；本单元先交付报告，随后品牌识别批次同步本单元的 main 结果重新验证。

# 背景、现状与问题

main 仍使用上传 Excel 的报告管理页面。冻结检查点 `0fd93aec403049d490d58543cc6178d3fec14604` 已实现数据库预检、快照、生成下载和独立发布。原 PR #686 的新 Active Change 使用日期 ID，被当前秒级身份规则拒绝；精确 Worker registry 测试遗漏两个新增报告 Job，使正式报告 PG suite 尚未实际执行。

本 Change 是新增的远程交付单元，不重命名、不修改或伪造归档原本地记录。原分支、提交和 [原 Change](https://github.com/dingyuwen777/AIMA_UGC/blob/0fd93aec403049d490d58543cc6178d3fec14604/changes/active/CHG-20261001-report-generation/CHANGE.md) 保留。项目 AGENTS 明确顶层 changes 为唯一 Carrier 并保留不可变 legacy archive；canonical new-change 的全记录 current-schema 自动判断无法识别这种混合历史，故在已确认 Carrier 中按当前 canonical 模板创建并执行同一机器 Contract 校验。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 用户授权全部本地修改分批合入 main，并指定已保存品牌车型证据 | #684、#685及本轮明确决定 | 报告先行，关键词不重新推断 |
| E2 | 原报告产品代码已有隔离本地验收 | 冻结提交0fd93aec及原 LOCAL_VALIDATION | 保留已验证实现，迁移到新的交付单元 |
| E3 | #686 CI 有治理身份和 registry 测试失败 | Actions run 36836921195 | 修正真实缺口，重新取得当前 head/base CI |
| E4 | 项目允许 current Change 与不可变 legacy archive 共存 | AGENTS.md 正式单元完成定义门禁；scripts/quality/check_change_completion.py | 不改旧身份、不创建平行 Carrier |
| E5 | 当前目录和运行目录不同；专用测试资源已建立 | E:/Desktop/AIMA_UGC；专用容器端口55437 | 直接修改当前目录，保持运行服务隔离 |

## 推断与待确认

真实模型额度、飞书账户权限和未知网络响应尚未在线验证。通过生产 Adapter 与可控 HTTP 测试，不由本地结果推导在线账户可用。当前报告交付 head/base、CI 和 post-merge 证据仍待取得。

# 目标、成功标准与非目标

目标为管理员从数据库目录选择品牌、车型和日期，冻结依据、生成并下载报告、独立发布或恢复发布。成功标准为 R1–R7 的当前验收及当前 head/base Review 和 required CI。Issue AC8 的 merge、main 新鲜验证、原生归档与 closure 在合并后逐项完成，不提前勾选。

范围为冻结报告、专属表和 Migration、两个持久 Job、8个管理员 API、生成 Client、页面、文件生命周期、必要安全日志、有界重试、相关测试与正式文档。非目标为运行目录和既有容器操作、生产部署或迁移、依赖升级、付费模型和真实飞书写入。保持离线报告、现有统计/Renderer、Job fence/lease/deadline/cancel、Artifact 与 Content Owner 不变。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 报告第一批，品牌第二批 | E1 | 本 PR 不转入品牌识别实现 |
| 接口与契约 | Pydantic reports API、generation/publication Job v1 | E2 | 同步 OpenAPI 与生成 Client |
| 数据与迁移 | report_runs、report_items、report_artifacts；20261001_0078 | E2 | 仅隔离库执行迁移 |
| 错误与失败语义 | 生成与发布分离；有界过载重试及取消 fence | E1、E2 | 发布重试复用已生成文件 |
| 兼容性 | 保持离线入口及既有统计口径 | E2 | 数据库关键词冻结有效证据标准名称并集 |
| 部署与回滚 | 无部署；未来回滚先保留所需产物并结清报告任务 | E1 | 不操作运行数据库 |

# 修改方案与决策依据

1. 本地创建秒级 Change、治理提交、首次 push 和早期 Draft PR → 当前项目唯一 Carrier → 稳定追溯 → canonical validate-change / validate-pr。
2. 转入冻结报告产品差异，排除旧日期 Change → 原生产实现与正式文档 → 保留已验证行为 → 逐文件与冻结提交比较。
3. 修正 Worker registry 精确预期和截图 Fake 的浏览器隔离 → 两个真实测试缺口 → 正式 PG 接线及 hermetic 单元测试 → 目标测试、完整回归和 CI。
4. 当前 main/head 独立复核及 Final Ready → 当前组合 → 当前 required checks → expected-head merge；合并后原生 archive/main-fresh/Issue 收尾。

## 备选方案与取舍

重命名原日期 Change 会丢失其身份并伪造历史，不采用。修改 canonical 或旧 archive 来迁就自动判断会扩大治理变更，不采用。新的真实交付单元保留原本地里程碑和失败 PR，以当前身份承担远程门禁和持续回归。

# 需求追溯

来源为 #684 的稳定 AC；当前 Change 不是上游需求。AC8 是合并后的交付责任，仍由 Issue 持有，合并前证据在本单元取得，post-merge 不伪装已完成。

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 数据库品牌车型日期过滤及等长上期；关键词用有效已保存标准名称，每条内容去重并冻结 | #684 / AC1 | satisfied | 报告PG9项及当前0fd逐文件守恒；关键词有效标准名称并集、等长上期、去重冻结实测 |
| R2 | 冻结版本、评论、指标、分析/Scheme及管理员 Provider；后续变化不改变输入 | #684 / AC2 | satisfied | 报告PG9项：版本/指标/评论/分析及Provider一致冻结，创建后事实变化不改变输入 |
| R3 | DOCX/XLSX/Markdown/可编辑图表可下载并重新解析；默认60天及孤儿清理 | #684 / AC3 | satisfied | 报告PG下载并解析DOCX/XLSX/Markdown和图表；到期410与孤儿互斥清理；当前单元/Contract回归 |
| R4 | Word/Excel/多维表独立发布，重试不重跑模型 | #684 / AC4 | satisfied | 生产Publisher/MockTransport单元及PG9项：发布恢复不增加LLM调用，生成文件保持可下载 |
| R5 | 冻结管理员模型；代表内容考虑粉丝互动；严格输出失败不产出错误案例 | #684 / AC5 | satisfied | test_report_selection及当前1749后端回归：冻结管理员配置、粉丝互动与严格输出校验 |
| R6 | 管理页预检、创建、历史、进度、取消/重试、下载和飞书链接；真实装配路径 | #684 / AC6 | satisfied | 当前274组件、38报告浏览器、生成Contract/build；与0fd完整真实浏览器API/Worker下载实现字节相同 |
| R7 | 安全日志、有界过载重试/超时/取消/fence；本地隔离不影响运行服务 | #684 / AC7 | satisfied | PG9项覆盖503/ReadTimeout/429耗尽、取消fence；安全日志检查；专用55437/55438资源，运行目录未操作 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| reporting Repository、HTTP/Worker、Contract/Migration、管理页、生成物 | 转入冻结0fd产品差异 | 交付已授权功能 | R1–R7 / E2 |
| CI classifier/workflow、报告PG测试及guard | 转入已有修正并取得实际CI结果 | 覆盖持久化真实边界 | R1–R7 / E3 |
| registry和截图Fake测试 | 精确补充两个Job及阻止Fake调用真实浏览器 | 修复验收缺口 | R6、R7 / E3 |
| docs、Owner README、AGENTS | 转入已批准报告事实更新 | 同步长期事实 | R1–R7 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 统计、选择、严格输出、有界恢复及页面 |
| 接口 / 契约 | required | OpenAPI/生成Client与兼容检查 |
| 集成 / 持久化 / 运行依赖 | required | PostgreSQL18迁移、冻结、事务/fence及实际文件 |
| 用户 / 工作流验收 | required | 预检→生成→下载→独立发布恢复 |
| 跨组件关键路径 | required | 生产装配与可控外部HTTP；冻结路径比较与正式CI |
| 外部依赖 / 供应方探测 | not_applicable | 本轮不调用付费服务或真实飞书；不验证账户权限 |
| 构建 / 打包 / 运行 | required | 前端构建、后端lint/type与实际运行入口 |
| 文档 / 治理 / 其他 | required | Docs/Owner/Secret/Change/Requirement及当前Review/CI |

# 风险、兼容性、迁移与回滚

新增3张报告专属表及0078，保持既有接口兼容。仅操作隔离测试库，生产未迁移。未知网络结果仍可能重复远端收费/写入，保留 checkpoint 与诊断，不承诺零重复。未来回滚先结清任务、保存产物，再停止新功能并按迁移手册处理，不在本轮执行。

# 文档、依赖、部署与发布影响

更新 Product、Blueprint、Appendix、代码导航及Owner README。无依赖升级；增加默认60天保留配置，Secret使用引用。无Release/部署；生成Client随Contract交付。源代码按0fd转入，必要测试修正有独立证据。

# 完成审计

- [x] upstream_re_read：重新读取当前#684 AC1–AC8、已批准方案/用户DB证据决定、当前main15dd366和正式Owner/Contract事实。
- [x] change_coverage：AC1–AC7逐条对应当前产品/测试/文档，0fd转入守恒；AC8由Issue持有post-merge责任且保持未勾选。
- [x] reverse_audit：8个API均有页面/Client或下载入口；独立生成/发布Job、取消与恢复使用正式Runtime；Artifact下载/过期/孤儿清理有当前PG和浏览器验收。
- [x] unresolved_cleared：R1–R7均有当前证据，not_satisfied已清零；在线账户和生产部署限制保留。远程Final Review/CI及post-merge逐项取得后才宣称交付完成。

# 完成证据与状态

产品提交d1e09a8d、main15dd366为base、canonical041c9b6为规则源；0fd产品字节守恒。当前后端1749 passed/16 skipped/12subtests；报告PG9 passed/1显式browserSkip、registry1、导航fixture11、前端274组件/38报告浏览器/build、mypy427/ruff868格式/Contract/Docs/Owner/Secret均通过。原22项真实报告全链路验收继续覆盖字节守恒实现。当前命令、失败与修复范围见LOCAL_VALIDATION.md，源字节与XML摘要见EVIDENCE.json。Draft PR #688已建立，当前Final Review、required CI、merge和post-merge仍需逐项取得，不提前声称交付完成。

原 PR #686 保留失败记录，建立替代 PR 后关闭为 superseded，原分支和 Change 保留。Issue #684 AC8 在 main-fresh、原生archive及收尾之前保持未勾选。生产部署与在线付费服务验收未执行。

## 真实CI修复检查点

旧headf19895fa的Ready CI36860409129：core/全前端/全栈16/Compose/WindowsLinux通过，前7PG套件通过，reporting实际5失败均缺中文字体。新增RV-REPORT-06环境依赖阻塞，PR退Draft，不merge。PG独立runner现在安装已有fonts-noto-cjk并覆盖target/all/reporting选择；1Red→64Green+12subtests，不修改报告生产行为或降低断言。当前产品AC1–AC7证据继续成立，新的CI修复需新head实际PG和Final Review确认，AC8继续未勾选。

## 字体修复最终本地检查点

6f600435真实Linux CI报告PG现9passed/1显式browserSkip，前7套通过，安装依赖成功；core只有旧“PG永不安装字体”断言失败。已同步为有条件安装和非报告Collection轻量保护，保留其他原断言，经独立Repair Review认可；生产/Renderer不变。完整本地父子进程统一PYTHONUTF8后1750passed/16skip/12subtests，68.39秒；XML1778tests/0error/0failure。此前仅父进程-Xutf8而Windows子进程CP936导致读取stderr失败的日志保留，环境原因已直接读取stderr字节证实，不改种子隔离测试。当前新head的完整required CI和Final Review仍待取得，不能用6f部分绿色宣称已合并。
