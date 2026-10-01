# 数据库报告交付验证

本单元基线为 main `15dd366db6e1632535fadc615513636a4b22c639`，产品提交为 `d1e09a8d`，canonical Source 为 `041c9b60aae0f566553002794eb5fde4ed614c7f`。原本地产品检查点 `0fd93aec403049d490d58543cc6178d3fec14604` 保留在 feature/report-generation；旧日期 Change 未转入、未改名。当前正式交付分支为 feature/report-delivery，Draft PR #688，替代关闭未合并的 #686。

## 源码守恒

转入后与0fd比较，除新交付记录，仅两个测试文件有差异：Worker registry 精确元组增加 generation/publication 两个报告 Job；截图 Fake 补 pytest import，其阻止真实浏览器启动的 monkeypatch 在冻结实现中已经存在。两文件按现有 Ruff 格式收敛；生产源码、Contract、Migration、UI 和直接文档均与0fd相同。生产字节清单与实际 XML 的 SHA256 见 EVIDENCE.json。

## 当前本地验证

测试只连接本任务新建 PostgreSQL18容器的127.0.0.1:55437/aima_report_test，文件与日志使用.runtime/report-validation。前端Mock使用55438专用端口；不修改运行目录 E:/work/03_Aima/code/AIMA_UGC，不操作既有容器或生产数据库。

| 验证 | 实际命令或入口 | 当前结果 |
| --- | --- | --- |
| 报告PG | `.venv/Scripts/python.exe .runtime/report-validate.py tests/integration/reporting/test_database_reports.py -q`，专用basetemp/cache，report-delivery-pg.xml/log | 9 passed、1显式browser skipped；冻结、目录改名/证据变化、实际DOCX/XLSX/Markdown解析、生成/发布恢复、有界过载/取消fence及清理 |
| Worker接线 | 同一隔离入口执行tests/integration/collection/test_collection_worker_runtime.py | 1 passed；完整精确registry和真实Worker消费 |
| 后端 | report-unit-validate.py运行tests/unit tests/contracts tests/api，独立Temp目录 | 1749 passed、16 skipped、12 subtests；report-delivery-backend-green.xml，107.39秒 |
| 文档fixture定位 | tests/unit/test_docs_navigation.py，独立Temp目录 | 11 passed；原Git父索引干扰消除，断言不变 |
| 前端组件/构建 | frontend中npm run build、npm run test -- --run | build退出0；36 files、274 passed |
| 报告页面浏览器 | npm exec playwright -- test --config playwright.report-local.config.ts e2e/admin-configuration-release2.spec.ts e2e/admin-configuration-figma.spec.ts | 38 passed；目录选择、预检、轮询503恢复、下载与发布失败独立重试 |
| 静态/Contract | ruff check/format --check backend/src tests scripts；mypy backend/src；scripts/contracts/generate.py --check及check_compatibility.py | lint通过；868 files格式通过；427 source files类型通过；Contract一致及兼容通过 |
| 文档/边界/Secret | check_docs.py --root . --strict；check_docs_facts.py；check_table_ownership.py；check_architecture.py；scan_secrets.py | 全部退出0 |
| preflight | scripts/dev/validate_changed.py --base origin/main --json | 使用CI唯一classifier生成当前变更scope；本记录不冒充整套命令已execute |

原0fd的22项真实报告工作流（含浏览器→API/Worker下载）、后端1742/16skip/12subtests、前端274/174browser证据继续覆盖逐字守恒的生产实现，详情在原分支 [冻结记录](https://github.com/dingyuwen777/AIMA_UGC/blob/0fd93aec403049d490d58543cc6178d3fec14604/changes/active/CHG-20261001-report-generation/LOCAL_VALIDATION.md)。当前实际报告PG执行责任仍需#688远程CI确认。

## 保留失败与范围

第一次命令误写tests/contract，收集失败，无业务测试结论。随后sandbox拒绝pytest临时目录ACL，日志保留；用已授权隔离目录执行。授权完整回归第一轮1743 passed/6 failed/16 skipped/12subtests：6个失败全部在文档导航fixture；将临时仓库放在本Git父仓库内使git ls-files索引了父项目，独立Temp重跑11项全部通过。未修改生产检查器或降低测试断言。

#686 CI失败保留：日期ID的新Active实例被当前Contract拒绝；registry精确预期遗漏两个新增Job；报告PG未执行。#688用新的真实交付单元与测试修正取得当前证据，不改旧身份或CI质量规则。

真实LLM、TikHub和飞书没有调用；本地用生产Adapter与可控HTTP证明协议/恢复，不能证明账户额度、权限或生产吞吐。迁移0078仅在隔离库执行；默认60天配置随功能交付，生产部署/Release未执行。Issue#684 AC8仍持有合并、main-fresh、原生archive和closure责任。

## 当前复核与就绪记录

独立Repair Review重新读取上游、canonical远程源码和57个产品差异路径：无新blocking Finding，报告01–05关闭；确认原历史守恒、CI report PG全量/目标路径和guard。Completion gate最终150 gated、128 legacy、150 strict、errors=[]。canonical接受的inline YAML列表在项目轻量parser中不兼容，已改为现有block列表，产品未变。Final Review与required CI仍在合并前取得。

## RV-REPORT-06：真实CI中文字体依赖修复

Ready run36860409129 / headf19895fa真实完成：core成功（包含全量前端），16真实全栈成功，Compose和Windows/Linux tooling成功；前7PG套件56/119/20/143/124/95/2通过。报告PG实际5fail/4pass/1skip，五项均在生产resolve_cjk_font抛缺少CJK字体，日志保留.runtime/report-final-pg-failure.log。core和PG是独立runner，不能复用另一个job已安装的字体，故CI Gate正确失败，PR退Draft修复。

在PG job、Selected PostgreSQL integration evidence之前安装项目已有fonts-noto-cjk，条件由现有classifier report_font_required或all/reporting套件选择控制，包含窄目标/混合目标；不增加第二套scope映射、不改Renderer/skip/assert。生产Dockerfile已有该系统依赖，应用/Contract/Migration/页面不变。新增独立runner依赖回归先1Red，修复后CI scope/Actions/validate_changed/报告DB guard64passed+12subtests。实际新head Linux runner报告PG绿色仍是合并前必需证据。原冻结守恒现在明确增加CI字体步骤及其测试这一交付修正。

## 字体修复最终本地检查点

6f600435真实Linux CI报告PG现9passed/1显式browserSkip，前7套通过，安装依赖成功；core只有旧“PG永不安装字体”断言失败。已同步为有条件安装和非报告Collection轻量保护，保留其他原断言，经独立Repair Review认可；生产/Renderer不变。完整本地父子进程统一PYTHONUTF8后1750passed/16skip/12subtests，68.39秒；XML1778tests/0error/0failure。此前仅父进程-Xutf8而Windows子进程CP936导致读取stderr失败的日志保留，环境原因已直接读取stderr字节证实，不改种子隔离测试。当前新head的完整required CI和Final Review仍待取得，不能用6f部分绿色宣称已合并。
