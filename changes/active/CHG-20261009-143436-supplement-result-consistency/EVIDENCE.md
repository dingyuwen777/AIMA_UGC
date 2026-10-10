# 补采一致性本地验证证据

本记录属于当前 Change，需求源为用户在本会话粘贴的完整任务书及“本地验证、先不合并远程主分支”的指令。只记录本轮实际命令与直接断言；不把 Mock、静态阅读或平台跳过项算成真实数据库验收。

## 测试环境与写入范围

基线 `caf06ae1be1d243545d21a71fcbfe72640d0bd5f`；本地分支 `fix/supplement-result-consistency`，decision epoch 为 1。所有运行数据在两个任务专属 PostgreSQL 18.4 容器内：`25439/aima_supplement_test`、`25439/aima_supplement_browser` 及 `55437/aima_report_test`。特殊身份用例按其既有保护要求使用同一任务容器内另建的专用库。没有迁移或修改用户开发库、生产库，没有 TikHub/付费模型 Probe。

首个完整实现提交为 `9ddc6513c9c63bbd7e51814c5f4ac998267fc85c`。此前分层命令按各自记录的工作树执行；独立Tester记录关键生产文件Hash，确认稳定源文件没有变化。整批审查随后发现两项局部消费者问题，返修范围和新鲜证据单独记录在下方，不把首轮提交及修前报告/Migration证据冒充最终状态。

Python 命令均使用仓库根 `.venv/Scripts/python.exe`；Node 命令使用 `D:/node/npm.ps1 --prefix frontend`。每批数据库测试先加载 `.runtime/supplement-consistency/` 中对应的显式隔离环境。日志、浏览器截图和测试文件保存在该忽略目录中；正式证据结论保留在此 Change。

## 已实际完成的验证

表中保留修前失败及环境诊断，后续标有返修/最终/独立补验的记录闭合对应项；不把失败或中断计入通过总数。

| 范围 | 实际命令（从仓库根执行） | 结果 |
| --- | --- | --- |
| Content/品牌补采定向 | `pytest tests/integration/content/test_supplement_author_snapshots.py tests/integration/collection/test_collection_content_runtime.py tests/integration/collection/test_collection_content_supplement.py tests/integration/collection/test_collection_date_supplement.py tests/integration/content/test_excel_follower_count_voice_plaza.py -q` | 第一切片 23 passed；作者解绑新增回归随后纳入 C/D 最终运行 |
| Analysis/作者/并发 | `pytest tests/integration/content/test_analysis_version_reuse.py tests/integration/content/test_supplement_author_snapshots.py tests/integration/content/test_content_current_concurrency.py tests/integration/content/test_excel_follower_count_voice_plaza.py -q --tb=short --show-capture=no` | 36 passed / 36.69s |
| 后端 Unit/Contract/API | `pytest tests/unit tests/contracts tests/api -q --tb=short --show-capture=no` | 首轮 2094 passed、16 平台 skip、12 subtests，1 API 环境失败；移除该进程的 `AIMA_EXTERNAL_SECRET_DIR` 覆盖后 API 全套 106 passed。失败来自用例临时 Secret 路径被隔离配置覆盖，未改生产或测试代码 |
| 生成与兼容 Contract | `scripts/contracts/generate.py --check`；`scripts/contracts/check_compatibility.py` | PASS；没有 HTTP Response/OpenAPI/TypeScript Client 语义变化 |
| 前端单元 | `npm --prefix frontend run test -- --run` | 38 files / 306 tests passed |
| Browser Mock | `npm --prefix frontend run test:e2e -- --workers=3` | 206 passed / 3.4m；不作为真实 API/DB 接线证据 |
| 前端构建 | `npm --prefix frontend run build` | TypeScript Native、Vue、Vite PASS；既有大 chunk 提示 |
| 前端依赖审计 | `npm --prefix frontend audit --audit-level=high` | 0 vulnerabilities，没有安装或升级依赖 |
| 前端 lint | `npm --prefix frontend run lint` | 新 Full-stack spec 修正后 PASS |
| 新补采真实 Journey | `npm --prefix frontend run test:e2e:fullstack -- comment-supplement.spec.ts -g 补采形成等价` | 1 passed / 25.9s；测试第一轮误用 POST，改为正式 PUT 人工审核接口后通过 |
| 全部真实 Full-stack | `npm --prefix frontend run test:e2e:fullstack` | 20 passed / 4.6m；Vue/API/PG/Worker 为真实生产链，Provider/LLM 边界为显式本地 Fake |
| 本地栈 Smoke | `scripts/dev/check_local_stack.py --require-ready` | API readiness、Vite、Vite→API proxy、PostgreSQL 均 PASS |
| 新结构 | `alembic upgrade head`、`alembic current`、`alembic check` | 专用空库 head=`20261009_0084`，无 metadata 漂移 |
| 历史修复与相邻Owner | `pytest tests/integration/content/test_content_consistency_repair.py tests/integration/vehicles/test_content_reclassification_postgres.py tests/integration/vehicles/test_brand_first_frozen_cleanup.py tests/integration/collection/test_collection_content_runtime.py -q` | 47 passed / 59.05s（30 repair、17相邻）；修复涵盖CLI、正式Worker重试、检查点恢复、取消、旧Fence、原子回滚、二次幂等 |
| 人工锁Replay兼容 | `pytest tests/integration/ingestion/test_canonical_replay_worker.py -k 'manual_brand_lock or manual_lock' -q` | 2 passed / 6.32s |
| repair有限批量查询数 | `pytest tests/integration/content/test_content_consistency_repair.py -k 'query_count or owner_batch_queries' -q -o junit_family=legacy --junitxml=.runtime/supplement-consistency/repair-performance.xml` | 3 passed / 8.67s；1/100：预检11/11、自动apply54/54、品牌/车型人工carry10/10；原人工carry Red=14/1004 |
| AC04精确新增时序 | `pytest tests/integration/collection/test_collection_content_runtime.py -q --tb=short --show-capture=no` | 14 passed / 6.82s，包含title/text后来新增品牌两参数，核版本、旧/新品牌、匹配字段/文本/目录版本 |
| 最终完整后端 | 移除API用例不需要的隔离外部Secret覆盖后 `pytest tests/unit tests/contracts tests/api -q -rs --tb=short --show-capture=no` | 2095 passed、16既有平台skip、12 subtests / 162.15s |
| 最终静态 | `mypy backend/src`；`ruff format --check backend tests scripts`及新增两Migration；相同范围`ruff check` | 461源mypy PASS；956文件format/lint PASS |
| 最终生成物 | `scripts/contracts/generate.py`；`npm --prefix frontend run generate:api`；`generate.py --check`；`check_compatibility.py` | PASS；公开生成物无语义diff |
| Wheel | `uv build --wheel --offline`（输出到runtime）；`uv export --frozen --no-dev --no-emit-project --offline`；新Wheel虚拟环境按导出运行依赖`uv pip sync --offline`后`uv pip install --offline --no-deps`；`python -I` | 构建/安装/隔离导入PASS；导入来自Wheel独立site-packages，新修复模块和Prompt资源存在；项目锁文件未改 |
| 全历史 Migration 兼容 | `tests/integration/database/verify_migration_compatibility.py` | 独立 Tester 实际执行 14 个 checkpoint（含 base），每次均恢复0084并 check PASS |
| 报告数据库工作流 | `pytest tests/integration/reporting -q -rs --tb=short --show-capture=no` | 独立 Tester 9 passed / 28.07s；仅浏览器环境开关导致1 skip，已补跑下项 |
| 报告真实浏览器 | 显式 `AIMA_REPORT_BROWSER_ACCEPTANCE=1`，运行 `pytest tests/integration/reporting/test_database_reports.py::test_browser_to_real_report_api_worker_and_download -q -rs --tb=short --show-capture=no` | 独立 Tester 1 passed / 11.69s；Chrome→Vue→API55439→报告Worker→DOCX下载，ZIP和document.xml通过；全部10项报告均实际通过 |
| 最终仓库质量 | `check_agent_governance.py`、`scan_secrets.py`、`check_architecture.py`、`check_table_ownership.py`、`check_docs.py`、`check_docs_facts.py` | 最终全部PASS；生产源与8a10f441一致 |
| Collection广域回归及修正 | `pytest tests/integration/collection -vv -o faulthandler_timeout=45`；随后在独立25439库运行两个失败项的完整文件 | 首次完整243 passed / 2 failed / 536.11s；新Job exact-set漏同步及缺Version的直接SQL夹具已修正，两个完整文件2 passed / 4.18s，独立复验待收齐。首轮缓冲输出运行在有界诊断前中断，不计完成或失败 |
| 独立Platform | `pytest tests/integration/platform -q`；专用身份库按原guard要求复验身份/同步用例 | 73项实际通过、无skip；首次环境身份guard失败保留，随后18项身份/guard在同任务容器的专用库通过，未放宽guard |
| 独立Database | `pytest tests/integration/database -q` | 120 passed / 54.98s |
| 独立Jobs | `pytest tests/integration/jobs -q -rs` | 22 passed / 1 Linux专属skip / 8.90s；Windows进程恢复两项实际通过 |
| 独立Content | `pytest tests/integration/content -q -rs --tb=short --show-capture=no` | 231 passed / 0skip / 374.25s；关键生产文件Hash与最终实现提交一致 |
| 独立Ingestion首轮 | `pytest tests/integration/ingestion -q -rs --tb=short --show-capture=no` | 154 passed / 2 SQL计数failed / 372.61s；两项fresh复现后，Root精确批量断言修正的定向Green已通过，独立完整文件补验进行中 |
| 独立Vehicles | `pytest tests/integration/vehicles -q -rs --tb=short --show-capture=no` | 5 passed / 0skip / 4.69s |
| Collection独立补验 | 55437 fresh边界运行`test_collection_worker_runtime.py`与`test_xiaohongshu_incremental_comments_runtime.py`两个完整文件 | 2 passed / 0skip / 2.75s；整组245个不同用例均闭合 |
| Review反例Red/Green | 25439运行新增6报告依据参数及2带数据降级参数，随后加Replay两查询计数参数 | 修复前3 failed / 5 passed / 14.61s，精确复现两null计数及一个stale反例；修复后10 passed / 17.17s，含101条总SQL上限与后续撤销分支 |
| 返修静态/包 | `mypy report_runs.py`；全956文件ruff format/check；离线重建Wheel并在原锁定依赖独立环境强制重装，`python -I`核对最终汇总实现与修复模块 | 全PASS；Wheel包含最终JSON对象计数，非旧构建 |
| 返修完整Analysis | `pytest tests/integration/content/test_analysis_version_reuse.py -q --tb=short --show-capture=no` | 30 passed / 69.38s；新增8项及原22项全部实际执行通过 |
| 返修独立完整Replay | fresh 55437运行`pytest tests/integration/ingestion/test_canonical_replay_worker.py -q -rs --tb=short --show-capture=no` | 42 passed / 0skip / 127.23s；Ingestion全部156个不同测试闭合 |
| 返修独立报告 | fresh 55437运行报告组并显式单跑真实浏览器项 | 9 passed / 28.44s + browser1 passed / 8.12s，无skip；新隐藏API/Vite进程均精确清理 |
| 返修独立Migration与新回归 | 正式`verify_migration_compatibility.py`；新增6报告计数+2带数据降级；最终upgrade/current/check | 14个checkpoint全部PASS；新8 passed / 14.53s；0084/head及metadata无漂移；report_runs/0083起止Hash与8a10f441一致 |
| 最终Completion | `scripts/quality/check_change_completion.py --root D:/test/AIMA_UGC --require-active-ready --json` | PASS；ok=true，gated163/strict163，errors=[]；AC01–AC22全部satisfied，四项Completion Audit已完成 |

完整后端的16个跳过来自现有 Windows/POSIX、符号链接及 Linux Noto 字体条件。未修改条件、未把 skip 记为 pass。正式报告在 Windows 可用中文字体上已完成真实生成和下载。

## AC 直接断言定位

以下是最终Completion逐项核对索引，全部有实际直接断言和执行证据；当前Change逐需求表维护同一状态。首轮遗漏的报告计数及有数据降级已纳入AC20返修证据，不能仅凭初始入口表宣称完成。

| AC | 当前直接断言入口与行为 |
| --- | --- |
| 01 | `test_collection_content_runtime.py::test_content_state_reader_separates_comment_count_from_other_business_change`；真实五平台评论/回复重复补采 Journey；版本与分析相邻回归 |
| 02 | `test_analysis_version_reuse.py::test_non_ai_version_change_reuses_real_result_without_new_run`、`test_legacy_non_model_url_format_does_not_add_an_equivalence_condition`；真实补采发布时间+1版本、Run/LLM计数不变 |
| 03 | `test_supplement_author_snapshots.py` 的8个稳定/无ID/解绑/批量参数；`test_supplement_reclassifies_merged_current_and_accepts_empty_evidence`；真实Excel→补采作者快照 |
| 04–07 | `test_supplement_adds_new_brand_from_changed_current_field[title/text]` 的补采前后新增品牌时序；`test_supplement_reclassifies_merged_current_and_accepts_empty_evidence` 的撤销/空命中断言；新浏览器 Journey 的爱玛/雅迪、各自一致性Q7/G5、mixed；原Discovery unmatched仍拒绝 |
| 08 | `test_supplement_carries_manual_brand_and_empty_vehicle_locks`；repair的 `test_manual_dimensions_inherit_independent_sources_and_respect_tombstone`、`test_empty_manual_locks_and_current_unlock_keep_original_identity` |
| 09 | `test_non_ai_version_change_reuses_real_result_without_new_run`；`test_all_current_consumers_share_reuse_and_manual_values`；真实页面新版本 completed且模型请求数不增加 |
| 10–11 | `test_one_actual_input_field_change_stays_stale`；`test_hash_proof_is_independent_of_supported_output_version`；`test_source_snapshot_must_prove_persisted_hash_and_apply_is_idempotent`；只信实际成功Result及冻结6项输入证明 |
| 12–13 | `test_inherited_manual_locks_require_unlock_and_tombstones_survive`；`test_inherited_relevance_can_return_to_ai_without_resurrection`；真实浏览器三项人工锁/值和相邻人工相关性两条Journey |
| 14–15 | `test_explicit_reanalysis_executes_and_direct_result_keeps_inherited_lock`；`test_nonadjacent_equal_input_reuses_original_success` |
| 16 | `test_ai_persistence_content_lock_serializes_supplement`；`test_manual_content_lock_serializes_supplement_and_preserves_new_lock`；用第二数据库线程的实际锁等待证明串行化 |
| 17 | `test_supplement_reuse_exception_rolls_back_content_evidence_and_relation`；Evidence异常、错误Content身份回滚；repair的 `test_failure_after_business_and_checkpoint_writes_rolls_back_entire_batch` |
| 18 | `test_stale_fence_cannot_write_candidate_or_content`；`test_late_frozen_ai_work_does_not_overwrite_reused_current`；repair的 `test_checkpoint_takeover_rejects_old_fence_and_resumes_remaining_targets`、`test_cancelled_run_cannot_write_remaining_targets`、`test_registered_worker_retries_failed_batch_without_partial_success` |
| 19 | `test_all_current_consumers_share_reuse_and_manual_values`；单行投影、Count、品牌/车型/情感/标签筛选、正式/兼容详情和真实浏览器刷新 |
| 20 | `test_frozen_export_and_report_use_target_version_and_inherited_manual`；`test_collection_irrelevant_filter_uses_reused_raw_ai_not_manual_overlay`；新增`test_report_manual_count_uses_actual_frozen_objects`六参数及`test_downgrade_reconciles_only_reuse_contents`两参数；active Scheme工作台保持既有范围；真实导出/报告及修复后浏览器下载 |
| 21–22 | `test_content_consistency_repair.py` 的30项只读预检/有限目标/冻结目录/检查点/重试/二次幂等、人工和自动批量查询回归；`test_reuse_preflight_batches_targets_without_n_plus_one` 的100目标固定SQL数；真实性能计数记录在上表 |

## 实际文件与修改原因

以下路径均相对仓库根。相同责任的文件合列，生成Client经正式生成验证后没有语义改动，不属于交付diff。

| 文件 | 修改原因 |
| --- | --- |
| `backend/src/aima_ugc/adapters/persistence/postgres/content.py`、`content_complete.py`（同目录） | 合并observed_fields与字段新鲜度，冻结作者实际模型输入，作者输入变化建立新版本，保留稀疏和无稳定ID输入 |
| `backend/src/aima_ugc/bootstrap/collection_http.py`、`collection_scope.py`（同目录）；`backend/src/aima_ugc/adapters/persistence/postgres/collection_content.py` | 新补采Run冻结全量有效v2目录，详情合并后收敛Current分类及复用关系；空命中合法、旧Run兼容、Fence与原子身份保护 |
| `backend/src/aima_ugc/adapters/persistence/postgres/brand_vehicle_classification.py`、`brand_vehicle.py`、`vehicles.py`（同目录） | 统一完整Current解析与两个Evidence Owner批量人工继承，保留分维锁、墓碑、来源及全部自动命中 |
| `backend/src/aima_ugc/adapters/persistence/postgres/analysis_reuse.py`、`analysis_effective.py`（同目录，新增） | 生产Hash与不可变源快照证明、同Content成功Result正式引用、统一有效结果及人工来源批量读取 |
| `backend/src/aima_ugc/adapters/persistence/postgres/analysis.py`、`analysis_batch.py`（同目录） | 统一冻结作者输入，持久化成功Result时加Content锁并保留旧冻结Run过期审计 |
| `backend/src/aima_ugc/adapters/persistence/postgres/analysis_manual_reviews.py`、`relevance_reviews.py`（同目录） | 继承结果上的人工写资格、显式解锁和inherit_ai墓碑遵循当前有效来源 |
| `backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py`、`collection_targets.py`、`report_runs.py`、`reporting.py`、`workbench.py`（同目录） | List/Count/详情/筛选、原AI相关性、冻结导出/报告和工作台使用同一有效来源规则，保留各自Scheme边界 |
| `backend/src/aima_ugc/bootstrap/manual_ingestion.py`、`historical_import_worker.py`、`canonical_replay_worker.py`（同目录）；`backend/src/aima_ugc/adapters/persistence/postgres/xiaohongshu_replay.py` | 现有Excel、历史导入、Canonical与Raw Replay在原事务调用同一生产复用规则 |
| `backend/src/aima_ugc/modules/analysis/tables.py`；`migrations/versions/20261009_0083_analysis_version_reuse.py`（新增Migration） | 新Analysis Owner关联表、完整FK/Hash约束、有效来源SQL函数和目标投影触发/刷新，无全量回填 |
| `backend/src/aima_ugc/modules/content/consistency_repair.py`、`consistency_repair_tables.py`（同目录，新增）；`backend/src/aima_ugc/adapters/persistence/postgres/content_consistency_repair.py`（新增） | 有限目标、只读预检、冻结目录、Run/Target持久事实、UUID检查点、批量幂等恢复 |
| `backend/src/aima_ugc/bootstrap/content_consistency_repair_worker.py`（新增）、`worker.py`（同目录）；`backend/src/aima_ugc/database_schema.py` | 复用正式Job Runtime/Fencing注册修复Handler与Schema，失败/接管/取消不产生部分成功 |
| `scripts/operations/content_consistency_repair.py`；`migrations/versions/20261009_0084_content_consistency_repair.py`（均新增） | 正式管理CLI的dry-run/start/status/cancel；新增修复Run/Target DDL，不在Migration扫描Content |
| `tests/integration/content/test_analysis_version_reuse.py`、`test_supplement_author_snapshots.py`、`test_content_consistency_repair.py`（同目录，新增） | Hash协议、非相邻复用、人工/冻结消费者、真实并发与回滚、快照稀疏输入、修复Runtime及固定SQL数直接回归 |
| `tests/integration/content/test_excel_follower_count_voice_plaza.py` | Excel非AI字段补齐后的版本、当前声音广场投影兼容 |
| `tests/integration/collection/test_collection_content_runtime.py`、`test_collection_content_supplement.py`（同目录） | 完整Current/多品牌/空命中/人工锁/事务/Fence与新Run目录冻结，包括title/text新增品牌时序 |
| `tests/integration/collection/test_collection_worker_runtime.py`、`test_xiaohongshu_incremental_comments_runtime.py`（同目录） | 同步新增Job的完整注册集合；由Content Owner建立合法历史版本夹具，原评论停止边界不变 |
| `tests/integration/ingestion/test_canonical_replay_worker.py` | 将过时的零Content查询断言同步为恰好两条限定批次的Analysis集合读取，保留账本/来源、101条总SQL<200及撤销回归 |
| `frontend/e2e-fullstack/comment-supplement.spec.ts` | 真实页面补采→AI→人工修正→等价补采自动刷新；核版本/来源/锁/品牌车型与零额外模型请求 |
| `tests/fullstack/create_stage8f_excel_fixture.py`、`fake_tikhub_comment_worker.py`、`fake_openai_llm.py`（同目录） | 仅新增明确测试Scenario的等价补采响应、人工值和Fake模型请求计数，不修改真实Provider行为 |
| `backend/src/aima_ugc/modules/analysis/README.md`、`backend/src/aima_ugc/modules/content/README.md`、`backend/src/aima_ugc/modules/reporting/README.md` | 同步生产复用、人工继承、历史冻结与管理入口，不重复维护字段Schema |
| `docs/blueprint/03_数据库与文件存储.md`、`04_后端任务API与前端.md`、`08_采集策略与平台能力.md`（同目录） | 说明新增Owner关系/持久Job/补采原子顺序及有效结果读取边界 |
| `docs/appendix/07_AI舆情打标与分析实现.md`；`docs/product/02_当前产品能力与用户流程.md` | 同步等价输入免重打标、变化时stale及人工保留的用户行为 |
| `docs/operations/03_内容重分类与Legacy_Cleanup运行手册.md`、`docs/operations/README.md` | 有限dry-run/申请生产范围/start/status/cancel、检查点恢复、升级与代码/DDL回退边界 |
| `changes/active/CHG-20261009-143436-supplement-result-consistency/CHANGE.md`、`EVIDENCE.md`（同目录） | 用户上游AC01–AC22追溯、决策、当前验证和本地交付审计 |

## 整批独立审查与定向返修

两个独立Reviewer完成全部主要投影后统一收口。首轮在9ddc6513发现两项P2，主审随后独立比较caf06ae1/9ddc6513并确认反例；没有把先前漏审的“无Finding”当最终结论。Parent接受以下同一Repair Package，R20暂回not_satisfied，其他已稳定业务规则不扩展。

- F-B1：统一读取无人工时返回`manual_override: null`，冻结报告的`has_key`统计错误地计入人工。汇总应只计真实JSON对象，兼容既有冻结null，并保留全解锁人工对象的基线计数语义，不改写历史报告。
- F-B2：本轮新增0083在删除复用表前未收敛物化投影。恢复旧函数后，按复用表的Content UUID Keyset每批1000定向刷新投影及筛选目录，再删除新增结构；保留直接结果、当前人工和无关内容，不扫描全部Content或伪造版本。
- Ingestion执行回归：两条旧SQL计数断言要求零Content查询，新增合法Analysis批量锁与成功历史查询使其固定为2。保留原101条总SQL<200、账本/来源/Evidence和撤销断言，并验证恰好两条限定批次IN查询及其锁/EXISTS用途，避免以放宽计数掩盖N+1。

实施前先增加真实PostgreSQL Red：报告缺键/null、直接/继承人工及解锁对象；带合法复用completed投影的结构降级，并对照直接结果和无关Content。Green后只复审原Finding、repair diff、相邻回归、AC20和回退，不重启无关全任务审查。

返修生产源冻结于`8a10f441b6ef7ea05952bb9fa87aecd754551f04`（base caf06ae1，decision_epoch 1）。主审`preflight_review`与盲审`blind_completion_review`分别核对当前revision、repair diff及Hash后完成限定复审，F-B1/F-B2均resolved，无新增blocking Finding。主审明确用修复后的结论替代漏审的初始结论。Parent在两轮全部主要投影闭合后作唯一综合结论，没有按部分草稿提前返修。最终待收齐的独立执行结果不由Reviewer的静态PASS代替。

最终独立执行已全部收齐并保持相同生产Hash。PostgreSQL不同测试汇总为Platform73、Database120、Jobs22、Collection245、Content239（原231加新8）、Ingestion156、Vehicles5、Reporting10，共870项实际通过；Jobs另1个既有Linux条件skip。修正后重跑的用例不重复加入这个总数，14个Migration checkpoint单列。完整后端2095、前端306、Browser Mock206、真实Full-stack20等其他层也分别计数。Parent重读上游、逐AC映射、反向核对及未决清零完成，当前终点为Local Ready for User Acceptance。

## 环境清理与实际边界

Full-stack拥有的5个进程树按PID、启动时间精确清理，8090/8091/4174/5173已释放。报告浏览器由Tester拥有的API/Vite已清理，55439/55440已释放。全部lease释放后，Parent逐一核对两个PostgreSQL容器的完整ID、名称、任务标签和端口，再删除容器及匿名volume：`6df07e643ee856a9498b683251e1eafdc457f6c270bd9950d5de7a561cf3eb22`和`0b3a6dfdb39ff6e96a05ebbd9f501f4810250c49f9b6e528dc8d3345dd6246bf`。25439/55437及上述所有测试端口已确认无监听；忽略目录中的日志、截图、下载报告和Wheel保留。用户开发容器、库及Secret未操作。

历史修复在隔离测试中实际完成dry-run、apply、重试/接管/取消、原子回滚和幂等验证，不仅验证预检；真实业务历史数据没有执行修复。本轮不发布、不部署、不push、不创建PR或合并。没有40M生产规模性能结论。全部AC及两轮独立Review已闭合，用户本地人工验收尚待进行，远程CI未触发，不声明PR Ready。
