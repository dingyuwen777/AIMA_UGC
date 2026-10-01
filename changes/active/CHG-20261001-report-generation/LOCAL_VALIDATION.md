# 数据库报告本地验证记录

前一轮本地里程碑直接修改 `E:/Desktop/AIMA_UGC`，本地分支为 `feature/report-generation`，基线为 `15dd366db6e1632535fadc615513636a4b22c639`。运行代码目录是独立的 `E:/work/03_Aima/code/AIMA_UGC`，两个 checkout 的 Git common directory 也不同。该里程碑没有 push、远程 Issue/PR、merge、Release、部署或运行数据库迁移。当前用户已新增分批远程交付授权，状态见下节与 Issue #684，旧证据不冒充远程结果。

## 远程交付准备的增量验证

报告能力由 [Issue #684](https://github.com/dingyuwen777/AIMA_UGC/issues/684) 的 AC1–AC7 接管，AC8 跟踪两批本地验证后的合并和收尾，当前未勾选。报告日期级 Change 是前轮已存在的身份，保持不变；当前 canonical `validate-change` 只校验新实例，日期级历史身份使用项目现有 ready validator 验证，不伪称新实例 create PASS。

CI 原未执行报告 PostgreSQL suite，且 fixture 会拒绝 CI 临时库；新增 classifier 回归先取得 2 条 Red。修正唯一 classifier/workflow 接线和 fixture 后，执行 `.venv/Scripts/python.exe -m pytest tests/unit/test_ci_scope.py tests/unit/test_report_test_database_guard.py tests/unit/test_ci_workflow_structure.py tests/unit/test_ci_test_impact_optimization.py -q -p no:cacheprovider --junitxml=.runtime/report-evidence/report-ci-green.xml`，82 项通过。不安全主机、运行库配置和缺少显式 CI 授权均在创建运行时/清表前被拒绝。

新建本任务独占 PostgreSQL 18.4 容器 `31c4b9340204766d8e24ab9d916ed80a67285a48228335372d5c970f81c7bea2`，端口 `127.0.0.1:55437`、空库 `aima_report_test`、1 CPU/1 GiB 上限。通过 `.runtime/report-validate.py migrate` 仅迁移该测试库，再运行 `.venv/Scripts/python.exe .runtime/report-validate.py tests/integration/reporting/test_database_reports.py -q -p no:cacheprovider --junitxml=.runtime/report-evidence/report-delivery-pg.xml`：9 项通过，1 项显式浏览器用例跳过。原真实浏览器 Evidence 仍覆盖未修改的生产页面/API/Worker；当前正式 CI 的 PG 执行结果尚未取得。未操作任何既有容器。

文档检查、Ruff 和 `check_change_completion.py --root . --changed-since main --require-active-ready --json` 已通过。当前生产代码与前端未新增改动；增量范围是 CI/安全测试保护、正式决策文档及交付追溯。PR/CI、合并、main 新鲜验证、原生归档、Issue 关闭和分支清理仍须后续取得直接证据；不部署、不操作运行数据。

## 当前结论

报告数据冻结、生成、下载、过载恢复、取消、独立发布和文件生命周期已取得本地工作流证据。用户随后明确采用已保存的品牌、车型命中证据，关键词口径已补齐并取得当前22项工作流与1742项后端回归通过证据。下载的Word关键词说明与排名、Excel数据与口径说明均实际解析。独立复核未发现遗漏的产品能力或新增blocking实现问题。当前Change按仅本地范围进入ready_for_review，不宣称远程CI/PR或生产Ready。真实模型额度、飞书账户权限和在线发布结果尚未验证。

## 初次实施的环境与隔离（历史记录）

- Python 3.14.7，使用仓库根 `.venv` 与现有锁定依赖；未升级依赖。
- PostgreSQL 18.4 专用容器 `aima-report-validation-20261001`，容器 ID 为 `8fd60d38dd103b9d85799148e34200ff2dcb009e6da5b52c0b49d922df7b830b`，仅绑定 `127.0.0.1:55437`，数据库为 `aima_report_test`。报告集成 fixture 对端口与数据库名执行硬校验后才允许清表。
- Browser Mock 使用独立 Vite 端口 55438；真实链路使用临时 API 55439 和 Vite 55440，代理只指向专用 API。没有复用或停止原开发服务器。
- 忽略的 `.runtime/report-validate.py` 只配置专用数据库、数据、日志和测试 Secret；`.runtime/report-unit-validate.py` 去掉会污染默认值测试的外部 Secret 环境变量。只在验证子进程中去掉不可写的系统 SSL keylog 路径。
- Windows 子进程统一采用 `PYTHONUTF8=1` 和 `PYTHONIOENCODING=utf-8`。测试临时目录位于系统 TEMP，避免文档导航 fixture 被上级真实 Git 仓库识别。
- 验证结束后按完整容器ID删除本轮专用容器，并通过记录的进程session停止本轮Vite；55437/55438/55439/55440均没有剩余监听。只读核对发现原`aima-ugc-postgres-dev`已于北京时间11:17以exit 0结束；本轮没有对它执行启停或删除，不能宣称它当前仍运行。

## 初次实施的实际命令与结果（历史记录）

以下 Python 命令均由仓库根执行；`python` 代表当前 `.venv/Scripts/python.exe`。前端命令在 `frontend/` 执行，使用本机 `D:/node/npm.ps1`。

| 验证 | 实际命令 | 结果 |
| --- | --- | --- |
| 后端完整回归 | `python .runtime/report-unit-validate.py tests/unit tests/contracts tests/api -q -p no:cacheprovider --basetemp=$env:TEMP/aima-report-provider-lock-final-20261001 --junitxml=.runtime/report-evidence/backend-preflight.xml` | 1738 passed、16 skipped、12 subtests passed，exit 0；包含8个新报告入口的非管理员拒绝测试 |
| 隔离 PG 与真实浏览器工作流 | `python .runtime/report-validate.py tests/unit/platform/test_report_dataset.py tests/unit/platform/test_report_publication_guards.py tests/integration/reporting/test_database_reports.py tests/integration/database/test_product_resource_lifecycle.py -q -p no:cacheprovider --basetemp=.runtime/report-workflow-final-4 --junitxml=.runtime/report-evidence/workflows.xml`；显式 `AIMA_REPORT_BROWSER_ACCEPTANCE=1` | 21 passed，exit 0 |
| 前端组件 | `npm run test -- --run --reporter junit --outputFile ../.runtime/report-evidence/frontend-unit.xml` | 274 tests、0 failure，exit 0 |
| 完整 Browser Mock | `npm exec playwright test -- --config playwright.report-local.config.ts --workers 1 --reporter list,junit`；设置 `PLAYWRIGHT_JUNIT_OUTPUT_FILE=../.runtime/report-evidence/frontend-e2e.xml` | 174 passed，exit 0，约4.4分钟 |
| 前端静态与构建 | `npm run lint`、`npm run build`（内含TS与Vue类型检查） | exit 0；构建仍有既有主包超过500kB提示 |
| 后端静态 | `python -m ruff check`、`python -m ruff format --check` 对受影响文件；`python -m mypy backend/src/aima_ugc` | Ruff通过；mypy 427 source files通过 |
| Contract | `python scripts/contracts/generate.py --check`、`python scripts/contracts/check_compatibility.py` | exit 0；正式生成 OpenAPI/Client，旧path/schema没有语义改动 |
| 文档与安全 | `python scripts/quality/check_docs.py`、`check_docs_facts.py`、`check_table_ownership.py`、`scan_secrets.py` | 均exit 0；新增3张表唯一Owner为Reporting |
| Change元数据 | `python scripts/quality/check_change_completion.py --root . --json` | 当前字段结构与历史记录校验；不替代新Change的Ready门禁 |
| 当时Change完成门禁 | `python scripts/quality/check_change_completion.py --root . --changed-since main --json` | 历史拒绝：未提交工作树时没有进入changed-commit范围；建立本地checkpoint后拒绝`in_progress`状态。当时关键词R1尚未满足，未强行改为Ready；最新决定、实现和当前门禁记录见文末 |
| Migration往返 | `python .runtime/report-migration-roundtrip.py` | 专用库78→77→78，`alembic check`没有新增操作，head为`20261001_0078`，exit 0 |
| 影响面 | `python scripts/dev/validate_changed.py --base main --json` | 复用唯一CI classifier；profile为full。未运行远程CI、完整PostgreSQL/Compose/Release矩阵，不能冒充正式交付 |

原始输出及源码SHA256清单保存在忽略的 `.runtime/report-evidence/`。有意保留失败复现和旧验证输出；上述初次实施Green为 `backend-preflight.xml`、`workflows.xml`、`frontend-unit.xml`、`frontend-e2e.xml`，最新关键词补齐后的Green与修订绑定见文末。历史失败XML不能当作最终状态，也不能删除它们来掩盖过程。

## 关键行为证据

- 创建后修改实时指标、粉丝数或分析数据，生成仍消费冻结记录。当前/上期范围为相邻等长北京时间自然日；相同外部ID出现在不同平台时不会串联标签或评论。
- 生产LLM Adapter只替换HTTP传输。503和ReadTimeout分别验证持久计划重试；已成功筛选不会再次调用。连续429只执行约定次数，最终失败且不开放半套产物。没有隐式网络重试。
- 下载返回真实字节，重新解析DOCX ZIP、Office图表、Excel工作簿与Markdown；真实浏览器通过正式API与Worker生成并下载Word。
- 发布失败仍可下载；重试读取已存文件且不增加LLM调用。生产Publisher上传Word和数据Excel、建立可编辑图表与两种Bitable，使用MockTransport验证断点、发送前guard与读回错误。真实飞书在线写入未执行。
- 取消或旧fence不能继续提交业务结果；DryRun在HTTP、Worker及prepared发布入口拒绝真实发布。
- 部分文件写入失败留下的孤儿文件经既有清理器删除；恢复后完整关联文件保持可用。61天到期返回410并清理字节，保留报告历史。
- 创建报告的冻结事务持有System Owner Provider行锁。另一个事务竞争同一锁时受控返回55P03；报告提交后历史删除守卫可见。环境模型回退经过真实Worker生成。原缺口Red保存在`provider-history-red.xml`及`provider-lock-red.xml`。
- 精确迟到GET测试先挂起创建前空历史请求，再创建报告、释放旧响应，确认新记录及轮询仍保留；轮询503可恢复、发布失败可独立重试。未保存报告输入的切换保护继续成立。

## Review与未完成项

独立只读Reviewer重新读取生产调用链、原始XML及具体断言，关闭了孤儿清理、飞书发送guard、旧GET覆盖、DryRun绕过和Provider并发删除共5项Finding。后续又独立重读会话最终方案、目录/本地限制和本轮关键词决定，确认R1–R7的实现及证据覆盖，没有发现遗漏的产品要求或新增blocking生产缺陷。该复核不替代正式CI和线上账户验收。

原关键词缺口已由用户本轮明确决定解除：采用数据库已保存的品牌、车型命中证据。此前已确认旧离线词包匹配与 Provider Probe 搜索上下文不同；本次仅为正式报告填充已批准的证据标准名称，不重解释历史离线字段，也不把普通数据导出的空默认值改为另一种含义。

## 后续 Word 标题修复

复核发现正文已按选择品牌生成标题，但 `docProps/core.xml` 仍固定“爱玛品牌舆情分析报告”。通过正式 Markdown→DOCX 入口先复现两个错误标题，再修复为第一个一级标题的可见文本，保留无标题旧入口的默认值，避免后续章节覆盖。XML 特殊字符经转义，Markdown 加粗标记不进入文件属性。

- Red：`python .runtime/report-unit-validate.py tests/unit/platform/test_docx_package_structure.py -k metadata -q -p no:cacheprovider --basetemp=$env:TEMP/aima-report-word-metadata-red-20261001 --junitxml=.runtime/report-evidence/word-metadata-red.xml`，2 failed、3 passed、7 deselected；失败断言是实际品牌和特殊字符标题与固定“爱玛”不一致。此前沙箱临时目录 ACL 错误不作为此行为的 Red 证据。
- Green：同一隔离 helper 执行 `test_docx_package_structure.py`、`test_offline_reporting.py`、`test_reporting_visual_fidelity.py`、`test_reporting_visuals.py`、`test_reporting_default_template.py`，`--basetemp=$env:TEMP/aima-report-word-metadata-green-20261001 --junitxml=.runtime/report-evidence/word-metadata-green.xml`，28 passed、2 skipped，exit 0；重新打开 ZIP 并解析正文和 core properties XML 核验。
- 完整后端回归还发现既有时间协议测试直接无参数调用 `_core_props_xml()`；恢复其默认标题参数后继续验证，没有改动该测试断言。初次回归的1项兼容失败保留在 `backend-word-title-compat-red.xml`。
- 最终完整后端回归：`python .runtime/report-unit-validate.py tests/unit tests/contracts tests/api -q -p no:cacheprovider --basetemp=$env:TEMP/aima-report-word-title-backend-final-20261001 --junitxml=.runtime/report-evidence/backend-word-title-final.xml`，1742 passed、16 skipped、12 subtests passed，exit 0，69.15秒。修复后 Ruff检查/格式检查、mypy受影响文件、文档链接/机器事实检查均 exit 0。
- 本次只改变 Word 元数据，不修改数据库、Job、HTTP Contract、依赖或 Migration，也不启动服务或 Docker。先前完整工作流证据对应实现 checkpoint `568b6e9`；本次修复另有当前源码的局部回归，不能把旧工作流 XML 说成重新执行。
- 独立只读复核重新解析 Red/Green 和最终完整回归 XML，确认首个可见标题、后续不覆盖、XML转义、旧无参数调用与UTC时间协议均成立，未发现新增 blocking Finding。当前源码清单核验50个文件与14个XML摘要，并通过 `validation_basis` 区分当前后端证据和既有 PG/前端证据。

## 关键词口径补齐后的当前验证

用户明确决定后，Reporting 复用按内容版本读取的有效 Brand/Vehicle 生产投影，把标准名称的去重并集写入本期及上期冻结记录；HTTP 同时冻结口径说明并写入报告模板，数据 Excel 仍使用原列结构，在同一流式导出中增加表头批注与文件属性说明。每条内容内同名只计一次，分母为报告全量内容。代码、模块README、Blueprint和报告Appendix同步，不新增依赖或Migration。

- 专项Red/Green：`python .runtime/report-validate.py tests/integration/reporting/test_database_reports.py -k keywords -q -p no:cacheprovider`，分别使用`.runtime/report-keywords-red`和`.runtime/report-keywords-green`；原始XML为`keywords-red.xml`与`keywords-green.xml`。Red为1 failed（冻结命中字段实际为两个空元组），Green为1 passed、9 deselected。
- 完整后端：`python .runtime/report-unit-validate.py tests/unit tests/contracts tests/api -q -p no:cacheprovider --basetemp=$env:TEMP/aima-report-keywords-backend-20261001 --junitxml=.runtime/report-evidence/backend-keywords-final.xml`，1742 passed、16 skipped、12 subtests passed，exit 0，101.10秒。
- 完整工作流：前述四个报告/Provider生命周期验证文件，显式`AIMA_REPORT_BROWSER_ACCEPTANCE=1`，`--basetemp=.runtime/report-keywords-identity-final --junitxml=.runtime/report-evidence/workflows-keywords-final.xml`，22 passed，exit 0，30.26秒。下载后重新解析DOCX正文XML中的关键词说明/排名，以及Excel数据、批注和属性；品牌名/车型名改动、有效证据停用后，冻结记录与报告计数保持不变。
- 追加Word断言的首次复跑发现测试把本期记录顺序误当成外部ID排序；失败结果保留为`keyword-order-assumption-red.xml`。正式target ordinal有自己的排序规则。测试已按external_content_id核对本期/上期和Excel的准确命中归属，没有改生产排序或降低去重、计数、冻结断言；最终22项重新通过。
- Ruff/format、mypy427个文件、Contract生成/兼容、docs/docs_facts、TableOwner、Secret检查均exit 0。唯一CI classifier仍给出full范围；其实现明确将重依赖PG与真实全栈矩阵留给正式CI，本轮补足隔离报告关键路径，未启动远程CI或默认Compose栈。
- 本次专用PostgreSQL容器为`aima-report-keyword-validation-20261001`，完整ID为`23348b461bc36566ff71efb8e13d2a61cea76a5142fa96e266430069ef3b3354`，仅55437，限制1核/1GB；创建前只读确认5432的既有容器运行，未对其执行启停、迁移或数据操作。结束后再次核对专用容器ID、名称、55437映射，仅删除该专用容器；通过本次session停止55440的Vite，API在测试finally关闭。55437–55440均无剩余监听。只读`docker ps`显示原`aima-ugc-postgres-dev`（`e444f87aaffa`）仍运行于5432；这是当前状态，不能沿用历史容器已退出的记录描述现状。
- 当前完成门禁：`python scripts/quality/check_change_completion.py --root . --require-active-ready --json`，exit 0，`ok=true`、`errors=[]`，150个当前gated文档严格检查、128个legacy保留。首次Ready校验要求上游稳定Acceptance绑定，已把引用会话和本轮明确决定按原有七项验收建立AC1–AC7稳定定位，没有新增需求或把Change当自己的需求源；原始通过输出保存为`completion-keywords-final.json`。
- 当前源码/证据清单为`.runtime/report-evidence/source-manifest.json`，SHA256绑定50个受影响源码/正式文档及19个XML。`validation_basis`区分关键词补齐后的当前后端/工作流证据与未改动的既有前端证据，保留原始失败复现和旧清单；独立Reviewer核验最终增量及这些绑定。
