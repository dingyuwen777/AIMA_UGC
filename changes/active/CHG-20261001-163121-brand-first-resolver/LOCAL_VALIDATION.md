# 品牌先行识别本地验证

本记录对应 `feature/brand-first-resolver` 的实现工作树；开工治理提交为 `04cccef5b5038b03fafab437bc32343a03683342`、基线 main 为 `15dd366db6e1632535fadc615513636a4b22c639`。当前处于实现和 Repair 验证，尚未 Final Ready，不能把未提交工作树测试替代最终提交的 CI、Review 与 current-base 检查。后续冻结时记录生产源文件摘要并复核最终提交。

实现检查点已保存并推送为 `36f0f7f5edf7d8f898a957b275a6b59dcd6e8036`。逐个读取该 HEAD 的18个生产 Git blob，全部与 EVIDENCE.json 的测试源码摘要一致。新增浏览器断言已在该提交的当前源码上完成最后全栈运行，以下记录据此更新；PR仍Draft，报告合入后再取得最终组合的Ready证据。

## 范围及隔离

只修改 `E:/Desktop/AIMA_UGC`。`E:/work/03_Aima/code/AIMA_UGC`、它的进程、数据库和既有容器不参与验证。复用本任务创建的 PostgreSQL 18.4 容器 `31c4b9340204766d8e24ab9d916ed80a67285a48228335372d5c970f81c7bea2`，标签 `codex.goal=brand-first-20261001`，仅绑定 `127.0.0.1:55437`，上限 1 CPU/1 GiB。品牌测试库为 `aima_brand_test`；报告库 `aima_report_test` 未降级或删除。

普通角色另有独立 `aima_codex_brand_ci_test` 用于 CI 凭据保护的平台注册测试，不具有超级用户、建库、建角色权限。历史迁移测试需要创建临时数据库和设置 session_replication_role，使用自有容器既有初始化账号执行，未新增或扩大高权限账号。测试脚本在连接和清表前核对固定 loopback、55437、专用库名与账号。测试 Secret 为本地假值，不提交、不进入日志。全部 Provider/LLM 为 Fake/Mock，没有真实 TikHub、模型或飞书请求。

`python` 为仓库根 `.venv/Scripts/python.exe`，Python 3.14.7。`.runtime/brand-unit-validate.py` 清理外部配置；`.runtime/brand-validate.py` 只装配专用数据库；`.runtime/brand-suites-local.py` 在每套前复用 CI 种子恢复，保持项目 CI 的分套空库边界，不修改测试断言。包装脚本不复制生产业务规则。前端 Mock 浏览器仅启动专属端口 55438。

## 缺陷复现与专项验证

| 场景 | 实际命令 / 原始记录 | 结果及范围 |
| --- | --- | --- |
| 算法初始 Red | `python -m pytest tests/unit/test_brand_first_resolver.py -q -p no:cacheprovider --junitxml=.runtime/brand-resolver-red.xml` | 10 failed / 8 passed，复现首字段遗漏、无品牌反推、短车型误命中、共享别名及人工范围 |
| Resolver、旧新 codec | `python .runtime/brand-unit-validate.py tests/unit/test_brand_first_resolver.py tests/unit/test_brand_vehicle_resolver.py tests/unit/test_brand_resolver_snapshot_semantics.py -q`；`.runtime/brand-expanded-core.xml` | 56 passed；保留原 v1 回归、全字段与 transcript、稳定证据、人工空锁、索引复用 |
| 正式来源链 | `python .runtime/brand-validate.py` 运行新 Replay/Owner 基线、Stage5 Account/Query、Current 并发、Stage12 Campaign、Stage8b Import、Collection 专项；`.runtime/brand-source-final.xml` | 65 passed / 40.23s，证据属于 selected 冻结修复前的实现，后续完整分套覆盖最终源码 |
| Replay/Owner 基线 | 新 Replay 与 `test_brand_replay_owner_baseline.py`；`.runtime/brand-chain-owner-final.log` | 16 passed / 13.70s；真实 before、准备账号、保护较新写入、连续及断链负→正和撤回 |
| selected 目录冻结 Red | `python .runtime/brand-validate.py tests/integration/vehicles/test_brand_first_frozen_cleanup.py -q --tb=short --show-capture=no --junitxml=.runtime/brand-frozen-scope-red.xml` | 2 failed，精确复现 frozen A→live B 留残留、frozen B→live A 误清理 |
| 冻结范围与 legacy Green | `python .runtime/brand-validate.py tests/integration/vehicles/test_brand_first_frozen_cleanup.py tests/integration/ingestion/test_brand_first_replay.py tests/unit/test_brand_resolver_snapshot_semantics.py -q --tb=short --show-capture=no --junitxml=.runtime/brand-frozen-and-legacy.xml` | 23 passed / 19.94s；含 deprecated/跨品牌 merged、范围外和人工保留；正式旧任务在 v2 部署后执行并保持幂等，新 v2 再收敛 |

冻结范围 PG 专项调用真实目录 Repository、正式车型管理 Service 和 Evidence Owner；完整 HTTP/Worker 接线由 Replay 与来源链测试覆盖，不能把该专项单独描述为完整用户浏览器旅程。

## 最新完整及静态验证

| 验证 | 实际命令 | 当前结果 |
| --- | --- | --- |
| 单元 / Contract / API | `python .runtime/brand-unit-validate.py tests/unit tests/contracts tests/api -q --tb=short --show-capture=no --junitxml=.runtime/brand-backend-frozen.xml` | 1753 passed、16 skipped、12 subtests passed，66.64s；保留既有 opt-in 跳过 |
| Ruff | `python -m ruff check backend tests scripts`；`python -m ruff format --check backend tests scripts` | PASS；5 个本次修改测试文件统一格式后，全目录 861 files already formatted |
| mypy | `python -m mypy backend/src` | 421 source files PASS |
| 生成 Contract / 兼容 | `python scripts/contracts/generate.py --check`；`python scripts/contracts/check_compatibility.py` | PASS；内部快照新增字段没有公共生成 Contract 漂移 |
| Frontend 单元 / 构建 | `npm run test -- --run`、`npm run build` 与受影响文件 ESLint | 274 项通过；TypeScript/Vue/Vite PASS；既有主包 500kB 警告保留 |
| 受影响浏览器 Mock | `npm exec playwright test -- --config playwright.report-local.config.ts`，四个声音广场 spec；`.runtime/brand-front-e2e-final.log` | 45 passed / 36.8s；真实点击“含竞品”发送 competitor_only+mixed，再取消 mixed 保留仅竞品 |
| 文档 / Owner / Secret | check_docs、check_docs_facts、check_table_ownership、check_architecture、scan_secrets | 当前 PASS，完成记录修订后须重新运行相关检查 |

## 完整 PG 重跑与失败归因

第一次单次 `tests/integration` 执行得到 **518 passed / 60 failed**，不能称为通过。项目 CI 在每个子套件启动独立 pytest session，并恢复空库；该本地单次执行没有相同边界。分析入口失败用例单独运行取得 2 passed，提示目录残留的顺序依赖，不能据此证明全部失败无关。另平台注册安全断言要求 CI 假凭据，本地假凭据不相同。

第二次使用普通角色复用 CI 模式：platform **56 passed**，database **87 passed / 2 failed / 30 errors**；实际错误为缺少建库及 session_replication_role 权限，与测试账号能力不匹配。保留该失败记录；未降低断言或增加超级用户权限。

随后 platform 使用普通 CI 测试角色，其余套件使用自有容器既有初始化账号，逐套前仅清理固定 `aima_brand_test` 并恢复 CI 种子。实际命令为 `python .runtime/brand-suites-local.py tests/integration/<suite> -q --tb=short --show-capture=no --junitxml=.runtime/brand-suite-<suite>.xml`。七套均 exit 0，共 **581 passed**：platform 56、database 119、jobs 20、collection 143、content 127、ingestion 111、vehicles 5。原始记录为 `.runtime/brand-ci-platform.xml` 和六份 `.runtime/brand-suite-<suite>.xml`。该分套执行完整覆盖初次失败的分析、人工相关性、粉丝数及平台注册场景；前述失败保留为运行边界不一致的失败记录。

完整真实浏览器全栈通过 `.runtime/brand-fullstack-local.py` 执行，复用普通角色的独立 CI 测试库，API 55439、Vite 55440、本机 Fake LLM 8091；启动前检查端口空闲，不复用既有服务。Fake TikHub Worker 复用正式 Worker Registry 与 Mapper。

首次浏览器记录有 7 个失败场景（截图/trace 保留在 `.runtime/brand-fullstack/browser-results`）。两项真实原因分别是：管理员旧 fixture 的品牌识别词不在内容中，依赖已取消的车型反推品牌；本地包装清库恢复投影为 pending，却没有复用生产启动的回填调度。更正 fixture 明确命中配置品牌，并由 `ensure_voice_plaza_projection_backfill_job` 创建正式可恢复 Job，在 ready 后启动浏览器，不直接改数据库状态或业务查询。第二次完整运行 `.runtime/brand-fullstack/browser-final.xml` 取得 **15 passed / 1 failed**，剩余失败为旧 import 来源显示断言“系统识别”，新版来源 alias_match 实际显示“词包 / 别名识别”。更新为批准的来源断言，并增加正式详情 API 的品牌及车型 alias_match、matched_text 校验；补充断言的一次辅助函数拼写错误已修正，随后取得下述16项通过的最终运行结果。

最终执行 `python .runtime/brand-fullstack-local.py`，使用同一正式API/Worker、专属普通角色库、Fake Provider和本机浏览器：`.runtime/brand-fullstack/browser-complete.xml` **16 passed / 0 failure / 0 skipped**，2.5分钟；`.runtime/brand-fullstack/browser-complete-exit.json` 的 returncode=0。其中管理员真实配置、导入、品牌/车型查询、详情实际持久证据和导出均通过。前两轮15/1以及初次7个失败记录继续保留；没有删除断言或增加超时预算。

`EVIDENCE.json` 保存 18 个实际生产源文件的 LF 规范化 SHA-256（生产集合摘要 `56da1bcfb53377a043130cb772b9af76098a64e85cb450d3fca4709e9f895d39`）以及原始 XML 摘要和结果，包含初次失败；后续只有测试文件统一 Ruff 格式和补充实际来源断言，生产源保持相同。该证据只绑定本地实现，最终交付仍需 commit/base/Review/CI 新鲜证明。

匹配机制的复杂度说明限定为各个 Aho-Corasick 自动机的一次扫描 `O(文本长度 + 命中数)`。整体 v2 还包括逐个已确认品牌的车型扫描、候选排序与局部归属判断，不把索引复用测试描述成全链路严格线性复杂度或生产吞吐基准。

## 审查及交付状态

独立只读 Repair 审查 RV-BRAND-01–09 已关闭。修复涵盖实际 Current、负向收敛、人工范围、Current 锁、旧 import 文本证据与 SQL NULL、正常来源/审核继承、Collection 索引复用及 selected 冻结清理集合。审查针对未提交工作树，未发现新的 P1/P2，仍须最终 current-head/current-base Review。

原实现记录时 PR #687 保持 Draft，最终组合门禁尚未执行；下述组合验证取代该状态描述。原报告 PR #686 的失败记录和原分支保留，不重命名历史 Change 身份。


## 报告合并后的当前组合验证

报告已由 PR #688 合并为 `e69b3d3829e2feb13d7e590cfc535bde58e493d6`，原生 Change 归档及 main-fresh 检查完成后 main 为 `dd821ca86a64951d4f7add4d39b6129368aac18d`，Issue #684 已关闭。本分支同步该 main 的提交为 `143f5a0bca6b5be72d4f574367fe358c69db0c7c`。唯一合并冲突为代表声音截图单元测试的同义隔离调整，采用已通过报告门禁的 main 版本；18个品牌生产文件的Git blob仍与实现提交36f0f7f5和原生产源摘要逐一一致。

自有三个测试数据库迁移到报告引入的当前0078。当前组合只使用同一自有容器和此前专属端口，全部新记录使用独立文件名，保留原始失败及通过记录。Windows 测试包装显式设置 `PYTHONUTF8=1`，让子进程继承UTF-8；pytest临时目录位于独立系统Temp，避免Git父目录和旧临时目录ACL干扰治理测试。

| 验证 | 实际命令 / 原始记录 | 当前组合结果 |
| --- | --- | --- |
| 完整后端 | `python .runtime/brand-unit-validate.py tests/unit tests/contracts tests/api -q --basetemp=C:/Users/YNND/AppData/Local/Temp/aima-codex-brand-combined-unit-20261001 --junitxml=.runtime/brand-combined-unit.xml` | 1782 passed / 16既有skipped / 12 subtests passed，83.96s；XML1810条/0 failure/0 error |
| 报告持久链路 | `python .runtime/report-validate.py tests/integration/reporting -q --junitxml=.runtime/brand-combined-report.xml` | 9 passed / 1显式浏览器opt-in skipped；19.47s |
| 冻结与人工/贡献账本 | `python .runtime/brand-suites-local.py tests/integration/vehicles/test_brand_first_frozen_cleanup.py tests/integration/vehicles/test_content_reclassification_postgres.py tests/integration/ingestion/test_brand_first_replay.py tests/integration/content/test_brand_replay_owner_baseline.py -q --junitxml=.runtime/brand-combined-owner.xml` | 24 passed / 20.72s |
| CI精确PG目标组合 | `python .runtime/brand-suites-local.py <brand-combined-preflight.json 的 postgres_targets> -q --basetemp=C:/Users/YNND/AppData/Local/Temp/aima-codex-brand-combined-ci-targets-20261001 --junitxml=.runtime/brand-combined-ci-targets.xml` | 当前classifier选择8个文件，同一pytest session中96 passed / 123.29s；不是用单文件通过替代组合验证 |
| 完整用户关键路径 | `python .runtime/brand-fullstack-combined-local.py`；`.runtime/brand-fullstack-combined/browser-complete.xml`及exit.json | 16 passed / 0 failure / 0 skipped，exit0；2.1分钟；完整HTTP/Worker/Fake供应方/浏览器 |
| 前端与构建 | `npm run test -- --run`、`npm run build` | 36文件274 passed；TS/Vue/Vite通过；既有主包大小警告保留 |
| 静态、Contract、文档 | Ruff check/format、mypy、generate --check/check_compatibility、check_docs/check_docs_facts/check_table_ownership/check_architecture/scan_secrets | 全部通过；874文件格式、428源文件类型检查；原始日志brand-combined-*.log |

`EVIDENCE.json`的`combined_validation`绑定上述提交/base、18个品牌Git blob、5份实际XML和全部检查日志的SHA-256。旧证据保留，不把旧581项PG分套结果冒充新组合结果；最终远程CI负责当前组合的全部PG分套和完整Mock浏览器。当前classifier为backend/frontend/fullstack/postgres all，并选出8个PG文件；字体标志为false，但main工作流在all/reporting套件仍安装Noto字体，覆盖本组合报告图表。

独立Repair复核绑定143f5a0b/base dd821ca8，RV-BRAND-01–09全部closed，NO_FINDINGS_WITHIN_SCOPE。审查重新读取Issue #685、引用方案和用户数据库配置决定，核对18个生产文件及旧新XML，报告读取版本化有效Evidence并冻结的消费者边界没有断裂。本地完成定义与当前组合覆盖满足Ready准备要求。

本记录中的组合验证为本地证据；本批最终HEAD的独立Review、required CI、expected-head merge、main-fresh、原生归档、Issue #685 AC21/Closure和cleanup由交付阶段持有，必须通过live读取完成，不能由本地结果代替。


## 当前head CI顺序缺陷与修复

Ready head `4b4e6b846a5e39ff9f701c57e47e67c47f5a3e83` 的CI run36869347726必须记为失败，不能由其余Green覆盖。PG job110392868740实际先96 targets通过，然后在旧Migration0062的Campaign状态check回退失败。pytest session fixture仅在启动清库，没有结束清库；目标测试留下revoked/revoking等新状态，而compatibility probe要求空库，原工作流将targets放在probe之前破坏了该前提。此故障不是CJK字体问题；PG安装字体成功。

RV-BRAND-10独立审查为阻塞项，PR已退Draft。修复仅将原完整 `verify_migration_compatibility.py` 移到任何target/suite数据测试之前，保留14个历史checkpoint/base的降级、升级、结构断言以及全部PG测试范围，不修改生产Migration/业务状态或约束。新增顺序回归：`.runtime/brand-ci-order-red.xml`真实1failed，修复后相关三文件79passed（`.runtime/brand-ci-order-green.xml`）。Ruff check/format通过。

本地专用aima_brand_test保留96targets后的数据，`python .runtime/brand-migration-local.py probe`实际复现同CheckViolation/exit1，记录brand-migration-after-targets-red.log。随后只清空该自有专用库，执行完整probe取得14次回0078及alembic check通过/exit0，记录brand-migration-before-targets-green.log。紧接probe执行 `python .runtime/brand-validate.py <同8个postgres_targets> -q --junitxml=.runtime/brand-ci-order-targets-green.xml`，包装未额外清库，仅保留正式pytest fixture，结果96passed/117.74s/exit0。相应源码、XML和日志SHA保存在EVIDENCE的ci_repair_validation。

原head其余CI实际成功：后端1584/113/101及12subtests、前端274/175Mock、全栈16、Compose与Windows/Linux Tooling。Compose还在正式worker镜像内加载常规/粗体CJK，渲染“爱玛”“续航”并Image.verify，确认字体属于最终镜像。服务器旧镜像与真实Provider/飞书权限仍未检查。本修复的新冻结head必须重新运行完整CI并取得Final Review后才允许合并。
