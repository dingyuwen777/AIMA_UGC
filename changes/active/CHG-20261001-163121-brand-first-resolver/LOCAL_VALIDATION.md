# 品牌先行识别本地验证

本记录对应 `feature/brand-first-resolver` 的实现工作树；开工治理提交为 `04cccef5b5038b03fafab437bc32343a03683342`、基线 main 为 `15dd366db6e1632535fadc615513636a4b22c639`。当前处于实现和 Repair 验证，尚未 Final Ready，不能把未提交工作树测试替代最终提交的 CI、Review 与 current-base 检查。后续冻结时记录生产源文件摘要并复核最终提交。

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

首次浏览器记录有 7 个失败场景（截图/trace 保留在 `.runtime/brand-fullstack/browser-results`）。两项真实原因分别是：管理员旧 fixture 的品牌识别词不在内容中，依赖已取消的车型反推品牌；本地包装清库恢复投影为 pending，却没有复用生产启动的回填调度。更正 fixture 明确命中配置品牌，并由 `ensure_voice_plaza_projection_backfill_job` 创建正式可恢复 Job，在 ready 后启动浏览器，不直接改数据库状态或业务查询。第二次完整运行 `.runtime/brand-fullstack/browser-final.xml` 取得 **15 passed / 1 failed**，剩余失败为旧 import 来源显示断言“系统识别”，新版来源 alias_match 实际显示“词包 / 别名识别”。更新为批准的来源断言，并增加正式详情 API 的品牌及车型 alias_match、matched_text 校验；补充断言的一次辅助函数拼写错误已修正，最新运行结果尚待补齐。

`EVIDENCE.json` 保存 18 个实际生产源文件的 LF 规范化 SHA-256（生产集合摘要 `56da1bcfb53377a043130cb772b9af76098a64e85cb450d3fca4709e9f895d39`）以及原始 XML 摘要和结果，包含初次失败；后续只有测试文件统一 Ruff 格式和补充实际来源断言，生产源保持相同。该证据只绑定本地实现，最终交付仍需 commit/base/Review/CI 新鲜证明。

匹配机制的复杂度说明限定为各个 Aho-Corasick 自动机的一次扫描 `O(文本长度 + 命中数)`。整体 v2 还包括逐个已确认品牌的车型扫描、候选排序与局部归属判断，不把索引复用测试描述成全链路严格线性复杂度或生产吞吐基准。

## 审查及交付状态

独立只读 Repair 审查 RV-BRAND-01–09 已关闭。修复涵盖实际 Current、负向收敛、人工范围、Current 锁、旧 import 文本证据与 SQL NULL、正常来源/审核继承、Collection 索引复用及 selected 冻结清理集合。审查针对未提交工作树，未发现新的 P1/P2，仍须最终 current-head/current-base Review。

PR #687 保持 Draft，远程 required CI 未取得最新实现结果。全部本地变化将按报告、品牌两批交付；报告原 PR #686 的新实例身份门禁失败记录保留，由新的秒级交付 Change/PR 承载，不重命名历史报告 Change。报告合并后本批必须同步当前 main、重跑受影响验证、再 Ready。merge、main-fresh、原生归档、Issue #685 AC21 与 closure、资源 cleanup 尚未完成。
