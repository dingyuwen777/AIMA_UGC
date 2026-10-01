---
schema: coding-change/v1
id: CHG-20261001-112055-analysis-capacity-feedback
title: 修正打标容量观测并加快不同规模任务的自适应调度
level: L3
status: ready_for_review
owner: assistant
branch: fix/analysis-capacity-feedback
created: 2026-10-01 11:20:55 +08:00
updated: 2026-10-02
completion_gate: required
depends_on: []
affected_areas:
  - analysis
  - llm
  - testing
  - documentation
affected_paths:
  - backend/src/aima_ugc
  - tests
  - docs
  - migrations
contracts:
  - Analysis Run 冻结容量协议
  - LLM 物理请求安全审计
data_changes:
  - 既有容量 Profile JSON 中的版本化观测和有期限分片预留
---

# 变更摘要

修正打标的容量证据、机器调度和持续恢复，使正常内容尽快推进且每条成功才正常完整退出。当前本地修复已完成隔离验证；本次授权将全部现有本地修改（含用户现有 Prompt 编辑）经受保护 PR 交付 main。远程 CI、合并、main-fresh、归档和清理尚未完成，不以本地 Ready 代替。

# 背景、现状与问题

## 背景

正式上游为 [docs/blueprint/07_技术决策与实施门禁.md](../../../docs/blueprint/07_技术决策与实施门禁.md) 第35/36节与稳定验收标识，以及本轮用户明确批准的 Git 交付、隔离验证和两平台自适应要求。

## 当前现状

本地分支 fix/analysis-capacity-feedback 基于 main 64bfade138e6cdf0f86e8d8961a0415b8f994ea8。epoch8 实现与审查资产完整，尚未提交或推送。现有控制器、持久 Profile 与 Job Runtime 是唯一生产实现。

## 问题、根因或约束

迟到旧发送错误重复压低新容量；短窗峰值和稀疏格式失败形成错误升降档；等待与退避冒充物理占用；资源/Lease/分片投放不一致；有限执行周期耗尽后 pending 未完整接续。新增 Git 交付必须取得当前 Head 的正式门禁，不能复用本地 PASS 冒充远程通过。

## 不修改的后果

健康模型的可用吞吐被错误限制，正常或未投放内容可能停留；单次本地验证无法证明受保护集成结果。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | epoch8 的38项冻结与用户 Prompt 哈希有完整清单 | [changes/active/CHG-20261001-112055-analysis-capacity-feedback/REVIEW_BASELINE.json](REVIEW_BASELINE.json) | 按字节判断旧证据可复用范围 |
| E2 | Windows、Linux wheel、真实PG和浏览器关键链已隔离运行 | [changes/active/CHG-20261001-112055-analysis-capacity-feedback/EVIDENCE.md](EVIDENCE.md) | 保留真实结果与最初环境失败，不重复无效测试 |
| E3 | 原阻塞项已由独立 Reviewer 关闭 | [changes/active/CHG-20261001-112055-analysis-capacity-feedback/REVIEW.md](REVIEW.md) | 新交付审查按 lineage 检查 delta 与直接相邻边界 |
| E4 | main Ruleset要求三个检查、最新base与线程解决 | 2026-10-02 gh api rules/branches/main | 通过PR和预期Head SHA合并，不绕过门禁 |

## 推断与待确认

真实付费模型吞吐、服务器具体加速倍数、Gold Set准确率仍未实测；正式Blueprint AC9明确延期，不将模拟冒充实际收益。远程 current-head/main-fresh Evidence 在正式交付阶段取得。

# 目标、成功标准与非目标

## 目标

同一代码持续探索不同模型和机器可用的成功入库吞吐；pending不冒充成功，保留质量与恢复边界；当前修改按正式PR交付。

## 成功标准

- [x] R1–R21实现、文档和本轮本地Evidence对应当前生产边界。
- [x] 原审查阻塞全部关闭，真实网络停止及正常完整成功边界可独立验证。
- [ ] 当前Head required CI、受保护merge、main-fresh、原生Archive和任务分支清理全部完成；这些交付状态不由本地Ready声明代替。

## 范围

LLM反馈、容量Owner/Planner/Worker/Recovery、有效资源、对应测试/文档、0076/0077降级guard、用户现有Prompt编辑与本Change交付。

## 非目标

PR #591/#662 在本次交付后由用户要求的新Codex会话依次收敛；不在本Change混入。不升级依赖、不新增业务表，不部署或操作用户在用服务/业务库，不进行收费模型性能基准。

## 必须保持不变

思考模式、严格Validator/repair/judge、用户Prompt编辑、历史冻结Run、幂等/Fence/取消、公共HTTP字段、依赖、启动方式与Migration head保持。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | Analysis/LLM与机器资源Owner修复，后续两PR分开 | E1与用户当前授权 | 当前分支单写入者 |
| 接口与契约 | v2冻结策略及控制3，旧版本不补写；HTTP字段不变 | Blueprint AC2/6/12 | 新协议成功语义更严格 |
| 数据与迁移 | 复用派生Profile JSON；既有Migration仅降级guard | E1/E2 | 没有新DDL/head |
| 错误与失败语义 | Validation持续pending；真实网络五分钟、系统硬错、取消显式停止 | Blueprint AC12–15/19 | 永久非法输出不承诺最终合法 |
| 兼容性 | 保留冻结v1与旧请求恢复边界，用户Prompt原字节纳入提交 | E1/E2 | 不改变在用DB配置 |
| 部署与回滚 | 不重启服务；旧代码回退前排空新协议Run/预留再重建派生Profile | Blueprint35/36 | 业务结果保留 |

# 修改方案与决策依据

## 最小充分方案

容量观测按真实在途积分与同档成熟成功证据 → Controller/Profile → 单元与事件模拟。
同Profile行锁预留C/RPS及Fence → Repository/Worker/Planner → 真实隔离PG和取消/接管回归。
有效CPU/内存/cgroup/DB与共享Lease身份 → 运行进程池 → Windows/Linux正式运行证据。
有限Job原子后继、成功项不重发 → Recovery/Item/Request Owner → 完整结果与失败边界验收。
正式文档/完成审计/独立Review → 当前Head CI → 受保护合并/main-fresh/原生Archive/清理；只按真实状态推进。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 | E1/E2 | 修正已有观测与Owner，切断根因且不建立平行控制器 |
| D2 | E2/E3 | 持久后继复用正式Job，保留Deadline与Fence而非无限延长租约 |
| D3 | E4 | 正式文件作为Requirement Source，实际CI/Review通过后受保护合并 |

## 备选方案与取舍

静态提高C不能修正错误反馈或跨分片重复承诺，不能适配机器与模型。改用全新异步调度/容量表会增加兼容与部署成本，当前无必要事实。选用现有线程/进程/单Profile和Job机制内完整修复，并以可控模拟、真实事务及两平台证据验证。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 从根因修正占用、超时和恢复机制 | docs/blueprint/07_技术决策与实施门禁.md#AC4 | satisfied | 在途积分包含跨窗未完成请求，阶段归属阻止旧请求证明新容量；1/34 超时、尾部、固定秒数恢复和审计排队时间回归通过 |
| R2 | 小任务及大数据量都快速利用可用容量，适配不同模型 | docs/blueprint/07_技术决策与实施门禁.md#AC8 | satisfied | 正式 API/Planner/Worker/Fake HTTP/PG 的 200 条全入库、物理峰值 100；200000 条事件模拟覆盖 100/500/2500 及 2500→800→2500；未知端点反馈学习 |
| R3 | 纳入机器资源、执行槽位和数据库背压 | docs/blueprint/07_技术决策与实施门禁.md#AC17 | satisfied | 有效 CPU、可用内存、CPU 差值压力和提交速率共同限定本地许可；资源受限与采样未知、背压恢复回归通过；Planner 按目标数/分片槽位投放 |
| R4 | 保持思考模式、Prompt、Validator 与打标准确性机制 | user:20261001-preserve-thinking-and-quality / AC6 | satisfied | HTTP 请求体仍只有 model/messages/response_format，没有关闭 thinking 或改变 effort/输出长度；用户 Prompt 保留；Validator、repair/judge、空值及持久恢复相关回归通过；不宣称量化语义准确率 |
| R5 | 跨 Run/Shard、取消、Fence、幂等、持久恢复正确 | docs/blueprint/07_技术决策与实施门禁.md#AC14 | satisfied | 多事务预留、零份额、缩容排空、尾部借额、旧 Fence 接管、配置热启动、恢复与终态调度的隔离 PG 回归通过；v1 冻结 45 秒/256 不改写 |
| R6 | 本地隔离验证，保护其他代码和依赖数据库 | docs/blueprint/07_技术决策与实施门禁.md#AC16 | satisfied | DB 127.0.0.1:55478/aima_capacity_feedback 独占容器和任务目录；API/Fake LLM/Frontend 使用 55480/55481/55479；只停止准确 PID/命令行匹配的本次服务；不连接用户 DB |
| R7 | Git交付遵守当前用户授权，保护已有修改并通过受保护PR集成 | docs/blueprint/07_技术决策与实施门禁.md#AC10 | satisfied | 当前授权与main Ruleset已核验，现有修复和用户Prompt原字节保留；current-head CI/merge/main-fresh/Archive按独立交付阶段执行，不宣称已完成 |
| R8 | Windows 启动器和实际解释器 PID 不同仍能准确扩容、保护忙碌 Worker | docs/blueprint/07_技术决策与实施门禁.md#AC17 | satisfied | 模拟包装 PID 与 Lease 不同仍扩容；内存缩容仅停止空闲 Lease；Windows 真启动器/解释器句柄及两系统正式 Worker Pool 通过 |
| R9 | 区分可发送工作、在途工作和延迟重试；尾部不形成错误容量证据 | docs/blueprint/07_技术决策与实施门禁.md#AC4 | satisfied | has_ready 复用正式重试条件并排除在途/未提交；1024目标/111占用不回退、不更新安全/不安全或吞吐记忆；两系统就绪与恢复回归通过 |
| R10 | 分片尾部能补充下一片，保持物理占用、Fence、幂等和取消 | docs/blueprint/07_技术决策与实施门禁.md#AC14 | satisfied | 真实 Fake HTTP 慢请求未完成时至少24项已入库；最终36请求/36成功且3片退出；取消、接管、份额、waiting Run 与终态相关回归通过 |
| R11 | 按宿主或容器有效配额测量 CPU 压力，配额变化后恢复探测 | docs/blueprint/07_技术决策与实施门禁.md#AC17 | satisfied | Windows 系统计数与 Linux host 回退、cgroup v1/v2、配额变化/计数复位回归；真实 Linux 0.5核容器压力1.0；不同资源/16核64GiB配置矩阵通过 |
| R12 | 保持原输出与思考行为，代码和启动入口可用，不影响用户服务 | docs/blueprint/07_技术决策与实施门禁.md#AC16 | satisfied | Windows357passed；Linux正式wheel354passed/1Windows专属skip；最终池13passed；思考请求体、用户Prompt SHA256、类型/Contract/文档检查通过 |
| R13 | 迟到旧发送错误不反复降低新的 C/RPS，Future 不冒充物理占用 | docs/blueprint/07_技术决策与实施门禁.md#AC4 | satisfied | Red 复现后两系统最终诊断/恢复组各53passed，RPS健康恢复成熟、真实多片迟到429及预留回归通过 |
| R14 | 格式错误持续只修复未成功内容，真实断网五分钟停止且兼容旧协议 | docs/blueprint/07_技术决策与实施门禁.md#AC12 | satisfied | v2格式超过十分钟仍修复成功、实际失败跨度300秒停止、HTTP/池等待排除与legacy v1两系统回归通过 |
| R15 | 低 C 下退避不空占，正常及未投放内容推进，有 pending 不成功完成 | docs/blueprint/07_技术决策与实施门禁.md#AC18 | satisfied | C=1/两片正式HTTP/PG中正常4条先成功，剩余pending4/failed0；12条第三未投放片最终全成功；缩容20条全成功 |
| R16 | 有限 Job 周期原子续接，成功项不重发，回滚/取消/Fence 仍正确 | docs/blueprint/07_技术决策与实施门禁.md#AC15 | satisfied | 旧成功1项不重发、剩余2项接续；插入异常整体回滚；Cancel与接续两提交顺序、旧Fence/回调和legacy/硬错误停止两系统通过 |
| R17 | 空闲分片归还 C/RPS，机器受限发送者用足可用速率，借额恢复和降档不重复承诺 | docs/blueprint/07_技术决策与实施门禁.md#AC3 | satisfied | Red 复现后改为同 Fence 原子 C/RPS 预留；Windows四文件74项通过、预留17项及三片补验通过，Linux当前wheel332项通过，真实借额/恢复/降档/小数/旧承诺边界覆盖；独立003关闭结论另见REVIEW |
| R18 | 同步远程 main 到本地，保留双方功能及未提交修改，隔离验证组合兼容 | docs/blueprint/07_技术决策与实施门禁.md#AC10 | satisfied | 当前任务分支及本地main均快进至64bfade1；42个非共同文件按备份原始字节恢复，用户Prompt不变；报告决定与打标决定共同保留；Windows524个行为/API/Contract用例、112个PG用例，Linux384个不同用例及前端274/浏览器14通过，完整边界和中途环境错误见MAIN_SYNC_EVIDENCE |
| R19 | 稀疏格式错误不阻断健康升档，保留严格校验和持续修复 | docs/blueprint/07_技术决策与实施门禁.md#AC19 | satisfied | Red重放后加权探测回归、Windows全后端1843项和PG80项、Linux正式wheel358项通过；201条三片六轮非法输出持续修复、成功项不重发 |
| R20 | 用跨窗成功量及真实模型延迟评估容量收益，明确429信号优先 | docs/blueprint/07_技术决策与实施门禁.md#AC20 | satisfied | 峰谷/稀疏/100-500-2500平台与资源矩阵通过；明确RPM/TPM经Adapter/Feedback保留分类；最后退出/本地受限候选生命周期Red后两系统Green，peer/未知Fence承诺保留 |
| R21 | 每条成功才正常完整退出，pending/未投放不得冒充成功 | docs/blueprint/07_技术决策与实施门禁.md#AC18 | satisfied | 正式API/Worker/PG/FakeHTTP中201目标全部成功前不succeeded，最终201成功、0pending、0failed；stale显式partial_failed、异常停止及未投放分片回归通过；真实Chrome两流程通过 |

R8–R12 同时追溯用户已确认决定 `user:20261001-machine-adaptation-root-fix`；Source 单元格采用正式 Blueprint 的单个稳定 Acceptance，用户决定及 Windows/Linux 要求保留于本 Change 目标与上游正文。

R18 同时追溯最新用户授权 `user:20261001-sync-remote-main`，Source 采用已同步授权的正式 Blueprint AC10；本次同步范围和功能保留验收由 R18 正文及本轮证据共同确定。

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| Analysis/LLM/资源生产Owner | epoch8容量、许可、持续恢复与诊断修复 | 切断反馈/调度/恢复根因 | R1–R21 / E1–E3 |
| 对应unit/integration与0076/0077 | 失败复现、边界回归、降级安全 | 保护真实事务和旧协议 | R5/14/16/20/21 |
| 正式专题/Blueprint/模块README | 同步机制、限制与当前Git授权 | 保持单一长期Owner | R7 / E4 |
| 用户内容打标Prompt | 原字节纳入当前交付 | 用户要求全部现有本地修改，生产Compiler验证 | R4 / E1 |
| 当前Change和Evidence | canonical结构、历史守恒、正式交付状态 | 可审查及原生归档 | R7 / E1–E4 |

# 验证矩阵

新增 R13–R16 同时追溯本轮用户决定 `user:20261001-all-normal-content-success`、后续“格式不对不断重试”目标及最终“连续五分钟真实网络不可用停止”答复；Source 采用正式 Blueprint 稳定验收标识。R14 的网络分类同时受 AC13 约束，R16 的取消/终态仍受 AC14 约束。历史 completed 记录不代替本轮证据。

| Layer | Applicability | Scope |
| --- | --- | --- |
| Behavior / Unit / Component | required | 真实占用、控制器、资源、错误分类、有限/持续工作量模拟 |
| Contract / Consumer | required | 冻结快照、HTTP 请求体、历史兼容及审计读取 |
| Integration / Persistence / Runtime | required | 独立 PostgreSQL、多事务预留、真实 Worker 与 Fake HTTP |
| User / Workflow Acceptance | required | 正式 API 创建、Planner/Worker 运行、结果查询 |
| Real Cross-component Golden Path | required | 隔离 API/Worker/PG/Fake LLM |
| External Dependency Probe | not_applicable | 真实付费模型性能对照按AC9明确延期；本次不改变Provider外部协议事实，不调用收费模型，不声称真实性能收益 |
| Build / Package / Runtime | required | Python Ruff/mypy、受影响回归 |
| Docs / Governance | required | Blueprint/专题与实现同步、完成审计 |

## 验证计划

目标与相关回归及实际完整命令见EVIDENCE。Windows1843passed/16skip/12subtests；PG80passed；Linux正式wheel358passed；Chrome两流程2passed，组间不累加。重新执行受影响Docs/Secret/new-Change/Ready/current-scope检查。正式current-head CI由真实classifier确定所需全部层；合并后main-fresh与Archive分别核验。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 真实模型最终输出仍由Provider决定；不保证永远成功或实际提速倍数 | pending保持可审计，不假成功；正式真实收益明确延期 |
| 兼容性 | HTTP/依赖/启动不变，历史冻结协议保持 | 真实Contract/恢复回归 |
| 数据 / Migration | 无新业务Schema/head；0076/0077只增强downgrade guard | 既有升级DDL未改 |
| 部署 / 运行 | 用户服务未重启，测试使用独占资源 | 新代码由后续正常发布/重启加载，不操作在用任务 |
| 回滚 / 恢复 | 排空新协议Run/预留后回退旧代码，重建派生Profile | 保留业务结果，不直接旧代码解释新状态 |

# 文档、依赖、部署与发布影响

专题和模块README按真实Owner同步；Blueprint AC10更新当前授权。无依赖/Runtime升级、无新的Secret或配置入口。只有Git交付，无生产Deploy/Release/Migration。用户Prompt通过既有Compiler与原子Scheme版本机制，不直接写用户DB。

# 完成审计

- [x] upstream_re_read：重新读取当前用户远程交付授权与Blueprint AC1–AC20、epoch8实际Evidence及Ruleset，重建当前实现完成定义和尚未完成的交付阶段。
- [x] change_coverage：R1–R21与实现/测试/文档一一核对；代码字节未变部分复用本轮证据；新Git授权与canonical结构变更单独验证，不冒充已合并。
- [x] reverse_audit：API冻结→Planner→Worker/严格修复→成功提交/后继→父Run与页面结果一致；PromptCompiler→Scheme原子版本消费保持；Git分支→PR→当前Head检查→guarded merge→main-fresh/Archive/cleanup分别审计。
- [x] unresolved_cleared：epoch8范围内阻塞均CLOSED；当前实现无not_satisfied。远程阶段尚未执行，明确列入交付状态，不伪造提前关闭或部署；真实性能/准确率按正式延期边界保留。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | epoch8/Windows/Linux | EVIDENCE内实际命令与原始输出、冻结哈希 | 本地各层通过 | 生产实现与本轮范围匹配；不代替current-head CI |
| V2 | epoch8独立Review | REVIEW内集中修复关闭与直接相邻审计 | PASS，原blocking CLOSED | 原实现完成定义，不代替新增交付审查 |
| V3 | 本次交付 | canonical new Change/项目Ready/Docs/Secret/preflight | 执行后写回EVIDENCE | 新结构与授权事实；远程状态随后按实更新 |

## 未验证内容与剩余风险

真实付费模型性能对照、服务器满载收益和量化Gold Set准确率明确未验；当前远程CI/合并后证据尚未取得。TikHub无本次LLM容量Owner边界，不调用。

## 交付状态

提交/PR/current-head CI/合并/main-fresh/Archive/分支cleanup尚未完成，按正式阶段逐项取得证据；本地ready不宣称远程交付完成。发布/部署不适用，本次仅用户授权的Git集成。

## 备注

下面原始epoch1–8施工记录以历史附录完整保留，旧“仅本地”授权及当时Evidence状态不再作为当前授权，禁止删除旧失败或首次漏检事实。

# 历史施工记录

### 历史：目标与约束

2026-10-01 用户追加授权拉取远程 main 并同步本地，解决兼容冲突；仅该本地同步动作扩展此前“不合并”的边界，不授权提交或推送本地修改。当前基线为 `64bfade138e6cdf0f86e8d8961a0415b8f994ea8`，原本地代码和用户 Prompt 保留；main 新增报告与品牌识别能力的组合验证见 [changes/active/CHG-20261001-112055-analysis-capacity-feedback/MAIN_SYNC_EVIDENCE.json](MAIN_SYNC_EVIDENCE.json)。旧阶段 Evidence 保留为历史，各环境中途 setup 错误及最终有效回归分别记录。

2026-10-01 17:28 的新运行事实重新打开本 Change：14618 条中 13988 条成功，412 条已投放但未完成、218 条未投放；旧阶段验证没有覆盖连续迟到 429 与许可等待组合。用户明确要求除真实网络/模型错误外全部正常内容成功，个别问题不得终止其余正常内容。当前工作以此新要求为准，以下旧完成记录保留为历史证据，不代表本轮修复已完成。

本轮计划：生产反馈/Repository 复现迟到错误反复压低 C/RPS、等待 Future 冒充占用、低 C 的退避份额阻塞，再修正发送阶段和物理许可。新 Run 冻结 recovery.v2，格式/字段/Taxonomy/证据错误持续修复，没有五分钟截止；用户最终确认连续五分钟真实网络不可用停止，429/HTTP 响应及本地等待不计断网。保留有限 Job Deadline/Attempt，以正式同 Request 后继 Job 原子续接 pending；成功项不重发。历史 recovery.v1 不补写快照。独占 PostgreSQL/Fake HTTP 验证正常/未投放分片、接续回滚、Fence/取消及两系统运行，完成文档和新审查。没有业务 Schema/依赖变更，不操作用户失败 Run、不重启用户服务，不调用收费模型。

修复本次 200 条任务中跨窗占用误判、单次超时误判容量和约两分钟恢复等待；小任务快速探测、大任务持续利用模型及机器容量。保持当前思考模式、Prompt、Taxonomy、单内容输出和 Validator、幂等、Fence、取消与持久恢复。只修改本地，不提交或推送，不访问用户业务数据库，不启停用户服务。现有用户 Prompt 改动保留。

2026-10-01 用户再次批准系统修复：同一代码根据不同机器的实际可用资源和模型能力持续提高成功入库吞吐。14,418 条真实任务的 9 个分片串行、Windows 虚拟环境启动器 PID 与 Lease 身份不一致、尾部 pending 被误作充足需求，均进入本 Change 的续修范围。原本地验证不能证明这些新增边界；续修完成前重新进入 in_progress。

### 历史：方案与计划

2026-10-01 最新授权续修：最新运行显示稀疏 Validation 错误重置升档、两秒吞吐峰值造成过早回退；402 为账户余额问题。保留原始历史 Evidence，重新验证后才能恢复 Ready。本轮新增 R19–R21：按当前容量累计成熟、充分负载的成功入库证据，用模型延迟和样本量决定观察长度；稀疏格式失败持续修复而不重置升档；429 显式请求/token 信号优先；正常完整退出必须全部目标成功，五分钟真实断网、系统硬错误和手动取消仍显式停止。复用现有 Profile JSON，不改变业务 Schema、依赖、Prompt 或思考设置。顺序为失败回归 → 生产修复 → 隔离 PostgreSQL/Fake HTTP 和 Windows/Linux验证 → 文档、完成审计、独立复核。仅本地，不提交或推送。

1. 真实开始/结束积分、阶段归属和短观察窗 → 局部聚合与 Profile → 回归跨窗、空闲和尾部。
2. 区分偶发超时、持续拥塞与限流，健康快速扩容与按时间恢复 → 生产控制器 → 不同容量/长尾/有限批次的事件模拟。
3. 既有 Profile 内带 Fence 和期限的容量预留，执行槽位与分片几何对齐 → Repository/Worker/Planner → 隔离 PostgreSQL 多事务、多分片及接管。
4. 有效资源与入库背压、传输阶段超时和安全诊断 → Worker/HTTP Adapter → 资源压力、协议体和错误恢复回归。
5. 同步正式文档、完成审计和两阶段复核 → 当前机器检查 → 只交付本地代码和明确证据。

选择复用单 Profile JSON，而非新增容量表或独立任务系统；每秒批量刷新预留，不对每次 HTTP 发送执行事务。静态提高并发不能切断误判和恢复原因，因此不采用。新建 Run 使用版本化容量策略；历史 Snapshot 不补写，恢复、输出业务协议和模型生成参数保持。无依赖升级或业务 Schema Migration；代码回退前须排空新策略 Run，派生 Profile 可重建。

### 历史：Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 从根因修正占用、超时和恢复机制 | docs/blueprint/07_技术决策与实施门禁.md#AC4 | satisfied | 在途积分包含跨窗未完成请求，阶段归属阻止旧请求证明新容量；1/34 超时、尾部、固定秒数恢复和审计排队时间回归通过 |
| R2 | 小任务及大数据量都快速利用可用容量，适配不同模型 | docs/blueprint/07_技术决策与实施门禁.md#AC8 | satisfied | 正式 API/Planner/Worker/Fake HTTP/PG 的 200 条全入库、物理峰值 100；200000 条事件模拟覆盖 100/500/2500 及 2500→800→2500；未知端点反馈学习 |
| R3 | 纳入机器资源、执行槽位和数据库背压 | docs/blueprint/07_技术决策与实施门禁.md#AC17 | satisfied | 有效 CPU、可用内存、CPU 差值压力和提交速率共同限定本地许可；资源受限与采样未知、背压恢复回归通过；Planner 按目标数/分片槽位投放 |
| R4 | 保持思考模式、Prompt、Validator 与打标准确性机制 | user:20261001-preserve-thinking-and-quality / AC6 | satisfied | HTTP 请求体仍只有 model/messages/response_format，没有关闭 thinking 或改变 effort/输出长度；用户 Prompt 保留；Validator、repair/judge、空值及持久恢复相关回归通过；不宣称量化语义准确率 |
| R5 | 跨 Run/Shard、取消、Fence、幂等、持久恢复正确 | docs/blueprint/07_技术决策与实施门禁.md#AC14 | satisfied | 多事务预留、零份额、缩容排空、尾部借额、旧 Fence 接管、配置热启动、恢复与终态调度的隔离 PG 回归通过；v1 冻结 45 秒/256 不改写 |
| R6 | 本地隔离验证，保护其他代码和依赖数据库 | docs/blueprint/07_技术决策与实施门禁.md#AC16 | satisfied | DB 127.0.0.1:55478/aima_capacity_feedback 独占容器和任务目录；API/Fake LLM/Frontend 使用 55480/55481/55479；只停止准确 PID/命令行匹配的本次服务；不连接用户 DB |
| R7 | 仅本地修改，不提交或推送远程 | docs/blueprint/07_技术决策与实施门禁.md#AC10 | satisfied | 当前本地任务分支，无 commit/push/PR |
| R8 | Windows 启动器和实际解释器 PID 不同仍能准确扩容、保护忙碌 Worker | docs/blueprint/07_技术决策与实施门禁.md#AC17 | satisfied | 模拟包装 PID 与 Lease 不同仍扩容；内存缩容仅停止空闲 Lease；Windows 真启动器/解释器句柄及两系统正式 Worker Pool 通过 |
| R9 | 区分可发送工作、在途工作和延迟重试；尾部不形成错误容量证据 | docs/blueprint/07_技术决策与实施门禁.md#AC4 | satisfied | has_ready 复用正式重试条件并排除在途/未提交；1024目标/111占用不回退、不更新安全/不安全或吞吐记忆；两系统就绪与恢复回归通过 |
| R10 | 分片尾部能补充下一片，保持物理占用、Fence、幂等和取消 | docs/blueprint/07_技术决策与实施门禁.md#AC14 | satisfied | 真实 Fake HTTP 慢请求未完成时至少24项已入库；最终36请求/36成功且3片退出；取消、接管、份额、waiting Run 与终态相关回归通过 |
| R11 | 按宿主或容器有效配额测量 CPU 压力，配额变化后恢复探测 | docs/blueprint/07_技术决策与实施门禁.md#AC17 | satisfied | Windows 系统计数与 Linux host 回退、cgroup v1/v2、配额变化/计数复位回归；真实 Linux 0.5核容器压力1.0；不同资源/16核64GiB配置矩阵通过 |
| R12 | 保持原输出与思考行为，代码和启动入口可用，不影响用户服务 | docs/blueprint/07_技术决策与实施门禁.md#AC16 | satisfied | Windows357passed；Linux正式wheel354passed/1Windows专属skip；最终池13passed；思考请求体、用户Prompt SHA256、类型/Contract/文档检查通过 |
| R13 | 迟到旧发送错误不反复降低新的 C/RPS，Future 不冒充物理占用 | docs/blueprint/07_技术决策与实施门禁.md#AC4 | satisfied | Red 复现后两系统最终诊断/恢复组各53passed，RPS健康恢复成熟、真实多片迟到429及预留回归通过 |
| R14 | 格式错误持续只修复未成功内容，真实断网五分钟停止且兼容旧协议 | docs/blueprint/07_技术决策与实施门禁.md#AC12 | satisfied | v2格式超过十分钟仍修复成功、实际失败跨度300秒停止、HTTP/池等待排除与legacy v1两系统回归通过 |
| R15 | 低 C 下退避不空占，正常及未投放内容推进，有 pending 不成功完成 | docs/blueprint/07_技术决策与实施门禁.md#AC18 | satisfied | C=1/两片正式HTTP/PG中正常4条先成功，剩余pending4/failed0；12条第三未投放片最终全成功；缩容20条全成功 |
| R16 | 有限 Job 周期原子续接，成功项不重发，回滚/取消/Fence 仍正确 | docs/blueprint/07_技术决策与实施门禁.md#AC15 | satisfied | 旧成功1项不重发、剩余2项接续；插入异常整体回滚；Cancel与接续两提交顺序、旧Fence/回调和legacy/硬错误停止两系统通过 |
| R17 | 空闲分片归还 C/RPS，机器受限发送者用足可用速率，借额恢复和降档不重复承诺 | docs/blueprint/07_技术决策与实施门禁.md#AC3 | satisfied | Red 复现后改为同 Fence 原子 C/RPS 预留；Windows四文件74项通过、预留17项及三片补验通过，Linux当前wheel332项通过，真实借额/恢复/降档/小数/旧承诺边界覆盖；独立003关闭结论另见REVIEW |
| R18 | 同步远程 main 到本地，保留双方功能及未提交修改，隔离验证组合兼容 | docs/blueprint/07_技术决策与实施门禁.md#AC10 | satisfied | 当前任务分支及本地main均快进至64bfade1；42个非共同文件按备份原始字节恢复，用户Prompt不变；报告决定与打标决定共同保留；Windows524个行为/API/Contract用例、112个PG用例，Linux384个不同用例及前端274/浏览器14通过，完整边界和中途环境错误见MAIN_SYNC_EVIDENCE |
| R19 | 稀疏格式错误不阻断健康升档，保留严格校验和持续修复 | docs/blueprint/07_技术决策与实施门禁.md#AC19 | satisfied | Red重放后加权探测回归、Windows全后端1843项和PG80项、Linux正式wheel358项通过；201条三片六轮非法输出持续修复、成功项不重发 |
| R20 | 用跨窗成功量及真实模型延迟评估容量收益，明确429信号优先 | docs/blueprint/07_技术决策与实施门禁.md#AC20 | satisfied | 峰谷/稀疏/100-500-2500平台与资源矩阵通过；明确RPM/TPM经Adapter/Feedback保留分类；最后退出/本地受限候选生命周期Red后两系统Green，peer/未知Fence承诺保留 |
| R21 | 每条成功才正常完整退出，pending/未投放不得冒充成功 | docs/blueprint/07_技术决策与实施门禁.md#AC18 | satisfied | 正式API/Worker/PG/FakeHTTP中201目标全部成功前不succeeded，最终201成功、0pending、0failed；stale显式partial_failed、异常停止及未投放分片回归通过；真实Chrome两流程通过 |

R8–R12 同时追溯用户已确认决定 `user:20261001-machine-adaptation-root-fix`；Source 单元格采用正式 Blueprint 的单个稳定 Acceptance，用户决定及 Windows/Linux 要求保留于本 Change 目标与上游正文。

R18 同时追溯最新用户授权 `user:20261001-sync-remote-main`，Source 采用已同步授权的正式 Blueprint AC10；本次同步范围和功能保留验收由 R18 正文及本轮证据共同确定。

### 历史：Validation Matrix

新增 R13–R16 同时追溯本轮用户决定 `user:20261001-all-normal-content-success`、后续“格式不对不断重试”目标及最终“连续五分钟真实网络不可用停止”答复；Source 采用正式 Blueprint 稳定验收标识。R14 的网络分类同时受 AC13 约束，R16 的取消/终态仍受 AC14 约束。历史 completed 记录不代替本轮证据。

| Layer | Applicability | Scope |
| --- | --- | --- |
| Behavior / Unit / Component | required | 真实占用、控制器、资源、错误分类、有限/持续工作量模拟 |
| Contract / Consumer | required | 冻结快照、HTTP 请求体、历史兼容及审计读取 |
| Integration / Persistence / Runtime | required | 独立 PostgreSQL、多事务预留、真实 Worker 与 Fake HTTP |
| User / Workflow Acceptance | required | 正式 API 创建、Planner/Worker 运行、结果查询 |
| Real Cross-component Golden Path | required | 隔离 API/Worker/PG/Fake LLM |
| External Dependency Probe | not_applicable | 用户要求本地修改；不调用收费模型，不声称真实性能收益 |
| Build / Package / Runtime | required | Python Ruff/mypy、受影响回归 |
| Docs / Governance | required | Blueprint/专题与实现同步、完成审计 |

### 历史：Completion Audit

本轮按2026-10-02当前用户规则及最新“提高速度、每条成功才正常退出”决定重新重建完成定义；旧阶段审查/测试仅在字节未变的边界保留。当前38项冻结身份为epoch8，epoch7/6/5保留历史。独立REPAIR_DIFF为PASS / NO_FINDINGS_WITHIN_SCOPE，当前实现达到本地可审查完成定义；远程交付不在本轮范围。

- [x] upstream_re_read：重新读取当前项目规则、Blueprint第35/36节与AC1–AC20、用户逐条成功/持续格式修复/五分钟真实断网停止/Windows-Linux机器自适应决定；旧冻结协议、收费实测和远程交付边界不改写。
- [x] change_coverage：R1–R21全部有实现/测试/文档依据；epoch8 Windows1843passed/16skip/12subtests，四PG组80passed，Linux正式wheel358passed，Chrome正式两流程2passed；量化语义准确率及真实Provider性能不冒充已验收。
- [x] reverse_audit：页面/API创建v2 → Planner有限投放 → Worker持久修复与正式后继 → 合法结果实际入库 → Run成功数等于target → 页面查询合法标签；pending/未投放/stale不冒充成功，成功项不重发，硬错误/五分钟真实断网/取消显式停止。物理反馈分类、同Profile C/RPS预留与有效资源一致，候选失效不删除peer/Fence承诺。
- [x] unresolved_cleared：CAPACITY-V3-REV-001两个投影经同包Red/Green及独立epoch8集中REPAIR_DIFF均CLOSED；最终PASS / NO_FINDINGS_WITHIN_SCOPE，无新范围内阻塞或UNCHANGED_BASELINE BLOCKING sibling。R1–R21无not_satisfied，历史CAP/MACHINE/RECOVERY Findings及首次漏检事实保留。

### 历史：历史完成审计（decision epoch 2）

以下保留 decision epoch 2 的历史完成审计，不作为当前阶段的重复审计字段：

- [x] upstream_re_read：重新读取最新 Windows/Linux 同代码充分利用实际可用性能要求及 Blueprint 35/36、AC1–AC17；真实付费性能对照和远程交付仍明确延期。
- [x] change_coverage：R1–R12 均有生产调用链与本阶段新鲜验证；旧阶段证据只复用未改变的前端和业务语义边界，新增机器/分片边界补两系统实机验证。
- [x] reverse_audit：父进程分配 Lease ID → 子进程继承 → DB busy → 扩缩容一致；API/Planner Job窗口 → Worker共享许可 → 物理占用 → 成功入库反馈一致；pending维持恢复/退出而ready决定需求；v1快照保留。无新增前端或公共入口。
- [x] unresolved_cleared：not_satisfied 已清零；范围内行为和两平台相关链通过，独立续修 Review 最终 PASS / NO_FINDINGS_WITHIN_SCOPE，三项测试收尾 Finding 均 CLOSED；不宣称真实 DeepSeek 吞吐、量化准确率或全仓CI通过。

续修首次独立结论 CHANGES_REQUIRED：新增生产机制无已确认阻塞缺陷，MACHINE-REV-001/002 指向新测试的断言失败及 Linux 退出超时收尾。作者以单个测试生命周期修复包处理，补真实失败注入和独占 session 强制回收证据；原有生产实现保持冻结；两项独立关闭后补出 Windows 早期失败 sibling（MACHINE-REV-003），也已局部修复并取得真实退出证据。最终 REPAIR_DIFF 为 PASS / NO_FINDINGS_WITHIN_SCOPE，三项均 CLOSED。

### 历史：续修计划与执行

1. Worker 父子共享稳定 Lease 身份，PID 只控制进程 → worker_main 与 Job 进程池回归 → 虚拟环境实际 PID 不同仍计忙碌，忙碌进程不被缩容。
2. 就绪需求和物理占用分开，低负载窗口不更新容量边界 → Analysis Worker/Profile/控制器 → 复现 1024 目标仅 111 在途、零新发送的错误降档并切断。
3. 根据真实空余和本机预算补充尾部分片 → Planner/Profile 预留 → 跨分片重叠、请求上限、取消和接管的隔离 PG/HTTP 验证。
4. CPU 压力采用有效配额，容器限流及未知/配额变化有明确处理 → platform/capacity → cgroup v1/v2 与宿主回退回归，服务器配置矩阵。
5. 按本次相关链验证小/大任务、质量协议与启动，更新专题文档和 Evidence，取得独立复核 → 保持本地未提交状态。

保留现有线程/多进程/单 Profile 方案，与只调静态上限或换异步/独立调度服务比较，选择修正已有机制：不新增依赖、表或对外参数，不改变打标业务语义。历史 Run 不补写快照，历史 Lease 继续按原有身份/Fence 收尾；新子进程使用新的稳定身份。测试必须新建任务独占 PostgreSQL/端口/目录，不重用用户 .runtime。

2026-10-01 重新读取本轮用户约束、Blueprint 第 35/36 节及 AC1–AC17；分别核对上游要求到本 Change，以及 Change 到实现、测试和文档。当前授权范围是本地改造与隔离验证，真实付费性能对照、远程交付和生产发布不属于本轮完成定义。

反向核对：新建 Run 的 v2 快照由 API 写入，Planner 投放和 Worker 消费均识别；历史 v1 由真实 HTTP 回归证明保留冻结参数；动态学习字段不进入 Preview/Create 幂等身份；安全审计新增字段由既有读取方兼容消费。前端沿用既有打标入口及只读容量展示，真实页面创建、Worker 结果与最终标签刷新另有 Full-stack 验收。模型生成行为、业务 Taxonomy、公共输出及用户 Prompt 未被速度优化改写。

### 历史：历史阶段两阶段复核

先完成需求覆盖复核，再按当前 diff 检查许可生命周期、事务锁顺序、版本兼容、异常退出、成本审计、取消与输出验证。前一阶段以下复核发现已修正并取得相应用例证据：配置热启动不能丢弃在途预留；旧控制器 unsafe 不可当作新容量证明；Client 关闭异常仍要回收本 Fence；downgrade guard 必须覆盖 v2；本地许可排队不能计作 HTTP 延迟且价格按实际发送时间生效。当前任务范围没有未处理阻塞 Finding。

两阶段自审之后，一个只读 Reviewer 独立完成 A1/A2 和质量审查，首次发现 CAP-REV-001（端点切换的声明提示与容量边界）及 CAP-REV-002（RPS 与并发许可顺序）两项 IN_SCOPE/BLOCKING 问题。修复后取得端点切换、物理发送间隔、取消与正式 Worker 组合回归证据；同一 Reviewer 的独立修复复核为 PASS / NO_FINDINGS_WITHIN_SCOPE，两项均 CLOSED。当前工作树满足本地可审查完成定义；没有远程 PR Review/CI/合并。审查范围和证据见 [REVIEW.md](REVIEW.md)。

Validation Asset Redundancy: clean。生产控制器与 Repository 是唯一判断实现；事件模拟复用生产观察和状态转换，内存 Session 只替换存储/时钟；PG 与浏览器验收复用既有 Fixture、Worker 和 Fake HTTP。临时隔离服务配置只改变地址与目录，没有建立平行业务实现。

### 历史：Evidence 与交付状态

基线 15dd366db6e1632535fadc615513636a4b22c639。原有诊断修改与用户 Prompt 修改继续保留。本 Change 保持 Active；没有提交、PR、CI、合并或部署。性能模拟不等于真实 DeepSeek 性能或语义准确率实测。

实际命令与完整结果见 [EVIDENCE.md](EVIDENCE.md)。没有新增表/列或 Migration head；既有 0076 只增强降级安全检查，upgrade DDL 不变。新版代码以派生 Profile JSON 升级观测协议；回退到仅识别 v1 的代码前应先排空 v2 Run 并重建派生 Profile，不删除业务结果。用户正在运行的 API/Worker 未重启；加载本地改造需在用户现有任务结束后使用原运行方式重启相应进程并创建新 Run。


### 历史：续修完成与本地交付

已重新核对最新用户 Windows/Linux 同代码自适应要求、Blueprint 35/36、AC1–AC17 与 R1–R12，完成双向能力审计及独立 A1/A2/质量审查。最终决策epoch2的32文件摘要为 `35e729e6b6bcfc01f9050141d0529a395d6878857925343dac174d955312aa38`，清单见REVIEW_BASELINE.json；独立Reviewer逐字节验证全部匹配，三项测试收尾Finding均CLOSED，MACHINE-REV-003的首次漏检事实保留。无未关闭范围内阻塞项。状态ready_for_review仅表示本地完成定义和审查通过；没有commit/push/PR/remote CI/merge/main-fresh/Archive/Issue Closure或部署。

续修没有公共Contract/依赖/Migration head/业务Schema变化；前阶段0076 downgrade guard仍保留。代码回退须按原既有v2排空/派生Profile重建边界执行。没有重启用户服务或迁移其数据库，测试容器/卷/网络/临时Secret与目录已精确回收。真实DeepSeek吞吐、服务器16核64GiB实部署与Gold Set准确率仍未实测，不将模拟/容器证据冒充这些结论。正式专题/模块Owner和Blueprint已按生产调用链同步。

### 历史：当前持续恢复与速率修复完成（decision epoch 4）

按用户最终“连续五分钟真实网络不可用停止”与持续格式修复决定，重新核对 Blueprint 第35/36节、AC1–AC18 和 R1–R17；完成需求到Change、Change到实现/测试/文档及API→冻结协议→执行恢复→当前Job→取消/结果的反向核验。最终独立REPAIR_DIFF为PASS / NO_FINDINGS_WITHIN_SCOPE，RECOVERY-REV-001/002/003均CLOSED；003的UNCHANGED_BASELINE / FIRST_REVIEW_ESCAPE保留。冻结38文件SHA256为4a43dab236787296d96c7189fe451b6fd311cd523139b60e046296d326b6a229，Reviewer开始和结束两次逐字节核验一致。

ready_for_review仅表示当前本地完成定义及独立审查通过。没有commit/push/PR/远程CI/merge/main-fresh/Archive/Issue Closure或部署；当前用户Run和数据库未改动，历史失败630条未自动恢复。新v2格式持续pending，只有合法提交才计成功；外部模型一直不合法时不承诺最终一定返回合法答案。当前正常完成边界与网络停止规则已取得隔离回归，而非真实付费模型/服务器收益对照。无公共Contract/依赖/业务Schema/head变化，0077 downgrade guard兼容两恢复版本。回退前排空新协议Run并按既有流程重建派生Profile，不删除业务结果。

### 历史：当前容量证据与完整成功修复完成（decision epoch 8）

2026-10-02再次核对用户最新规则、提高速度和每条成功要求及Blueprint AC1–AC20；当前Requirement Traceability R1–R21、实现/测试/文档与反向页面结果审计闭合。独立epoch7首次CHANGES_REQUIRED保持历史，CAPACITY-V3-REV-001的候选生命周期两个投影经一次修复包关闭；epoch8最终REPAIR_DIFF为PASS / NO_FINDINGS_WITHIN_SCOPE，38文件aggregate为3de577e65419ed45c4c77b44718d5eeef4ff8239ad1cea1c7a2c4f9afbc2d3a5。审查报告所读施工快照的pending记录不覆盖本段最终有效结果。

Windows全后端1843passed/16skip/12subtests、四PG组80passed、Linux非root正式wheel358passed、真实Chrome两流程2passed；这些组不累加。Prompt保持用户原字节，没有关闭thinking、放宽Validator或发送已成功Item。正常Run只有成功数等于target才成功；格式错误持续仅修复未成功内容，已确认真实断网五分钟、硬错误、取消仍显式异常停止，stale不冒充成功。没有新增API字段、依赖、业务Schema或Migration head；旧控制JSON回退前排空新协议Run/预留并重建派生Profile，不删除业务结果。

任务容器/匿名卷/镜像/网络、测试服务进程与55493–55496端口、scratch与九个仓库外临时目录均精确回收；原.venv、frontend/node_modules和用户服务/数据库未操作。本地任务分支与HEAD保持不变，修改继续未暂存/未提交；没有commit/push/PR/remote CI/merge/main-fresh/Archive/Issue Closure或部署。当前ready_for_review仅表示本地可审查，不表示真实付费吞吐、16核64GiB服务器满载或Gold Set语义准确率已实测。
