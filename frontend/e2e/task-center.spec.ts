import { expect, test } from './fixture'

import { stubVoicePlazaTaxonomy } from './voicePlazaTaxonomy'

const analysisRunId = '71345678-1234-5678-1234-567812345678'

const analysisRun = {
  id: analysisRunId,
  planner_job_id: '72345678-1234-5678-1234-567812345678',
  sequence_no: 21,
  status: 'running',
  run_intent: 'manual_reanalysis',
  scope: 'selected',
  target_count: 100,
  shard_count: 2,
  shard_size: 50,
  prompt_version: 'content_labeling_v3',
  prompt_sha256: 'a'.repeat(64),
  taxonomy_sha256: 'b'.repeat(64),
  model_provider: 'openai-compatible',
  model: 'fixture-model',
  generation_config: { temperature: 0 },
  generation_config_hash: 'c'.repeat(64),
  stats: { pending: 50, succeeded: 48, failed: 2, cancelled: 0, stale: 0 },
  shards: [
    { request_id: '73345678-1234-5678-1234-567812345678', job_id: '74345678-1234-5678-1234-567812345678', shard_no: 0, target_count: 50, status: 'succeeded', progress: 100, error_code: null },
    { request_id: '75345678-1234-5678-1234-567812345678', job_id: '76345678-1234-5678-1234-567812345678', shard_no: 1, target_count: 50, status: 'running', progress: 0, error_code: null },
  ],
  created_at: '2026-09-03T10:00:00Z',
  started_at: '2026-09-03T10:00:05Z',
  finished_at: null,
}

const collectionRun = {
  record_id: '77345678-1234-5678-1234-567812345678',
  record_type: 'tikhub_discovery',
  display_name: '爱玛关键词采集',
  job_id: '78345678-1234-5678-1234-567812345678',
  collection_run_id: '79345678-1234-5678-1234-567812345678',
  import_batch_id: null,
  status: 'running',
  stage: 'discovering',
  progress: 36,
  created_at: '2026-09-03T09:55:00Z',
  started_at: '2026-09-03T09:55:03Z',
  finished_at: null,
  platforms: ['xiaohongshu'],
  keywords: ['爱玛'],
  collection_stats: {
    content_count: 120,
    comment_count: 36,
    requested_count: 160,
    succeeded_count: 120,
    failed_count: 4,
    filtered_count: 36,
  },
}

const exportRun = {
  id: '80345678-1234-5678-1234-567812345678',
  job: {
    id: '81345678-1234-5678-1234-567812345678',
    job_type: 'reporting.content-export-excel.v1',
    status: 'running',
    attempt: 1,
    max_attempts: 3,
    progress: 64,
    error_code: null,
    result: null,
    created_at: '2026-09-03T09:50:00Z',
    started_at: '2026-09-03T09:50:02Z',
    finished_at: null,
  },
  artifact_id: null,
  filename: null,
  stats: null,
  created_at: '2026-09-03T09:50:00Z',
  completed_at: null,
}

test.beforeEach(async ({ page }) => {
  await stubVoicePlazaTaxonomy(page)
  await page.route('**/api/v1/content-analysis-capabilities', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ configured: true }) })
  })
  await page.route('**/api/v1/contents**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [], next_cursor: null, has_more: false }),
    })
  })
  await page.route('**/api/v1/analysis/content-runs**', async (route) => {
    const url = new URL(route.request().url())
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(url.pathname === `/api/v1/analysis/content-runs/${analysisRunId}`
        ? analysisRun
        : { items: [analysisRun] }),
    })
  })
  await page.route('**/api/v1/collection-runtime/runs**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [collectionRun], next_cursor: null, has_more: false }),
    })
  })
  await page.route('**/api/v1/data-exports**', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ items: [exportRun] }) })
  })
})

test('从声音广场打开全局任务中心并统一查看三类活动任务', async ({ page }) => {
  await page.goto('/voice-plaza')

  const taskTrigger = page.getByRole('button', { name: /任务中心/ })
  await expect(taskTrigger).toBeVisible()
  await expect(taskTrigger).toContainText('3')
  await expect(page.getByRole('button', { name: '站内通知' })).toBeVisible()
  await expect(page.getByText('AI Analysis Run 历史')).toHaveCount(0)
  await expect(page.getByText('AI 打标任务')).toBeVisible()

  await taskTrigger.click()
  const drawer = page.getByRole('complementary', { name: '任务中心' })
  await expect(drawer).toBeVisible()
  await expect(drawer.getByText('AI 打标 · Run #21')).toBeVisible()
  await expect(drawer.getByText('爱玛关键词采集')).toBeVisible()
  await expect(drawer.getByText('Excel 导出')).toBeVisible()
  await expect(drawer.getByText('3 个')).toBeVisible()
  await expect(drawer.getByText('TikHub 采集 · 小红书')).toBeVisible()
  await expect(drawer.getByRole('link', { name: '查看' })).toHaveCount(3)

  await drawer.getByRole('button', { name: '关闭任务中心' }).click()
  await page.getByRole('button', { name: '站内通知' }).click()
  await expect(page.getByText('消息中心')).toBeVisible()
  await expect(page.getByRole('complementary', { name: '任务中心' })).toHaveCount(0)
})