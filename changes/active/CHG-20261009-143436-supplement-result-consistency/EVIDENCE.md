# 补采一致性本地验证证据

本记录属于当前 Change，需求源为用户在本会话粘贴的完整任务书及“本地验证、先不合并远程主分支”的指令。只记录本轮实际命令与直接断言；不把 Mock、静态阅读或平台跳过项算成真实数据库验收。

## 测试环境与写入范围

基线 `caf06ae1be1d243545d21a71fcbfe72640d0bd5f`；本地分支 `fix/supplement-result-consistency`，decision epoch 为 1。所有运行数据在两个任务专属 PostgreSQL 18.4 容器内：`25439/aima_supplement_test`、`25439/aima_supplement_browser` 及 `55437/aima_report_test`。特殊身份用例按其既有保护要求使用同一任务容器内另建的专用库。没有迁移或修改用户开发库、生产库，没有 TikHub/付费模型 Probe。

Python 命令均使用仓库根 `.venv/Scripts/python.exe`；Node 命令使用 `D:/node/npm.ps1 --prefix frontend`。每批数据库测试先加载 `.runtime/supplement-consistency/` 中对应的显式隔离环境。日志、浏览器截图和测试文件保存在该忽略目录中；正式证据结论保留在此 Change。

## 已实际完成的验证

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
| 仓库质量 | `check_agent_governance.py`、`scan_secrets.py`、`check_architecture.py`、`check_table_ownership.py`、`check_docs.py`、`check_docs_facts.py` | 已通过阶段检查，最终文档及 Writer 释放后重新核对受影响项 |
| Collection广域回归及修正 | `pytest tests/integration/collection -vv -o faulthandler_timeout=45`；随后在独立25439库运行两个失败项的完整文件 | 首次完整243 passed / 2 failed / 536.11s；新Job exact-set漏同步及缺Version的直接SQL夹具已修正，两个完整文件2 passed / 4.18s，独立复验待收齐。首轮缓冲输出运行在有界诊断前中断，不计完成或失败 |

完整后端的16个跳过来自现有 Windows/POSIX、符号链接及 Linux Noto 字体条件。未修改条件、未把 skip 记为 pass。正式报告在 Windows 可用中文字体上已完成真实生成和下载。

## AC 直接断言定位

以下是最终 Completion 的核对索引；最终状态由 CHANGE 的逐需求表维护，尚未完成项不会因为这里列了测试入口而自动通过。

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
| 20 | `test_frozen_export_and_report_use_target_version_and_inherited_manual`；`test_collection_irrelevant_filter_uses_reused_raw_ai_not_manual_overlay`；active Scheme工作台保持其既有范围；真实账号补采→导出/报告工作台及报告下载 |
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
| `frontend/e2e-fullstack/comment-supplement.spec.ts` | 真实页面补采→AI→人工修正→等价补采自动刷新；核版本/来源/锁/品牌车型与零额外模型请求 |
| `tests/fullstack/create_stage8f_excel_fixture.py`、`fake_tikhub_comment_worker.py`、`fake_openai_llm.py`（同目录） | 仅新增明确测试Scenario的等价补采响应、人工值和Fake模型请求计数，不修改真实Provider行为 |
| `backend/src/aima_ugc/modules/analysis/README.md`、`backend/src/aima_ugc/modules/content/README.md`、`backend/src/aima_ugc/modules/reporting/README.md` | 同步生产复用、人工继承、历史冻结与管理入口，不重复维护字段Schema |
| `docs/blueprint/03_数据库与文件存储.md`、`04_后端任务API与前端.md`、`08_采集策略与平台能力.md`（同目录） | 说明新增Owner关系/持久Job/补采原子顺序及有效结果读取边界 |
| `docs/appendix/07_AI舆情打标与分析实现.md`；`docs/product/02_当前产品能力与用户流程.md` | 同步等价输入免重打标、变化时stale及人工保留的用户行为 |
| `docs/operations/03_内容重分类与Legacy_Cleanup运行手册.md`、`docs/operations/README.md` | 有限dry-run/申请生产范围/start/status/cancel、检查点恢复、升级与代码/DDL回退边界 |
| `changes/active/CHG-20261009-143436-supplement-result-consistency/CHANGE.md`、`EVIDENCE.md`（同目录） | 用户上游AC01–AC22追溯、决策、当前验证和本地交付审计 |

## 环境清理与实际边界

Full-stack拥有的5个进程树按PID、启动时间精确清理，8090/8091/4174/5173已释放。报告浏览器由Tester拥有的API/Vite已清理，55439/55440已释放。两个PostgreSQL测试容器在全部数据库验收结束后由Parent按完整ID及任务标签统一清理。

本轮不运行生产历史修复、不发布、不部署、不push、不创建PR或合并。没有40M生产数据规模性能结论。全部AC已有上面的直接证据；广域PG、最终Completion和独立Review仍在执行，当前记录不宣称已Ready。
