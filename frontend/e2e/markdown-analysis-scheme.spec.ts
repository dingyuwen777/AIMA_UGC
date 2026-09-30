import { readFileSync } from 'node:fs'
import type { AnalysisSchemeResponse } from '../src/generated/api/client'
import { expect, test } from './fixture'

const prompt = readFileSync(new URL('../../backend/src/aima_ugc/modules/analysis/prompts/content_labeling.md', import.meta.url), 'utf8')
const schemeId = '91111111-1111-4111-8111-111111111111'
const versionId = '92111111-1111-4111-8111-111111111111'
const draftId = '93111111-1111-4111-8111-111111111111'
const now = '2026-09-30T10:00:00+08:00'

test('Markdown 导入、保存错误、只读编译预览及发布走公开管理入口', async ({ page }) => {
  const state: AnalysisSchemeResponse = {
    id: schemeId, name: '文档规则验收', is_active: true, active_version_id: versionId,
    created_at: now, updated_at: now, versions: [{
      id: versionId, scheme_id: schemeId, version: 1, status: 'published', description: '原版本',
      definition: { prompt_template: prompt, voice_types: ['真实用户发声'], sentiments: ['正面'], labels: { 骑行性能: ['舒适性'] } },
      prompt_sha256: 'a'.repeat(64), taxonomy_sha256: 'b'.repeat(64), created_at: now, created_by: 'test',
    }],
  }
  let saved = 0
  let published = false
  await page.route('**/api/v1/analysis-schemes', async (route) => {
    if (route.request().method() === 'GET') return route.fulfill({ json: { items: [state] } })
    const request = route.request().postDataJSON() as { definition: { prompt_template: string } }
    expect(Object.keys(request.definition)).toEqual(['prompt_template'])
    expect(request.definition.prompt_template).toContain('积极')
    saved += 1
    if (saved === 1) return route.fulfill({ status: 422, json: { status: 422, detail: '行 12：定义表分类重复', request_id: 'markdown-compile' } })
    const draft = { ...state.versions[0]!, id: draftId, version: 2, status: 'draft' as const,
      definition: { prompt_template: request.definition.prompt_template, voice_types: ['真实用户发声'], sentiments: ['积极'], labels: { 骑行性能: ['舒适性'] } },
    }
    state.versions.push(draft)
    return route.fulfill({ status: 201, json: state })
  })
  await page.route(`**/api/v1/analysis-scheme-versions/${draftId}/publish`, async (route) => {
    published = true
    state.active_version_id = draftId
    state.versions[1]!.status = 'published'
    return route.fulfill({ json: state })
  })
  await page.goto('/admin/configuration')
  await page.getByRole('button', { name: 'AI 分析规则', exact: true }).click()
  const revisedPrompt = prompt.replaceAll('正面', '积极')
  await page.getByLabel('导入提示词文档').setInputFiles({ name: 'rules.md', mimeType: 'text/markdown', buffer: Buffer.from(revisedPrompt) })
  const markdownEditor = page.getByLabel('提示词 Markdown')
  await expect(markdownEditor).toHaveValue(/积极/)
  await markdownEditor.fill(revisedPrompt.replace('<!-- AIMA_TABLE: voice_types -->', '<!-- AIMA_TABLE: broken -->'))
  await page.getByRole('button', { name: '基于此版本新建草稿', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('行 12：定义表分类重复')
  await expect(markdownEditor).toBeVisible()
  await expect(markdownEditor).toHaveValue(/AIMA_TABLE: broken/)
  expect(published).toBe(false)
  await markdownEditor.fill(revisedPrompt)
  await page.getByRole('button', { name: '基于此版本新建草稿', exact: true }).click()
  await expect(page.getByText('AI 分析规则草稿已保存并记录操作。', { exact: true })).toBeVisible()
  await page.getByText('已保存草稿的编译结果（只读）', { exact: true }).click()
  await expect(page.locator('.taxonomy-preview')).toContainText('积极')
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: '发布', exact: true }).click()
  await expect(page.getByText('AI 分析规则已发布并记录操作。', { exact: true })).toBeVisible()
  expect(published).toBe(true)
})
