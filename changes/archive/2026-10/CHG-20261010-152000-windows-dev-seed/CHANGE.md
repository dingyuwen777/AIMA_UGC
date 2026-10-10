---
schema: coding-change/v1
id: CHG-20261010-152000-windows-dev-seed
title: Windows 源码开发安全恢复共享快照
level: L3
status: done
owner: Codex
branch: feature/716-windows-dev-seed
created: 2026-10-10T15:20:00+08:00
updated: 2026-10-10
completion_gate: required
depends_on: []
affected_areas:
  - development
  - data-restore
affected_paths:
  - scripts/dev/backend.py
  - scripts/dev/seed_data.py
  - scripts/dev/recent_snapshot.py
  - tests/unit/test_dev_seed.py
  - tests/unit/test_local_dev_runtime.py
  - tests/integration/platform/test_dev_seed_postgres.py
  - devdata/seed
  - .gitattributes
  - .dockerignore
  - docs/02_环境运行与部署.md
contracts:
  - aima-recent-content-postgresql.v1
  - aima-dev-seed-state.v1
data_changes:
  - 仅固定本地空开发库初导
  - 人工确认后重置固定开发库
---

# 变更摘要

源码开发第一次启动从 Git 共享快照恢复业务数据；已有 Schema 保守跳过，失败后保留现场并拒绝继续业务启动。唯一上游需求为 [#716](https://github.com/dingyuwen777/AIMA_UGC/issues/716)。

# 背景、现状与问题

## 背景

用户要求 Windows + uv 原命令自动初始化，不安装 Bash/WSL/宿主 PostgreSQL CLI，并交付原始压缩包。

## 当前现状

main 7bc3fd3 启动器在 PostgreSQL ready 后直接 Migration；服务器脚本只允许新建其它名称数据库，不能直接用于固定 aima_ugc。实际包 PG18、0082、103表、632文件、1.65GB。

## 问题、根因或约束

不能根据 contents=0 推断库为空，不能移除服务器原保护后对任意库导入。必须校验固定 Docker 身份、实际 Schema、文件与 FK，并阻止旧任务复跑。

## 不修改的后果

开发者需手工恢复且可能误覆已有数据，Windows 无原生自动入口。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 固定容器/卷/DB/user，先迁移后 Worker/API | scripts/dev/backend.py、local_runtime.py | 仅增加 ready 后恢复 |
| E2 | CSV无表头，列序来自manifest，NULL为\\N；原导入取消Job、禁用计划/Provider | 原服务器脚本 SHA B896D2AF5739597D18A7CAA2D3F17F44DC6023F0EBE9CFE68EF2B37FC6D1E3E8 | 复用原格式/SQL语义 |
| E3 | 包内0082是当前0087的已知祖先 | migrations/versions；真实恢复后 Alembic 输出20261010_0087 | 先原Schema恢复再正常upgrade |
| E4 | scripts/dev变更现有classifier要求full | scripts/quality/classify_ci_scope.py | 不建立新映射或降低门禁 |
| E5 | 独立前置审查D1–D6 | 本轮独立只读审查 | 目标身份/失败关闭/Windows/FK/文件/空间 |

## 推断与待确认

远程 LFS 已正常上传，并由全新 clone 的独立缓存下载、核对大小与 SHA；真实包完整校验、隔离恢复、Migration和正式API读取已执行，不把元数据扫描当完整校验。Windows 临时 bind 目录的冷查询耗时较高，不能由此宣称生产性能达标。

# 目标、成功标准与非目标

## 目标

原命令安全初始化，重复启动复用数据，Windows/Linux共同Python实现。

## 成功标准

成功标准唯一由 #716 AC1–AC10 维护；下文R行只映射执行与证据，不另立需求。

## 范围

启动接入、专用状态与维护CLI、单一归档恢复模块、LFS/镜像排除、定向测试、文档。

## 非目标

不改前端、业务API、依赖、正式调度/生产备份/部署，不改用户已有env示例。

## 必须保持不变

固定开发DB/卷/身份，用户已有数据、AI原结论、正式Worker机制、合法本地Provider调试，Compose入口。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | Parent单Writer，独立Reviewer只读 | 项目规则 | 无共享写冲突 |
| 接口与契约 | 原v1格式，新增专用CLI | #716 | 不变更业务API |
| 数据与迁移 | 无应用对象才初导；旧schema正常upgrade | E1/E3 | 无新Migration |
| 错误与失败语义 | 阶段化脱敏错误，失败marker拒绝启动 | E5 | 不自动drop重试 |
| 兼容性 | 无包/CI/prepare不导入，已有Schema跳过 | #716 | 原启动行为保留 |
| 部署与回滚 | 仅源码入口，回滚代码不删本地数据 | #716 | 无生产操作 |

# 修改方案与决策依据

## 最小充分方案

1. 建立文件/决策失败测试 → tests/unit/test_dev_seed.py → 验证拒绝条件。
2. 专用seed入口与唯一共享恢复模块 → scripts/dev → 流式验证/恢复、固定目标、互斥与失败保护；合成PG验证。
3. backend接入 → ready后migration前，prepare/skip/CI不恢复；启动回归与Compose隔离检查。
4. LFS/镜像排除与文档 → 原包共享，不进入镜像；真实包一次隔离恢复/正式查询。
5. Completion、独立Review、current-head CI、正常合并及原生收口。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| 保守Schema skip | E1/E5及用户允许 | 无需冒险证明全表为空 |
| 原SQL单一模块 | E2 | 避免多套恢复业务规则 |
| 使用已有classifier | E4 | 唯一影响面Owner |

## 备选方案与取舍

Bash/WSL违反用户环境约束；新常驻DB违反固定aima_ugc；完整Schema空库强制恢复增加误覆风险，用户允许保守跳过；因此无额外平台或配置。

# 需求追溯

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 原命令ready后迁移前检查；各skip入口与Compose/frontend隔离 | #716 / AC1 | satisfied | backend生命周期测试、validate-only/CMD命令、test_compose_and_frontend_do_not_invoke_seed；V1/V4 |
| R2 | 固定本地Docker/数据库身份；已有Schema不覆盖 | #716 / AC2 | satisfied | Docker context优先级/卷/身份单元测试、真实PG空库/已有库/并发保护；V1/V2 |
| R3 | 原v1文件与Schema/CSV/Artifact/FK及版本校验 | #716 / AC3 | satisfied | 全包verify；103表真实COPY/全部FK和行数审计；0082正常升级0087；V2/V3 |
| R4 | Windows安全路径、空间检查与流式处理，不增加宿主工具 | #716 / AC4 | satisfied | 路径/成员/磁盘不足测试；Windows PowerShell/CMD及无Bash实际恢复；V1/V3/V4 |
| R5 | 帖子、评论/回复、AI/人工、品牌车型及Artifact恢复可查询 | #716 / AC5 | satisfied | 合成PG数据和真实包行数/632文件通过；正式API读取帖子/AI/人工/评论回复/筛选/品牌车型/工作台，V2/V3/V9 |
| R6 | 历史Job取消，计划/Provider停用，成功AI结论保持 | #716 / AC6 | satisfied | 真实包queued/running Job=0、enabled/default Provider=0、enabled计划=0；合成PG验证AI/Run不改写；V2/V3 |
| R7 | 缓存不替代DB事实；跨checkout失败保护；重复启动不展开全包 | #716 / AC7 | satisfied | 共享状态/Artifact根绑定/失败skip拒绝/租约测试；真实包重复初始化通过；V1/V2/V3 |
| R8 | status/verify/dry-run只读，人工确认reset与中断保护 | #716 / AC8 | satisfied | 真实PG错误确认/活跃连接/外来OID/删库后失败/建库后失败恢复和数据哨兵验证；V2 |
| R9 | 原包LFS交付、镜像排除、CI合成数据 | #716 / AC9 | satisfied | V10全新远程clone独立LFS下载，原包大小/SHA一致；Dockerignore、CI隔离与合成测试通过 |
| R10 | 本施工单元的必要验证与独立Review | #716 / AC10 | satisfied | V1–V10、四项修复及后续专项独立复核；实现SHA保持，全部本地必要层通过 |
| R11 | 当前HEAD CI、正常合并、main-fresh、原生归档与Issue闭环 | #716 / AC10 | explicitly_deferred | 正式Owner为Implementation PR required checks与仓库原生ci.yml/change-archive.yml；AGENTS.md及docs/blueprint/06_开发约束与分阶段实施.md规定先Active Ready再PR/CI/merge，合并后归档和Closure；仅按依赖顺序后置，不豁免且未声称AC10完成 |

# 计划改动

保持上述affected_paths；原包不重编码/重打包；不混入两个env示例现有用户修改。独立review仅读，Parent集成前核对revision。

# 验证矩阵

| 维度 | 结论 | 证据计划 |
| --- | --- | --- |
| 行为/Unit/Component | required | 文件/决策/Windows路径/失败状态 |
| 接口/Contract | required | v1归档、CLI退出码及状态格式 |
| 集成/Persistence/Runtime Dependency | required | 合成真实PG18恢复/闭包/序列 |
| 用户/Workflow Acceptance | required | Windows PowerShell/CMD及原启动回归 |
| 跨组件Golden Path | required | 真实包恢复、Migration、正式声音广场/详情查询 |
| 外部依赖Probe | not_applicable | 不调用付费Provider或生产飞书 |
| Build/Package/Runtime | required | Dockercontext排除、LFS交付、适用CI |
| Docs/Governance/Other | required | 文档/secret/Change/Completion |

# 验证计划

目标pytest、既有启动器单元、Ruff/mypy、隔离Docker18合成与真实快照、validate_changed.py --base origin/main、现有required CI。大包不进入每次CI。人工本地验收 USER_WAIVED（用户要求实施并合并，不声称人工已验收）。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 误覆/半库/任务外发/文件冲突 | D1–D6，写前检查、排他、失败状态、取消历史Job |
| 兼容性 | 固定DB与旧入口保持 | 仅源码启动增加安全检查 |
| 数据 / Migration | 无新增Schema；0082正常upgrade0087 | 正式Alembic真实执行 |
| 部署 / 运行 | 不部署，不触碰用户在用开发库 | 自有隔离容器 |
| 回滚 / 恢复 | revert代码保留DB及配置；失败人工确认reset | 不自动删除 |

# 文档、依赖、部署与发布影响

更新环境指南及快照README；无依赖/Runtime/Secret变更。归档可信来源为用户批准的Git快照，schema.dump执行DDL，不能当任意不可信上传文件。无Release/部署授权和动作。

# 完成审计

- [x] upstream_re_read：Ready前重新读取live #716（updatedAt=2026-10-10T07:18:08Z），与原附件及确认范围逐项比较；主分支仍7bc3fd3。
- [x] change_coverage：AC1–AC9各项对应R1–R9及直接Evidence；AC10实现/验证/Review对应R10，平台依赖部分由R11及正式交付Owner后续证明，Issue保持open。
- [x] reverse_audit：CLI/flags→parser/handler→状态/退出码与副作用；原命令→租约→恢复→Migration→正式API读取；CSV/Artifact→真实FK/序列/投影→评论、AI、品牌车型和工作台；历史可执行Job=0、计划/Provider停用。前端/Compose不自动恢复，测试分层没有互相冒充。
- [x] unresolved_cleared：本地施工范围not_satisfied清零；后置平台检查有项目正式顺序和Owner，不以延期冒充任务完成。新增永久单元与PG测试分别证明文件/决策和真实持久化风险，无复制业务实现的冗余验证资产；临时大包/API专项脚本合并后清理。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V0 | main7bc3fd3 | 前置只读审查/manifest扫描 | 可实施 | 仅设计事实，不证明恢复 |
| V1 | Windows Python3.14.7；当前功能代码 | pytest tests/unit/test_dev_seed.py tests/unit/test_local_dev_runtime.py | 48 passed、1 skipped（Windows符号链接权限） | 路径、状态、身份、skip和完整启动租约 |
| V2 | 自有Docker PostgreSQL18.4；最终代码 | pytest tests/integration/platform/test_dev_seed_postgres.py | 13 passed，116.52s | COPY/外键/序列/AI/评论/Artifact、并发、跨checkout、reset恢复及真实autovacuum |
| V3 | 原包SHA d95862f9149f04857d3841c5cd02b46ae01c0add32408f8066da4f9f734ebc6c；自有E盘隔离PG | seed_data.py verify；initialize；重复initialize；alembic upgrade head | 103表、639163帖子、22评论、219568AI、632实际文件、missing=0；重复保护通过；0087 | 原包可恢复，不只验证fixture；旧可执行Job/启用Provider/启用计划均0 |
| V4 | Windows PowerShell/CMD | seed_data.py --help；backend.py --validate-only | exit0 | 原命令入口与Windows原生CLI可用 |
| V5 | main基线及本轮功能代码 | pytest tests/unit tests/contracts tests/api | 2697 passed、23 skipped、12 subtests，342.18s | 后端/API/Contract现有行为回归；后续autovacuum修复由V2覆盖 |
| V6 | 当前前端未改源代码 | npm --prefix frontend run lint；npm --prefix frontend run test -- --run；npm --prefix frontend run build；npm --prefix frontend run test:e2e -- --workers=3 --output=../.runtime/dev/seed-implementation/playwright-results | Lint通过；42文件361测试通过；Typecheck/Build通过；218浏览器测试通过（4.9m） | 既有前端不回退；既有大chunk提示保持 |
| V7 | 最终源代码 | Ruff check/format；mypy backend/src scripts/dev/seed_data.py scripts/dev/recent_snapshot.py；generate.py --check | Ruff通过，482个源文件类型检查通过，生成Contract一致 | 静态/生成契约一致 |
| V8 | 当前文档/规则 | check_docs、scan_secrets、check_docs_facts、check_agent_governance、架构/表Owner检查 | exit0 | 文档/Secret与模块边界保持 |
| V9 | 实际恢复DB；最终entrypoints.api_main.app；未替换Service/Repository | TestClient读取ready、详情、一级评论/回复、人工锁、Taxonomy、筛选目录、数据修订、品牌车型、工作台声音流；先前bootstrap同Service默认/AI筛选列表 | 全部200；人工锁1、品牌6、车型页50、声音流10；旧Job和计划仍0 | 真实数据在正式API装配可读；开发身份用于本地测试，不作为生产飞书授权验收 |
| V10 | 远程分支实现e2f7d96；2026-10-10T21:10:49+08:00；全新E盘clone、独立.git/lfs缓存 | 正常git push；GIT_LFS_SKIP_SMUDGE clone后git lfs pull，仅指定原包；文件大小与SHA-256核对 | 远程下载1,646,496,154 bytes，SHA d95862f9149f04857d3841c5cd02b46ae01c0add32408f8066da4f9f734ebc6c，与原包一致 | 不是本地缓存副本，团队能从远程获得完整原始包；测试副本按归属清理 |

### 独立 Review 与失败修复

Parent 单Writer；独立只读Reviewer审查后形成整批F1–F4，修复后逐项复核并关闭：共享卷状态与Artifact根绑定、完整启动租约、Docker context优先级、reset删库/建库中断及陌生OID保护。最后一项有真实PG Red→Green与未变哨兵数据证明。

真实大包重复初始化又暴露autovacuum误判：旧代码真实PG用例1 failed/12 deselected；仅排除服务端backend_type='autovacuum worker'后最终V2全部13 passed，普通idle客户端仍拒绝。独立复核该修复NO_FINDINGS；未放行其它后台类型或客户端可伪造的application_name。

最终reviewed SHA256：backend.py=`FDCA649405201EF5A3D8D7E91E2C2C9179DD221975C3B1FFBB03055F774CBE4C`；seed_data.py=`0897C8669E143747E6E8C5A39DFAE0F0F53CB9DA804AB24CE6DAC5E72ACFE86B`；recent_snapshot.py=`E87C8F58730FD4E9ACFD60D82A88DB96A0BFC49A3F8F0B548500DAE1A5E44717`。后续若代码改变须重核受影响Evidence。

全包临时展开5,507,135,452 bytes；恢复DB约4,381,300,415 bytes，Artifact935,508,047 bytes。测试隔离目录与容器在合并后按精确归属删除，正式1,646,496,154-byte LFS快照保留。开发库/Secret与用户env编辑保持。

本轮曾遇到沙箱前端TEMP权限错误、D盘LFS未跟踪过滤临时文件积累导致空间不足、脚本单独mypy未解析项目源码，以及新增单测两处默认GBK读取；已分别使用任务TEMP、正常暂存LFS原包并删除本次失败tmp、以正式backend/src加新增脚本作为静态检查范围、显式UTF-8读取复验通过。V1最终绿色输出保存为unit-utf8-final.log，unit-reviewed-final.log是修复前失败记录，不冒充成功。Windows绑定目录的冷查询耗时不作为生产性能证据。

API专项首段默认和AI筛选列表各5条、详情及AI结果通过；随后因把root=self的一级评论误选成回复样本而失败。更正为实际二级回复后，发现测试使用bootstrap工厂缺扩展品牌路由；改为正式entrypoints.api_main.app，全部扩展查询通过。这两处均属临时验收接线修正，未据此修改业务代码。真实包13条一级评论/9条回复。无日期工作台声音流查询389.46s返回200，取消动作匹配时已无该活动查询；随后带真实页面日期范围读取15.94s返回200。保留慢查询事实，不伪称取消成功或生产性能通过。

PR #718 首轮HEAD 83701da2 的主CI在单元测试发现环境隔离遗漏：runner同时设置CI/GITHUB_ACTIONS，已有Schema保留用例先走CI跳过分支，1 failed、2115 passed、10 skipped。只修单测两处各显式清除这两个外部标志，ci=True参数仍随后设置CI以验证对应分支；不改生产跳过规则、不降低原断言。CI=true本地目标Red为1 failed；双标志重现仍Red后最终两个单元文件48 passed、1 skipped（github-env-green.log，0.83s），Ruff check/format通过。首次沙箱basetemp权限错误不作为目标Red。真实PG workspace原已清两标志，无需改变。该修复由独立Reviewer另行复核后提交并重新取得当前HEAD CI；首轮Compose、离线候选回放、Windows/Linux工具通过仅作为首轮事实，不代替新HEAD门禁。

独立Repair Review结论NO_FINDINGS_WITHIN_SCOPE：复核live #716/PR #718、最终4行增量、完整双标志Red/Green及相邻生产/PG fixture，独立Ruff check/format exit0；测试SHA256为2a9ccaf7244819f0118fec695bd608072a9f8c4054c3fd130b04723472ce293e，三份生产SHA不变。新HEAD仍须取得平台CI，本结论不冒充新CI通过。

## 未验证内容与剩余风险

LFS远程证明已取得；current-head CI、main-fresh及归档/Issue关闭依正常交付顺序执行，未满足前不合并或关闭Issue。正式生产、飞书企业授权与服务器性能不在任务范围；没有运行付费Provider或生产部署。

## 交付状态

实现checkpoint e2f7d961829e4ed921d2bf1ce839f4d2a98c2b0d已正常推送任务分支，LFS独立远程下载通过；最终审计记录随后提交并进入PR/current-head CI。Active Change保持ready_for_review，归档由仓库原生Workflow负责。用户授权正常合并，禁止绕过保护；尚未发生的PR/CI/合并/归档不标完成。

## 备注

父任务decision_epoch=1，单Writer；一名独立reviewer。
