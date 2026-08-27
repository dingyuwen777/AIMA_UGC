import { expect, test } from '@playwright/test'

const batchId = '12345678-1234-5678-1234-567812345678'
const importJobId = '22345678-1234-5678-1234-567812345678'
const contentId = '32345678-1234-5678-1234-567812345678'
const exportId = '42345678-1234-5678-1234-567812345678'
const exportJobId = '52345678-1234-5678-1234-567812345678'

const importDetail = {
  id: batchId,
  input_artifact_id: '62345678-1234-5678-1234-567812345678',
  source_filename: '爱玛导入.xlsx',
  status: 'cancelled',
  stage: 'reading',
  stats: {
    rows_seen: 10,
    rows_matched: 9,
    rows_filtered_out: 1,
    duplicates_removed: 0,
    rows_ingested: 0,
    rows_rejected: 0,
  },
  error_summary: null,
  created_at: '2099-01-01T00:00:00Z',
  started_at: '2099-01-01T00:00:01Z',
  finished_at: null,
  job: {
    id: importJobId,
    job_type: 'ingestion.import-excel.v1',
    status: 'cancelled',
    attempt: 1,
    max_attempts: 10,
    progress: 40,
    error_code: null,
    result: null,
    created_at: '2099-01-01T00:00:00Z',
    started_at: '2099-01-01T00:00:01Z',
    finished_at: '2099-01-01T00:01:00Z',
  },
}

const runtimeItem = {
  record_id: batchId,
  record_type: 'excel_import',
  display_name: '爱玛导入.xlsx',
  source_filename: '爱玛导入.xlsx',
  import_batch_id: batchId,
  collection_run_id: null,
  job_id: importJobId,
  status: 'cancelled',
  stage: 'reading',
  progress: 40,
  import_stats: importDetail.stats,
  collection_stats: null,
  platforms: [],
  keywords: [],
  created_at: importDetail.created_at,
  started_at: importDetail.started_at,
  finished_at: importDetail.job.finished_at,
  error_code: null,
  error_summary: null,
}

const content = {
  id: contentId,
  platform: 'xiaohongshu',
  external_content_id: 'note-retention',
  content_type: 'note',
  title: '爱玛用户体验',
  text: '用于 Artifact retention UI 验收。',
  author_display_name: '保留策略测试用户',
  published_at: '2099-01-01T00:00:00Z',
  last_seen_at: '2099-01-01T00:00:00Z',
  content_url: 'https://example.com/note-retention',
  metrics: { like_count: 1, comment_count: 0, share_count: 0 },
  analysis: {
    status: 'completed',
    sentiment: '中性',
    labels: [],
    analyzed_at: '2099-01-01T00:00:30Z',
    model_provider: 'fixture',
    model: 'fixture-model',
  },
  source: { provider_name: 'file-import', import_batch_id: batchId },
}

const completedExport = {
  id: exportId,
  job: {
    id: exportJobId,
    job_type: 'reporting.content-export-excel.v1',
    status: 'succeeded',
    attempt: 1,
    max_attempts: 3,
    progress: 100,
    error_code: null,
    result: {
      export_id: exportId,
      artifact_id: '72345678-1234-5678-1234-567812345678',
      content_count: 1,
      analyzed_count: 1,
      unanalyzed_count: 0,
      comment_count: 0,
    },
    created_at: '2099-01-01T00:00:00Z',
    started_at: '2099-01-01T00:00:01Z',
    finished_at: '2099-01-01T00:01:00Z',
  },
  artifact_id: '72345678-1234-5678-1234-567812345678',
  filename: `aima-ugc-voice-plaza-${exportId}.xlsx`,
  stats: { content_count: 1, analyzed_count: 1, unanalyzed_count: 0, comment_count: 0 },
  created_at: '2099-01-01T00:00:00Z',
  completed_at: '2099-01-01T00:01:00Z',
}

test('shows Excel import source retention from terminal Job time when Batch time is absent', async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname === '/api/v1/collection-runtime/summary') {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          processing_count: 0,
          completed_today_count: 1,
          contents_ingested_today: 0,
          as_of: '2099-01-01T00:02:00Z',
        }),
      })
    }
    if (url.pathname === '/api/v1/collection-runtime/runs') {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ items: [runtimeItem], next_cursor: null, has_more: false }),
      })
    }
    if (url.pathname === '/api/v1/collection-capabilities') {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ provider_configs: [], capabilities: [] }),
      })
    }
    if (url.pathname === '/api/v1/import-batches') {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ items: [importDetail], next_cursor: null, has_more: false }),
      })
    }
    if (url.pathname === `/api/v1/import-batches/${batchId}`) {
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify(importDetail) })
    }
    await route.fulfill({ status: 404, body: 'not mocked' })
  })

  await page.goto('/collection-runtime')
  await page.getByRole('button', { name: '查看详情' }).click()
  const detail = page.getByRole('dialog', { name: '批次详情' })

  await expect(detail.getByText(/源 Excel 保留至/)).toBeVisible()
  await expect(detail.getByText(/到期后只清理文件字节/)).toBeVisible()
})

test('shows the seven-day Excel export window in the existing export dialog', async ({ page }) => {
  await page.route('**/api/v1/content-analysis-capabilities', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ configured: true }) })
  })
  await page.route('**/api/v1/contents**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [content], next_cursor: null, has_more: false }),
    })
  })
  await page.route('**/api/v1/analysis/content-runs**', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ items: [] }) })
  })
  await page.route('**/api/v1/data-exports**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname === `/api/v1/data-exports/${exportId}`) {
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify(completedExport) })
    }
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [completedExport] }),
    })
  })

  await page.goto('/voice-plaza')
  await page.getByRole('button', { name: /导出记录/ }).click()
  const dialog = page.getByRole('dialog', { name: '导出声音记录' })

  await expect(dialog).toBeVisible()
  await expect(dialog.getByText(/Excel 导出文件自生成完成后保留 7 天/)).toBeVisible()
  await expect(dialog.getByText(/下载有效期至/)).toBeVisible()
  await expect(dialog.getByRole('button', { name: '下载' })).toBeEnabled()
})
