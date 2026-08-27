import { expect, test } from '@playwright/test'

const contentId = '42345678-1234-5678-1234-567812345678'
const analysisJobId = '52345678-1234-5678-1234-567812345678'
const analysisRunId = '62345678-1234-5678-1234-567812345678'
const exportId = '72345678-1234-5678-1234-567812345678'
const exportJobId = '82345678-1234-5678-1234-567812345678'

const analysisRun = {
  id: analysisRunId,
  planner_job_id: analysisJobId,
  sequence_no: 1,
  status: 'running',
  run_intent: 'manual_reanalysis',
  scope: 'query',
  target_count: 20,
  shard_count: 2,
  shard_size: 6,
  prompt_version: 'content_labeling_v3',
  prompt_sha256: 'a'.repeat(64),
  taxonomy_sha256: 'b'.repeat(64),
  model_provider: 'openai-compatible',
  model: 'fixture-model',
  generation_config: { temperature: 0 },
  generation_config_hash: 'c'.repeat(64),
  stats: { pending: 20, succeeded: 0, failed: 0, cancelled: 0, stale: 0 },
  shards: [
    { request_id: '63345678-1234-5678-1234-567812345678', job_id: '64345678-1234-5678-1234-567812345678', shard_no: 0, target_count: 4, status: 'running', progress: 50, error_code: null },
    { request_id: '65345678-1234-5678-1234-567812345678', job_id: '66345678-1234-5678-1234-567812345678', shard_no: 1, target_count: 6, status: 'running', progress: 25, error_code: null },
  ],
  created_at: '2026-08-21T03:00:00Z',
  started_at: null,
  finished_at: null,
}

const item = {
  id: contentId,
  platform: 'xiaohongshu',
  external_content_id: 'note-stage8d-1',
  content_type: 'note',
  title: '爱玛 Q7 的坐垫舒适，但续航仍有提升空间',
  text: '日常通勤约 12 公里，坐垫很舒服，希望后续优化低温续航。',
  author_display_name: '小满的通勤日记',
  published_at: '2026-08-21T01:42:00Z',
  last_seen_at: '2026-08-21T02:00:00Z',
  content_url: 'https://example.com/note-stage8d-1',
  metrics: { like_count: 128, comment_count: 18, share_count: 6, favorite_count: 32 },
  analysis: {
    status: 'completed',
    sentiment: '负面',
    labels: [
      { primary_label: '电池、续航与充电', secondary_label: '实际续航表现' },
      { primary_label: '驾乘体验', secondary_label: '坐垫舒适性' },
      { primary_label: '售后服务', secondary_label: '客服与服务态度' },
    ],
    analyzed_at: '2026-08-21T02:30:00Z',
    model_provider: 'fixture',
    model: 'fixture-model',
  },
  source: {
    provider_name: 'file-import',
    import_batch_id: '12345678-1234-5678-1234-567812345678',
  },
}

const job = (id: string, jobType: string) => ({
  id,
  job_type: jobType,
  status: 'queued',
  attempt: 0,
  max_attempts: 3,
  progress: 0,
  error_code: null,
  result: null,
  created_at: '2026-08-21T03:00:00Z',
  started_at: null,
  finished_at: null,
})

const runningExport = {
  id: exportId,
  job: {
    ...job(exportJobId, 'reporting.content-export-excel.v1'),
    status: 'running',
    progress: 64,
  },
  artifact_id: null,
  filename: null,
  stats: null,
  created_at: '2026-08-21T03:00:00Z',
  completed_at: null,
}

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/content-analysis-capabilities', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ configured: true }),
    })
  })

  await page.route('**/api/v1/contents**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname === `/api/v1/contents/${contentId}`) {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          ...item,
          media: [],
          comments: [
            {
              id: '92345678-1234-5678-1234-567812345678',
              external_comment_id: 'comment-1',
              author_display_name: '用户乙',
              text: '我也关注冬季续航。',
              published_at: '2026-08-21T02:10:00Z',
              like_count: 3,
              reply_count: 0,
            },
          ],
          comment_coverage: {
            coverage: 'partial',
            reported_total: 18,
            collected_count: 1,
            observed_at: '2026-08-21T02:20:00Z',
          },
          source_records: [item.source],
        }),
      })
      return
    }
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [item], next_cursor: null, has_more: false }),
    })
  })

  await page.route('**/api/v1/analysis/content-runs/preview', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        target_count: 1,
        shard_count: 1,
        shard_size: 1,
        prompt_version: 'content_labeling_v3',
        prompt_sha256: 'a'.repeat(64),
        taxonomy_sha256: 'b'.repeat(64),
        model_provider: 'openai-compatible',
        model: 'fixture-model',
        generation_config: { temperature: 0 },
        generation_config_hash: 'c'.repeat(64),
        configuration_hash: 'd'.repeat(64),
        cost_estimate_available: false,
        cost_estimate_note: '当前无法可靠估算费用；运行后以实际审计为准。',
      }),
    })
  })
  await page.route('**/api/v1/analysis/content-runs', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({
          run_id: analysisRunId,
          planner_job_id: analysisJobId,
          target_count: 1,
          shard_count: 1,
          status: 'queued',
        }),
      })
      return
    }
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [] }),
    })
  })
  await page.route(`**/api/v1/analysis/content-runs/${analysisRunId}`, async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(analysisRun),
    })
  })
  await page.route(`**/api/v1/analysis/content-runs/${analysisRunId}/cancel`, async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        id: analysisRunId,
        planner_job_id: analysisJobId,
        sequence_no: 1,
        status: 'cancelled',
        run_intent: 'manual_reanalysis',
        scope: 'query',
        target_count: 1,
        shard_count: 1,
        shard_size: 1,
        prompt_version: 'content_labeling_v3',
        prompt_sha256: 'a'.repeat(64),
        taxonomy_sha256: 'b'.repeat(64),
        model_provider: 'openai-compatible',
        model: 'fixture-model',
        generation_config: { temperature: 0 },
        generation_config_hash: 'c'.repeat(64),
        stats: { pending: 0, succeeded: 0, failed: 0, cancelled: 1, stale: 0 },
        shards: [],
        created_at: '2026-08-21T03:00:00Z',
        started_at: null,
        finished_at: '2026-08-21T03:01:00Z',
      }),
    })
  })

  await page.route('**/api/v1/data-exports**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (request.method() === 'POST') {
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({
          export_id: exportId,
          job_id: exportJobId,
          target_count: 1,
          status: 'queued',
        }),
      })
      return
    }
    if (url.pathname === `/api/v1/data-exports/${exportId}`) {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          id: exportId,
          job: job(exportJobId, 'reporting.content-export-excel.v1'),
          artifact_id: null,
          filename: null,
          stats: null,
          created_at: '2026-08-21T03:00:00Z',
          completed_at: null,
        }),
      })
      return
    }
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [runningExport] }),
    })
  })
})

test('renders every AI label and opens the text-first content detail', async ({ page }) => {
  await page.goto('/voice-plaza')

  await expect(page.getByRole('heading', { name: '声音广场' })).toBeVisible()
  await expect(page.getByText('电池、续航与充电 / 实际续航表现')).toBeVisible()
  await expect(page.getByText('驾乘体验 / 坐垫舒适性')).toBeVisible()
  await expect(page.getByText('售后服务 / 客服与服务态度')).toBeVisible()

  if (process.env.AIMA_CAPTURE_VISUAL === '1') {
    await page.screenshot({ path: 'test-results/stage8d-voice-plaza.png', fullPage: true })
  }

  await page.getByRole('button', { name: '查看详情' }).click()
  await expect(page.getByRole('complementary', { name: '内容详情' })).toBeVisible()
  await expect(page.getByText('AI 情感与全部标签')).toBeVisible()
  await expect(page.getByText('我也关注冬季续航。')).toBeVisible()
  await expect(page.getByText('原始内容媒体')).toHaveCount(0)
  if (process.env.AIMA_CAPTURE_VISUAL === '1') {
    await page.screenshot({ path: 'test-results/stage8d-content-detail.png', fullPage: true })
  }
})

test('shows AI unavailable and disables analysis when runtime is not configured', async ({ page }) => {
  await page.unroute('**/api/v1/content-analysis-capabilities')
  await page.route('**/api/v1/content-analysis-capabilities', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ configured: false }),
    })
  })

  await page.goto('/voice-plaza')

  await expect(page.getByText(/AI 打标暂不可用：当前环境尚未配置可用的 LLM Runtime/)).toBeVisible()
  await expect(page.getByRole('button', { name: /AI 打标/ })).toBeDisabled()
})

test('creates explicit analysis and durable Excel export jobs', async ({ page }) => {
  let analysisRequest: unknown
  let exportRequest: unknown
  let previewRequest: unknown
  let analysisCreated = false
  let cancelRequested = false
  await page.route('**/api/v1/analysis/content-runs/preview', async (route) => {
    previewRequest = route.request().postDataJSON()
    await route.fallback()
  })
  await page.route('**/api/v1/analysis/content-runs', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ items: analysisCreated ? [analysisRun] : [] }),
      })
      return
    }
    analysisRequest = route.request().postDataJSON()
    analysisCreated = true
    await route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({
        run_id: analysisRunId,
        planner_job_id: analysisJobId,
        target_count: 1,
        shard_count: 1,
        status: 'queued',
      }),
    })
  })
  await page.route('**/api/v1/data-exports', async (route) => {
    if (route.request().method() !== 'POST') return route.fallback()
    exportRequest = route.request().postDataJSON()
    await route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({
        export_id: exportId,
        job_id: exportJobId,
        target_count: 1,
        status: 'queued',
      }),
    })
  })
  await page.route(`**/api/v1/analysis/content-runs/${analysisRunId}/cancel`, async (route) => {
    cancelRequested = true
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        ...analysisRun,
        status: 'cancelled',
        stats: { pending: 0, succeeded: 0, failed: 0, cancelled: 20, stale: 0 },
        finished_at: '2026-08-21T03:01:00Z',
        shards: [],
      }),
    })
  })

  await page.goto('/voice-plaza')
  const analysisButton = page.getByRole('button', { name: /AI 打标/ })
  await expect(analysisButton).toBeDisabled()
  await page.getByLabel('选择当前已加载内容').check()
  await expect(analysisButton).toBeEnabled()
  await analysisButton.click()
  await expect(page.getByText('预检目标 1 条，拆分 1 个 Shard')).toBeVisible()
  await expect(page.getByText('每个 Shard 1 条 · openai-compatible / fixture-model')).toBeVisible()
  await expect(page.getByText(/当前无法可靠估算费用/)).toBeVisible()
  await page.getByRole('button', { name: '确认并创建 Analysis Run' }).click()
  await expect(page.getByText(/已创建 AI Analysis Run/)).toBeVisible()
  await expect(page.getByText('AI Analysis Run 历史')).toBeVisible()
  await expect(page.getByText('Run #1 · 处理中')).toBeVisible()
  await expect(page.getByRole('progressbar', { name: 'AI Run #1 进度' })).toHaveAttribute('aria-valuenow', '18')
  expect(previewRequest).toMatchObject({
    targets: { scope: 'selected', content_ids: [contentId] },
  })
  expect(analysisRequest).toMatchObject({
    targets: { scope: 'selected', content_ids: [contentId] },
    expected_target_count: 1,
    expected_configuration_hash: 'd'.repeat(64),
    run_intent: 'manual_reanalysis',
  })
  await page.getByRole('button', { name: '取消 Run' }).click()
  await expect(page.getByText('Run #1 · 已取消')).toBeVisible()
  expect(cancelRequested).toBe(true)

  await page.getByRole('button', { name: /导出记录/ }).click()
  await expect(page.getByText('未完成 AI 打标的内容不会被丢弃')).toBeVisible()
  await page.getByText('当前页内容').click()
  await page.getByRole('button', { name: '创建 Excel 导出' }).click()
  await expect(page.getByText(/已创建 Excel 导出 Job/)).toBeVisible()
  expect(exportRequest).toMatchObject({
    format: 'xlsx',
    targets: { scope: 'selected', content_ids: [contentId] },
  })
})

test('keeps export history visible but disables empty query export creation', async ({ page }) => {
  await page.unroute('**/api/v1/contents**')
  await page.route('**/api/v1/contents**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [], next_cursor: null, has_more: false }),
    })
  })

  await page.goto('/voice-plaza')
  await expect(page.getByRole('button', { name: /AI 打标/ })).toBeDisabled()
  await page.getByRole('button', { name: /导出记录/ }).click()
  const dialog = page.getByRole('dialog', { name: '导出声音记录' })
  await expect(dialog.getByText('当前筛选没有可导出内容')).toBeVisible()
  await expect(dialog.getByRole('radio', { name: /全部查询结果/ })).toBeDisabled()
  await expect(dialog.getByRole('button', { name: '创建 Excel 导出' })).toBeDisabled()
  await expect(dialog.getByText('最近导出记录')).toBeVisible()
  await expect(dialog.getByRole('progressbar', { name: '导出 72345678 进度' })).toHaveAttribute('aria-valuenow', '64')
})
