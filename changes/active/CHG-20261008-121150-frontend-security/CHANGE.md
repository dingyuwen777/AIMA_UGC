---
schema: coding-change/v1
id: CHG-20261008-121150-frontend-security
title: 修复前端依赖安全审计阻塞
level: L3
status: ready_for_review
owner: Codex
branch: tech/frontend-security-20261008
created: 2026-10-08
updated: 2026-10-08
completion_gate: required
depends_on: []
affected_areas:
  - "frontend-dependencies"
  - "frontend-ci-prerequisite"
affected_paths:
  - "frontend/package.json"
  - "frontend/package-lock.json"
  - ".github/workflows/ci.yml"
  - "tests/unit/test_ci_workflow_structure.py"
contracts: []
data_changes: []
---

# 变更摘要

按用户批准的独立安全升级任务，把 Vue 及同步组件升级至 3.5.42，source-map-js 至 1.2.2，postcss-selector-parser 至 7.1.6，解除现有依赖审计阻塞；其他依赖与产品代码保持现行事实。

# 背景、现状与问题

## 背景

Requirement Source 为 #704；用户已明确批准上述最小升级并要求继续合并主分支。原 #702/#703 飞书整合任务保持原范围，本任务先独立修复其遇到的 main 基线依赖问题。

## 当前现状

起始 main 为 cef862941cf1a2bb9b67e0c0e32aa4edf2f265f1。Vue/@vue 3.5.41、source-map-js 1.2.1、postcss-selector-parser 7.1.5。Node 24.19.0/npm 11.17.0，唯一前端锁文件为 frontend/package-lock.json。

## 问题、根因或约束

锁定版本命中三项安全公告；npm audit 实测 exit 1，4 个漏洞计数中包含 Vue 元依赖计数，3 high/1 moderate。不能把包审计命中等同于生产漏洞已被利用，也不能绕过现有 required 检查。

## 不修改的后果

相同锁文件继续命中已确认公告，正式 required CI Gate 失败，阻止当前受保护 main 交付。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 旧锁实际 npm audit exit 1，3 high/1 moderate | .runtime/sync-local-feishu-20261008/security-audit-before.json；CI 37722547954/job113133356401 | 按失败版本修复，不关闭审计 |
| E2 | 公告的最小修复版本及 npm 发布均已确认 | GHSA-g2v6-rqmx-r4w6、GHSA-68fv-2mgg-jv7q、GHSA-rj75-hqrm-r3gf；官方 release 和 npm view | 仅升级已批准的三个补丁版本 |
| E3 | 两个间接依赖的上游范围支持修复版本 | @vue/compiler-core/postcss 的 source-map-js ^1.2.1；eslint-plugin-vue 的 parser ^7.1.4 | 优先普通依赖解析，不增加 override 或直接依赖 |
| E4 | 项目依赖升级是独立任务，现有 CI/归档有效 | AGENTS.md；.github/workflows/ci.yml、change-archive.yml | 本地独立分支、Issue、Change、PR |

## 推断与待确认

未测试生产部署或真实 Provider；无本轮发布授权，不构成依赖修复的证据替代。

# 目标、成功标准与非目标

## 目标

在保持产品兼容的前提下消除本次已确认的依赖公告，并让团队 main 可以通过正式安全审计。

## 成功标准

以 #704 / AC1–AC6 为上游完成定义。预合并 Ready 与实际 main-fresh/archive/Closure 不混为同一阶段。

## 范围

两个frontend依赖文件、现有CI的Python测试前置条件、前置回归与本Change。依赖仍只更新三组批准补丁；正式CI新失败要求补齐既有前端测试需要的锁定Python环境。

## 非目标

其他依赖/Runtime/工具链升级、业务代码、API/Schema/Migration、CI重构、删减检查或保护规则改造、Release、部署与生产数据操作。

## 必须保持不变

Node/npm 精确版本、无关包版本、下载源与 integrity 校验、公共 Contract、业务 Schema、页面行为与现有质量门禁。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | root 单写，独立 Reviewer 只读 | #704、E4 | 两个依赖文件 |
| 接口与契约 | 不适用：不修改 HTTP/CLI/模型 | 仅 Manifest/lock 变化 | 无生产 Contract 变动 |
| 数据与迁移 | 不适用：不修改业务 Schema | 无后端或 migration diff | 不连接业务库 |
| 错误与失败语义 | 保留 npm audit 和 CI 的非零失败 | E1 | 禁止强制修复或 gate bypass |
| 兼容性 | 同一 minor 的精确补丁，Vue 内部保持同步 | E2/E3 | 编译、渲染与测试需回归 |
| 部署与回滚 | 正常 npm ci；普通 PR 可回滚 lock，但旧漏洞会复现 | E1/E4 | 不执行部署 |

# 修改方案与决策依据

## 最小充分方案

1. 保存旧 lock 的实际 audit Red，确认 Issue、分支和独立 Change；首个治理 checkpoint 后建立早期 Draft PR。
2. 用 npm 的 package-lock-only 精确更新 Vue 3.5.42；在现有 semver 内精确解析两个间接补丁，不增加直接依赖或 override。检查所有 lock 节点与元数据差异，拒绝无关漂移。
3. 正式 npm ci、audit 和完整 frontend lint/typecheck/unit/build/browser；运行生成器确认 Client 无漂移，并读取统一 classifier 的 preflight。
4. 重读 #704 / 用户决定，做 Completion Audit 和独立 Review；Final Ready 同步最新 main，取得 current-head CI 后 guarded merge、main-fresh、原生归档与 Issue Closure。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| 精确补丁升级 | E1/E2 | 切断已确认失败机制，避免解析 latest |
| 保留原解析策略 | E3 | 上游支持修复版本，无需新 override |
| 独立安全 PR | E4 | 与飞书资产分开审查和回滚 |

## 备选方案与取舍

| 方案 | 覆盖与代价 | 决定 |
| --- | --- | --- |
| 在现有四处Python前置条件纳入frontend_required | 所有被选择的前端测试都有正式解析器所需环境；增加锁定安装成本，metadata/docs/main复用flags false仍保持轻量 | 采用；切断已复现遗漏且无需新分类协议或平行事实源 |
| 在classifier新增frontend_python_required并逐个测试映射 | 可减少无需Python的前端target安装，但增加输出/Workflow耦合，今后调用解析器的新target需同步维护 | 当前缺陷无需该机制，不采用；不为了成本优化扩大重构 |
| 生成可供前端读取的Prompt taxonomy fixture | 需增加生成/漂移检查与维护边界，避免复制生产解析器仍有额外成本 | 当前只缺测试环境，不改变正式事实读取，不采用 |

不删除测试或弱化断言、审计阈值、required checks；本次无需用户业务/公共Contract/Schema/权限/不可逆行为的新决定。
# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 三组精确升级且无无关漂移 | #704 / AC1 | satisfied | verify_security_lock.py PASS：12 个批准节点；无节点新增/删除，无关元数据不变；Babel 解析器保持原 7.29.8 |
| R2 | 正式安装与审计 Green，保留报告 | #704 / AC2 | satisfied | npm ci exit0、npm audit --json exit0，各严重性及 total 均 0；npm ls exit0 无旧副本或 invalid |
| R3 | 前端回归及生成一致性 | #704 / AC3 | satisfied | lint/typecheck/build exit0；38 文件306 unit PASS；205 Browser Mock PASS；Orval 生成无 Git diff |
| R4 | 需求/实现完整审计及独立 Review | #704 / AC4 | satisfied | epoch3独立A1需求覆盖/A2源码与局部证据PASS，reviewed head91d14315/base cef8629；SEC-PF-01 CLOSED。SEC-CI-01要求CI风险升L3，本最终载体已修正并记录当前Source依据，最终Change与4个源码blob定点复核后启动正式CI |
| R5 | required CI、受保护合并、main-fresh 和原生 archive | #704 / AC5 | explicitly_deferred | 正式平台阶段：current-head required CI 为合并前门禁；guarded merge、main-fresh、native archive、Closure 只能在随后真实发生后确认。AGENTS.md/原生 Workflow 规定此阶段，不代表批准跳过或当前已完成；全部满足才关闭 Issue |

| R6 | 正式前端测试的锁定Python环境与轻量边界 | #704 / AC6 | satisfied | V9：真实classifier8场景回归先4fail/4pass，修正4处前置条件后相关6文件100pass；docs/governance无安装，metadata/main复用边界由既有结构/行为检查保持；新head正式CI仍由R5合并前责任覆盖 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| frontend/package.json | Vue 精确补丁版本 | 公告修复 | R1/E2 |
| frontend/package-lock.json | Vue 同版本树及两个间接依赖 | 正式可复现安装 | R1/R2/E3 |
| .github/workflows/ci.yml | frontend_required加入4处Python前置条件 | 正式Prompt解析测试缺少.venv | R6 |
| tests/unit/test_ci_workflow_structure.py | 从真实classifier输入验证前置条件与轻量边界 | 防止纯前端测试环境再遗漏 | R6 |
| 本 Change | 当前计划及有效证据 | 项目独立升级追溯 | R4/E4 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 全部 frontend Vitest；Vue 编译、响应式、组件行为 |
| 接口 / 契约 | required | generate:api 后生成 Client 与 Git 一致 |
| 集成 / 持久化 / 运行依赖 | required | npm ci、lock diff、audit；正式 CI 按唯一 classifier 选择集成层 |
| 用户 / 工作流验收 | required | frontend Browser Mock Acceptance；Human Local Acceptance 不适用：无新增可见行为，也无人工路径可直接验证公告消除 |
| 跨组件关键路径 | required | 正式 CI 与 Compose Golden Path，按仓库实际选择器执行 |
| 外部依赖 / 供应方探测 | not_applicable | npm 元数据核实已完成；不需真实飞书/TikHub 等业务 Provider |
| 构建 / 打包 / 运行 | required | lint/typecheck/build 与 locked 安装 |
| 文档 / 治理 / 其他 | required | canonical Issue/Change/PR 校验、Completion/Review、Ready Check；版本事实由 Manifest/lock 唯一维护 |

## 验证计划

旧锁 audit 已真实失败；Manifest/lock 任务不用新增镜像版本断言的永久测试。替代证据为 npm 解析/安装/审计及现有行为回归。执行正式 frontend scripts、生成 Client 一致性和项目 changed-scope preflight；Windows npm.cmd原生子进程限制如实报告，必要命令从PowerShell执行；本次CI仅补齐已证实缺失的正式测试环境。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 编译/渲染回归及无关 lock 漂移 | 完整 frontend 回归与逐包 diff |
| 兼容性 | 精确补丁，无框架/工具链切换 | #704 批准范围与 npm 元数据 |
| 数据 / Migration | 不适用，无相关源码变化 | 不生成或运行业务迁移 |
| 部署 / 运行 | 构建依赖重新 npm ci | 不执行真实部署 |
| 回滚 / 恢复 | 普通 PR 恢复两个文件会重新引入已知审计失败 | 无数据回滚，不将回滚声明为安全修复 |

# 文档、依赖、部署与发布影响

长期文档不适用：既有技术栈和流程未变，精确版本由 Manifest/lock 维护，不复制平行版本列表。依赖仅为已批准的三组补丁。无配置、Secret、生产 Contract、Migration 或部署步骤改变。Release/Deploy 未授权且不执行。

# 完成审计

- [x] upstream_re_read：重新读取用户决定与 live #704，独立重建 AC1–AC6。
- [x] change_coverage：核对三组精确补丁、无关漂移、回归和平台交付全部责任。
- [x] reverse_audit：Manifest → lock → npm ci 实际树 → audit → 现有用户/构建路径；公共业务入口无变化。
- [x] unresolved_cleared：所有预合并实现 not_satisfied 清零，独立审查无阻塞；current-head CI 仍须在合并前通过，post-merge 责任保留且不冒充完成。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | cef8629 / Node24.19.0 npm11.17.0 | npm --prefix frontend audit --json | exit1；3 high/1 moderate | 旧 lock 的真实安全审计 Red |
| V2 | 当前 Source / Issue704 | canonical prepare/validate-issue create、平台读回同检 | PASS | 独立 Requirement 已持久化且符合机器 Contract |
| V3 | 新 Manifest/lock / Node24.19.0 npm11.17.0 | verify_security_lock.py；npm package-lock-only 普通校验 | PASS，12 节点、0 无关变化 | 三组批准补丁与原 registry/integrity 策略，无新增直接依赖/override |
| V4 | 新 lock / 本地 Windows | npm --prefix frontend ci --no-audit；npm audit --json；npm ls | 全部 exit0；漏洞 total0 | 正式安装可复现，三公告均不再命中 |
| V5 | 新 lock / 本地 Windows、Chrome | frontend lint；test -- --run；build（含 ts7/vue typecheck）；test:e2e | 全部 exit0；38 文件306 unit、205 Browser Mock PASS；858 modules build | 补丁升级后的既有组件、页面流程与产物兼容 |
| V6 | 新 lock / 当前 OpenAPI | frontend generate:api；git diff --exit-code -- frontend/src/generated | exit0，无生成 Client 差异 | 现行 API 消费者不漂移 |
| V7 | 当前 Change/文档/Source | check_docs.py；canonical validate-change；validate_changed.py --base origin/main | 全部 exit0；frontend_only，changed3 | 文档导航和载体合规；采用唯一 classifier 的4个前端命令已逐项执行，未声称 Windows 原生 --execute 成功 |
| V8 | head8c98d421/base cef8629 | 独立 Requirement/代码/证据 Completion Review | A1/A2 PASS，SEC-PF-01 CLOSED | 冻结依赖文件、实际安装物与本地证据满足 AC1–AC4；最终载体只允许更新本 Change，两个依赖 blob 不变 |

## 未验证内容与剩余风险

依赖实现及本地Green已完成，旧依赖边界Review PASS；Ready CI37728521340已在前端Prompt解析测试失败，依赖审计PASS。epoch3正式测试前置、局部Green与独立A1/A2已PASS；最终载体升L3并补齐备选方案，仍须新head正式CI全绿，禁止提前merge。构建有既有 chunk size warning，未降低预算或改切包策略。真实部署和生产 Provider 不在此依赖修复范围。

## 交付状态

本地任务分支、独立 Requirement #704 与早期 Draft PR #705 已建立；进入 Ready 载体与正式 CI 阶段。未合并、未归档、未关闭 Issue；main-fresh、归档、Acceptance/Closure 与 cleanup 保留为后续必需动作。

## 备注

原 #702/#703 保持原意图和独立验收；本任务完成后其 Final Ready 集成最新 main 并重新取得所需证据。

## epoch 3：正式前端测试环境修正

上游live #704已追加AC6，保留AC1–AC5原验收责任；PR #705已返回Draft。失败日志为.runtime/sync-local-feishu-20261008/security-ci-failure.log。生产test从.venv调用正式PromptTaxonomyLoader，纯前端CI漏掉锁定Python环境；不复制解析器或改断言来规避。

Workflow Responsibility Audit / Evidence Preservation Mapping：

| 责任 / 前置 | 原位置与失败边界 | 修正与证据保持 |
| --- | --- | --- |
| Python setup、下载缓存、版本校验与uv frozen安装 | quality-core现有4处条件仅backend/repository_quality，frontend_only遗漏 | 仅加入frontend_required；Python3.14.7/uv锁、uv lock --check、uv sync --locked和正式package安装保持；不新增依赖或安装脚本 |
| frontend lint/unit/build/browser与Prompt事实读取 | quality-core原前端step，305 pass/1 ENOENT | 原测试、全量选择器、失败退出、审计high阈值均保持；不使用系统Python降级、PYTHONPATH或平行Prompt解析 |
| Draft/metadata/main证据复用 | Draft在安装前fail closed，metadata/main reuse classifier将产品flags置false | 原门禁/事件/同tree复用规则保持，无产品flags时不新增安装 |
| 后端/Contract/PostgreSQL/Full-stack/Compose/Tooling | 原独立Owner及classifier | 全部保持；CI自身diff按原classifier full保守验证，无删除或转移责任 |

R6局部修复满足：新增回归Red→Green、相关6文件100pass。R4独立A1/A2 PASS；SEC-CI-01风险等级已修正为L3，最终载体定点复核后启动新head正式CI；4个源码blob不变。旧依赖两blob不变，既有306/205本地回归继续按其实际范围保留。

| V9 | epoch3现有CI4处条件及真实classifier | 新前置回归Red：4 failed/4 passed；修正后pytest test_ci_scope/test_ci_workflow_structure/test_ci_test_impact_optimization/test_ci_main_evidence_reuse/test_actions_runner_optimization/test_validate_changed | 100 passed、exit0；ruff format/check PASS，check_docs PASS | frontend-only正式解析器环境、docs/governance无额外安装、现有事件与复用责任保持 |

V9第一次广测试因沙箱临时目录权限出现3个setup errors（97pass），独占路径仍受沙箱访问限制；随后在本机权限下使用新的本任务专用basetemp执行相同100项全部通过，没有修改测试、断言或依赖。旧依赖文件无进一步变化；正式Runner的原始ENOENT仍需新head完整CI验证切断。

CI改动风险升级依据：当前canonical 19_CI审查升级门禁.md（source blob c60ed155439bbe8cefa347a972863751f8255844）将CI变更最低风险设为L3；本轮epoch3相应升级载体，继续使用既有两阶段独立Review与完整正式CI，不改变源码或授权边界。




V10：epoch3独立A1需求覆盖、A2四条件表达式与局部证据PASS；Reviewer独立按完整布尔逻辑求值8场景，核对Draft/metadata/main复用及原产品检查段字节不变。SEC-CI-01仅要求风险分类L3，本载体按Source修正；CI blob d5c53fc7d936271c779f1d07bd820f6da1a5a02d、回归blob 0b76f228461be8ce4c5c8a2d13e432d6bcdd6536和两个依赖blob均保持91d14315冻结版本。最终Carrier及new-head CI分别取证，不替代mainfresh/归档/Closure。

