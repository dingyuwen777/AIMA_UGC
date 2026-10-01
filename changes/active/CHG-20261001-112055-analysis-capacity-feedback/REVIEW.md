# 独立本地审查与修复复核

> 本文件先保留 decision epoch 1 的审查记录。Windows/Linux 机器适配续修是 decision epoch 2，必须独立重建完成定义并重新审查；当前续修最终结论见本文件末尾，不能把旧 PASS 当成续修已通过。

日期：2026-10-01。Reviewer：独立只读 Agent `/root/capacity_review`。基线/HEAD：`15dd366db6e1632535fadc615513636a4b22c639`；本地分支：`fix/analysis-capacity-feedback`。本轮没有提交、远程 PR Review 或远程 CI。

## 范围与结论

Reviewer 独立执行需求覆盖、完成定义和实现质量复核，检查容量控制、物理 HTTP 许可、RPS、锁顺序、预留/Fence/取消、历史 v1、审计、持久恢复和文档。没有写入生产代码、连接数据库、调用收费模型、启动浏览器或执行 Git 写操作。

首次结论：**CHANGES_REQUIRED**。作者完成一个修复包后，同一 Reviewer 重新审查修复差异及关联路径，最终结论：**PASS / NO_FINDINGS_WITHIN_SCOPE**。两项阻塞 Finding 均关闭，没有新增或未处理的范围内阻塞问题；没有以作者自审代替独立关闭。

首次实现差异摘要 SHA-256：`f809b6178cbfbb1173a3af9e291ecbabebe73a001c6e8dc7916504ca2f5aaec4`。

修复后实现差异摘要 SHA-256：`4f3dbc3a5dfecc37985cf4fe75888ef8ac7213bc45164520c1830f4118f568e9`。

摘要范围为已跟踪的 backend/tests/migrations/docs 差异及六个新增实现/测试文件，排除用户 Prompt 修改、scratch 与本 Change 证据文件。复核之后只更新记录与清理临时资源，没有修改实现。

## Findings 与关闭证据

| ID | 首次判定 | 机制与修复 | 最终状态 |
| --- | --- | --- | --- |
| CAP-REV-001 | IN_SCOPE / BLOCKING / AUTO_REPAIR | 官方端点的声明额度在切换未知端点时被错误保留；切换到较低官方上界时热启动也可能超界。Repository 现区分省略声明与明确无声明，按当前 Revision 替换提示并约束 warm start，同时保留尚未排空的物理预留。官方→未知、未知→官方和省略/旧 Revision 回归覆盖。 | CLOSED |
| CAP-REV-002 | IN_SCOPE / BLOCKING / AUTO_REPAIR | 先领取 RPS 再等待并发许可，会使队列积累过期速率许可并在排空后突发发送。现通过同一 Condition 在 C 和即时 RPS 都允许时才开始请求，等待不预占许可，C/RPS 更新原子生效。实际发送间隔、零许可取消及正式 Worker 缩容组合回归覆盖。 | CLOSED |

Reviewer 独立运行六个既有修复回归：两个端点切换、省略/旧 Revision、C/RPS 突发、零 C 取消、零 RPS 取消，全部通过；独立 `git diff --check` 通过。确认锁顺序为 Condition→RateLimiter，RPS 回调仅读取当前值，没有反向获取 Condition；同时复核每次 Retry 的物理许可、HTTP 计时起点、缩容排空和历史 v1 冻结参数。

## 复用证据及限制

复用作者在最终实现上的 276 项单元/Contract/API 回归、60 项隔离 PostgreSQL 集成回归、另一个正式 Worker 限速组合用例、最终真实 Full-stack 1 项、24 个 Python 文件的 Ruff 和 422 个源码文件的 mypy 证据。详细命令、时间、扩展扫描失败和资源隔离见 [EVIDENCE.md](EVIDENCE.md)。前端代码未因修复变化，既有单元/浏览器/构建证据仍适用。

原有内容类型和持久恢复路径未被此次调度改造替换；输出验证、repair/judge、Prompt 和模型思考参数保持。审查不代表真实 DeepSeek 吞吐、Gold Set 准确率、严格账号额度跨 Provider 汇总、全仓远程 CI、最新远程 main 或正式发布已经验收。扩展全仓扫描的既有文档导航和报告浏览器测试问题仍按证据记录保留。


## Windows/Linux 机器适配续修独立审查（decision epoch 2）

Reviewer `/root/capacity_review` 重新读取项目真实 AGENTS、docs/AGENTS、Blueprint 35/36、AC1–17 和已授权 GitHub 当前 canonical Review/Coding 及适用 References，独立重建 A1/A2 与完成定义。没有沿用前阶段 PASS。逐文件验证初次冻结 30 文件及汇总 SHA-256 `684963ecc6ec52b307bc198158480e827541ab1d29b1a68235c12101e5299e0c`；用户 Prompt 哈希也一致。审查全程只读，没有 DB/服务/Docker/收费模型/浏览器/Git 写入，也没有把源码阅读冒充新测试。

首次结论 **CHANGES_REQUIRED**。生产实现的新增机器适配、分片衔接和完成退出路径未发现有证据的阻塞缺陷；新集成测试有两个失败收尾缺口，集中作为单个测试生命周期修复包处理。前阶段 CAP-REV-001/002 在当前工作树仍成立，保持 CLOSED；未确认其他生产阻塞 sibling。

| Finding | Scope / Delivery Effect / Action | 机制与修复 | 状态 |
| --- | --- | --- | --- |
| MACHINE-REV-001 / MEDIUM | IN_SCOPE / BLOCKING / AUTO_REPAIR | 原测试在首次发送和跨片行为断言失败时，没有统一先释放 HTTP 并取消本 Run，可能进入执行器无界等待。修复将第一个 Future 之后的启动、进度、释放和 Future 收尾置于共同异常边界；失败使用正式 Cancel API 只取消本 Run，保留原始断言。两种真实 Worker/HTTP/PG 失败注入在执行器 __exit__ 之前直接断言释放 Event 及已提交 Cancel 状态，最终无运行 Job 且在10秒以内收尾。 | CLOSED（最终独立复核） |
| MACHINE-REV-002 / MEDIUM | IN_SCOPE / BLOCKING / AUTO_REPAIR | 原 Linux 测试只有 SIGINT + 8秒等待，超时可能遗留本次 Worker 并替换原始行为错误。正式测试现在为入口建立独占 session、记录进程组，并验证它不属于测试运行器；先协作退出，超时仅 SIGKILL 本组，确认父进程退出。注入忽略 SIGINT/SIGTERM 的真实父子进程，0.1秒协作界限后两者均退出，原始 AssertionError 仍可匹配。异常清理附加 note，保留原始测试错误。 | CLOSED（最终独立复核） |

修复仅改变两个测试文件：`tests/integration/content/test_analysis_machine_adaptation.py`、`tests/integration/jobs/test_worker_process_lifecycle.py`；六个生产文件及所有相邻实现未变化。新的30文件汇总 SHA-256 为 `a0046db44b459ada498fa43997788d0716d4da42ae88c4e12ea6221cf007759f`。

Reviewer 同时核对稳定 Lease/包装 PID、忙碌缩容、ready/pending/未来退避、低负载占用门禁、有真实后续内容的有界衔接、已完成分片优先退出、cgroup/host未知与配额基线、旧Profile周期重探、共享预留/排空/锁/Fence、思考及Validator/repair/judge/持久恢复/v1、双向需求与正式文档。现有算法/持久链和两平台证据相称；生产机制没有因修测试而替换。修复复核结论待下方补充。


最终摘要覆盖校准：最初的30项清单含29个Python文件及Analysis README。Git默认中文路径引号转义使两份中文文档未进入字节清单，它们已在正式文档语义审查和机器检查中覆盖。使用git `-z` +显式UTF-8补齐后，原30项哈希全部相同；最终32项汇总SHA-256为 `5d0f5b8e6f8211763d6a78deef6518469cc7d41d6205964b8a4fad43380c5aa4`，完整路径/哈希保留在[REVIEW_BASELINE.json](REVIEW_BASELINE.json)，重新解析并逐文件校验通过。本次只校准摘要范围，未改变实现或文档。


第二次 REPAIR_DIFF：MACHINE-REV-001/002 独立核验均 CLOSED；Reviewer发现Windows生命周期用例的句柄建立前失败没有回收Popen，为 First-pass Coverage Miss / UNCHANGED_BASELINE sibling，新增 MACHINE-REV-003（MEDIUM / IN_SCOPE / BLOCKING / AUTO_REPAIR）。Reviewer纯内存调用真实测试函数复现 ready 超时： surfaced_error=TimeoutExpired、original_context=AssertionError、owned_process_stopped=False；没有将内存结果说成实际孤儿进程。

第三项局部修复从 Popen 创建起统一回收本次树；句柄未取得时也使用已审回收入口，保留原始异常并附清理note，原生解释器句柄验证保持。新增真实Windows venv父子进程失败观测：仅隐藏ready观测，另持实际解释器原生句柄；调用原测试函数，原始ready断言仍可匹配，Popen已退出、实际解释器句柄已置退出。当前原成功用例和新失败用例 **2 passed / 1 Linux专属 skipped**（5.43秒），exit0；Ruff check/format通过。只修改该Windows测试及新增失败用例，没有改变已关闭两项和Linux回收入口，Linux既有证据仍适用。

第三项修复后的完整32项摘要为 `35e729e6b6bcfc01f9050141d0529a395d6878857925343dac174d955312aa38`，清单已更新并重新解析验证。前32项摘要保持为本阶段前次修复身份；本次仅一个Windows测试文件变化，生产实现保持冻结。


## decision epoch 2 最终独立结论

最终 REPAIR_DIFF 为 **PASS / NO_FINDINGS_WITHIN_SCOPE**。MACHINE-REV-001/002/003全部CLOSED，CAP-REV-001/002继续CLOSED，没有确认新范围内阻塞或未关闭的UNCHANGED_BASELINE BLOCKING sibling；未重开FIRST_REVIEW。Reviewer重新核验持久REVIEW_BASELINE.json全部32文件原始哈希与汇总 `35e729e6b6bcfc01f9050141d0529a395d6878857925343dac174d955312aa38`；当前生命周期测试文件SHA256为 `78cb83de97a52a037f784a2fa8f3342ab5c336e1483c742e927f801904ecffc5`。

Reviewer另以纯内存Path/Popen/FFI替身调用当前真实Windows测试函数，分别注入ready、PID、句柄失败，三种均surfaced_error=AssertionError、owned_process_stopped=True、wait_calls=1。该证据只证明真实函数控制流；实际进程退出由作者真实Windows原生句柄回归证明，未混淆两类证据。MACHINE-REV-003的First-pass Coverage Miss保留，关闭不抹去此前漏检。

生产代码及Linux helper未因最后Windows局部修复变化，既有两平台完整生产组和Linux真实配额/进程组证据仍适用，不为形式重建环境或无条件全量重跑。最终审查始终只读，无数据库、服务、Docker、浏览器、付费模型或Git写操作。该结论不代表远程CI/合并/部署、真实DeepSeek最大吞吐、所有模型数学最优容量或Gold Set准确率已验证；既有全仓遗留失败继续明确保留。

## 持续恢复与容量反馈（decision epoch 3）

用户最新决定重新打开本Change，旧epoch2 PASS不代表新完成定义。开发中独立审查首次为CHANGES_REQUIRED：RECOVERY-REV-001（MEDIUM/IN_SCOPE/BLOCKING/AUTO_REPAIR，RPS降低未切发送阶段导致迟到速率429级联下降）及RECOVERY-REV-002（HIGH/IN_SCOPE/BLOCKING/AUTO_REPAIR，无ready最低占额且空闲余数不可借，低C正常分片阻塞）。作者将两项作为完整机制包修复，先取得Red3failed/10passed，再验证旧速率迟到拒绝保持7/7/7、新阶段仍响应拒绝，C=1真实两片正常内容推进。Reviewer只读复用生产方法纯内存复核，001/002均CLOSED；健康RPS7→8.05→9.2575仍保持阶段成熟，真实/旧Fence未知占用不被借出。

Reviewer指出接续/Cancel竞争尚缺实际证据，未将其报成确认生产缺陷。随后两提交顺序通过正式Cancel API与实际SQL行锁等待补齐：Reaper先持旧Job锁，Cancel读取旧集合等待，接续提交后重取集合取消successor；Cancel先提交时Reaper不接续。已成功1项保持、其余2项取消，当前Job无queued/running。另有真实Service/Validator成功项不重发及successor插入失败事务整体回滚。两系统最终完整恢复/诊断/Planner文件各53passed。详见EVIDENCE.md。

最终基线为HEAD15dd366db6e1632535fadc615513636a4b22c639、分支fix/analysis-capacity-feedback的38文件未提交工作树，汇总c92ef47ce4b9fd698167bc826909ddc1db544d347168a5d79968b977a3409d24；完整逐字节清单与epoch2历史保留于REVIEW_BASELINE.json。当前最终A1/A2/质量结论待独立Reviewer按冻结清单核验，不能沿用开发中修复关闭结论作为整个Change的PASS。

该基线的最终独立结论为 **CHANGES_REQUIRED**。A1 已批准需求覆盖与 A2 持续恢复/接续/取消边界成立，但发现 **RECOVERY-REV-003 / MEDIUM / IN_SCOPE / BLOCKING / AUTO_REPAIR**：退避片已归还 C，仍参与按活动 Job 数均分 RPS，C=1 的唯一正常发送片只能使用一半全局速率。这是 **UNCHANGED_BASELINE / FIRST_REVIEW_ESCAPE**，此前 C=1 完整链只用无限制 RPS，未覆盖有限速率；保留首次漏检事实，不用旧 PASS 覆盖。

修复复用既有 Fence reservation 增加派生 RPS，在 Profile 行锁短事务中同时预留并由 Feedback 同事务读取。分配按可发送份额确定理想值，同时扣除其他未过期旧速率；零 C/ready 归还发送速率，恢复需求逐次归还借额。旧记录缺失或无限制表示未知，旧 Fence 及控制版本升级保留未知承诺；全局降档不能代替其他进程宣称已归还，小数速率不抬高下限。新增 shard_rps 聚合日志便于核对本片真正发送保护，不记录内容、响应或 Secret。

Reviewer 对草稿边界评估认为方向可行，未确认新的独立阻塞项，但明确 003 仍 OPEN，须冻结后取得真实多事务和两系统证据，不能把设计认可当成最终 PASS。最终修复复核在下方另行记录。

## decision epoch 4 最终独立修复复核

Reviewer `/root/capacity_review` 最终结论 **PASS / NO_FINDINGS_WITHIN_SCOPE**；RECOVERY-REV-003 **CLOSED**，001/002及CAP/MACHINE前序项继续CLOSED，没有确认新的范围内阻塞或残留UNCHANGED_BASELINE BLOCKING sibling。003的首次漏检保留。Review全程只读，无Git、DB、Docker、用户服务或付费模型操作。

Reviewer开始和结束两次核验当前38文件原始哈希、汇总`4a43dab236787296d96c7189fe451b6fd311cd523139b60e046296d326b6a229`、HEAD/branch、用户Prompt哈希；相对epoch3恰10文件变化，其余28字节不变，历史完整清单仍保留。已读取当前canonical Agent_Skills根入口/ENTRY/Router/Review/Coding及适用References，SHA与本阶段版本一致，没有用安装副本替代规则源。

独立核对共享Owner理想份额与旧承诺扣减、零/无限制/未知语义、机器受限唯一发送者、恢复者零速率后恢复、全局降档逐次归还、三片竞争、旧Fence/TTL/release、控制升级保留、Feedback暂停/同事务读取/提交后联合安装/异常target归零、无逐HTTP事务、小数及长间隔取消、shard_rps安全日志。当前机制切断空闲片按Job数稀释RPS的根因，同时保持全局保护，未声称其他进程旧速率瞬间收缩。

Reviewer实际独立执行冻结摘要/Git身份读取、纯内存调用当前Feedback回归、小数动态Retry回归及生产分配五个边界，全部Green；这些结果只证明控制流/计算，不冒充真实事务。实际解析Windows XML确认未变四文件74passed、预留初始16passed/1fixture失败及最终17passed/0failure/0error；三片资源事实的最后单项补验证据单独复核，不累计重复。Linux正式当前wheel332passed/97.32秒及35文件Ruff、422文件mypy、Contract/文档/Secret/diff检查按本轮作者工具事实与持久Evidence复核，没有再启动容器/DB测试。

A1 从最新用户决定及Blueprint第35/36节、AC1–AC18重建，R1–R17覆盖成立；A2从实现反查测试、三个现有正式文档Owner和当前Job/API/恢复/结果边界，覆盖成立。前阶段持续格式恢复、五分钟真实网络不可用、successor/Cancel两提交顺序、成功项不重发和legacy v1保持字节不变，复用相称的新鲜证据。没有把三片资源Fixture当成三个真实进程运行，没有扩大成真实DeepSeek吞吐、账号可用额度、Gold Set准确率或16核64GiB部署验收。

独立结论允许关闭当前unresolved_cleared及本地交付门禁；远程提交、push、PR、CI、merge、main-fresh、Archive、Issue Closure和部署仍不在本轮声明内。最终资源清理由主任务记录在EVIDENCE。

## 远程 main 本地同步最终独立审查（decision epoch 5）

Reviewer `/root/capacity_review` 针对最新授权重新复核，最终结论为 **PASS / NO_FINDINGS_WITHIN_SCOPE**，没有确认范围内阻塞项。开始与结束均读取 Git 身份，HEAD、本地 main、origin/main 同为 `64bfade138e6cdf0f86e8d8961a0415b8f994ea8`，任务分支仍为 `fix/analysis-capacity-feedback`；38项冻结清单逐文件核验通过，汇总为 `e90ee1e36245133a6bf8b230ba9e8c2e6170ad78dfa4990b4381a0bda829fb87`，用户 Prompt 字节哈希不变。前序 RECOVERY-REV-001/002/003、CAP-REV-001/002、MACHINE-REV-001/002/003 继续 CLOSED，首次漏检记录保留。

语义复核确认上游正式报告的快照、生成、下载、独立发布及 Worker 注册保留，本地 Analysis Planner、执行器、持续恢复和 successor/取消接续没有被替换；Provider 删除保护叠加而未覆盖 Analysis 保护，严格模型输出验证保持，报告冻结串行调用仍兼容可选 LLM hooks。品牌车型数据库目录优先、冻结回放、人工及后续写入保护与 Analysis Owner 边界未发现冲突；0078接续0077，无迁移分叉。前端生成 Client、报告面板和品牌筛选保留，没有重新引入 content_type 筛选。唯一共同修改的 Blueprint 自动合并完整，上游第23节与本地第35/36节及 AC1–AC18 均存在，AC10仅同步本地 main 的新授权。

A1 从最新同步授权、R18与上游正式决定重建；A2复核组合实现及本轮 Windows、Linux、前端、Contract、Schema 和文档证据。Reviewer 实际解析的 MAIN_SYNC_EVIDENCE.json 当时 SHA256 为 `47de51141b7ca006cd2c4316f6edad6861501df666f90be92bd470789a65fd2e`；随后只补充主任务实际清理与最终门禁记录，原测试记录保留。有效去重用例为 Windows 行为/API/Contract 524、Windows 独占 PG/Worker/品牌112、Linux384、前端274、浏览器Mock14；首次环境错误、修正后的复验和 skip 边界均保留，未累计重叠测试。

独立审查全程只读，没有运行数据库、容器、用户服务或付费模型，也没有自行重跑作者测试。它依据当前真实实现、逐字节身份和作者工具输出复核证据，没有将记录解析冒充测试执行。结论适用于当前 main 与未提交本地修改的组合，不代表所有 full CI、浏览器到真实后端全栈、付费模型准确率、吞吐或正式服务器部署已验收。没有新实现提交、push、PR、远程 CI、远程 merge 或部署；主任务实际清理另见 EVIDENCE 与机器记录。

## decision epoch 6 独立 Assembly（最终目标为 epoch 7）

Reviewer `/root/capacity_review` 于 2026-10-02 按新增要求独立重建 A1/A2，结论为 **CHANGES_REQUIRED**。本节一次汇总本轮全部已确认 Findings；没有沿用 epoch 5 PASS。审查开始后作者仅补充 README 导航与零请求空闲清理，最终按 epoch 7 复核这些变化及直接相邻路径。前序 CAP、MACHINE、RECOVERY Findings 继续 CLOSED，历史 First-pass Coverage Miss / FIRST_REVIEW_ESCAPE 记录保留。

审查身份：HEAD/base `64bfade138e6cdf0f86e8d8961a0415b8f994ea8`，分支 `fix/analysis-capacity-feedback`，38 项文件原始 SHA256 全部与 [changes/active/CHG-20261001-112055-analysis-capacity-feedback/REVIEW_BASELINE.json](REVIEW_BASELINE.json) 一致，汇总 `0d8d65adf1f0283db7f42138ce92f605f2061896b237922ad958cc2c9931a502`。摘要按该文件规定的 UTF-8、sort_keys、无额外空白 JSON 计算；相对 epoch 5 有 15 项变化，其余 23 项字节相同。用户 Prompt SHA256 仍为 `9e0489a330dd1a5bffcdea90703310e37eb1abf4cdf7aa53224a44864e261741`。epoch 6 的历史冻结身份仍保存在嵌套清单中。

实际读取了项目根与 docs 规则、Blueprint 第35/36节及 AC1–AC20、Change、当前实现/调用链/测试/三个正式文档 Owner。当前 canonical Agent_Skills 根 → ENTRY → Router → Coding/Review/Testing/Docs 与适用 References 经授权 GitHub 默认分支重新取得；Review Skill SHA 为 `e2e50d120e266999122bffecc3633cd48998bfbe`，执行流程 Reference SHA 为 `4bb26b5388c5fbd716c8616e4b4fb24d4815fe09`，Coding SHA 为 `62c9bf03d8b85353fe7fee97e5dd53dea12b06a1`。没有把安装副本当作规范源。

### A1、A2 与 Coverage Map

上游完成定义包含：按真实机器和模型容量尽快成功入库；稀疏格式错误持续严格修复；以充分负载、成熟结果和跨窗墙钟证据学习；每个目标成功才允许正常 succeeded；真实连续五分钟断网、硬错误及手动取消仍显式停止；保留 thinking、Prompt、Validator/repair/judge、历史冻结协议、Fence、幂等和持久恢复；只在本地并隔离验证。R19–R21已纳入 Change，AC19/AC20来源可追溯，未发现遗漏上游需求。当前 Change 的三项仍为 not_satisfied、状态 in_progress；历史勾选不能替代本轮完成审计，须在修复及证据闭合后更新。

| Root Invariant / Material Projection | 本轮检查与证据 | 状态 |
| --- | --- | --- |
| 同一 C 的跨窗加权成功量/时间、延迟与样本门槛、两块平台确认、快速恢复 | Controller 与正式 Repository 窗口合并；稀疏格式、峰谷、100/500/2500及容量突降恢复模拟 | covered；候选失效边界有下方阻塞 |
| 不适用候选在空闲、低需求、本地压力和发送策略切换后失效 | 零请求新修复、普通低负载、C/RPS收紧、最后 Fence 退出、低样本且本地受限 | 最后退出与低样本本地受限两投影 confirmed defect |
| 物理拒绝分类与共享保护 | Adapter 明确 request/token 429 优先，Feedback原样聚合，未知反馈路径，旧阶段拒绝隔离；同事务 C/RPS 和 finally 归还 | covered；未发现新阻塞 |
| 搜索版本升级、历史承诺及回滚 | v2→v3只丢弃证明，保留未过期 C/RPS reservation；Revision/sentinel/Prompt保持；新 JSON字段回退前排空并重建派生Profile | covered；不是业务结果迁移 |
| 只有全部目标成功才能 normal succeeded | 基础/高吞吐统计含未投放 pending；新 v2 refresh_run检查成功数等于target；真实 stale 回归与201条三片六轮格式失败 | covered；stale保留且partial_failed，不计成功 |
| 持久恢复、成功不重发、取消/Deadline/successor/Fence | 本轮四组PG及未变化前阶段直接链；正式Service、Validator、defer、current Request Job、Cancel两提交顺序 | covered；未发现新阻塞 |
| 思考、Prompt和严格输出规则 | 请求生成无thinking关闭字段；冻结合规Service/Validator与repair/judge保持；Prompt字节核验 | covered；未声称真实语义准确率实测 |
| Windows/Linux资源、打包、文档和外部副作用 | Win全后端/PG与目标回归记录；Linux正式wheel最终组仍待结果；本轮无用户环境或付费调用 | Linux证据 pending；不能宣布最终完成 |

反向审计从 Run API 的结果和统计回溯 Item/Request/Job，再检查 Worker 正常返回、明确停止、未投放统计和旧成功复用。新增 succeeded 门槛不修改输出 Contract；声音广场内容类型修复及 main 报告/品牌组合的未变化字节和前阶段证据按新鲜性复用。Docs targeted 的当前说明与实际链一致，但“低需求/本地受限清除候选”须以下方修复闭合，不能通过弱化说明消除缺陷。没有发现其他确认阻塞或相邻无关技术债需扩大范围。

### CAPACITY-V3-REV-001 — 不适用的未完成候选可跨退出/本地受限阶段继续参与升档

**Severity: MEDIUM；Scope: IN_SCOPE；Delivery Effect: BLOCKING；Action: AUTO_REPAIR；Provenance: NEW_REQUIREMENT / 新 v3 diff及epoch7直接相邻路径；状态 OPEN。**

位置一：[backend/src/aima_ugc/adapters/persistence/postgres/analysis_capacity.py](../../../backend/src/aima_ugc/adapters/persistence/postgres/analysis_capacity.py) 第542–565行 `release()`，尤其551–560行。最后 Fence 退出只重置 window/epoch，不清除 v3 `state.evidence_*`。正常末次 refresh 若尚不足两秒不会进入297行的闭窗；取消/异常收尾也可直接走 finally release。之后同身份 `ensure()`不热启动，空闲期间没有 Worker 调用 `observe()`，因此新增纯空闲 observation 的清理分支没有执行机会。

位置二：[backend/src/aima_ugc/modules/analysis/adaptive_capacity.py](../../../backend/src/aima_ugc/modules/analysis/adaptive_capacity.py) 第223–229行。低成功数先返回；在 `demand=True、local_limited=True` 时保留原候选，尚未到下面的本地受限 `clear_evidence()`。正式 Repository 能因至少三次超时关闭这一窗，因此不是仅人工调用纯函数才会触发的分支。

独立纯内存复现使用当前真实 Repository `observe/release/ensure`、真实 Controller 与现有内存 Session，没有 Engine/DB/HTTP。先从 `C=100、last_safe=50、last_safe_throughput=3、P95=12` 经两个真实充分负载、成熟的两秒窗，各成功10项，得到**可达**状态 `evidence_seconds=4、evidence_persisted=20、reason=collecting_capacity_evidence`，不是直接伪造未可能到达的候选。第五秒末次零delta未闭窗后释放最后Fence；五分钟后同身份 ensure仍返回4/20。新批两秒成功30项立即升到 **C=200**，接受吞吐 **50/6=8.333…**；清除旧候选的对照仍为 **C=100 / collecting_capacity_evidence**。另一分支通过生产 Repository 输入两秒 `requests=4、persisted=1、timeouts=3、busy_seconds=200、demand=True、local_limited=True`，同样保留4/20，下一窗同样提前升到200。命令均为既有 `.venv/Scripts/python.exe -B -` 的内联脚本，exit0；输出值实际核验。

实际影响是新批或本地瓶颈恢复后的少量样本借用了已失效累计，提前满足样本/时间/收益门槛，把混合阶段吞吐接受为新安全档；也可能影响平台回退判断。这违背 AC20/R20 的有效候选证据边界，会再次造成不可靠升降档和重复探测。它不绕过 Validator，也不把未成功 Item计为成功；严重度因此为MEDIUM。

Counterevidence：epoch7新增 `test_idle_gap_discards_unfinished_capacity_evidence` 仅调用 Controller的纯空闲样本；运行间隔没有这一调用。现有尾部测试没有从非零未完成候选出发走最后release；本地受限回归用充分成功数量，会到达229行，未保护223行的早返回。正常长尾经过完整低需求窗时确实会清候选，但不足两秒退出/取消路径不保证经过该窗，不能排除此触发。

收口方向：在候选失效的 Owner 边界清除 `evidence_*`，保持已学习安全档和历史吞吐；最后有效持有者结束时清候选，其他活动/未知Fence仍存在时不能无条件擦除共享候选。本地受限的失效应覆盖低样本早返回。验证应至少覆盖：可达非零候选→不足两秒末次刷新→最后Fence释放→空闲→同身份新Run；低样本/超时闭窗的本地受限；仍有peer时退出不误清共享证据；C/RPS真实占用和旧Fence保护不变。真实PG应补最后释放/重新启动事务边界；纯Controller/Repository内存回归保护分支顺序。两投影属于同一候选生命周期不变量，作为一个修复包处理。

### Evidence 与完成边界

已解析 [changes/active/CHG-20261001-112055-analysis-capacity-feedback/CAPACITY_PROBE_EVIDENCE.json](CAPACITY_PROBE_EVIDENCE.json)：Windows全后端1841passed/16skipped/12subtests为idle局部修复前的全范围结果，修复后反馈/工作量26passed提供新增路径当前证据；epoch7四组真实隔离PG77passed包含201条三片与六轮不合法输出、成功仅一次、旧v2控制升级、取消和持久恢复。既有控制器/分类Red5、stale门槛Red1、idleRed1保留。不能把这三组重叠累加为不同用例总数。

模拟的200条完成为44个虚拟秒；200000条仅运行1200秒观测持续吞吐，并非所有200000条完成。100/500/2500稳态约为静态同延迟参考的87.5%/89.1%/88.5%，只证明受控事件模型，不是付费DeepSeek、账号额度、机器满载或Gold Set准确率结果。原始Windows隔离runner错误、Linux缺libpq5/测试文档/scripts的失败已记录，不冒充Green、不改生产guard。

本报告落盘时Linux字段仍为 `final wheel validation pending`，最终Linux正式wheel组、当前静态/Contract检查和本轮Completion Audit由主任务补充；此处没有宣布Linux通过或完整交付。已保留的排空新协议Run后重建派生Profile回滚说明覆盖新增JSON字段，不能直接将v3未知字段交给旧v2代码构造器；没有新增业务Schema、依赖或Migration head。

Reviewer只做只读Git/文件、canonical读取和纯内存生产调用，唯一写入为本节审查资产；未启动测试服务、数据库、Docker、浏览器或收费模型，未创建缓存/测试文件、改生产/测试代码或Git。最终完成须先关闭 CAPACITY-V3-REV-001，取得必要新鲜两系统证据，并据本轮上游要求更新R19–R21/Completion Audit。当前不允许 unresolved_cleared 或本地完成声明；没有授权commit/push/远程合并/部署。

## decision epoch 8 独立 REPAIR_DIFF 关闭复核

Reviewer `/root/capacity_review` 于 2026-10-02 对上述单个修复包完成集中复核，结论为 **PASS / NO_FINDINGS_WITHIN_SCOPE**。CAPACITY-V3-REV-001 两个已确认投影均 **CLOSED**；没有确认新的范围内阻塞项或 UNCHANGED_BASELINE BLOCKING sibling。本节关闭 epoch7 的 Findings，不改写前节 CHANGES_REQUIRED、当时 Linux pending 或先前 First-pass Coverage Miss / FIRST_REVIEW_ESCAPE 事实。CAP、MACHINE、RECOVERY 已关闭项及其原始首次漏检记录继续保留；当前候选生命周期 Finding 是新 v3 范围在首次 Assembly 发现的项，不将其改标为旧基线漏检。

### 实际冻结身份与范围

开始与结束均逐字节检查当前38项清单：HEAD/base `64bfade138e6cdf0f86e8d8961a0415b8f994ea8`，分支 `fix/analysis-capacity-feedback`，decision_epoch=8，原始文件汇总 SHA256 `3de577e65419ed45c4c77b44718d5eeef4ff8239ad1cea1c7a2c4f9afbc2d3a5`。计算使用 UTF-8 的 `json.dumps(files, ensure_ascii=False, sort_keys=True, separators=(',', ':'))`。当前持久 REVIEW_BASELINE.json 自身 SHA256 为 `a8a6c869940546fe79a36daa8f0c99e19fdd86d54d1362d6338594edcf5aaf41`。用户 Prompt SHA256 仍为 `9e0489a330dd1a5bffcdea90703310e37eb1abf4cdf7aa53224a44864e261741`，没有修改用户内容。

相对嵌套 epoch7 只5项字节变化：`adaptive_capacity.py`、PostgreSQL `analysis_capacity.py`、专题 `07_AI舆情打标与分析实现.md`、`test_analysis_capacity_reservations.py`、`test_capacity_feedback_regression.py`；其余33项完全相同。复用上一节已完成的 v3、结果成功门禁、429 分类、恢复/取消/Fence/Planner 和质量链审查，只检查当前修复及直接相邻生命周期，不重新开启 FIRST_REVIEW。项目真实规则和当前 canonical Source Mode 在本轮连续审查中已读取，规范身份见前节；未以安装副本或旧阶段 PASS 替代。

### A1 / A2 与修复 Coverage Map

重新对照最新用户决定及 Blueprint AC18/AC19/AC20：正常完整退出要求每个目标成功；未投放/正常 pending 持续推进；格式持续严格修复，保留思考和 Prompt；五分钟真实断网、硬错误和手动取消显式停止；同容量成熟且充分负载的成功量/墙钟证据才用于收益判断。候选生命周期是该完成定义的直接组成部分，没有新增业务决定或需求遗漏。Change R19–R21 的来源已对应稳定 AC anchors。本次复核所读取的早期施工快照中三项仍 not_satisfied、Change仍 in_progress；主任务随后已依据本轮证据与独立结论更新为 satisfied、ready_for_review，并完成本轮四项 Completion Audit。最终措辞复核已实际读取这些记录，早期快照不代表报告落盘时的最终状态，也不删除此前 pending 历史。

| 修复路径 / 不变量 | 独立检查、反证及证据 | 结论 |
| --- | --- | --- |
| 最后 Fence 退出后候选失效；安全档保留 | PG Owner `release()` 第542–567行持 Profile 行锁，删除精确 Job/Lease key；仅无其他 reservation 时重置尾窗/epoch，control3 经 clear_evidence 只清四个候选字段 | CLOSED；安全容量、吞吐与其他学习字段保留 |
| 仍有活动 peer / 未知旧 Fence 不误清共享状态 | 释放当前精确 key 后按剩余字典判断；没有按 Job ID 整体删除，也没有本轮新增 TTL/接管捷径；真实 PG 的 peer/unknown 参数保留原 C/RPS entry | covered；没有新的占用或接管风险 |
| 旧控制协议继续原状态 | `state.get('control_version') == CONTROL_VERSION` 才构造新 CapacityState 并清候选；旧版本不被新字段解释 | covered；独立内存 legacy 分支证明状态原样保留 |
| 本地受限低成功量早返回也清候选 | Controller 第223–231行 local_limited 已移至低成功数判断前；零请求本地受限已有失效分支，发送策略收紧仍由 Owner 清证据 | CLOSED；新增低样本且三个超时回归不是降低成功门槛 |
| 调用链、事务与锁顺序 | 正常末次 refresh、release 参数路径及异常 finally 均进入同 Owner；Profile-only 清理不新增 Job 锁；观察仍 Job→Profile；事务失败整体回滚，独立 Fence 不删接管者 | covered；没有确认相邻阻塞 |
| 测试和正式说明与机制一致 | 单元第60行低成功/超时/本地受限；PG第468行 last/peer/unknown，从实际生产 observe 得到4秒20成功候选，经不足两秒尾窗、真实 release、5分钟空闲和同身份 ensure/reserve；专题第715行同步此生命周期 | covered；没有平行控制算法或放宽断言 |

反向审计沿末次 Worker 刷新/异常收尾回到 Owner release，再检查同身份新任务 ensure 和下一窗观察；未变化的 Run API→Item/Request/Job→持久成功门禁、successor 和取消双提交顺序沿用上一节已核验链。当前修复不影响 Prompt、请求生成参数、Validator/repair/judge、业务幂等、恢复版本、未投放统计或结果提交；旧控制回退仍要求排空新协议 Run/预留再重建派生 Profile，业务结果保留。

### CAPACITY-V3-REV-001 关闭证据

原标识、严重度及范围保持：**MEDIUM / IN_SCOPE / BLOCKING / AUTO_REPAIR**；本次状态改为 **CLOSED**。两个投影都由 Owner/Controller 生命周期机制修复，未以弱化文档或断言消除 Finding。

Reviewer 实际独立运行纯内存 `.venv/Scripts/python.exe -B -`，只使用既有 `_MemorySession/_MemoryCapacityRepository` 替换存储/时钟，调用生产 `observe/release/ensure` 和 Controller，不创建 Engine/DB/HTTP。C100、last_safe50、已接受吞吐3、P95=12，经两个真实充分负载成熟的2秒/10成功窗得到可达4秒/20候选；1秒尾窗不闭，最后 release 后候选为0，同身份空闲5分钟再观察2秒/30成功，只保留新候选2秒/30且 C仍100，不能借旧累计升到200。peer/unknown 均保留20候选和完整原状态；额外 legacy control2 分支完整原状态保持。低成功/三个超时/local_limited 分支候选归零、安全档仍100与吞吐3。最终全部内存断言 exit0。

透明保留 Reviewer 探针过程：第一版内联脚本错误期待 reason=`collecting_probe_results`，实际正式标识为 `collecting_capacity_evidence`，因此该探针 AssertionError 不作为失败产品证据；随后读取实际状态，并改用 C、新候选时间/数量及原状态不变这些行为断言，完整四分支和本地受限探针通过，没有写入或修改项目测试。

作者 Red 证据为本地受限低样本1failed、PG last/peer/unknown 1failed/2passed；修复 Green为同三参数3passed和 feedback/workloads 27passed。该三参数使用真实 PostgreSQL 多事务、生产 Owner/控制器及明确受控墙钟，覆盖了原症状和关键复发路径。没有为了获得 Green 提高样本预算、减少断言、删除测试、关闭 thinking 或放宽输出校验。

### 当前 Evidence 与完成边界

实际解析 CAPACITY_PROBE_EVIDENCE.json，解析时自身 SHA256 为 `f90f674102e92c639c36ff6d36739095c0519761fd9c1d17de0afd67953e763c`；其中 decision_epoch、HEAD、branch、aggregate 与冻结清单一致，Linux controller SHA256 `656e3e7e6526c4c59d458ad353af9f1f76b48466540fd78adb9a3044e355e803` 同时匹配本机当前文件和清单。当前作者工具记录为：

- Windows完整 Unit/Contract/API：1843passed、16skipped、12subtests，93.14秒，exit0。
- Windows四组真实隔离PG：80passed，139.70秒，exit0；包含最后退出回归以及201条/三片/六次非法JSON后合法成功、正常200条不重发、全部结果成功和预留释放等链。
- Linux当前正式 uv wheel build/install 到 site-packages，Python3.14.7，非root10001:10001，3CPU/3GiB：analysis unit、stage12 planner与同四PG组358passed，132.54秒，exit0。先前缺libpq5/测试资产与uv缓存权限的无效环境执行保留，未当成生产通过。
- 当前真实 Chrome→Frontend→API→Worker→独占PG→FakeHTTP 两个既有 spec：2passed，38.1秒，exit0；独占服务端口清空的作者记录已保存。它补足了前节当时尚缺的本轮页面结果链，范围仅这两个 spec。
- 当前 Ruff、mypy430源、Contract漂移/兼容、Docs/Facts、架构、Table Ownership、Secret与diff检查记录 exit0；没有新增API字段、业务Schema、依赖或Migration head。

各组重叠且部分重跑，不相加为不同测试总数；Reviewer解析作者实际结果并检查证据身份，没有自行执行PG/Linux/浏览器测试或把解析冒充运行。200条模拟44秒仅虚拟时间；20万条只观测1200模拟秒稳态，不是全部完成，更不是付费DeepSeek、账号实际额度、服务器满载或Gold Set准确率对照。保留准确性机制并不等于语义准确率已量化验收。外部模型永久给出非法输出时，持续重试保证未成功项不伪装正常完成，不承诺最终一定获得合法答案。

本次复核所读取的早期施工快照中 JSON cleanup.status 仍 in_progress；主任务随后已完成自己的资源清理与本地收口。最终措辞复核实际解析的 CAPACITY_PROBE_EVIDENCE.json SHA256 为 `04a32158c294a6ea6a1f5416f641a1797fb99388b15c6716e4a93d93b8b78273`，cleanup.status=complete、Finding=CLOSED。作者记录五个专属容器、专属匿名卷/镜像/network查询为空，55493–55496无监听；scratch及九个仓库外临时目录经owner/固定路径核验、先移除三个仅指向本次夹具的junction后，以原生LiteralPath精确删除，原.venv与frontend/node_modules仍存在。作者执行 `check_change_completion.py --root . --require-active-ready` 报告exit0、gated152/strict152/legacy128；Reviewer已读取当前ready_for_review、R19–R21 satisfied及Completion Audit四项勾选，仅读取/解析最终事实，没有自行运行清理、端口查询或该Ready命令。该收口属于审计/交付记录，不改变已冻结实现，早期pending历史保留。结论限于当前未提交本地代码和既有 main 组合；没有commit/push/PR/remote CI/merge/Archive/Issue Closure/部署验收。

Reviewer全程仅只读Git/文件和无缓存纯内存调用，本节是唯一写入审查资产。没有新发现的 IN_SCOPE BLOCKING 项；无需再扩大修复包或重复不变范围测试。最终范围内结论 **PASS / NO_FINDINGS_WITHIN_SCOPE，CAPACITY-V3-REV-001 CLOSED**。
