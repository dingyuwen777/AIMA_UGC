# 数据库报告本地验证记录

本轮直接修改 `E:/Desktop/AIMA_UGC`，本地分支为 `feature/report-generation`，基线为 `15dd366db6e1632535fadc615513636a4b22c639`。运行代码目录是独立的 `E:/work/03_Aima/code/AIMA_UGC`，两个 checkout 的 Git common directory 也不同。没有 push、远程 Issue/PR、merge、Release、部署或运行数据库迁移。

## 当前结论

报告数据冻结、生成、下载、过载恢复、取消、独立发布和文件生命周期已取得本地工作流证据。关键词统计口径仍待用户决定；当前 Change 保持 `in_progress`，不宣称完整需求满足或 Final Ready。真实模型额度、飞书账户权限和在线发布结果尚未验证。

## 环境与隔离

- Python 3.14.7，使用仓库根 `.venv` 与现有锁定依赖；未升级依赖。
- PostgreSQL 18.4 专用容器 `aima-report-validation-20261001`，容器 ID 为 `8fd60d38dd103b9d85799148e34200ff2dcb009e6da5b52c0b49d922df7b830b`，仅绑定 `127.0.0.1:55437`，数据库为 `aima_report_test`。报告集成 fixture 对端口与数据库名执行硬校验后才允许清表。
- Browser Mock 使用独立 Vite 端口 55438；真实链路使用临时 API 55439 和 Vite 55440，代理只指向专用 API。没有复用或停止原开发服务器。
- 忽略的 `.runtime/report-validate.py` 只配置专用数据库、数据、日志和测试 Secret；`.runtime/report-unit-validate.py` 去掉会污染默认值测试的外部 Secret 环境变量。只在验证子进程中去掉不可写的系统 SSL keylog 路径。
- Windows 子进程统一采用 `PYTHONUTF8=1` 和 `PYTHONIOENCODING=utf-8`。测试临时目录位于系统 TEMP，避免文档导航 fixture 被上级真实 Git 仓库识别。
- 验证结束后按完整容器ID删除本轮专用容器，并通过记录的进程session停止本轮Vite；55437/55438/55439/55440均没有剩余监听。只读核对发现原`aima-ugc-postgres-dev`已于北京时间11:17以exit 0结束；本轮没有对它执行启停或删除，不能宣称它当前仍运行。

## 实际命令与结果

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
| 当前Change完成门禁 | `python scripts/quality/check_change_completion.py --root . --changed-since main --json` | 未提交工作树时没有进入changed-commit范围；建立本地checkpoint后，明确拒绝`in_progress`状态、要求`ready_for_review`。关键词R1尚未满足，因此保留此阻塞，未把状态强行改为Ready |
| Migration往返 | `python .runtime/report-migration-roundtrip.py` | 专用库78→77→78，`alembic check`没有新增操作，head为`20261001_0078`，exit 0 |
| 影响面 | `python scripts/dev/validate_changed.py --base main --json` | 复用唯一CI classifier；profile为full。未运行远程CI、完整PostgreSQL/Compose/Release矩阵，不能冒充正式交付 |

本轮原始输出及源码SHA256清单保存在忽略的 `.runtime/report-evidence/`。有意保留失败复现和旧验证输出；最终Green使用 `backend-preflight.xml`、`workflows.xml`、`frontend-unit.xml`、`frontend-e2e.xml`。历史失败XML不能当作最终状态，也不能删除它们来掩盖过程。

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

独立只读Reviewer重新读取生产调用链、原始XML及具体断言，关闭了孤儿清理、飞书发送guard、旧GET覆盖、DryRun绕过和Provider并发删除共5项Finding。没有新的已知blocking代码Finding；这不替代R1的业务决定、完整Completion审计或正式CI。

关键词来源尚缺正式决定。旧离线导入的 `RelevanceService.evaluate()` 只检查标题和正文，返回指定词包的标准名称；`UnifiedContentRecordV1.matched_keywords` 经打标写入 Excel。离线 Provider Probe 可使用搜索上下文，二者不能统一称为“原采集关键词”。正式数据库导出的 `UnifiedDataExcelContentV1.matched_keywords` 目前使用空默认值，没有投影同口径证据。历史 Campaign 的词包快照不等于全量内容的命中字段。采用现有品牌/车型证据或明确词包后保持原匹配规则会改变这一业务口径，因此再次列出准确选项，等待用户决定；没有补造统计、标为延期或宣称已满足。

## 后续 Word 标题修复

复核发现正文已按选择品牌生成标题，但 `docProps/core.xml` 仍固定“爱玛品牌舆情分析报告”。通过正式 Markdown→DOCX 入口先复现两个错误标题，再修复为第一个一级标题的可见文本，保留无标题旧入口的默认值，避免后续章节覆盖。XML 特殊字符经转义，Markdown 加粗标记不进入文件属性。

- Red：`python .runtime/report-unit-validate.py tests/unit/platform/test_docx_package_structure.py -k metadata -q -p no:cacheprovider --basetemp=$env:TEMP/aima-report-word-metadata-red-20261001 --junitxml=.runtime/report-evidence/word-metadata-red.xml`，2 failed、3 passed、7 deselected；失败断言是实际品牌和特殊字符标题与固定“爱玛”不一致。此前沙箱临时目录 ACL 错误不作为此行为的 Red 证据。
- Green：同一隔离 helper 执行 `test_docx_package_structure.py`、`test_offline_reporting.py`、`test_reporting_visual_fidelity.py`、`test_reporting_visuals.py`、`test_reporting_default_template.py`，`--basetemp=$env:TEMP/aima-report-word-metadata-green-20261001 --junitxml=.runtime/report-evidence/word-metadata-green.xml`，28 passed、2 skipped，exit 0；重新打开 ZIP 并解析正文和 core properties XML 核验。
- 完整后端回归还发现既有时间协议测试直接无参数调用 `_core_props_xml()`；恢复其默认标题参数后继续验证，没有改动该测试断言。初次回归的1项兼容失败保留在 `backend-word-title-compat-red.xml`。
- 最终完整后端回归：`python .runtime/report-unit-validate.py tests/unit tests/contracts tests/api -q -p no:cacheprovider --basetemp=$env:TEMP/aima-report-word-title-backend-final-20261001 --junitxml=.runtime/report-evidence/backend-word-title-final.xml`，1742 passed、16 skipped、12 subtests passed，exit 0，69.15秒。修复后 Ruff检查/格式检查、mypy受影响文件、文档链接/机器事实检查均 exit 0。
- 本次只改变 Word 元数据，不修改数据库、Job、HTTP Contract、依赖或 Migration，也不启动服务或 Docker。先前完整工作流证据对应实现 checkpoint `568b6e9`；本次修复另有当前源码的局部回归，不能把旧工作流 XML 说成重新执行。
- 独立只读复核重新解析 Red/Green 和最终完整回归 XML，确认首个可见标题、后续不覆盖、XML转义、旧无参数调用与UTC时间协议均成立，未发现新增 blocking Finding。当前源码清单核验50个文件与14个XML摘要，并通过 `validation_basis` 区分当前后端证据和既有 PG/前端证据。
