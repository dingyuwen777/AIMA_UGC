# CHG-314 剩余失败诊断（临时）

## Browser Mock
exit_code=1
```text

> aima-ugc-frontend@0.1.0 test:e2e
> playwright test


Running 48 tests using 2 workers

  ✓   2 e2e/artifact-retention.spec.ts:164:1 › shows the seven-day Excel export window in the existing export dialog (4.1s)
  ✓   1 e2e/artifact-retention.spec.ts:118:1 › shows Excel import source retention from terminal Job time when Batch time is absent (4.1s)
  ✓   4 e2e/collection-runtime.spec.ts:130:1 › creates a one-time TikHub discovery Run from multiple Keyword Packs (2.4s)
  ✓   3 e2e/collection-runtime.spec.ts:106:1 › centralizes runtime facts, opens Batch detail, and creates a local Campaign with selected packs (3.0s)
  ✓   5 e2e/collection-runtime.spec.ts:152:1 › creates a TikHub supplement Run only for a platform that exists in the Batch (2.2s)
  ✓   6 e2e/collection-runtime.spec.ts:172:1 › re-probes Batch platform eligibility when switching A to B and back to A (2.2s)
  ✓   7 e2e/collection-runtime.spec.ts:191:1 › explains failed Import terminal state without inventing pending stages (2.1s)
  ✓   8 e2e/collection-runtime.spec.ts:202:1 › shows a safe actionable error when the Worker cannot read the Provider Secret (2.2s)
  ✘   9 e2e/collection-runtime.spec.ts:269:1 › shows the stable unified Error Contract request_id (1.8s)
  ✓  10 e2e/collection-strategy-figma-geometry.spec.ts:173:1 › matches the formal 1440×900 Figma geometry for the strategy workspace (1.7s)
  ✓  11 e2e/collection-strategy-figma-geometry.spec.ts:194:1 › matches the formal keyword modal and collection plan drawer geometry (1.8s)
  ✘  12 e2e/collection-runtime.spec.ts:269:1 › shows the stable unified Error Contract request_id (retry #1) (2.8s)
  ✓  13 e2e/collection-strategy-figma-geometry.spec.ts:219:1 › matches the formal relevance workspace and plan detail drawer geometry (2.0s)
  ✓  14 e2e/collection-strategy.spec.ts:162:1 › disables Keyword Pack stop actions when current backend facts forbid them (1.7s)
  ✓  15 e2e/collection-strategy.spec.ts:115:1 › matches the approved Figma workspace and resolves historical vehicle scope from the API catalog (2.5s)
  ✓  16 e2e/collection-strategy.spec.ts:175:1 › creates only a periodic Collection Plan and fully paginates the active-only vehicle selector (2.8s)
  ✓  17 e2e/excel-import-submit-state.spec.ts:130:1 › does not present an incomplete local Campaign form as a busy operation (1.7s)
  ✓  18 e2e/excel-import-submit-state.spec.ts:149:1 › stages local files through Campaign upload and restores a visible error (2.2s)
  ✓  19 e2e/excel-import-submit-state.spec.ts:193:1 › allows an interrupted local upload Campaign to be cancelled (1.8s)
  ✓  20 e2e/frontend-reliability.spec.ts:34:1 › keeps healthy admin resources usable when audit fails and paginates audit after retry (2.0s)
  ✓  22 e2e/historical-migration.spec.ts:208:1 › selects a server directory for bounded recursive discovery (1.5s)
  ✓  23 e2e/historical-migration.spec.ts:229:1 › continues directory enumeration with the server cursor (1.1s)
  ✓  24 e2e/historical-migration.spec.ts:239:1 › reopens an existing campaign after a page reload (1.1s)
  ✓  25 e2e/historical-migration.spec.ts:249:1 › does not invent a percentage while directory discovery has no total (1.1s)
  ✓  21 e2e/historical-migration.spec.ts:150:1 › selects only server-relative files, preflights, and explicitly starts a campaign (7.5s)
  ✓  27 e2e/historical-migration.spec.ts:344:1 › uses campaign failed-chunk facts even when bounded detail omits failed chunks (1.8s)
  ✓  28 e2e/manual-relevance-review.spec.ts:87:1 › marks AI irrelevant content as relevant through the explicit decision contract (1.2s)
  ✓  29 e2e/manual-relevance-review.spec.ts:118:1 › marks AI relevant content as irrelevant from the business-relevant list (1.1s)
  ✓  30 e2e/manual-relevance-review.spec.ts:149:1 › undoes a manual relevant override without deleting the AI irrelevant fact (1.1s)
  ✓  26 e2e/historical-migration.spec.ts:290:1 › keeps polling a cancelling campaign until it reaches cancelled (6.9s)
  ✓  31 e2e/manual-relevance-review.spec.ts:181:1 › keeps manual override undoable when the current AI result is stale (1.8s)
  ✓  32 e2e/manual-relevance-review.spec.ts:213:1 › batch marks selected AI relevant content as irrelevant through the same endpoint (2.2s)
  ✓  33 e2e/voice-plaza-design.spec.ts:136:1 › matches the formal normal data composition with run history, table rows and cursor (1.8s)
  ✓  34 e2e/voice-plaza-design.spec.ts:160:1 › matches the formal 1440 desktop shell and empty-state composition (1.9s)
  ✓  35 e2e/voice-plaza-design.spec.ts:189:1 › renders the formal loading state while the content request is in flight (1.9s)
  ✓  36 e2e/voice-plaza-design.spec.ts:217:1 › renders the formal error banner and recoverable list error state (2.0s)
  ✓  37 e2e/voice-plaza-design.spec.ts:245:1 › keeps the formal runtime-unavailable warning while the content list stays usable (1.9s)
  ✓  39 e2e/voice-plaza-review-regressions.spec.ts:59:1 › 辅助能力失败时保留成功加载的空内容状态 (1.7s)
  ✘  38 e2e/voice-plaza-design.spec.ts:267:1 › matches the formal detail, analysis and export overlay geometry (2.8s)
  ✓  40 e2e/voice-plaza-review-regressions.spec.ts:96:1 › 车型目录响应缺少 items 时显示错误且不中断页面渲染 (1.3s)
  ✓  41 e2e/voice-plaza-review-regressions.spec.ts:122:1 › Failed Analysis Run 保留后端 error_code (1.8s)
  ✓  43 e2e/voice-plaza.spec.ts:284:1 › renders every AI label and opens the text-first content detail (1.8s)
  ✘  42 e2e/voice-plaza-design.spec.ts:267:1 › matches the formal detail, analysis and export overlay geometry (retry #1) (2.9s)
  ✓  44 e2e/voice-plaza.spec.ts:307:1 › loads taxonomy options and submits voice type with dependent labels (1.8s)
  ✓  45 e2e/voice-plaza.spec.ts:328:1 › reconciles taxonomy before issuing the initial content query (2.1s)
  ✓  46 e2e/voice-plaza.spec.ts:350:1 › keeps the content list usable when taxonomy is unavailable (1.9s)
  ✓  47 e2e/voice-plaza.spec.ts:376:1 › shows AI unavailable and disables analysis when runtime is not configured (1.9s)
  ✓  48 e2e/voice-plaza.spec.ts:391:1 › creates explicit analysis and durable Excel export jobs (2.9s)
  ✓  49 e2e/voice-plaza.spec.ts:491:1 › creates an all-data analysis run without browser-side content ids (2.1s)
  ✓  50 e2e/voice-plaza.spec.ts:547:1 › keeps export history visible but disables empty query export creation (1.5s)


  1) e2e/collection-runtime.spec.ts:269:1 › shows the stable unified Error Contract request_id ─────

    Error: expect(locator).toContainText(expected) failed

    Locator: getByRole('alert')
    Expected substring: "req_stage8e_error"
    Error: strict mode violation: getByRole('alert') resolved to 2 elements:
        1) <div role="alert" data-v-5e8e65b0="" class="principal-error">…</div> aka getByText('身份读取失败重试')
        2) <div role="alert" data-v-a9575d50="" data-v-3f03d98b="" class="aima-feedback is-error page-error">…</div> aka getByRole('alert').filter({ hasText: '分页服务配置不可用，请使用 request_id' })

    Call log:
      - Expect "toContainText" with timeout 5000ms
      - waiting for getByRole('alert')


      275 |   })
      276 |   await page.goto('/collection-runtime')
    > 277 |   await expect(page.getByRole('alert')).toContainText('req_stage8e_error')
          |                                         ^
      278 | })
      279 |
        at /home/runner/work/AIMA_UGC/AIMA_UGC/frontend/e2e/collection-runtime.spec.ts:277:41

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/collection-runtime-shows-t-d3cbe-d-Error-Contract-request-id/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/collection-runtime-shows-t-d3cbe-d-Error-Contract-request-id/error-context.md

    attachment #3: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/collection-runtime-shows-t-d3cbe-d-Error-Contract-request-id/trace.zip
    Usage:

        npx playwright show-trace test-results/collection-runtime-shows-t-d3cbe-d-Error-Contract-request-id/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

    Retry #1 ───────────────────────────────────────────────────────────────────────────────────────

    Error: expect(locator).toContainText(expected) failed

    Locator: getByRole('alert')
    Expected substring: "req_stage8e_error"
    Error: strict mode violation: getByRole('alert') resolved to 2 elements:
        1) <div role="alert" data-v-5e8e65b0="" class="principal-error">…</div> aka getByText('身份读取失败重试')
        2) <div role="alert" data-v-a9575d50="" data-v-3f03d98b="" class="aima-feedback is-error page-error">…</div> aka getByRole('alert').filter({ hasText: '分页服务配置不可用，请使用 request_id' })

    Call log:
      - Expect "toContainText" with timeout 5000ms
      - waiting for getByRole('alert')


      275 |   })
      276 |   await page.goto('/collection-runtime')
    > 277 |   await expect(page.getByRole('alert')).toContainText('req_stage8e_error')
          |                                         ^
      278 | })
      279 |
        at /home/runner/work/AIMA_UGC/AIMA_UGC/frontend/e2e/collection-runtime.spec.ts:277:41

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/collection-runtime-shows-t-d3cbe-d-Error-Contract-request-id-retry1/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/collection-runtime-shows-t-d3cbe-d-Error-Contract-request-id-retry1/error-context.md

    attachment #3: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/collection-runtime-shows-t-d3cbe-d-Error-Contract-request-id-retry1/trace.zip
    Usage:

        npx playwright show-trace test-results/collection-runtime-shows-t-d3cbe-d-Error-Contract-request-id-retry1/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  2) e2e/voice-plaza-design.spec.ts:267:1 › matches the formal detail, analysis and export overlay geometry 

    Error: expect(received).toBeLessThanOrEqual(expected)

    Expected: <= 1
    Received:    10

      117 | function expectNear(actual: number | undefined, expected: number): void {
      118 |   expect(actual).toBeDefined()
    > 119 |   expect(Math.abs((actual ?? 0) - expected)).toBeLessThanOrEqual(1)
          |                                              ^
      120 | }
      121 |
      122 | /** 固定正式 Normal / Runtime 状态共用的三行内容列表。 */
        at expectNear (/home/runner/work/AIMA_UGC/AIMA_UGC/frontend/e2e/voice-plaza-design.spec.ts:119:46)
        at /home/runner/work/AIMA_UGC/AIMA_UGC/frontend/e2e/voice-plaza-design.spec.ts:335:3

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/voice-plaza-design-matches-d38d5-and-export-overlay-geometry/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/voice-plaza-design-matches-d38d5-and-export-overlay-geometry/error-context.md

    attachment #3: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/voice-plaza-design-matches-d38d5-and-export-overlay-geometry/trace.zip
    Usage:

        npx playwright show-trace test-results/voice-plaza-design-matches-d38d5-and-export-overlay-geometry/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

    Retry #1 ───────────────────────────────────────────────────────────────────────────────────────

    Error: expect(received).toBeLessThanOrEqual(expected)

    Expected: <= 1
    Received:    10

      117 | function expectNear(actual: number | undefined, expected: number): void {
      118 |   expect(actual).toBeDefined()
    > 119 |   expect(Math.abs((actual ?? 0) - expected)).toBeLessThanOrEqual(1)
          |                                              ^
      120 | }
      121 |
      122 | /** 固定正式 Normal / Runtime 状态共用的三行内容列表。 */
        at expectNear (/home/runner/work/AIMA_UGC/AIMA_UGC/frontend/e2e/voice-plaza-design.spec.ts:119:46)
        at /home/runner/work/AIMA_UGC/AIMA_UGC/frontend/e2e/voice-plaza-design.spec.ts:335:3

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/voice-plaza-design-matches-d38d5-and-export-overlay-geometry-retry1/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/voice-plaza-design-matches-d38d5-and-export-overlay-geometry-retry1/error-context.md

    attachment #3: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/voice-plaza-design-matches-d38d5-and-export-overlay-geometry-retry1/trace.zip
    Usage:

        npx playwright show-trace test-results/voice-plaza-design-matches-d38d5-and-export-overlay-geometry-retry1/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  2 failed
    e2e/collection-runtime.spec.ts:269:1 › shows the stable unified Error Contract request_id ──────
    e2e/voice-plaza-design.spec.ts:267:1 › matches the formal detail, analysis and export overlay geometry 
  46 passed (1.1m)
```

## PostgreSQL Ingestion
exit_code=1
```text
============================= test session starts ==============================
platform linux -- Python 3.14.7, pytest-9.1.1, pluggy-1.6.0 -- /home/runner/work/AIMA_UGC/AIMA_UGC/.venv/bin/python
cachedir: .pytest_cache
rootdir: /home/runner/work/AIMA_UGC/AIMA_UGC
configfile: pyproject.toml
plugins: anyio-4.14.2
collecting ... collected 20 items

tests/integration/ingestion/test_frontend_reliability_postgres.py::test_keyword_pack_initial_keywords_commit_atomically_and_roll_back_together FAILED [  5%]
tests/integration/ingestion/test_frontend_reliability_postgres.py::test_audit_repository_and_service_page_complete_history PASSED [ 10%]
tests/integration/ingestion/test_frontend_reliability_postgres.py::test_historical_campaign_failed_chunk_count_ignores_bounded_detail_shape PASSED [ 15%]
tests/integration/ingestion/test_multi_keyword_pack_import.py::test_excel_import_uses_union_of_multiple_selected_keyword_packs PASSED [ 20%]
tests/integration/ingestion/test_stage12_historical_campaign_worker.py::test_source_manifest_identity_is_database_unique_when_ordinal_is_null PASSED [ 25%]
tests/integration/ingestion/test_stage12_historical_campaign_worker.py::test_historical_campaign_preflights_before_fill_only_import PASSED [ 30%]
tests/integration/ingestion/test_stage12_historical_campaign_worker.py::test_local_campaign_uploads_immutable_artifact_before_common_preflight PASSED [ 35%]
tests/integration/ingestion/test_stage12_historical_campaign_worker.py::test_local_campaign_can_be_cancelled_while_uploading PASSED [ 40%]
tests/integration/ingestion/test_stage12_historical_campaign_worker.py::test_historical_snapshot_fails_closed_when_source_changes_after_discovery PASSED [ 45%]
tests/integration/ingestion/test_stage12_historical_campaign_worker.py::test_historical_snapshot_technical_retry_reuses_bound_source_artifact PASSED [ 50%]
tests/integration/ingestion/test_stage12_historical_campaign_worker.py::test_historical_single_source_schedules_chunks_in_order_for_stable_first_row PASSED [ 55%]
tests/integration/ingestion/test_stage12_historical_campaign_worker.py::test_historical_failed_chunk_range_is_included_in_campaign_accounting PASSED [ 60%]
tests/integration/ingestion/test_stage12_historical_campaign_worker.py::test_historical_failed_retry_preserves_cross_chunk_duplicate_identity PASSED [ 65%]
tests/integration/ingestion/test_stage12_historical_campaign_worker.py::test_historical_queued_cancel_reaches_terminal_without_business_writes PASSED [ 70%]
tests/integration/ingestion/test_stage12_historical_campaign_worker.py::test_historical_chunk_resumes_after_lease_takeover_without_duplicate_outcome PASSED [ 75%]
tests/integration/ingestion/test_stage12_historical_capacity_harness.py::test_capacity_harness_records_bounded_end_to_end_evidence PASSED [ 80%]
tests/integration/ingestion/test_stage8b_import_http_worker.py::test_http_upload_worker_and_status_query_use_formal_stage8a_ingestion PASSED [ 85%]
tests/integration/ingestion/test_stage8b_import_http_worker.py::test_unavailable_source_artifact_fails_job_and_batch_without_content PASSED [ 90%]
tests/integration/ingestion/test_stage8b_import_http_worker.py::test_import_retry_after_business_commit_is_fenced_and_does_not_duplicate_content PASSED [ 95%]
tests/integration/ingestion/test_stage8c_import_batch_query.py::test_postgres_batch_list_cursor_filters_and_summary_roll_back_fixture PASSED [100%]

=================================== FAILURES ===================================
_ test_keyword_pack_initial_keywords_commit_atomically_and_roll_back_together __
tests/integration/ingestion/test_frontend_reliability_postgres.py:64: in test_keyword_pack_initial_keywords_commit_atomically_and_roll_back_together
    assert [item["text"] for item in created.json()["keywords"]] == [
E   AssertionError: assert ['电动车-0011d83...3f9694135b48'] == ['爱玛-0011d834...3f9694135b48']
E     
E     At index 0 diff: '电动车-0011d834a3e14cecb4d63f9694135b48' != '爱玛-0011d834a3e14cecb4d63f9694135b48'
E     
E     Full diff:
E       [
E     +     '电动车-0011d834a3e14cecb4d63f9694135b48',
E           '爱玛-0011d834a3e14cecb4d63f9694135b48',
E     -     '电动车-0011d834a3e14cecb4d63f9694135b48',
E       ]
----------------------------- Captured stdout call -----------------------------
[2026-09-03 08:31:36.061 runtime.py L114] [INFO] event=service.started timezone="Asia/Shanghai" message="Platform 运行基础已装配"
=============================== warnings summary ===============================
.venv/lib/python3.14/site-packages/pydantic/_internal/_generate_schema.py:325: 60 warnings
  /home/runner/work/AIMA_UGC/AIMA_UGC/.venv/lib/python3.14/site-packages/pydantic/_internal/_generate_schema.py:325: PydanticDeprecatedSince20: `json_encoders` is deprecated. See https://docs.pydantic.dev/2.13/concepts/serialization/#custom-serializers for alternatives. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.13/migration/
    warnings.warn(

.venv/lib/python3.14/site-packages/fastapi/testclient.py:1
  /home/runner/work/AIMA_UGC/AIMA_UGC/.venv/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/integration/ingestion/test_frontend_reliability_postgres.py::test_keyword_pack_initial_keywords_commit_atomically_and_roll_back_together - AssertionError: assert ['电动车-0011d83...3f9694135b48'] == ['爱玛-0011d834...3f9694135b48']
  
  At index 0 diff: '电动车-0011d834a3e14cecb4d63f9694135b48' != '爱玛-0011d834a3e14cecb4d63f9694135b48'
  
  Full diff:
    [
  +     '电动车-0011d834a3e14cecb4d63f9694135b48',
        '爱玛-0011d834a3e14cecb4d63f9694135b48',
  -     '电动车-0011d834a3e14cecb4d63f9694135b48',
    ]
================== 1 failed, 19 passed, 61 warnings in 14.71s ==================
```

## Real Full-stack
```text
===== admin-product-capabilities.spec.ts =====
exit_code=0
===== collection-plan-search-config.spec.ts =====
exit_code=0
===== excel-import.spec.ts =====
exit_code=1

> aima-ugc-frontend@0.1.0 test:e2e:fullstack
> playwright test --config playwright.fullstack.config.ts excel-import.spec.ts


Running 2 tests using 1 worker

  ✓  1 e2e-fullstack/excel-import.spec.ts:68:1 › Excel 浏览器多选词包后经过真实 API、Worker 和 PostgreSQL 可在声音广场查看 (12.5s)
  ✘  2 e2e-fullstack/excel-import.spec.ts:88:1 › 错误表头 Excel 由统一链路在预检阶段拒绝 (36.3s)


  1) e2e-fullstack/excel-import.spec.ts:88:1 › 错误表头 Excel 由统一链路在预检阶段拒绝 ─────────────────────────────

    Error: expect(locator).toBeDisabled() failed

    Locator: getByRole('dialog', { name: '导入数据' }).getByRole('button', { name: '开始导入' })
    Expected: disabled
    Timeout: 30000ms
    Error: element(s) not found

    Call log:
      - Expect "toBeDisabled" with timeout 30000ms
      - waiting for getByRole('dialog', { name: '导入数据' }).getByRole('button', { name: '开始导入' })


       96 |   await expect(detail.getByText('状态：failed')).toBeVisible({ timeout: 60_000 })
       97 |   await expect(detail.getByText('historical_snapshot_invalid')).toBeVisible()
    >  98 |   await expect(detail.getByRole('button', { name: '开始导入' })).toBeDisabled()
          |                                                              ^
       99 |   await expect(detail.getByRole('button', { name: '查看导入内容' })).toHaveCount(0)
      100 | })
      101 |
        at /home/runner/work/AIMA_UGC/AIMA_UGC/frontend/e2e-fullstack/excel-import.spec.ts:98:62

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/excel-import-错误表头-Excel-由统一链路在预检阶段拒绝/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/excel-import-错误表头-Excel-由统一链路在预检阶段拒绝/error-context.md

    attachment #3: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/excel-import-错误表头-Excel-由统一链路在预检阶段拒绝/trace.zip
    Usage:

        npx playwright show-trace test-results/excel-import-错误表头-Excel-由统一链路在预检阶段拒绝/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  1 failed
    e2e-fullstack/excel-import.spec.ts:88:1 › 错误表头 Excel 由统一链路在预检阶段拒绝 ──────────────────────────────
  1 passed (50.1s)
===== manual-relevance-review.spec.ts =====
exit_code=0
===== stage12-historical-analysis.spec.ts =====
exit_code=0
```
